"""18:20 test-call fixes: business-hours guard, now note, known-caller direct
booking, recap wording, unclear 'text', bare first greeting, email confirm."""

import asyncio
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app import business_hours, call_end, config, fillers, guide_client, reservations, stt_fixups
from app.booqable_client import BooqableError
from app.guide_client import GuideSession
from app.guide_publish import render

ET = ZoneInfo("America/New_York")
HOURS = [{"day": d, "open": "09:00", "close": "18:00", "closed": d == 0} for d in range(7)]  # Sunday closed
TUE_620PM = datetime(2026, 10, 13, 18, 20, tzinfo=ET)
TUE_10AM = datetime(2026, 10, 13, 10, 0, tzinfo=ET)
TEMPLATE = Path(__file__).resolve().parents[1] / "guide-demo" / "template" / "instructions.template.md"


@pytest.fixture(autouse=True)
def _tz(monkeypatch):
    monkeypatch.setattr(config, "BOOQABLE_TIMEZONE", "America/New_York")


# --- A: hours guard --------------------------------------------------------------

def test_today_after_close_is_closed_for_catalog_with_next_open():
    p = business_hours.check_window("2026-10-13T09:00:00", "2026-10-13T18:00:00",
                                    now=TUE_620PM, hours=HOURS, for_booking=False)
    assert p["reason"] == "after_close"
    assert p["next_open_spoken"] == "Wednesday, October 14th at 9 AM"


def test_today_while_open_whole_day_check_is_fine():
    assert business_hours.check_window("2026-10-13T09:00:00", "2026-10-13T18:00:00",
                                       now=TUE_10AM, hours=HOURS, for_booking=False) is None


@pytest.mark.parametrize("start,stop,reason", [
    ("2026-10-13T19:00:00", "2026-10-13T20:00:00", "after_close"),   # 7 PM
    ("2026-10-14T08:00:00", "2026-10-14T18:00:00", "before_open"),
    ("2026-10-14T18:00:00", "2026-10-14T18:30:00", "after_close"),   # at close
    ("2026-10-14T12:00:00", "2026-10-14T19:00:00", "stop_after_close"),
    ("2026-10-18T12:00:00", "2026-10-18T18:00:00", "closed_day"),    # Sunday
    ("2026-10-12T12:00:00", "2026-10-12T18:00:00", "past"),
])
def test_booking_refused_outside_hours(start, stop, reason):
    p = business_hours.check_window(start, stop, now=TUE_620PM, hours=HOURS, for_booking=True)
    assert p and p["reason"] == reason


def test_booking_in_hours_passes_and_utc_input_ok():
    assert business_hours.check_window("2026-10-14T16:00:00Z", "2026-10-14T22:00:00Z",
                                       now=TUE_620PM, hours=HOURS) is None


def test_next_open_skips_closed_sunday():
    sat_7pm = datetime(2026, 10, 17, 19, 0, tzinfo=ET)
    assert business_hours.next_open(sat_7pm, HOURS) == datetime(2026, 10, 19, 9, 0, tzinfo=ET)


def test_next_open_today_before_opening():
    early = datetime(2026, 10, 13, 7, 0, tzinfo=ET)
    assert business_hours.next_open(early, HOURS) == datetime(2026, 10, 13, 9, 0, tzinfo=ET)


def test_closed_result_has_no_items():
    p = business_hours.check_window("2026-10-13T09:00:00", "2026-10-13T18:00:00",
                                    now=TUE_620PM, hours=HOURS, for_booking=False)
    r = business_hours.closed_result(p)
    assert r["closed"] and r["products"] == [] and "Wednesday, October 14th at 9 AM" in r["note"]


def test_not_booked_message():
    p = business_hours.check_window("2026-10-13T19:00:00", None, now=TUE_620PM, hours=HOURS)
    msg = business_hours.not_booked_message(p)
    assert msg.startswith("NOT BOOKED: outside business hours") and "Next open: Wednesday" in msg


def test_create_reservation_guard_raises_before_any_booqable_call(monkeypatch):
    monkeypatch.setattr(config, "BUSINESS_HOURS_GUARD_ENABLED", True)
    monkeypatch.setattr(business_hours, "current_hours", lambda: HOURS)
    monkeypatch.setattr(business_hours, "now_local", lambda now=None: TUE_620PM)

    class Boom:
        def __getattr__(self, name):
            raise AssertionError("Booqable must not be called")

    with pytest.raises(BooqableError, match="NOT BOOKED: outside business hours"):
        asyncio.run(reservations.create_reservation(
            Boom(), customer={"name": "A B", "phone": "+15550000000"}, location_id="l",
            starts_at="2026-10-13T19:00:00", stops_at="2026-10-13T20:00:00",
            items=[{"product_id": "p", "quantity": 1}]))


def test_dated_list_catalog_closed_after_hours(monkeypatch):
    monkeypatch.setattr(config, "BUSINESS_HOURS_GUARD_ENABLED", True)
    monkeypatch.setattr(business_hours, "current_hours", lambda: HOURS)
    monkeypatch.setattr(business_hours, "now_local", lambda now=None: TUE_620PM)
    monkeypatch.setattr(guide_client, "BooqableClient", lambda: object())
    s = GuideSession()
    s.catalog_cache = [{"product_id": "p", "name": "Lake Loop"}]
    out = asyncio.run(guide_client._run_reservation_tool(
        "listCatalog", {"starts_at": "2026-10-13T09:00:00", "stops_at": "2026-10-13T18:00:00"}, s))
    assert out["closed"] and out["products"] == []


def test_now_note_after_close():
    note = business_hours.now_note(TUE_620PM, HOURS)
    assert "Tuesday, October 13th, 6:20 PM" in note
    assert "closed for today" in note and "Wednesday, October 14th at 9 AM" in note


