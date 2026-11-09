"""End-of-call classification: asks the guide to summarize the just-ended
call as structured JSON, for app/calls/call_recording.py to persist."""

import json
from typing import Any

from . import connection
from .session import GuideSession

_VALID_OUTCOMES = {"completed", "escalated", "abandoned", "failed", "follow_up_required"}

_CLASSIFICATION_PROMPT = (
    "The call has ended. Reply with ONLY a JSON object, no other text, with "
    'these exact keys: "intent" (a short business-language description of '
    'what the caller wanted, e.g. "Book a rental"), "outcome" (one of: '
    "completed, escalated, abandoned, failed, follow_up_required), "
    '"escalated" (true or false), and "summary" (one or two sentences in '
    "business language, no internal jargon)."
)


async def classify_conversation(session: GuideSession) -> dict[str, Any]:
    """Ask the guide to classify the just-ended call as structured JSON, for
    app/calls/call_recording.py to persist. Raises ValueError on any failure
    (missing conversation, network/API error, non-JSON or invalid reply) --
    callers must supply their own safe defaults; see the design spec's
    section 3."""
    if not session.conversation_id:
        raise ValueError("no conversation id to classify")

    client = connection.get_client()
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
