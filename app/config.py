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
WELCOME_BACK_GREETING_TEMPLATE = os.environ.get(
    "WELCOME_BACK_GREETING_TEMPLATE", "Hi {name}, welcome back! How can I help you today?"
)

# --- Console configuration seed -------------------------------------------
# Seeded on first read (app/configuration_store.py), NOT in a migration:
# app/db.py's create_all() is the real runtime schema path, so a migration's
# data step would never run for most checkouts.
#
# These fill guide-demo/template/instructions.template.md's business and
# identity slots. The template itself is generic (any business); these
# values are just the demo shop it ships configured for.
DEFAULT_BUSINESS_PROFILE = {
    "name": "Peachtree Pedals",
    "description": "a bike rental shop in Atlanta, Georgia",
    # Obviously-fake placeholders (555 is the reserved fiction exchange), not
    # blanks: the Configuration console's businessProfileFormSchema requires a
    # non-empty phone, so an empty seed would greet the very first admin with
    # a validation error on a field they never touched. Neither phone nor
    # website is a template slot, so their values cannot reach the guide.
    "phone": "(404) 555-0142",
    "website": "",
    "timezone": "America/New_York",
    "address": "1234 Road Pkwy, Atlanta, GA",
    "locations": "1 location",
    "hours": [
        {"day": day, "open": "09:00", "close": "18:00", "closed": False}
        for day in range(7)
    ],
}

DEFAULT_IDENTITY = {
    "name": "Peachtree Pedals Receptionist",
    "greeting": WELCOME_GREETING,
    "closing": "Thanks for calling. Have a great ride!",
    # One of frontend/src/lib/voices.ts's VOICE_OPTIONS, for the same reason
    # as `phone` above -- identityFormSchema requires a non-empty voice. Not a
    # template slot either; today nothing outside the console reads it.
    "voice": "Avery — Warm",
    "tone": "custom",
    "customTone": "warm, upbeat, and polite",
    "primaryLanguage": "en-US",
    "supportedLanguages": ["en-US"],
}

DEFAULT_TERMINOLOGY = {
    "customer": "Customer",
    "reservation": "Reservation",
    "location": "Location",
    "employee": "Team member",
}

# --- Console knowledge seed -----------------------------------------------
# The shop's policy knowledge, seeded on first read (app/knowledge_store.py's
# seed_default_items) exactly as the configuration row above is.
#
# This is not decoration. A publish replaces the live guide's vector store
# wholesale (anything absent from the bundle is DELETED -- see
# app/guide_publish/bundle.py), and instructions.template.md tells the guide
# to "search the knowledge base" for precisely these topics. With an empty
# knowledge_items table the first publish would strip the receptionist's
# entire policy knowledge while leaving it talking fluently about nothing.
#
# The text is the original guide-demo vector-store document, one item per
# section. Live stock and prices deliberately are NOT here: those come from
# Booqable through the reservation tools.
DEFAULT_KNOWLEDGE_ITEMS = [
    {
        "id": "seed-location-contact-hours",
        "title": "Location, Contact, and Hours",
        "type": "location",
        "content": (
            "Peachtree Pedals is located at 1234 Road Pkwy, Atlanta, GA, with a lot "
            "behind the shop and a gate that opens directly onto the Atlanta BeltLine "
            "trail. Open every day, 9:00 AM to 6:00 PM, including weekends and "
            "holidays except Thanksgiving Day and Christmas Day, when the shop is "
            "closed."
        ),
    },
    {
        "id": "seed-how-rentals-work",
        "title": "How Rentals Work",
        "type": "procedure",
        "content": (
            "Bikes rent by the day: pick up any time after opening and return by close "
            "the same day. Multi-day rentals are available on request at a discounted "
            "daily rate — ask a team member for current multi-day pricing. Walk-ins "
            "are welcome if a bike is in stock, but calling ahead to reserve is "
            "recommended, especially on weekends and holidays when popular bikes sell "
            "out."
        ),
    },
    {
        "id": "seed-what-you-need-to-rent",
        "title": "What You Need to Rent",
        "type": "policy",
        "content": (
            "A valid photo ID and a credit card are required at pickup. The card is "
            "used to place a security hold, not a charge, unless the bike is returned "
            "damaged or isn't returned at all. Riders must be at least 16 to rent in "
            "their own name; younger riders can ride if a parent or guardian rents the "
            "bike and stays with them. Helmet rental is available for an additional "
            "daily fee — current pricing is in the booking system. We recommend a "
            "helmet for every rider and require one for riders under 18, though riders "
            "are welcome to bring their own at no charge instead of renting one."
        ),
    },
    {
        "id": "seed-bike-types",
        "title": "Bike Types",
        "type": "product",
        "content": (
            "Cruisers: comfortable upright riding position, best for casual BeltLine "
            "rides.\n"
            "Road bikes: lightweight with drop handlebars, best for longer or faster "
            "rides.\n"
            "Mountain bikes: rugged tires, good for trails and rougher pavement.\n"
            "Electric bikes: pedal-assist, popular for hills and longer distances; "
            "riders must be at least 18.\n"
            "Kids bikes: a range of smaller frame sizes.\n"
            "Tandem bikes: two riders on one bike; limited stock, best reserved ahead "
            "of time.\n"
            "\n"
            "Exact prices change with season and demand, so always check the live "
            "booking system rather than quoting a remembered price."
        ),
    },
    {
        "id": "seed-accessories",
        "title": "Accessories",
        "type": "product",
        "content": (
            "A cable lock is included with every rental at no extra charge. Helmet "
            "rental, baskets, phone mounts, child seats, and trailers are all "
            "available for an additional daily fee, subject to availability — check "
            "the booking system for what's currently in stock and its price."
        ),
    },
    {
        "id": "seed-guided-tours",
        "title": "Guided Tours",
        "type": "service",
        "content": (
            "A guided two-hour BeltLine tour runs daily at 10 AM and 2 PM, and "
            "includes the bike, helmet, and a guide. Tours should be booked at least a "
            "day ahead. Groups larger than six people should call ahead so the shop "
            "can make sure enough guides and bikes are available."
        ),
    },
    {
        "id": "seed-damage-loss-theft",
        "title": "Damage, Loss, and Theft",
        "type": "policy",
        "content": (
            "The renter is responsible for the cost of repair or replacement, up to "
            "the bike's value, for damage beyond normal wear or for a bike that's lost "
            "or stolen during the rental period. The card on file covers this. If a "
            "bike is stolen during a rental, the renter should notify the shop and "
            "file a police report as soon as possible."
        ),
    },
    {
        "id": "seed-cancellations-and-changes",
        "title": "Cancellations and Changes",
        "type": "policy",
        "content": (
            "Reservations can be canceled or rescheduled at no charge if done more "
            "than 24 hours before pickup. Cancellations inside 24 hours may be charged "
            "a partial fee. To reschedule instead of canceling outright, let the "
            "caller know a team member can help once they call back, since "
            "rescheduling isn't done automatically."
        ),
    },
    {
        "id": "seed-groups-and-kids",
        "title": "Groups and Kids",
        "type": "policy",
        "content": (
            "Groups of up to 10 can usually be accommodated without advance notice; "
            "larger groups should call ahead. Kids bikes are available in a range of "
            "sizes, and riders under 12 must ride with an accompanying adult."
        ),
    },
    {
        "id": "seed-directions-and-parking",
        "title": "Directions and Parking",
        "type": "location",
        "content": (
            "Free parking is available in the lot behind the shop. The shop also has a "
            "gate directly onto the Atlanta BeltLine, so riders coming from the trail "
            "don't need to deal with street parking at all."
        ),
    },
    {
        "id": "seed-weather-policy",
        "title": "Weather Policy",
        "type": "policy",
        "content": (
            "Rentals go out rain or shine. In severe weather (thunderstorms, extreme "
            "heat advisories), the shop will offer a same-day reschedule at no charge "
            "if a caller asks."
        ),
    },
    {
        "id": "seed-employment",
        "title": "Employment",
        "type": "faq",
        "content": (
            "The shop hires bike mechanics and rental associates, part-time and "
            "full-time, ages 18 and up. Apply in person at the shop or ask to speak "
            "with the manager for hiring questions."
        ),
    },
    {
        "id": "seed-frequently-asked-questions",
        "title": "Frequently Asked Questions",
        "type": "faq",
        "content": (
            "- Do I need a reservation? Not required, but recommended, especially on "
            "weekends and holidays.\n"
            "- Can I rent for more than one day? Yes — ask a team member for the "
            "current multi-day rate.\n"
            "- Do you deliver bikes or offer drop-off? Not currently — all rentals are "
            "picked up and returned at the shop.\n"
            "- What happens if a bike breaks during my rental? Call the shop right "
            "away and they'll swap it out or adjust the charge.\n"
            "- Is there an age minimum? Riders must be 16 to rent in their own name, "
            "or younger with a parent or guardian renting for them."
        ),
    },
]

