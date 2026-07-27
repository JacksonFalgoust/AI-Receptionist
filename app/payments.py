"""Glue between the Booqable reservation data and outbound payment-link
delivery -- kept separate from reservations.py (Booqable-only) and the
per-vendor clients (twilio_client.py, postmark_client.py). Supports both an
email channel (Postmark) and an SMS channel (Twilio); SMS is currently
unavailable pending carrier/government verification, so
config.PAYMENT_LINK_DEFAULT_CHANNEL defaults to "email". build_test_payment_link
is a placeholder: no real Stripe/Booqable payment-link generation exists yet
(see docs/PAYMENT_LINK_OPTIONS.md)."""

from __future__ import annotations

from typing import Any

from . import config, reservations
from .booqable_client import BooqableClient, BooqableError
from .postmark_client import PostmarkClient
from .twilio_client import TwilioSmsClient


def build_test_payment_link(order_id: str) -> str:
    return f"{config.PAYMENT_LINK_BASE_URL}/{order_id}"


def _normalize_channel(channel: str) -> str:
    value = (channel or "").strip().lower()
    if value in ("email", "e-mail", "mail"):
        return "email"
    if value in ("sms", "text", "message"):
        return "sms"
    raise BooqableError(f"Unknown payment link channel {channel!r}; expected 'email' or 'sms'")


def _looks_like_email(value: str) -> bool:
    if not value or any(ch.isspace() for ch in value):
        return False
    local, sep, domain = value.rpartition("@")
    return bool(sep) and bool(local) and "." in domain.strip(".")


def _payment_message(name: str | None, link: str) -> tuple[str, str, str]:
    greeting = f"Hi {name}," if name else "Hi,"
    subject = "Your bike rental payment link"
    text_body = (
        f"{greeting}\n\n"
        f"Here's your payment link for your reservation:\n{link}\n\n"
        "Thanks!"
    )
    html_body = (
        f"<p>{greeting}</p>"
        f'<p>Here\'s your payment link for your reservation: <a href="{link}">{link}</a></p>'
        "<p>Thanks!</p>"
    )
    return subject, text_body, html_body


async def send_payment_link(
    booqable_client: BooqableClient,
    *,
    order_id: str,
    channel: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    sms_client: TwilioSmsClient | None = None,
    postmark_client: PostmarkClient | None = None,
) -> dict[str, Any]:
    channel = _normalize_channel(channel or config.PAYMENT_LINK_DEFAULT_CHANNEL)
    contact = await reservations.get_order_contact(booqable_client, order_id)
    link = build_test_payment_link(order_id)

    if channel == "email":
        to_email = email or contact.get("email")
        if not to_email:
            raise BooqableError(f"No email address on file for order {order_id}; pass one explicitly")
        if not _looks_like_email(to_email):
            raise BooqableError(
                f"{to_email!r} doesn't look like a valid email address; confirm it with the caller"
            )
        subject, text_body, html_body = _payment_message(contact.get("name"), link)
        client = postmark_client or PostmarkClient()
        await client.send_email(to=to_email, subject=subject, text_body=text_body, html_body=html_body)
        return {"order_id": order_id, "channel": "email", "sent_to": to_email, "payment_link": link}

    to_phone = phone or contact.get("phone")
    if not to_phone:
        raise BooqableError(f"No phone number on file for order {order_id}; pass one explicitly")
    greeting = f"Hi {contact['name']}, " if contact.get("name") else "Hi, "
    client = sms_client or TwilioSmsClient()
    await client.send_sms(
        to=to_phone,
        body=f"{greeting}here's your payment link for your reservation: {link}",
    )
    return {"order_id": order_id, "channel": "sms", "sent_to": to_phone, "payment_link": link}
