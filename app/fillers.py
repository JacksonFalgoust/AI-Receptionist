"""Heuristics for the "please wait" filler feature.

Decides whether a caller's utterance looks like a question or a request that
warrants a short filler phrase (e.g. "Let me look that up for you") before
streaming the guide's real reply. The question detection is also used by
barge_in.should_interrupt() to help decide whether a caller's utterance heard
mid-reply should cancel and restart the in-flight reply. Also decides whether
an utterance is pure backchannel noise (e.g. "ok", "yeah") that shouldn't get
a reply at all.
"""

import random
import re
import string
from typing import Iterable

QUESTION_STARTERS = frozenset(
    {
        "what",
        "who",
        "whom",
        "whose",
        "where",
        "when",
        "why",
        "how",
        "which",
        "can",
        "could",
        "would",
        "will",
        "should",
        "shall",
        "may",
        "might",
        "do",
        "does",
        "did",
        "is",
        "are",
        "was",
        "were",
        "am",
        "have",
        "has",
        "had",
        "don't",
        "doesn't",
        "didn't",
        "isn't",
        "aren't",
        "won't",
        "wouldn't",
        "couldn't",
        "shouldn't",
    }
)

REQUEST_STARTERS = frozenset(
    {
        "tell",
        "give",
        "find",
        "get",
        "show",
        "help",
    }
)

# Checked against the front of the normalized text, in addition to the
# single-leading-word REQUEST_STARTERS check. Written post-normalization
# (apostrophes stripped, e.g. "i'd" -> "id") since _normalize runs first.
REQUEST_LEAD_PHRASES = (
    "i need",
    "i want",
    "id like",
    "looking for",
)

# Stripped from the front before starter checks, so "okay so what time..." is
# evaluated as "what time...".
LEADING_FILLERS = frozenset(
    {"um", "uh", "er", "ah", "okay", "ok", "so", "well", "hey", "yeah", "like", "oh", "alright"}
)

# Whole-utterance acknowledgments/backchannel: no request content of their
# own, so they never warrant a guide reply -- whether heard while the
# assistant is mid-reply or (due to STT lag) just after it finishes.
BACKCHANNEL_PHRASES = frozenset(
    {
        "ok",
        "okay",
        "yeah",
        "yep",
        "yup",
        "alright",
        "all right",
        "sure",
        "sure thing",
        "got it",
        "gotcha",
        "sounds good",
        "sounds great",
        "mmhmm",
        "mmhm",
        "uhhuh",
        "cool",
        "great",
        "right",
    }
)

_PUNCT_TABLE = str.maketrans("", "", string.punctuation)
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    text = text.lower().translate(_PUNCT_TABLE)
    return _WHITESPACE_RE.sub(" ", text).strip()


def _strip_leading_fillers(words: list) -> list:
    i = 0
    while i < len(words) and words[i] in LEADING_FILLERS:
        i += 1
    return words[i:]


def looks_like_question(text: str) -> bool:
    """True if the utterance looks like a question or a request/imperative
    that warrants a "let me check" filler before answering."""
    if text.rstrip().endswith("?"):
        return True
    words = _strip_leading_fillers(_normalize(text).split())
    if not words:
        return False
    if words[0] in QUESTION_STARTERS or words[0] in REQUEST_STARTERS:
        return True
    stripped = " ".join(words)
    return any(
        stripped == phrase or stripped.startswith(phrase + " ")
        for phrase in REQUEST_LEAD_PHRASES
    )


def is_backchannel(text: str, extra_phrases: Iterable[str] = ()) -> bool:
    """True if the utterance is pure acknowledgment/backchannel noise (e.g.
    "ok", "yeah", "mmhmm") with no request content of its own -- said mid- or
    right after the assistant's reply, not meant to start a new turn."""
    normalized = _normalize(text)
    if not normalized:
        return True
    return normalized in BACKCHANNEL_PHRASES or normalized in set(extra_phrases)


def pick(phrases: list[str], avoid: str | None = None) -> str | None:
    """Return a random filler phrase, or None if there are none to pick from.

    `avoid` (usually the last filler spoken this call) is skipped when any
    other phrase is available, so the same phrase never plays back to back.
    """
    if not phrases:
        return None
    choices = [p for p in phrases if p != avoid] or list(phrases)
    return random.choice(choices)


# Per-action filler pools: a booking or a text message shouldn't be covered
# by "let me look that up". Matched against client tool names (lowercased).
ACTION_FILLERS: dict[str, list[str]] = {
    "booking": [
        "One moment while I book that.",
        "Okay, booking that for you now.",
        "Just a moment while I get that booked.",
    ],
    "message": [
        "Sending that now.",
        "Okay, sending that over now.",
        "One moment while I send that.",
    ],
    "lookup": [
        "Let me check.",
        "One moment while I check.",
        "Let me take a quick look.",
    ],
}

# Tools that need no filler at all (hanging up, trivial local reads).
NO_FILLER_TOOLS = frozenset({"endcall", "end_call"})

# Prefix-based so read-only tools like getOrder / lookupCustomerByEmail stay
# in the "lookup" pool.
_BOOKING_PREFIXES = ("create", "book", "reserve", "cancel", "update", "modify", "reschedule")
_MESSAGE_PREFIXES = ("send", "sms", "text", "email")


def action_for_tools(names) -> str | None:
    """Classify the in-flight tool call(s) into a filler pool key, or None
    when every tool is filler-free. Messaging wins over booking, which wins
    over lookup, when a round mixes several tools."""
    lowered = [n.lower() for n in names or () if n]
    lowered = [n for n in lowered if n not in NO_FILLER_TOOLS]
    if not lowered and names:
        return None
    if any(n.startswith(_MESSAGE_PREFIXES) for n in lowered):
        return "message"
    if any(n.startswith(_BOOKING_PREFIXES) for n in lowered):
        return "booking"
    return "lookup"


def pick_for_tools(
    names, fallback: list[str], avoid: str | None = None, use_action_pools: bool = True
) -> str | None:
    """Filler phrase that fits the tool(s) in flight; `fallback` when no tool
    name is known yet, or when `use_action_pools` is off (a custom
    FILLER_PHRASES override is configured). Filler-free tools (endCall) get
    None either way. Never repeats `avoid` back to back."""
    if not names:
        return pick(fallback, avoid)
    action = action_for_tools(names)
    if action is None:
        return None
    return pick(ACTION_FILLERS[action] if use_action_pools else fallback, avoid)
