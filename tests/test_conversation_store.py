from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import conversation_store
from app.db import Base


def _session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _create(db, **overrides):
    defaults = dict(
        customer_name="Jane Doe",
        customer_phone="+15551234567",
        started_at=datetime(2026, 9, 1, 9, 0, 0),
        ended_at=datetime(2026, 9, 1, 9, 5, 0),
        intent="Book a rental",
        outcome="completed",
        escalated=False,
        summary="Booked an e-bike for Saturday.",
        messages=[{"speaker": "customer", "text": "Hi", "at": datetime(2026, 9, 1, 9, 0, 0)}],
        actions=[
            {
                "action": "Create reservation",
                "system": "Booqable",
                "result": "Completed successfully",
                "status": "success",
                "details": {"product_id": "prod_1"},
            }
        ],
    )
    defaults.update(overrides)
    conversation = conversation_store.create_conversation(db, **defaults)
    db.commit()
    return conversation.id


def test_create_conversation_persists_messages_and_actions():
    db = _session()
    conversation_id = _create(db)

    fetched = conversation_store.get_conversation(db, conversation_id)

    assert fetched is not None
    assert fetched.customer_name == "Jane Doe"
    assert len(fetched.messages) == 1
    assert len(fetched.actions) == 1
    assert fetched.actions[0].details == {"product_id": "prod_1"}


def test_create_conversation_falls_back_to_completed_on_invalid_outcome():
    db = _session()
    conversation_id = _create(db, outcome="not-a-real-outcome")

    fetched = conversation_store.get_conversation(db, conversation_id)
    assert fetched.outcome == "completed"


def test_get_conversation_returns_none_when_missing():
    db = _session()
    assert conversation_store.get_conversation(db, "does-not-exist") is None


def test_list_conversations_sorts_newest_first():
    db = _session()
    _create(db, started_at=datetime(2026, 9, 1, 9, 0, 0), ended_at=datetime(2026, 9, 1, 9, 5, 0))
    _create(db, started_at=datetime(2026, 9, 2, 9, 0, 0), ended_at=datetime(2026, 9, 2, 9, 5, 0))

    rows, total = conversation_store.list_conversations(db)

    assert total == 2
    assert rows[0].started_at > rows[1].started_at


def test_list_conversations_filters_by_outcome():
    db = _session()
    _create(db, outcome="completed")
    _create(db, outcome="abandoned", customer_name="No Show")

    rows, total = conversation_store.list_conversations(db, outcome="abandoned")

    assert total == 1
    assert rows[0].customer_name == "No Show"


def test_list_conversations_filters_by_escalated():
    db = _session()
    _create(db, escalated=False)
    _create(db, escalated=True, customer_name="Escalated Caller")

    rows, total = conversation_store.list_conversations(db, escalated=True)

    assert total == 1
    assert rows[0].customer_name == "Escalated Caller"


def test_list_conversations_search_matches_customer_name():
    db = _session()
    _create(db, customer_name="Jane Doe")
    _create(db, customer_name="John Smith")

    rows, total = conversation_store.list_conversations(db, search="Jane")

    assert total == 1
    assert rows[0].customer_name == "Jane Doe"


def test_list_conversations_paginates():
    db = _session()
    for i in range(3):
        _create(
            db,
            customer_name=f"Customer {i}",
            started_at=datetime(2026, 9, 1 + i, 9, 0, 0),
            ended_at=datetime(2026, 9, 1 + i, 9, 5, 0),
        )

    page_one, total = conversation_store.list_conversations(db, page=1, page_size=2)
    page_two, _ = conversation_store.list_conversations(db, page=2, page_size=2)

    assert total == 3
    assert len(page_one) == 2
    assert len(page_two) == 1


def test_list_distinct_intents_is_sorted_and_deduplicated():
    db = _session()
    _create(db, intent="Book a rental")
    _create(db, intent="Book a rental", customer_name="Second Booking")
    _create(db, intent="Ask about hours", customer_name="Third Caller")

    assert conversation_store.list_distinct_intents(db) == ["Ask about hours", "Book a rental"]
