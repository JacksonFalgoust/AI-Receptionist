import os

from dotenv import load_dotenv

load_dotenv()

GUIDEANTS_BASE_URL = os.environ.get("GUIDEANTS_BASE_URL", "http://localhost:5107").rstrip("/")
GUIDEANTS_PUB_ID = os.environ.get("GUIDEANTS_PUB_ID", "")
GUIDEANTS_API_KEY = os.environ.get("GUIDEANTS_API_KEY", "anonymous")
GUIDEANTS_MODEL = os.environ.get("GUIDEANTS_MODEL", "guide")

WELCOME_GREETING = os.environ.get(
    "WELCOME_GREETING", "Thanks for calling! How can I help you today?"
)

TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")

PORT = int(os.environ.get("PORT", "8080"))

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
