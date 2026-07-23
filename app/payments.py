"""Glue between the Booqable reservation data and outbound Twilio SMS --
kept separate from reservations.py (Booqable-only) and twilio_client.py
(Twilio-only). build_test_payment_link is a placeholder: no real Stripe/
Booqable payment-link generation exists yet (see docs/PAYMENT_LINK_OPTIONS.md)."""

from __future__ import annotations

from typing import Any

from . import config, reservations
from .booqable_client import BooqableClient, BooqableError
from .twilio_client import TwilioSmsClient


def build_test_payment_link(order_id: str) -> str:
    return f"{config.PAYMENT_LINK_BASE_URL}/{order_id}"


async def send_payment_link(
    booqable_client: BooqableClient,
    twilio_client: TwilioSmsClient,
    *,
    order_id: str,
    phone: str | None = None,
) -> dict[str, Any]:
    contact = await reservations.get_order_contact(booqable_client, order_id)
    to_phone = phone or contact["phone"]
    if not to_phone:
        raise BooqableError(f"No phone number on file for order {order_id}; pass one explicitly")

    link = build_test_payment_link(order_id)
    greeting = f"Hi {contact['name']}, " if contact.get("name") else "Hi, "
    await twilio_client.send_sms(
        to=to_phone,
        body=f"{greeting}here's your payment link for your reservation: {link}",
    )
    return {"order_id": order_id, "sent_to": to_phone, "payment_link": link}
