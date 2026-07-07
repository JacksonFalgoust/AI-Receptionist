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
    """Yield text deltas for the guide's reply to the given chat history.

    The GuideAnts published wire API's chat/completions endpoint is
    non-streaming only (stream=true returns unsupported_feature), so this
    makes a single blocking call and yields the whole reply as one delta.
    """
    client = _get_client()
    response = await client.chat.completions.create(
        model=config.GUIDEANTS_MODEL,
        messages=messages,
    )
    if not response.choices:
        return
    content = response.choices[0].message.content
    if content:
        yield content
