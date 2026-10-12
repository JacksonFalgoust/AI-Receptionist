import asyncio
import json
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app import config, guide_client, payments
from app.booqable_client import BooqableClient
from app.guide_client import GuideSession
from app.main import app, mask_phone
from app.reservations import find_or_create_customer


# --- payments: first-name greeting + caller-phone fallback ---


def test_sms_greets_by_first_name_only(monkeypatch):
    monkeypatch.setattr(config, "PAYMENT_LINK_BASE_URL", "https://example.com/pay")
    monkeypatch.setattr(
        payments.reservations,
        "get_order_contact",
        AsyncMock(return_value={"order_id": "o1", "name": "A quarry Brackens", "phone": "+15550001111"}),
    )
    sms = AsyncMock()
    asyncio.run(payments.send_payment_link(object(), order_id="o1", channel="sms", sms_client=sms))
    assert sms.send_sms.call_args.kwargs["body"].startswith("Hi A, ")


def test_sms_falls_back_to_caller_phone_when_order_has_none(monkeypatch):
    monkeypatch.setattr(
        payments.reservations,
        "get_order_contact",
        AsyncMock(return_value={"order_id": "o1", "name": None, "phone": None}),
    )
    sms = AsyncMock()
    result = asyncio.run(
        payments.send_payment_link(
            object(), order_id="o1", channel="sms", sms_client=sms, fallback_phone="+15550002222"
        )
    )
    assert result["sent_to"] == "+15550002222"
    assert sms.send_sms.call_args.kwargs["body"].startswith("Hi, ")


def test_execute_send_payment_link_passes_caller_phone_as_fallback(monkeypatch):
    monkeypatch.setattr(guide_client, "BooqableClient", lambda: object())
    send = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr(guide_client.payments, "send_payment_link", send)
    session = GuideSession(caller_phone="+15550003333")
    asyncio.run(guide_client._execute_tool("sendPaymentLink", json.dumps({"order_id": "o1", "channel": "sms"}), session))
    assert send.call_args.kwargs["fallback_phone"] == "+15550003333"
    assert send.call_args.kwargs["phone"] is None


# --- per-call caches ---


def test_list_catalog_cached_per_call(monkeypatch):
    monkeypatch.setattr(guide_client, "BooqableClient", lambda: object())
    lc = AsyncMock(return_value=[{"product_id": "p1"}])
    monkeypatch.setattr(guide_client.reservations, "list_catalog", lc)
    session = GuideSession()
    for _ in range(3):
        asyncio.run(guide_client._execute_tool("listCatalog", "{}", session))
    assert lc.await_count == 1
    asyncio.run(guide_client._execute_tool("listCatalog", "{}", GuideSession()))
    assert lc.await_count == 2  # new call, fresh fetch


def test_location_cached_and_reused_by_create_reservation(monkeypatch):
    monkeypatch.setattr(guide_client, "BooqableClient", lambda: object())
    rl = AsyncMock(return_value={"id": "loc_1"})
    monkeypatch.setattr(guide_client.reservations, "resolve_location", rl)
    monkeypatch.setattr(
        guide_client.reservations, "check_product_availability", AsyncMock(return_value={"status": "available"})
    )
    cr = AsyncMock(return_value={"order_id": "o1"})
    monkeypatch.setattr(guide_client.reservations, "create_reservation", cr)
    session = GuideSession()
    avail = {"product_id": "p1", "starts_at": "2026-10-13T09:00:00", "stops_at": "2026-10-13T18:00:00"}
    asyncio.run(guide_client._execute_tool("checkAvailability", json.dumps(avail), session))
    asyncio.run(guide_client._execute_tool("checkAvailability", json.dumps(avail), session))
    assert rl.await_count == 1
    args = {"customer_name": "Jane", "customer_phone": "+15550004444", "items": [{"product_id": "p1", "quantity": 1}],
            "starts_at": avail["starts_at"], "stops_at": avail["stops_at"]}
    asyncio.run(guide_client._execute_tool("createReservation", json.dumps(args), session))
    assert cr.call_args.kwargs["location"] == {"id": "loc_1"}


# --- createReservation reuses the get_caller_phone_number lookup ---


def _reserve(session, phone):
    args = {"customer_name": "Jane", "customer_phone": phone, "items": [{"product_id": "p1", "quantity": 1}],
            "starts_at": "2026-10-13T09:00:00", "stops_at": "2026-10-13T18:00:00"}
    return asyncio.run(guide_client._execute_tool("createReservation", json.dumps(args), session))


def test_create_reservation_reuses_caller_lookup_for_same_number(monkeypatch):
    monkeypatch.setattr(guide_client, "BooqableClient", lambda: object())
    cr = AsyncMock(return_value={"order_id": "o1"})
    monkeypatch.setattr(guide_client.reservations, "create_reservation", cr)
    session = GuideSession(caller_phone="+15550005555", known_customer_checked=True, known_customer=None)
    _reserve(session, "555-000-5555")
    assert "prefetched_customer" in cr.call_args.kwargs
    assert cr.call_args.kwargs["prefetched_customer"] is None


def test_create_reservation_looks_up_when_number_differs(monkeypatch):
    monkeypatch.setattr(guide_client, "BooqableClient", lambda: object())
    cr = AsyncMock(return_value={"order_id": "o1"})
    monkeypatch.setattr(guide_client.reservations, "create_reservation", cr)
    session = GuideSession(caller_phone="+15550005555", known_customer_checked=True)
    _reserve(session, "+15550009999")
    assert "prefetched_customer" not in cr.call_args.kwargs


def test_find_or_create_customer_prefetched_skips_lookup():
    client = object.__new__(BooqableClient)
    client.list_all = AsyncMock()
    client.post = AsyncMock(return_value={"data": {"id": "new"}})
    out = asyncio.run(find_or_create_customer(client, name="Jane", phone="+15550006666", prefetched=None))
    assert out == {"id": "new"}
    client.list_all.assert_not_called()
    existing = {"id": "cust_1", "attributes": {}}
    out = asyncio.run(find_or_create_customer(client, name="Jane", phone="+15550006666", prefetched=existing))
    assert out is existing


# --- logging / TwiML ---


def test_mask_phone_keeps_last_four_only():
    assert mask_phone("+15551234567") == "***4567"
    assert mask_phone(None) == "none"


def test_twiml_sets_deepgram_model_and_language(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "")
    monkeypatch.setattr(config, "BOOQABLE_API_KEY", "")
    r = TestClient(app).post("/twiml", data={"CallSid": "CA1", "From": "+15551234567"})
    assert r.status_code == 200
    assert 'speechModel="nova-3-general"' in r.text
    assert 'language="en-US"' in r.text
