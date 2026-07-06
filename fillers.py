"""Heuristics for the "please wait" filler feature.

Decides whether a caller's utterance looks like a question or a request that
warrants a short filler phrase (e.g. "Let me look that up for you") before
streaming the guide's real reply. Replies are uninterruptible, so there is no
stop/resume classification here anymore. Also decides whether an utterance is
pure backchannel noise (e.g. "ok", "yeah") that shouldn't get a reply at all.
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
    {"um", "uh", "er", "ah", "okay", "ok", "so", "well", "hey", "yeah", "like", "oh"}
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


def pick(phrases: list[str]) -> str | None:
    """Return a random filler phrase, or None if there are none to pick from."""
    return random.choice(phrases) if phrases else None
