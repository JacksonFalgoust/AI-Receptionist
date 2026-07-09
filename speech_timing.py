"""Estimates how long Twilio's TTS will take to speak a given text.

GuideAnts typically returns the whole reply well before Twilio finishes
speaking it aloud (with some models, as a single burst -- see guide_client.py
and ARCHITECTURE.md), so app.py can't rely on "we're still receiving tokens"
to know a reply is still being spoken. The primary end-of-playback signal is
Twilio's agent-stopped speaker event (`events="speaker-events"` in the
TwiML, see speaker_events.py); this estimate is what app.py holds its
in-flight-reply flag open on until the first such event is recognized on a
call, and the basis of the ceiling on how long it will wait for one, so a
lost event can't hold a turn open forever. estimate_spoken_prefix() inverts
the same words-per-second model to guess how much of a reply the caller had
heard when they barged in mid-playback.
"""


def estimate_seconds(text: str, words_per_second: float) -> float:
    """Estimate spoken duration of text at a constant speaking rate."""
    words = text.split()
    if not words:
        return 0.0
    return len(words) / words_per_second


def estimate_spoken_prefix(text: str, elapsed_seconds: float, words_per_second: float) -> str:
    """Best-effort guess at how much of `text` has been spoken aloud after
    `elapsed_seconds` of playback, assuming the same constant speaking rate
    as estimate_seconds(). Returns "" when nothing has plausibly been spoken
    yet, and the full text once the elapsed time covers all of it.
    """
    words = text.split()
    if not words or elapsed_seconds <= 0 or words_per_second <= 0:
        return ""
    words_heard = int(elapsed_seconds * words_per_second)
    if words_heard <= 0:
        return ""
    if words_heard >= len(words):
        return text
    return " ".join(words[:words_heard])
