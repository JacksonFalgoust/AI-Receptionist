import os

from dotenv import load_dotenv

load_dotenv()

GUIDEANTS_BASE_URL = os.environ.get("GUIDEANTS_BASE_URL", "http://localhost:5107").rstrip("/")
GUIDEANTS_PUB_ID = os.environ.get("GUIDEANTS_PUB_ID", "")
GUIDEANTS_API_KEY = os.environ.get("GUIDEANTS_API_KEY", "anonymous")
GUIDEANTS_MODEL = os.environ.get("GUIDEANTS_MODEL", "guide")

# Request timeout for calls to GuideAnts. The openai SDK's default (600s,
# 2 retries) is dead air on a live phone call, so this app uses a much
# tighter budget and a single retry (set in guide_client._get_client()).
GUIDEANTS_TIMEOUT_SECONDS = float(os.environ.get("GUIDEANTS_TIMEOUT_SECONDS", "30"))

# Average TTS speaking rate, used to estimate how long Twilio will take to
# speak a reply (see speech_timing.py). Twilio's agent-stopped speaker event
# is the primary "reply finished playing" signal; this estimate paces the
# reply until the first such event is recognized on a call, and caps how
# long the app waits for one after that. ~150 wpm is a typical
# conversational TTS rate.
TTS_WORDS_PER_SECOND = float(os.environ.get("TTS_WORDS_PER_SECOND", "2.5"))

WELCOME_GREETING = os.environ.get(
    "WELCOME_GREETING", "Thanks for calling! How can I help you today?"
)

TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")

PORT = int(os.environ.get("PORT", "8080"))

# How long to wait for GuideAnts' reply before speaking a filler phrase to
# mask the lookup latency. If the reply arrives before this elapses, no
# filler is spoken at all.
FILLER_DELAY_SECONDS = float(os.environ.get("FILLER_DELAY_SECONDS", "1.0"))

# Twilio finalizes a `prompt` at each pause in caller speech, so a caller who
# takes a brief mid-sentence breath used to have their turn split in two: the
# first half was answered as the whole turn and the second half arrived
# mid-reply and was ignored. Instead, app.py buffers each transcribed prompt
# and only commits the turn after this much further caller silence; a
# clientSpeaking-start speaker event during the wait holds the buffer open
# for the caller's continuation (see app.py's schedule_turn()). Raising this
# tolerates longer pauses but delays the start of every reply by the same
# amount.
TURN_PAUSE_SECONDS = float(os.environ.get("TURN_PAUSE_SECONDS", "0.5"))

# When the caller resumes speaking during that wait, their continuation's
# transcript only arrives after STT finalization, which trails the
# clientSpeaking-stop event -- so once they stop again, wait this long
# (instead of TURN_PAUSE_SECONDS) for the transcript before giving up and
# committing the buffered text alone. Also bounds the extra dead air when
# the "resume" was just untranscribable noise.
TURN_RESUME_GRACE_SECONDS = float(os.environ.get("TURN_RESUME_GRACE_SECONDS", "1.5"))

# Filler phrases spoken before the real answer, to mask GuideAnts lookup
# latency. Pipe-separated in the env var since phrases contain commas/periods.
_DEFAULT_FILLER_PHRASES = [
    "Let me look that up for you.",
    "One moment while I check on that.",
    "Sure, give me just a second.",
    "Let me find that for you.",
    "Okay, let me pull that up.",
    "Happy to help — one second while I check.",
]

FILLER_PHRASES = [
    p.strip()
    for p in os.environ.get("FILLER_PHRASES", "").split("|")
    if p.strip()
] or _DEFAULT_FILLER_PHRASES

# Extra phrases (beyond fillers.BACKCHANNEL_PHRASES) that are pure
# acknowledgment noise and should never get a guide reply.
EXTRA_BACKCHANNEL_PHRASES = [
    p.strip().lower()
    for p in os.environ.get("EXTRA_BACKCHANNEL_PHRASES", "").split(",")
    if p.strip()
]

# Extra phrases (beyond barge_in.STOP_PHRASES) that should also cancel an
# in-flight reply when heard mid-reply.
EXTRA_STOP_PHRASES = [
    p.strip().lower()
    for p in os.environ.get("EXTRA_STOP_PHRASES", "").split(",")
    if p.strip()
]

# Short local acknowledgment spoken when a stop/wait phrase cancels an
# in-flight reply -- never sent through GuideAnts, so it cuts over the
# playback immediately instead of waiting on another guide round-trip.
_DEFAULT_STOP_ACK_PHRASES = [
    "Okay.",
    "Got it.",
    "No problem.",
    "Sure thing.",
]

STOP_ACK_PHRASES = [
    p.strip()
    for p in os.environ.get("STOP_ACK_PHRASES", "").split("|")
    if p.strip()
] or _DEFAULT_STOP_ACK_PHRASES

# Booqable reservation API (/api/reservations/*, /api/booqable/ping) -- lets
# the GuideAnts guide check availability and book rentals through this app
# instead of talking to Booqable directly.
BOOQABLE_COMPANY_URL = os.environ.get(
    "BOOQABLE_COMPANY_URL", "https://smart-apps-innovations.booqable.com"
).rstrip("/")
BOOQABLE_BASE_URL = BOOQABLE_COMPANY_URL + "/api/4"
BOOQABLE_API_KEY = os.environ.get("BOOQABLE_API_KEY", "")

# Shared secret the GuideAnts guide sends as X-Api-Key when calling
# /api/reservations/*. Distinct from BOOQABLE_API_KEY -- the LLM must never
# see the real Booqable key.
RECEPTIONIST_API_KEY = os.environ.get("RECEPTIONIST_API_KEY", "")

# Timezone naive starts_at/stops_at values from the caller/guide are
# interpreted in, before being converted to UTC for Booqable.
BOOQABLE_TIMEZONE = os.environ.get("BOOQABLE_TIMEZONE", "America/New_York")
