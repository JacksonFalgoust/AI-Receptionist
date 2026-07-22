# Architecture — how the code and endpoints work

This is the deep-dive companion to [README.md](README.md) (overview) and
[SETUP.md](SETUP.md) (complete setup steps, including manual Twilio/GuideAnts
config). It explains what each file
does, the exact wire protocol on every endpoint, and how a call flows through
the system end to end.

There is no database — the one piece of durable state is server-side, inside
GuideAnts: a `conversation` id captured on each call's first turn and echoed
back on every later turn (see "The GuideAnts endpoint this app depends on"
below). This app itself holds nothing but that id and a local debug log —
it's purely a **protocol bridge** between Twilio Conversation Relay's
WebSocket protocol and GuideAnts' OpenAI-compatible Responses API.
`fillers.py`, `barge_in.py`, and `speaker_events.py` are the exceptions to
"no business logic": pure, I/O-free heuristics that decide whether a
caller's utterance warrants a spoken filler phrase (`fillers.py`), should
cancel and restart an in-flight reply (`barge_in.py`), or whether an
unrecognized WS message is one of Twilio's speaker events
(`speaker_events.py`).

```
                    POST /twiml (TwiML)            WS /ws (JSON frames)
Caller ⇄ Twilio ⇄ ───────────────────── ⇄ app.py ⇄ ───────────────────── ⇄ Twilio Conversation Relay
                                            │
                                            │ HTTPS, OpenAI SDK
                                            ▼
                              GuideAnts POST /api/published/openai/{pubId}/v1/responses
                                            │
                                            ▼
                                     Published guide (LLM)
```

## File map

| File | Role |
|---|---|
| [config.py](config.py) | Reads all settings from environment / `.env`, no other file touches `os.environ`. |
| [guide_client.py](guide_client.py) | Thin wrapper around the `openai` SDK pointed at GuideAnts' Responses API; exposes `stream_reply` (one turn) and `build_input` (interruption-note folding), plus the `GuideSession` continuation handle. |
| [fillers.py](fillers.py) | Pure functions used by `app.py` to decide the filler-phrase behavior: `looks_like_question` classifies a caller utterance as question/request-like (warrants a filler) or not, `pick` returns a random filler phrase from a list, and `is_backchannel` classifies an utterance as pure acknowledgment noise (e.g. "ok", "yeah") that should never get a guide reply. No I/O, no Twilio/GuideAnts knowledge. |
| [barge_in.py](barge_in.py) | Pure functions used by `app.py` to decide selective barge-in: `is_stop_command` matches a caller utterance against a built-in stop/wait phrase list, and `should_interrupt` (= `is_stop_command` or `fillers.looks_like_question`) decides whether an utterance heard mid-reply should cancel the in-flight reply at all. No I/O, no Twilio/GuideAnts knowledge — unit-tested directly in `test_barge_in.py`. |
| [speech_timing.py](speech_timing.py) | One pure function, `estimate_seconds`, used by `app.py` to estimate how long Twilio's TTS will take to speak a given text from its word count. Fallback pacing until the first agent-stopped speaker event is recognized on a call, and the basis of the ceiling on waiting for one. No I/O. |
| [speaker_events.py](speaker_events.py) | One pure function, `classify`, used by `app.py` to recognize Twilio's speaker-event WS messages (`agentSpeaking`/`clientSpeaking` start/stop, subscribed via `events="speaker-events"` in the TwiML). Matches loosely since Twilio doesn't document the exact JSON shape — unit-tested in `test_speaker_events.py`. No I/O. |
| [app.py](app.py) | FastAPI app with the two endpoints Twilio talks to: `POST /twiml` and `WS /ws`. All call-handling logic lives here; also mounts `reservations_api.router`. |
| [reservations_api.py](reservations_api.py) | FastAPI router: `/api/reservations/*` + `/api/booqable/ping` — GuideAnts' tool-calling surface, independent of the Twilio WS path. See "Reservation API" below. |
| [reservations.py](reservations.py) | Booqable business logic (catalog lookup, availability check, create/cancel order) behind `reservations_api.py`. |
| [booqable_client.py](booqable_client.py) | Thin async `httpx` wrapper around Booqable's JSON:API v4 (Bearer-token auth). |

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
| `GUIDEANTS_MODEL` | `GUIDEANTS_MODEL` | `"guide"` | `guide_client.py` — `model` field in the responses request (fixed alias, not a real model name) |
| `GUIDEANTS_TIMEOUT_SECONDS` | `GUIDEANTS_TIMEOUT_SECONDS` | `30` | `guide_client.py` — request timeout passed to the `AsyncOpenAI` client (with `max_retries=1`), replacing the SDK's 600s/2-retry defaults, which would be dead air on a live call |
| `WELCOME_GREETING` | `WELCOME_GREETING` | `"Thanks for calling! How can I help you today?"` | `app.py` — spoken by Twilio before any WS traffic happens |
| `TWILIO_AUTH_TOKEN` | `TWILIO_AUTH_TOKEN` | `""` | not currently used in code — reserved for optional `X-Twilio-Signature` validation (not implemented, see SETUP.md) |
| `PORT` | `PORT` | `8080` | not read by `app.py` itself — `uvicorn` is started with `--port` on the command line; this constant is unused today |
| `FILLER_PHRASES` | `FILLER_PHRASES` | a built-in list of 6 phrases (e.g. `"Let me look that up for you."`) | `app.py` (via `fillers.pick`) — pool of filler phrases spoken before the real reply when the caller's utterance looks like a question/request *and* GuideAnts hasn't replied within `FILLER_DELAY_SECONDS`. Pipe-separated (`\|`) in the env var, since phrases contain commas/periods; falls back to the built-in list if unset. |
| `FILLER_DELAY_SECONDS` | `FILLER_DELAY_SECONDS` | `1.0` | `app.py` — how long to wait for GuideAnts' reply, for a filler-eligible utterance, before speaking a filler phrase. If the reply arrives before this elapses, no filler is spoken at all. |
| `TURN_PAUSE_SECONDS` | `TURN_PAUSE_SECONDS` | `0.5` | `app.py` (`schedule_turn()`) — how long the caller must stay quiet after a transcribed prompt before the buffered text is committed as their turn; a clientSpeaking-start speaker event during the wait holds the buffer open for the continuation instead (see "Turn-pause buffering" below). The only latency this feature adds to an ordinary turn. |
| `TURN_RESUME_GRACE_SECONDS` | `TURN_RESUME_GRACE_SECONDS` | `1.5` | `app.py` — after the caller resumes speaking mid-buffer and then stops again, how long to wait for the continuation's transcript (which trails the clientSpeaking-stop event by STT finalization time) before giving up and committing the buffered text alone. |
| `EXTRA_BACKCHANNEL_PHRASES` | `EXTRA_BACKCHANNEL_PHRASES` | `[]` (empty) | `app.py` (via `fillers.is_backchannel`) — comma-separated phrases, on top of the built-in `fillers.BACKCHANNEL_PHRASES`, that count as pure acknowledgment noise and should never get a guide reply. |
| `EXTRA_STOP_PHRASES` | `EXTRA_STOP_PHRASES` | `[]` (empty) | `app.py` (via `barge_in.should_interrupt`/`is_stop_command`) — comma-separated phrases, on top of the built-in `barge_in.STOP_PHRASES`, that also cancel an in-flight reply when heard mid-reply. |
| `STOP_ACK_PHRASES` | `STOP_ACK_PHRASES` | a built-in list of 4 phrases (e.g. `"Okay."`) | `app.py` (via `fillers.pick`) — pool of short local acknowledgments spoken (instead of a GuideAnts reply) when a stop/wait phrase cancels an in-flight reply. Pipe-separated (`\|`) in the env var; falls back to the built-in list if unset. |
| `TTS_WORDS_PER_SECOND` | `TTS_WORDS_PER_SECOND` | `2.5` | `app.py` (via `speech_timing.estimate_seconds`) — assumed TTS speaking rate, used to estimate how long a reply takes to speak aloud. Twilio's agent-stopped speaker event is the primary "reply finished playing" signal; this estimate paces replies until the first such event is recognized on a call, and caps how long the app waits for one after that (×1.5 + 2s). |

