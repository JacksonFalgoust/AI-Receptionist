# Architecture — how the code and endpoints work

This is the deep-dive companion to [README.md](README.md) (overview) and
[SETUP.md](SETUP.md) (complete setup steps, including manual Twilio/GuideAnts
config). It explains what each file
does, the exact wire protocol on every endpoint, and how a call flows through
the system end to end.

There is no database, no session store outside memory — this is purely a
**protocol bridge** between Twilio Conversation Relay's WebSocket protocol
and GuideAnts' OpenAI-compatible chat API. `fillers.py` and `barge_in.py` are
the exceptions to "no business logic": pure, I/O-free heuristics that decide
whether a caller's utterance warrants a spoken filler phrase (`fillers.py`)
or should cancel and restart an in-flight reply (`barge_in.py`).

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
| [fillers.py](fillers.py) | Pure functions used by `app.py` to decide the filler-phrase behavior: `looks_like_question` classifies a caller utterance as question/request-like (warrants a filler) or not, `pick` returns a random filler phrase from a list, and `is_backchannel` classifies an utterance as pure acknowledgment noise (e.g. "ok", "yeah") that should never get a guide reply. No I/O, no Twilio/GuideAnts knowledge. |
| [barge_in.py](barge_in.py) | Pure functions used by `app.py` to decide selective barge-in: `is_stop_command` matches a caller utterance against a built-in stop/wait phrase list, and `should_interrupt` (= `is_stop_command` or `fillers.looks_like_question`) decides whether an utterance heard mid-reply should cancel and restart the in-flight reply. No I/O, no Twilio/GuideAnts knowledge — unit-tested directly in `test_barge_in.py`. |
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
| `FILLER_PHRASES` | `FILLER_PHRASES` | a built-in list of 6 phrases (e.g. `"Let me look that up for you."`) | `app.py` (via `fillers.pick`) — pool of filler phrases spoken before the real reply when the caller's utterance looks like a question/request. Pipe-separated (`\|`) in the env var, since phrases contain commas/periods; falls back to the built-in list if unset. |
| `EXTRA_BACKCHANNEL_PHRASES` | `EXTRA_BACKCHANNEL_PHRASES` | `[]` (empty) | `app.py` (via `fillers.is_backchannel`) — comma-separated phrases, on top of the built-in `fillers.BACKCHANNEL_PHRASES`, that count as pure acknowledgment noise and should never get a guide reply. |
| `EXTRA_STOP_PHRASES` | `EXTRA_STOP_PHRASES` | `[]` (empty) | `app.py` (via `barge_in.should_interrupt`) — comma-separated phrases, on top of the built-in `barge_in.STOP_PHRASES`, that also cancel and restart an in-flight reply when heard mid-reply. |

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
        interruptible="none"
        reportInputDuringAgentSpeech="speech" />
    </Connect>
  </Response>
  ```
- `interruptible="none"` + `reportInputDuringAgentSpeech="speech"` together mean Twilio itself never pauses or stops TTS playback because of caller speech, but caller speech heard during agent speech is still transcribed and delivered to this app as a `prompt` message (instead of the `interrupt` message Twilio would send under `interruptible="speech"`). What this app does with that reported speech — ignore it, or cancel and restart the reply for it — is a decision made in `app.py`/`fillers.py`/`barge_in.py`; see "Filler phrases and mid-reply speech" and "Selective barge-in" below.
- Response content type is `application/xml`. No request body is read — everything needed comes from the `Host` header and this app's own config.

### `WS /ws`

Twilio opens exactly one WebSocket connection here per call, immediately after `/twiml` returns, and keeps it open for the life of the call. All messages are JSON text frames.

**Per-connection state** (`CallState`, one instance per call — all local to the WS handler closure; nothing is shared across calls, nothing persists after disconnect):
- `messages: list[dict]` — the full running chat history sent to GuideAnts on every turn.
- `task` — the `asyncio.Task` currently generating/streaming a reply, if any; also doubles as the "is a reply active right now" flag (`st.task and not st.task.done()`).
- `partial_reply: str` — the real (GuideAnts-sourced) reply text streamed so far in the current turn, never including the filler. Reset to `""` at the start of every turn; read and appended to `st.messages` if a trigger utterance cancels the turn before it finishes.

**Inbound message types** (sent by Twilio Conversation Relay):

| `type` | Key fields | Handling |
|---|---|---|
| `setup` | `callSid`, `from`, `to` | Logged only; no state change. First message on every connection. |
| `prompt` | `voicePrompt` (caller's transcribed speech) | If a reply *is* already streaming: `barge_in.should_interrupt()` checks whether this is a stop/wait phrase or a new question. If so, the in-flight reply is cancelled and a fresh one starts for this utterance (see "Selective barge-in" below). Otherwise the text is just logged — not spoken, not acted on, not recorded. If no reply is streaming: `fillers.is_backchannel()` catches pure acknowledgment noise (e.g. "ok", "yeah") and records it into `messages` with no reply — this also covers the case where STT finishes transcribing a short "ok" just *after* the reply already finished. Otherwise a new reply starts (`start_reply()`), which also decides via `fillers.looks_like_question()` whether to prepend a filler phrase. |
| `interrupt` | `utteranceUntilInterrupt` | Not expected given `interruptible="none"` — logged only, no state change. Caller speech during agent speech arrives as `prompt` instead (see above); Twilio itself never auto-pauses. |
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

`start_reply(user_text)` appends the caller's utterance to `st.messages`, decides whether a filler is warranted (`fillers.looks_like_question(user_text)`; if so, `fillers.pick(config.FILLER_PHRASES)` picks one at random), and spawns `respond_to(filler)` as an `asyncio.Task` stored on `st.task`:

1. If a filler was picked, send it immediately as the very first spoken token: `{"type": "text", "token": filler + " ", "last": False}`. This happens *before* `guide_client.stream_reply()` is even called, so the caller hears something right away while GuideAnts is still generating the real answer.
2. Call `guide_client.stream_reply(st.messages)` and forward each delta to the WS as a `{"type": "text", ...}` frame, accumulating it into `reply_text`.
3. Send a final `{"token": "", "last": true}` frame to signal end-of-turn to Twilio.
4. **On success**, append to `st.messages` in this exact order:
   1. the filler, as its own `{"role": "assistant", "content": filler}` message (only if one was picked),
   2. the real reply, as `{"role": "assistant", "content": reply_text}`.

   **Why this order matters:** GuideAnts resolves/matches its persisted server-side conversation by looking at the text of the *latest* assistant message in the transcript this app sends each turn (see "The GuideAnts endpoint this app depends on" below). If the filler were appended last instead of the real reply, GuideAnts would fail to match the existing conversation on the next turn and would start a brand-new one every single turn — silently discarding all prior context. So the filler must be appended *before* the real reply, never after it and never in its place. The filler is also deliberately kept out of `st.messages` before `stream_reply()` is called, so GuideAnts itself never sees the filler as part of the conversation it's continuing.
5. **On `asyncio.CancelledError`** (only ever raised by `cancel_task()`, which runs on `WebSocketDisconnect`): re-raises without touching `st.messages`.
6. **On any other exception** (e.g. GuideAnts unreachable, HTTP error): logs the full traceback and sends a single spoken fallback line (`"Sorry, I'm having trouble right now."`) as a `last: true` frame, rather than leaving the caller in silence or crashing the WS loop. `st.messages` is left as it was before the failed attempt (the filler, if any, was never appended, and neither is a reply — since none was produced).

### Filler phrases and mid-reply speech

1. **While a reply is streaming, non-trigger speech.** If the utterance is neither a stop/wait phrase nor a new question (see "Selective barge-in" below for exactly what counts as a trigger), it is not acted on at all: not spoken, not cancelled, not recorded anywhere — `fillers.py` is not even consulted for this case. The current reply keeps playing to its end exactly as if the caller had stayed silent, and the utterance itself is gone: it is never replayed to GuideAnts as context on a later turn.
2. **While a reply is streaming, trigger speech.** See "Selective barge-in" below — the in-flight reply is cancelled and a fresh one starts immediately for the new utterance.
3. **Late backchannel, after the reply already finished.** Twilio's speech-to-text can finish transcribing a short utterance like "ok" slightly *after* the reply has already finished playing, so by the time the `prompt` arrives `st.task.done()` is already `True` — it no longer looks like "mid-reply" at all. To stop this from being treated as a brand-new question, `fillers.is_backchannel(text, config.EXTRA_BACKCHANNEL_PHRASES)` checks whether the whole utterance is pure acknowledgment noise (`fillers.BACKCHANNEL_PHRASES`: "ok", "okay", "yeah", "mmhmm", "got it", ... plus anything in the env-configurable extra list). If so, it's appended straight to `st.messages` as a `user` message and logged ("Recorded backchannel utterance (not acted on)") — no guide call, no reply.
4. **Starting a real reply.** Otherwise, `start_reply(text)` runs: it appends the caller's text to `st.messages`, and separately (not stored in `st.messages`) checks `fillers.looks_like_question(text)` — true for text ending in `?`, or starting (after stripping leading fillers like "um"/"okay"/"so") with an interrogative word (`what`, `how`, `can`, `is`, ...) or a request verb (`tell`, `find`, `help`, ...), or a lead-in phrase like "i need"/"i want"/"looking for". If true, a random phrase from `config.FILLER_PHRASES` is spoken first, immediately, before the real GuideAnts reply — masking the network/LLM latency of the lookup with something audible right away. If false, the real reply just starts streaming with no filler.

On `WebSocketDisconnect`, any in-flight task is cancelled and the loop exits — nothing is persisted, so a dropped call simply forgets the conversation.

### Selective barge-in

`interruptible` stays `"none"` — Twilio itself never pauses or stops
playback on its own. Instead, `app.py` decides, per mid-reply `prompt`,
whether to cut the reply over using `barge_in.should_interrupt(text,
config.EXTRA_STOP_PHRASES)`:

- **Stop/wait phrase** (`barge_in.STOP_PHRASES`/`EXTRA_STOP_PHRASES` — "stop",
  "wait", "hold on", "no", ...) or **a new question**
  (`fillers.looks_like_question()`) → the in-flight reply is cancelled
  (`cancel_task()`), the real reply text streamed so far this turn
  (`st.partial_reply` — never including the filler) is appended to
  `st.messages` if non-empty, and `start_reply(text)` runs for the new
  utterance exactly as if it were a fresh prompt.
- **Anything else** (statement, backchannel, noise) → logged and ignored,
  exactly as before this feature.

Playback is actually cut off using Conversation Relay's `preemptible` flag,
not Twilio-native interruption: every `text` frame `respond_to()` sends is
marked `"preemptible": true`. Per Twilio's docs this flag is a property of
the *currently playing* turn declaring "this may be replaced by whatever
comes after it" — so marking every outgoing frame this way is what lets a
later, trigger-cancelled-and-restarted turn cut off one still mid-playback.
It's a no-op in the normal case, since a new turn only starts normally once
the previous one has already fully finished.

Caveat: on a cancelled turn, `st.partial_reply` is this app's own
best-effort record of what was *sent*, not a guarantee of what GuideAnts
persisted server-side for an aborted stream — there's no Twilio-side
"what was actually heard" signal available here (unlike a native
`interrupt` event), so this can't be made fully precise from the client.

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
5. `app.py` appends it to `messages`. If the utterance looks like a question/request (`fillers.looks_like_question()`), a random filler phrase is sent first as its own spoken token. Then `guide_client.stream_reply` is called and the reply is streamed back as `text` frames; Twilio speaks it via TTS as tokens arrive, with `interruptible="none"` so nothing Twilio hears from the caller during this stops playback.
6. If the caller talks during the reply, Twilio still transcribes it and sends it as another `prompt` (`report_input_during_agent_speech="speech"`) rather than an `interrupt`. If it's a stop/wait phrase or a new question (`barge_in.should_interrupt()`), the in-flight reply is cancelled and a fresh reply starts for it immediately (repeat from step 4). Otherwise the current reply keeps playing to the end and the utterance is just logged.
7. Once the reply finishes normally, the filler (if any) and the real reply are appended to `messages` in that order. `messages` grows for the life of the call.
8. Repeat from step 4 for each new turn. Non-trigger speech heard mid-reply (step 6) is never recorded anywhere and is not automatically revisited — if it was itself a real question, it is only answered if the caller asks it again after the current reply finishes.
9. Caller hangs up → WS disconnects → in-flight task is cancelled, connection state (and the entire conversation) is discarded.

## Known gaps (intentionally out of scope today)

From SETUP.md's "optional hardening" list — not implemented, not required for the demo to work:
- No `X-Twilio-Signature` validation on `/twiml` (any request to that URL is trusted).
- No handling of Twilio `end`/handoff messages (e.g. transfer to a human).
- No silence timeout / re-prompt if the caller goes quiet.
- `dtmf` digits are logged but never acted on — no keypad menu.
