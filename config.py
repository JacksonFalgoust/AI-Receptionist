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

# Selective barge-in: how long to wait after a caller interrupts before
# assuming it was noise/silence and resuming the reply on our own.
BARGE_IN_RESUME_TIMEOUT_S = float(os.environ.get("BARGE_IN_RESUME_TIMEOUT_S", "2.5"))

# Extra phrases (beyond barge_in.STOP_PHRASES) that should stop the reply.
BARGE_IN_EXTRA_STOP_PHRASES = [
    p.strip().lower()
    for p in os.environ.get("BARGE_IN_EXTRA_STOP_PHRASES", "").split(",")
    if p.strip()
]
