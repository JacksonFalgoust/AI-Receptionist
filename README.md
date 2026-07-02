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
   - `interrupt` — caller spoke over the AI; `utteranceUntilInterrupt` is what they actually heard
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
5. On `interrupt`, the in-flight reply is cancelled and the conversation
   history is corrected to only what the caller actually heard, so the next
   guide reply has accurate context.

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
