"""A published greeting reaches callers; a drafted one does not.

This is the draft/publish boundary made real: editing a greeting in the
console must not change what the next caller hears until someone clicks
Publish. _greeting_for() therefore reads the last SUCCEEDED publication's
snapshot, never the live configuration row.
"""

import asyncio
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config, db as db_module, models
from app.db import Base
from app.main import _greeting_for


@pytest.fixture
def session_factory(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(db_module, "SessionLocal", factory)
    return factory


def _publish(factory, greeting, status="succeeded"):
    session = factory()
    session.add(
        models.GuidePublication(
            organization_id=config.DEFAULT_ORGANIZATION_ID,
            published_by="admin@example.com",
            content_hash="hash-" + greeting,
            instructions_text="...",
            published_config={"identity": {"greeting": greeting}},
            knowledge_item_count=0,
            status=status,
            created_at=datetime.utcnow(),
        )
    )
    session.commit()
    session.close()


def test_no_publication_falls_back_to_the_env_greeting(session_factory):
    assert asyncio.run(_greeting_for("")) == config.WELCOME_GREETING


def test_published_greeting_is_used(session_factory):
    _publish(session_factory, "Thanks for calling Peachtree Pedals!")
    assert asyncio.run(_greeting_for("")) == "Thanks for calling Peachtree Pedals!"


def test_failed_publication_is_ignored(session_factory):
    _publish(session_factory, "Never spoken", status="failed")
    assert asyncio.run(_greeting_for("")) == config.WELCOME_GREETING


def test_most_recent_succeeded_publication_wins(session_factory):
    _publish(session_factory, "Old greeting")
    _publish(session_factory, "New greeting")
    assert asyncio.run(_greeting_for("")) == "New greeting"


def test_database_failure_falls_back_without_raising(session_factory, monkeypatch):
    """This sits in the call-answering path -- Twilio expects a prompt TwiML
    response, so a broken lookup must never delay or break answering."""

    def boom():
        raise RuntimeError("database gone")

    monkeypatch.setattr(db_module, "SessionLocal", boom)
    assert asyncio.run(_greeting_for("")) == config.WELCOME_GREETING
