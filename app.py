"""Twilio Conversation Relay <-> GuideAnts voice receptionist middleware.

POST /twiml   Twilio calls this when a call comes in; returns TwiML that opens
              a Conversation Relay WebSocket back to this server.
WS   /ws      Conversation Relay's WebSocket bridge: receives transcribed
              caller speech and streams the GuideAnts guide's reply back as
              speakable text tokens.
"""

import asyncio
import json
import logging

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from twilio.twiml.voice_response import Connect, VoiceResponse

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


@app.websocket("/ws")
async def conversation_relay_ws(websocket: WebSocket) -> None:
    await websocket.accept()

    messages: list[dict] = []
    state = {"task": None}

    async def respond_to(user_text: str) -> None:
        messages.append({"role": "user", "content": user_text})
        reply_text = ""
        try:
            async for delta in stream_reply(messages):
                reply_text += delta
                await websocket.send_json({"type": "text", "token": delta, "last": False})
            await websocket.send_json({"type": "text", "token": "", "last": True})
            if reply_text:
                messages.append({"role": "assistant", "content": reply_text})
        except asyncio.CancelledError:
            # Caller interrupted mid-reply; record only what was actually spoken
            # so far, then let the "interrupt" handler correct it further.
            if reply_text:
                messages.append({"role": "assistant", "content": reply_text})
            raise
        except Exception:
            logger.exception("Error while streaming guide reply")
            await websocket.send_json(
                {
                    "type": "text",
                    "token": "Sorry, I'm having trouble right now.",
                    "last": True,
                }
            )

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
                user_text = msg.get("voicePrompt", "")
                if user_text:
                    if state["task"] and not state["task"].done():
                        state["task"].cancel()
                    state["task"] = asyncio.create_task(respond_to(user_text))

            elif msg_type == "interrupt":
                if state["task"] and not state["task"].done():
                    state["task"].cancel()
                heard = msg.get("utteranceUntilInterrupt", "")
                if heard and messages and messages[-1].get("role") == "assistant":
                    messages[-1]["content"] = heard
                elif heard:
                    messages.append({"role": "assistant", "content": heard})

            elif msg_type == "dtmf":
                logger.info("DTMF digit: %s", msg.get("digit"))

            elif msg_type == "error":
                logger.error("Conversation Relay error: %s", msg.get("description"))

            else:
                logger.warning("Unhandled message type: %s", msg_type)

    except WebSocketDisconnect:
        if state["task"] and not state["task"].done():
            state["task"].cancel()
        logger.info("WebSocket disconnected")
