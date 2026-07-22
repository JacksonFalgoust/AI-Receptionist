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
7. **Wire up the reservation tool** so the guide can check availability and
   book rentals (optional — skip if this demo doesn't need Booqable):
   - In the guide's tool/API config, import
     `guide-demo/booqable-reservations-openapi.json` from this repo as an
     OpenAPI tool.
   - Its `servers[0].url` is `http://host.docker.internal:8080/api/reservations`
     — correct as-is if GuideAnts runs in Docker and this app runs on the
     host at port 8080 (the default, see step 5 below). If GuideAnts runs
     outside Docker, change it to `http://localhost:8080/api/reservations`
     before importing.
   - Set the tool's `X-Api-Key` auth value to the same string you'll put in
     this app's `RECEPTIONIST_API_KEY` (step 3).
   - If you re-import this schema later after editing it, re-import replaces
     the stored copy in GuideAnts — the file on disk isn't read live.

## 2. Install this project's dependencies

1. Open a terminal in this folder.
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## 3. Fill in `.env`

Copy `.env.example` to `.env` in this folder and fill in the values from step 1:

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

If you wired up the reservation tool in step 1.7, also fill in:

```
BOOQABLE_COMPANY_URL=<your Booqable account URL, e.g. https://yourco.booqable.com>
BOOQABLE_API_KEY=<Booqable API key>
RECEPTIONIST_API_KEY=<a separate secret you invent — never reuse BOOQABLE_API_KEY>
BOOQABLE_TIMEZONE=America/New_York
```

`RECEPTIONIST_API_KEY` must match whatever you set as the tool's `X-Api-Key`
value inside GuideAnts (step 1.7) — this app rejects `/api/reservations/*`
calls that don't send a matching header, and the LLM must never be given
`BOOQABLE_API_KEY` directly. Verify the Booqable side is reachable with:

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

## 5. Run the app and expose it publicly

Conversation Relay requires a public `wss://` URL — it will not connect to
`localhost`.

1. Start the app locally:
   ```
   uvicorn app:app --host 0.0.0.0 --port 8080
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

## Optional hardening (not implemented, not required for the demo)

- **Validate `X-Twilio-Signature`** on `/twiml` (and the WebSocket upgrade
  request) using `TWILIO_AUTH_TOKEN`, so only real Twilio requests are
  accepted. Useful before exposing this publicly for real.
- **Handle `end`/handoff messages** (e.g., transfer to a human) and configure
  the `<Connect action="...">` callback URL.
- **Silence timeouts** — end or re-prompt the call if the caller goes quiet.
- **DTMF menu** — currently keypresses are logged but not acted on.
