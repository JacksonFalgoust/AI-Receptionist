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
   - Turn on **"Enable Wire API"**, and check the **"Chat Completions"**
     endpoint checkbox. Both are required — the OpenAI-compatible endpoint
     returns `403 endpoint_disabled` if either is off. (Not on by default.)
   - Leave `GUIDEANTS_MODEL=guide` as-is — `guide` is the fixed alias key for
     the chat/completions endpoint, not the underlying model name shown in the
     alias mapping. You can confirm the exact alias to use by calling
     `GET {GUIDEANTS_BASE_URL}/api/published/openai/{pubId}/v1/models` — it
     lists the valid `id`s (`guide`, `embeddings`, `image`, etc.).
   - Confirm the OpenAI-compatible base path shown there matches
     `{GUIDEANTS_BASE_URL}/api/published/openai/{pubId}/v1`.
6. Make sure the GuideAnts backend is running and reachable at the host/port
   you'll put in `GUIDEANTS_BASE_URL` (default dev: `http://localhost:5107`).

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
ask a question and hear the guide's answer. Try talking over the AI's reply —
it should stop and listen (barge-in).

## Optional hardening (not implemented, not required for the demo)

- **Validate `X-Twilio-Signature`** on `/twiml` (and the WebSocket upgrade
  request) using `TWILIO_AUTH_TOKEN`, so only real Twilio requests are
  accepted. Useful before exposing this publicly for real.
- **Handle `end`/handoff messages** (e.g., transfer to a human) and configure
  the `<Connect action="...">` callback URL.
- **Silence timeouts** — end or re-prompt the call if the caller goes quiet.
- **DTMF menu** — currently keypresses are logged but not acted on.
