"""app/dashboard_store.py -- KPI counts, recent-activity/escalation
derivation, range resolution, and org-scoping for the Overview page
(E6 dashboard slice). See docs/superpowers/specs/
2026-09-22-e6-dashboard-design.md."""

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import conversation_store, dashboard_store, models
from app.db import Base


def _session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_range_bounds_today_is_a_rolling_24_hour_window(monkeypatch):
    fixed_now = datetime(2026, 9, 20, 12, 0, 0)

    class _FixedDatetime(datetime):
        @classmethod
        def utcnow(cls):
            return fixed_now

    monkeypatch.setattr(dashboard_store, "datetime", _FixedDatetime)

    from_, to = dashboard_store.range_bounds("today", None, None)

    assert from_ == fixed_now - timedelta(hours=24)
    assert to is None


def test_range_bounds_7d_and_30d_are_rolling_day_windows(monkeypatch):
    fixed_now = datetime(2026, 9, 20, 12, 0, 0)

    class _FixedDatetime(datetime):
        @classmethod
        def utcnow(cls):
            return fixed_now

    monkeypatch.setattr(dashboard_store, "datetime", _FixedDatetime)

    assert dashboard_store.range_bounds("7d", None, None) == (fixed_now - timedelta(days=7), None)
    assert dashboard_store.range_bounds("30d", None, None) == (fixed_now - timedelta(days=30), None)


def test_range_bounds_custom_uses_the_literal_from_and_to():
    from_ = datetime(2026, 1, 1)
    to = datetime(2026, 1, 31)

    assert dashboard_store.range_bounds("custom", from_, to) == (from_, to)


def test_range_bounds_no_preset_is_unbounded():
    assert dashboard_store.range_bounds(None, None, None) == (None, None)
