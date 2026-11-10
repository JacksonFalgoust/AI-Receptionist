"""Client-side tool calls: GuideAnts hands every tool call declared on the
guide back to this app, and execute_tool answers it in-process."""

import asyncio
import contextlib
import json
import logging
import re
from datetime import datetime
from typing import Any

from app import config
from app.booking import business_hours, payments, reservations
from app.booking.booqable_client import BooqableClient, BooqableError
from app.booking.postmark_client import PostmarkError
from app.booking.twilio_client import TwilioSmsError

from .session import GuideSession

logger = logging.getLogger("voice_receptionist.guide")


# All of these tools -- get_caller_phone_number plus the Booqable reservation
# operations below -- are declared as GuideAnts "Client Actions" tool sources
# (see guide-demo/caller-phone-client-tool.json and
# guide-demo/reservations-client-tool.json), not attached by this app --
# GuideAnts includes them on the guide's behalf and, being client-handled (a
# client:// server URL), never executes them itself: it always hands the
# function_call back to whichever client is on that conversation. This app
# only needs to answer it when it arrives. The reservation operations used to
# be a Web API tool source that GuideAnts called directly against
# /api/reservations/*; moving them here means there's no HTTP endpoint left
# for anyone but this app (mid-call) to invoke them through -- see
# docs/ARCHITECTURE.md's "Client-side tool calls" section.
_RESERVATION_TOOLS = {
    "listCatalog",
    "checkAvailability",
    "listCustomers",
    "createCustomer",
    "createReservation",
    "findReservations",
    "cancelReservation",
    "sendPaymentLink",
}

# Business-language (action, system) label for each reservation tool's
# ConversationAction row -- mirrors the frontend's routingLabels.ts/
# knowledgeLabels.ts pattern of keeping raw identifiers out of admin-facing
# copy.
_TOOL_ACTION_LABELS: dict[str, tuple[str, str]] = {
    "listCatalog": ("List catalog", "Booqable"),
    "checkAvailability": ("Check availability", "Booqable"),
    "listCustomers": ("Look up customer", "Booqable"),
    "createCustomer": ("Create customer", "Booqable"),
    "createReservation": ("Create reservation", "Booqable"),
    "findReservations": ("Find reservation", "Booqable"),
    "cancelReservation": ("Cancel reservation", "Booqable"),
    "sendPaymentLink": ("Send payment link", "Messaging"),
}


def _same_phone(a: str | None, b: str | None) -> bool:
    return bool(a and b) and reservations._normalize_phone(a) == reservations._normalize_phone(b)


async def _default_location(client, session: "GuideSession | None", location_id: str | None) -> dict[str, Any]:
    if location_id or session is None:
        return await reservations.resolve_location(client, location_id)
    if session.location_cache is None:
        session.location_cache = await reservations.resolve_location(client, None)
    return session.location_cache


