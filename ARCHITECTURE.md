# Architecture — how the code and endpoints work

This is the deep-dive companion to [README.md](README.md) (overview) and
[SETUP.md](SETUP.md) (complete setup steps, including manual Twilio/GuideAnts
config). It explains what each file
does, the exact wire protocol on every endpoint, and how a call flows through
the system end to end.

The whole app is four files. There is no database, no session store outside
memory, and no business logic — this is purely a **protocol bridge** between
Twilio Conversation Relay's WebSocket protocol and GuideAnts' OpenAI-compatible
chat API. `barge_in.py` is the one exception to "no business logic": it holds
the pure, I/O-free heuristics that decide how the app reacts to a caller
talking over the AI.

```
                    POST /twiml (TwiML)            WS /ws (JSON frames)
Caller ⇄ Twilio ⇄ ───────────────────── ⇄ app.py ⇄ ───────────────────── ⇄ Twilio Conversation Relay
                                            │
                                            │ HTTPS, OpenAI SDK
                                            ▼
                              GuideAnts POST /api/published/openai/{pubId}/v1/chat/completions
                                            │
                                            ▼
                                     Published guide (LLM)
```

## File map

| File | Role |
|---|---|
| [config.py](config.py) | Reads all settings from environment / `.env`, no other file touches `os.environ`. |
| [guide_client.py](guide_client.py) | Thin wrapper around the `openai` SDK pointed at GuideAnts; exposes one function, `stream_reply`. |
| [barge_in.py](barge_in.py) | Pure functions used by `app.py` to handle selective barge-in: `should_stop_reply` classifies a caller utterance as a stop command/question (cancel the reply) vs. filler/statement/noise (resume it), and `split_spoken` diffs already-sent text against what Twilio reports it actually played. No I/O, no Twilio/GuideAnts knowledge — this is why it's unit-tested directly in `test_barge_in.py`. |
| [app.py](app.py) | FastAPI app with the two endpoints Twilio talks to: `POST /twiml` and `WS /ws`. All call-handling logic lives here. |

---

## config.py

Loads `.env` via `python-dotenv` at import time, then exposes plain module-level
constants. Nothing else in the codebase reads `os.environ` directly — every
other file imports `config` and reads attributes off it. Defaults (used if the
env var is unset):

| Constant | Env var | Default | Used by |
|---|---|---|---|
| `GUIDEANTS_BASE_URL` | `GUIDEANTS_BASE_URL` | `http://localhost:5107` | `guide_client.py` — base URL of the GuideAnts backend |
| `GUIDEANTS_PUB_ID` | `GUIDEANTS_PUB_ID` | `""` | `guide_client.py` — published guide GUID, part of the URL path |
| `GUIDEANTS_API_KEY` | `GUIDEANTS_API_KEY` | `"anonymous"` | `guide_client.py` — sent as `Authorization: Bearer <key>` |
| `GUIDEANTS_MODEL` | `GUIDEANTS_MODEL` | `"guide"` | `guide_client.py` — `model` field in the chat-completions request (fixed alias, not a real model name) |
| `WELCOME_GREETING` | `WELCOME_GREETING` | `"Thanks for calling! How can I help you today?"` | `app.py` — spoken by Twilio before any WS traffic happens |
| `TWILIO_AUTH_TOKEN` | `TWILIO_AUTH_TOKEN` | `""` | not currently used in code — reserved for optional `X-Twilio-Signature` validation (not implemented, see SETUP.md) |
| `PORT` | `PORT` | `8080` | not read by `app.py` itself — `uvicorn` is started with `--port` on the command line; this constant is unused today |
| `BARGE_IN_RESUME_TIMEOUT_S` | `BARGE_IN_RESUME_TIMEOUT_S` | `2.5` | `app.py` — seconds to wait after an `interrupt` for a follow-up `prompt` before auto-resuming the paused reply on its own (handles a cough or silence) |
| `BARGE_IN_EXTRA_STOP_PHRASES` | `BARGE_IN_EXTRA_STOP_PHRASES` | `""` (empty) | `barge_in.py` (via `app.py`) — comma-separated phrases, on top of the built-in `barge_in.STOP_PHRASES`, that should cancel the in-flight reply |

If `GUIDEANTS_PUB_ID` is empty when the guide client is first used, `guide_client.py` raises a `RuntimeError` telling the user to fill in `.env` — this is the only config validation in the app.

---

## guide_client.py

Exposes exactly one public function: `stream_reply(messages) -> AsyncIterator[str]`.

- `_get_client()` lazily builds a module-level singleton `AsyncOpenAI` client the first time it's needed, pointed at:
  `{GUIDEANTS_BASE_URL}/api/published/openai/{GUIDEANTS_PUB_ID}/v1`
  This is GuideAnts' OpenAI-compatible endpoint, **not** the OpenAI API — same request/response shape, different backend. Because it's a singleton, the client (and its HTTP connection pool) is reused across every call/WS connection the app handles.
