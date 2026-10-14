"""Stock guard (dated catalog, booking refusal), payment-link guard, text-or-email STT fix."""

import asyncio
import json

import pytest

from app import guide_client, reservations, stt_fixups
from app.booqable_client import BooqableError
from app.guide_client import GuideSession

CATALOG = [
    {"product_id": "p-dash", "name": "Downtown Dash"},
    {"product_id": "p-loop", "name": "Lake Loop"},
    {"product_id": "p-helmet", "name": "Helmet"},
]
AVAIL = {"p-dash": 0, "p-loop": 2, "p-helmet": 5}


@pytest.fixture
def fake_booqable(monkeypatch):
    checked = []

    async def check(client, *, product_id, location_id, starts_at, stops_at, quantity):
        checked.append(product_id)
        a = AVAIL[product_id]
        status = "unavailable" if a <= 0 else ("partial" if a < quantity else "available")
        return {"status": status, "available": a, "requested": quantity}

    async def catalog(client):
        return list(CATALOG)

    async def loc(client, session, location_id):
        return {"id": "loc-1"}

    monkeypatch.setattr(reservations, "check_product_availability", check)
    monkeypatch.setattr(reservations, "list_catalog", catalog)
    monkeypatch.setattr(guide_client, "_default_location", loc)
    monkeypatch.setattr(guide_client, "BooqableClient", lambda: object())
    return checked


def _run(name, args, session=None):
    return asyncio.run(guide_client._run_reservation_tool(name, args, session or GuideSession()))


def test_dated_catalog_lists_only_in_stock_items(fake_booqable):
    out = _run("listCatalog", {"starts_at": "2026-10-13T12:00:00", "stops_at": "2026-10-13T18:00:00"})
    assert [p["name"] for p in out["products"]] == ["Lake Loop"]
    assert out["unavailable"] == ["Downtown Dash"]
    assert [p["name"] for p in out["accessories"]] == ["Helmet"]
    assert "p-helmet" not in fake_booqable  # accessories aren't stock-checked as main items


def test_undated_catalog_says_availability_not_checked(fake_booqable):
    out = _run("listCatalog", {})
    assert out["availability_checked"] is False
    assert [p["name"] for p in out["products"]] == ["Downtown Dash", "Lake Loop"]
    assert [p["name"] for p in out["accessories"]] == ["Helmet"]


def test_create_reservation_refuses_out_of_stock(fake_booqable, monkeypatch):
    created = []

    async def no_customer(*a, **k):
        created.append("customer")
        return {"id": "c1"}

    monkeypatch.setattr(reservations, "find_or_create_customer", no_customer)

    class Client:
        async def post(self, *a, **k):
            created.append("order")
            return {"data": {"id": "o1"}}

    with pytest.raises(BooqableError, match="NOT BOOKED"):
        asyncio.run(reservations.create_reservation(
            Client(), customer={"name": "X", "phone": "+15550001111"}, location_id=None,
            location={"id": "loc-1"}, starts_at="2026-10-13T12:00:00", stops_at="2026-10-13T18:00:00",
            items=[{"product_id": "p-dash", "quantity": 1}],
        ))
    assert created == []  # no customer, no order


def test_ensure_items_available_passes_when_in_stock(fake_booqable):
    asyncio.run(reservations.ensure_items_available(
        object(), location_id="loc-1", starts_at="2026-10-13T12:00:00", stops_at="2026-10-13T18:00:00",
        items=[{"product_id": "p-loop", "quantity": 2}],
    ))
    with pytest.raises(BooqableError):
        asyncio.run(reservations.ensure_items_available(
            object(), location_id="loc-1", starts_at="2026-10-13T12:00:00", stops_at="2026-10-13T18:00:00",
            items=[{"product_id": "p-loop", "quantity": 3}],
        ))


def test_payment_link_refused_when_turn_asked_a_question(monkeypatch):
    sent = []

    async def send(client, **k):
        sent.append(k)
        return {"sent": True}

    monkeypatch.setattr(guide_client.payments, "send_payment_link", send)
    monkeypatch.setattr(guide_client, "BooqableClient", lambda: object())
    s = GuideSession()
    s.round_text = "Just to make sure, by text to the number ending in 1 1 1 1?"
    out = _run("sendPaymentLink", {"order_id": "o1", "channel": "sms"}, s)
    assert out["sent"] is False and "NOT SENT" in out["error"] and not sent
    s.round_text = "Sending that now."
    assert _run("sendPaymentLink", {"order_id": "o1", "channel": "sms"}, s) == {"sent": True}


def test_round_text_collects_all_rounds(monkeypatch):
    async def fake_turn(client, inp, session, outcome):
        if isinstance(inp, str):
            yield "Okay, by text?"
            outcome.function_calls.append(("c1", "sendPaymentLink", "{}"))
        else:
            yield "declare victory Done."

    async def outputs(outcome, session):
        return [{"type": "function_call_output"}]

    monkeypatch.setattr(guide_client, "_stream_turn", fake_turn)
    monkeypatch.setattr(guide_client, "_tool_outputs", outputs)
    s = GuideSession()

    async def run():
        return [e async for e in guide_client._stream_reply_with_tools(None, "Text", s)]

    asyncio.run(run())
    assert "by text?" in s.round_text and "Done." in s.round_text


@pytest.mark.parametrize("heard", ["Tex.", "by tex", "Texts"])  # unclear "6"/"next": see test_hours_email_known_booking.py
def test_text_mishearing_fixed_after_text_or_email(heard):
    assert stt_fixups.fix_choice("Would you like it by text or by email?", heard) == "Text."


@pytest.mark.parametrize("agent,heard", [
    ("How many bikes would you like?", "6."),
    ("Would you like it by text or by email?", "Email."),
    ("Would you like it by text or by email?", "Next week please"),
])
def test_text_fix_is_narrow(agent, heard):
    assert stt_fixups.fix_choice(agent, heard) == heard


def test_text_after_tool_waits_for_earlier_speech_to_finish(monkeypatch):
    import time
    from fastapi.testclient import TestClient
    from app import config, main, twilio_auth
    from app.guide_client import Delta, ToolCallStarted
    from tests.test_streaming_and_tool_barge_in import _read_or_timeout

    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-ws-secret")
    monkeypatch.setattr(config, "TURN_PAUSE_SECONDS", 0.01)
    monkeypatch.setattr(config, "TTS_WORDS_PER_SECOND", 10.0)  # 6 words ~ 0.6 s
    monkeypatch.setattr(config, "FILLER_ONLY_FOR_TOOL_CALLS", True)

    async def fake(input_text, guide):
        yield Delta("Sure, checking both bikes right now.")
        yield ToolCallStarted(("checkAvailability",))
        yield Delta(" Both are free.")

    monkeypatch.setattr(main, "stream_reply", fake)
    sid = "CA_nocut"
    with TestClient(main.app).websocket_connect(f"/ws?token={twilio_auth.mint_ws_token(sid)}") as ws:
        ws.send_json({"type": "setup", "callSid": sid, "from": "+15551234567", "to": "+15557654321"})
        ws.send_json({"type": "prompt", "voicePrompt": "Is it free Monday?", "last": True})
        stamps = []
        while (f := _read_or_timeout(ws, timeout=2.0)) is not None:
            if f["type"] == "text" and f.get("token", "").strip():
                stamps.append((time.monotonic(), f["token"]))
            if f.get("last"):
                break
    first = next(t for t, tok in stamps if "checking" in tok)
    second = next(t for t, tok in stamps if "Both are free" in tok)
    assert second - first >= 0.4
