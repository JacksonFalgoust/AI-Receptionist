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
