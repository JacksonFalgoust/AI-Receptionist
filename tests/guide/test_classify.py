import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.guide import classify, connection
from app.guide.session import GuideSession


def test_classify_conversation_parses_structured_reply(monkeypatch):
    session = GuideSession(conversation_id="conv_123")
    fake_response = SimpleNamespace(
        output_text=json.dumps(
            {
                "intent": "Book a rental",
                "outcome": "completed",
                "escalated": False,
                "summary": "Booked an e-bike for Saturday.",
            }
        )
    )
    fake_client = SimpleNamespace(
        responses=SimpleNamespace(create=AsyncMock(return_value=fake_response))
    )
    monkeypatch.setattr(connection, "get_client", lambda: fake_client)

    result = asyncio.run(classify.classify_conversation(session))

    assert result["intent"] == "Book a rental"
    assert result["outcome"] == "completed"
    assert result["escalated"] is False
    fake_client.responses.create.assert_awaited_once_with(
        conversation="conv_123", input=classify._CLASSIFICATION_PROMPT, stream=False
    )


def test_classify_conversation_raises_when_no_conversation_id():
    with pytest.raises(ValueError):
        asyncio.run(classify.classify_conversation(GuideSession(conversation_id=None)))


def test_classify_conversation_raises_on_malformed_json(monkeypatch):
    session = GuideSession(conversation_id="conv_123")
    fake_client = SimpleNamespace(
        responses=SimpleNamespace(
            create=AsyncMock(return_value=SimpleNamespace(output_text="not json"))
        )
    )
    monkeypatch.setattr(connection, "get_client", lambda: fake_client)

    with pytest.raises(ValueError):
        asyncio.run(classify.classify_conversation(session))


def test_classify_conversation_raises_on_invalid_outcome(monkeypatch):
    session = GuideSession(conversation_id="conv_123")
    fake_response = SimpleNamespace(
        output_text=json.dumps({"outcome": "not-a-real-outcome", "escalated": False})
    )
    fake_client = SimpleNamespace(
        responses=SimpleNamespace(create=AsyncMock(return_value=fake_response))
    )
    monkeypatch.setattr(connection, "get_client", lambda: fake_client)

    with pytest.raises(ValueError):
        asyncio.run(classify.classify_conversation(session))


def test_classify_conversation_raises_when_request_fails(monkeypatch):
    session = GuideSession(conversation_id="conv_123")
    fake_client = SimpleNamespace(
        responses=SimpleNamespace(create=AsyncMock(side_effect=RuntimeError("network down")))
    )
    monkeypatch.setattr(connection, "get_client", lambda: fake_client)

    with pytest.raises(ValueError):
        asyncio.run(classify.classify_conversation(session))
