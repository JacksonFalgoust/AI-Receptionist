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
from dataclasses import dataclass
from typing import AsyncIterator

import openai
from openai import AsyncOpenAI

import config

logger = logging.getLogger("voice_receptionist.guide")

_client: AsyncOpenAI | None = None

# How much of an interrupted reply to quote back to the guide. Long enough to
# give real context, short enough not to balloon the prompt.
_INTERRUPTED_TAIL_CHARS = 150

_LOST_CONVERSATION_CODES = {"conversation_not_found", "invalid_conversation_id"}


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
    """Per-call continuation handle for one GuideAnts conversation."""

    conversation_id: str | None = None
    # Set when a streamed turn with no conversation id completed without one
    # -- signals an older GuideAnts build; the next such turn falls back to
    # a non-streaming call to obtain the id.
    stream_missing_conversation: bool = False


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


async def _start_conversation(client: AsyncOpenAI, input_text: str, session: GuideSession) -> AsyncIterator[str]:
    """Non-streaming fallback for establishing a conversation id against an
    older GuideAnts build whose streamed events don't carry one yet."""
    response = await client.responses.create(
        model=config.GUIDEANTS_MODEL,
        input=input_text,
    )
    session.conversation_id = _extract_conversation_id(response)
    if session.conversation_id is None:
        logger.warning(
            "GuideAnts response %s carried no conversation id even on the "
            "non-streaming path",
            getattr(response, "id", "?"),
        )
    text = response.output_text
    if text:
        yield text


async def _stream_turn(client: AsyncOpenAI, user_text: str, session: GuideSession) -> AsyncIterator[str]:
    """Stream one turn's reply, capturing the conversation id from
    `response.created`/`response.completed` if the session doesn't have one
    yet. Raises openai.BadRequestError on GuideAnts 4xx responses (including
    a lost-conversation error); callers handle retry/fallback."""
    had_conversation_id = session.conversation_id is not None
    kwargs = {"model": config.GUIDEANTS_MODEL, "input": user_text, "stream": True}
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
            elif etype in ("response.created", "response.completed"):
                if etype == "response.completed":
                    completed = True
                if session.conversation_id is None:
                    session.conversation_id = _extract_conversation_id(getattr(event, "response", None))
            elif etype in ("response.failed", "error"):
                raise RuntimeError(f"GuideAnts stream reported failure: {event!r}")
            # response.output_item.added / response.content_part.added /
            # response.output_text.done / response.output_item.done:
            # structural events, nothing to forward.

    if not had_conversation_id and completed and session.conversation_id is None:
        session.stream_missing_conversation = True
        logger.warning(
            "GuideAnts stream completed without a conversation id -- possibly "
            "an older GuideAnts build; falling back to a non-streaming call "
            "next turn to obtain one"
        )


async def stream_reply(user_text: str, session: GuideSession) -> AsyncIterator[str]:
    """Yield text deltas for the guide's reply to a single caller utterance.

    `user_text` should already include any interruption note (see
    build_input); this function only handles GuideAnts continuation, not
    prompt shaping.
    """
    client = _get_client()

    if session.conversation_id is None and session.stream_missing_conversation:
        async for delta in _start_conversation(client, user_text, session):
            yield delta
        return

    # `_stream_turn` is a nested async generator holding the actual SSE
    # connection open (via its own `async with stream:`). `async for ... yield`
    # does not delegate cancellation the way sync `yield from` does, so if
    # this generator is closed mid-turn (barge-in), nothing would otherwise
    # close the inner one -- wrap it in `aclosing` so `.aclose()` here
    # deterministically closes the underlying stream too.
    lost_conversation = False
    async with contextlib.aclosing(_stream_turn(client, user_text, session)) as gen:
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