- `stream_reply(messages)` calls `client.chat.completions.create(model=..., messages=messages, stream=True)` and yields each non-empty `chunk.choices[0].delta.content` string as it arrives. Empty/keepalive chunks (`chunk.choices` empty, or `delta.content` falsy) are silently skipped.
- `messages` is the **full chat history** (list of `{"role": ..., "content": ...}` dicts) — GuideAnts is stateless from this client's point of view per the wire protocol used here (see below), so `app.py` is responsible for holding and resending the whole conversation on every turn.

### Why this endpoint and not `/invoke`

GuideAnts has multiple ways to talk to a published guide. This project deliberately uses the OpenAI-wire chat-completions endpoint instead of the native `/invoke` endpoint, because `/invoke` starts a brand-new conversation on every call with no memory across turns — unworkable for a receptionist that needs to remember what the caller already said earlier in the same phone call. The wire endpoint lets the client hold the message array and resend it each turn, giving multi-turn memory for free via a standard SDK.

---

## app.py

### `POST /twiml`

Called once by Twilio the moment a call comes in (this URL is configured on the Twilio phone number as its "A call comes in" webhook — see SETUP.md).

- Reads the `Host` header from the incoming request so the WebSocket URL it returns always points back at wherever this app is actually reachable (no hardcoded domain).
- Builds and returns TwiML:
  ```xml
  <Response>
    <Connect>
      <ConversationRelay
        url="wss://<host>/ws"
        welcomeGreeting="<WELCOME_GREETING>"
        ttsProvider="ElevenLabs"
        transcriptionProvider="Deepgram"
        interruptible="speech"
        reportInputDuringAgentSpeech="speech" />
    </Connect>
  </Response>
  ```
- `interruptible="speech"` + `reportInputDuringAgentSpeech="speech"` together enable **barge-in** at the Twilio layer: the instant Twilio hears caller speech it pauses TTS playback and reports it via an `interrupt` WS message, followed by a `prompt` once transcription finishes. This Twilio-side pause is unconditional — it happens on any caller speech, every time. What this app does with that pause (actually stop the reply, or let it resume) is a decision made in `app.py`/`barge_in.py`; see "Concurrency / barge-in model" below.
- Response content type is `application/xml`. No request body is read — everything needed comes from the `Host` header and this app's own config.

### `WS /ws`

Twilio opens exactly one WebSocket connection here per call, immediately after `/twiml` returns, and keeps it open for the life of the call. All messages are JSON text frames.

**Per-connection state** (`CallState`, one instance per call — all local to the WS handler closure; nothing is shared across calls, nothing persists after disconnect):
- `messages: list[dict]` — the full running chat history sent to GuideAnts on every turn.
- `task` — the `asyncio.Task` currently generating/streaming a reply, if any.
- `gate: asyncio.Event` — set = the reply task is flowing, cleared = paused mid barge-in; `respond_to()` awaits this before every send.
- `cycle_text` / `cycle_base` — text handed to Twilio so far this talk cycle, and text confirmed spoken in earlier segments of the same reply; together they let a barge-in figure out what was actually heard.
- `pending` — the current `PendingBargeIn` (an unresolved `interrupt` awaiting a follow-up `prompt`), if any.
- `resume_timer` — the `asyncio.Task` running the auto-resume countdown after an `interrupt`, if any.

**Inbound message types** (sent by Twilio Conversation Relay):

