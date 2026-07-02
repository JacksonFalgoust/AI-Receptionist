"""Twilio Conversation Relay <-> GuideAnts voice receptionist middleware.

POST /twiml   Twilio calls this when a call comes in; returns TwiML that opens
              a Conversation Relay WebSocket back to this server.
WS   /ws      Conversation Relay's WebSocket bridge: receives transcribed
              caller speech and streams the GuideAnts guide's reply back as
              speakable text tokens.

Barge-in model: Twilio pauses TTS playback the instant it hears caller speech
(`interruptible="speech"`) and reports it as an "interrupt" message. Rather
than treating every interrupt as a hard stop, this handler *pauses* the
in-flight reply and waits for the caller's transcribed utterance (the
following "prompt" message) to decide whether to actually stop (a stop
command or a question) or resume speaking (a filler, backchannel, or noise).
See barge_in.py for the classification heuristics and ARCHITECTURE.md for the
full state machine.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from twilio.twiml.voice_response import Connect, VoiceResponse

import barge_in
import config
from guide_client import stream_reply

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice_receptionist")

app = FastAPI()


@app.post("/twiml")
async def twiml(request: Request) -> Response:
    """Return TwiML that connects the call to our Conversation Relay WebSocket."""
    host = request.headers.get("host", request.url.hostname)

    vr = VoiceResponse()
    connect = Connect()
    connect.conversation_relay(
        url=f"wss://{host}/ws",
        welcome_greeting=config.WELCOME_GREETING,
        tts_provider="ElevenLabs",
        transcription_provider="Deepgram",
        interruptible="speech",
        report_input_during_agent_speech="speech",
    )
    vr.append(connect)

    return Response(content=str(vr), media_type="application/xml")


@dataclass
class PendingBargeIn:
    """An "interrupt" that hasn't yet been resolved by a follow-up prompt."""

    heard: str
    task_was_done: bool


@dataclass
class CallState:
    messages: list = field(default_factory=list)
    task: object = None  # asyncio.Task | None
    gate: asyncio.Event = field(default_factory=asyncio.Event)  # set = flowing, cleared = paused
    cycle_text: str = ""  # all text handed to Twilio for the current talk cycle
    cycle_base: str = ""  # text confirmed-spoken in earlier segments of this reply
    pending: object = None  # PendingBargeIn | None
    resume_timer: object = None  # asyncio.Task | None


