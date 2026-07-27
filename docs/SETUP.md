# Setup (SETUP.md)

Everything needed to get this voice receptionist demo running on your device,
from creating the GuideAnts guide through placing a real phone call.

## Prerequisites

- **Python 3.10+** — check with `python --version`.
- **ngrok** — https://ngrok.com/download (free account is fine).
- **A Twilio account** with (or able to buy) a voice-capable phone number.
- **The GuideAnts backend** running and reachable somewhere (default dev:
  `http://localhost:5107`). This is a separate project — start it however that
  project documents before continuing.

## 1. GuideAnts — create and publish the receptionist guide

1. In the GuideAnts UI, create a new **guide** (Assistant of kind Guide).
2. Write the receptionist's entire behavior into its **Instructions**: who the
   business is, hours, services offered, how to greet callers, how to handle
   common questions, and what to say when it can't help. Since this is voice:
   - Keep replies short and conversational.
   - Avoid markdown, bullet lists, links, or anything that doesn't make sense
     spoken aloud.
3. **Publish** the guide. Copy its **Published Guide ID** (a GUID) — this is
   `GUIDEANTS_PUB_ID`.
4. Choose an auth mode for the published guide:
   - **Anonymous** — simplest for a demo, no key needed.
   - **API Key** — copy the generated key once (it's only shown at creation);
     this is `GUIDEANTS_API_KEY`.
5. Open the guide's **APIs** config tab (in the Publish dialog) and:
   - Turn on **"Enable Wire API"**, and check the **"Responses"** endpoint
     checkbox (not "Chat Completions" — this app uses the Responses endpoint
     for its explicit conversation-id continuation, see ARCHITECTURE.md).
     Both are required — the OpenAI-compatible endpoint returns
     `403 endpoint_disabled` if either is off. (Not on by default.)
   - Leave `GUIDEANTS_MODEL=guide` as-is — `guide` is the fixed alias key,
     not the underlying model name shown in the alias mapping. You can
     confirm the exact alias to use by calling
     `GET {GUIDEANTS_BASE_URL}/api/published/openai/{pubId}/v1/models` — it
     lists the valid `id`s (`guide`, `embeddings`, `image`, etc.).
   - Confirm the OpenAI-compatible base path shown there matches
     `{GUIDEANTS_BASE_URL}/api/published/openai/{pubId}/v1`.
6. Make sure the GuideAnts backend is running and reachable at the host/port
   you'll put in `GUIDEANTS_BASE_URL` (default dev: `http://localhost:5107`).
7. **Wire up the reservation tools** so the guide can check availability and
   book rentals (optional — skip if this demo doesn't need Booqable), and the
   **caller's-phone-number tool** (optional, but the callback flow and
   reservation phone step in the guide's instructions both reference it).
   Both are **Client Actions** tool sources — meaning GuideAnts never calls
   them itself over HTTP; it hands each one back, unresolved, to whichever
   client (this app) is on the call, which answers it in
   `app/guide_client.py`. See ARCHITECTURE.md's "Client-side tool calls"
   section for the full mechanism and why this is more secure than the
   Web API tool source this demo used to use: there's no HTTP endpoint or
   shared API key that anyone (or anything) other than an active call
   through this app could use to invoke a reservation operation.
   1. In the guide editor, open its **Tools** section and click **+ Add Tool
      Source**.
   2. In the picker, choose **Client Actions** ("An action executed by the
      connecting client"), not **Web API**.
   3. On the **Schema** tab, paste the full contents of
      `guide-demo/reservations-client-tool.json` from this repo. Its
      `servers[0].url` is `client://voice-receptionist` — leave this as-is;
      unlike a Web API server URL, it's never actually dialed, it just marks
      the source as client-handled.
   4. No Authentication tab entry is needed — GuideAnts never sends a real
      HTTP request for this tool source.
   5. Save. The eight operations (`listCatalog`, `checkAvailability`,
      `createReservation`, `findReservations`, `cancelReservation`,
      `listCustomers`, `createCustomer`, `sendPaymentLink`) should appear as
      tools the guide can call.
   6. **If you edit `reservations-client-tool.json` later**, re-paste it into
      the same Schema tab and save — the file on disk isn't read live, and
      there's no auto-sync. A stale copy is a common source of confusing
      guide behavior (e.g. the guide asking for fields that don't exist, or
      not knowing about fields that do) that looks like a code bug but isn't
      — see ARCHITECTURE.md's "`createReservation` argument shape" for a
      real example (and why this schema deliberately uses flat
      `customer_name`/`customer_email`/`customer_phone` fields instead of a
      nested `customer` object).
   7. Repeat steps 1–2 for a second tool source, then on its **Schema** tab
      paste the full contents of `guide-demo/caller-phone-client-tool.json`
      instead. Its `servers[0].url` is `client://caller-phone` — a different
      bridge identifier from the reservations tool's `client://voice-receptionist`
      so the two tool sources don't collide in the GuideAnts UI; still no
      Authentication entry. Save — `get_caller_phone_number` should now
      appear alongside the Booqable operations. If you edit that file later,
      re-paste it the same way.
   8. Both tools are only answered on a real call through this app — testing
      the guide directly in GuideAnts' own chat UI won't resolve either one,
      since that path doesn't go through `app/guide_client.py`. The guide's
      instructions already account for the phone-number tool specifically
      (they fall back to just asking the caller for a number); the
      reservation tools will simply appear to hang or error in that UI.
   9. If you skip this step entirely, also skip filling in the Booqable/Twilio
      variables in step 3 below — leave `BOOQABLE_API_KEY` unset and the
      reservation tools will fail closed with a clear config error rather
      than silently doing nothing.

## 2. Install this project's dependencies

1. Open a terminal at the repository root.
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## 3. Fill in `.env`

Copy `.env.example` to `.env` in the repository root and fill in the values from step 1:

```
GUIDEANTS_BASE_URL=http://localhost:5107
GUIDEANTS_PUB_ID=<published-guide-guid>
GUIDEANTS_API_KEY=<key-or-"anonymous">
WELCOME_GREETING=<what the AI says when it picks up>
PORT=8080
```

A couple more variables control the filler-phrase behavior (see the manual
test in step 6). Both are optional — sensible built-in defaults apply if you
leave them unset:

```
FILLER_PHRASES=Let me look that up for you.|One moment while I check on that.
FILLER_DELAY_SECONDS=1.0
```

- `FILLER_PHRASES` — pipe-separated (`|`) list of short phrases the app can
  speak, before the real answer, when the caller's utterance looks like a
  question or request *and* GuideAnts hasn't replied yet (masks GuideAnts
  lookup latency). Pipe-separated rather than comma-separated because the
  phrases themselves contain commas and periods. If unset, a built-in default
  list of six phrases is used.
- `FILLER_DELAY_SECONDS` — how long (in seconds) to wait for GuideAnts' reply,
  for a filler-eligible utterance, before speaking a filler phrase. If the
  reply arrives before this elapses, no filler is spoken at all. Defaults to
  `1.0`.
- `EXTRA_BACKCHANNEL_PHRASES` — comma-separated list of extra phrases (beyond
  the built-in list in `fillers.py`) that count as pure acknowledgment noise
  ("ok", "yeah", "got it", ...) and should never get a guide reply, whether
  heard mid-reply or just after it finishes. Optional.

If you wired up the reservation tools in step 1.7, also fill in:

```
BOOQABLE_COMPANY_URL=<your Booqable account URL, e.g. https://yourco.booqable.com>
BOOQABLE_API_KEY=<Booqable API key>
BOOQABLE_TIMEZONE=America/New_York
```

`BOOQABLE_API_KEY` is only ever read by this app's own process
(`app/booqable_client.py`, constructed inside `app/guide_client.py`'s
reservation tool handlers) — the LLM never sees it, and since the reservation
tools are Client Actions rather than a Web API source, there's no separate
shared secret to configure for GuideAnts either. Verify the Booqable side is
reachable with:

```
curl http://localhost:8080/api/booqable/ping
```

## 4. Twilio account setup

1. **Accept the Conversation Relay AI/ML Features Addendum.** In the Twilio
   Console: **Voice → Settings**. Calls to Conversation Relay fail immediately
   without this.
2. Have (or buy) a **voice-capable Twilio phone number**.
3. **If you're on a Twilio trial account**, add the phone number you'll be
   calling from to your **Verified Caller IDs**: Console → **Phone Numbers →
   Manage → Verified Caller IDs** → add your number and confirm it via the
   code Twilio calls/texts you. Trial accounts can only place/receive calls
   with numbers on this list — calls from any other number are rejected.
4. Note your Account SID and Auth Token from the Console dashboard — not
   required for the demo to run, but keep them handy (and see the optional
   signature-validation note below).

## 4b. Postmark account setup (for the `sendPaymentLink` email channel)

The `sendPaymentLink` tool emails a payment link by default — SMS
(`TWILIO_ACCOUNT_SID`/`TWILIO_FROM_NUMBER` above) is only used if you set
`PAYMENT_LINK_DEFAULT_CHANNEL=sms` or the guide passes `channel: sms`.

1. In the Postmark dashboard, open your server and copy its **Server API
   token** (Servers → your server → API Tokens) into `POSTMARK_SERVER_TOKEN`.
2. Confirm a **Sender Signature** for the address you want to send from
   (Sender Signatures → Add Domain/Signature, then click the confirmation
   link Postmark emails you) and put that address in `POSTMARK_FROM_EMAIL`.
   Sending with an unconfirmed address fails every send with `ErrorCode 401`.
3. Leave `POSTMARK_MESSAGE_STREAM` unset unless you've created a custom
   message stream — it defaults to `outbound`.

## 5. Run the app and expose it publicly

Conversation Relay requires a public `wss://` URL — it will not connect to
`localhost`.

1. Start the app locally (from the repository root):
   ```
   uvicorn app.main:app --host 0.0.0.0 --port 8080
   ```
2. In another terminal, tunnel it:
   ```
   ngrok http 8080
   ```
   Copy the `https://xxxx.ngrok-free.app` URL it prints.
3. In the Twilio Console, open your phone number's configuration page and set
   **"A call comes in"** to:
   - Webhook: `https://xxxx.ngrok-free.app/twiml`
   - Method: `HTTP POST`

   (No need to construct the `wss://.../ws` URL yourself — `/twiml` builds it
   automatically from the request's Host header.)
4. **ngrok URLs change every restart on the free tier** — you'll need to
   update the Twilio webhook each time you restart ngrok, unless you use a
   paid ngrok static domain.

## 6. Call it

Dial the Twilio number. You should hear the `WELCOME_GREETING`, then be able to
ask a question and hear the guide's answer.

Try these to see the filler-phrase and selective-barge-in behavior:

- **Ask a question** (e.g. "what time do you close?") or a request ("can you
  help me find...", "I need...") **and GuideAnts takes longer than
  `FILLER_DELAY_SECONDS` to answer.** You should hear a short filler phrase
  (e.g. "Let me look that up for you.") while it's still thinking, followed by
  the real answer. If GuideAnts answers faster than that, no filler plays —
  the reply just starts.
- **Say "stop" (or "wait", "hold on", "no", ...) while the guide is
  mid-answer.** The answer should cut off right away, followed by a short
  local acknowledgment (e.g. "Okay.") — not a new guide reply.
- **Ask a different question while the guide is still answering a previous
  one.** The current answer should cut off and a fresh reply should start for
  your new question. Check the conversation in the GuideAnts UI afterward —
  your new question's turn should show an interruption note prefixed to it
  (e.g. "[Note: your previous reply was interrupted...]"), and the whole call
  should still be **one** conversation, not two. See ARCHITECTURE.md's
  "Interruption notes" section for what this looks like and its caveats.
- **Make a plain statement** (not a stop phrase or a question) while the
  guide is mid-answer. It should *not* get cut off; it keeps playing all the
  way to the end, and what you said is not recorded or acted on.
- **Say "ok" (or "okay", "yeah", "got it", ...) right as the guide finishes
  answering.** You should hear nothing in response — no new guide reply. This
  also covers the case where speech-to-text finishes transcribing your "ok"
  a moment *after* the answer already ended.
- **Make a plain statement** (not phrased as a question or request) as a
  fresh prompt and notice no filler phrase plays — the reply just starts
  directly.

If you wired up the reservation tools (step 1.7), try these too:

- **Book a rental.** When the guide asks for your phone number, it should ask
  whether to use the number you're calling from or a different one — not just
  assume one. Answer either way and confirm it uses the right number in the
  confirmation and in the resulting order in Booqable.
- **After booking, say yes to the payment link.** The guide should ask to
  email it, then ask for (or confirm) an email address and read it back
  before sending. Confirm the email actually arrives (check Postmark's
  Activity tab if it doesn't) and that the guide says "email" rather than
  "text."
- **Say "I'd like to buy a bike"** (or "can you service my bike?", or "can I
  talk to a person?"). The guide should offer to have someone call you back,
  ask for your name, then use your caller-ID number **without asking** — this
  is the one place it should use the number automatically. Check Booqable
  afterward: a customer should exist with a note describing the request (e.g.
  "wants to buy an e-bike").

## Security

`X-Twilio-Signature` validation on `/twiml`, and token verification on the
`/ws` WebSocket upgrade, are enforced automatically whenever
`TWILIO_AUTH_TOKEN` is set — no extra setup step required. `/twiml` rejects
requests with a missing/invalid signature (403), and mints a short-lived,
HMAC-signed token bound to the call's `CallSid`, embedded in the `wss://` URL
it returns. `/ws` verifies that token against the `callSid` reported in the
call's `setup` message and closes the connection if it doesn't match or has
expired. No other message type is processed — the guide is never touched —
until a `setup` message has passed that check: a client that sends `prompt`
(or anything else) before a valid `setup` gets the connection closed the
same way. If `TWILIO_AUTH_TOKEN` is left unset, both checks are skipped
(with a logged warning) so local/dev use without a token still works as
before. See `app/twilio_auth.py` for the implementation.

## Optional hardening (not implemented, not required for the demo)

- **Handle `end`/handoff messages** (e.g., transfer to a human) and configure
  the `<Connect action="...">` callback URL.
- **Silence timeouts** — end or re-prompt the call if the caller goes quiet.
- **DTMF menu** — currently keypresses are logged but not acted on.