def test_now_note_while_open():
    note = business_hours.now_note(TUE_10AM, HOURS)
    assert "open today until 6 PM" in note and "Next opening" not in note


# --- B: known callers book directly; no filler on the caller lookup ------------------

def test_known_caller_booking_uses_calling_number(monkeypatch):
    seen = {}

    async def fake_create(client, **kw):
        seen.update(kw)
        return {"order_id": "o"}

    monkeypatch.setattr(guide_client, "BooqableClient", lambda: object())
    monkeypatch.setattr(guide_client.reservations, "create_reservation", fake_create)
    s = GuideSession(caller_phone="+15550003374")
    s.known_customer = {"id": "c1", "attributes": {"name": "Eric Smith"}}
    s.location_cache = {"id": "loc"}
    asyncio.run(guide_client._run_reservation_tool("createReservation", {
        "customer_name": "Eric Smith", "starts_at": "x", "stops_at": "y",
        "items": [{"product_id": "p", "quantity": 1}]}, s))
    assert seen["customer"]["phone"] == "+15550003374" and seen["customer"]["name"] == "Eric Smith"


def test_unknown_caller_still_needs_contact(monkeypatch):
    monkeypatch.setattr(guide_client, "BooqableClient", lambda: object())
    with pytest.raises(BooqableError):
        asyncio.run(guide_client._run_reservation_tool("createReservation", {
            "customer_name": "A B", "starts_at": "x", "stops_at": "y", "items": []},
            GuideSession(caller_phone="+15550009999")))


def test_known_caller_note_says_book_directly():
    s = GuideSession(caller_phone="+15550003374")
    s.known_customer = {"id": "c1", "attributes": {"name": "Eric Smith"}}
    note = guide_client.known_caller_note(s)
    assert "don't call get_caller_phone_number" in note and "Booking under Eric Smith?" in note


def test_caller_phone_lookup_has_no_filler():
    assert fillers.pick_for_tools(["get_caller_phone_number"], ["x"]) is None


def test_first_turn_carries_now_note(monkeypatch):
    monkeypatch.setattr(config, "NOW_NOTE_ENABLED", True)
    monkeypatch.setattr(business_hours, "now_note", lambda *a, **k: "[Note: it is now X.]")
    out = asyncio.run(guide_client._with_known_caller_note("Hi there, a bike please", GuideSession()))
    assert out == "[Note: it is now X.] Hi there, a bike please"


# --- C: recap wording / instructions -------------------------------------------------

def test_template_rules():
    t = TEMPLATE.read_text(encoding="utf-8")
    assert "BUSINESS HOURS:" in t and "offer the next open day" in t
    assert '"Booking under"' in t and "read the details back again" in t


def test_spoken_name_default_aliases():
    assert render.spoken_name("Peachtree Pedals") == "Peach tree Peddles"


# --- unclear 'text' and bare greeting ------------------------------------------------

def test_clear_text_mishearing_still_fixed():
    assert stt_fixups.fix_choice("Would you like it by text or by email?", "Tex.") == "Text."


@pytest.mark.parametrize("heard", ["6.", "Six", "next"])
def test_unclear_text_asks_to_confirm(heard):
    out = stt_fixups.fix_choice("Would you like it by text or by email?", heard)
    assert "By text, right?" in out and out.endswith(heard)


@pytest.mark.parametrize("text,bare", [("Hi.", True), ("Hello?", True), ("Hi, I want a bike", False)])
def test_bare_greeting(text, bare):
    assert call_end.is_bare_greeting(text) is bare


# --- payment links: text only (email removed) ----------------------------------------

def _send(args, session=None):
    return asyncio.run(guide_client._run_reservation_tool(
        "sendPaymentLink", {"order_id": "o", **args}, session or GuideSession(caller_phone="+15550003374")))


@pytest.mark.parametrize("args", [
    {"channel": "email", "email": "someone@example.com"},
    {"channel": "email"},
    {"channel": "sms", "email": "someone@example.com"},
])
def test_email_payment_link_refused(monkeypatch, args):
    async def boom(*a, **k):
        raise AssertionError("must not send")

    monkeypatch.setattr(guide_client, "BooqableClient", lambda: object())
    monkeypatch.setattr(guide_client.payments, "send_payment_link", boom)
    out = _send(args)
    assert out["sent"] is False and out["error"].startswith("NOT SENT: payment links are only sent by text")


@pytest.mark.parametrize("args", [{"channel": "sms"}, {}, {"channel": "text"}])
def test_payment_link_always_sms_to_caller(monkeypatch, args):
    seen = {}

    async def fake_send(client, **kw):
        seen.update(kw)
        return {"sent": True}

    monkeypatch.setattr(guide_client, "BooqableClient", lambda: object())
    monkeypatch.setattr(guide_client.payments, "send_payment_link", fake_send)
    assert _send(args) == {"sent": True}
    assert seen["channel"] == "sms" and "email" not in seen
    assert seen["fallback_phone"] == "+15550003374"


def test_spec_and_template_have_no_email_channel():
    import json
    spec = json.loads((TEMPLATE.parents[0] / "OpenAPI" / "voice-receptionist.json").read_text(encoding="utf-8"))
    body = spec["paths"]["/{order_id}/send-payment-link"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert body["properties"]["channel"]["enum"] == ["sms"] and "email" not in body["properties"]
    t = TEMPLATE.read_text(encoding="utf-8")
    assert "only ever sent by text message, never by email" in t and "by text or by email" not in t
    assert "booking confirmation with your confirmation number and a secure payment link" in t
    assert "the confirmation\"" not in t
