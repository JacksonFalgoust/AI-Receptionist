"""FastAPI-level tests for GET /api/conversations, GET
/api/conversations/filter-options, and GET /api/conversations/{id} --
frontend/src/services/conversationService.ts's httpConversationService,
made real."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import auth, conversation_store, models
from app.db import Base, get_db
from app.main import app

client = TestClient(app)


@pytest.fixture
def db_session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    testing_session_local = sessionmaker(bind=engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[auth.require_auth] = lambda: models.AuthSession(
        token="test", user_email="admin@example.com", expires_at=datetime.max
    )
    yield testing_session_local
    app.dependency_overrides.clear()


def _seed(SessionLocal, **overrides):
    db = SessionLocal()
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
    conversation_id = conversation.id
    db.close()
    return conversation_id


def test_list_returns_seeded_conversation(db_session_factory):
    _seed(db_session_factory)

    response = client.get("/api/conversations")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["customerName"] == "Jane Doe"


def test_list_filters_by_outcome(db_session_factory):
    _seed(db_session_factory, outcome="completed")
    _seed(db_session_factory, outcome="abandoned", customer_name="No Show")

    response = client.get("/api/conversations", params={"outcome": "abandoned"})

    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["customerName"] == "No Show"


def test_list_paginates(db_session_factory):
    for i in range(3):
        _seed(
            db_session_factory,
            customer_name=f"Customer {i}",
            started_at=datetime(2026, 9, 1 + i, 9, 0, 0),
            ended_at=datetime(2026, 9, 1 + i, 9, 5, 0),
        )

    response = client.get("/api/conversations", params={"page": 1, "pageSize": 2})

    body = response.json()
    assert len(body["items"]) == 2
    assert body["total"] == 3


def test_get_returns_messages_and_actions(db_session_factory):
    conversation_id = _seed(db_session_factory)

    response = client.get(f"/api/conversations/{conversation_id}")

    body = response.json()
    assert body["conversation"]["id"] == conversation_id
    assert len(body["messages"]) == 1
    assert len(body["actions"]) == 1
    assert body["actions"][0]["action"] == "Create reservation"


def test_get_missing_conversation_is_404(db_session_factory):
    response = client.get("/api/conversations/does-not-exist")
    assert response.status_code == 404


def test_filter_options_returns_distinct_intents(db_session_factory):
    _seed(db_session_factory, intent="Book a rental")
    _seed(db_session_factory, intent="Ask about hours", customer_name="Second Caller")

    response = client.get("/api/conversations/filter-options")

    body = response.json()
    assert sorted(body["intents"]) == ["Ask about hours", "Book a rental"]
    assert body["locations"] == []
    assert body["employees"] == []


def test_list_requires_auth():
    response = client.get("/api/conversations")
    assert response.status_code == 401


def test_list_rejects_malformed_from_date_with_422(db_session_factory):
    response = client.get("/api/conversations", params={"from": "not-a-date"})
    assert response.status_code == 422


def test_escalated_conversation_reports_new_escalation_status(db_session_factory):
    escalated_id = _seed(db_session_factory, escalated=True, customer_name="Escalated Caller")
    fine_id = _seed(db_session_factory, escalated=False, customer_name="Fine Caller")

    response = client.get("/api/conversations")

    body = {item["id"]: item for item in response.json()["items"]}
    assert body[escalated_id]["escalationStatus"] == "new"
    assert body[fine_id]["escalationStatus"] is None
