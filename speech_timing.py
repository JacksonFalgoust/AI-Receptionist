"""Estimates how long Twilio's TTS will take to speak a given text.

GuideAnts' chat-completions endpoint is non-streaming (see guide_client.py),
so app.py gets the whole reply back and sends it to Twilio as a single frame
almost instantly -- it can no longer rely on "we're still receiving tokens"
to know a reply is still being spoken aloud. This lets app.py instead keep
its in-flight-reply flag set for roughly as long as Twilio will actually take
to speak the text, so mid-reply caller speech is still recognized as
mid-reply instead of looking like a fresh turn once the words are counted.
"""


def estimate_seconds(text: str, words_per_second: float) -> float:
    """Estimate spoken duration of text at a constant speaking rate."""
    words = text.split()
    if not words:
        return 0.0
    return len(words) / words_per_second
