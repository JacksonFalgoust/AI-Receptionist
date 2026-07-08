# Architecture — how the code and endpoints work

This is the deep-dive companion to [README.md](README.md) (overview) and
[SETUP.md](SETUP.md) (complete setup steps, including manual Twilio/GuideAnts
config). It explains what each file
does, the exact wire protocol on every endpoint, and how a call flows through
the system end to end.

There is no database, no session store outside memory — this is purely a
**protocol bridge** between Twilio Conversation Relay's WebSocket protocol
and GuideAnts' OpenAI-compatible chat API. `fillers.py`, `barge_in.py`, and
`speaker_events.py` are the exceptions to "no business logic": pure, I/O-free
heuristics that decide whether a caller's utterance warrants a spoken filler
phrase (`fillers.py`), should cancel and restart an in-flight reply
(`barge_in.py`), or whether an unrecognized WS message is one of Twilio's
speaker events (`speaker_events.py`).

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
| [barge_in.py](barge_in.py) | Pure functions used by `app.py` to decide selective barge-in: `is_stop_command` matches a caller utterance against a built-in stop/wait phrase list, and `should_interrupt` (= `is_stop_command` or `fillers.looks_like_question`) decides whether an utterance heard mid-reply should cancel the in-flight reply at all. No I/O, no Twilio/GuideAnts knowledge — unit-tested directly in `test_barge_in.py`. |
| [speech_timing.py](speech_timing.py) | One pure function, `estimate_seconds`, used by `app.py` to estimate how long Twilio's TTS will take to speak a given text from its word count. Fallback pacing until the first agent-stopped speaker event is recognized on a call, and the basis of the ceiling on waiting for one. No I/O. |
| [speaker_events.py](speaker_events.py) | One pure function, `classify`, used by `app.py` to recognize Twilio's speaker-event WS messages (`agentSpeaking`/`clientSpeaking` start/stop, subscribed via `events="speaker-events"` in the TwiML). Matches loosely since Twilio doesn't document the exact JSON shape — unit-tested in `test_speaker_events.py`. No I/O. |
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
| `FILLER_PHRASES` | `FILLER_PHRASES` | a built-in list of 6 phrases (e.g. `"Let me look that up for you."`) | `app.py` (via `fillers.pick`) — pool of filler phrases spoken before the real reply when the caller's utterance looks like a question/request *and* GuideAnts hasn't replied within `FILLER_DELAY_SECONDS`. Pipe-separated (`\|`) in the env var, since phrases contain commas/periods; falls back to the built-in list if unset. |
| `FILLER_DELAY_SECONDS` | `FILLER_DELAY_SECONDS` | `1.0` | `app.py` — how long to wait for GuideAnts' reply, for a filler-eligible utterance, before speaking a filler phrase. If the reply arrives before this elapses, no filler is spoken at all. |
| `EXTRA_BACKCHANNEL_PHRASES` | `EXTRA_BACKCHANNEL_PHRASES` | `[]` (empty) | `app.py` (via `fillers.is_backchannel`) — comma-separated phrases, on top of the built-in `fillers.BACKCHANNEL_PHRASES`, that count as pure acknowledgment noise and should never get a guide reply. |
| `EXTRA_STOP_PHRASES` | `EXTRA_STOP_PHRASES` | `[]` (empty) | `app.py` (via `barge_in.should_interrupt`/`is_stop_command`) — comma-separated phrases, on top of the built-in `barge_in.STOP_PHRASES`, that also cancel an in-flight reply when heard mid-reply. |
| `STOP_ACK_PHRASES` | `STOP_ACK_PHRASES` | a built-in list of 4 phrases (e.g. `"Okay."`) | `app.py` (via `fillers.pick`) — pool of short local acknowledgments spoken (instead of a GuideAnts reply) when a stop/wait phrase cancels an in-flight reply. Pipe-separated (`\|`) in the env var; falls back to the built-in list if unset. |
| `TTS_WORDS_PER_SECOND` | `TTS_WORDS_PER_SECOND` | `2.5` | `app.py` (via `speech_timing.estimate_seconds`) — assumed TTS speaking rate, used to estimate how long a reply takes to speak aloud. Twilio's agent-stopped speaker event is the primary "reply finished playing" signal; this estimate paces replies until the first such event is recognized on a call, and caps how long the app waits for one after that (×1.5 + 2s). |

If `GUIDEANTS_PUB_ID` is empty when the guide client is first used, `guide_client.py` raises a `RuntimeError` telling the user to fill in `.env` — this is the only config validation in the app.

