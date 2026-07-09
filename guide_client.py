"""Streams replies from a GuideAnts published guide via its OpenAI-compatible
wire API, using the /v1/responses endpoint with server-side conversation
continuation.

Turn 1 of a call is a single non-streaming responses.create() call: the
streaming path returns a random resp_ id and never echoes back the
conversation id, so the only way to obtain a durable continuation handle is a
non-streaming response body. Turn 2+ pass that handle back via the
`conversation` parameter and stream token deltas over SSE.

If GuideAnts no longer recognizes a conversation id (e.g. it restarted), the
next call automatically falls back to starting a fresh conversation --
earlier context for that call is lost, but the caller still gets an answer.
"""

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
    response = await client.responses.create(
        model=config.GUIDEANTS_MODEL,
        input=input_text,
    )
    session.conversation_id = _extract_conversation_id(response)
    if session.conversation_id is None:
        logger.warning(
            "GuideAnts response %s carried no conversation id; continuation will "
            "keep using the non-streaming path",
            getattr(response, "id", "?"),
        )
    text = response.output_text
    if text:
        yield text


async def stream_reply(user_text: str, session: GuideSession) -> AsyncIterator[str]:
    """Yield text deltas for the guide's reply to a single caller utterance.

    `user_text` should already include any interruption note (see
    build_input); this function only handles GuideAnts continuation, not
    prompt shaping.
    """
    client = _get_client()

    if session.conversation_id is None:
        async for delta in _start_conversation(client, user_text, session):
            yield delta
        return

    try:
        stream = await client.responses.create(
            model=config.GUIDEANTS_MODEL,
            input=user_text,
            conversation=session.conversation_id,
            stream=True,
        )
    except openai.BadRequestError as err:
        if not _is_lost_conversation(err):
            raise
        logger.warning(
            "GuideAnts no longer recognizes conversation %s (%s); starting a "
            "fresh conversation for this call -- prior context is lost",
            session.conversation_id,
            getattr(err, "code", None),
        )
        session.conversation_id = None
        async for delta in _start_conversation(client, user_text, session):
            yield delta
        return

    async with stream:
        async for event in stream:
            etype = getattr(event, "type", "")
            if etype == "response.output_text.delta":
                delta = getattr(event, "delta", None)
                if delta:
                    yield delta
            elif etype in ("response.failed", "error"):
                raise RuntimeError(f"GuideAnts stream reported failure: {event!r}")
            # response.created / response.output_item.added /
            # response.content_part.added / response.output_text.done /
            # response.output_item.done / response.completed: structural
            # events, nothing to forward.
