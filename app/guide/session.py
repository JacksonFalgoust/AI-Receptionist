"""Per-call GuideAnts session state, and the shaping of a caller turn's
input text."""

from dataclasses import dataclass, field

# How much of an interrupted reply to quote back to the guide. Long enough to
# give real context, short enough not to balloon the prompt.
_INTERRUPTED_TAIL_CHARS = 150


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
