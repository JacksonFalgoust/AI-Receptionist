# Architecture — how the code and endpoints work

This is the deep-dive companion to [README.md](README.md) (overview) and
[SETUP.md](SETUP.md) (complete setup steps, including manual Twilio/GuideAnts
config). It explains what each file
does, the exact wire protocol on every endpoint, and how a call flows through
the system end to end.

The whole app is three files. There is no database, no session store outside
memory, and no business logic — this is purely a **protocol bridge** between
Twilio Conversation Relay's WebSocket protocol and GuideAnts' OpenAI-compatible
chat API.

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
- `interruptible="speech"` + `reportInputDuringAgentSpeech="speech"` together enable **barge-in**: the caller can talk over the AI and Twilio will report that speech via an `interrupt` WS message (see below) instead of ignoring it.
- Response content type is `application/xml`. No request body is read — everything needed comes from the `Host` header and this app's own config.

### `WS /ws`

Twilio opens exactly one WebSocket connection here per call, immediately after `/twiml` returns, and keeps it open for the life of the call. All messages are JSON text frames.

**Per-connection state** (all local to the WS handler closure — nothing is shared across calls, nothing persists after disconnect):
- `messages: list[dict]` — the full running chat history sent to GuideAnts on every turn.
- `state["task"]` — the `asyncio.Task` currently generating/streaming a reply, if any.

**Inbound message types** (sent by Twilio Conversation Relay):

| `type` | Key fields | Handling |
|---|---|---|
| `setup` | `callSid`, `from`, `to` | Logged only; no state change. First message on every connection. |
| `prompt` | `voicePrompt` (caller's transcribed speech) | Cancels any in-flight reply task, appends `{"role": "user", ...}` to `messages`, spawns a new `respond_to()` task that streams the guide's reply back. |
| `interrupt` | `utteranceUntilInterrupt` (what the caller actually heard before interrupting) | Cancels the in-flight reply task. Rewrites the last assistant message in `messages` to `utteranceUntilInterrupt` (or appends it) so the history reflects only what was truly spoken, not the full reply that was cut off. |
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

### `respond_to(user_text)` — the reply pipeline

This is the core per-turn coroutine, run as a cancellable `asyncio.Task`:

1. Append the caller's utterance to `messages`.
2. Call `guide_client.stream_reply(messages)` and forward every delta to the WS as a `{"type": "text", ...}` frame, accumulating the full reply text.
3. Send a final `{"token": "", "last": true}` frame to signal end-of-turn to Twilio.
4. Append the full assistant reply to `messages` so the next turn has it as context.
5. **On cancellation** (`asyncio.CancelledError`, raised when a new `prompt` or an `interrupt` arrives mid-reply): whatever partial reply text had been generated so far is still appended to `messages` before re-raising, so history stays roughly in sync. If the event was an `interrupt`, the `interrupt` handler then overwrites that same message with the more accurate `utteranceUntilInterrupt` text Twilio provides.
6. **On any other exception** (e.g. GuideAnts unreachable, HTTP error): logs the full traceback and sends a single spoken fallback line (`"Sorry, I'm having trouble right now."`) as a `last: true` frame, rather than leaving the caller in silence or crashing the WS loop.

### Concurrency / barge-in model

Only one reply task runs at a time per call. Both `prompt` (caller spoke again before the AI finished) and `interrupt` (caller explicitly barged in) cancel whatever task is currently running before starting/handling the next thing. This is why `state` is a mutable dict rather than a plain variable — it's captured by reference inside the `respond_to` closure and read/written from the outer message loop.

On `WebSocketDisconnect`, any in-flight task is cancelled and the loop exits — nothing is persisted, so a dropped call simply forgets the conversation.

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
6. If the caller talks over the reply, Twilio sends `interrupt` with `utteranceUntilInterrupt`; the in-flight task is cancelled and history is corrected.
7. Repeat from step 4 for each new turn — `messages` grows for the life of the call.
8. Caller hangs up → WS disconnects → in-flight task cancelled, connection state (and the entire conversation) is discarded.

## Known gaps (intentionally out of scope today)

From SETUP.md's "optional hardening" list — not implemented, not required for the demo to work:
- No `X-Twilio-Signature` validation on `/twiml` (any request to that URL is trusted).
- No handling of Twilio `end`/handoff messages (e.g. transfer to a human).
- No silence timeout / re-prompt if the caller goes quiet.
- `dtmf` digits are logged but never acted on — no keypad menu.
