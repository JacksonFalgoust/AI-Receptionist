"""SQLAlchemy-backed derivation for the Overview page's KPIs, recent
activity feed, and recent escalations feed (E6 dashboard slice). No new
table -- every value is computed from Conversation/ConversationAction rows
already written by app/conversation_store.py. Called only by
app/dashboard_api.py. See docs/superpowers/specs/
2026-09-22-e6-dashboard-design.md.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload

from . import config, models

DateRangePreset = Literal["today", "7d", "30d", "custom"]

_WINDOWS: dict[str, timedelta] = {
    "today": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


def range_bounds(
    preset: DateRangePreset | None,
    from_: datetime | None,
    to: datetime | None,
) -> tuple[datetime | None, datetime | None]:
    """Backend twin of frontend/src/lib/dateRange.ts's presetBounds --
    `today` is a rolling 24-hour window, not since-midnight. No preset at
    all means unbounded, matching the mock's rangeBounds(undefined)."""
    if preset is None:
        return None, None
    if preset == "custom":
        return from_, to
    return datetime.utcnow() - _WINDOWS[preset], None


def _conversations_in_range(from_: datetime | None, to: datetime | None) -> Select:
    query = select(models.Conversation).where(
        models.Conversation.organization_id == config.DEFAULT_ORGANIZATION_ID
    )
    if from_:
        query = query.where(models.Conversation.started_at >= from_)
    if to:
        query = query.where(models.Conversation.started_at <= to)
    return query


def _count(db: Session, query: Select) -> int:
    return db.scalar(select(func.count()).select_from(query.subquery())) or 0


def get_overview_kpis(
    db: Session, from_: datetime | None, to: datetime | None
) -> list[dict]:
    """The five KPIs US-2.2 requires, label and value only -- five simple
    SQL counts, not loaded into Python or combined into one clever query."""
    base = _conversations_in_range(from_, to)

    conversations_count = _count(db, base)
    voice_count = _count(db, base.where(models.Conversation.channel == "voice"))
    completed_count = _count(db, base.where(models.Conversation.outcome == "completed"))
    escalated_count = _count(db, base.where(models.Conversation.escalated.is_(True)))

    transactions_query = (
        select(func.count())
        .select_from(models.ConversationAction)
        .join(models.Conversation, models.ConversationAction.conversation_id == models.Conversation.id)
        .where(models.Conversation.organization_id == config.DEFAULT_ORGANIZATION_ID)
        .where(models.ConversationAction.status == "success")
        .where(models.ConversationAction.action.startswith("Create "))
    )
    if from_:
        transactions_query = transactions_query.where(models.Conversation.started_at >= from_)
    if to:
        transactions_query = transactions_query.where(models.Conversation.started_at <= to)
    transactions_count = db.scalar(transactions_query) or 0

    return [
        {"id": "conversations_today", "label": "Conversations Today", "value": conversations_count},
        {"id": "calls_answered", "label": "Calls Answered", "value": voice_count},
        {"id": "requests_completed", "label": "Requests Completed", "value": completed_count},
        {"id": "human_escalations", "label": "Human Escalations", "value": escalated_count},
        {"id": "transactions_created", "label": "Transactions Created", "value": transactions_count},
    ]


def list_recent_activity(
    db: Session, from_: datetime | None, to: datetime | None, limit: int
) -> list[models.ConversationAction]:
    """Newest-`at`-first, joined to the parent conversation (eager-loaded
    so the API layer never issues an N+1 query for customer_name/channel).
    Filtered on the action's own `at` -- not the conversation's
    started_at."""
    query = (
        select(models.ConversationAction)
        .join(models.Conversation, models.ConversationAction.conversation_id == models.Conversation.id)
        .where(models.Conversation.organization_id == config.DEFAULT_ORGANIZATION_ID)
        .options(joinedload(models.ConversationAction.conversation))
    )
    if from_:
        query = query.where(models.ConversationAction.at >= from_)
    if to:
        query = query.where(models.ConversationAction.at <= to)
    query = query.order_by(models.ConversationAction.at.desc()).limit(limit)
    return list(db.scalars(query))
