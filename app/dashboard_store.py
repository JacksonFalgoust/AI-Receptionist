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
