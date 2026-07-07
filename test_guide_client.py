import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import guide_client


async def _collect(aiter):
    return [item async for item in aiter]


def test_stream_reply_does_not_request_streaming(monkeypatch):
    """The GuideAnts published wire API rejects stream=true with
    unsupported_feature, so the client must not ask for it."""
    fake_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Hello there!"))]
    )
    create = AsyncMock(return_value=fake_response)
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(guide_client, "_get_client", lambda: fake_client)

    deltas = asyncio.run(_collect(guide_client.stream_reply([{"role": "user", "content": "hi"}])))

    assert "".join(deltas) == "Hello there!"
    _, kwargs = create.call_args
    assert kwargs.get("stream") is not True
