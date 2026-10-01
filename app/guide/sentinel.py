"""The final-answer sentinel gate: withholds a round's streamed text until
the guide's trigger phrase (config.FINAL_ANSWER_SENTINEL) has been seen.
See SentinelGate's docstring."""

import re

from app import config


# Leading whitespace/sentence punctuation trimmed off whatever immediately
# follows a phrase match -- the marker's own sentence-ending "." (or ":",
# extra spaces, ...) belongs to the marker, never to the caller's actual
# answer. Not phrase-dependent, so it's a single module-level pattern shared
# by `_SentinelGate._trim` and `_start_conversation`.
LEAD_PUNCT_RE = re.compile(r"^[\s.,:;!?—-]+")


def _compile_sentinel_patterns(phrase: str) -> tuple["re.Pattern | None", "re.Pattern | None"]:
    """Build the core (gating) and loose (failsafe cleanup) patterns for
    `phrase`. Returns `(None, None)` for an empty phrase -- the signal
    `_SentinelGate` and `_strip_sentinel` use for "gating disabled, every
    delta streams live".

    The core pattern matches only the bare words, in order, separated by
    whitespace -- no trailing punctuation absorption here. GuideAnts can
    stream the marker's own sentence-ending punctuation as a *separate*
    delta from the phrase itself (observed live: "Declare victory" arrives
    whole, then ". " arrives in the next delta) -- a pattern that only
    absorbs trailing punctuation already present in the same accumulated
    match can't consume characters that haven't arrived yet. `_LEAD_PUNCT_RE`
    (via `_SentinelGate._trim`) handles that punctuation instead, as its own
    persistent step that survives a delta boundary."""
    if not phrase:
        return None, None
    words = phrase.split()
    core_body = r"\s+".join(re.escape(w) for w in words)
    core = re.compile(core_body, re.IGNORECASE)
    # Loose: tolerant of a near-miss the core pattern didn't catch (a
    # trailing "victory:" GuideAnts formatted oddly, extra punctuation
    # between words) -- used only to clean the failsafe text before it's
    # spoken, never for gating. Anchored to the start of the text; does not
    # catch a reworded phrase ("Declaring victory"), an accepted limit.
    loose_body = r"\W+".join(rf"{re.escape(w)}\w*" for w in words)
    loose = re.compile(rf"^\W*{loose_body}\W*", re.IGNORECASE)
    return core, loose


SENTINEL_STRICT, SENTINEL_LOOSE = _compile_sentinel_patterns(config.FINAL_ANSWER_SENTINEL)


def strip_sentinel(text: str) -> str:
    """Best-effort cleanup for the failsafe path (see `_SentinelGate`): if
    the sentinel phrase is present in `text` but `_SENTINEL_STRICT` never
    matched it while streaming, strip it here so it's never spoken as part
    of the failsafe burst. A no-op when gating is disabled."""
    if SENTINEL_LOOSE is None:
        return text
    return SENTINEL_LOOSE.sub("", text, count=1)


class SentinelGate:
    """Per-round gate: withholds a round's text until
    `config.FINAL_ANSWER_SENTINEL` has been seen in the stream, then passes
    every later delta straight through unchanged. Nothing is ever held back
    once the gate is fully open -- `feed()` is synchronous and does no
    buffering of its own once `self._state == "open"`, so the caller can
    yield its return value inside the same `async for` iteration that
    received the delta. This is the difference from `main`'s whole-round
    buffering and from `feature/live-token-streaming`'s STREAM_COMMIT_CHARS
    threshold: neither of those ever defers a decision past a fixed point,
    this one defers nothing at all once the phrase is seen.

    Three internal states, `"closed"` -> `"trimming"` -> `"open"`:
    - `"closed"`: searching `retained` for the phrase. No output.
    - `"trimming"`: the phrase itself has been found; now stripping the
      leading run of whitespace/sentence punctuation that belongs to the
      marker's own sentence end (`_LEAD_PUNCT_RE`), one delta at a time if
      necessary -- this is what makes trimming survive a delta boundary
      (GuideAnts can stream "Declare victory" and its trailing ". "
      separately; a one-shot strip against a single delta would miss that).
      No output while there's nothing left after trimming.
    - `"open"`: real content has started. Pure pass-through from here.

    `open` (the public property) is `True` for `"trimming"` or `"open"` --
    both mean the phrase has been found, which is what the round-end
    failsafe/mis-bet logic in `_stream_reply_with_tools` actually cares
    about, not whether trimming has finished.

    `retained` accumulates only the pre-match text, purely so the caller can
    fall back to speaking it (via `_strip_sentinel`) if the round ends still
    `"closed"` -- the failsafe for a turn where the guide forgot the phrase.

    `emitted_any` is distinct from `open`: with gating disabled
    (`config.FINAL_ANSWER_SENTINEL` empty) the gate starts fully open, but a
    round that produced zero text should still not be reported as "already
    spoken" by the caller's round-end logging -- `emitted_any` tracks
    whether `feed` actually returned non-empty text at least once."""

    def __init__(self) -> None:
        self._state = "open" if SENTINEL_STRICT is None else "closed"
        self.retained = ""
        self.emitted_any = False

    @property
    def open(self) -> bool:
        return self._state != "closed"

    def feed(self, delta: str) -> str:
        if self._state == "open":
            if delta:
                self.emitted_any = True
            return delta
        if self._state == "closed":
            self.retained += delta
            match = SENTINEL_STRICT.search(self.retained)
            if not match:
                return ""
            self._state = "trimming"
            return self._trim(self.retained[match.end():])
        return self._trim(delta)  # self._state == "trimming"

    def _trim(self, text: str) -> str:
        remainder = LEAD_PUNCT_RE.sub("", text, count=1)
        if not remainder:
            return ""  # still trimming -- nothing but punctuation/whitespace so far
        self._state = "open"
        self.emitted_any = True
        return remainder
