from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import auth, config
from app.db import Base


def _session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_hash_and_verify_password_round_trip():
    hashed = auth.hash_password("correct-horse")
    assert auth.verify_password("correct-horse", hashed)
    assert not auth.verify_password("wrong", hashed)


def test_login_succeeds_with_correct_credentials(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", auth.hash_password("correct-horse"))
    db = _session()

    session = auth.login(db, "admin@example.com", "correct-horse")

    assert session.token
    assert session.user_email == "admin@example.com"


def test_login_rejects_wrong_password(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", auth.hash_password("correct-horse"))
    db = _session()

    with pytest.raises(auth.InvalidCredentials):
        auth.login(db, "admin@example.com", "wrong")


def test_login_rejects_unknown_email(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", auth.hash_password("correct-horse"))
    db = _session()

    with pytest.raises(auth.InvalidCredentials):
        auth.login(db, "someone-else@example.com", "correct-horse")


def test_verify_token_rejects_expired_session():
    db = _session()
    from app import models

    db.add(
        models.AuthSession(
            token="tok_expired",
            user_email="admin@example.com",
            expires_at=datetime.utcnow() - timedelta(seconds=1),
        )
    )
    db.commit()

    assert auth.verify_token(db, "tok_expired") is None


def test_logout_deletes_the_session(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", auth.hash_password("correct-horse"))
    db = _session()
    session = auth.login(db, "admin@example.com", "correct-horse")
    db.commit()

    auth.logout(db, session.token)
    db.commit()

    assert auth.verify_token(db, session.token) is None
