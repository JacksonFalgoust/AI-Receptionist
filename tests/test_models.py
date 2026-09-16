from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.db import Base


def _memory_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_conversation_with_messages_and_actions_round_trips():
    db = _memory_session()
    started_at = datetime(2026, 9, 14, 12, 0, 0)
    ended_at = datetime(2026, 9, 14, 12, 5, 0)

    conversation = models.Conversation(
        organization_id="org_default",
        customer_name="Jane Doe",
        customer_phone="+15551234567",
        channel="voice",
        started_at=started_at,
        ended_at=ended_at,
        duration_seconds=300,
        outcome="completed",
        escalated=False,
    )
    conversation.messages.append(
        models.ConversationMessage(speaker="customer", text="Hi", at=started_at)
    )
    conversation.actions.append(
        models.ConversationAction(
            action="Create reservation",
            system="Booqable",
            at=started_at,
            result="Completed successfully",
            status="success",
            details={"product_id": "prod_1"},
        )
    )
    db.add(conversation)
    db.commit()

    fetched = db.query(models.Conversation).one()
    assert fetched.customer_name == "Jane Doe"
    assert len(fetched.messages) == 1
    assert fetched.messages[0].speaker == "customer"
    assert len(fetched.actions) == 1
    assert fetched.actions[0].details == {"product_id": "prod_1"}


def test_auth_session_round_trips():
    db = _memory_session()
    session = models.AuthSession(
        token="tok_abc",
        user_email="admin@example.com",
        expires_at=datetime.utcnow() + timedelta(hours=8),
    )
    db.add(session)
    db.commit()

    fetched = db.get(models.AuthSession, "tok_abc")
    assert fetched.user_email == "admin@example.com"


def test_init_db_is_idempotent(monkeypatch, tmp_path):
    from app import db

    engine = create_engine(f"sqlite:///{tmp_path / 't.db'}")
    monkeypatch.setattr(db, "engine", engine)

    db.init_db()
    db.init_db()  # must not raise on already-existing tables


def test_knowledge_item_round_trips_with_tags_and_dates():
    db = _memory_session()
    item = models.KnowledgeItem(
        organization_id="org_default",
        title="Damage policy",
        type="policy",
        status="active",
        source="Manual entry",
        category="Policies",
        content="Minor scratches are free.",
        tags=["damage", "policy"],
        effective_date=datetime(2026, 1, 15),
        expiration_date=None,
    )
    db.add(item)
    db.commit()
    db.expire_all()

    fetched = db.get(models.KnowledgeItem, item.id)

    assert fetched is not None
    assert len(fetched.id) == 36  # uuid4 default
    assert fetched.tags == ["damage", "policy"]
    assert fetched.effective_date == datetime(2026, 1, 15)
    assert fetched.expiration_date is None
    assert fetched.updated_at is not None  # default applied


def test_knowledge_item_tags_default_to_empty_list():
    db = _memory_session()
    item = models.KnowledgeItem(
        organization_id="org_default",
        title="Hours",
        type="faq",
        status="active",
        source="Manual entry",
    )
    db.add(item)
    db.commit()

    assert db.get(models.KnowledgeItem, item.id).tags == []
