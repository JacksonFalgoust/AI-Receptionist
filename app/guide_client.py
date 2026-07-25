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

import contextlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import openai
from openai import AsyncOpenAI

from . import config, payments, reservations
from .booqable_client import BooqableClient, BooqableError
from .twilio_client import TwilioSmsClient, TwilioSmsError

logger = logging.getLogger("voice_receptionist.guide")

_client: AsyncOpenAI | None = None

# How much of an interrupted reply to quote back to the guide. Long enough to
# give real context, short enough not to balloon the prompt.
_INTERRUPTED_TAIL_CHARS = 150

_LOST_CONVERSATION_CODES = {"conversation_not_found", "invalid_conversation_id"}

# Ceiling on responses.create calls within a single caller turn (one call, plus
# one more per round of tool calls) -- guards against a guide that keeps
# calling tools without ever producing a text answer.
_MAX_TOOL_ITERATIONS = 5


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


async def _run_reservation_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Execute one Booqable-backed reservation tool -- the same business
    logic the old /api/reservations/* routes wrapped (app/reservations.py,
    app/payments.py), called directly instead of over HTTP. Required
    arguments missing from `args` raise KeyError, caught by the caller."""
    client = BooqableClient()
    if name == "listCatalog":
        return {"products": await reservations.list_catalog(client)}
    if name == "checkAvailability":
        location = await reservations.resolve_location(client, args.get("location_id"))
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
        if not args.get("customer_email") and not args.get("customer_phone"):
            raise BooqableError("customer_email or customer_phone is required")
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
        )
    if name == "findReservations":
        return await reservations.find_reservations(
            client, email=args.get("customer_email"), phone=args.get("customer_phone")
        )
    if name == "cancelReservation":
        return await reservations.cancel_reservation(client, args["order_id"])
    if name == "sendPaymentLink":
        twilio_client = TwilioSmsClient()
        return await payments.send_payment_link(
            client, twilio_client, order_id=args["order_id"], phone=args.get("phone")
        )
    raise KeyError(name)


async def _execute_tool(name: str, arguments: str, session: GuideSession) -> str:
    """Run one client-side tool call and return its result as the string to
    send back as a function_call_output. Never raises -- an error result is
    still a well-formed reply the model can react to."""
    if name == "get_caller_phone_number":
        return json.dumps({"phone_number": session.caller_phone})
    if name in _RESERVATION_TOOLS:
        try:
            args = json.loads(arguments) if arguments else {}
        except json.JSONDecodeError:
            logger.warning("Guide sent malformed arguments for %r: %r", name, arguments)
            return json.dumps({"error": "malformed arguments"})
        try:
            result = await _run_reservation_tool(name, args)
        except (BooqableError, TwilioSmsError) as exc:
            logger.warning("Reservation tool %r failed: %s", name, exc)
            return json.dumps({"error": str(exc)})
        except KeyError as exc:
            return json.dumps({"error": f"missing required argument: {exc}"})
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
    outputs = []
    for call_id, name, arguments in outcome.function_calls:
        output = await _execute_tool(name, arguments, session)
        outputs.append({"type": "function_call_output", "call_id": call_id, "output": output})
    return outputs


async def _next_tool_input(outcome: "_TurnOutcome", session: GuideSession) -> list[dict[str, str]] | None:
    """Given one turn's outcome, return the next request's `input` (the
    resolved tool outputs) if the turn ended in a function_call, or None if
    the turn already produced its final text answer -- shared by both the
    streaming and non-streaming tool loops below."""
    if not outcome.function_calls:
        return None
    return await _tool_outputs(outcome, session)


async def _start_conversation(client: AsyncOpenAI, input_text: str, session: GuideSession) -> AsyncIterator[str]:
    """Non-streaming fallback for establishing a conversation id against an
    older GuideAnts build whose streamed events don't carry one yet. Also
    tool-aware, so a turn that needs this fallback can still call tools."""
    next_input: Any = input_text
    for _ in range(_MAX_TOOL_ITERATIONS):
        kwargs: dict[str, Any] = {"model": config.GUIDEANTS_MODEL, "input": next_input}
        if session.conversation_id is not None:
            kwargs["conversation"] = session.conversation_id
        response = await client.responses.create(**kwargs)
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
        text = response.output_text
        if text:
            yield text
        next_input = await _next_tool_input(outcome, session)
        if next_input is None:
            return
    logger.warning("Non-streaming tool loop hit its %d-iteration bound; ending the turn", _MAX_TOOL_ITERATIONS)


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

    stream = await client.responses.create(**kwargs)

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
) -> AsyncIterator[str]:
    """Drive one caller turn to completion, running any client-side tool
    calls (declared on the guide in GuideAnts -- see
    guide-demo/caller-phone-client-tool.json, and _execute_tool for how this
    app answers them) in between. Each iteration is its own `_stream_turn`
    call, individually wrapped in `aclosing` so a `.aclose()` on this
    generator (barge-in) cascades down to whichever streamed request is
    currently live -- see `stream_reply`'s docstring for why that matters.
    Bounded by _MAX_TOOL_ITERATIONS so a guide that never stops calling tools
    can't hang a turn forever."""
    next_input: Any = user_text
    for _ in range(_MAX_TOOL_ITERATIONS):
        outcome = _TurnOutcome()
        async with contextlib.aclosing(_stream_turn(client, next_input, session, outcome)) as gen:
            async for delta in gen:
                yield delta
        next_input = await _next_tool_input(outcome, session)
        if next_input is None:
            return
    logger.warning("Tool-call loop hit its %d-iteration bound; ending the turn", _MAX_TOOL_ITERATIONS)


async def stream_reply(user_text: str, session: GuideSession) -> AsyncIterator[str]:
    """Yield text deltas for the guide's reply to a single caller utterance.

    `user_text` should already include any interruption note (see
    build_input); this function only handles GuideAnts continuation, not
    prompt shaping. Client-side tool calls (declared on the guide in
    GuideAnts, see guide-demo/caller-phone-client-tool.json) are resolved
    internally by `_stream_reply_with_tools` -- only assistant text is ever
    yielded here.
    """
    client = _get_client()

    if session.conversation_id is None and session.stream_missing_conversation:
        async for delta in _start_conversation(client, user_text, session):
            yield delta
        return

    # `_stream_reply_with_tools` nests one or more `_stream_turn` calls, each
    # holding the actual SSE connection open (via its own `async with
    # stream:`). `async for ... yield` does not delegate cancellation the way
    # sync `yield from` does, so if this generator is closed mid-turn
    # (barge-in), nothing would otherwise close the inner one(s) -- wrap it in
    # `aclosing` so `.aclose()` here deterministically closes whichever
    # underlying stream is live too.
    lost_conversation = False
    async with contextlib.aclosing(_stream_reply_with_tools(client, user_text, session)) as gen:
        try:
            async for delta in gen:
                yield delta
            return
        except openai.BadRequestError as err:
            if session.conversation_id is None or not _is_lost_conversation(err):
                raise
            logger.warning(
                "GuideAnts no longer recognizes conversation %s (%s); starting a "
                "fresh conversation for this call -- prior context is lost",
                session.conversation_id,
                getattr(err, "code", None),
            )
            session.conversation_id = None
            lost_conversation = True

    if lost_conversation:
        async with contextlib.aclosing(stream_reply(user_text, session)) as retry_gen:
            async for delta in retry_gen:
                yield delta
