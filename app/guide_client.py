"""Streams replies from a GuideAnts published guide via its OpenAI-compatible
wire API, using the /v1/responses endpoint with server-side conversation
continuation.

Every turn, including turn 1, is a streaming responses.create() call.
GuideAnts' streamed `response.created`/`response.completed` events carry the
`conversation` id, so it's captured directly from the stream -- no separate
non-streaming round trip is needed to establish continuation.

As a safety net for an older GuideAnts build whose stream doesn't carry the
id yet, if a turn with no conversation id completes without one, the session
is marked `stream_missing_conversation` and the *next* such turn falls back
to a single non-streaming call to obtain the id; turns after that stream
normally again.

If GuideAnts no longer recognizes a conversation id (e.g. it restarted), the
next call automatically falls back to starting a fresh conversation --
earlier context for that call is lost, but the caller still gets an answer.
"""

import asyncio
import contextlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator

import openai
from openai import AsyncOpenAI

from . import business_hours, call_end, config, payments, reservations
from .booqable_client import BooqableClient, BooqableError
from .postmark_client import PostmarkError
from .twilio_client import TwilioSmsError

logger = logging.getLogger("voice_receptionist.guide")

_client: AsyncOpenAI | None = None

# How much of an interrupted reply to quote back to the guide. Long enough to
# give real context, short enough not to balloon the prompt.
_INTERRUPTED_TAIL_CHARS = 150

_LOST_CONVERSATION_CODES = {"conversation_not_found", "invalid_conversation_id"}

# GuideAnts rejects a function_call_output whose turn is no longer "streaming"
# (it completed, or -- the case we hit -- was cancelled server-side when a
# mid-stream disconnect aborted the request that carried it). See
# GuideAnts' WireToolResultContinuation.cs. Treated like a lost conversation:
# the turn is unresumable, so recover by starting fresh rather than crashing.
_STALE_TOOL_RESULT_CODE = "tool_results_not_pending"

# Ceiling on responses.create calls within a single caller turn (one call, plus
# one more per round of tool calls) -- guards against a guide that keeps
# calling tools without ever producing a text answer.
_MAX_TOOL_ITERATIONS = 5

_VALID_OUTCOMES = {"completed", "escalated", "abandoned", "failed", "follow_up_required"}

_CLASSIFICATION_PROMPT = (
    "The call has ended. Reply with ONLY a JSON object, no other text, with "
    'these exact keys: "intent" (a short business-language description of '
    'what the caller wanted, e.g. "Book a rental"), "outcome" (one of: '
    "completed, escalated, abandoned, failed, follow_up_required), "
    '"escalated" (true or false), and "summary" (one or two sentences in '
    "business language, no internal jargon)."
)


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not config.GUIDEANTS_PUB_ID:
            raise RuntimeError(
                "GUIDEANTS_PUB_ID is not set. Copy .env.example to .env and fill it in."
            )
        _client = AsyncOpenAI(
            base_url=f"{config.GUIDEANTS_BASE_URL}/api/published/openai/{config.GUIDEANTS_PUB_ID}/v1",
            api_key=config.GUIDEANTS_API_KEY or "anonymous",
            timeout=config.GUIDEANTS_TIMEOUT_SECONDS,
            max_retries=1,
        )
    return _client


@dataclass(frozen=True)
class Delta:
    """A chunk of assistant text to speak, forwarded to Twilio verbatim."""

    text: str


@dataclass(frozen=True)
class ToolCallStarted:
    """A round ended in one or more client-side tool calls, about to be run.
    Nothing will be spoken until a later round's text clears the sentinel
    gate, which can be several seconds away (real Booqable HTTP time) --
    app.py uses this to soften barge-in for that gap so a caller talking
    into the silence can't cancel the answer that's still coming."""

    names: tuple[str, ...]


ReplyEvent = Delta | ToolCallStarted


