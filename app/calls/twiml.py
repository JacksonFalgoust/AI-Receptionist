"""POST /twiml: Twilio calls this when a call comes in; returns TwiML that
opens a Conversation Relay WebSocket back to /ws (see relay.py)."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, Response
from twilio.twiml.voice_response import Connect, VoiceResponse

from app import config

from . import twilio_auth
from .greeting import greeting_for

router = APIRouter()

_WORKING_SOUND_FILE = Path(__file__).resolve().parent.parent / "static" / "working.mp3"


@router.get(config.WORKING_SOUND_PATH)
async def working_sound() -> FileResponse:
    """Public, static, non-sensitive: the soft 'working' loop Twilio fetches."""
    return FileResponse(_WORKING_SOUND_FILE, media_type="audio/mpeg")


@router.post("/twiml")
async def twiml(request: Request) -> Response:
    """Return TwiML that connects the call to our Conversation Relay WebSocket."""
    if not await twilio_auth.validate_twiml_request(request):
        return Response(status_code=403)

    host = request.headers.get("host", request.url.hostname)
    form = await request.form()
    call_sid = form.get("CallSid", "")
    token = twilio_auth.mint_ws_token(call_sid)
    greeting = await greeting_for(form.get("From", ""))

    vr = VoiceResponse()
    connect = Connect()
    connect.conversation_relay(
        url=f"wss://{host}/ws?token={token}",
        welcome_greeting=greeting,
        tts_provider="ElevenLabs",
        transcription_provider="Deepgram",
        **({"hints": config.STT_HINTS} if config.STT_HINTS else {}),
        speech_model=config.STT_SPEECH_MODEL,
        language=config.STT_LANGUAGE,
        interruptible="none",
        # The welcome greeting has its own interruptibility setting, separate
        # from `interruptible` -- without this, Twilio cuts the greeting off
        # whenever it detects caller-side audio during it (including echo of
        # the greeting itself picked up on speakerphone) and sends an
        # `interrupt` message. Observed on real calls before this was set.
        welcome_greeting_interruptible="none",
        report_input_during_agent_speech="speech",
        events="speaker-events",
    )
    vr.append(connect)
    # Reached when the app ends the ConversationRelay session (endCall).
    vr.hangup()

    return Response(content=str(vr), media_type="application/xml")
