"""Minimal real authentication for E6 slice 1: one hardcoded admin
credential (app/config.py's ADMIN_EMAIL/ADMIN_PASSWORD_HASH), bearer tokens
persisted in the auth_sessions table so logout and expiry are enforced
server-side rather than only client-trusted.

A real multi-user Users & Roles backend (frontend/TODO.md's own future E6
slice) replaces ADMIN_EMAIL/ADMIN_PASSWORD_HASH with a real users table --
login()/verify_token()'s shape is designed so that slice only has to change
where the credential/role come from, not this module's callers
(app/auth_api.py, app/conversations_api.py's require_auth dependency).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from . import config, models
from .db import get_db

_PBKDF2_ITERATIONS = 200_000


def hash_password(plaintext: str) -> str:
    """PBKDF2-HMAC-SHA256, salted. Format: "<salt_hex>:<hash_hex>" so
    verify_password never needs a second place to read the salt from. Good
    enough for one hardcoded demo credential; a real Users & Roles backend
    should use a vetted library (e.g. passlib) instead."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", plaintext.encode(), bytes.fromhex(salt), _PBKDF2_ITERATIONS)
    return f"{salt}:{digest.hex()}"


def verify_password(plaintext: str, hashed: str) -> bool:
    try:
        salt, digest_hex = hashed.split(":", 1)
    except ValueError:
        return False
    expected = hashlib.pbkdf2_hmac("sha256", plaintext.encode(), bytes.fromhex(salt), _PBKDF2_ITERATIONS)
    return hmac.compare_digest(expected.hex(), digest_hex)


class InvalidCredentials(Exception):
    pass


def login(db: Session, email: str, password: str) -> models.AuthSession:
    if not config.ADMIN_PASSWORD_HASH or email != config.ADMIN_EMAIL:
        raise InvalidCredentials()
    if not verify_password(password, config.ADMIN_PASSWORD_HASH):
        raise InvalidCredentials()

    session = models.AuthSession(
        token=secrets.token_urlsafe(32),
        user_email=email,
        expires_at=datetime.utcnow() + timedelta(seconds=config.AUTH_TOKEN_TTL_SECONDS),
    )
    db.add(session)
    db.flush()
    return session


def logout(db: Session, token: str) -> None:
    session = db.get(models.AuthSession, token)
    if session:
        db.delete(session)


def verify_token(db: Session, token: str) -> models.AuthSession | None:
    session = db.get(models.AuthSession, token)
    if session is None or session.expires_at <= datetime.utcnow():
        return None
    return session


def require_auth(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> models.AuthSession:
    """FastAPI dependency: every protected route (Task 4's conversations_api.py)
    takes `Depends(require_auth)`. Matches frontend/src/services/http.ts's
    `Authorization: Bearer <token>` header and its 401 handling exactly."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token = authorization.removeprefix("Bearer ")
    session = verify_token(db, token)
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    return session