# Ceiling on the Booqable customer lookup done before answering the call --
# this runs in the call-answering path (POST /twiml must respond promptly),
# so a slow/unreachable Booqable must never delay or block picking up.
CALLER_LOOKUP_TIMEOUT_SECONDS = float(os.environ.get("CALLER_LOOKUP_TIMEOUT_SECONDS", "3"))

TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
WS_TOKEN_TTL_SECONDS = int(os.environ.get("WS_TOKEN_TTL_SECONDS", "120"))

PORT = int(os.environ.get("PORT", "8080"))

# E6 slice 1: this app's first durable state (everything else here is
# stateless apart from a GuideAnts-side conversation id per call). SQLite
# file, created on first run -- see app/db.py.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./data/concierge.db")

# Every record this app creates belongs to an organization; there is no
# multi-organization support yet (see frontend/TODO.md's Phase F), so every
# row gets this one hardcoded id.
DEFAULT_ORGANIZATION_ID = os.environ.get("DEFAULT_ORGANIZATION_ID", "org_default")

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")
# A salted PBKDF2 hash ("<salt_hex>:<hash_hex>"), never a plaintext password
# -- see app/auth.py's hash_password() to generate one. No default: an
# unset value means no one can log in, the safe failure mode for a fresh
# checkout.
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH", "")
AUTH_TOKEN_TTL_SECONDS = int(os.environ.get("AUTH_TOKEN_TTL_SECONDS", str(60 * 60 * 8)))

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

# --- GuideAnts authoring API ----------------------------------------------
# Distinct from GUIDEANTS_API_KEY, which is the *published-guide* key.
# /api/guides requires an admin JWT (RequireAuthorization("RequireAdmin")).
# Unset -> publishing returns 503; preview and bundle download still work.
GUIDEANTS_ADMIN_EMAIL = os.environ.get("GUIDEANTS_ADMIN_EMAIL", "")
GUIDEANTS_ADMIN_PASSWORD = os.environ.get("GUIDEANTS_ADMIN_PASSWORD", "")
# The update-match key: GuideAnts decides create-vs-update by matching
# manifest.json's name against an existing guide's name.
GUIDEANTS_GUIDE_NAME = os.environ.get("GUIDEANTS_GUIDE_NAME", "Twilio Demo Agent")
