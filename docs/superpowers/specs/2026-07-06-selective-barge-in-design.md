# Selective barge-in (keyword/question-triggered interruption)

## Context

`app.py` currently configures Conversation Relay with `interruptible="none"`:
caller speech never stops TTS playback. Speech that arrives while a reply is
in flight is transcribed (`report_input_during_agent_speech="speech"`) but
only logged, never acted on — see the module docstring in `app.py` and
`fillers.py`.

An earlier version of this app (`barge_in.py`, removed in the "please wait
phrases" commit) took a different approach: `interruptible="speech"` made
Twilio pause TTS on *any* caller speech, and the app then classified the
follow-up transcript as a stop command / question (cancel + restart) or
anything else (resume from where Twilio paused). That required a
pause/resume gate, an auto-resume timer, and diffing sent-vs-heard text to
resume mid-sentence — reverted in favor of the simpler filler-based design.

This spec reintroduces selective interruption, but only for a bounded set of
trigger utterances (stop/wait phrases and questions), and without
reintroducing Twilio-native pausing or resume machinery: `interruptible`
stays `"none"`, and the app itself decides when to cut off playback.

## Goals

- A caller saying a stop/wait phrase ("stop", "wait", "hold on", "no", ...)
  or asking a new question while the assistant is mid-reply cuts off the
  current reply and starts a fresh one for what they just said.
- Plain statements, backchannel ("ok", "yeah"), and noise during a reply
  continue to be ignored, exactly as today.
- No change to Twilio-native barge-in behavior (`interruptible="none"`
  stays); Twilio never auto-pauses on its own.

## Non-goals

- Resuming a paused reply from where it left off (the old `split_spoken`
  behavior). A trigger always fully cancels and restarts; there is no
  partial-resume path.
- Perfect history alignment with GuideAnts on a cancelled stream. See
  "History bookkeeping" below — this is inherently best-effort.

## Design

### 1. `barge_in.py` (new file, trimmed from the old removed version)

Pure, I/O-free classifier, no Twilio/GuideAnts knowledge — mirrors the role
`fillers.py` already plays for filler phrases.

```python
STOP_PHRASES = frozenset({"stop", "wait", "hold on", "hang on", "hold up",
    "one moment", "one second", "just a second", "just a moment", "pause",
    "shut up", "be quiet", "quiet", "enough", "that's enough", "never mind",
    "nevermind", "excuse me", "no", "no no", "stop talking", "listen"})

def is_stop_command(text: str, extra_phrases: Iterable[str] = ()) -> bool: ...

def should_interrupt(text: str, extra_phrases: Iterable[str] = ()) -> bool:
    """True if this utterance should cut off an in-flight reply."""
    return is_stop_command(text, extra_phrases) or fillers.looks_like_question(text)
```

`is_stop_command` reuses the same normalize/strip-leading-fillers helpers the
old version had (front-anchored phrase match after stripping "um", "so",
"okay", etc.). The question half of `should_interrupt` deliberately reuses
`fillers.looks_like_question` rather than duplicating a second, narrower
question detector — the same bar used to decide "does a fresh utterance
deserve a filler" is used to decide "does a mid-reply utterance deserve an
interrupt."

### 2. `app.py` — `prompt` handler, mid-reply branch

Today (lines ~147-167), any prompt while `st.task` is active just logs and
drops the text. New behavior for that branch only:

- `fillers.is_backchannel(text, ...)` → unchanged: log and ignore.
- `barge_in.should_interrupt(text, config.EXTRA_STOP_PHRASES)` → **trigger**:
  1. Cancel the in-flight task (`cancel_task()`).
  2. If any partial reply text had already been sent this turn, append it to
     `st.messages` as the assistant's message (see bookkeeping below).
  3. Call `start_reply(text)` exactly as for a fresh prompt — it goes through
     the normal filler-then-reply pipeline for the new utterance.
- Anything else → unchanged: log and ignore.

The prompt-while-idle branch (`st.task` is `None` or done) is untouched.

### 3. Cutting off audio: `preemptible`

`respond_to()` marks the first frame it sends in a turn with
`"preemptible": true` (filler frame if there is one, otherwise the first
reply delta). This is a no-op when nothing else is playing (the normal,
non-interrupting case). When it follows a just-cancelled turn, it tells
Twilio to drop whatever's still queued/playing for the old turn and switch
to this audio immediately.

No TwiML changes: `interruptible` stays `"none"`, `report_input_during_agent_speech`
stays `"speech"`.

### 4. History bookkeeping

`CallState` gains a way to track text accumulated so far in the current
turn (equivalent to the old `cycle_text`, without `cycle_base`/resume
complexity since we never resume). On a trigger-cancelled turn, that
accumulated text — if non-empty — is appended to `st.messages` as the
assistant's reply before the new user turn is appended, mirroring the old
code's behavior for its "stop-worthy prompt arrives mid-reply" case.

Caveat, called out in code comments: this is our best local approximation
of "what the caller actually heard," not a guarantee of what GuideAnts
persisted server-side for an aborted stream. GuideAnts alignment on this
specific edge case (client cancels the HTTP stream early) is not something
this client can fully control — same limitation the old implementation had
(it approximated with Twilio's `utteranceUntilInterrupt`, which we don't
have here since we never trigger a native Twilio `interrupt`).

### 5. Config

New `EXTRA_STOP_PHRASES` env var, comma-separated, same pattern as
`EXTRA_BACKCHANNEL_PHRASES`: extra phrases beyond the built-in `STOP_PHRASES`
that should also trigger an interrupt.

### 6. Testing

- Add `pytest` to `requirements.txt`.
- `test_barge_in.py`: unit tests for `is_stop_command` and `should_interrupt`
  (pure functions, no I/O) — leading-filler stripping, extra phrases,
  question passthrough, negative cases (backchannel/statement should not
  trigger).
- `app.py`'s WebSocket wiring remains untested, consistent with the rest of
  the app today.

## Open risk (accepted)

If GuideAnts' server-side generation for a cancelled request continues and
persists a full assistant turn despite the client aborting the stream, our
locally-recorded partial text will diverge from what GuideAnts actually
persisted, and the *next* turn's history-alignment check
(`WireConversationResolver.ResolveConversationFromTranscriptAsync`) could
fail to match, starting a new GuideAnts-side conversation. This risk already
existed conceptually in the previous barge-in implementation and is not
newly introduced or solvable from the client side; not blocking this spec.
