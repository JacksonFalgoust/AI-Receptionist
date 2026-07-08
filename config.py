import os

from dotenv import load_dotenv

load_dotenv()

GUIDEANTS_BASE_URL = os.environ.get("GUIDEANTS_BASE_URL", "http://localhost:5107").rstrip("/")
GUIDEANTS_PUB_ID = os.environ.get("GUIDEANTS_PUB_ID", "")
GUIDEANTS_API_KEY = os.environ.get("GUIDEANTS_API_KEY", "anonymous")
GUIDEANTS_MODEL = os.environ.get("GUIDEANTS_MODEL", "guide")

# Average TTS speaking rate, used to estimate how long Twilio will take to
# speak a reply since GuideAnts' non-streaming endpoint gives no real
# playback-progress signal (see speech_timing.py). ~150 wpm is a typical
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
