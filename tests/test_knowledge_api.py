"""FastAPI-level tests for /api/knowledge -- frontend/src/services/
knowledgeService.ts's httpKnowledgeService, made real (E6 slice 2)."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import auth, knowledge_store, models
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
    fields = dict(title="Damage policy", type="policy", content="Minor scratches are free.")
    fields.update(overrides)
    item = knowledge_store.create_item(db, **fields)
    db.commit()
    item_id = item.id
    db.close()
    return item_id


def test_create_returns_201_and_camelcase_item(db_session_factory):
    response = client.post(
        "/api/knowledge",
        json={
            "title": "Do you rent kids' bikes?",
            "type": "faq",
            "category": "Rentals",
            "content": "Yes, 16 and 20 inch.",
            "tags": ["kids"],
            "effectiveDate": "2026-01-15T00:00:00.000Z",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["organizationId"] == "org_default"
    assert body["status"] == "active"
    assert body["source"] == "Manual entry"
    assert body["tags"] == ["kids"]
    assert body["effectiveDate"] == "2026-01-15T00:00:00Z"
    assert body["expirationDate"] is None
    assert body["updatedAt"].endswith("Z")
    assert set(body) == {
        "id", "organizationId", "title", "type", "status", "source", "category",
        "content", "tags", "effectiveDate", "expirationDate", "updatedAt",
    }


def test_create_document_upload_is_saved_as_needs_review(db_session_factory):
    response = client.post(
        "/api/knowledge",
        json={"title": "Menu", "type": "document", "status": "processing", "source": "menu.pdf"},
    )

    assert response.status_code == 201
    assert response.json()["status"] == "needs_review"
    assert response.json()["source"] == "menu.pdf"


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "   ", "type": "faq"},
        {"type": "faq"},
        {"title": "x", "type": "blog"},
        {"title": "x", "type": "faq", "status": "archived"},
    ],
)
def test_create_rejects_invalid_input_with_422(db_session_factory, payload):
    assert client.post("/api/knowledge", json=payload).status_code == 422


def test_get_returns_item(db_session_factory):
    item_id = _seed(db_session_factory)

    response = client.get(f"/api/knowledge/{item_id}")

    assert response.status_code == 200
    assert response.json()["title"] == "Damage policy"


def test_list_passes_filters_and_paging_through(db_session_factory):
    _seed(db_session_factory, title="Helmet rules", type="policy")
    _seed(db_session_factory, title="Helmet FAQ", type="faq")
    _seed(db_session_factory, title="Tours", type="policy")

    response = client.get(
        "/api/knowledge",
        params={"search": "helmet", "type": "policy", "status": "active", "page": 1, "pageSize": 10},
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["title"] for item in body["items"]] == ["Helmet rules"]
    assert (body["page"], body["pageSize"], body["total"]) == (1, 10, 1)


def test_list_rejects_unknown_type_filter_with_422(db_session_factory):
    assert client.get("/api/knowledge", params={"type": "blog"}).status_code == 422


def test_patch_changes_only_sent_fields(db_session_factory):
    item_id = _seed(db_session_factory, category="Policies")

    response = client.patch(f"/api/knowledge/{item_id}", json={"title": "Damage & loss policy"})

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Damage & loss policy"
    assert body["category"] == "Policies"
    assert body["content"] == "Minor scratches are free."


def test_patch_explicit_null_clears_optional_field(db_session_factory):
    item_id = _seed(db_session_factory, category="Policies")

    response = client.patch(
        f"/api/knowledge/{item_id}", json={"category": None, "expirationDate": None}
    )

    assert response.status_code == 200
    assert response.json()["category"] is None


@pytest.mark.parametrize(
    "payload",
    [{"title": None}, {"title": ""}, {"type": None}, {"status": "archived"}, {"tags": None}],
)
def test_patch_rejects_invalid_values_with_422(db_session_factory, payload):
    item_id = _seed(db_session_factory)
    assert client.patch(f"/api/knowledge/{item_id}", json=payload).status_code == 422


def test_patch_processing_is_saved_as_needs_review(db_session_factory):
    item_id = _seed(db_session_factory, type="document", source="menu.pdf")

    response = client.patch(f"/api/knowledge/{item_id}", json={"status": "processing"})

    assert response.json()["status"] == "needs_review"


def test_delete_returns_204_then_item_is_gone(db_session_factory):
    item_id = _seed(db_session_factory)

    response = client.delete(f"/api/knowledge/{item_id}")

    assert response.status_code == 204
    assert client.get(f"/api/knowledge/{item_id}").status_code == 404


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_unknown_id_is_404(db_session_factory, method):
    kwargs = {"json": {"title": "x"}} if method == "patch" else {}
    response = getattr(client, method)("/api/knowledge/missing", **kwargs)
    assert response.status_code == 404


def test_routes_require_auth():
    # No db_session_factory fixture: require_auth is not overridden.
    assert client.get("/api/knowledge").status_code == 401
    assert client.post("/api/knowledge", json={"title": "x", "type": "faq"}).status_code == 401
