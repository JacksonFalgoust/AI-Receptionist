"""GuideAnts' OpenAI-compatible audio endpoints, used by the local audio demo
(app/local_demo_api.py) in place of Conversation Relay's built-in Deepgram
transcription and ElevenLabs speech.

Both endpoints are request/response, not streaming: a whole utterance goes in
and a whole reply comes out. That is why the local demo is turn-based
(<Record> / <Play>) rather than a live bridge like /ws.
"""

from __future__ import annotations

from typing import Any

import httpx

from . import config


class GuideAudioError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _base_url() -> str:
    if not config.GUIDEANTS_PUB_ID:
        raise GuideAudioError(
            "GUIDEANTS_PUB_ID is not set. Copy .env.example to .env and fill it in."
        )
    return f"{config.GUIDEANTS_BASE_URL}/api/published/openai/{config.GUIDEANTS_PUB_ID}/v1"


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {config.GUIDEANTS_API_KEY or 'anonymous'}"}


async def transcribe(wav: bytes) -> str:
    """Caller audio -> text.

    The upload's filename extension is significant: GuideAnts dispatches on it
    and rejects an unrecognized one with `provider_not_ready`, so the file part
    is always named audio.wav regardless of where the bytes came from.
    """
    url = f"{_base_url()}/audio/transcriptions"
    async with httpx.AsyncClient(timeout=config.GUIDEANTS_TIMEOUT_SECONDS) as client:
        response = await client.post(
            url,
            headers=_headers(),
            files={"file": ("audio.wav", wav, "audio/wav")},
            data={"model": config.GUIDEANTS_TRANSCRIPTION_MODEL},
        )

    if response.status_code >= 400:
        raise GuideAudioError(
            f"GuideAnts transcription failed ({response.status_code}): {response.text[:200]}",
            status_code=response.status_code,
        )

    try:
        body = response.json()
    except Exception as exc:
        raise GuideAudioError("GuideAnts transcription returned a non-JSON body") from exc

    text = body.get("text") if isinstance(body, dict) else None
    if not isinstance(text, str):
        raise GuideAudioError(f"GuideAnts transcription returned no text: {body!r}")
    return text.strip()


async def synthesize(text: str) -> bytes:
    """Reply text -> spoken WAV bytes, ready to serve to Twilio's <Play>."""
    url = f"{_base_url()}/audio/speech"
    payload: dict[str, Any] = {
        "model": config.GUIDEANTS_SPEECH_MODEL,
        "input": text,
        "responseFormat": "wav",
    }
    if config.GUIDEANTS_SPEECH_VOICE:
        payload["voice"] = config.GUIDEANTS_SPEECH_VOICE

    async with httpx.AsyncClient(timeout=config.GUIDEANTS_TIMEOUT_SECONDS) as client:
        response = await client.post(url, headers=_headers(), json=payload)

    if response.status_code >= 400:
        raise GuideAudioError(
            f"GuideAnts speech failed ({response.status_code}): {response.text[:200]}",
            status_code=response.status_code,
        )
    if not response.content:
        raise GuideAudioError("GuideAnts speech returned empty audio")
    return response.content
