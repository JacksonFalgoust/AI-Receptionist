"""Twilio Conversation Relay <-> GuideAnts voice receptionist middleware.

POST /twiml   Twilio calls this when a call comes in; returns TwiML that opens
              a Conversation Relay WebSocket back to this server.
WS   /ws      Conversation Relay's WebSocket bridge: receives transcribed
              caller speech and streams the GuideAnts guide's reply back as
              speakable text tokens.

Conversation Relay is configured `interruptible="none"`, so caller speech
never stops TTS playback; it still arrives here as "prompt" messages
(`report_input_during_agent_speech="speech"`) and is logged but not acted
on mid-reply. When a caller's utterance looks like a question or request
(see fillers.py), a short filler phrase is spoken immediately, before the
real GuideAnts reply, to mask lookup latency.

Only real user prompts and the guide's own replies go into `st.messages`.
Fillers, mid-reply interjections, and backchannel noise ("ok", "thanks")
are never added there, even though they're spoken/heard: GuideAnts matches
a follow-up request to its existing server-side conversation by replaying
our message history and checking it exactly aligns with what it actually
persisted (see WireConversationResolver.ResolveConversationFromTranscriptAsync
in the GuideAnts repo). Any local message that GuideAnts never saw --
a filler line, a swallowed interjection -- breaks that alignment and makes
GuideAnts start a brand-new conversation on the very next turn.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from twilio.twiml.voice_response import Connect, VoiceResponse

import config
import fillers
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


@app.websocket("/ws")
async def conversation_relay_ws(websocket: WebSocket) -> None:
    await websocket.accept()

    st = CallState()

    async def respond_to(filler: str | None) -> None:
        reply_text = ""
        try:
            if filler:
                await websocket.send_json({"type": "text", "token": filler + " ", "last": False})
            async for delta in stream_reply(st.messages):
                await websocket.send_json({"type": "text", "token": delta, "last": False})
                reply_text += delta
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
        # Only the real reply goes into st.messages -- never the filler.
        # GuideAnts matches a follow-up to its existing server-side
        # conversation by checking that our sent history exactly aligns with
        # what it actually persisted. It never sees the filler, so recording
        # it here would desync our local history from GuideAnts' and break
        # matching on the very next turn.
        if reply_text:
            st.messages.append({"role": "assistant", "content": reply_text})

    def start_reply(user_text: str) -> None:
        st.messages.append({"role": "user", "content": user_text})
        filler = fillers.pick(config.FILLER_PHRASES) if fillers.looks_like_question(user_text) else None
        st.task = asyncio.create_task(respond_to(filler))

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