@dataclass
class GuideSession:
    """Per-call state for one GuideAnts conversation: its continuation handle,
    plus data served to the guide on demand via client-side tools."""

    conversation_id: str | None = None
    # Set when a streamed turn with no conversation id completed without one
    # -- signals an older GuideAnts build; the next such turn falls back to
    # a non-streaming call to obtain the id.
    stream_missing_conversation: bool = False
    # The caller's phone number, captured from Twilio's `setup` `from` field
    # (see app/main.py). Served to the guide via the client-side
    # get_caller_phone_number tool -- not sent as prompt text, since it's
    # only relevant if/when the guide actually asks for it.
    caller_phone: str | None = None
    # Set the first time get_caller_phone_number is called this session --
    # caches whether a Booqable customer lookup for caller_phone has already
    # been attempted, so a call that invokes the tool more than once (e.g.
    # once during a reservation, again later for a callback) doesn't repeat
    # the lookup.
    known_customer_checked: bool = False
    # The matched Booqable customer record from that lookup, or None if not
    # yet checked, no match was found, or the lookup failed/timed out.
    known_customer: dict | None = None
    # Per-call caches for Booqable data that doesn't change mid-call: the
    # catalog (listCatalog) and the resolved default location. Saves the
    # repeat product_groups/locations GETs on later tool turns.
    catalog_cache: list | None = None
    # All text the model produced so far in the current caller turn (every
    # round, spoken or not) -- used by the sendPaymentLink guard.
    round_text: str = ""
    # Background Booqable prefetch started at call setup (see prefetch_booqable).
    prefetch_task: Any = None
    # Set when the guide calls endCall; app/main.py ends the ConversationRelay
    # session once the current reply's playback finishes.
    end_call_requested: bool = False
    location_cache: dict | None = None
    # Background known-caller lookup started at call setup (see
    # lookup_known_caller); the first turn's input carries its result.
    caller_lookup_task: Any = None
    # Booking-confirmation guard: the previous turn's agent text and this
    # turn's caller text (see booking_confirmed).
    prev_round_text: str = ""
    turn_user_text: str = ""
    # Set when the caller said yes to a recap: the booking details it covered
    # (see _booking_key). Lets createReservation through after a phone/email
    # side question without a second recap, if the details are unchanged.
    recap_yes_key: str | None = None
    known_caller_note_sent: bool = False
    # Business-language log of every reservation tool this call actually
    # ran, in call order -- persisted as ConversationAction rows by
    # app/call_recording.py at call end. Not sent to GuideAnts; purely an
    # observation of what _execute_tool did. get_caller_phone_number is
    # deliberately not logged here -- it's internal bookkeeping, not a
    # business action an admin needs to see in a call's action timeline.
    actions: list[dict] = field(default_factory=list)


def build_input(user_text: str, interrupted_partial: str | None) -> str:
    """Return the text to send as this turn's input.

    If the caller's previous reply was cut off by a barge-in, prefix a note
    telling the guide what the caller actually heard before interrupting, so
    it doesn't have to guess or repeat itself. See ARCHITECTURE.md
    ("Interruption notes") for the tradeoffs of this approach.
    """
    if not interrupted_partial:
        return user_text
    tail = interrupted_partial[-_INTERRUPTED_TAIL_CHARS:]
    note = f'[Note: your previous reply was interrupted; the caller heard only up to: "…{tail}"]'
    return f"{note} {user_text}"


def _extract_conversation_id(response) -> str | None:
    # GuideAnts returns conversation as the plain string "conv_...". The
    # openai SDK's type annotation models it as an object with `.id`; handle
    # both shapes in case the SDK ever starts constructing that object.
    conv = getattr(response, "conversation", None)
    if isinstance(conv, str):
        return conv or None
    conv_id = getattr(conv, "id", None)
    return conv_id or None


def _is_lost_conversation(err: "openai.BadRequestError") -> bool:
    code = getattr(err, "code", None)
    return code in _LOST_CONVERSATION_CODES


