import os

from dotenv import load_dotenv

load_dotenv()

# Rotating log file, in addition to the console output logging.basicConfig
# already gives every module's logger (see app/logging_setup.py). Empty
# disables file logging -- console-only, the previous behavior. Sized for a
# long-running dev server, not production log retention.
LOG_FILE = os.environ.get("LOG_FILE", "logs/app.log")
LOG_MAX_BYTES = int(os.environ.get("LOG_MAX_BYTES", str(5_000_000)))
LOG_BACKUP_COUNT = int(os.environ.get("LOG_BACKUP_COUNT", "3"))

GUIDEANTS_BASE_URL = os.environ.get("GUIDEANTS_BASE_URL", "http://localhost:5107").rstrip("/")
GUIDEANTS_PUB_ID = os.environ.get("GUIDEANTS_PUB_ID", "")
GUIDEANTS_API_KEY = os.environ.get("GUIDEANTS_API_KEY", "anonymous")
GUIDEANTS_MODEL = os.environ.get("GUIDEANTS_MODEL", "guide")

# Request timeout for calls to GuideAnts. The openai SDK's default (600s,
# 2 retries) is dead air on a live phone call, so this app uses a much
# tighter budget and a single retry (set in guide_client._get_client()).
GUIDEANTS_TIMEOUT_SECONDS = float(os.environ.get("GUIDEANTS_TIMEOUT_SECONDS", "30"))

# GuideAnts periodically reconciles its local ASR/TTS engines (observed:
# roughly every 30s) without waiting out an in-flight request first, so a
# request whose timing overlaps that cycle can have its connection dropped or
# get a transient 5xx moments before the engine is healthy again. Used by
# local_audio_client's single retry on such a failure (see
# local_audio_client._post_with_retry) -- a real retry, unlike guide_client's
# SDK-level one, since httpx has no automatic retry-after-response-started.
GUIDEANTS_RETRY_DELAY_SECONDS = float(os.environ.get("GUIDEANTS_RETRY_DELAY_SECONDS", "1"))

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
WELCOME_BACK_GREETING_TEMPLATE = os.environ.get(
    "WELCOME_BACK_GREETING_TEMPLATE", "Hi {name}, welcome back! How can I help you today?"
)
# Ceiling on the Booqable customer lookup done before answering the call --
# this runs in the call-answering path (POST /twiml must respond promptly),
# so a slow/unreachable Booqable must never delay or block picking up.
CALLER_LOOKUP_TIMEOUT_SECONDS = float(os.environ.get("CALLER_LOOKUP_TIMEOUT_SECONDS", "3"))

TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
WS_TOKEN_TTL_SECONDS = int(os.environ.get("WS_TOKEN_TTL_SECONDS", "120"))

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

# The literal phrase the guide is instructed (see guide-demo/Twillio demo
# agent/instructions.md's "FINAL ANSWER MARKER" paragraph) to speak at the
# start of its final answer, once it has nothing left to check. guide_client
# scans every incoming delta for this phrase and forwards nothing to Twilio
# until it's seen -- so narration and tool-call preamble are dropped with
# certainty rather than guessed at by a length threshold (see
# _SentinelGate). Matching is case-insensitive and tolerant of the
# whitespace/punctuation GuideAnts puts around it; the phrase itself is
# never spoken. Set to "" to disable gating entirely (every delta streams
# live, unconditionally) -- used as this app's control/no-op mode.
FINAL_ANSWER_SENTINEL = os.environ.get("FINAL_ANSWER_SENTINEL", "declare victory")

# For this long (in seconds) after a client-side tool call starts (see
# guide_client._stream_reply_with_tools's ToolCallStarted event), app.py
# ignores non-stop-command caller speech instead of letting
# barge_in.should_interrupt() treat it as a new question and cancel the
# answer that's still coming; an explicit stop/wait phrase always still cuts
# through. Bounded so a hung tool can't make the caller un-interruptible for
# the rest of the call.
TOOL_CALL_BARGE_IN_GRACE_SECONDS = float(os.environ.get("TOOL_CALL_BARGE_IN_GRACE_SECONDS", "8"))

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

# Booqable reservation tools (see app/guide_client.py's _run_reservation_tool
# and /api/booqable/ping) -- lets the GuideAnts guide check availability and
# book rentals through this app instead of talking to Booqable directly. The
# guide never sees BOOQABLE_API_KEY -- these calls are resolved in-process,
# never over HTTP, so there's no separate shared secret to gate them with.
BOOQABLE_COMPANY_URL = os.environ.get(
    "BOOQABLE_COMPANY_URL", "https://smart-apps-innovations.booqable.com"
).rstrip("/")
BOOQABLE_BASE_URL = BOOQABLE_COMPANY_URL + "/api/4"
BOOQABLE_API_KEY = os.environ.get("BOOQABLE_API_KEY", "")

# Timezone naive starts_at/stops_at values from the caller/guide are
# interpreted in, before being converted to UTC for Booqable.
BOOQABLE_TIMEZONE = os.environ.get("BOOQABLE_TIMEZONE", "America/New_York")

# Outbound SMS (the sendPaymentLink reservation tool) -- lets the
# receptionist text a payment link after booking. TWILIO_AUTH_TOKEN (above)
# doubles as the REST API auth token here.
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER", "")

# Placeholder until real Stripe/Booqable payment-link generation exists (see
# docs/PAYMENT_LINK_OPTIONS.md) -- not a real checkout URL yet.
PAYMENT_LINK_BASE_URL = os.environ.get("PAYMENT_LINK_BASE_URL", "https://example.com/pay").rstrip("/")

