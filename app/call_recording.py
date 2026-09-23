"""Persists a finished call as a Conversation record: transcript, tool
actions, and a GuideAnts wrap-up classification. Called once, from the
/ws handler's disconnect teardown in app/main.py -- see that module's
docstring for why the call site wraps this in its own try/except (a
persistence failure must never crash call teardown; the caller has already
hung up).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from . import conversation_store, guide_client
from .booqable_client import BooqableClient
from .db import session_scope

if TYPE_CHECKING:
    from .main import CallState

logger = logging.getLogger("voice_receptionist.call_recording")

_DEFAULT_CLASSIFICATION: dict[str, Any] = {
    "intent": None,
    "outcome": "completed",
    "escalated": False,
    "summary": None,
}

_ROLE_TO_SPEAKER = {"assistant": "concierge", "user": "customer"}


def _spread_timestamps(started_at: datetime, ended_at: datetime, count: int) -> list[datetime]:
    """st.messages carries no timing of its own (see app/main.py's
    CallState.messages) -- messages are spread evenly across the call's
    actual duration instead. List order (already chronological) stays
    exact; the individual instants are an approximation."""
    if count <= 1:
        return [started_at] * count
    span = ended_at - started_at
    return [started_at + span * (i / (count - 1)) for i in range(count)]


def _customer_name(session: guide_client.GuideSession) -> str | None:
    if not session.known_customer:
        return None
    return BooqableClient.attrs(session.known_customer).get("name")


async def record_call(st: "CallState") -> None:
    # A session that authenticated (setup arrived) but had no dialogue and
    # triggered no tool action isn't a call worth recording -- it's a bare
    # connect/disconnect (a probe, a hang-up before speaking, a retry).
    # Recording these unconditionally is what let hundreds of empty rows
    # accumulate in the conversations table with no real content behind
    # them. Messages alone aren't the full signal: get_caller_phone_number
    # and the reservation tools populate guide.actions without ever
    # appending to st.messages, so a real call can legitimately have empty
    # messages as long as it did something.
    if not st.messages and not st.guide.actions:
        return

    ended_at = datetime.utcnow()
    started_at = st.started_at

    try:
        classification = await guide_client.classify_conversation(st.guide)
    except Exception:  # noqa: BLE001 -- any failure (bad conversation id, network error,
        # invalid JSON) just means "can't classify"; fall back to safe defaults instead.
        logger.warning("Wrap-up classification failed; saving with defaults", exc_info=True)
        classification = dict(_DEFAULT_CLASSIFICATION)

    timestamps = _spread_timestamps(started_at, ended_at, len(st.messages))
    messages = [
        {
            "speaker": _ROLE_TO_SPEAKER.get(message["role"], message["role"]),
            "text": message["content"],
            "at": at,
        }
        for message, at in zip(st.messages, timestamps)
    ]

    with session_scope() as db:
        conversation_store.create_conversation(
            db,
            customer_name=_customer_name(st.guide),
            customer_phone=st.guide.caller_phone,
            started_at=started_at,
            ended_at=ended_at,
            intent=classification.get("intent"),
            outcome=classification.get("outcome", "completed"),
            escalated=bool(classification.get("escalated", False)),
            summary=classification.get("summary"),
            messages=messages,
            actions=st.guide.actions,
        )
