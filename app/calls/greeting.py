"""The welcome greeting spoken when a call is answered: personalized for a
known Booqable customer, else the last published greeting, else
config.WELCOME_GREETING."""

import asyncio
import logging

from app import config
from app.booking import reservations
from app.booking.booqable_client import BooqableClient, BooqableError

logger = logging.getLogger("voice_receptionist")


def _published_greeting() -> str:
    """The greeting from the last SUCCEEDED publish, or the configured
    default. Reading the published snapshot rather than the live
    configuration row is what preserves draft semantics: editing a greeting
    in the console must not change what callers hear until Publish.

    Wrapped in a broad try like the rest of this function's lookups -- it
    sits in the call-answering path, and a database problem must never
    delay answering the phone."""
    try:
        from app import db as db_module
        from app.guide.publish import publisher

        session = db_module.SessionLocal()
        try:
            publication = publisher.latest_succeeded(session)
            if publication:
                greeting = (publication.published_config or {}).get("identity", {}).get(
                    "greeting"
                )
                if greeting:
                    return greeting
        finally:
            session.close()
    except Exception:  # noqa: BLE001 -- never block answering a call
        logger.warning("could not read published greeting; using the default", exc_info=True)
    return config.WELCOME_GREETING


async def greeting_for(from_number: str) -> str:
    """Personalize the welcome greeting for a known Booqable customer, by
    caller phone number. Falls back to the published greeting (or the plain
    WELCOME_GREETING if nothing has been published) on any failure -- this
    sits directly in the call-answering path (Twilio expects a prompt TwiML
    response), so a slow/unreachable Booqable or an unset BOOQABLE_API_KEY
    (which makes BooqableClient() itself raise immediately, see
    app/booking/booqable_client.py) must never delay or break answering the call."""
    if not from_number:
        return _published_greeting()
    try:
        client = BooqableClient()
        customer = await asyncio.wait_for(
            reservations.find_customer(client, phone=from_number),
            timeout=config.CALLER_LOOKUP_TIMEOUT_SECONDS,
        )
        if not customer:
            return _published_greeting()
        name = (client.attrs(customer).get("name") or "").split()
        if not name:
            return _published_greeting()
        return config.WELCOME_BACK_GREETING_TEMPLATE.format(name=name[0])
    except (BooqableError, asyncio.TimeoutError, Exception):
        logger.warning("Caller lookup failed; using default greeting", exc_info=True)
        return _published_greeting()
