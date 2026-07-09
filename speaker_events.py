"""Loose classifier for Conversation Relay speaker-event WS messages.

Subscribing with `events="speaker-events"` in the <ConversationRelay> TwiML
(see app.py's /twiml) makes Twilio notify this app when the agent (TTS
playback) and the client (caller) start and stop speaking. Twilio's
reference docs document the subscription attribute but not (yet) the exact
JSON shape of the resulting messages, so `classify` matches loosely instead
of pattern-matching one exact schema: it scans the message's string values
for the documented event names ("agentSpeaking" / "clientSpeaking") and for
start/stop-flavored words. app.py acts on "agent-stop" (the playback hold in
respond_to(), and only after at least one agent-stop has already been
recognized on the call) and on "client-start"/"client-stop" (holding a
buffered turn open while the caller is still speaking -- see
schedule_turn()); both degrade gracefully if a wire shape this parser can't
recognize stops these events being seen -- estimate-based pacing and a plain
TURN_PAUSE_SECONDS debounce respectively, rather than misbehaving. Only called for message types app.py doesn't already handle,
so a caller's prompt whose transcript happens to mention "agent speaking"
never reaches it. Pure functions only, no I/O -- mirrors the role
fillers.py and barge_in.py play for their features.
"""

import re

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

# Checked in this order: a stop notification may plausibly mention when the
# speech *started* (e.g. a startTime), but not the other way around.
_STOP_HINTS = ("stop", "end", "finish", "complete", "done")
_START_HINTS = ("start", "begin")

# Twilio's actual live wire shape (observed on real calls, 2026-07-09) is
# {"type": "info", "name": "agentSpeaking", "value": "on"|"off"} -- the
# direction is a bare on/off value rather than a start/stop word. Matched by
# exact string equality, not substring, so words that merely contain "on"
# (e.g. "conversation") can't false-positive.
_STOP_VALUES = ("off",)
_START_VALUES = ("on",)

_MAX_DEPTH = 3


def _iter_strings(value, depth: int = _MAX_DEPTH):
    """Yield every string value in a (shallowly) nested JSON-ish structure, lowercased."""
    if isinstance(value, str):
        yield value.lower()
    elif depth > 0 and isinstance(value, dict):
        for v in value.values():
            yield from _iter_strings(v, depth - 1)
    elif depth > 0 and isinstance(value, (list, tuple)):
        for v in value:
            yield from _iter_strings(v, depth - 1)


def classify(msg) -> str | None:
    """Classify a decoded WS message as a speaker event, or None if it isn't one.

    Returns "agent-start", "agent-stop", "client-start", "client-stop", or --
    for a recognized speaker event whose direction can't be determined --
    "agent-unknown"/"client-unknown".
    """
    if not isinstance(msg, dict):
        return None
    strings = list(_iter_strings(msg))
    # "agentSpeaking" / "agent-speaking-started" / "agent_speaking" all
    # squash to something containing "agentspeaking".
    squashed = [_NON_ALNUM_RE.sub("", s) for s in strings]
    if any("agentspeaking" in s for s in squashed):
        speaker = "agent"
    elif any("clientspeaking" in s for s in squashed):
        speaker = "client"
    else:
        return None
    if any(hint in s for s in strings for hint in _STOP_HINTS) or any(
        s in _STOP_VALUES for s in strings
    ):
        return f"{speaker}-stop"
    if any(hint in s for s in strings for hint in _START_HINTS) or any(
        s in _START_VALUES for s in strings
    ):
        return f"{speaker}-start"
    return f"{speaker}-unknown"