| `type` | Key fields | Handling |
|---|---|---|
| `setup` | `callSid`, `from`, `to` | Logged only; no state change. First message on every connection. |
| `prompt` | `voicePrompt` (caller's transcribed speech) | If it resolves a pending `interrupt`, classifies the utterance to decide whether to stop the paused reply or resume it. Otherwise starts (or, if a stop-worthy prompt arrives mid-reply with nothing paused, restarts) a reply normally. See "Concurrency / barge-in model" below for the full logic. |
| `interrupt` | `utteranceUntilInterrupt` (what the caller actually heard before interrupting) | **Pauses** (does not cancel) the in-flight reply and starts an auto-resume timer, pending the caller's next `prompt`. See "Concurrency / barge-in model" below for the full logic. |
| `dtmf` | `digit` | Logged only — not acted on (no IVR menu implemented; see SETUP.md's "not implemented" list). |
| `error` | `description` | Logged as an error. Connection is not closed by this app. |
| anything else | — | Logged as a warning, ignored. |

Non-JSON frames are logged and skipped rather than crashing the loop.

**Outbound message shape** (sent by this app to Twilio), streamed token-by-token as GuideAnts generates them:
```json
{"type": "text", "token": "Hello", "last": false}
{"type": "text", "token": " there!", "last": false}
{"type": "text", "token": "", "last": true}
```
Twilio starts speaking (TTS) as tokens arrive rather than waiting for the full reply — this is what makes the reply feel low-latency on a phone call.

### `start_reply()` / `respond_to()` — the reply pipeline

`start_reply(user_text)` appends the caller's utterance to `messages`, resets `cycle_text`/`cycle_base` for the new talk cycle, opens the gate, and spawns `respond_to()` as a cancellable `asyncio.Task`:

1. Call `guide_client.stream_reply(messages)` and, for each delta: wait on `st.gate` (this is where the task blocks while paused by a barge-in), forward the delta to the WS as a `{"type": "text", ...}` frame, and accumulate it into both the reply text and `st.cycle_text`.
2. Wait on the gate once more, then send a final `{"token": "", "last": true}` frame to signal end-of-turn to Twilio.
3. Append the full assistant reply to `messages` so the next turn has it as context.
4. **On cancellation** (`asyncio.CancelledError`, raised only by `cancel_task()` — called from `stop_and_restart()` when a barge-in resolves to a stop command/question, from the plain-prompt path when a stop-worthy prompt arrives mid-reply with no pending barge-in, or on `WebSocketDisconnect`): re-raises without touching `messages` itself; whichever caller triggered the cancellation is responsible for recording the correct history (`stop_and_restart()` writes `cycle_base + heard`; the plain-prompt path appends `cycle_base + cycle_text`).
5. **On any other exception** (e.g. GuideAnts unreachable, HTTP error): logs the full traceback and sends a single spoken fallback line (`"Sorry, I'm having trouble right now."`) as a `last: true` frame, rather than leaving the caller in silence or crashing the WS loop.

Note that a plain `interrupt` never cancels this task by itself — it only clears `st.gate`, which the task is already cooperatively waiting on between sends.

### Concurrency / barge-in model

Only one reply task runs at a time per call, but an `interrupt` no longer cancels it outright — Twilio pausing TTS on caller speech doesn't by itself mean the reply should stop. Instead, `interrupt` **pauses** the reply and the caller's next `prompt` **classifies** what to do with it:

1. **Pause.** On `interrupt`, `st.gate` (set = flowing, cleared = paused) is cleared, so `respond_to()` blocks in place at its next `gate.wait()` — no text or task state is lost or cancelled. The app records `st.pending = PendingBargeIn(heard=utteranceUntilInterrupt, task_was_done=...)` and starts a `config.BARGE_IN_RESUME_TIMEOUT_S`-second (default 2.5s) auto-resume timer via `restart_resume_timer()`.
2. **Classify.** The caller's transcribed speech then arrives as `prompt`. With `st.pending` set, `barge_in.should_stop_reply(text, config.BARGE_IN_EXTRA_STOP_PHRASES)` decides:
   - **Stop** (a phrase from `barge_in.STOP_PHRASES`/`BARGE_IN_EXTRA_STOP_PHRASES`, or a question — ends in `?` or starts with an interrogative/auxiliary word per `barge_in.QUESTION_STARTERS`) → `stop_and_restart()`: the paused task is actually cancelled, `messages` is corrected to reflect only what was truly heard (`cycle_base + pend.heard`), and a fresh reply is started for the new utterance.
   - **Resume** (anything else — filler like "uh-huh"/"okay", a statement, background noise) → `resume()`: `barge_in.split_spoken()` diffs `cycle_text` against `utteranceUntilInterrupt` to find the tail Twilio discarded, that remainder is re-sent, then the gate reopens so playback continues where it left off instead of repeating from the start. The filler utterance itself is never added to `messages`. (If the reply task had already finished streaming before the barge — TTS was just still catching up — the remainder starts a fresh talk cycle instead of resuming an in-flight one.)
3. **Auto-resume.** If no `prompt` follows an `interrupt` within `BARGE_IN_RESUME_TIMEOUT_S` seconds (e.g. a cough, or silence that doesn't transcribe to anything), `auto_resume()` fires on its own and calls `resume()` exactly as above.

A caller can also barge into the welcome greeting itself, which Twilio speaks directly from the TwiML `welcomeGreeting` attribute and which never crosses the WebSocket. This falls out of the same machinery for free: `st.cycle_text` is seeded with `config.WELCOME_GREETING` when the WS connects, so an `interrupt` during the greeting has real text to diff against in `split_spoken()`.

Known cosmetic limitation: a token already in flight to Twilio at the exact instant of an `interrupt` can be spoken once immediately and then repeated at the start of the resumed remainder (one stray word). This is self-healing on the next sentence and not worth engineering around.

This is why per-call state lives in a `CallState` dataclass (`st`) rather than plain closure variables — `gate`, `pending`, `resume_timer`, `cycle_text`/`cycle_base`, and `task` are all read and mutated from multiple coroutines (the message loop, `respond_to()`, and the resume timer) and need to be shared by reference.

On `WebSocketDisconnect`, the resume timer is cancelled, any in-flight task is cancelled, and the loop exits — nothing is persisted, so a dropped call simply forgets the conversation.

---

## The GuideAnts endpoint this app depends on

`guide_client.py` calls **`POST {GUIDEANTS_BASE_URL}/api/published/openai/{GUIDEANTS_PUB_ID}/v1/chat/completions`** — GuideAnts' OpenAI-wire-compatible endpoint (implemented server-side in `PublishedOpenAiChatWireHandler.PostChatCompletionsAsync`, routed via `PublishedOpenAiWireEndpoints`, GuideAnts repo). Relevant contract details:

- **Auth**: `Authorization: Bearer <GUIDEANTS_API_KEY>` header (the `openai` SDK adds this automatically from `api_key=`). GuideAnts also accepts `x-guideants-apikey` or anonymous access, depending on how the published guide's auth mode was configured (see SETUP.md step 1.4).
- **Request body**: standard OpenAI chat-completions shape — `{"model": "guide", "messages": [...], "stream": true}`. `model` must match one of the alias `id`s returned by `GET .../v1/models` (normally the fixed alias `"guide"` for the chat-completions endpoint, not the real underlying model name).
- **Statelessness**: this endpoint does not remember prior turns on its own from a bare `messages` array the way `/invoke` implicitly manages a conversation — GuideAnts derives/resumes a conversation from the message history it's given, but this client's contract is "send the full transcript every time," which is exactly what `app.py`'s `messages` list does.
- **Streaming response**: with `stream: true`, GuideAnts returns `text/event-stream` SSE chunks, each an OpenAI-shaped JSON object under `choices[0].delta.content`. `guide_client.stream_reply` reads these via the `openai` SDK's async streaming iterator and yields just the text deltas.
- **Non-streaming response** (not used by this app, but supported by the same endpoint): a single JSON object with `choices[0].message.content`, `finish_reason`, and `usage`.
- **Tool calls**: the wire endpoint also supports OpenAI-style `tools`/`tool_calls` (client-side tool execution) — unused here since the receptionist guide doesn't define any tools today, but the endpoint would return `finish_reason: "tool_calls"` if it did.
- **Errors**: e.g. `403 endpoint_disabled` if the guide's "Enable Wire API" / "Chat Completions" toggle isn't turned on in the Publish dialog (see SETUP.md step 1.5).

`GET {GUIDEANTS_BASE_URL}/api/published/openai/{pubId}/v1/models` is the companion read-only endpoint used manually (not by this app's code) to discover the valid `model` alias values before filling in `.env`.

---

## Full call sequence

1. Caller dials the Twilio number.
2. Twilio POSTs to `/twiml`. App returns `<Connect><ConversationRelay url="wss://.../ws" .../></Connect>`.
3. Twilio opens the WS, speaks `WELCOME_GREETING` to the caller immediately (handled entirely by Twilio, not by this app), then sends `setup`.
4. Caller speaks. Twilio transcribes it and sends `prompt` with `voicePrompt`.
5. `app.py` appends it to `messages`, calls `guide_client.stream_reply`, and streams the reply back as `text` frames; Twilio speaks it via TTS as tokens arrive.
6. If the caller talks over the reply, Twilio pauses TTS instantly and sends `interrupt` with `utteranceUntilInterrupt`; the app pauses the reply task (it does not cancel it yet) and starts a short auto-resume timer.
7. The caller's utterance then arrives as `prompt`. `barge_in.should_stop_reply()` decides: a stop command or question actually cancels the paused reply, corrects the history, and starts a fresh reply (steps 4–5 repeat for it); anything else (filler, statement, noise) resumes the paused reply from where Twilio left off. If no `prompt` arrives in time, the app resumes on its own.
8. Repeat from step 4 for each new turn — `messages` grows for the life of the call.
9. Caller hangs up → WS disconnects → in-flight task and any pending resume timer are cancelled, connection state (and the entire conversation) is discarded.

## Known gaps (intentionally out of scope today)

From SETUP.md's "optional hardening" list — not implemented, not required for the demo to work:
- No `X-Twilio-Signature` validation on `/twiml` (any request to that URL is trusted).
- No handling of Twilio `end`/handoff messages (e.g. transfer to a human).
- No silence timeout / re-prompt if the caller goes quiet.
- `dtmf` digits are logged but never acted on — no keypad menu.
