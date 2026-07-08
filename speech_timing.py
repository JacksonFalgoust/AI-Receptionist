"""Estimates how long Twilio's TTS will take to speak a given text.

GuideAnts' chat-completions endpoint is non-streaming (see guide_client.py),
so app.py gets the whole reply back and sends it to Twilio as a single frame
almost instantly -- it can't rely on "we're still receiving tokens" to know
a reply is still being spoken aloud. The primary end-of-playback signal is
Twilio's agent-stopped speaker event (`events="speaker-events"` in the
TwiML, see speaker_events.py); this estimate is what app.py holds its
in-flight-reply flag open on until the first such event is recognized on a
call, and the basis of the ceiling on how long it will wait for one, so a
lost event can't hold a turn open forever.
"""


def estimate_seconds(text: str, words_per_second: float) -> float:
    """Estimate spoken duration of text at a constant speaking rate."""
    words = text.split()
    if not words:
        return 0.0
    return len(words) / words_per_second
