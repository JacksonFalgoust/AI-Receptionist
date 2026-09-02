"""Local audio demo: a phone call answered entirely with GuideAnts' own
speech models, with Twilio reduced to the phone line.

POST /local/twiml        Twilio's answer webhook -- greets, then starts recording.
POST /local/turn         <Record>'s action URL -- one turn, then records again.
GET  /local/audio/{id}   Serves one synthesized reply to Twilio's <Play>.

Unlike /twiml + /ws (Conversation Relay), Twilio does no transcription and no
speech synthesis here: it records the caller's turn, hands this app the audio,
and plays back whatever WAV it is pointed at. Turn-taking is Twilio's own
silence detection (<Record timeout>), so none of the barge-in, filler-phrase
or turn-buffering machinery in app/main.py applies -- and the caller cannot
interrupt a reply once it starts playing.

Setup and the GuideAnts-side model configuration: docs/LOCAL_AUDIO_DEMO.md.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from dataclasses import dataclass

from fastapi import APIRouter, Request
from fastapi.responses import Response
from twilio.twiml.voice_response import VoiceResponse

from . import config, local_audio_client, local_call, twilio_auth
from .greeting import greeting_for
from .guide_client import GuideSession

logger = logging.getLogger("voice_receptionist")

router = APIRouter()


@dataclass
class _CallSession:
    session: GuideSession
    touched: float


# Process-local, like the Conversation Relay demo's per-connection CallState:
# nothing is shared between calls and nothing is persisted.
_sessions: dict[str, _CallSession] = {}
# Synthesized audio waiting to be fetched by Twilio's player, keyed by an
# unguessable id. Popped on read -- see _serve_audio.
_audio: dict[str, tuple[bytes, float]] = {}
# Synthesized greetings, keyed by greeting text (the "welcome back" variants
# differ per caller). Kept for the process lifetime: the greeting is spoken on
# every single call, and re-synthesizing it just adds latency to answering.
_greetings: dict[str, bytes] = {}


def _sweep() -> None:
    now = time.monotonic()
    for call_sid, entry in list(_sessions.items()):
        if now - entry.touched > config.LOCAL_SESSION_TTL_SECONDS:
            _sessions.pop(call_sid, None)
    for audio_id, (_, created) in list(_audio.items()):
        if now - created > config.LOCAL_AUDIO_TTL_SECONDS:
            _audio.pop(audio_id, None)


def _session_for(call_sid: str, caller_phone: str) -> GuideSession:
    _sweep()
    entry = _sessions.get(call_sid)
    if entry is None:
        entry = _CallSession(
            session=GuideSession(caller_phone=caller_phone or None),
            touched=time.monotonic(),
        )
        _sessions[call_sid] = entry
    else:
        entry.touched = time.monotonic()
    return entry.session


def _store_audio(wav: bytes) -> str:
    audio_id = secrets.token_urlsafe(16)
    _audio[audio_id] = (wav, time.monotonic())
    return audio_id


def _turn_response(request: Request, wav: bytes | None) -> Response:
    """Play `wav` (when there is any) and record the caller's next turn.

    The <Play> URL is built from the request's Host header for the same reason
    /twiml builds its WebSocket URL that way: the tunnel's hostname changes
    between demos and must never be hardcoded.
    """
    vr = VoiceResponse()
    if wav:
        scheme = request.headers.get("x-forwarded-proto", "https")
        host = request.headers.get("host", request.url.hostname)
        vr.play(f"{scheme}://{host}/local/audio/{_store_audio(wav)}")
    vr.record(
        action="/local/turn",
        method="POST",
        timeout=config.LOCAL_RECORD_SILENCE_SECONDS,
        max_length=config.LOCAL_RECORD_MAX_SECONDS,
        play_beep=False,
        trim="trim-silence",
    )
    return Response(content=str(vr), media_type="application/xml")


@router.post("/local/twiml")
async def local_twiml(request: Request) -> Response:
    """Answer the call: speak the greeting, then record the first turn."""
    if not await twilio_auth.validate_twiml_request(request):
        return Response(status_code=403)

    form = await request.form()
    call_sid = form.get("CallSid", "")
    from_number = form.get("From", "")
    _session_for(call_sid, from_number)

    text = await greeting_for(from_number)
    wav = _greetings.get(text)
    if wav is None:
        try:
            # Bounded by its own budget, separate from LOCAL_TURN_BUDGET_SECONDS:
            # this runs after the (also bounded) caller lookup in greeting_for,
            # so an unbounded call here could stack on top of that elapsed time
            # and blow past Twilio's webhook timeout for /local/twiml.
            async with asyncio.timeout(config.LOCAL_FALLBACK_TTS_BUDGET_SECONDS):
                wav = await local_audio_client.synthesize(text)
            _greetings[text] = wav
        except Exception:
            # Answering the call matters more than greeting it: a silent but
            # working line beats a Twilio error.
            logger.warning("Greeting synthesis failed; answering silently", exc_info=True)
            wav = None

    return _turn_response(request, wav)


@router.post("/local/turn")
async def local_turn(request: Request) -> Response:
    """One turn: transcribe what the caller just said, answer it, speak the
    answer, and record again."""
    if not await twilio_auth.validate_twiml_request(request):
        return Response(status_code=403)

    form = await request.form()
    call_sid = form.get("CallSid", "")

    if form.get("Digits") == "hangup":
        _sessions.pop(call_sid, None)
        return Response(content=str(VoiceResponse()), media_type="application/xml")

    session = _session_for(call_sid, form.get("From", ""))
    recording_url = form.get("RecordingUrl", "")

    if recording_url:
        result = await local_call.run_turn(recording_url, session)
    else:
        logger.warning("No RecordingUrl on /local/turn for call %s", call_sid)
        result = await local_call.no_speech_turn()

    logger.info(
        "Local turn (%s) caller=%r reply=%r",
        result.outcome,
        result.transcript,
        result.reply_text[:80],
    )
    return _turn_response(request, result.reply_wav)


@router.get("/local/audio/{audio_id}")
async def serve_audio(audio_id: str) -> Response:
    """Serve one synthesized clip to Twilio's media player.

    This cannot be signature-validated -- Twilio fetches it as a plain GET --
    so it relies on an unguessable id, single-use eviction, and a short TTL.
    """
    entry = _audio.pop(audio_id, None)
    if entry is None:
        return Response(status_code=404)
    return Response(content=entry[0], media_type="audio/wav")
