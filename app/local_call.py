"""One turn of the local audio demo: the caller's recording in, spoken reply
out.

Deliberately free of FastAPI and TwiML so the whole pipeline can be tested
through a single seam -- app/local_demo_api.py does nothing but turn a
TurnResult into TwiML.

The guide itself is reused unchanged from the Conversation Relay demo:
stream_reply() is drained to completion instead of being forwarded token by
token, which keeps the final-answer sentinel gate, the Booqable client-side
tools, and conversation-id continuation working exactly as they do on /ws.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Literal

from . import config, local_audio_client
from .guide_client import Delta, GuideSession, stream_reply
from .recording_fetch import fetch_recording_wav

logger = logging.getLogger("voice_receptionist")

Outcome = Literal["ok", "no_speech", "error", "timeout"]


@dataclass(frozen=True)
class TurnResult:
    transcript: str  # what the caller said; "" when nothing was heard
    reply_text: str  # what will be spoken -- the guide's answer, or a fallback
    reply_wav: bytes | None  # None only if even the fallback couldn't be synthesized
    outcome: Outcome


def _fallback_phrase(outcome: Outcome) -> str:
    if outcome == "no_speech":
        return config.LOCAL_NO_SPEECH_PHRASE
    if outcome == "timeout":
        return config.LOCAL_TIMEOUT_PHRASE
    return config.LOCAL_ERROR_PHRASE


async def _with_fallback_audio(result: TurnResult) -> TurnResult:
    """Give a failed turn something to say. Synthesized outside the turn
    budget: the phrase is short, and a caller hearing nothing at all would
    have no idea the line is still open."""
    phrase = _fallback_phrase(result.outcome)
    try:
        wav = await local_audio_client.synthesize(phrase)
    except Exception:
        logger.warning("Fallback speech synthesis failed", exc_info=True)
        return result
    return TurnResult(result.transcript, phrase, wav, result.outcome)


async def _pipeline(recording_url: str, session: GuideSession) -> TurnResult:
    wav = await fetch_recording_wav(recording_url)
    transcript = await local_audio_client.transcribe(wav)
    if not transcript.strip():
        return TurnResult("", "", None, "no_speech")

    parts: list[str] = []
    async for event in stream_reply(transcript, session):
        if isinstance(event, Delta):
            parts.append(event.text)
    reply_text = "".join(parts).strip()

    if not reply_text:
        # The gate never opened, or the guide answered with nothing at all.
        logger.warning("Guide produced no speakable text for %r", transcript)
        return TurnResult(transcript, "", None, "error")

    return TurnResult(transcript, reply_text, await local_audio_client.synthesize(reply_text), "ok")


async def run_turn(recording_url: str, session: GuideSession) -> TurnResult:
    """Run one turn under a hard deadline. Never raises: every failure comes
    back as a non-"ok" outcome carrying audio to speak, because the caller is
    on the line and the router must always return TwiML."""
    try:
        async with asyncio.timeout(config.LOCAL_TURN_BUDGET_SECONDS):
            result = await _pipeline(recording_url, session)
    except TimeoutError:
        logger.warning(
            "Local turn exceeded its %ss budget", config.LOCAL_TURN_BUDGET_SECONDS
        )
        result = TurnResult("", "", None, "timeout")
    except Exception:
        logger.warning("Local turn failed", exc_info=True)
        result = TurnResult("", "", None, "error")

    if result.outcome == "ok":
        return result
    return await _with_fallback_audio(result)


async def no_speech_turn() -> TurnResult:
    """A turn with nothing to transcribe -- Twilio's callback carried no
    RecordingUrl, e.g. the caller stayed silent through the whole <Record>."""
    return await _with_fallback_audio(TurnResult("", "", None, "no_speech"))
