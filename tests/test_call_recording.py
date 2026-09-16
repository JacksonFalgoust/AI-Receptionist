"""Tests app/call_recording.py in isolation -- app/main.py's own wiring
(the /ws handler actually calling this) is covered separately in
tests/test_call_recording_wiring.py."""

import asyncio
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import call_recording, models
from app.db import Base
from app.guide_client import GuideSession


class _FakeState:
    def __init__(self, guide, messages, started_at):
        self.guide = guide
        self.messages = messages
        self.started_at = started_at


def _memory_session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_record_call_persists_transcript_and_classification(monkeypatch):
    session_local = _memory_session_factory()
    monkeypatch.setattr(call_recording, "SessionLocal", session_local)

    async def fake_classify(session):
        return {
            "intent": "Book a rental",
            "outcome": "completed",
            "escalated": False,
            "summary": "Booked an e-bike.",
        }

    monkeypatch.setattr(call_recording.guide_client, "classify_conversation", fake_classify)

    guide = GuideSession(conversation_id="conv_1", caller_phone="+15551234567")
    st = _FakeState(
        guide=guide,
        messages=[
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello! How can I help?"},
        ],
        started_at=datetime(2026, 9, 14, 9, 0, 0),
    )

    asyncio.run(call_recording.record_call(st))

    db = session_local()
    saved = db.query(models.Conversation).one()
    assert saved.intent == "Book a rental"
    assert saved.customer_phone == "+15551234567"
    assert len(saved.messages) == 2
    assert saved.messages[0].speaker == "customer"
    assert saved.messages[1].speaker == "concierge"


def test_record_call_falls_back_to_defaults_when_classification_fails(monkeypatch):
    session_local = _memory_session_factory()
    monkeypatch.setattr(call_recording, "SessionLocal", session_local)

    async def failing_classify(session):
        raise ValueError("no conversation id")

    monkeypatch.setattr(call_recording.guide_client, "classify_conversation", failing_classify)

    guide = GuideSession(conversation_id=None)
    st = _FakeState(guide=guide, messages=[], started_at=datetime(2026, 9, 14, 9, 0, 0))

    asyncio.run(call_recording.record_call(st))

    db = session_local()
    saved = db.query(models.Conversation).one()
    assert saved.outcome == "completed"
    assert saved.escalated is False
    assert saved.intent is None


def test_record_call_includes_tool_actions(monkeypatch):
    session_local = _memory_session_factory()
    monkeypatch.setattr(call_recording, "SessionLocal", session_local)

    async def fake_classify(session):
        return {"intent": None, "outcome": "completed", "escalated": False, "summary": None}

    monkeypatch.setattr(call_recording.guide_client, "classify_conversation", fake_classify)

    guide = GuideSession(conversation_id="conv_1")
    guide.actions.append(
        {
            "action": "Create reservation",
            "system": "Booqable",
            "result": "Completed successfully",
            "status": "success",
            "details": {"product_id": "prod_1"},
        }
    )
    st = _FakeState(guide=guide, messages=[], started_at=datetime(2026, 9, 14, 9, 0, 0))

    asyncio.run(call_recording.record_call(st))

    db = session_local()
    saved = db.query(models.Conversation).one()
    assert len(saved.actions) == 1
    assert saved.actions[0].action == "Create reservation"


def test_record_call_customer_name_from_known_customer(monkeypatch):
    session_local = _memory_session_factory()
    monkeypatch.setattr(call_recording, "SessionLocal", session_local)

    async def fake_classify(session):
        return {"intent": None, "outcome": "completed", "escalated": False, "summary": None}

    monkeypatch.setattr(call_recording.guide_client, "classify_conversation", fake_classify)

    guide = GuideSession(
        conversation_id="conv_1",
        known_customer={"attributes": {"name": "Jane Doe"}},
    )
    st = _FakeState(guide=guide, messages=[], started_at=datetime(2026, 9, 14, 9, 0, 0))

    asyncio.run(call_recording.record_call(st))

    db = session_local()
    saved = db.query(models.Conversation).one()
    assert saved.customer_name == "Jane Doe"
