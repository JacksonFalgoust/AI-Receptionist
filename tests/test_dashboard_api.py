"""FastAPI-level tests for /api/dashboard/* -- frontend/src/services/
dashboardService.ts's httpDashboardService, made real (E6 dashboard
slice). See docs/superpowers/specs/2026-09-22-e6-dashboard-design.md."""

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
        messages=[],
        actions=[
            {
                "action": "Create reservation",
                "system": "Booqable",
                "result": "Completed successfully",
                "status": "success",
                "at": datetime(2026, 9, 1, 9, 3, 0),
            }
        ],
    )
    defaults.update(overrides)
    conversation = conversation_store.create_conversation(db, **defaults)
    db.commit()
    conversation_id = conversation.id
    db.close()
    return conversation_id


@pytest.mark.parametrize(
    "path",
    [
        "/api/dashboard/overview",
        "/api/dashboard/activity",
        "/api/dashboard/escalations",
        "/api/dashboard/escalations/count",
    ],
)
def test_routes_require_auth(path):
    # No db_session_factory fixture: require_auth is not overridden.
    response = client.get(path)
    assert response.status_code == 401


def test_overview_returns_five_kpis(db_session_factory):
    _seed(db_session_factory)

    response = client.get("/api/dashboard/overview")

    assert response.status_code == 200
    body = response.json()
    assert [kpi["id"] for kpi in body["kpis"]] == [
        "conversations_today",
        "calls_answered",
        "requests_completed",
        "human_escalations",
        "transactions_created",
    ]


def test_activity_returns_camelcase_fields_from_the_conversation_action(db_session_factory):
    conversation_id = _seed(db_session_factory)

    response = client.get("/api/dashboard/activity")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1
    event = body[0]
    assert event["title"] == "Create reservation"
    assert event["system"] == "Booqable"
    assert event["status"] == "success"
    assert event["customerRef"] == "Jane Doe"
    assert event["channel"] == "voice"
    assert event["conversationId"] == conversation_id
    assert event["organizationId"] == "org_default"
    assert event["at"].endswith("Z")


def test_activity_respects_limit(db_session_factory):
    for i in range(3):
        _seed(db_session_factory, customer_name=f"Customer {i}")

    response = client.get("/api/dashboard/activity", params={"limit": 2})

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_activity_rejects_limit_outside_1_to_100(db_session_factory):
    assert client.get("/api/dashboard/activity", params={"limit": 0}).status_code == 422
    assert client.get("/api/dashboard/activity", params={"limit": 101}).status_code == 422


def test_activity_rejects_unknown_preset(db_session_factory):
    response = client.get("/api/dashboard/activity", params={"preset": "yesterday"})
    assert response.status_code == 422


def test_activity_rejects_malformed_from_date(db_session_factory):
    response = client.get("/api/dashboard/activity", params={"from": "not-a-date"})
    assert response.status_code == 422


def test_escalations_synthesizes_placeholder_status_and_assigned_to(db_session_factory):
    conversation_id = _seed(db_session_factory, escalated=True, intent="Refund request")

    response = client.get("/api/dashboard/escalations")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    row = body[0]
    assert row["id"] == conversation_id
    assert row["conversationId"] == conversation_id
    assert row["organizationId"] == "org_default"
    assert row["customerName"] == "Jane Doe"
    assert row["reason"] == "Refund request"
    assert row["assignedTo"] is None
    assert row["status"] == "new"
    assert row["createdAt"].endswith("Z")


def test_escalations_reason_falls_back_when_intent_is_null(db_session_factory):
    _seed(db_session_factory, escalated=True, intent=None)

    response = client.get("/api/dashboard/escalations")

    assert response.json()[0]["reason"] == "Escalated during the call"


def test_escalations_customer_name_falls_back_when_null(db_session_factory):
    _seed(db_session_factory, escalated=True, customer_name=None)

    response = client.get("/api/dashboard/escalations")

    assert response.json()[0]["customerName"] == "Unknown caller"


def test_escalations_excludes_non_escalated_conversations(db_session_factory):
    _seed(db_session_factory, escalated=False)

    response = client.get("/api/dashboard/escalations")

    assert response.json() == []


def test_escalations_count_matches_uncapped_total(db_session_factory):
    _seed(db_session_factory, escalated=True, customer_name="A")
    _seed(db_session_factory, escalated=True, customer_name="B")
    _seed(db_session_factory, escalated=False, customer_name="C")

    response = client.get("/api/dashboard/escalations/count")

    assert response.status_code == 200
    assert response.json() == 2


def test_escalations_count_is_not_capped_by_a_small_limit_on_the_list_route(db_session_factory):
    for i in range(3):
        _seed(db_session_factory, escalated=True, customer_name=f"Caller {i}")

    count_response = client.get("/api/dashboard/escalations/count")
    list_response = client.get("/api/dashboard/escalations", params={"limit": 2})

    assert count_response.json() == 3
    assert len(list_response.json()) == 2
