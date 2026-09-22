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


def _seed_conversation(db, **overrides):
    defaults = dict(
        customer_name="Jane Doe",
        customer_phone="+15551234567",
        started_at=datetime(2026, 9, 1, 9, 0, 0),
        ended_at=datetime(2026, 9, 1, 9, 5, 0),
        intent="Book a rental",
        outcome="completed",
        escalated=False,
        summary="Booked an e-bike for Saturday.",
        messages=[],
        actions=[],
    )
    defaults.update(overrides)
    conversation = conversation_store.create_conversation(db, **defaults)
    db.commit()
    return conversation


def _raw_conversation(db, **overrides):
    """Bypasses create_conversation for scenarios it can't produce --
    non-voice channel and a different organization_id."""
    defaults = dict(
        organization_id="org_default",
        customer_name="Jane Doe",
        channel="voice",
        started_at=datetime(2026, 9, 1, 9, 0, 0),
        ended_at=datetime(2026, 9, 1, 9, 5, 0),
        outcome="completed",
        escalated=False,
    )
    defaults.update(overrides)
    conversation = models.Conversation(**defaults)
    db.add(conversation)
    db.commit()
    return conversation


def _kpi(kpis, kpi_id):
    return next(k for k in kpis if k["id"] == kpi_id)


def test_overview_kpis_returns_all_five_in_order():
    db = _session()
    _seed_conversation(db)

    kpis = dashboard_store.get_overview_kpis(db, None, None)

    assert [k["id"] for k in kpis] == [
        "conversations_today",
        "calls_answered",
        "requests_completed",
        "human_escalations",
        "transactions_created",
    ]
    assert [k["label"] for k in kpis] == [
        "Conversations Today",
        "Calls Answered",
        "Requests Completed",
        "Human Escalations",
        "Transactions Created",
    ]


def test_overview_kpis_conversations_today_counts_only_in_range():
    db = _session()
    _seed_conversation(db, started_at=datetime(2026, 9, 20, 9, 0), ended_at=datetime(2026, 9, 20, 9, 5))
    _seed_conversation(db, started_at=datetime(2026, 8, 1, 9, 0), ended_at=datetime(2026, 8, 1, 9, 5))

    kpis = dashboard_store.get_overview_kpis(db, datetime(2026, 9, 1), None)

    assert _kpi(kpis, "conversations_today")["value"] == 1


def test_overview_kpis_calls_answered_counts_voice_only():
    db = _session()
    _raw_conversation(db, channel="voice")
    _raw_conversation(db, channel="sms")

    kpis = dashboard_store.get_overview_kpis(db, None, None)

    assert _kpi(kpis, "conversations_today")["value"] == 2
    assert _kpi(kpis, "calls_answered")["value"] == 1


def test_overview_kpis_requests_completed_counts_completed_outcome_only():
    db = _session()
    _seed_conversation(db, outcome="completed")
    _seed_conversation(db, outcome="abandoned")

    kpis = dashboard_store.get_overview_kpis(db, None, None)

    assert _kpi(kpis, "requests_completed")["value"] == 1


def test_overview_kpis_human_escalations_counts_escalated_only():
    db = _session()
    _seed_conversation(db, escalated=True)
    _seed_conversation(db, escalated=False)

    kpis = dashboard_store.get_overview_kpis(db, None, None)

    assert _kpi(kpis, "human_escalations")["value"] == 1


def test_overview_kpis_transactions_created_counts_successful_creates_only():
    db = _session()
    _seed_conversation(
        db,
        actions=[
            {"action": "Create reservation", "system": "Booqable", "result": "ok", "status": "success"},
            {"action": "Cancel reservation", "system": "Booqable", "result": "ok", "status": "success"},
            {"action": "Create reservation", "system": "Booqable", "result": "err", "status": "error"},
        ],
    )

    kpis = dashboard_store.get_overview_kpis(db, None, None)

    assert _kpi(kpis, "transactions_created")["value"] == 1


def test_overview_kpis_org_scoping_excludes_other_organizations():
    db = _session()
    _seed_conversation(db)
    _raw_conversation(db, organization_id="org_other")

    kpis = dashboard_store.get_overview_kpis(db, None, None)

    assert _kpi(kpis, "conversations_today")["value"] == 1


def test_recent_activity_orders_newest_first_and_respects_limit():
    db = _session()
    for minute in (1, 2, 3):
        _seed_conversation(
            db,
            customer_name=f"Customer {minute}",
            actions=[
                {
                    "action": "Create reservation",
                    "system": "Booqable",
                    "result": "ok",
                    "status": "success",
                    "at": datetime(2026, 9, 20, 9, minute, 0),
                }
            ],
        )

    rows = dashboard_store.list_recent_activity(db, None, None, limit=2)

    assert [r.conversation.customer_name for r in rows] == ["Customer 3", "Customer 2"]


def test_recent_activity_filters_on_the_actions_own_at_not_conversation_started_at():
    db = _session()
    _seed_conversation(
        db,
        started_at=datetime(2026, 8, 1, 9, 0),
        ended_at=datetime(2026, 8, 1, 9, 5),
        actions=[
            {
                "action": "Create reservation",
                "system": "Booqable",
                "result": "ok",
                "status": "success",
                "at": datetime(2026, 9, 20, 9, 0, 0),
            }
        ],
    )

    rows = dashboard_store.list_recent_activity(db, datetime(2026, 9, 1), None, limit=8)

    assert len(rows) == 1


def test_recent_activity_org_scoping_excludes_other_organizations():
    db = _session()
    other = models.Conversation(
        organization_id="org_other",
        customer_name="Foreign Customer",
        channel="voice",
        started_at=datetime(2026, 9, 20, 9, 0),
        ended_at=datetime(2026, 9, 20, 9, 5),
        outcome="completed",
        escalated=False,
    )
    db.add(other)
    db.flush()
    db.add(
        models.ConversationAction(
            conversation_id=other.id,
            action="Create reservation",
            system="Booqable",
            at=datetime(2026, 9, 20, 9, 0),
            result="ok",
            status="success",
        )
    )
    db.commit()

    rows = dashboard_store.list_recent_activity(db, None, None, limit=8)

    assert rows == []
