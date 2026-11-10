"""Per-call context the guide is given beyond the caller's words: who is
calling (a known Booqable customer) and the current time, plus a background
prefetch of the Booqable catalog/location so the first tool turn is fast."""

import asyncio
import contextlib
import logging

from app import config
from app.booking import business_hours, reservations
from app.booking.booqable_client import BooqableClient

from .session import GuideSession

logger = logging.getLogger("voice_receptionist.guide")


async def lookup_known_caller(session: GuideSession) -> None:
    """Look the caller's number up in Booqable right at call setup (the same
    lookup get_caller_phone_number does), so the first turn can tell the guide
    who is calling. Best effort; never raises."""
    if session.known_customer_checked or not session.caller_phone:
        return
    try:
        client = BooqableClient()
        session.known_customer = await asyncio.wait_for(
            reservations.find_customer(client, phone=session.caller_phone),
            timeout=config.CALLER_LOOKUP_TIMEOUT_SECONDS,
        )
        session.known_customer_checked = True
    except Exception as exc:  # pragma: no cover - best effort
        logger.info("Known-caller lookup skipped: %s", type(exc).__name__)


def known_caller_note(session: GuideSession) -> str | None:
    """One-time note for the guide naming a known caller. Never contains the
    phone number itself -- only its last four digits, spoken."""
    if not session.known_customer:
        return None
    name = (BooqableClient.attrs(session.known_customer).get("name") or "").strip()
    if not name:
        return None
    digits = "".join(ch for ch in (session.caller_phone or "") if ch.isdigit())
    last_four = ", ".join(digits[-4:]) if len(digits) >= 4 else ""
    ending = f" (number ending in {last_four})" if last_four else ""
    return (
        f"[Note: this caller is a known customer, {name}, calling from the number on file{ending}. "
        f"They were already greeted by first name. Never ask for their name, and don't call "
        f"get_caller_phone_number for them: to book, call createReservation with customer_name "
        f"'{name}' and leave customer_phone empty (the number they're calling from is used). "
        f"Skipping the name and phone questions does NOT skip the recap: before booking, always read "
        f"back the item, day, start time and total, ending with 'Booking under {name}, shall I go "
        f"ahead?', and book only after they say yes.]"
    )


async def _with_known_caller_note(user_text: str, session: GuideSession) -> str:
    if session.known_caller_note_sent:
        return user_text
    session.known_caller_note_sent = True
    now_text = ""
    if config.NOW_NOTE_ENABLED:
        with contextlib.suppress(Exception):
            now_text = business_hours.now_note()
    if not config.KNOWN_CALLER_NOTE_ENABLED:
        return f"{now_text} {user_text}" if now_text else user_text
    task = session.caller_lookup_task
    if task is not None and not task.done():
        with contextlib.suppress(Exception):
            await asyncio.wait_for(asyncio.shield(task), timeout=config.CALLER_LOOKUP_TIMEOUT_SECONDS)
    note = known_caller_note(session)
    prefix = " ".join(x for x in (now_text, note) if x)
    return f"{prefix} {user_text}" if prefix else user_text


async def prefetch_booqable(session: GuideSession) -> None:
    """Fill the per-call catalog and location caches in the background right
    after call setup, so the first listCatalog/checkAvailability turn doesn't
    wait on ~2-3 s of Booqable reads. Best effort; never raises."""
    try:
        client = BooqableClient()
        catalog, location = await asyncio.gather(
            reservations.list_catalog(client), reservations.resolve_location(client, None)
        )
        if session.catalog_cache is None:
            session.catalog_cache = catalog
        if session.location_cache is None:
            session.location_cache = location
    except Exception as exc:  # pragma: no cover - best effort
        logger.info("Booqable prefetch skipped: %s", type(exc).__name__)
