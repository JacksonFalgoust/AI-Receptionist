"""FastAPI-level tests for /api/concierge -- the live backing for
frontend/src/services/configurationService.ts."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import auth, models
from app.db import Base, get_db
from app.guide_publish import guideants_admin
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


@pytest.fixture
def push_ok(monkeypatch):
    async def fake_update(instructions):
        return {"guideId": "abc", "warnings": []}

    monkeypatch.setattr(guideants_admin, "update_guide_instructions", fake_update)
    monkeypatch.setattr(guideants_admin, "is_configured", lambda: True)


@pytest.fixture
def push_fails(monkeypatch):
    async def fake_update(instructions):
        raise guideants_admin.GuideAntsAdminError("GuideAnts unreachable on GET /api/guides")

    monkeypatch.setattr(guideants_admin, "update_guide_instructions", fake_update)
    monkeypatch.setattr(guideants_admin, "is_configured", lambda: True)


def test_get_configuration_seeds_and_returns_camel_case(db_session_factory):
    response = client.get("/api/concierge/configuration")
    assert response.status_code == 200
    body = response.json()
    assert body["businessProfile"]["name"] == "Peachtree Pedals"
    assert body["hasUnpublishedChanges"] is False
    assert "business_profile" not in body


def test_patch_merges_one_section_and_marks_dirty(db_session_factory):
    original = client.get("/api/concierge/configuration").json()
    response = client.patch(
        "/api/concierge/configuration",
        json={"identity": {**original["identity"], "greeting": "Hello there"}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["identity"]["greeting"] == "Hello there"
    assert body["businessProfile"]["name"] == original["businessProfile"]["name"]
    assert body["hasUnpublishedChanges"] is True


def test_patch_rejects_unknown_sections(db_session_factory):
    response = client.patch("/api/concierge/configuration", json={"nonsense": {}})
    assert response.status_code == 422


def test_preview_returns_instructions_without_publishing(db_session_factory):
    response = client.post("/api/concierge/configuration/preview")
    assert response.status_code == 200
    body = response.json()
    assert "Peachtree Pedals" in body["instructions"]
    assert body["changed"] is True
    assert client.get("/api/concierge/publications").json() == []


def test_publish_succeeds_and_clears_the_draft_flag(db_session_factory, push_ok):
    client.patch(
        "/api/concierge/configuration",
        json={"identity": {"greeting": "Hi", "tone": "custom", "customTone": "warm, upbeat, and polite"}},
    )
    response = client.post("/api/concierge/configuration/publish")
    assert response.status_code == 200
    body = response.json()
    assert body["published"] is True
    assert body["status"] == "succeeded"
    assert body["configuration"]["hasUnpublishedChanges"] is False


def test_publish_failure_reports_error_and_stays_dirty(db_session_factory, monkeypatch):
    async def fake_update(instructions):
        raise guideants_admin.GuideAntsAdminError("GuideAnts unreachable on GET /api/guides")

    monkeypatch.setattr(guideants_admin, "update_guide_instructions", fake_update)
    monkeypatch.setattr(guideants_admin, "is_configured", lambda: True)

    client.patch("/api/concierge/configuration", json={"terminology": {"customer": "Rider"}})
    response = client.post("/api/concierge/configuration/publish")

    assert response.status_code == 200
    body = response.json()
    assert body["published"] is False
    assert body["status"] == "failed"
    assert "unreachable" in body["error"]
    assert body["configuration"]["hasUnpublishedChanges"] is True


def test_publish_without_credentials_returns_503(db_session_factory, monkeypatch):
    monkeypatch.setattr(guideants_admin, "is_configured", lambda: False)
    response = client.post("/api/concierge/configuration/publish")
    assert response.status_code == 503
    assert "GUIDEANTS_ADMIN_EMAIL" in response.json()["detail"]


def test_bundle_download_works_without_credentials(db_session_factory, monkeypatch):
    monkeypatch.setattr(guideants_admin, "is_configured", lambda: False)
    response = client.get("/api/concierge/bundle")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.content[:2] == b"PK"


def test_invalid_configuration_fails_preview_with_422(db_session_factory):
    original = client.get("/api/concierge/configuration").json()
    patched = client.patch(
        "/api/concierge/configuration",
        json={"businessProfile": {**original["businessProfile"], "name": "**Bad**"}},
    )
    assert patched.status_code == 200, "a draft may hold invalid values"

    response = client.post("/api/concierge/configuration/preview")
    assert response.status_code == 422
    assert "business.name" in response.json()["detail"]


def test_rollback_republishes_an_earlier_publication(db_session_factory, push_ok):
    client.post("/api/concierge/configuration/publish")
    first_id = client.get("/api/concierge/publications").json()[0]["id"]

    original = client.get("/api/concierge/configuration").json()
    client.patch(
        "/api/concierge/configuration",
        json={"businessProfile": {**original["businessProfile"], "name": "Dogwood Cycles"}},
    )
    client.post("/api/concierge/configuration/publish")

    response = client.post(f"/api/concierge/publications/{first_id}/rollback")

    assert response.status_code == 200
    assert response.json()["published"] is True
    assert len(client.get("/api/concierge/publications").json()) == 3


def test_rollback_of_a_missing_publication_is_404(db_session_factory, push_ok):
    assert client.post("/api/concierge/publications/nope/rollback").status_code == 404


def test_publications_list_is_newest_first(db_session_factory, push_ok):
    client.post("/api/concierge/configuration/publish")
    original = client.get("/api/concierge/configuration").json()
    client.patch(
        "/api/concierge/configuration",
        json={"businessProfile": {**original["businessProfile"], "name": "Dogwood Cycles"}},
    )
    client.post("/api/concierge/configuration/publish")
    body = client.get("/api/concierge/publications").json()
    assert len(body) == 2
    assert body[0]["createdAt"] >= body[1]["createdAt"]


def test_requires_auth(db_session_factory):
    app.dependency_overrides.pop(auth.require_auth, None)
    assert client.get("/api/concierge/configuration").status_code == 401


def test_rollback_of_a_failed_publication_is_404(db_session_factory, push_fails):
    """A failed row still carries instructions_text, so replaying it would
    "succeed" at the network layer -- but its published_config is {}, and
    republish() copies that forward, silently reverting the live greeting.
    A failed publication is not a rollback target."""
    client.post("/api/concierge/configuration/publish")
    publications = client.get("/api/concierge/publications").json()
    assert [p["status"] for p in publications] == ["failed"]

    response = client.post(
        f"/api/concierge/publications/{publications[0]['id']}/rollback"
    )

    assert response.status_code == 404
    # Nothing new was recorded, and nothing was pushed.
    assert len(client.get("/api/concierge/publications").json()) == 1


def test_rollback_of_a_pending_publication_is_404(db_session_factory, push_ok):
    session = db_session_factory()
    session.add(
        models.GuidePublication(
            id="pending-1",
            organization_id="org_default",
            published_by="admin@example.com",
            content_hash="abc",
            instructions_text="...",
            published_config={},
            knowledge_item_count=0,
            bundle_bytes=b"PK\x03\x04",
            status="pending",
        )
    )
    session.commit()
    session.close()

    assert (
        client.post("/api/concierge/publications/pending-1/rollback").status_code == 404
    )