If `GUIDEANTS_PUB_ID` is empty when the guide client is first used, `guide_client.py` raises a `RuntimeError` telling the user to fill in `.env` — this is the only config validation in the app.

---

## guide_client.py

Exposes:

- `GuideSession` — a small dataclass holding one field, `conversation_id: str | None`. One instance lives for the life of a call (`CallState.guide` in `app.py`), and is mutated in place by `stream_reply` as the continuation handle it gets back from GuideAnts.
- `stream_reply(user_text, session) -> AsyncIterator[str]` — sends a single caller utterance and yields the guide's reply as text deltas.
- `build_input(user_text, interrupted_partial) -> str` — pure text-shaping helper, see "Interruption notes" below.

`_get_client()` lazily builds a module-level singleton `AsyncOpenAI` client the first time it's needed, pointed at:
`{GUIDEANTS_BASE_URL}/api/published/openai/{GUIDEANTS_PUB_ID}/v1`
This is GuideAnts' OpenAI-compatible endpoint, **not** the OpenAI API — same request/response shape, different backend. `timeout=config.GUIDEANTS_TIMEOUT_SECONDS` and `max_retries=1` are set explicitly (the SDK's defaults, 600s/2 retries, would leave a caller in silence far too long on a hung request). Because it's a singleton, the client (and its HTTP connection pool) is reused across every call/WS connection the app handles.