def _is_stale_tool_result(err: "openai.BadRequestError") -> bool:
    return getattr(err, "code", None) == _STALE_TOOL_RESULT_CODE


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
    logic the old /api/reservations/* routes wrapped (app/reservations.py,
    app/payments.py), called directly instead of over HTTP. Required
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


async def _execute_tool(name: str, arguments: str, session: GuideSession) -> str:
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


@dataclass
class _TurnOutcome:
    """Side-channel for what a streamed turn produced beyond text deltas --
    a generator can only `yield` one thing (text), so function_calls collected
    mid-stream are written here instead."""

    function_calls: list[tuple[str, str, str]] = field(default_factory=list)  # (call_id, name, arguments)


def _collect_function_calls(output: Any, outcome: "_TurnOutcome") -> None:
    """Backstop scan of a response's full `output` list for function_call
    items -- covers a GuideAnts build that surfaces a tool call only in
    response.completed rather than as discrete streamed output_item events."""
    seen = {call_id for call_id, _, _ in outcome.function_calls}
    for item in output or []:
        if getattr(item, "type", None) == "function_call" and item.call_id not in seen:
            outcome.function_calls.append((item.call_id, item.name, item.arguments or "{}"))
            seen.add(item.call_id)


async def _tool_outputs(outcome: "_TurnOutcome", session: GuideSession) -> list[dict[str, str]]:
    calls = outcome.function_calls
    if (
        config.FAST_TOOLS_ENABLED
        and len(calls) > 1
        and all(name in _READ_ONLY_TOOLS for _, name, _ in calls)
    ):
        results = await asyncio.gather(*(_execute_tool(n, a, session) for _, n, a in calls))
    else:
        results = [await _execute_tool(n, a, session) for _, n, a in calls]
    return [
        {"type": "function_call_output", "call_id": call_id, "output": output}
        for (call_id, _, _), output in zip(calls, results)
    ]


# Safe to run concurrently within one round: no writes, no ordering needs.
_READ_ONLY_TOOLS = frozenset({"listCatalog", "checkAvailability", "listCustomers", "findReservations"})


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


# Leading whitespace/sentence punctuation trimmed off whatever immediately
# follows a phrase match -- the marker's own sentence-ending "." (or ":",
# extra spaces, ...) belongs to the marker, never to the caller's actual
# answer. Not phrase-dependent, so it's a single module-level pattern shared
# by `_SentinelGate._trim` and `_start_conversation`.
_LEAD_PUNCT_RE = re.compile(r"^[\s.,:;!?—-]+")


def _compile_sentinel_patterns(phrase: str) -> tuple["re.Pattern | None", "re.Pattern | None"]:
    """Build the core (gating) and loose (failsafe cleanup) patterns for
    `phrase`. Returns `(None, None)` for an empty phrase -- the signal
    `_SentinelGate` and `_strip_sentinel` use for "gating disabled, every
    delta streams live".

    The core pattern matches only the bare words, in order, separated by
    whitespace -- no trailing punctuation absorption here. GuideAnts can
    stream the marker's own sentence-ending punctuation as a *separate*
    delta from the phrase itself (observed live: "Declare victory" arrives
    whole, then ". " arrives in the next delta) -- a pattern that only
    absorbs trailing punctuation already present in the same accumulated
    match can't consume characters that haven't arrived yet. `_LEAD_PUNCT_RE`
    (via `_SentinelGate._trim`) handles that punctuation instead, as its own
    persistent step that survives a delta boundary."""
    if not phrase:
        return None, None
    words = phrase.split()
    core_body = r"\s+".join(re.escape(w) for w in words)
    core = re.compile(core_body, re.IGNORECASE)
    # Loose: tolerant of a near-miss the core pattern didn't catch (a
    # trailing "victory:" GuideAnts formatted oddly, extra punctuation
    # between words) -- used only to clean the failsafe text before it's
    # spoken, never for gating. Anchored to the start of the text; does not
    # catch a reworded phrase ("Declaring victory"), an accepted limit.
    loose_body = r"\W+".join(rf"{re.escape(w)}\w*" for w in words)
    loose = re.compile(rf"^\W*{loose_body}\W*", re.IGNORECASE)
    return core, loose


_SENTINEL_STRICT, _SENTINEL_LOOSE = _compile_sentinel_patterns(config.FINAL_ANSWER_SENTINEL)


def _strip_sentinel(text: str) -> str:
    """Best-effort cleanup for the failsafe path (see `_SentinelGate`): if
    the sentinel phrase is present in `text` but `_SENTINEL_STRICT` never
    matched it while streaming, strip it here so it's never spoken as part
    of the failsafe burst. A no-op when gating is disabled."""
    if _SENTINEL_LOOSE is None:
        return text
    return _SENTINEL_LOOSE.sub("", text, count=1)


class _SentinelGate:
    """Per-round gate: withholds a round's text until
    `config.FINAL_ANSWER_SENTINEL` has been seen in the stream, then passes
    every later delta straight through unchanged. Nothing is ever held back
    once the gate is fully open -- `feed()` is synchronous and does no
    buffering of its own once `self._state == "open"`, so the caller can
    yield its return value inside the same `async for` iteration that
    received the delta. This is the difference from `main`'s whole-round
    buffering and from `feature/live-token-streaming`'s STREAM_COMMIT_CHARS
    threshold: neither of those ever defers a decision past a fixed point,
    this one defers nothing at all once the phrase is seen.

    Three internal states, `"closed"` -> `"trimming"` -> `"open"`:
    - `"closed"`: searching `retained` for the phrase. No output.
    - `"trimming"`: the phrase itself has been found; now stripping the
      leading run of whitespace/sentence punctuation that belongs to the
      marker's own sentence end (`_LEAD_PUNCT_RE`), one delta at a time if
      necessary -- this is what makes trimming survive a delta boundary
      (GuideAnts can stream "Declare victory" and its trailing ". "
      separately; a one-shot strip against a single delta would miss that).
      No output while there's nothing left after trimming.
    - `"open"`: real content has started. Pure pass-through from here.

    `open` (the public property) is `True` for `"trimming"` or `"open"` --
    both mean the phrase has been found, which is what the round-end
    failsafe/mis-bet logic in `_stream_reply_with_tools` actually cares
    about, not whether trimming has finished.

    `retained` accumulates only the pre-match text, purely so the caller can
    fall back to speaking it (via `_strip_sentinel`) if the round ends still
    `"closed"` -- the failsafe for a turn where the guide forgot the phrase.

    `emitted_any` is distinct from `open`: with gating disabled
    (`config.FINAL_ANSWER_SENTINEL` empty) the gate starts fully open, but a
    round that produced zero text should still not be reported as "already
    spoken" by the caller's round-end logging -- `emitted_any` tracks
    whether `feed` actually returned non-empty text at least once."""

    def __init__(self) -> None:
        self._state = "open" if _SENTINEL_STRICT is None else "closed"
        self.retained = ""
        self.emitted_any = False

    @property
    def open(self) -> bool:
        return self._state != "closed"

    def feed(self, delta: str) -> str:
        if self._state == "open":
            if delta:
                self.emitted_any = True
            return delta
        if self._state == "closed":
            self.retained += delta
            match = _SENTINEL_STRICT.search(self.retained)
            if not match:
                return ""
            self._state = "trimming"
            return self._trim(self.retained[match.end():])
        return self._trim(delta)  # self._state == "trimming"

    def _trim(self, text: str) -> str:
        remainder = _LEAD_PUNCT_RE.sub("", text, count=1)
        if not remainder:
            return ""  # still trimming -- nothing but punctuation/whitespace so far
        self._state = "open"
        self.emitted_any = True
        return remainder


async def _start_conversation(
    client: AsyncOpenAI, input_text: str, session: GuideSession
) -> AsyncIterator[ReplyEvent]:
    """Non-streaming fallback for establishing a conversation id against an
    older GuideAnts build whose streamed events don't carry one yet. Also
    tool-aware, so a turn that needs this fallback can still call tools.
    Applies the same sentinel-phrase rule as `_stream_reply_with_tools` to a
    round's whole text at once, since there's nothing to gate mid-flight on
    a single blocking call -- see that function's docstring for why a round
    ahead of a tool call must never reach Twilio unless it cleared the
    phrase."""
    next_input: Any = input_text
    for i in range(_MAX_TOOL_ITERATIONS):
        kwargs: dict[str, Any] = {"model": config.GUIDEANTS_MODEL, "input": next_input}
        if session.conversation_id is not None:
            kwargs["conversation"] = session.conversation_id
        # Same non-idempotence guard as _stream_turn: never retry a tool-output
        # submission (next_input is a list of function_call_output items).
        call_client = client.with_options(max_retries=0) if isinstance(next_input, list) else client
        response = await call_client.responses.create(**kwargs)
        if session.conversation_id is None:
            session.conversation_id = _extract_conversation_id(response)
            if session.conversation_id is None:
                logger.warning(
                    "GuideAnts response %s carried no conversation id even on the "
                    "non-streaming path",
                    getattr(response, "id", "?"),
                )
        outcome = _TurnOutcome()
        _collect_function_calls(getattr(response, "output", None), outcome)
        text = response.output_text or ""

        if _SENTINEL_STRICT is None:
            matched, spoken = True, text
        else:
            m = _SENTINEL_STRICT.search(text)
            # _LEAD_PUNCT_RE strips the marker's own trailing "." / ":" /
            # extra spaces from the remainder -- see _SentinelGate's
            # docstring for why the phrase pattern itself no longer absorbs
            # this (it only matters here for a single already-complete
            # `text` blob, but the same cleanup is needed for the same
            # reason: that punctuation belongs to the marker, not the
            # caller's actual answer).
            matched = bool(m)
            spoken = _LEAD_PUNCT_RE.sub("", text[m.end():], count=1) if m else ""

        if not outcome.function_calls:  # final round
            if not matched:
                spoken = _strip_sentinel(text)
                logger.warning(
                    "No trigger phrase this turn (non-streaming path); speaking "
                    "the round unstreamed (failsafe)"
                )
            if spoken:
                yield Delta(spoken)
            return

        if i == _MAX_TOOL_ITERATIONS - 1:
            logger.warning(
                "Non-streaming tool loop hit its %d-iteration bound; speaking whatever "
                "text this round produced instead of ending the turn in silence",
                _MAX_TOOL_ITERATIONS,
            )
            if not matched:
                spoken = _strip_sentinel(text)
            if spoken:
                yield Delta(spoken)
            return

        if spoken:
            if matched:
                logger.warning(
                    "Trigger phrase appeared in a round that then called %s (non-streaming "
                    "path) -- already-yielded text will be cut off",
                    ", ".join(name for _, name, _ in outcome.function_calls),
                )
            yield Delta(spoken)
        elif text:
            logger.info(
                "Discarding pre-trigger narration ahead of a tool call (non-streaming path): %r",
                text,
            )
        yield ToolCallStarted(tuple(name for _, name, _ in outcome.function_calls))
        next_input = await _tool_outputs(outcome, session)


async def _stream_turn(
    client: AsyncOpenAI,
    input_value: Any,
    session: GuideSession,
    outcome: "_TurnOutcome",
) -> AsyncIterator[str]:
    """Stream one turn's reply, capturing the conversation id from
    `response.created`/`response.completed` if the session doesn't have one
    yet, and any function_call items into `outcome` (see `_TurnOutcome`).
    `input_value` is a caller utterance (str) on a fresh turn, or a list of
    function_call_output items when resuming after a tool call. Only text
    deltas are ever yielded -- tool calls are handled entirely via `outcome`.
    Raises openai.BadRequestError on GuideAnts 4xx responses (including a
    lost-conversation error); callers handle retry/fallback."""
    had_conversation_id = session.conversation_id is not None
    kwargs: dict[str, Any] = {
        "model": config.GUIDEANTS_MODEL,
        "input": input_value,
        "stream": True,
    }
    if had_conversation_id:
        kwargs["conversation"] = session.conversation_id

    # A tool-output submission (input is a list of function_call_output items)
    # is not idempotent: if it reaches GuideAnts and the connection then blips,
    # the SDK's automatic retry re-POSTs the same call_id -- but the first
    # attempt has already advanced or (on a mid-stream disconnect) cancelled the
    # turn, so the retry hits tool_results_not_pending. Disable retries for
    # exactly those calls; a fresh turn's request stays retryable.
    call_client = client.with_options(max_retries=0) if isinstance(input_value, list) else client
    stream = await call_client.responses.create(**kwargs)

    completed = False
    async with stream:
        async for event in stream:
            etype = getattr(event, "type", "")
            if etype == "response.output_text.delta":
                delta = getattr(event, "delta", None)
                if delta:
                    yield delta
            elif etype == "response.output_item.done":
                _collect_function_calls([getattr(event, "item", None)], outcome)
            elif etype in ("response.created", "response.completed"):
                resp = getattr(event, "response", None)
                if etype == "response.completed":
                    completed = True
                    _collect_function_calls(getattr(resp, "output", None), outcome)
                if session.conversation_id is None:
                    session.conversation_id = _extract_conversation_id(resp)
            elif etype in ("response.failed", "error"):
                raise RuntimeError(f"GuideAnts stream reported failure: {event!r}")
            # response.output_item.added / response.content_part.added /
            # response.output_text.done / response.function_call_arguments.*:
            # structural events, nothing to forward.

    if not had_conversation_id and completed and session.conversation_id is None:
        session.stream_missing_conversation = True
        logger.warning(
            "GuideAnts stream completed without a conversation id -- possibly "
            "an older GuideAnts build; falling back to a non-streaming call "
            "next turn to obtain one"
        )


async def _stream_reply_with_tools(
    client: AsyncOpenAI, user_text: str, session: GuideSession
) -> AsyncIterator[ReplyEvent]:
    """Drive one caller turn to completion, running any client-side tool
    calls (declared on the guide in GuideAnts -- see
    guide-demo/caller-phone-client-tool.json, and _execute_tool for how this
    app answers them) in between. Each iteration is its own `_stream_turn`
    call, individually wrapped in `aclosing` so a `.aclose()` on this
    generator (barge-in) cascades down to whichever streamed request is
    currently live -- see `stream_reply`'s docstring for why that matters.
    Bounded by _MAX_TOOL_ITERATIONS so a guide that never stops calling tools
    can't hang a turn forever.

    A round's deltas pass through a `_SentinelGate`: withheld until
    `config.FINAL_ANSWER_SENTINEL` (the guide is instructed -- see
    guide-demo/template/instructions.template.md's "FINAL ANSWER MARKER"
    paragraph -- to speak it once, at the very start of its actual final
    answer) has been seen in that round's stream, then forwarded live from
    that point on with no further delay. This is not just a latency
    tradeoff -- it's required for correct playback on a real call. GuideAnts
    sometimes narrates ahead of a tool call (e.g. "let me check the helmet
    too"), or leaks the model's raw reasoning as plain content (see
    docs/THINKING_LEAK_FIXES.md) -- but Twilio Conversation Relay's
    `preemptible` flag (every frame this app sends carries it) means ANY
    later frame cuts off whatever's still playing, even a later frame from
    this same reply after the real silence a tool call takes. So text ahead
    of the phrase must never reach Twilio as a frame at all, or the caller
    hears it start and then gets cut off mid-word once the tool finishes and
    the real answer's frames arrive. Unlike buffering a whole round (`main`)
    or a fixed character threshold (`feature/live-token-streaming`), this
    isn't a bet against length -- the marker says definitively whether a
    round is the final answer, so a short final answer streams immediately
    after the phrase instead of waiting to accumulate enough characters to
    look final, and a long narration round is never mistaken for one.

    Failsafe: if a round that turns out to be final never produced the
    phrase (the guide forgot it), the round's whole retained text is spoken
    as one un-gated burst -- exactly `main`'s behavior, the one case with no
    streaming. If an *intermediate* round's phrase opened the gate and it
    still went on to call a tool, whatever was already streamed is spoken
    and then cut off same as the buffering branches' worst case; this is
    logged as a warning since it means the guide said the marker too early."""
    next_input: Any = user_text
    spoken_so_far = ""
    # Set once a round has already spoken a goodbye and then called endCall:
    # the follow-up round (the guide answering the endCall result) is
    # consumed but not spoken, so the caller never hears the goodbye twice.
    mute = False
    for i in range(_MAX_TOOL_ITERATIONS):
        outcome = _TurnOutcome()
        gate = _SentinelGate()
        if i == 0:
            session.prev_round_text = session.round_text
            session.turn_user_text = user_text if isinstance(user_text, str) else ""
            session.round_text = ""
        async with contextlib.aclosing(_stream_turn(client, next_input, session, outcome)) as gen:
            async for delta in gen:
                session.round_text += delta
                if (text := gate.feed(delta)) and not mute:
                    spoken_so_far += text
                    yield Delta(text)
        if mute and not gate.open and gate.retained:
            logger.info("Goodbye already spoken before endCall; not repeating it: %r", gate.retained)

        if not outcome.function_calls:  # final round
            if mute:
                return
            if not gate.open:  # FAILSAFE: phrase never arrived this turn
                if text := _strip_sentinel(gate.retained):
                    yield Delta(text)
                logger.warning(
                    "No trigger phrase this turn; speaking the round unstreamed (failsafe)"
                )
            return

        names = [name for _, name, _ in outcome.function_calls]
        if (
            gate.emitted_any
            and names
            and all(n == "endCall" for n in names)
            and call_end.reply_is_goodbye(spoken_so_far)
        ):
            logger.info("Goodbye spoken in the same round as endCall; the follow-up round stays silent")
            mute = True
            yield ToolCallStarted(tuple(names))
            next_input = await _tool_outputs(outcome, session)
            continue
        if (
            gate.emitted_any
            and names
            and all(n == "sendPaymentLink" for n in names)
            and "?" in spoken_so_far
        ):
            # The guide asked "shall I text you…?" and called sendPaymentLink
            # in the same round. The send guard refuses it (NOT SENT); the
            # follow-up round stays silent so the question isn't asked twice
            # and the caller's answer isn't talked over (22:14 call).
            logger.info("Text offer asked in the same round as sendPaymentLink; waiting for the answer")
            mute = True  # no ToolCallStarted either: no "One moment." filler after the question
            next_input = await _tool_outputs(outcome, session)
            continue

        if i == _MAX_TOOL_ITERATIONS - 1:
            logger.warning(
                "Tool-call loop hit its %d-iteration bound; speaking whatever text this "
                "round produced instead of ending the turn in silence",
                _MAX_TOOL_ITERATIONS,
            )
            if not gate.open:
                if text := _strip_sentinel(gate.retained):
                    yield Delta(text)
            return

        if gate.emitted_any:
            logger.warning(
                "Trigger phrase appeared in a round that then called %s -- "
                "already-spoken text will be cut off",
                ", ".join(name for _, name, _ in outcome.function_calls),
            )
        elif gate.retained:
            logger.info(
                "Discarding pre-trigger narration ahead of a tool call: %r", gate.retained
            )
        yield ToolCallStarted(tuple(name for _, name, _ in outcome.function_calls))
        next_input = await _tool_outputs(outcome, session)


async def stream_reply(
    user_text: str, session: GuideSession, *, _is_retry: bool = False
) -> AsyncIterator[ReplyEvent]:
    """Yield events for the guide's reply to a single caller utterance: text
    to speak (`Delta`) and, when a client-side tool call is about to run
    (declared on the guide in GuideAnts, see
    guide-demo/caller-phone-client-tool.json, resolved internally by
    `_stream_reply_with_tools`), a `ToolCallStarted` marker so the caller can
    be protected from a false barge-in during the gap before the next
    `Delta`.

    `user_text` should already include any interruption note (see
    build_input); this function only handles GuideAnts continuation, not
    prompt shaping.

    A lost conversation or stale tool result is retried on a fresh
    conversation at most once per turn (`_is_retry` marks that retry): if
    GuideAnts rejects the retry the same way, the error propagates rather
    than opening fresh conversations forever.
    """
    client = _get_client()
    if not _is_retry:
        user_text = await _with_known_caller_note(user_text, session)

    if session.conversation_id is None and session.stream_missing_conversation:
        async for event in _start_conversation(client, user_text, session):
            yield event
        return

    # `_stream_reply_with_tools` nests one or more `_stream_turn` calls, each
    # holding the actual SSE connection open (via its own `async with
    # stream:`). `async for ... yield` does not delegate cancellation the way
    # sync `yield from` does, so if this generator is closed mid-turn
    # (barge-in), nothing would otherwise close the inner one(s) -- wrap it in
    # `aclosing` so `.aclose()` here deterministically closes whichever
    # underlying stream is live too.
    lost_conversation = False
    emitted_any = False
    async with contextlib.aclosing(_stream_reply_with_tools(client, user_text, session)) as gen:
        try:
            async for event in gen:
                if isinstance(event, Delta):
                    emitted_any = True
                yield event
            return
        except openai.BadRequestError as err:
            if session.conversation_id is None:
                raise
            if _is_lost_conversation(err):
                logger.warning(
                    "GuideAnts no longer recognizes conversation %s (%s)",
                    session.conversation_id,
                    getattr(err, "code", None),
                )
            elif _is_stale_tool_result(err):
                # The turn carrying the tool call is no longer resumable (it was
                # completed or cancelled server-side, typically by a mid-stream
                # disconnect). Recover like a lost conversation. NOTE: any tool
                # side effect this app already ran (e.g. a Booqable reservation)
                # has happened; re-asking on a fresh conversation could prompt
                # the guide to repeat it -- acceptable for now over crashing the
                # turn, but worth revisiting if a tool becomes costly to repeat.
                logger.warning(
                    "GuideAnts rejected a tool result for conversation %s as no "
                    "longer pending (%s); the turn was cancelled/completed "
                    "server-side",
                    session.conversation_id,
                    getattr(err, "code", None),
                )
            else:
                raise
            # Still clear the id so the *next* caller turn recovers on a
            # fresh conversation, even when this turn can't retry below.
            session.conversation_id = None
            if emitted_any:
                logger.warning(
                    "Conversation was lost after this turn had already spoken text; "
                    "not retrying, since a retry would re-speak it"
                )
                raise
            if _is_retry:
                logger.warning(
                    "Fresh conversation was rejected the same way; not retrying again"
                )
                raise
            logger.warning("Starting a fresh conversation for this call -- prior context is lost")
            lost_conversation = True

    if lost_conversation:
        async with contextlib.aclosing(stream_reply(user_text, session, _is_retry=True)) as retry_gen:
            async for event in retry_gen:
                yield event


async def classify_conversation(session: GuideSession) -> dict[str, Any]:
    """Ask the guide to classify the just-ended call as structured JSON, for
    app/call_recording.py to persist. Raises ValueError on any failure
    (missing conversation, network/API error, non-JSON or invalid reply) --
    callers must supply their own safe defaults; see the design spec's
    section 3."""
    if not session.conversation_id:
        raise ValueError("no conversation id to classify")

    client = _get_client()
    try:
        response = await client.responses.create(
            conversation=session.conversation_id, input=_CLASSIFICATION_PROMPT, stream=False
        )
    except Exception as exc:  # noqa: BLE001 -- any transport/API failure is equally "couldn't classify"
        raise ValueError(f"classification request failed: {exc}") from exc

    text = getattr(response, "output_text", None)
    if not text:
        raise ValueError("empty classification response")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"non-JSON classification response: {text!r}") from exc

    if data.get("outcome") not in _VALID_OUTCOMES:
        raise ValueError(f"invalid outcome: {data.get('outcome')!r}")
    if not isinstance(data.get("escalated"), bool):
        raise ValueError(f"invalid escalated flag: {data.get('escalated')!r}")
    return data
