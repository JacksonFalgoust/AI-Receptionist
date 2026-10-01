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
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import openai
from openai import AsyncOpenAI

from app import config

from . import connection, sentinel, tools
from .session import GuideSession

logger = logging.getLogger("voice_receptionist.guide")

# Ceiling on responses.create calls within a single caller turn (one call, plus
# one more per round of tool calls) -- guards against a guide that keeps
# calling tools without ever producing a text answer.
_MAX_TOOL_ITERATIONS = 5


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
        output = await tools.execute_tool(name, arguments, session)
        outputs.append({"type": "function_call_output", "call_id": call_id, "output": output})
    return outputs


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
            session.conversation_id = connection.extract_conversation_id(response)
            if session.conversation_id is None:
                logger.warning(
                    "GuideAnts response %s carried no conversation id even on the "
                    "non-streaming path",
                    getattr(response, "id", "?"),
                )
        outcome = _TurnOutcome()
        _collect_function_calls(getattr(response, "output", None), outcome)
        text = response.output_text or ""

        if sentinel.SENTINEL_STRICT is None:
            matched, spoken = True, text
        else:
            m = sentinel.SENTINEL_STRICT.search(text)
            # _LEAD_PUNCT_RE strips the marker's own trailing "." / ":" /
            # extra spaces from the remainder -- see _SentinelGate's
            # docstring for why the phrase pattern itself no longer absorbs
            # this (it only matters here for a single already-complete
            # `text` blob, but the same cleanup is needed for the same
            # reason: that punctuation belongs to the marker, not the
            # caller's actual answer).
            matched = bool(m)
            spoken = sentinel.LEAD_PUNCT_RE.sub("", text[m.end():], count=1) if m else ""

        if not outcome.function_calls:  # final round
            if not matched:
                spoken = sentinel.strip_sentinel(text)
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
                spoken = sentinel.strip_sentinel(text)
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
                    session.conversation_id = connection.extract_conversation_id(resp)
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
    for i in range(_MAX_TOOL_ITERATIONS):
        outcome = _TurnOutcome()
        gate = sentinel.SentinelGate()
        async with contextlib.aclosing(_stream_turn(client, next_input, session, outcome)) as gen:
            async for delta in gen:
                if text := gate.feed(delta):
                    yield Delta(text)

        if not outcome.function_calls:  # final round
            if not gate.open:  # FAILSAFE: phrase never arrived this turn
                if text := sentinel.strip_sentinel(gate.retained):
                    yield Delta(text)
                logger.warning(
                    "No trigger phrase this turn; speaking the round unstreamed (failsafe)"
                )
            return

        if i == _MAX_TOOL_ITERATIONS - 1:
            logger.warning(
                "Tool-call loop hit its %d-iteration bound; speaking whatever text this "
                "round produced instead of ending the turn in silence",
                _MAX_TOOL_ITERATIONS,
            )
            if not gate.open:
                if text := sentinel.strip_sentinel(gate.retained):
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
    client = connection.get_client()

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
            if connection.is_lost_conversation(err):
                logger.warning(
                    "GuideAnts no longer recognizes conversation %s (%s)",
                    session.conversation_id,
                    getattr(err, "code", None),
                )
            elif connection.is_stale_tool_result(err):
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
