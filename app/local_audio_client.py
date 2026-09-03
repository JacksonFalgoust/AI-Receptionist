"""GuideAnts' OpenAI-compatible audio endpoints, used by the local audio demo
(app/local_demo_api.py) in place of Conversation Relay's built-in Deepgram
transcription and ElevenLabs speech.

Both endpoints are request/response, not streaming: a whole utterance goes in
and a whole reply comes out. That is why the local demo is turn-based
(<Record> / <Play>) rather than a live bridge like /ws.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from httpx import RequestError  # bound at import time: see _post_with_retry

from . import config

# 5xx codes worth one retry: all of them mean "GuideAnts itself is the
# problem right now", which is exactly what its reconcile-cycle races look
# like (see _post_with_retry). A 4xx means the request itself was bad and
# retrying would just repeat the same failure.
_RETRYABLE_STATUS_CODES = {500, 502, 503, 504}


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


async def _post_with_retry(url: str, **kwargs: Any) -> httpx.Response:
    """POST to GuideAnts, retrying once after GUIDEANTS_RETRY_DELAY_SECONDS on
    a transient failure (a dropped connection, or one of _RETRYABLE_STATUS_CODES).

    GuideAnts periodically reconciles its local ASR/TTS engines without
    waiting out an in-flight request first, so a request whose timing
    overlaps that cycle can have its connection dropped -- observed directly
    as `httpx.RequestError` -- or get served a transient 5xx. By the time of
    a retry, GuideAnts' reconcile has normally already finished.

    `RequestError` is imported by name at module load, not looked up as
    `httpx.RequestError`, so this still works under tests that monkeypatch
    the `httpx` name to a fake client.
    """
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=config.GUIDEANTS_TIMEOUT_SECONDS) as client:
                response = await client.post(url, **kwargs)
        except RequestError as exc:
            if attempt == 1:
                raise GuideAudioError(f"GuideAnts request failed: {exc}") from exc
        else:
            if attempt == 1 or response.status_code not in _RETRYABLE_STATUS_CODES:
                return response
        await asyncio.sleep(config.GUIDEANTS_RETRY_DELAY_SECONDS)
    raise AssertionError("unreachable: loop above always returns or raises")


async def transcribe(wav: bytes) -> str:
    """Caller audio -> text.

    The upload's filename extension is significant: GuideAnts dispatches on it
    and rejects an unrecognized one with `provider_not_ready`, so the file part
    is always named audio.wav regardless of where the bytes came from.
    """
    url = f"{_base_url()}/audio/transcriptions"
    response = await _post_with_retry(
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

    response = await _post_with_retry(url, headers=_headers(), json=payload)

    if response.status_code >= 400:
        raise GuideAudioError(
            f"GuideAnts speech failed ({response.status_code}): {response.text[:200]}",
            status_code=response.status_code,
        )
    if not response.content:
        raise GuideAudioError("GuideAnts speech returned empty audio")
    return response.content
