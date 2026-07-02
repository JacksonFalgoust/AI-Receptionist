"""Heuristics for selective barge-in.

Decides whether a caller's utterance during a barge-in should stop the
assistant's reply (a stop command or a question) or let it resume (a filler,
backchannel, or noise). Also computes the spoken/unspoken split of a talk
cycle from Twilio's ``utteranceUntilInterrupt`` so a resumed reply can pick
up where playback actually left off.
"""

import re
import string
from typing import Iterable

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

# Stripped from the front before stop/question checks, so "okay so what
# time..." is evaluated as "what time...".
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


def is_stop_command(voice_prompt: str, extra_phrases: Iterable[str] = ()) -> bool:
    """True if the utterance is a command to stop talking."""
    words = _strip_leading_fillers(_normalize(voice_prompt).split())
    if not words:
        return False
    text = " ".join(words)
    phrases = STOP_PHRASES | frozenset(extra_phrases)
    return any(text == phrase or text.startswith(phrase + " ") for phrase in phrases)


def is_question(voice_prompt: str) -> bool:
    """True if the utterance looks like a question."""
    if voice_prompt.rstrip().endswith("?"):
        return True
    words = _strip_leading_fillers(_normalize(voice_prompt).split())
    if not words:
        return False
    return words[0] in QUESTION_STARTERS


def should_stop_reply(voice_prompt: str, extra_phrases: Iterable[str] = ()) -> bool:
    """True if the assistant's reply should be cancelled for this utterance."""
    return is_stop_command(voice_prompt, extra_phrases) or is_question(voice_prompt)


def split_spoken(full: str, heard: str) -> tuple:
    """Split ``full`` (all text handed to Twilio this talk cycle) into
    ``(spoken, remainder)`` given Twilio's ``utteranceUntilInterrupt``.

    Tries an exact prefix match first, then falls back to a tolerant,
    punctuation/case-insensitive alignment. If nothing lines up, replays the
    whole cycle (safe, if repetitive) rather than dropping text.
    """
    if not heard:
        return "", full
    if full.startswith(heard):
        return heard, full[len(heard) :]

    full_chars = [(i, c.lower()) for i, c in enumerate(full) if c.isalnum()]
    heard_chars = [c.lower() for c in heard if c.isalnum()]

    if not heard_chars:
        return "", full

    if len(heard_chars) >= len(full_chars):
        if [c for _, c in full_chars] == heard_chars[: len(full_chars)]:
            return full, ""
        return "", full

    if all(full_chars[k][1] == heard_chars[k] for k in range(len(heard_chars))):
        cut = full_chars[len(heard_chars) - 1][0] + 1
        return full[:cut], full[cut:]

    return "", full
