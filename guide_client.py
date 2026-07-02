"""Streams replies from a GuideAnts published guide via its OpenAI-compatible wire API."""

from typing import AsyncIterator

from openai import AsyncOpenAI

import config

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not config.GUIDEANTS_PUB_ID:
            raise RuntimeError(
                "GUIDEANTS_PUB_ID is not set. Copy .env.example to .env and fill it in."
            )
        _client = AsyncOpenAI(
            base_url=f"{config.GUIDEANTS_BASE_URL}/api/published/openai/{config.GUIDEANTS_PUB_ID}/v1",
            api_key=config.GUIDEANTS_API_KEY or "anonymous",
        )
    return _client


async def stream_reply(messages: list[dict]) -> AsyncIterator[str]:
    """Yield text deltas for the guide's reply to the given chat history."""
    client = _get_client()
    stream = await client.chat.completions.create(
        model=config.GUIDEANTS_MODEL,
        messages=messages,
        stream=True,
    )
    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
