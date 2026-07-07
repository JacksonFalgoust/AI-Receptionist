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
| `guide_client.py` | Fetches replies from the GuideAnts guide using the `openai` SDK pointed at GuideAnts' OpenAI-compatible endpoint (non-streaming — see below). |
| `fillers.py` | Pure logic for the filler-phrase feature: `looks_like_question` decides whether a caller's utterance looks like a question or request that warrants a short filler phrase before the real reply; `pick` returns a random filler phrase from a list; `is_backchannel` decides whether an utterance (e.g. "ok", "yeah") is pure acknowledgment noise that should never get a guide reply. |
| `barge_in.py` | Pure logic for selective barge-in: `should_interrupt` decides whether a caller's utterance heard mid-reply (a stop/wait phrase, or a new question) should cancel the in-flight reply; a stop/wait phrase then gets a local acknowledgment, a new question starts a fresh reply. |
| `speech_timing.py` | Pure logic: `estimate_seconds` estimates how long Twilio's TTS will take to speak a given text, from its word count. |
| `config.py` | Loads settings from `.env`. |
| `.env.example` | Template for required configuration — copy to `.env`. |

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
4. On each `prompt`, if no reply is currently in flight, `/ws` sends the
   running chat history to the GuideAnts guide (`guide_client.stream_reply`),
   which makes a single non-streaming call (GuideAnts' chat-completions
   endpoint rejects `stream: true`) and sends the whole reply to Twilio as one
   frame:
   ```json
   {"type": "text", "token": "Hello there!", "last": false}
   {"type": "text", "token": "", "last": true}
   ```
   Since the reply arrives all at once rather than incrementally, a short
   filler phrase (e.g. "Let me look that up for you.") is spoken first, before
   the real reply, whenever the caller's utterance looks like a question or
   request (see `fillers.py`) — this is what masks GuideAnts lookup latency.
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
   mid-reply or just after — like fillers and other non-trigger mid-reply
   speech, they're never added to the conversation history either.

## Setup

**See [SETUP.md](SETUP.md) for the complete, step-by-step guide** to getting
this running on your device — GuideAnts guide creation, installing
dependencies, `.env`, Twilio account/number configuration, tunneling, and
placing a call.

## Manual verification without a phone call

With the server running and `.env` pointed at a real published guide, confirm
GuideAnts is reachable directly:

```
curl http://localhost:5107/api/published/openai/<pubId>/v1/chat/completions ^
  -H "Authorization: Bearer <key-or-anonymous>" -H "Content-Type: application/json" ^
  -d "{\"model\":\"<alias>\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}"
```

You should see a single JSON object with `choices[0].message.content` (don't
pass `"stream":true` — this endpoint is non-streaming only and rejects it with
an `unsupported_feature` error). If this works, `/ws` will work too.