@app.websocket("/ws")
async def conversation_relay_ws(websocket: WebSocket) -> None:
    await websocket.accept()

    st = CallState()
    st.gate.set()
    # The welcome greeting is spoken by Twilio directly from the TwiML
    # attribute and never crosses the WebSocket, but a caller can still barge
    # into it. Seeding cycle_text lets that case fall out of the normal
    # pause/resume machinery for free.
    st.cycle_text = config.WELCOME_GREETING

    async def respond_to() -> None:
        reply_text = ""
        try:
            async for delta in stream_reply(st.messages):
                await st.gate.wait()
                await websocket.send_json({"type": "text", "token": delta, "last": False})
                reply_text += delta
                st.cycle_text += delta
            await st.gate.wait()
            await websocket.send_json({"type": "text", "token": "", "last": True})
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Error while streaming guide reply")
            try:
                await websocket.send_json(
                    {
                        "type": "text",
                        "token": "Sorry, I'm having trouble right now.",
                        "last": True,
                    }
                )
            except Exception:
                pass
            return
        if reply_text:
            st.messages.append({"role": "assistant", "content": reply_text})

    def start_reply(user_text: str) -> None:
        st.messages.append({"role": "user", "content": user_text})
        st.cycle_text = ""
        st.cycle_base = ""
        st.gate.set()
        st.task = asyncio.create_task(respond_to())

    async def _cancel_and_await(task) -> None:
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def cancel_task() -> None:
        t, st.task = st.task, None
        await _cancel_and_await(t)

    async def resume(pend: PendingBargeIn) -> None:
        spoken, remainder = barge_in.split_spoken(st.cycle_text, pend.heard)
        if st.task is not None and not st.task.done():
            # Still streaming, parked at the gate. Twilio discarded the
            # unplayed tail; re-supply it, then reopen the gate. The send
            # must complete before gate.set() so a fresh delta can't
            # interleave ahead of the remainder.
            if remainder:
                await websocket.send_json({"type": "text", "token": remainder, "last": False})
            st.gate.set()
        else:
            # Reply already fully generated (or this is the greeting) but
            # TTS was still playing when the barge happened. The old cycle
            # is over at Twilio; the remainder starts a brand-new cycle.
            if remainder:
                st.cycle_base += spoken
                st.cycle_text = remainder
                await websocket.send_json({"type": "text", "token": remainder, "last": True})
            st.gate.set()

    async def stop_and_restart(pend: PendingBargeIn, user_text: str) -> None:
        await cancel_task()
        heard_total = st.cycle_base + pend.heard
        if pend.task_was_done and st.messages and st.messages[-1].get("role") == "assistant":
            if heard_total:
                st.messages[-1]["content"] = heard_total
            else:
                st.messages.pop()
        elif heard_total:
            st.messages.append({"role": "assistant", "content": heard_total})
        start_reply(user_text)

    async def cancel_resume_timer() -> None:
        t, st.resume_timer = st.resume_timer, None
        await _cancel_and_await(t)

    async def restart_resume_timer() -> None:
        await cancel_resume_timer()
        st.resume_timer = asyncio.create_task(auto_resume())

    async def auto_resume() -> None:
        await asyncio.sleep(config.BARGE_IN_RESUME_TIMEOUT_S)
        pend, st.pending = st.pending, None
        if pend is not None:
            logger.info("No prompt after interrupt; auto-resuming")
            await resume(pend)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Received non-JSON WS frame: %r", raw)
                continue

            msg_type = msg.get("type")

            if msg_type == "setup":
                logger.info(
                    "Call setup: callSid=%s from=%s to=%s",
                    msg.get("callSid"),
                    msg.get("from"),
                    msg.get("to"),
                )

            elif msg_type == "prompt":
                text = msg.get("voicePrompt", "") or ""
                # Cancel and fully await any in-flight auto-resume before touching
                # st.pending/st.cycle_text/st.gate — otherwise a resume() triggered
                # by the timer could still be mid-flight (suspended on a send) and
                # clobber state after this handler has already moved the call on to
                # a new talk cycle.
                await cancel_resume_timer()
                pend, st.pending = st.pending, None
                if pend is not None:
                    if text.strip() and barge_in.should_stop_reply(
                        text, config.BARGE_IN_EXTRA_STOP_PHRASES
                    ):
                        await stop_and_restart(pend, text)
                    else:
                        await resume(pend)
                elif text.strip():
                    if st.task and not st.task.done():
                        if barge_in.should_stop_reply(text, config.BARGE_IN_EXTRA_STOP_PHRASES):
                            await cancel_task()
                            if st.cycle_text:
                                st.messages.append(
                                    {
                                        "role": "assistant",
                                        "content": st.cycle_base + st.cycle_text,
                                    }
                                )
                            start_reply(text)
                        else:
                            logger.info("Ignoring non-stop prompt during active reply: %r", text)
                    else:
                        start_reply(text)

            elif msg_type == "interrupt":
                # `or ""` guards against Twilio sending an explicit JSON null
                # (key present, value null) rather than omitting the key --
                # `.get(..., "")`'s default only covers the latter.
                heard = msg.get("utteranceUntilInterrupt") or ""
                was_done = st.task is None or st.task.done()
                st.gate.clear()
                st.pending = PendingBargeIn(heard=heard, task_was_done=was_done)
                await restart_resume_timer()

            elif msg_type == "dtmf":
                logger.info("DTMF digit: %s", msg.get("digit"))

            elif msg_type == "error":
                logger.error("Conversation Relay error: %s", msg.get("description"))

            else:
                logger.warning("Unhandled message type: %s", msg_type)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    finally:
        await cancel_resume_timer()
        await cancel_task()
