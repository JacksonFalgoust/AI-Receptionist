import asyncio
from unittest.mock import AsyncMock

import pytest

from app import config, payments
from app.booqable_client import BooqableError


def test_build_test_payment_link(monkeypatch):
    monkeypatch.setattr(config, "PAYMENT_LINK_BASE_URL", "https://example.com/pay")
    assert payments.build_test_payment_link("order_1") == "https://example.com/pay/order_1"


def test_send_payment_link_uses_contact_phone(monkeypatch):
    monkeypatch.setattr(config, "PAYMENT_LINK_BASE_URL", "https://example.com/pay")
    monkeypatch.setattr(
        payments.reservations,
        "get_order_contact",
        AsyncMock(return_value={"order_id": "order_1", "name": "Jane Doe", "phone": "+15551234567"}),
    )
    twilio_client = AsyncMock()

    result = asyncio.run(payments.send_payment_link(object(), twilio_client, order_id="order_1"))

    assert result == {
        "order_id": "order_1",
        "sent_to": "+15551234567",
        "payment_link": "https://example.com/pay/order_1",
    }
    twilio_client.send_sms.assert_called_once_with(
        to="+15551234567",
        body="Hi Jane Doe, here's your payment link for your reservation: https://example.com/pay/order_1",
    )


def test_send_payment_link_prefers_explicit_phone_override(monkeypatch):
    monkeypatch.setattr(config, "PAYMENT_LINK_BASE_URL", "https://example.com/pay")
    monkeypatch.setattr(
        payments.reservations,
        "get_order_contact",
        AsyncMock(return_value={"order_id": "order_1", "name": "Jane Doe", "phone": "+15551234567"}),
    )
    twilio_client = AsyncMock()

    result = asyncio.run(
        payments.send_payment_link(object(), twilio_client, order_id="order_1", phone="+15559998888")
    )

    assert result["sent_to"] == "+15559998888"
    twilio_client.send_sms.assert_called_once_with(
        to="+15559998888",
        body="Hi Jane Doe, here's your payment link for your reservation: https://example.com/pay/order_1",
    )


def test_send_payment_link_raises_without_any_phone(monkeypatch):
    monkeypatch.setattr(
        payments.reservations,
        "get_order_contact",
        AsyncMock(return_value={"order_id": "order_1", "name": "Jane Doe", "phone": None}),
    )
    twilio_client = AsyncMock()

    with pytest.raises(BooqableError):
        asyncio.run(payments.send_payment_link(object(), twilio_client, order_id="order_1"))

    twilio_client.send_sms.assert_not_called()
