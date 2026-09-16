"""POST /api/auth/login and /api/auth/logout -- frontend/src/services/
authService.ts's httpAuthService, made real for the first time. See
docs/superpowers/specs/2026-09-14-e6-conversation-history-design.md,
section 4."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import auth, config
from .db import get_db

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


class SessionUser(BaseModel):
    id: str
    name: str
    email: str
    role: str
    organizationId: str
    organizationName: str


class SessionResponse(BaseModel):
    token: str
    user: SessionUser
    expiresAt: str


@router.post("/api/auth/login", response_model=SessionResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> SessionResponse:
    try:
        session = auth.login(db, payload.email, payload.password)
    except auth.InvalidCredentials as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid email or password",
        ) from exc
    db.commit()
    return SessionResponse(
        token=session.token,
        user=SessionUser(
            id="owner",
            name="Owner",
            email=session.user_email,
            role="owner",
            organizationId=config.DEFAULT_ORGANIZATION_ID,
            organizationName="Default Organization",
        ),
        expiresAt=session.expires_at.isoformat() + "Z",
    )


@router.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(auth_session=Depends(auth.require_auth), db: Session = Depends(get_db)) -> None:
    auth.logout(db, auth_session.token)
    db.commit()
