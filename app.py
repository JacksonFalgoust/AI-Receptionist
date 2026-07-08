"""Twilio Conversation Relay <-> GuideAnts voice receptionist middleware.

POST /twiml   Twilio calls this when a call comes in; returns TwiML that opens
              a Conversation Relay WebSocket back to this server.
WS   /ws      Conversation Relay's WebSocket bridge: receives transcribed
              caller speech and streams the GuideAnts guide's reply back as
              speakable text tokens.

Conversation Relay is configured `interruptible="none"`, so Twilio itself
never pauses TTS playback on caller speech; it still arrives here as
"prompt" messages (`report_input_during_agent_speech="speech"`). Most
mid-reply speech (statements, backchannel, noise) is logged but not acted
on. The exception is a trigger utterance -- a stop/wait phrase or a new
question, per barge_in.should_interrupt() -- which cancels the in-flight
reply. A stop/wait phrase (barge_in.is_stop_command()) then just gets a
short local acknowledgment (config.STOP_ACK_PHRASES) and silence -- never
routed through GuideAnts, so it cuts over immediately with no extra
round-trip and doesn't depend on the guide choosing to reply briefly. A new
question instead starts a fresh reply for what the caller just said, same
as any other prompt. Playback is actually cut over using Conversation
Relay's per-frame `preemptible` flag (see respond_to()), not Twilio-native
interruption. When a caller's utterance looks like a question or request
(see fillers.py) and GuideAnts' reply doesn't arrive within
config.FILLER_DELAY_SECONDS, a short filler phrase is spoken while still
waiting on the same in-flight call, to mask lookup latency.

Only real user prompts and the guide's own replies go into `st.messages`.
Fillers, stop acknowledgments, mid-reply interjections, and backchannel
noise ("ok", "thanks") are never added there, even though they're
spoken/heard: GuideAnts matches a follow-up request to its existing
server-side conversation by replaying our message history and checking it
exactly aligns with what it actually persisted (see
WireConversationResolver.ResolveConversationFromTranscriptAsync in the
GuideAnts repo). Any local message that GuideAnts never saw -- a filler
line, a stop acknowledgment, a swallowed interjection -- breaks that
alignment and makes GuideAnts start a brand-new conversation on the very
next turn.
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
import fillers
import speech_timing
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
        interruptible="none",
        report_input_during_agent_speech="speech",
    )
    vr.append(connect)

    return Response(content=str(vr), media_type="application/xml")


@dataclass
class CallState:
    messages: list = field(default_factory=list)
    task: object = None  # asyncio.Task | None
    partial_reply: str = ""  # real reply text streamed so far this turn (never the filler)


@app.websocket("/ws")
async def conversation_relay_ws(websocket: WebSocket) -> None:
    await websocket.accept()

    st = CallState()

    async def respond_to(filler_eligible: bool) -> None:
        # Every frame is marked preemptible so that if this turn is still
        # playing when a later trigger-interrupted turn starts, Twilio drops
        # this audio and switches to the new turn's audio immediately. This
        # is a no-op in the normal (non-interrupting) case, since by the
        # time a new turn starts normally the previous one has already
        # finished.
        start_time = asyncio.get_event_loop().time()
        reply_text = ""
        filler = None
        gen = stream_reply(st.messages)
        # Only utterances that look like a question/request (see fillers.py)
        # are filler-eligible at all. Among those, race GuideAnts' reply
        # against the filler delay: if it's already back within
        # FILLER_DELAY_SECONDS, skip the filler; otherwise speak one and keep
        # waiting on the same in-flight call.
        first_chunk = asyncio.ensure_future(gen.__anext__())
        try:
            if filler_eligible:
                done, _ = await asyncio.wait({first_chunk}, timeout=config.FILLER_DELAY_SECONDS)
                if first_chunk not in done:
                    filler = fillers.pick(config.FILLER_PHRASES)
                    if filler:
                        await websocket.send_json(
                            {"type": "text", "token": filler + " ", "last": False, "preemptible": True}
                        )
            try:
                first_delta = await first_chunk
            except StopAsyncIteration:
                first_delta = None
            if first_delta is not None:
                await websocket.send_json(
                    {"type": "text", "token": first_delta, "last": False, "preemptible": True}
                )
                reply_text += first_delta
                st.partial_reply = reply_text
            async for delta in gen:
                await websocket.send_json(
                    {"type": "text", "token": delta, "last": False, "preemptible": True}
                )
                reply_text += delta
                st.partial_reply = reply_text
            await websocket.send_json({"type": "text", "token": "", "last": True, "preemptible": True})
        except asyncio.CancelledError:
            first_chunk.cancel()
            raise
        except Exception:
            logger.exception("Error while streaming guide reply")
            try:
                await websocket.send_json(
                    {
                        "type": "text",
                        "token": "Sorry, I'm having trouble right now.",
                        "last": True,
                        "preemptible": True,
                    }
                )
            except Exception:
                pass
            return
        # Only the real reply goes into st.messages -- never the filler.
        # GuideAnts matches a follow-up to its existing server-side
        # conversation by checking that our sent history exactly aligns with
        # what it actually persisted. It never sees the filler, so recording
        # it here would desync our local history from GuideAnts' and break
        # matching on the very next turn.
        if reply_text:
            st.messages.append({"role": "assistant", "content": reply_text})
            # Cleared so a later barge-in cancellation (which lands during
            # the pacing sleep below, not during generation) doesn't re-append
            # this same content via the st.partial_reply check in the `prompt`
            # handler.
            st.partial_reply = ""
        # GuideAnts' endpoint is non-streaming, so the whole reply arrives and
        # is sent to Twilio in one shot -- this task would otherwise be marked
        # "done" well before Twilio actually finishes speaking it aloud,
        # making mid-reply caller speech look like it arrived after the reply
        # ended and incorrectly starting a brand-new turn. Hold the task open
        # for the estimated remaining speaking time instead.
        spoken_text = f"{filler} {reply_text}" if filler else reply_text
        estimated_duration = speech_timing.estimate_seconds(spoken_text, config.TTS_WORDS_PER_SECOND)
        remaining = estimated_duration - (asyncio.get_event_loop().time() - start_time)
        if remaining > 0:
            await asyncio.sleep(remaining)

    def start_reply(user_text: str) -> None:
        st.messages.append({"role": "user", "content": user_text})
        st.partial_reply = ""
        st.task = asyncio.create_task(respond_to(fillers.looks_like_question(user_text)))

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
                if text.strip():
                    if st.task and not st.task.done():
                        if barge_in.should_interrupt(text, config.EXTRA_STOP_PHRASES):
                            await cancel_task()
                            # Only the real reply text streamed so far goes
                            # into st.messages -- never the filler -- same
                            # invariant as a normal completed turn (see
                            # module docstring).
                            if st.partial_reply:
                                st.messages.append({"role": "assistant", "content": st.partial_reply})
                                st.partial_reply = ""
                            if barge_in.is_stop_command(text, config.EXTRA_STOP_PHRASES):
                                # Stop/wait means stop -- acknowledge locally
                                # and go silent rather than asking GuideAnts
                                # what to say next, which would both add a
                                # round-trip before playback cuts over and
                                # leave whether the turn actually ends up to
                                # the guide's own reply. Never sent through
                                # GuideAnts, so (like fillers) never recorded
                                # in st.messages either.
                                logger.info("Stop command heard during active reply -- cancelling and going silent: %r", text)
                                ack = fillers.pick(config.STOP_ACK_PHRASES)
                                if ack:
                                    await websocket.send_json(
                                        {"type": "text", "token": ack, "last": True, "preemptible": True}
                                    )
                            else:
                                logger.info("Interrupting active reply for a new question: %r", text)
                                start_reply(text)
                        else:
                            # Logged only, never added to st.messages: GuideAnts
                            # never receives or persists this utterance, so
                            # recording it locally would desync our history from
                            # GuideAnts' and break conversation matching on the
                            # next turn (see module docstring).
                            logger.info("Ignored caller speech during active reply (not acted on): %r", text)
                    elif fillers.is_backchannel(text, config.EXTRA_BACKCHANNEL_PHRASES):
                        # STT can finish transcribing a short "ok" after the
                        # reply has already finished playing, so this branch
                        # (not just the one above) also has to swallow pure
                        # acknowledgments -- otherwise a late "ok" looks like
                        # a brand-new prompt and gets its own guide reply.
                        # Also never added to st.messages, for the same
                        # reason as above.
                        logger.info("Ignored backchannel utterance (not acted on): %r", text)
                    else:
                        start_reply(text)

            elif msg_type == "interrupt":
                logger.info("Received interrupt message (unexpected with interruptible=none): %s", msg.get("utteranceUntilInterrupt"))

            elif msg_type == "dtmf":
                logger.info("DTMF digit: %s", msg.get("digit"))

            elif msg_type == "error":
                logger.error("Conversation Relay error: %s", msg.get("description"))

            else:
                logger.warning("Unhandled message type: %s", msg_type)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    finally:
        await cancel_task()
