"""Heuristics for selective barge-in.

Decides whether a caller's utterance heard while a reply is already
streaming should cancel and restart it (a stop/wait command, or a new
question -- see `should_interrupt`) versus be ignored (backchannel,
statement, noise). Pure functions only, no I/O, no Twilio/GuideAnts
knowledge -- mirrors the role fillers.py plays for the filler-phrase
feature. Used by app.py's `prompt` handler.
"""

import re
import string
from typing import Iterable

from . import fillers

STOP_PHRASES = frozenset(
    {
        "stop",
        "wait",
        "hold on",
        "hang on",
        "hold up",
        "one moment",
        "one second",
        "just a second",
        "just a moment",
        "pause",
        "shut up",
        "be quiet",
        "quiet",
        "enough",
        "that's enough",
        "never mind",
        "nevermind",
        "excuse me",
        "no",
        "no no",
        "stop talking",
        "listen",
    }
)

# Stripped from the front before the stop-phrase check, so "okay stop" is
# evaluated as "stop".
LEADING_FILLERS = frozenset(
    {"um", "uh", "er", "ah", "okay", "ok", "so", "well", "hey", "yeah", "like", "oh"}
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


def is_stop_command(text: str, extra_phrases: Iterable[str] = ()) -> bool:
    """True if the utterance is a command to stop/pause talking."""
    words = _strip_leading_fillers(_normalize(text).split())
    if not words:
        return False
    normalized = " ".join(words)
    phrases = STOP_PHRASES | frozenset(extra_phrases)
    return any(
        normalized == phrase or normalized.startswith(phrase + " ") for phrase in phrases
    )


def should_interrupt(text: str, extra_phrases: Iterable[str] = ()) -> bool:
    """True if this utterance, heard mid-reply, should cancel and restart it."""
    return is_stop_command(text, extra_phrases) or fillers.looks_like_question(text)
