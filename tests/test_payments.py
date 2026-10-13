import asyncio
from unittest.mock import AsyncMock

import pytest

from app import config, payments
from app.booqable_client import BooqableError


def test_build_test_payment_link(monkeypatch):
    monkeypatch.setattr(config, "PAYMENT_LINK_BASE_URL", "https://example.com/pay")
    assert payments.build_test_payment_link("order_1") == "https://example.com/pay/order_1"


# --- SMS channel ---


def test_send_payment_link_sms_uses_contact_phone(monkeypatch):
    monkeypatch.setattr(config, "PAYMENT_LINK_BASE_URL", "https://example.com/pay")
    monkeypatch.setattr(
        payments.reservations,
        "get_order_contact",
        AsyncMock(return_value={"order_id": "order_1", "name": "Jane Doe", "phone": "+15551234567"}),
    )
    sms_client = AsyncMock()

    result = asyncio.run(
        payments.send_payment_link(object(), order_id="order_1", channel="sms", sms_client=sms_client)
    )

    assert result == {
        "order_id": "order_1",
        "channel": "sms",
        "sent_to": "+15551234567",
        "payment_link": "https://example.com/pay/order_1",
    }
    sms_client.send_sms.assert_called_once_with(
        to="+15551234567",
        body=payments.confirmation_sms("Jane", None, "https://example.com/pay/order_1", payments._business_name()),
    )


def test_send_payment_link_sms_prefers_explicit_phone_override(monkeypatch):
    monkeypatch.setattr(config, "PAYMENT_LINK_BASE_URL", "https://example.com/pay")
    monkeypatch.setattr(
        payments.reservations,
        "get_order_contact",
        AsyncMock(return_value={"order_id": "order_1", "name": "Jane Doe", "phone": "+15551234567"}),
    )
    sms_client = AsyncMock()

    result = asyncio.run(
        payments.send_payment_link(
            object(), order_id="order_1", channel="sms", phone="+15559998888", sms_client=sms_client
        )
    )

    assert result["sent_to"] == "+15559998888"
    sms_client.send_sms.assert_called_once_with(
        to="+15559998888",
        body=payments.confirmation_sms("Jane", None, "https://example.com/pay/order_1", payments._business_name()),
    )


def test_send_payment_link_sms_raises_without_any_phone(monkeypatch):
    monkeypatch.setattr(
        payments.reservations,
        "get_order_contact",
        AsyncMock(return_value={"order_id": "order_1", "name": "Jane Doe", "phone": None}),
    )
    sms_client = AsyncMock()

    with pytest.raises(BooqableError):
        asyncio.run(payments.send_payment_link(object(), order_id="order_1", channel="sms", sms_client=sms_client))

    sms_client.send_sms.assert_not_called()


def test_send_payment_link_channel_text_normalizes_to_sms(monkeypatch):
    monkeypatch.setattr(config, "PAYMENT_LINK_BASE_URL", "https://example.com/pay")
    monkeypatch.setattr(
        payments.reservations,
        "get_order_contact",
        AsyncMock(return_value={"order_id": "order_1", "name": "Jane Doe", "phone": "+15551234567"}),
    )
    sms_client = AsyncMock()

    result = asyncio.run(
        payments.send_payment_link(object(), order_id="order_1", channel="text", sms_client=sms_client)
    )

    assert result["channel"] == "sms"
    sms_client.send_sms.assert_called_once()


# --- Email channel ---


def test_send_payment_link_email_uses_contact_email(monkeypatch):
    monkeypatch.setattr(config, "PAYMENT_LINK_BASE_URL", "https://example.com/pay")
    monkeypatch.setattr(
        payments.reservations,
        "get_order_contact",
        AsyncMock(
            return_value={
                "order_id": "order_1",
                "name": "Jane Doe",
                "phone": "+15551234567",
                "email": "jane@example.com",
            }
        ),
    )
    postmark_client = AsyncMock()

    result = asyncio.run(
        payments.send_payment_link(
            object(), order_id="order_1", channel="email", postmark_client=postmark_client
        )
    )

    assert result == {
        "order_id": "order_1",
        "channel": "email",
        "sent_to": "jane@example.com",
        "payment_link": "https://example.com/pay/order_1",
    }
    postmark_client.send_email.assert_called_once_with(
        to="jane@example.com",
        subject="Your bike rental payment link",
        text_body=(
            "Hi Jane,\n\n"
            "Here's your payment link for your reservation:\n"
            "https://example.com/pay/order_1\n\n"
            "Thanks!"
        ),
        html_body=(
            '<p>Hi Jane,</p>'
            '<p>Here\'s your payment link for your reservation: '
            '<a href="https://example.com/pay/order_1">https://example.com/pay/order_1</a></p>'
            "<p>Thanks!</p>"
        ),
    )