---

## guide_client.py

Exposes exactly one public function: `stream_reply(messages) -> AsyncIterator[str]`.

- `_get_client()` lazily builds a module-level singleton `AsyncOpenAI` client the first time it's needed, pointed at:
  `{GUIDEANTS_BASE_URL}/api/published/openai/{GUIDEANTS_PUB_ID}/v1`
  This is GuideAnts' OpenAI-compatible endpoint, **not** the OpenAI API — same request/response shape, different backend. Because it's a singleton, the client (and its HTTP connection pool) is reused across every call/WS connection the app handles.
- `stream_reply(messages)` calls `client.chat.completions.create(model=..., messages=messages)` (no `stream=True` — the published wire API's chat-completions endpoint is non-streaming only and rejects `stream=true` with `unsupported_feature`) and yields the whole `choices[0].message.content` as a single delta, if non-empty.
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
        reportInputDuringAgentSpeech="speech"
        events="speaker-events" />
    </Connect>
  </Response>
  ```
- `interruptible="none"` + `reportInputDuringAgentSpeech="speech"` together mean Twilio itself never pauses or stops TTS playback because of caller speech, but caller speech heard during agent speech is still transcribed and delivered to this app as a `prompt` message (instead of the `interrupt` message Twilio would send under `interruptible="speech"`). What this app does with that reported speech — ignore it, or cancel and restart the reply for it — is a decision made in `app.py`/`fillers.py`/`barge_in.py`; see "Filler phrases and mid-reply speech" and "Selective barge-in" below.
- `events="speaker-events"` subscribes to Twilio's notifications that the agent (TTS playback) or client (caller) started/stopped speaking. The agent-stopped event is the real "the reply finished playing" signal used to hold the reply task open (see "`start_reply()` / `respond_to()`" below); Twilio documents the subscription attribute but not the messages' JSON shape, so `speaker_events.py` recognizes them loosely and the app falls back to the word-count estimate until the first agent-stop is recognized on a call.
- Response content type is `application/xml`. No request body is read — everything needed comes from the `Host` header and this app's own config.

### `WS /ws`

Twilio opens exactly one WebSocket connection here per call, immediately after `/twiml` returns, and keeps it open for the life of the call. All messages are JSON text frames.

**Per-connection state** (`CallState`, one instance per call — all local to the WS handler closure; nothing is shared across calls, nothing persists after disconnect):
- `messages: list[dict]` — the full running chat history sent to GuideAnts on every turn.
- `task` — the `asyncio.Task` currently generating/speaking a reply, if any; also doubles as the "is a reply active right now" flag (`st.task and not st.task.done()`). Because GuideAnts' endpoint is non-streaming, the whole reply is fetched and sent to Twilio in one shot almost immediately — `respond_to()` doesn't let this task finish there, though; it holds the task open until Twilio's agent-stopped speaker event reports that playback actually finished (with the word-count estimate — `speech_timing.estimate_seconds`, paced by `config.TTS_WORDS_PER_SECOND` — as a ×1.5 + 2s ceiling on that wait), or, until the first such event has been recognized on the call, just sleeps out whatever's left of that same estimate. Either way the task stays "not done," and mid-reply speech still gets evaluated as mid-reply, for roughly as long as Twilio is actually still speaking.
- `playback_done: asyncio.Event` — set by the WS loop whenever an agent-stopped speaker event arrives; awaited by `respond_to()`'s playback hold. Cleared by `respond_to()` only at the start of the hold, so stale sets (the welcome greeting ending, or a filler finishing while GuideAnts was still generating) can't release a later hold early.
- `agent_stop_seen: bool` — `True` once any agent-stop speaker event has been recognized this call. Until then `respond_to()` paces on the estimate alone, so an account/edge whose speaker events never arrive (or arrive in a shape `speaker_events.classify` doesn't recognize) behaves exactly as before this feature.
- `partial_reply: str` — the real (GuideAnts-sourced) reply text streamed so far in the current turn, never including the filler. Reset to `""` at the start of every turn; read and appended to `st.messages` if a trigger utterance cancels the turn before it finishes.

**Inbound message types** (sent by Twilio Conversation Relay):

| `type` | Key fields | Handling |
|---|---|---|
| `setup` | `callSid`, `from`, `to` | Logged only; no state change. First message on every connection. |
| `prompt` | `voicePrompt` (caller's transcribed speech) | If a reply *is* already streaming: `barge_in.should_interrupt()` checks whether this is a stop/wait phrase or a new question. If so, the in-flight reply is cancelled; a stop/wait phrase then just gets a local acknowledgment and silence, a new question starts a fresh reply for this utterance (see "Selective barge-in" below). Otherwise the text is just logged — not spoken, not acted on, not recorded anywhere. If no reply is streaming: `fillers.is_backchannel()` catches pure acknowledgment noise (e.g. "ok", "yeah") and it's just logged, never recorded into `messages` either — this also covers the case where STT finishes transcribing a short "ok" just *after* the reply already finished. Otherwise a new reply starts (`start_reply()`), which also decides via `fillers.looks_like_question()` whether to prepend a filler phrase. |
| `interrupt` | `utteranceUntilInterrupt` | Not expected given `interruptible="none"` — logged only, no state change. Caller speech during agent speech arrives as `prompt` instead (see above); Twilio itself never auto-pauses. |
| `dtmf` | `digit` | Logged only — not acted on (no IVR menu implemented; see SETUP.md's "not implemented" list). |
| `error` | `description` | Logged as an error. Connection is not closed by this app. |
| speaker events | undocumented by Twilio | Any type not listed above is run through `speaker_events.classify()`, which loosely recognizes the `agentSpeaking`/`clientSpeaking` start/stop notifications subscribed via `events="speaker-events"`. An agent-stop sets `st.agent_stop_seen` and `st.playback_done` (releasing `respond_to()`'s playback hold — see above); every recognized event is logged with its full payload, since Twilio doesn't document the shape and the log is how a mismatch with the classifier gets noticed. Because only unhandled types reach the classifier, a caller's `prompt` whose transcript mentions "agent speaking" can never match. |
| anything else | — | Logged as a warning (with the full payload), ignored. |

Non-JSON frames are logged and skipped rather than crashing the loop.

**Outbound message shape** (sent by this app to Twilio):
```json
{"type": "text", "token": "Hello there!", "last": false, "preemptible": true}
{"type": "text", "token": "", "last": true, "preemptible": true}
```
Because GuideAnts' chat-completions endpoint is non-streaming only, `guide_client.stream_reply` yields the whole reply as one token frame rather than incremental deltas — the filler phrase (sent as its own frame first, see below) is what actually masks the wait while GuideAnts generates the answer. Every frame carries `preemptible: true` — see "Selective barge-in" below for why.

### `start_reply()` / `respond_to()` — the reply pipeline

`start_reply(user_text)` appends the caller's utterance to `st.messages` and spawns `respond_to(filler_eligible)` as an `asyncio.Task` stored on `st.task`, where `filler_eligible = fillers.looks_like_question(user_text)`:

1. Start `guide_client.stream_reply(st.messages)` and immediately begin fetching its first chunk as a background task (`gen.__anext__()`), rather than awaiting it directly.
2. If `filler_eligible` is true, race that fetch against `config.FILLER_DELAY_SECONDS` (`asyncio.wait(..., timeout=...)`). If GuideAnts hasn't responded by the time the timeout elapses, pick a random phrase from `config.FILLER_PHRASES` and send it immediately as its own spoken token: `{"type": "text", "token": filler + " ", "last": False, "preemptible": True}`. Either way (timed out or not), keep waiting on the *same* in-flight fetch afterward — nothing is restarted or duplicated. If `filler_eligible` is false, the fetch is simply awaited with no race and no filler, regardless of how long it takes.
3. Forward the resulting delta(s) to the WS as `{"type": "text", ...}` frames, accumulating them into `reply_text`, then send a final `{"token": "", "last": true}` frame to signal end-of-turn to Twilio.
4. **On success**, append the real reply to `st.messages` as `{"role": "assistant", "content": reply_text}` — the filler is never appended. Then hold the turn open until playback actually ends: wait for Twilio's agent-stopped speaker event (`st.playback_done`, with ×1.5 + 2s of the word-count estimate as a ceiling in case the event is lost), or — until the first agent-stop has been recognized on the call — just sleep out the remainder of the word-count estimate as the older versions did. This is what keeps `st.task` "not done" while Twilio is still speaking.

   **Why the filler is excluded:** GuideAnts resolves/matches its persisted server-side conversation by looking at the text of the *latest* assistant message in the transcript this app sends each turn (see "The GuideAnts endpoint this app depends on" below). GuideAnts never sees or generates the filler — it's spoken locally by this app, before `stream_reply()` is even called — so if the filler were ever appended to `st.messages` as an assistant message, it would become the "latest assistant message" GuideAnts checks against, which GuideAnts itself never produced. That mismatch would make GuideAnts fail to match the existing conversation on the next turn and start a brand-new one every single turn — silently discarding all prior context. So the filler is kept out of `st.messages` entirely, both before and after the turn.
5. **On `asyncio.CancelledError`** (raised by `cancel_task()`, called either from the `finally` block on `WebSocketDisconnect`, or from the mid-reply barge-in branch when a trigger utterance cancels this turn — see "Selective barge-in" below): explicitly cancels the background chunk-fetch task too (so the abandoned GuideAnts call doesn't keep running unobserved), then re-raises without touching `st.messages` here; the barge-in caller is responsible for its own history bookkeeping (`st.partial_reply`) in the latter case.
6. **On any other exception** (e.g. GuideAnts unreachable, HTTP error): logs the full traceback and sends a single spoken fallback line (`"Sorry, I'm having trouble right now."`) as a `last: true` frame, rather than leaving the caller in silence or crashing the WS loop. `st.messages` is left as it was before the failed attempt (the filler, if any, was never appended, and neither is a reply — since none was produced).

### Filler phrases and mid-reply speech

1. **While a reply is streaming, non-trigger speech.** `barge_in.should_interrupt()` calls `fillers.looks_like_question()` on every mid-reply utterance to classify it (see "Selective barge-in" below for exactly what counts as a trigger); if it comes back false and the utterance also isn't a stop/wait phrase, nothing further happens: not spoken, not cancelled, not recorded anywhere, and no filler is picked. The current reply keeps playing to its end exactly as if the caller had stayed silent, and the utterance itself is gone: it is never replayed to GuideAnts as context on a later turn.
2. **While a reply is streaming, trigger speech.** See "Selective barge-in" below — the in-flight reply is cancelled; a stop/wait phrase gets a local acknowledgment and silence, a new question starts a fresh reply immediately for the new utterance.
3. **Late backchannel, after the reply already finished.** Twilio's speech-to-text can finish transcribing a short utterance like "ok" slightly *after* the reply (and its playback-end hold — the agent-stopped speaker event or the estimate fallback, see above) has actually finished, so by the time the `prompt` arrives `st.task.done()` is already `True` — it no longer looks like "mid-reply" at all. To stop this from being treated as a brand-new question, `fillers.is_backchannel(text, config.EXTRA_BACKCHANNEL_PHRASES)` checks whether the whole utterance is pure acknowledgment noise (`fillers.BACKCHANNEL_PHRASES`: "ok", "okay", "yeah", "mmhmm", "got it", ... plus anything in the env-configurable extra list). If so, it's just logged ("Ignored backchannel utterance (not acted on)") — never appended to `st.messages`, no guide call, no reply — for the same reason fillers and non-trigger mid-reply speech aren't: GuideAnts must never see a local message it didn't itself produce (see the module docstring in `app.py`).
4. **Starting a real reply.** Otherwise, `start_reply(text)` runs: it appends the caller's text to `st.messages`, and separately (not stored in `st.messages`) checks `fillers.looks_like_question(text)` — true for text ending in `?`, or starting (after stripping leading fillers like "um"/"okay"/"so") with an interrogative word (`what`, `how`, `can`, `is`, ...) or a request verb (`tell`, `find`, `help`, ...), or a lead-in phrase like "i need"/"i want"/"looking for". This result (`filler_eligible`) only decides whether a filler is a *candidate* — the filler itself is only actually spoken if GuideAnts also hasn't replied within `config.FILLER_DELAY_SECONDS` (see "`start_reply()` / `respond_to()`" above). So a filler-eligible question that GuideAnts answers quickly gets no filler, and a non-eligible utterance (e.g. "thank you") never gets one no matter how slow GuideAnts is.

On `WebSocketDisconnect`, any in-flight task is cancelled and the loop exits — nothing is persisted, so a dropped call simply forgets the conversation.

### Selective barge-in

`interruptible` stays `"none"` — Twilio itself never pauses or stops
playback on its own. Instead, `app.py` decides, per mid-reply `prompt`,
whether to cut the reply over using `barge_in.should_interrupt(text,
config.EXTRA_STOP_PHRASES)`:

Both cases below start by cancelling the in-flight reply (`cancel_task()`)
and, if any reply text had been sent so far this turn (`st.partial_reply` —
never including the filler), appending it to `st.messages`. What happens
next differs:

- **Stop/wait phrase** (`barge_in.is_stop_command()` — "stop", "wait", "hold
  on", "no", ... plus `EXTRA_STOP_PHRASES`) → GuideAnts is *not* called. A
  random phrase from `config.STOP_ACK_PHRASES` (e.g. "Okay.") is sent as a
  single preemptible frame instead, then the turn ends there — no
  `start_reply()`, no new `st.messages` entries for the stop utterance or the
  acknowledgment (same reasoning as fillers: GuideAnts never saw either, so
  recording them would desync local history from GuideAnts' persisted
  state). This is what actually makes "stop" stop: cutting over doesn't wait
  on a GuideAnts round-trip, and doesn't depend on the guide choosing to
  reply briefly.
- **A new question** (`fillers.looks_like_question()`, and not itself a stop
  phrase) → `start_reply(text)` runs for the new utterance exactly as if it
  were a fresh prompt.
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
- **Request body**: standard OpenAI chat-completions shape — `{"model": "guide", "messages": [...]}`. `model` must match one of the alias `id`s returned by `GET .../v1/models` (normally the fixed alias `"guide"` for the chat-completions endpoint, not the real underlying model name).
- **Statelessness**: this endpoint does not remember prior turns on its own from a bare `messages` array the way `/invoke` implicitly manages a conversation — GuideAnts derives/resumes a conversation from the message history it's given, but this client's contract is "send the full transcript every time," which is exactly what `app.py`'s `messages` list does.
- **Non-streaming only**: this endpoint rejects `stream: true` with an OpenAI-shaped `unsupported_feature` error — it always returns a single JSON object with `choices[0].message.content`, `finish_reason`, and `usage`. `guide_client.stream_reply` reads that whole message and yields it as one delta.
- **Tool calls**: the wire endpoint also supports OpenAI-style `tools`/`tool_calls` (client-side tool execution) — unused here since the receptionist guide doesn't define any tools today, but the endpoint would return `finish_reason: "tool_calls"` if it did.
- **Errors**: e.g. `403 endpoint_disabled` if the guide's "Enable Wire API" / "Chat Completions" toggle isn't turned on in the Publish dialog (see SETUP.md step 1.5).

`GET {GUIDEANTS_BASE_URL}/api/published/openai/{pubId}/v1/models` is the companion read-only endpoint used manually (not by this app's code) to discover the valid `model` alias values before filling in `.env`.

---

## Full call sequence

1. Caller dials the Twilio number.
2. Twilio POSTs to `/twiml`. App returns `<Connect><ConversationRelay url="wss://.../ws" .../></Connect>`.
3. Twilio opens the WS, speaks `WELCOME_GREETING` to the caller immediately (handled entirely by Twilio, not by this app), then sends `setup`.
4. Caller speaks. Twilio transcribes it and sends `prompt` with `voicePrompt`.
5. `app.py` appends it to `messages` and calls `guide_client.stream_reply`. If the utterance looks like a question/request (`fillers.looks_like_question()`) and GuideAnts hasn't replied within `config.FILLER_DELAY_SECONDS`, a random filler phrase is sent as its own spoken token while still waiting on the same in-flight call, masking the wait. GuideAnts' (non-streaming) reply is then sent to Twilio as one `text` frame; Twilio speaks it via TTS, with `interruptible="none"` so nothing Twilio hears from the caller during this stops playback.
6. If the caller talks during the reply, Twilio still transcribes it and sends it as another `prompt` (`report_input_during_agent_speech="speech"`) rather than an `interrupt`. If it's a stop/wait phrase (`barge_in.is_stop_command()`), the in-flight reply is cancelled and a short local acknowledgment is spoken instead — no GuideAnts call. If it's a new question, the in-flight reply is cancelled and a fresh reply starts for it immediately (repeat from step 4). Otherwise the current reply keeps playing to the end and the utterance is just logged.
7. Once the reply finishes normally, the real reply is appended to `messages` (the filler, if any, is never appended — see "Why the filler is excluded" above). `messages` grows for the life of the call.
8. Repeat from step 4 for each new turn. Non-trigger speech heard mid-reply (step 6) is never recorded anywhere and is not automatically revisited — if it was itself a real question, it is only answered if the caller asks it again after the current reply finishes.
9. Caller hangs up → WS disconnects → in-flight task is cancelled, connection state (and the entire conversation) is discarded.

## Known gaps (intentionally out of scope today)

From SETUP.md's "optional hardening" list — not implemented, not required for the demo to work:
- No `X-Twilio-Signature` validation on `/twiml` (any request to that URL is trusted).
- No handling of Twilio `end`/handoff messages (e.g. transfer to a human).
- No silence timeout / re-prompt if the caller goes quiet.
- `dtmf` digits are logged but never acted on — no keypad menu.
