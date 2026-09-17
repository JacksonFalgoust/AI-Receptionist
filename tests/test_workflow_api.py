"""FastAPI-level tests for /api/workflows -- frontend/src/services/
workflowService.ts's httpWorkflowService, made real (E6 slice 3)."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import auth, models, workflow_store
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
    fields = dict(name="New rental intake")
    fields.update(overrides)
    workflow = workflow_store.create_workflow(db, **fields)
    db.commit()
    workflow_id = workflow.id
    db.close()
    return workflow_id


def _seed_with_steps(SessionLocal, steps):
    db = SessionLocal()
    workflow = workflow_store.create_workflow(db, name="With steps")
    workflow_store.save_draft(db, workflow, {"steps": steps})
    db.commit()
    workflow_id = workflow.id
    db.close()
    return workflow_id


ONE_STEP = [{"id": "s1", "name": "Ask for ID", "type": "ask_customer"}]


def test_create_returns_201_and_camelcase_workflow(db_session_factory):
    response = client.post(
        "/api/workflows", json={"name": "New rental intake", "description": "First-timer flow"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["organizationId"] == "org_default"
    assert body["status"] == "draft"
    assert body["version"] == 1
    assert body["steps"] == []
    assert body["executionCount"] == 0
    assert body["lastUpdatedAt"].endswith("Z")
    assert set(body) == {
        "id", "organizationId", "name", "description", "status", "version",
        "steps", "executionCount", "lastUpdatedAt",
    }


@pytest.mark.parametrize("payload", [{"name": "   "}, {}])
def test_create_rejects_invalid_input_with_422(db_session_factory, payload):
    assert client.post("/api/workflows", json=payload).status_code == 422


def test_get_returns_workflow(db_session_factory):
    workflow_id = _seed(db_session_factory)

    response = client.get(f"/api/workflows/{workflow_id}")

    assert response.status_code == 200
    assert response.json()["name"] == "New rental intake"


def test_list_returns_a_bare_array(db_session_factory):
    _seed(db_session_factory, name="First")
    _seed(db_session_factory, name="Second")

    response = client.get("/api/workflows")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert {item["name"] for item in body} == {"First", "Second"}


def test_patch_changes_only_sent_fields(db_session_factory):
    workflow_id = _seed(db_session_factory, description="Original")

    response = client.patch(f"/api/workflows/{workflow_id}", json={"name": "Renamed"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Renamed"
    assert body["description"] == "Original"
    assert body["status"] == "draft"
    assert body["version"] == 1


def test_patch_explicit_null_clears_description(db_session_factory):
    workflow_id = _seed(db_session_factory, description="Original")

    response = client.patch(f"/api/workflows/{workflow_id}", json={"description": None})

    assert response.status_code == 200
    assert response.json()["description"] is None


def test_patch_ignores_status_and_version_fields(db_session_factory):
    """status/version aren't in the schema at all -- sending them is a
    no-op (FastAPI/Pydantic silently ignores unrecognized extra fields by
    default), never an error and never applied."""
    workflow_id = _seed(db_session_factory)

    response = client.patch(
        f"/api/workflows/{workflow_id}", json={"status": "active", "version": 99}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "draft"
    assert body["version"] == 1


def test_patch_rejects_explicit_null_name_with_422(db_session_factory):
    """name is a NOT NULL column -- an explicit null must be rejected before
    it ever reaches the ORM, not surface as a 500 from a commit-time
    IntegrityError."""
    workflow_id = _seed(db_session_factory)

    response = client.patch(f"/api/workflows/{workflow_id}", json={"name": None})

    assert response.status_code == 422


def test_patch_rejects_explicit_null_steps_and_leaves_steps_intact(db_session_factory):
    """steps is a NOT NULL column -- an explicit null must be rejected, not
    silently accepted and stored as a JSON null that wipes every step."""
    workflow_id = _seed_with_steps(db_session_factory, ONE_STEP)

    response = client.patch(f"/api/workflows/{workflow_id}", json={"steps": None})
    assert response.status_code == 422

    follow_up = client.get(f"/api/workflows/{workflow_id}")
    assert [step["id"] for step in follow_up.json()["steps"]] == ["s1"]


def test_patch_replaces_steps_wholesale(db_session_factory):
    workflow_id = _seed_with_steps(db_session_factory, ONE_STEP)

    response = client.patch(
        f"/api/workflows/{workflow_id}",
        json={"steps": [{"id": "s2", "name": "Confirm details", "type": "confirm"}]},
    )

    assert response.status_code == 200
    ids = [step["id"] for step in response.json()["steps"]]
    assert ids == ["s2"]


def test_patch_rejects_step_with_unknown_type(db_session_factory):
    workflow_id = _seed(db_session_factory)

    response = client.patch(
        f"/api/workflows/{workflow_id}",
        json={"steps": [{"id": "s1", "name": "Bad step", "type": "not_a_real_type"}]},
    )

    assert response.status_code == 422


def test_patch_rejects_step_with_unrecognized_field(db_session_factory):
    workflow_id = _seed(db_session_factory)

    response = client.patch(
        f"/api/workflows/{workflow_id}",
        json={
            "steps": [
                {
                    "id": "s1",
                    "name": "x",
                    "type": "ask_customer",
                    "bogusField": "should not be accepted",
                }
            ]
        },
    )

    assert response.status_code == 422


def test_patch_keeps_step_optional_fields(db_session_factory):
    workflow_id = _seed(db_session_factory)
    step = {
        "id": "s1",
        "name": "Look up availability",
        "type": "look_up",
        "requiredIntegrationId": "int_booqable",
        "errorBehavior": "Apologize and offer a callback",
        "escalationBehavior": "Transfer to a human",
        "configuration": {"category": "bikes"},
    }

    response = client.patch(f"/api/workflows/{workflow_id}", json={"steps": [step]})

    assert response.status_code == 200
    out_step = response.json()["steps"][0]
    assert out_step["requiredIntegrationId"] == "int_booqable"
    assert out_step["errorBehavior"] == "Apologize and offer a callback"
    assert out_step["escalationBehavior"] == "Transfer to a human"
    assert out_step["configuration"] == {"category": "bikes"}


def test_publish_rejects_empty_steps_with_422(db_session_factory):
    workflow_id = _seed(db_session_factory)

    response = client.post(f"/api/workflows/{workflow_id}/publish")

    assert response.status_code == 422


def test_publish_activates_and_increments_version(db_session_factory):
    workflow_id = _seed_with_steps(db_session_factory, ONE_STEP)

    response = client.post(f"/api/workflows/{workflow_id}/publish")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "active"
    assert body["version"] == 2


def test_delete_returns_204_then_workflow_is_gone(db_session_factory):
    workflow_id = _seed(db_session_factory)

    response = client.delete(f"/api/workflows/{workflow_id}")

    assert response.status_code == 204
    assert client.get(f"/api/workflows/{workflow_id}").status_code == 404


@pytest.mark.parametrize("method", ["get", "patch", "delete", "publish"])
def test_unknown_id_is_404(db_session_factory, method):
    if method == "patch":
        response = client.patch("/api/workflows/missing", json={"name": "x"})
    elif method == "publish":
        response = client.post("/api/workflows/missing/publish")
    else:
        response = getattr(client, method)("/api/workflows/missing")
    assert response.status_code == 404


@pytest.mark.parametrize(
    "method,path,kwargs",
    [
        ("get", "/api/workflows", {}),
        ("get", "/api/workflows/x", {}),
        ("post", "/api/workflows", {"json": {"name": "x"}}),
        ("patch", "/api/workflows/x", {"json": {"name": "x"}}),
        ("post", "/api/workflows/x/publish", {}),
        ("delete", "/api/workflows/x", {}),
    ],
)
def test_routes_require_auth(method, path, kwargs):
    # No db_session_factory fixture: require_auth is not overridden.
    response = getattr(client, method)(path, **kwargs)
    assert response.status_code == 401
