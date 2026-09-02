"""The spoken welcome greeting, shared by both phone demos: Conversation
Relay (app/main.py) passes it to Twilio as `welcome_greeting`, and the local
audio demo (app/local_demo_api.py) synthesizes it through GuideAnts.
"""

from __future__ import annotations

import asyncio
import logging

from . import config, reservations
from .booqable_client import BooqableClient

logger = logging.getLogger("voice_receptionist")


async def greeting_for(from_number: str) -> str:
    """Personalize the welcome greeting for a known Booqable customer, by
    caller phone number. Falls back to the plain WELCOME_GREETING on any
    failure -- this sits directly in the call-answering path (Twilio expects
    a prompt TwiML response), so a slow/unreachable Booqable or an unset
    BOOQABLE_API_KEY (which makes BooqableClient() itself raise immediately,
    see booqable_client.py) must never delay or break answering the call."""
    if not from_number:
        return config.WELCOME_GREETING
    try:
        client = BooqableClient()
        customer = await asyncio.wait_for(
            reservations.find_customer(client, phone=from_number),
            timeout=config.CALLER_LOOKUP_TIMEOUT_SECONDS,
        )
        if not customer:
            return config.WELCOME_GREETING
        name = (client.attrs(customer).get("name") or "").split()
        if not name:
            return config.WELCOME_GREETING
        return config.WELCOME_BACK_GREETING_TEMPLATE.format(name=name[0])
    except Exception:
        logger.warning("Caller lookup failed; using default greeting", exc_info=True)
        return config.WELCOME_GREETING
