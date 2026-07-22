# Voice Receptionist — Twilio Conversation Relay × GuideAnts

A phone-based AI receptionist demo. A caller dials a Twilio number; **Twilio
Conversation Relay** handles speech-to-text and text-to-speech and streams the
conversation over a WebSocket to this middleware; the middleware forwards the
caller's words to a **GuideAnts** guide and sends the guide's reply back to
Twilio, which speaks it to the caller.

```
Caller ⇄ Twilio number ⇄ Conversation Relay ⇄ this app (/twiml, /ws) ⇄ GuideAnts guide
```

## What's in this project

| File | Purpose |
|---|---|
| `app.py` | FastAPI server: `POST /twiml` returns the TwiML that opens the relay; `WS /ws` is the Conversation Relay message loop. |
| `guide_client.py` | Fetches replies from the GuideAnts guide using the `openai` SDK pointed at GuideAnts' OpenAI-compatible Responses endpoint. Every turn streams, including the first — the conversation id is captured directly off the stream (see below). |
| `fillers.py` | Pure logic for the filler-phrase feature: `looks_like_question` decides whether a caller's utterance looks like a question or request that warrants a short filler phrase before the real reply; `pick` returns a random filler phrase from a list; `is_backchannel` decides whether an utterance (e.g. "ok", "yeah") is pure acknowledgment noise that should never get a guide reply. |
| `barge_in.py` | Pure logic for selective barge-in: `should_interrupt` decides whether a caller's utterance heard mid-reply (a stop/wait phrase, or a new question) should cancel the in-flight reply; a stop/wait phrase then gets a local acknowledgment, a new question starts a fresh reply. |
| `speech_timing.py` | Pure logic: `estimate_seconds` estimates how long Twilio's TTS will take to speak a given text, from its word count — the fallback pacing signal when Twilio's speaker events aren't available. |
| `speaker_events.py` | Pure logic: `classify` recognizes Twilio's speaker-event messages (`agentSpeaking`/`clientSpeaking` start/stop) — the agent-stopped event is the real "reply finished playing" signal. |
| `config.py` | Loads settings from `.env`. |
| `.env.example` | Template for required configuration — copy to `.env`. |
| `reservations_api.py` | FastAPI router: `/api/reservations/*` + `/api/booqable/ping`, the tool surface GuideAnts calls to check availability and book rentals. See "Reservation API" below. |
| `reservations.py` | Booqable business logic (catalog, availability, create/cancel order) behind `reservations_api.py`. |
| `booqable_client.py` | Thin async HTTP client for Booqable's JSON:API v4, Bearer-token auth. |

All of the receptionist's actual knowledge/behavior (business hours, services,
tone, FAQs, etc.) lives in the **guide's instructions inside GuideAnts**, not in
this code. This app is just the phone/WebSocket bridge.

## How the call flow works

1. Twilio receives a call and POSTs to `/twiml`.
2. `/twiml` returns:
   ```xml
   <Response>
     <Connect>
       <ConversationRelay url="wss://<your-host>/ws" welcomeGreeting="..." .../>
     </Connect>
   </Response>
   ```
3. Twilio opens a WebSocket to `/ws` and sends JSON messages:
   - `setup` — call metadata (callSid, from, to)
   - `prompt` — `voicePrompt` holds the caller's transcribed speech; this
     arrives for normal turns *and* for caller speech heard while the agent is
     still talking (`report_input_during_agent_speech="speech"`)
   - `interrupt` — not expected in this app's configuration
     (`interruptible="none"` means Twilio never pauses/stops TTS on caller
     speech); logged if it ever arrives
   - `dtmf` — caller pressed a key
   - `error` — Conversation Relay reported a problem
   - speaker events (`events="speaker-events"`) — notifications that the
     agent or caller started/stopped speaking; the agent-stopped event is
     how the app knows a reply actually finished playing (with a word-count
     estimate as fallback and ceiling — see `speech_timing.py`), and the
     client started/stopped events are how it knows a caller who paused
     briefly has resumed talking (see step 4)
4. Twilio finalizes a `prompt` at each pause in caller speech, so one spoken
   turn can arrive as several prompts. On each `prompt`, if no reply is
   currently in flight, `/ws` buffers the text and commits it as the
   caller's turn only after `TURN_PAUSE_SECONDS` (default 0.5s) of further
   silence — if a clientSpeaking-started event arrives first, the caller
   just took a breath mid-sentence, and the continuation is merged into the
   same turn instead of the first half being answered alone. The committed
   turn is sent as just the caller's latest utterance to the GuideAnts guide
   (`guide_client.stream_reply`) — never a resent transcript. Every turn,
   including the call's first, streams the reply token-by-token; the
   `conversation` id this app holds for the rest of the call is captured
   directly off the stream's `response.created`/`response.completed` events
   the first time a turn doesn't already have one, and passed back on every
   later turn so GuideAnts continues the same server-side conversation. Each
   token is forwarded to Twilio as its own frame as it arrives:
   ```json
   {"type": "text", "token": "Hello ", "last": false}
   {"type": "text", "token": "there!", "last": false}
   {"type": "text", "token": "", "last": true}
   ```
   A short filler phrase (e.g. "Let me look that up for you.") is spoken
   first, before the real reply, whenever the caller's utterance looks like a
   question or request (see `fillers.py`) *and* GuideAnts hasn't replied
   within `FILLER_DELAY_SECONDS` (default 1s) — this masks GuideAnts lookup
   latency without adding a filler to fast replies, and covers the gap before
   the first token arrives on any turn, including the first. (If replies seem
   to arrive all at once instead of incrementally, the GuideAnts container
   image is likely outdated — see the streaming caveat in ARCHITECTURE.md,
   and `check_streaming.py` to verify.)
