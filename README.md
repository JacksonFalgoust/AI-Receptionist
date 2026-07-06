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
| `fillers.py` | Pure logic for the filler-phrase feature: `looks_like_question` decides whether a caller's utterance looks like a question or request that warrants a short filler phrase before the real reply; `pick` returns a random filler phrase from a list; `is_backchannel` decides whether an utterance (e.g. "ok", "yeah") is pure acknowledgment noise that should never get a guide reply. |
| `barge_in.py` | Pure logic for selective barge-in: `should_interrupt` decides whether a caller's utterance heard mid-reply (a stop/wait phrase, or a new question) should cancel the in-flight reply and start a fresh one. |
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
4. On each `prompt`, if no reply is currently streaming, `/ws` sends the
   running chat history to the GuideAnts guide (`guide_client.stream_reply`)
   and streams the reply back to Twilio as it's generated:
   ```json
   {"type": "text", "token": "Hello", "last": false}
   ...
   {"type": "text", "token": "", "last": true}
   ```
   Twilio starts speaking tokens as they arrive, so the caller doesn't wait for
   the full reply to be generated. If the caller's utterance looks like a
   question or request (see `fillers.py`), a short filler phrase (e.g. "Let me
   look that up for you.") is spoken first, before the real reply, to mask
   GuideAnts lookup latency.
5. If a `prompt` arrives *while* a reply is already streaming, Twilio does not
   stop or pause TTS on its own (`interruptible="none"`) — but this app does
   act on it if it's a stop/wait phrase ("stop", "wait", "hold on", ...) or a
   new question: the in-flight reply is cancelled and a fresh reply starts
   immediately for what the caller just said, cutting over playback via
   Conversation Relay's `preemptible` flag. Anything else said mid-reply
   (statements, backchannel, noise) is just logged and the current reply
   keeps playing to the end — see [ARCHITECTURE.md](ARCHITECTURE.md) for the
   full model and why.
6. Speech-to-text can finish transcribing a short utterance like "ok" *after*
   the reply has already finished playing, so it wouldn't be caught by the
   "already streaming" case above. `fillers.is_backchannel()` catches this
   too: pure acknowledgments ("ok", "okay", "yeah", "mmhmm", "got it", ...)
   are recorded into history but never trigger a guide reply, whether they
   arrive mid-reply or just after.

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
