"""SQLAlchemy-backed CRUD for conversation history (E6 slice 1). Called by
app/conversations_api.py (reads) and app/call_recording.py (the one write,
at call end). Every function takes a Session rather than opening its own,
so callers control the transaction boundary (see app/db.py's
get_db/session_scope) -- none of these functions commit.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import config, models

_VALID_OUTCOMES = {"completed", "escalated", "abandoned", "failed", "follow_up_required"}


def create_conversation(
    db: Session,
    *,
    customer_name: str | None,
    customer_phone: str | None,
    started_at: datetime,
    ended_at: datetime,
    intent: str | None,
    outcome: str,
    escalated: bool,
    summary: str | None,
    messages: list[dict[str, Any]],
    actions: list[dict[str, Any]],
) -> models.Conversation:
    if outcome not in _VALID_OUTCOMES:
        outcome = "completed"

    conversation = models.Conversation(
        organization_id=config.DEFAULT_ORGANIZATION_ID,
        customer_name=customer_name,
        customer_phone=customer_phone,
        channel="voice",
        started_at=started_at,
        ended_at=ended_at,
        duration_seconds=int((ended_at - started_at).total_seconds()),
        intent=intent,
        outcome=outcome,
        escalated=escalated,
        summary=summary,
    )
    conversation.messages = [
        models.ConversationMessage(speaker=m["speaker"], text=m["text"], at=m["at"])
        for m in messages
    ]
    conversation.actions = [
        models.ConversationAction(
            action=a["action"],
            system=a["system"],
            at=a.get("at", ended_at),
            result=a["result"],
            status=a["status"],
            details=a.get("details"),
        )
        for a in actions
    ]
    db.add(conversation)
    db.flush()
    return conversation


def get_conversation(db: Session, conversation_id: str) -> models.Conversation | None:
    return db.get(models.Conversation, conversation_id)


def list_conversations(
    db: Session,
    *,
    search: str | None = None,
    channel: str | None = None,
    intent: str | None = None,
    outcome: str | None = None,
    escalated: bool | None = None,
    location_id: str | None = None,
    assigned_employee: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[models.Conversation], int]:
    """Newest first, matching the mock service's sortByDesc(startedAt)."""
    query = select(models.Conversation)
    if channel:
        query = query.where(models.Conversation.channel == channel)
    if intent:
        query = query.where(models.Conversation.intent == intent)
    if outcome:
        query = query.where(models.Conversation.outcome == outcome)
    if escalated is not None:
        query = query.where(models.Conversation.escalated == escalated)
    if assigned_employee:
        query = query.where(models.Conversation.assigned_employee == assigned_employee)
    # location_id is accepted but never applied -- there is no multi-location
    # model yet (see the design spec's scope cuts); filtering on it would
    # just return zero rows instead of ignoring the filter.
    if date_from:
        query = query.where(models.Conversation.started_at >= date_from)
    if date_to:
        query = query.where(models.Conversation.started_at <= date_to)
    if search:
        like = f"%{search}%"
        query = query.where(
            (models.Conversation.customer_name.ilike(like))
            | (models.Conversation.customer_phone.ilike(like))
            | (models.Conversation.intent.ilike(like))
            | (models.Conversation.summary.ilike(like))
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    page = max(page, 1)
    page_size = max(page_size, 1)
    rows = list(
        db.scalars(
            query.order_by(models.Conversation.started_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return rows, total


def list_distinct_intents(db: Session) -> list[str]:
    return list(
        db.scalars(
            select(models.Conversation.intent)
            .where(models.Conversation.intent.is_not(None))
            .distinct()
            .order_by(models.Conversation.intent)
        )
    )