5. If a `prompt` arrives *while* a reply is already streaming, Twilio does not
   stop or pause TTS on its own (`interruptible="none"`) — but this app does
   act on it if it's a stop/wait phrase ("stop", "wait", "hold on", ...) or a
   new question, cutting over playback via Conversation Relay's `preemptible`
   flag either way. A stop/wait phrase gets a short local acknowledgment
   (e.g. "Okay.") and then silence — it's never sent to GuideAnts, so it cuts
   over immediately and doesn't depend on the guide replying briefly. A new
   question instead cancels the in-flight reply and starts a fresh one
   immediately for what the caller just said. Anything else said mid-reply
   (statements, backchannel, noise) is just logged and the current reply
   keeps playing to the end — see [ARCHITECTURE.md](ARCHITECTURE.md) for the
   full model and why.
6. Speech-to-text can finish transcribing a short utterance like "ok" *after*
   the reply has already finished playing, so it wouldn't be caught by the
   "already streaming" case above. `fillers.is_backchannel()` catches this
   too: pure acknowledgments ("ok", "okay", "yeah", "mmhmm", "got it", ...)
   are just logged and never trigger a guide reply, whether they arrive
   mid-reply or just after — they're genuinely noise, never sent to
   GuideAnts, like fillers and other non-trigger mid-reply speech.

## Reservation API

Separate from the Twilio call bridge above, this app also serves the Booqable
reservation surface the GuideAnts receptionist guide calls as a tool (via its
imported OpenAPI schema, `guide-demo/booqable-reservations-openapi.json`) —
so one running app (`uvicorn app:app --port 8080`) is enough for both the
phone call and live availability/booking, instead of running a second
project.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/booqable/ping` | Connectivity check — confirms `BOOQABLE_API_KEY`/`BOOQABLE_COMPANY_URL` are correct. Unauthenticated. |
| GET | `/api/reservations/catalog` | Live rentable product list (name, `product_id`, price). |
| GET | `/api/reservations/availability` | Check stock for a product/date-range/quantity. |
| POST | `/api/reservations` | Find-or-create customer, create order, book items, and (by default) reserve it. |
| POST | `/api/reservations/{order_id}/cancel` | Cancel a reservation. |

The four `/api/reservations/*` routes require an `X-Api-Key` header matching
`RECEPTIONIST_API_KEY` — a secret distinct from `BOOQABLE_API_KEY`, since the
LLM should never see the real Booqable key. `reservations_api.py` wraps
`booqable_client.BooqableClient`/`reservations.py`'s find/check/book/reserve
workflow so GuideAnts never has to speak Booqable's JSON:API format directly.

## Setup

**See [SETUP.md](SETUP.md) for the complete, step-by-step guide** to getting
this running on your device — GuideAnts guide creation, installing
dependencies, `.env`, Twilio account/number configuration, tunneling, and
placing a call.

## Manual verification without a phone call

With the server running and `.env` pointed at a real published guide, confirm
GuideAnts is reachable directly. First turn, streaming (a current GuideAnts
build echoes the `conversation` id in the streamed events themselves):

```
curl -N http://localhost:5107/api/published/openai/<pubId>/v1/responses ^
  -H "Authorization: Bearer <key-or-anonymous>" -H "Content-Type: application/json" ^
  -d "{\"model\":\"<alias>\",\"input\":\"Hi, my name is Jackson. What are your hours?\",\"stream\":true}"
```

You should see a stream of `response.output_text.delta` events (`-N` disables
curl's output buffering so they print as they arrive); the `response.created`
and `response.completed` events both carry `"conversation": "conv_..."` —
copy that id. Then continue the same conversation, referencing a fact only
turn 1 mentioned:

```
curl -N http://localhost:5107/api/published/openai/<pubId>/v1/responses ^
  -H "Authorization: Bearer <key-or-anonymous>" -H "Content-Type: application/json" ^
  -d "{\"model\":\"<alias>\",\"input\":\"What did I say my name was?\",\"conversation\":\"conv_...\",\"stream\":true}"
```

The final answer should say "Jackson" — proof the conversation continued
server-side with no history resent. If both of these work, `/ws` will work
too. (If your GuideAnts build predates the streamed `conversation` field, the
first curl above will stream fine but omit that field from the JSON payloads
— in that case, drop `"stream":true` from the first call only to get the id
from the non-streaming response body instead, same as this app's
`stream_missing_conversation` fallback in `guide_client.py`.)