async def _run_reservation_tool(
    name: str, args: dict[str, Any], session: "GuideSession | None" = None
) -> dict[str, Any]:
    """Execute one Booqable-backed reservation tool -- the same business
    logic the old /api/reservations/* routes wrapped (app/booking/reservations.py,
    app/booking/payments.py), called directly instead of over HTTP. Required
    arguments missing from `args` raise KeyError, caught by the caller."""
    client = BooqableClient()
    if name == "listCatalog":
        if session is not None and session.prefetch_task is not None:
            with contextlib.suppress(Exception):
                await session.prefetch_task
        if session is not None and session.catalog_cache is not None:
            catalog = session.catalog_cache
        else:
            catalog = await reservations.list_catalog(client)
            if session is not None:
                session.catalog_cache = catalog
        if args.get("starts_at") and args.get("stops_at"):
            if config.BUSINESS_HOURS_GUARD_ENABLED:
                problem = business_hours.check_window(
                    args["starts_at"], args["stops_at"], for_booking=False
                )
                if problem:
                    return business_hours.closed_result(problem)
            location = await _default_location(client, session, args.get("location_id"))
            return await reservations.list_available_catalog(
                client, catalog, location_id=location["id"],
                starts_at=args["starts_at"], stops_at=args["stops_at"],
                quantity=int(args.get("quantity") or 1),
            )
        main = [p for p in catalog if not reservations.is_accessory(p.get("name"))]
        return {
            "products": main,
            "accessories": [p for p in catalog if reservations.is_accessory(p.get("name"))],
            "availability_checked": False,
            "note": "Availability NOT checked. Don't say any item is available until you've called "
                    "listCatalog with starts_at/stops_at or checkAvailability.",
        }
    if name == "checkAvailability":
        if config.BUSINESS_HOURS_GUARD_ENABLED and args.get("starts_at"):
            problem = business_hours.check_window(
                args["starts_at"], args.get("stops_at"), for_booking=False
            )
            if problem:
                return business_hours.closed_result(problem)
        location = await _default_location(client, session, args.get("location_id"))
        result = await reservations.check_product_availability(
            client,
            product_id=args["product_id"],
            location_id=location["id"],
            starts_at=args["starts_at"],
            stops_at=args["stops_at"],
            quantity=args.get("quantity", 1),
        )
        return {**result, "location_id": location["id"]}
    if name == "listCustomers":
        return {"customers": await reservations.list_customers(client)}
    if name == "createCustomer":
        return await reservations.register_customer(
            client,
            name=args["customer_name"],
            email=args.get("customer_email"),
            phone=args.get("customer_phone"),
            note=args.get("note"),
        )
    if name == "createReservation":
        if config.BOOKING_CONFIRM_GUARD_ENABLED and session is not None:
            key = _booking_key(args)
            if booking_confirmed(session):
                session.recap_yes_key = key
            elif not (session.recap_yes_key == key and _after_contact_question(session)):
                return {
                    "error": "NOT BOOKED: confirm details with caller first. Read back the item, day, start "
                             "time, total price and name, ending with 'Booking under <name>, shall I go "
                             "ahead?', wait for their answer, and only call createReservation after they "
                             "clearly say yes. If they already said yes to that recap and you only asked "
                             "for a phone number or email since, call createReservation right after they "
                             "answer, with the same details -- no new recap.",
                    "booked": False,
                }
        if (
            session is not None
            and not args.get("customer_email")
            and not args.get("customer_phone")
            and session.caller_phone
        ):
            # No contact given: book with the number they're calling from --
            # known callers, and new callers who chose "the number I'm
            # calling from" (22:14 call: the guide left it out and the
            # booking failed, forcing a re-ask and a second recap).
            args = {**args, "customer_phone": session.caller_phone}
        if (
            session is not None
            and not (args.get("customer_name") or "").strip()
            and session.known_customer
        ):
            args = {**args, "customer_name": BooqableClient.attrs(session.known_customer).get("name") or ""}
        if not args.get("customer_email") and not args.get("customer_phone"):
            return {
                "error": "NOT BOOKED: a phone number or email is needed. Ask the caller for one, then "
                         "call createReservation right after they answer, with the same details -- "
                         "they already confirmed the recap, so no new recap.",
                "booked": False,
            }
        extra: dict[str, Any] = {}
        if not args.get("location_id") and session is not None and session.location_cache:
            # Resolved earlier this call (checkAvailability always runs first).
            extra["location"] = session.location_cache
        if (
            session is not None
            and session.known_customer_checked
            and not args.get("customer_email")
            and _same_phone(args.get("customer_phone"), session.caller_phone)
        ):
            # get_caller_phone_number already looked this exact number up
            # this call -- reuse that result instead of a second customers GET.
            extra["prefetched_customer"] = session.known_customer
        return await reservations.create_reservation(
            client,
            customer={
                "name": args["customer_name"],
                "email": args.get("customer_email"),
                "phone": args.get("customer_phone"),
            },
            location_id=args.get("location_id"),
            starts_at=args["starts_at"],
            stops_at=args["stops_at"],
            items=args["items"],
            auto_reserve=args.get("auto_reserve", True),
            **extra,
        )
    if name == "findReservations":
        return await reservations.find_reservations(
            client, email=args.get("customer_email"), phone=args.get("customer_phone")
        )
    if name == "cancelReservation":
        return await reservations.cancel_reservation(client, args["order_id"])
    if name == "sendPaymentLink":
        if session is not None and "?" in (session.round_text or ""):
            # Guard: the model asked the caller something in this same turn
            # (e.g. "by text to the number ending in ...?") -- wait for the answer.
            return {
                "error": "NOT SENT: you asked the caller a question in this same turn. Wait for "
                         "their answer, then call sendPaymentLink.",
                "sent": False,
            }
        if (args.get("channel") or "sms").strip().lower() not in ("sms", "text") or args.get("email"):
            # Email payment links were removed (spelled addresses are misheard
            # on the phone, and the 18:46 test call took ~90 s and still failed).
            return {
                "error": "NOT SENT: payment links are only sent by text message, never by email. Tell the "
                         "caller you can text it to the number they're calling from (or a number they "
                         "give you), and call sendPaymentLink with channel sms once they agree.",
                "sent": False,
            }
        return await payments.send_payment_link(
            client,
            order_id=args["order_id"],
            channel="sms",
            phone=args.get("phone"),
            # SMS with no number from the guide: payments falls back to the
            # order's phone, then to the number this call came from.
            fallback_phone=session.caller_phone if session is not None else None,
        )
    raise KeyError(name)


