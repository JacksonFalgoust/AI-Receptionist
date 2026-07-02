# Voice Receptionist — Twilio Conversation Relay × GuideAnts

A phone-based AI receptionist demo. A caller dials a Twilio number; **Twilio
Conversation Relay** handles speech-to-text and text-to-speech and streams the
conversation over a WebSocket to this middleware; the middleware forwards the
caller's words to a **GuideAnts** guide and streams the guide's reply back to
Twilio, which speaks it to the caller.

```
Caller ⇄ Twilio number ⇄ Conversation Relay ⇄ this app (/twiml, /ws) ⇄ GuideAnts guide
```

## What's in this project

| File | Purpose |
|---|---|
| `app.py` | FastAPI server: `POST /twiml` returns the TwiML that opens the relay; `WS /ws` is the Conversation Relay message loop. |
| `guide_client.py` | Streams replies from the GuideAnts guide using the `openai` SDK pointed at GuideAnts' OpenAI-compatible endpoint. |
| `barge_in.py` | Pure logic for selective barge-in: decides whether a caller's utterance should stop the AI's reply (a stop command or a question) or let it resume (a filler, statement, or noise). |
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
   - `prompt` — `voicePrompt` holds the caller's transcribed speech
   - `interrupt` — caller spoke over the AI; Twilio pauses TTS immediately and reports what they'd heard so far via `utteranceUntilInterrupt`
   - `dtmf` — caller pressed a key
   - `error` — Conversation Relay reported a problem
4. On each `prompt`, `/ws` sends the running chat history to the GuideAnts
   guide (`guide_client.stream_reply`) and streams the reply back to Twilio as
   it's generated:
   ```json
   {"type": "text", "token": "Hello", "last": false}
   ...
   {"type": "text", "token": "", "last": true}
   ```
   Twilio starts speaking tokens as they arrive, so the caller doesn't wait for
   the full reply to be generated.
5. On `interrupt`, the app pauses the reply rather than stopping it, and waits
   for the caller's transcribed words (the next `prompt`) to decide what to
   do: a stop command ("stop", "hold on", ...) or a question actually cancels
   the reply and starts a fresh one for the new words; anything else (a
   filler like "uh-huh", a statement, background noise) resumes the paused
   reply right where Twilio left off. If no `prompt` follows within a couple
   of seconds (e.g. a cough), the app resumes on its own. See
   [ARCHITECTURE.md](ARCHITECTURE.md) for the full state machine.

## Setup

**See [SETUP.md](SETUP.md) for the complete, step-by-step guide** to getting
this running on your device — GuideAnts guide creation, installing
dependencies, `.env`, Twilio account/number configuration, tunneling, and
placing a call.

## Manual verification without a phone call

With the server running and `.env` pointed at a real published guide, confirm
GuideAnts is reachable directly:

```
curl -N http://localhost:5107/api/published/openai/<pubId>/v1/chat/completions ^
  -H "Authorization: Bearer <key-or-anonymous>" -H "Content-Type: application/json" ^
  -d "{\"model\":\"<alias>\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"stream\":true}"
```

You should see `data:` chunks containing `choices[].delta.content`. If this
works, `/ws` will work too.