Every turn — including the first — streams: `client.responses.create(model=..., input=user_text, conversation=session.conversation_id, stream=True)` (the `conversation` kwarg is simply omitted when `session.conversation_id` is still `None`). This is wrapped in `async with stream:` so the underlying SSE connection is always closed, including when a barge-in cancels the caller task mid-stream — the inner streaming generator is itself wrapped in `contextlib.aclosing()` from `stream_reply` so closing the outer generator deterministically closes the SSE connection even when the caller has already consumed one or more deltas (plain `async for ... yield` doesn't forward `.aclose()`/`GeneratorExit` to a nested async generator the way sync `yield from` does).

- **Capturing the conversation id**: GuideAnts' streamed `response.created` and `response.completed` events both carry a `conversation` field (a current GuideAnts build only — see the fallback below). `stream_reply` reads it off the first such event once per turn where `session.conversation_id` is still `None`, so the very first turn of a call gets its continuation handle without a separate round trip. Each `response.output_text.delta` event's `.delta` text is yielded as it arrives; other structural events (`response.output_item.added`, etc.) are skipped, and a `response.failed`/`error` event raises.
- **Old-build fallback**: if a turn that started with no conversation id completes without GuideAnts ever supplying one (an older GuideAnts build whose stream doesn't carry the field yet), `session.stream_missing_conversation` is set and a warning is logged. The *next* such turn falls back to a single **non-streaming** `client.responses.create(model=..., input=user_text)` call (the only path guaranteed to return `response.conversation`); turns after that stream normally again once an id is in hand.
- If GuideAnts returns a 400 with code `conversation_not_found` or `invalid_conversation_id` (e.g. the GuideAnts process restarted mid-call and lost its in-memory/db state for that conversation), `stream_reply` logs a warning, clears `session.conversation_id`, and retries once as a fresh streaming turn — the caller still gets an answer, but everything earlier in the call is no longer visible to the guide. This is deliberate (no recap replay): see "Known gaps" below.
- `user_text` here is **only the current turn's input** — never a resent transcript. On continuation, GuideAnts identifies the conversation purely by the `conversation` id and ignores any history the client might send, so there is nothing to resend.

### Why this endpoint and not `/invoke` or chat/completions

GuideAnts has multiple ways to talk to a published guide:

- **`/invoke`** starts a brand-new conversation on every call with no memory across turns — unworkable for a receptionist that needs to remember what the caller already said earlier in the same phone call.
- **The OpenAI-wire `chat/completions` endpoint** (used by this app before an earlier change) supports multi-turn conversations, but has no first-class continuation id — it returns a random `chatcmpl_...` id that means nothing to GuideAnts. Continuation instead relies on GuideAnts replaying the client's *entire* sent message history and matching it, message-for-message, against what it actually persisted (`WireConversationResolver.ResolveConversationFromTranscriptAsync` in the GuideAnts repo) — exact-string comparison, a 60-minute activity window, and a hard requirement that *exactly one* server-side conversation match (zero or multiple matches both silently start a brand-new conversation). Any drift between the client's held transcript and what GuideAnts actually persisted — a stray local message, or (worse) a streamed reply cancelled by a barge-in, where GuideAnts persists everything generated so far but the client only has what it received before cancelling — breaks that alignment and starts a new conversation, discarding all prior context, with no error raised.
- **The Responses endpoint** (used by this app now) returns an explicit `conversation: "conv_..."` id in every response, streaming included, and accepts it back as a request parameter. Continuation is then a simple, exact id lookup, not fuzzy transcript matching — it survives barge-in cancellations, concurrent similar-sounding calls, and any local bookkeeping differences, because none of that matters to how the conversation is found.

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
        welcomeGreetingInterruptible="none"
        reportInputDuringAgentSpeech="speech"
        events="speaker-events" />
    </Connect>
  </Response>
  ```
- `interruptible="none"` + `reportInputDuringAgentSpeech="speech"` together mean Twilio itself never pauses or stops TTS playback because of caller speech, but caller speech heard during agent speech is still transcribed and delivered to this app as a `prompt` message (instead of the `interrupt` message Twilio would send under `interruptible="speech"`). What this app does with that reported speech — ignore it, or cancel and restart the reply for it — is a decision made in `app.py`/`fillers.py`/`barge_in.py`; see "Filler phrases and mid-reply speech" and "Selective barge-in" below.
- `welcomeGreetingInterruptible="none"` — the welcome greeting's interruptibility is a **separate** attribute from `interruptible`, and defaults to interruptible. Before this was set, real calls showed Twilio cutting off the greeting and sending an `interrupt` message (with the greeting text as `utteranceUntilInterrupt`) whenever it detected caller-side audio during the greeting — including the greeting's own echo picked up from a speakerphone.
- `events="speaker-events"` subscribes to Twilio's notifications that the agent (TTS playback) or client (caller) started/stopped speaking. The agent-stopped event is the real "the reply finished playing" signal used to hold the reply task open (see "`start_reply()` / `respond_to()`" below); Twilio documents the subscription attribute but not the messages' JSON shape, so `speaker_events.py` recognizes them loosely and the app falls back to the word-count estimate until the first agent-stop is recognized on a call. The shape actually observed on live calls is `{"type": "info", "name": "agentSpeaking"|"clientSpeaking", "value": "on"|"off"}` — pinned in `test_speaker_events.py`.
- Response content type is `application/xml`. No request body is read — everything needed comes from the `Host` header and this app's own config.

### `WS /ws`

Twilio opens exactly one WebSocket connection here per call, immediately after `/twiml` returns, and keeps it open for the life of the call. All messages are JSON text frames.

**Per-connection state** (`CallState`, one instance per call — all local to the WS handler closure; nothing is shared across calls, nothing persists after disconnect):
- `guide: GuideSession` — the one piece of state that actually matters for memory: holds the `conversation_id` GuideAnts assigned on this call's first turn, echoed back on every later turn. See `guide_client.py` above.
- `messages: list[dict]` — a local log of what was actually said, for debugging only; never sent to GuideAnts.
- `interrupted_reply: str | None` — the text of a reply the caller was cut off mid-way through by a barge-in, if any; consumed and cleared by the next `start_reply()` call via `build_input()`. See "Interruption notes" below.
- `task` — the `asyncio.Task` currently generating/speaking a reply, if any; also doubles as the "is a reply active right now" flag (`st.task and not st.task.done()`). On turns 2+, deltas arrive continuously over SSE, but Twilio still plays TTS far slower than the deltas stream in — `respond_to()` doesn't let this task finish once generation ends; it holds the task open until Twilio's agent-stopped speaker event reports that playback actually finished (with the word-count estimate — `speech_timing.estimate_seconds`, paced by `config.TTS_WORDS_PER_SECOND` — as a ×1.5 + 2s ceiling on that wait), or, until the first such event has been recognized on the call, just sleeps out whatever's left of that same estimate. Either way the task stays "not done," and mid-reply speech still gets evaluated as mid-reply, for roughly as long as Twilio is actually still speaking.
- `playback_done: asyncio.Event` — set by the WS loop whenever an agent-stopped speaker event arrives; awaited by `respond_to()`'s playback hold. Cleared by `respond_to()` only at the start of the hold, so stale sets (the welcome greeting ending, or a filler finishing while GuideAnts was still generating) can't release a later hold early.
- `agent_stop_seen: bool` — `True` once any agent-stop speaker event has been recognized this call. Until then `respond_to()` paces on the estimate alone, so an account/edge whose speaker events never arrive (or arrive in a shape `speaker_events.classify` doesn't recognize) behaves exactly as before this feature.
- `partial_reply: str` — the real (GuideAnts-sourced) reply text streamed so far in the current turn, never including the filler. Reset to `""` at the start of every turn; read into `st.messages` and `st.interrupted_reply` if a trigger utterance cancels the turn before it finishes.
- `pending_text: str` / `pending_commit` — caller text transcribed but not yet committed as a turn, and the timer task that will commit it. Twilio finalizes a prompt at each brief pause, so one spoken turn can arrive as several prompt messages; these hold the fragments together until the caller has actually stopped talking. See "Turn-pause buffering" below.
- `client_speaking: bool` — whether the caller is currently speaking, per the clientSpeaking speaker events. Stays `False` if those events never arrive (or aren't recognized), so such a call degrades to the plain `TURN_PAUSE_SECONDS` debounce instead of misbehaving.

**Inbound message types** (sent by Twilio Conversation Relay):

| `type` | Key fields | Handling |
|---|---|---|
| `setup` | `callSid`, `from`, `to` | Logged only; no state change. First message on every connection. |
| `prompt` | `voicePrompt` (caller's transcribed speech) | If a reply *is* already streaming: `barge_in.should_interrupt()` checks whether this is a stop/wait phrase or a new question. If so, the in-flight reply is cancelled; a stop/wait phrase then just gets a local acknowledgment and silence, a new question starts a fresh reply for this utterance (see "Selective barge-in" below). Otherwise the text is just logged — not spoken, not acted on, not recorded anywhere. If no reply is streaming: text merging into an already-buffered turn skips further classification (a mid-turn fragment is a continuation, not noise); otherwise `fillers.is_backchannel()` catches pure acknowledgment noise (e.g. "ok", "yeah") and it's just logged, never recorded into `messages` either — this also covers the case where STT finishes transcribing a short "ok" just *after* the reply already finished. Anything else is buffered by `schedule_turn()` and committed as the caller's turn only after `TURN_PAUSE_SECONDS` of further silence (see "Turn-pause buffering" below); the commit calls `start_reply()`, which also decides via `fillers.looks_like_question()` whether to prepend a filler phrase. |
| `interrupt` | `utteranceUntilInterrupt` | Not expected given `interruptible="none"` — logged only, no state change. Caller speech during agent speech arrives as `prompt` instead (see above); Twilio itself never auto-pauses. |
| `dtmf` | `digit` | Logged only — not acted on (no IVR menu implemented; see SETUP.md's "not implemented" list). |
| `error` | `description` | Logged as an error. Connection is not closed by this app. |
| speaker events | undocumented by Twilio | Any type not listed above is run through `speaker_events.classify()`, which loosely recognizes the `agentSpeaking`/`clientSpeaking` start/stop notifications subscribed via `events="speaker-events"`. An agent-stop sets `st.agent_stop_seen` and `st.playback_done` (releasing `respond_to()`'s playback hold — see above). A client-start/stop updates `st.client_speaking` and re-arms the pending-turn commit timer if a turn is buffered: start holds the buffer open for the caller's continuation, stop gives that continuation's transcript `TURN_RESUME_GRACE_SECONDS` to arrive (see "Turn-pause buffering" below). Every recognized event is logged with its full payload, since Twilio doesn't document the shape and the log is how a mismatch with the classifier gets noticed. Because only unhandled types reach the classifier, a caller's `prompt` whose transcript mentions "agent speaking" can never match. |
| anything else | — | Logged as a warning (with the full payload), ignored. |

Non-JSON frames are logged and skipped rather than crashing the loop.

**Outbound message shape** (sent by this app to Twilio):
```json
{"type": "text", "token": "Hello there!", "last": false, "preemptible": true}
{"type": "text", "token": "", "last": true, "preemptible": true}
```
Every turn, including the call's first, is forwarded at whatever granularity GuideAnts' SSE stream actually emits — `respond_to()` sends one Twilio `text` frame per `response.output_text.delta` event, so the caller starts hearing the reply as soon as the first tokens arrive, without waiting for the whole answer. The filler phrase (sent as its own frame first, see below) still covers the gap before the first delta arrives. Verified live (2026-07-10, current GuideAnts build): a long reply arrives as ~120 incremental deltas spread over ~6.5s, first delta ~3.3s in. **Caveat: this depends on the deployed GuideAnts build being current** — an outdated `guideants-webapi-ui` image (pre-dating GuideAnts' wire-streaming fixes, or pre-dating the streamed `conversation` field) emits the entire reply as a single SSE burst after generation completes, regardless of which model the guide uses, which looks exactly like "streaming doesn't work"; an image that streams but doesn't yet echo `conversation` falls back to one non-streaming turn (see `guide_client.py`'s `stream_missing_conversation` above) before resuming streaming. If replies seem to arrive all at once, rebuild/update the GuideAnts container before blaming the model or this app; `check_streaming.py` at this repo's root prints per-delta timings, including turn 1, to check either way. Every frame carries `preemptible: true` — see "Selective barge-in" below for why.

### Turn-pause buffering (`schedule_turn()`)

Twilio finalizes a `prompt` at each pause in caller speech, so a caller who
takes a brief mid-sentence breath produces two prompts. Before this feature,
the first half was answered as the whole turn and the second half arrived
mid-reply and was ignored. Instead, every prompt that would start a new turn
goes through `schedule_turn()`, which appends the text to `st.pending_text`
and (re)arms a commit timer; when the timer fires, the buffered text is
committed as one turn via `start_reply()`. The timer's window depends on
what the caller is doing, per the `clientSpeaking` speaker events:

- **Caller quiet** (the normal case): `TURN_PAUSE_SECONDS` (default 0.5s) —
  the only latency this feature adds to an ordinary turn.
- **clientSpeaking-start arrives while text is buffered** — the caller
  resumed. This includes resuming *before* the first fragment's transcript
  even lands (the ordering actually observed on live calls: off, on, then
  the prompt), which is why `schedule_turn()` also checks
  `st.client_speaking` at buffer time. The commit is pushed out to a 10s
  ceiling (`PENDING_TURN_CEILING_SECONDS`), which only fires — with a
  warning — if the matching stop event is lost.
- **clientSpeaking-stop with text buffered**: re-armed to
  `TURN_RESUME_GRACE_SECONDS` (default 1.5s), since the continuation's
  transcript trails the stop event by STT finalization time. If the
  "resume" was just untranscribable noise, this is also what bounds the
  extra dead air before the buffered text is committed alone.

A prompt arriving while text is buffered merges into it and re-arms the
timer — even one that alone would look like a backchannel, since a mid-turn
fragment is a continuation, not noise. Stop/wait phrases are exempt from all
of this: the barge-in check still runs immediately per prompt, so "stop"
cuts playback with no added delay. A mid-reply trigger that is a *new
question* is scheduled through the same buffer after the old reply is
cancelled, so an interrupting question can also be spoken with pauses (the
old audio keeps playing up to `TURN_PAUSE_SECONDS` longer before the new
reply's frames preempt it).

If speaker events never arrive (or arrive in a shape
`speaker_events.classify` doesn't recognize), `st.client_speaking` stays
`False` and the whole feature degrades to a plain `TURN_PAUSE_SECONDS`
debounce — same graceful-degradation posture as the agent-stop playback
hold. On disconnect, the pending timer is cancelled *before* the reply task,
so it can't fire mid-teardown and start a reply nothing would cancel.

### `start_reply()` / `respond_to()` — the reply pipeline

`start_reply(user_text)` builds this turn's actual input via `build_input(user_text, st.interrupted_reply)` (folding in an interruption note if the previous reply was cut short — see "Interruption notes" below), clears `st.interrupted_reply`, logs `user_text` to `st.messages`, and spawns `respond_to(input_text, filler_eligible)` as an `asyncio.Task` stored on `st.task`, where `filler_eligible = fillers.looks_like_question(user_text)`:

1. Start `guide_client.stream_reply(input_text, st.guide)` and immediately begin fetching its first chunk as a background task (`gen.__anext__()`), rather than awaiting it directly.
2. If `filler_eligible` is true, race that fetch against `config.FILLER_DELAY_SECONDS` (`asyncio.wait(..., timeout=...)`). If GuideAnts hasn't responded by the time the timeout elapses, pick a random phrase from `config.FILLER_PHRASES` and send it immediately as its own spoken token: `{"type": "text", "token": filler + " ", "last": False, "preemptible": True}`. Either way (timed out or not), keep waiting on the *same* in-flight fetch afterward — nothing is restarted or duplicated. If `filler_eligible` is false, the fetch is simply awaited with no race and no filler, regardless of how long it takes.
3. Forward each resulting delta to the WS as its own `{"type": "text", ...}` frame as it arrives, accumulating them into `reply_text` (and `st.partial_reply`, kept current after every delta so a mid-stream barge-in has an accurate cut-off point), then send a final `{"token": "", "last": true}` frame to signal end-of-turn to Twilio.
4. **On success**, log the real reply to `st.messages` — the filler is never logged. Then hold the turn open until playback actually ends: wait for Twilio's agent-stopped speaker event (`st.playback_done`, with ×1.5 + 2s of the word-count estimate as a ceiling in case the event is lost), or — until the first agent-stop has been recognized on the call — just sleep out the remainder of the word-count estimate as the older versions did. This is what keeps `st.task` "not done" while Twilio is still speaking.
5. **On `asyncio.CancelledError`** (raised by `cancel_task()`, called either from the `finally` block on `WebSocketDisconnect`, or from the mid-reply barge-in branch when a trigger utterance cancels this turn — see "Selective barge-in" below): cancels the background chunk-fetch task, awaits it (suppressing the resulting `CancelledError`), then calls `await gen.aclose()` (also suppressing exceptions) so the underlying SSE HTTP response is definitely closed before the interrupting turn's own request goes out on the shared connection pool — then re-raises. `st.messages`/`st.interrupted_reply` bookkeeping for the cut-off reply is the barge-in caller's responsibility (see "Selective barge-in" below), not this handler's.
6. **On any other exception** (e.g. GuideAnts unreachable, HTTP error, a `response.failed`/`error` SSE event): logs the full traceback and sends a single spoken fallback line (`"Sorry, I'm having trouble right now."`) as a `last: true` frame, rather than leaving the caller in silence or crashing the WS loop. `st.messages` is left as it was before the failed attempt, and `st.guide.conversation_id` is untouched — if GuideAnts had already started persisting the turn server-side before the error, the next turn still continues that same conversation.

### Filler phrases and mid-reply speech

1. **While a reply is streaming, non-trigger speech.** `barge_in.should_interrupt()` calls `fillers.looks_like_question()` on every mid-reply utterance to classify it (see "Selective barge-in" below for exactly what counts as a trigger); if it comes back false and the utterance also isn't a stop/wait phrase, nothing further happens: not spoken, not cancelled, not recorded anywhere, and no filler is picked. The current reply keeps playing to its end exactly as if the caller had stayed silent, and the utterance itself is gone: it is never replayed to GuideAnts as context on a later turn.
2. **While a reply is streaming, trigger speech.** See "Selective barge-in" below — the in-flight reply is cancelled; a stop/wait phrase gets a local acknowledgment and silence, a new question starts a fresh reply immediately for the new utterance.
3. **Late backchannel, after the reply already finished.** Twilio's speech-to-text can finish transcribing a short utterance like "ok" slightly *after* the reply (and its playback-end hold — the agent-stopped speaker event or the estimate fallback, see above) has actually finished, so by the time the `prompt` arrives `st.task.done()` is already `True` — it no longer looks like "mid-reply" at all. To stop this from being treated as a brand-new question, `fillers.is_backchannel(text, config.EXTRA_BACKCHANNEL_PHRASES)` checks whether the whole utterance is pure acknowledgment noise (`fillers.BACKCHANNEL_PHRASES`: "ok", "okay", "yeah", "mmhmm", "got it", ... plus anything in the env-configurable extra list). If so, it's just logged ("Ignored backchannel utterance (not acted on)") — never sent to GuideAnts, never logged to `st.messages`: it's genuinely noise, not part of the conversation.
4. **Starting a real reply.** Otherwise, `start_reply(text)` runs: it logs the caller's text to `st.messages` and checks `fillers.looks_like_question(text)` — true for text ending in `?`, or starting (after stripping leading fillers like "um"/"okay"/"so") with an interrogative word (`what`, `how`, `can`, `is`, ...) or a request verb (`tell`, `find`, `help`, ...), or a lead-in phrase like "i need"/"i want"/"looking for". This result (`filler_eligible`) only decides whether a filler is a *candidate* — the filler itself is only actually spoken if GuideAnts also hasn't replied within `config.FILLER_DELAY_SECONDS` (see "`start_reply()` / `respond_to()`" above). So a filler-eligible question that GuideAnts answers quickly gets no filler, and a non-eligible utterance (e.g. "thank you") never gets one no matter how slow GuideAnts is.

On `WebSocketDisconnect`, any in-flight task is cancelled and the loop exits — nothing is persisted, so a dropped call simply forgets the conversation.

### Selective barge-in

`interruptible` stays `"none"` — Twilio itself never pauses or stops
playback on its own. Instead, `app.py` decides, per mid-reply `prompt`,
whether to cut the reply over using `barge_in.should_interrupt(text,
config.EXTRA_STOP_PHRASES)`:

Both cases below start by cancelling the in-flight reply (`cancel_task()`)
and, if any reply text had been sent so far this turn (`st.partial_reply` —
never including the filler), logging it to `st.messages` and remembering it
as `st.interrupted_reply` (see "Interruption notes" below). What happens
next differs:

- **Stop/wait phrase** (`barge_in.is_stop_command()` — "stop", "wait", "hold
  on", "no", ... plus `EXTRA_STOP_PHRASES`) → GuideAnts is *not* called. A
  random phrase from `config.STOP_ACK_PHRASES` (e.g. "Okay.") is sent as a
  single preemptible frame instead, then the turn ends there — no
  `start_reply()`. `st.interrupted_reply` stays set, and is picked up by
  whatever real question the caller asks next.
- **A new question** (`fillers.looks_like_question()`, and not itself a stop
  phrase) → the new utterance is scheduled exactly as if it were a fresh
  prompt (`schedule_turn()` — so it too can be spoken with brief pauses, see
  "Turn-pause buffering" above), and the reply that starts once it commits
  consumes `st.interrupted_reply` via `build_input()`.
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
persisted server-side for an aborted stream, nor of what the caller actually
*heard* — there's no Twilio-side "what was actually heard" signal available
here (unlike a native `interrupt` event's `utteranceUntilInterrupt`), so this
can't be made fully precise from the client. See "Interruption notes" below
for how this imprecision plays out.

### Interruption notes: how they work and what could go wrong

When a barge-in cuts a reply short, the next turn's input is prefixed with a
note telling the guide what the caller actually heard, so it can pick up
naturally instead of repeating itself or guessing. The mechanism:

1. On a barge-in that trims a cut-off reply, `st.interrupted_reply` is set to
   `st.partial_reply` (the text streamed so far this turn).
2. The next call to `start_reply(user_text)` builds this turn's actual input
   via `guide_client.build_input(user_text, st.interrupted_reply)`, which
   (if `interrupted_reply` is set) prefixes something like:
   `[Note: your previous reply was interrupted; the caller heard only up to: "…{last ~150 chars}"] {user_text}`
   — then clears `st.interrupted_reply`.
3. That combined string is what's actually sent to GuideAnts as `input`;
   `st.messages` still logs the caller's plain utterance, not the note.

**Known rough edges, deliberately accepted for this demo:**

1. **The note becomes part of the persisted turn.** GuideAnts stores
   `input` as the user's message for that turn, so the note shows up
   verbatim in the GuideAnts conversation UI as if the caller had said it.
2. **The guide may narrate the interruption out loud** (e.g. "Before you cut
   me off, I was saying…"). If this is observed in testing, fix it with an
   instruction in the guide's system prompt (e.g. "if a message starts with
   a `[Note: ...]` bracket, use it silently — never quote or acknowledge it
   in your reply"), not with middleware changes.
3. **`partial_reply` measures text sent to Twilio, not audio actually
   heard.** TTS playback lags behind the text frames `respond_to()` sends,
   so the note likely overstates how much the caller actually heard before
   the audio cut over. Twilio's own `utteranceUntilInterrupt` (sent on a
   native `interrupt` message) would be the accurate signal, but it's not
   available here — this app uses `interruptible="none"` with per-frame
   `preemptible` cutover instead of Twilio-native interruption (see above),
   so `interrupt` messages are never sent.
4. **The inverse case produces no note at all.** If a barge-in lands during
   the *playback hold* (generation already finished, `st.partial_reply`
   already cleared, only trailing audio still playing when cut off), there's
   no way for `app.py` to know the caller missed the tail end — the guide
   will believe the caller heard the whole reply.
5. **Long partials are truncated to their last ~150 characters** before
   being quoted, so the note may start mid-sentence.
6. **The note only has a real window to fire while text is still
   streaming in.** With a current GuideAnts build, deltas arrive
   incrementally over several seconds (see "Outbound message shape" above),
   so a mid-generation barge-in genuinely captures a partial reply. But on
   a deployment that emits the whole reply as one SSE burst (e.g. an
   outdated GuideAnts image — same section), a barge-in almost always
   either lands before any text has arrived (`partial_reply` still empty)
   or after the whole reply already arrived and was cleared during the
   post-generation playback hold — both produce no note, same as rough
   edge #4.

---

## Reservation API (reservations_api.py, reservations.py, booqable_client.py)

A second, independent inbound surface on the same app/port: GuideAnts calls
`/api/reservations/*` as a tool (via its imported OpenAPI schema,
`guide-demo/booqable-reservations-openapi.json`) to check availability and
book rentals in Booqable, and `/api/booqable/ping` as a manual connectivity
check. None of this touches the Twilio WS path — it's plain request/response
FastAPI routes, no streaming, no per-call state.

```
GuideAnts (tool call) ⇄ this app (/api/reservations/*) ⇄ Booqable JSON:API v4
```

- **`reservations_api.py`** — the router: request/response models, the
  `require_receptionist_key` dependency, and the four
  `/api/reservations/*` routes plus `/api/booqable/ping`. Mounted in
  `app.py` via `app.include_router(reservations_router)`.
- **`reservations.py`** — the actual find/check/book/reserve logic against a
  `BooqableClient`: `list_catalog`, `check_product_availability`,
  `find_or_create_customer`, `create_reservation`, `cancel_reservation`, plus
  small helpers for resolving the account's one active location and mapping
  a product group to its bookable product.
- **`booqable_client.py`** — a thin async `httpx` wrapper around Booqable's
  JSON:API v4 (`{company_url}/api/4`), Bearer-token auth from
  `config.BOOQABLE_API_KEY`, plus `resource()`/`attrs()` helpers for building
  and reading JSON:API envelopes.

**Auth**: the four `/api/reservations/*` routes require an `X-Api-Key` header
matching `config.RECEPTIONIST_API_KEY` — deliberately a *different* secret
from `BOOQABLE_API_KEY`, so the LLM calling this API can never obtain the
real Booqable key. `/api/booqable/ping` is unauthenticated (it only reports
whether the key is configured and the account's timezone), same trust level
as the already-unauthenticated `/twiml`.

**Config**: `config.py` reads `BOOQABLE_COMPANY_URL`, `BOOQABLE_API_KEY`,
`RECEPTIONIST_API_KEY`, and `BOOQABLE_TIMEZONE` (naive `starts_at`/`stops_at`
values from the guide are interpreted in this timezone before converting to
UTC for Booqable) — same pattern as every other setting in this app, plain
module constants read once from `.env`.

**Origin**: this logic was ported from a separate `AI_Receptionist_seed_data`
project's backend, which also has a seed console (`/api/seed`, `/api/plan`,
etc.) for populating demo data in Booqable — that console was deliberately
*not* ported here; it's an occasional data-setup tool, not part of the live
call path, and stays in that project.

---

## The GuideAnts endpoint this app depends on

`guide_client.py` calls **`POST {GUIDEANTS_BASE_URL}/api/published/openai/{GUIDEANTS_PUB_ID}/v1/responses`** — GuideAnts' OpenAI-wire-compatible Responses endpoint (implemented server-side in `PublishedOpenAiChatWireHandler.PostResponsesAsync`, routed via `PublishedOpenAiWireEndpoints`, GuideAnts repo). Relevant contract details:

- **Auth**: `Authorization: Bearer <GUIDEANTS_API_KEY>` header (the `openai` SDK adds this automatically from `api_key=`). GuideAnts also accepts `x-guideants-apikey` or anonymous access, depending on how the published guide's auth mode was configured (see SETUP.md step 1.4).
- **Request body**: `{"model": "guide", "input": "<latest utterance>", "conversation": "conv_...", "stream": true|false}`. `model` must match one of the alias `id`s returned by `GET .../v1/models` (normally the fixed alias `"guide"`). `input` is just the current turn's text — not a message array, not a resent transcript. `conversation` is present on every request once a call has one; on the very first turn of a call it's simply omitted (there is nothing to send yet).
- **Continuation**: this endpoint accepts either a `conversation` id or a `previous_response_id` to resume an existing server-side conversation (this app always uses `conversation`); if neither is supplied, GuideAnts falls back to the same fragile transcript-matching used by chat/completions (see "Why this endpoint and not `/invoke` or chat/completions" above) — this app avoids that path entirely by always sending `conversation` once it has one.
- **Non-streaming response** (`stream: false`, used by this app only as the `stream_missing_conversation` fallback against an older GuideAnts build): a single JSON object —
  ```json
  {
    "id": "resp_<assistantMessageId>",
    "conversation": "conv_<notebookConversationId>",
    "object": "response",
    "status": "completed",
    "model": "guide",
    "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "..."}]}],
    "usage": {"input_tokens": ..., "output_tokens": ..., "total_tokens": ...}
  }
  ```
  `response.conversation` here is the durable continuation handle `guide_client.py` captures into `GuideSession.conversation_id`. The openai SDK also exposes the concatenated text directly as `response.output_text`.
- **Streaming response** (`stream: true`, used on every turn including the first): `text/event-stream`, typed events —
  `response.created` → `response.output_item.added` → `response.content_part.added` → repeated `response.output_text.delta` (the actual token text, in `.delta`) → `response.output_text.done` → `response.output_item.done` → `response.completed`. On a current GuideAnts build, both the `response.created` and `response.completed` events' embedded `response` object carry the same `conversation` field as the non-streaming body — `guide_client.py` reads it off whichever of those two events arrives first with the session not yet having an id. An older GuideAnts build whose stream predates this omits the field entirely; see the `stream_missing_conversation` fallback in `guide_client.py` above.
- **Tool calls**: the endpoint also supports OpenAI-style `tools`/client-side tool execution (emitted as `function_call` output items) — unused here since the receptionist guide doesn't define any tools today.
- **Errors this app handles specially**: HTTP 400 with `code: "conversation_not_found"` or `code: "invalid_conversation_id"` — GuideAnts no longer recognizes the `conversation` id sent (e.g. it restarted and lost in-memory/db state). `guide_client.stream_reply` catches this, clears the session, and retries once as a fresh conversation (no recap replay — prior context for that call is lost; see "Known gaps" below).
- **Other errors**: e.g. `403 endpoint_disabled` if the guide's "Enable Wire API" / **"Responses"** toggle isn't turned on in the Publish dialog (see SETUP.md step 1.5 — note this is a different checkbox from "Chat Completions").

`GET {GUIDEANTS_BASE_URL}/api/published/openai/{pubId}/v1/models` is the companion read-only endpoint used manually (not by this app's code) to discover the valid `model` alias values before filling in `.env`.

---

## Full call sequence

1. Caller dials the Twilio number.
2. Twilio POSTs to `/twiml`. App returns `<Connect><ConversationRelay url="wss://.../ws" .../></Connect>`.
3. Twilio opens the WS, speaks `WELCOME_GREETING` to the caller immediately (handled entirely by Twilio, not by this app), then sends `setup`.
4. Caller speaks. Twilio transcribes it and sends `prompt` with `voicePrompt`.
   One spoken turn can arrive as several prompts (Twilio finalizes at each
   pause), so `schedule_turn()` buffers them and commits the merged text as
   the turn only after `TURN_PAUSE_SECONDS` of caller silence, holding
   longer if the clientSpeaking speaker events say the caller resumed — see
   "Turn-pause buffering" above.
5. On commit, `app.py` logs it to `messages`, builds this turn's input via `build_input()` (folding in an interruption note if the previous reply was cut short), and calls `guide_client.stream_reply`. If the utterance looks like a question/request (`fillers.looks_like_question()`) and GuideAnts hasn't replied within `config.FILLER_DELAY_SECONDS`, a random filler phrase is sent as its own spoken token while still waiting on the same in-flight call, masking the wait. Every turn, including the call's first, streams in as many small deltas as GuideAnts emits, each forwarded to Twilio as its own frame as soon as it arrives (capturing the conversation id off the first `response.created`/`response.completed` event on turns that don't have one yet). Twilio speaks it via TTS, with `interruptible="none"` so nothing Twilio hears from the caller during this stops playback.
6. If the caller talks during the reply, Twilio still transcribes it and sends it as another `prompt` (`report_input_during_agent_speech="speech"`) rather than an `interrupt`. If it's a stop/wait phrase (`barge_in.is_stop_command()`), the in-flight reply is cancelled and a short local acknowledgment is spoken instead — no GuideAnts call. If it's a new question, the in-flight reply is cancelled and the question is scheduled as a fresh turn through the same turn-pause buffer (repeat from step 4). Either way, the reply text streamed so far is remembered as `st.interrupted_reply` for the next real question. Otherwise (non-trigger speech) the current reply keeps playing to the end and the utterance is just logged.
7. Once the reply finishes normally, the real reply is logged to `messages` (the filler, if any, is never logged). `messages` grows for the life of the call as a debug record only — GuideAnts' own memory of the conversation lives server-side, keyed by `st.guide.conversation_id`.
8. Repeat from step 4 for each new turn. Non-trigger speech heard mid-reply (step 6) is never recorded anywhere and is not automatically revisited — if it was itself a real question, it is only answered if the caller asks it again after the current reply finishes.
9. Caller hangs up → WS disconnects → in-flight task is cancelled, local connection state is discarded. (The conversation itself remains in GuideAnts; only this app's handle to it — `st.guide.conversation_id` — is lost, so a later call, even from the same caller, always starts a new conversation.)

## Known gaps (intentionally out of scope today)

From SETUP.md's "optional hardening" list — not implemented, not required for the demo to work:
- No `X-Twilio-Signature` validation on `/twiml` (any request to that URL is trusted).
- No handling of Twilio `end`/handoff messages (e.g. transfer to a human).
- No silence timeout / re-prompt if the caller goes quiet.
- `dtmf` digits are logged but never acted on — no keypad menu.
- If GuideAnts loses track of a conversation mid-call (restart, expiry — see "The GuideAnts endpoint this app depends on" above), the fallback starts a brand-new conversation with **no recap** of what was said earlier in the call. The guide won't remember anything from before the reset; a caller who'd already explained their situation would have to repeat it. Replaying a summary from `st.messages` into the fresh conversation's first turn would fix this but was deliberately left out — this failure mode is mostly a dev-environment concern (a live GuideAnts restart mid-call), not something expected in normal operation.
- Against an older GuideAnts build whose streamed events don't carry `conversation` yet: the very first turn of a call streams with no way to capture a continuation handle, so that turn's server-side conversation is orphaned (the client has no id for it). `stream_missing_conversation` catches this after the fact, and the *next* turn falls back to one non-streaming call, which starts (and captures the id of) yet another fresh conversation — so the first turn's context is lost, same as the lost-conversation case above. Every turn after that streams and continues normally. This only happens once per call, on the first turn, against a build old enough to lack the field — see `guide_client.py` above.
- See "Interruption notes" above for the known rough edges of the barge-in note-folding feature specifically.