_AFFIRMATIVE = re.compile(
    r"^(yes|yeah|yep|yup|yes please|correct|that'?s (right|correct|it|fine)|right|sure|ok(ay)? yes|"
    r"go ahead|please do|do it|book it|let'?s do it|let'?s book it|sounds good|absolutely|"
    r"of course|perfect|uh huh|mm hmm|you got it)\b"
)
_LEADING_ACKS_RE = re.compile(r"^(ok(ay)?|alright|all right|well|um|uh|great|perfect)\s+")
_RECAP_QUESTION = re.compile(
    r"(shall i|should i|can i|may i|do you want me to|would you like me to|want me to|ready for me to|"
    r"okay to|ok to)\b[^?]*\b(book|reserve|go ahead|lock|confirm)|booking under[^?]*\?|"
    r"go ahead and (book|reserve)[^?]*\?|book (it|that|this)[^?]*\?"
)


def _is_affirmative(user_text: str) -> bool:
    text = re.sub(r"\[[^\]]*\]", " ", user_text or "")  # drop app notes
    norm = " ".join(re.sub(r"[^a-z' ]+", " ", text.lower()).split())
    norm = _LEADING_ACKS_RE.sub("", norm) if not _AFFIRMATIVE.match(norm) else norm
    return bool(_AFFIRMATIVE.match(norm))


_CONTACT_QUESTION = re.compile(r"\b(phone|number|email|e-mail|calling from|reach you)\b")


def _booking_key(args: dict) -> str:
    """The booking details a recap covers: items, times and name."""
    return json.dumps(
        [
            args.get("items"),
            args.get("starts_at"),
            args.get("stops_at"),
            " ".join((args.get("customer_name") or "").lower().split()),
        ],
        sort_keys=True,
        default=str,
    )


def _after_contact_question(session: "GuideSession") -> bool:
    """The previous agent turn was a phone/email side question (not a change
    of the booking), so a recap yes from before it still stands."""
    prev = (session.prev_round_text or "").lower()
    return "?" in prev and bool(_CONTACT_QUESTION.search(prev))


def booking_confirmed(session: "GuideSession") -> bool:
    """True when the previous agent turn asked the recap/book-it question and
    the caller's reply this turn is a clear yes."""
    prev = (session.prev_round_text or "").lower()
    return "?" in prev and bool(_RECAP_QUESTION.search(prev)) and _is_affirmative(session.turn_user_text)


async def execute_tool(name: str, arguments: str, session: GuideSession) -> str:
    """Run one client-side tool call and return its result as the string to
    send back as a function_call_output. Never raises -- an error result is
    still a well-formed reply the model can react to."""
    if name == "endCall":
        session.end_call_requested = True
        return json.dumps({"ok": True, "note": "Say a brief goodbye now; the call ends right after it plays."})
    if name == "get_caller_phone_number":
        if not session.known_customer_checked:
            session.known_customer_checked = True
            if session.caller_phone:
                try:
                    client = BooqableClient()
                    session.known_customer = await asyncio.wait_for(
                        reservations.find_customer(client, phone=session.caller_phone),
                        timeout=config.CALLER_LOOKUP_TIMEOUT_SECONDS,
                    )
                except Exception:
                    session.known_customer = None
        result: dict[str, Any] = {"phone_number": session.caller_phone}
        digits = "".join(ch for ch in (session.caller_phone or "") if ch.isdigit())
        if len(digits) >= 4:
            # Read this to the caller -- never work the digits out yourself.
            result["last_four"] = digits[-4:]
            result["last_four_spoken"] = ", ".join(digits[-4:])
        if session.known_customer:
            attrs = BooqableClient.attrs(session.known_customer)
            if attrs.get("name"):
                result["customer_name"] = attrs["name"]
            if attrs.get("email"):
                result["customer_email"] = attrs["email"]
        return json.dumps(result)
    if name in _RESERVATION_TOOLS:
        try:
            args = json.loads(arguments) if arguments else {}
        except json.JSONDecodeError:
            logger.warning("Guide sent malformed arguments for %r: %r", name, arguments)
            args = {}
            result: dict[str, Any] = {"error": "malformed arguments"}
        else:
            try:
                result = await _run_reservation_tool(name, args, session)
            except (BooqableError, TwilioSmsError, PostmarkError) as exc:
                logger.warning("Reservation tool %r failed: %s", name, exc)
                result = {"error": str(exc)}
            except KeyError as exc:
                result = {"error": f"missing required argument: {exc}"}
        action_label, system_label = _TOOL_ACTION_LABELS.get(name, (name, "Booqable"))
        # Args can contain nested objects/arrays (e.g. createReservation's
        # `items` list of dicts), but ConversationAction.details is persisted
        # and rendered by the frontend as Record<str, str> -- flatten any
        # non-string value to its JSON representation so it's always
        # frontend-safe while staying informative.
        details = {k: v if isinstance(v, str) else json.dumps(v) for k, v in args.items()}
        session.actions.append(
            {
                "action": action_label,
                "system": system_label,
                "result": result.get("error", "Completed successfully"),
                "status": "error" if "error" in result else "success",
                "details": details,
                "at": datetime.utcnow(),
            }
        )
        return json.dumps(result)
    logger.warning("Guide requested unknown tool %r; returning error result", name)
    return json.dumps({"error": f"unknown tool: {name}"})