def test_send_payment_link_email_prefers_explicit_email_override(monkeypatch):
    monkeypatch.setattr(config, "PAYMENT_LINK_BASE_URL", "https://example.com/pay")
    monkeypatch.setattr(
        payments.reservations,
        "get_order_contact",
        AsyncMock(
            return_value={
                "order_id": "order_1",
                "name": "Jane Doe",
                "phone": "+15551234567",
                "email": "jane@example.com",
            }
        ),
    )
    postmark_client = AsyncMock()

    result = asyncio.run(
        payments.send_payment_link(
            object(),
            order_id="order_1",
            channel="email",
            email="override@example.com",
            postmark_client=postmark_client,
        )
    )

    assert result["sent_to"] == "override@example.com"
    postmark_client.send_email.assert_called_once()
    assert postmark_client.send_email.call_args.kwargs["to"] == "override@example.com"


def test_send_payment_link_email_raises_without_any_email(monkeypatch):
    monkeypatch.setattr(
        payments.reservations,
        "get_order_contact",
        AsyncMock(return_value={"order_id": "order_1", "name": "Jane Doe", "phone": "+15551234567", "email": None}),
    )
    postmark_client = AsyncMock()

    with pytest.raises(BooqableError):
        asyncio.run(
            payments.send_payment_link(
                object(), order_id="order_1", channel="email", postmark_client=postmark_client
            )
        )

    postmark_client.send_email.assert_not_called()


def test_send_payment_link_email_raises_on_malformed_email(monkeypatch):
    monkeypatch.setattr(
        payments.reservations,
        "get_order_contact",
        AsyncMock(return_value={"order_id": "order_1", "name": "Jane Doe", "phone": None, "email": None}),
    )
    postmark_client = AsyncMock()

    with pytest.raises(BooqableError):
        asyncio.run(
            payments.send_payment_link(
                object(),
                order_id="order_1",
                channel="email",
                email="not-an-email",
                postmark_client=postmark_client,
            )
        )

    postmark_client.send_email.assert_not_called()


def test_send_payment_link_channel_e_mail_normalizes_to_email(monkeypatch):
    monkeypatch.setattr(config, "PAYMENT_LINK_BASE_URL", "https://example.com/pay")
    monkeypatch.setattr(
        payments.reservations,
        "get_order_contact",
        AsyncMock(
            return_value={"order_id": "order_1", "name": "Jane Doe", "phone": None, "email": "jane@example.com"}
        ),
    )
    postmark_client = AsyncMock()

    result = asyncio.run(
        payments.send_payment_link(
            object(), order_id="order_1", channel="e-mail", postmark_client=postmark_client
        )
    )

    assert result["channel"] == "email"
    postmark_client.send_email.assert_called_once()


# --- Channel selection ---


def test_send_payment_link_uses_default_channel_from_config(monkeypatch):
    monkeypatch.setattr(config, "PAYMENT_LINK_BASE_URL", "https://example.com/pay")
    monkeypatch.setattr(config, "PAYMENT_LINK_DEFAULT_CHANNEL", "sms")
    monkeypatch.setattr(
        payments.reservations,
        "get_order_contact",
        AsyncMock(return_value={"order_id": "order_1", "name": "Jane Doe", "phone": "+15551234567", "email": None}),
    )
    sms_client = AsyncMock()

    result = asyncio.run(payments.send_payment_link(object(), order_id="order_1", sms_client=sms_client))

    assert result["channel"] == "sms"
    sms_client.send_sms.assert_called_once()


def test_send_payment_link_unknown_channel_raises(monkeypatch):
    monkeypatch.setattr(
        payments.reservations,
        "get_order_contact",
        AsyncMock(return_value={"order_id": "order_1", "name": "Jane Doe", "phone": "+15551234567", "email": None}),
    )

    with pytest.raises(BooqableError):
        asyncio.run(payments.send_payment_link(object(), order_id="order_1", channel="carrier-pigeon"))


def test_confirmation_sms_includes_confirmation_id(monkeypatch):
    monkeypatch.setattr(config, "PAYMENT_LINK_BASE_URL", "https://example.com/pay")
    monkeypatch.setattr(
        payments.reservations,
        "get_order_contact",
        AsyncMock(return_value={"order_id": "order_1", "name": "Eric Smith", "phone": "+15550003374", "order_number": 54}),
    )
    sms_client = AsyncMock()
    result = asyncio.run(
        payments.send_payment_link(object(), order_id="order_1", channel="sms", sms_client=sms_client)
    )
    assert result["confirmation_id"] == "#54"
    sms_client.send_sms.assert_called_once_with(
        to="+15550003374",
        body=payments.confirmation_sms("Eric", 54, "https://example.com/pay/order_1", payments._business_name()),
    )


def test_confirmation_sms_wording():
    assert payments.confirmation_sms("Eric", 54, "https://x/pay", "Peachtree Pedals") == (
        "Hi Eric, your reservation with Peachtree Pedals is confirmed. Confirmation number: #54. "
        "You can pay securely ahead of your visit here: https://x/pay Thank you!"
    )
    assert payments.confirmation_sms(None, None, "L") == (
        "Hello, your reservation is confirmed. You can pay securely ahead of your visit here: L Thank you!"
    )
