"""FastAPI-level tests for POST /api/auth/login and /api/auth/logout --
frontend/src/services/authService.ts's httpAuthService, made real."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import auth, config
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
    yield testing_session_local
    app.dependency_overrides.clear()


def test_login_succeeds_with_correct_credentials(monkeypatch, db_session_factory):
    monkeypatch.setattr(config, "ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", auth.hash_password("correct-horse"))

    response = client.post(
        "/api/auth/login", json={"email": "admin@example.com", "password": "correct-horse"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "admin@example.com"
    assert body["user"]["role"] == "owner"
    assert body["token"]


def test_login_rejects_wrong_password(monkeypatch, db_session_factory):
    monkeypatch.setattr(config, "ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", auth.hash_password("correct-horse"))

    response = client.post(
        "/api/auth/login", json={"email": "admin@example.com", "password": "wrong"}
    )

    assert response.status_code == 422


def test_logout_invalidates_the_token(monkeypatch, db_session_factory):
    monkeypatch.setattr(config, "ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", auth.hash_password("correct-horse"))

    login_response = client.post(
        "/api/auth/login", json={"email": "admin@example.com", "password": "correct-horse"}
    )
    token = login_response.json()["token"]

    logout_response = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_response.status_code == 204

    # The token no longer authenticates -- proven by calling the one other
    # protected route this task adds (logout itself) a second time.
    second_logout = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert second_logout.status_code == 401


def test_protected_route_without_token_is_401():
    response = client.post("/api/auth/logout")
    assert response.status_code == 401


@pytest.mark.parametrize(
    "email", ["admin@example.com", "definitely-not-a-real-account@example.com"]
)
def test_password_reset_always_returns_204(email):
    # Must always succeed, regardless of whether the email matches a real
    # account -- revealing that would leak account existence (mirrors
    # frontend/src/services/authService.ts's mock behavior).
    response = client.post("/api/auth/password-reset", json={"email": email})
    assert response.status_code == 204