# Outbound email (the sendPaymentLink reservation tool) -- Postmark, added
# as a second channel alongside the Twilio SMS path above. POSTMARK_FROM_EMAIL
# must be a confirmed Sender Signature in the Postmark account or every send
# fails with ErrorCode 401.
POSTMARK_SERVER_TOKEN = os.environ.get("POSTMARK_SERVER_TOKEN", "")
POSTMARK_FROM_EMAIL = os.environ.get("POSTMARK_FROM_EMAIL", "")
POSTMARK_MESSAGE_STREAM = os.environ.get("POSTMARK_MESSAGE_STREAM", "outbound")
POSTMARK_API_URL = os.environ.get("POSTMARK_API_URL", "https://api.postmarkapp.com").rstrip("/")

# Fallback channel when the guide calls sendPaymentLink without one: "email" or
# "sms".
PAYMENT_LINK_DEFAULT_CHANNEL = os.environ.get("PAYMENT_LINK_DEFAULT_CHANNEL", "email").strip().lower()

# --- Local audio demo (app/local_demo_api.py) -------------------------------
# A second phone demo that keeps Twilio only as the phone line: <Record>
# captures each caller turn and GuideAnts' own speech models do the
# transcription and synthesis, instead of Conversation Relay's built-in
# Deepgram/ElevenLabs. Unused by the /twiml + /ws Conversation Relay flow.

# Model ids on GuideAnts' published OpenAI-compatible API. The defaults match
# what /v1/models advertises; override only if a guide exposes different ids.
GUIDEANTS_TRANSCRIPTION_MODEL = os.environ.get("GUIDEANTS_TRANSCRIPTION_MODEL", "transcription")
GUIDEANTS_SPEECH_MODEL = os.environ.get("GUIDEANTS_SPEECH_MODEL", "speech")
# Voice name for synthesis. Left out of the request entirely when empty, so
# GuideAnts picks its configured default voice.
GUIDEANTS_SPEECH_VOICE = os.environ.get("GUIDEANTS_SPEECH_VOICE", "")

# <Record timeout>: seconds of caller silence that end a turn. This is the
# whole of turn-taking in this demo -- there is no VAD or barge-in. Lower
# feels snappier but cuts off callers who pause mid-sentence.
LOCAL_RECORD_SILENCE_SECONDS = int(os.environ.get("LOCAL_RECORD_SILENCE_SECONDS", "3"))
# <Record maxLength>: hard ceiling on a single caller turn.
LOCAL_RECORD_MAX_SECONDS = int(os.environ.get("LOCAL_RECORD_MAX_SECONDS", "30"))

# Deadline for the whole turn pipeline (fetch + STT + guide + TTS). Twilio
# abandons a webhook that takes ~15s, so this (plus LOCAL_FALLBACK_TTS_BUDGET_
# SECONDS below, which can run afterward) must stay under that: on expiry the
# caller hears LOCAL_TIMEOUT_PHRASE and the call continues, instead of Twilio
# dropping it. A tool-calling turn (checkAvailability/createOrder) can run
# long enough to blow even this: if GuideAnts' own turn gets cancelled by a
# mid-stream disconnect while a tool result is in flight, guide_client.py's
# recovery discards everything and starts a fresh conversation from scratch
# (see stream_reply's `_is_stale_tool_result` branch) -- which can easily
# not fit in whatever's left of the budget. Raising this gives that retry
# more room but doesn't guarantee it fits; there's no budget short of
# Twilio's own ceiling that guarantees a from-scratch retry completes.
LOCAL_TURN_BUDGET_SECONDS = float(os.environ.get("LOCAL_TURN_BUDGET_SECONDS", "11"))

# Separate deadline for the apology/greeting synthesis spoken OUTSIDE that
# budget (see local_call._with_fallback_audio and local_demo_api's greeting
# synthesis): both run after their own timing budget has already elapsed, so
# without a bound of their own a slow GuideAnts TTS call could stack on top
# of that elapsed time and blow past Twilio's ~15s webhook timeout. Short,
# because the text being synthesized here is always a short fixed phrase.
# LOCAL_TURN_BUDGET_SECONDS + this is the real worst-case wait Twilio sees --
# keep their sum comfortably under ~15s if you raise either one.
LOCAL_FALLBACK_TTS_BUDGET_SECONDS = float(os.environ.get("LOCAL_FALLBACK_TTS_BUDGET_SECONDS", "3"))

# <Record>'s action callback fires before the recording's media is finished
# being stored, so the first fetch can 404 for a beat.
LOCAL_RECORDING_FETCH_ATTEMPTS = int(os.environ.get("LOCAL_RECORDING_FETCH_ATTEMPTS", "5"))
LOCAL_RECORDING_FETCH_DELAY_SECONDS = float(os.environ.get("LOCAL_RECORDING_FETCH_DELAY_SECONDS", "0.4"))

# Idle eviction for the per-CallSid GuideAnts session map and the cache of
# synthesized replies waiting to be fetched by Twilio's player.
LOCAL_SESSION_TTL_SECONDS = float(os.environ.get("LOCAL_SESSION_TTL_SECONDS", "1800"))
LOCAL_AUDIO_TTL_SECONDS = float(os.environ.get("LOCAL_AUDIO_TTL_SECONDS", "300"))

# Spoken when a turn can't produce a real answer. Every one of these is
# followed by another <Record>, so the call always continues.
LOCAL_NO_SPEECH_PHRASE = os.environ.get(
    "LOCAL_NO_SPEECH_PHRASE", "Sorry, I didn't catch that. Could you say it again?"
)
LOCAL_ERROR_PHRASE = os.environ.get(
    "LOCAL_ERROR_PHRASE", "Sorry, I had trouble with that. Could you try again?"
)
LOCAL_TIMEOUT_PHRASE = os.environ.get(
    "LOCAL_TIMEOUT_PHRASE",
    "Sorry, that's taking longer than expected. Could you say that again?",
)
