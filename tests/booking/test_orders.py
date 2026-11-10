from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.booking.orders import (
    Booking,
    BookingSummary,
    classify,
    parse_timestamp,
    payment_label,
    sort_for_view,
    summarize,
    to_bookings,
)

NOW = datetime(2026, 11, 10, 15, 0, tzinfo=UTC)
TZ = ZoneInfo("America/New_York")
HOUR = timedelta(hours=1)
DAY = timedelta(days=1)


def _order(id, status, starts_at, stops_at, payment_status="paid", customer_id="c1", **attrs):
    return {
        "id": id,
        "type": "orders",
        "attributes": {
            "status": status,
            "starts_at": starts_at,
            "stops_at": stops_at,
            "payment_status": payment_status,
            "customer_id": customer_id,
            **attrs,
        },
    }


def _booking(id, view, starts_at, stops_at, payment="paid"):
    return Booking(
        id=id, number=None, view=view, label=None, starts_at=starts_at, stops_at=stops_at,
        customer_name=None, customer_phone=None, customer_email=None,
        total_cents=0, payment=payment, item_count=None,
    )


@pytest.mark.parametrize("status", ["draft", "new", "archived"])
def test_hidden_statuses_are_dropped(status):
    assert classify(status, NOW + DAY, NOW) is None


@pytest.mark.parametrize(
    "status,stops_at,expected",
    [
        ("canceled", NOW + DAY, ("past", "canceled")),
        ("stopped", NOW - DAY, ("past", "returned")),
        ("started", NOW + DAY, ("upcoming", "out_now")),
        ("started", NOW - DAY, ("upcoming", "overdue")),
        ("reserved", NOW + DAY, ("upcoming", None)),
        ("reserved", NOW - DAY, ("past", "not_picked_up")),
    ],
)
def test_classification_table(status, stops_at, expected):
    assert classify(status, stops_at, NOW) == expected


def test_unknown_status_falls_back_to_dates():
    assert classify("concept", NOW + HOUR, NOW) == ("upcoming", None)
    assert classify("concept", NOW - HOUR, NOW) == ("past", None)


def test_missing_stops_at_goes_to_past():
    assert classify("reserved", None, NOW) == ("past", "not_picked_up")
    assert classify("started", None, NOW) == ("upcoming", "out_now")


def test_payment_label():
    assert payment_label("paid") == "paid"
    assert payment_label("overpaid") == "paid"
    assert payment_label("partially_paid") == "partly_paid"
    assert payment_label("payment_due") == "unpaid"
    assert payment_label(None) == "unpaid"


def test_parse_timestamp():
    parsed = parse_timestamp("2026-11-04T14:00:00.000000+00:00")
    assert parsed.tzinfo is not None
    assert parsed == datetime(2026, 11, 4, 14, tzinfo=UTC)
    assert parse_timestamp(None) is None
    assert parse_timestamp("") is None


def test_to_bookings_joins_customer():
    order = _order(
        "o1", "reserved", "2026-11-12T14:00:00+00:00", "2026-11-13T14:00:00+00:00",
        number=42, item_count=3, grand_total_in_cents=12500,
    )
    customer = {
        "type": "customers", "id": "c1",
        "attributes": {"name": "Maria Lopez", "email": "m@example.com", "properties": {"phone": "+15552014477"}},
    }
    [booking] = to_bookings([order], [customer], NOW)
    assert booking.customer_name == "Maria Lopez"
    assert booking.customer_phone == "+15552014477"
    assert booking.customer_email == "m@example.com"
    assert booking.total_cents == 12500
    assert booking.number == 42
    assert booking.item_count == 3
    assert booking.view == "upcoming"
    assert booking.starts_at == datetime(2026, 11, 12, 14, tzinfo=UTC)


def test_order_without_customer_still_listed():
    orders = [
        _order("o1", "reserved", "2026-11-12T14:00:00+00:00", "2026-11-13T14:00:00+00:00", customer_id=None),
        _order("o2", "reserved", "2026-11-12T14:00:00+00:00", "2026-11-13T14:00:00+00:00", customer_id="missing"),
        _order("o3", "draft", "2026-11-12T14:00:00+00:00", "2026-11-13T14:00:00+00:00"),
    ]
    bookings = to_bookings(orders, [], NOW)
    assert [b.id for b in bookings] == ["o1", "o2"]
    assert all(b.customer_name is None for b in bookings)
    assert all(b.total_cents == 0 for b in bookings)


def test_sort_for_view():
    soon = _booking("soon", "upcoming", NOW + DAY, NOW + 2 * DAY)
    later = _booking("later", "upcoming", NOW + 3 * DAY, NOW + 4 * DAY)
    undated = _booking("undated", "upcoming", None, None)
    old = _booking("old", "past", NOW - 5 * DAY, NOW - 4 * DAY)
    recent = _booking("recent", "past", NOW - 2 * DAY, NOW - DAY)
    past_undated = _booking("past_undated", "past", None, None)
    everything = [undated, later, old, soon, past_undated, recent]
    assert [b.id for b in sort_for_view(everything, "upcoming")] == ["soon", "later", "undated"]
    assert [b.id for b in sort_for_view(everything, "past")] == ["recent", "old", "past_undated"]


def test_summary_counts():
    # NOW is 10:00 on Nov 10 in New York; the 7-day window ends at Nov 17 00:00 New York (05:00 UTC).
    a = _booking("a", "upcoming", datetime(2026, 11, 10, 14, tzinfo=UTC), datetime(2026, 11, 12, 14, tzinfo=UTC))
    b = _booking("b", "upcoming", datetime(2026, 11, 9, 14, tzinfo=UTC), datetime(2026, 11, 10, 22, tzinfo=UTC))
    c = _booking("c", "upcoming", datetime(2026, 11, 14, 15, tzinfo=UTC), datetime(2026, 11, 16, 15, tzinfo=UTC), "unpaid")
    d = _booking("d", "upcoming", datetime(2026, 11, 17, 5, tzinfo=UTC), datetime(2026, 11, 18, 5, tzinfo=UTC), "partly_paid")
    e = _booking("e", "past", datetime(2026, 11, 10, 14, tzinfo=UTC), datetime(2026, 11, 10, 20, tzinfo=UTC), "unpaid")
    # pickups_today: a. returns_today: b. next_7_days: a, c (b started yesterday, d is on the boundary). unpaid: c, d.
    assert summarize([a, b, c, d, e], NOW, TZ) == BookingSummary(
        pickups_today=1, returns_today=1, next_7_days=2, unpaid=2
    )


def test_summary_uses_business_day_not_utc_day():
    now = datetime(2026, 11, 10, 20, 0, tzinfo=UTC)  # 3 PM in New York
    booking = _booking(
        "x", "upcoming",
        datetime(2026, 11, 11, 5, 30, tzinfo=UTC),  # 00:30 Nov 11 New York
        datetime(2026, 11, 11, 4, 30, tzinfo=UTC),  # 23:30 Nov 10 New York
    )
    summary = summarize([booking], now, TZ)
    assert summary.returns_today == 1
    assert summary.pickups_today == 0
