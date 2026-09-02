"""Downloading the caller's recorded turn from Twilio, for the local audio
demo (app/local_demo_api.py).

<Record>'s action callback fires the moment recording stops, but the media is
only downloadable once the recording's status is `completed` -- a fetch
immediately after the callback can 404 for a beat, so this retries a bounded
number of times before giving up.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from . import config

logger = logging.getLogger("voice_receptionist")


class RecordingUnavailable(Exception):
    pass


async def fetch_recording_wav(recording_url: str) -> bytes:
    """Fetch `recording_url` as WAV. Raises RecordingUnavailable rather than
    returning partial audio -- the caller (app/local_call.py) turns that into
    a spoken apology and another <Record>, so the call survives."""
    if not (config.TWILIO_ACCOUNT_SID and config.TWILIO_AUTH_TOKEN):
        raise RecordingUnavailable(
            "TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN are not configured; cannot fetch recordings"
        )

    url = f"{recording_url}.wav"
    auth = (config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
    attempts = max(1, config.LOCAL_RECORDING_FETCH_ATTEMPTS)

    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt in range(1, attempts + 1):
            response = await client.get(url, auth=auth)

            if response.status_code == 200:
                return response.content

            if response.status_code != 404:
                raise RecordingUnavailable(
                    f"Twilio recording fetch failed ({response.status_code}): {response.text[:200]}"
                )

            logger.info("Recording not ready yet (attempt %s/%s)", attempt, attempts)
            if attempt < attempts:
                await asyncio.sleep(config.LOCAL_RECORDING_FETCH_DELAY_SECONDS)

    raise RecordingUnavailable(
        f"Twilio recording still unavailable after {attempts} attempts: {url}"
    )
