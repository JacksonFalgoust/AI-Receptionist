# Selective Barge-In Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a caller's stop/wait phrase or new question, spoken while the assistant is mid-reply, cancel the in-flight reply and immediately start answering the new utterance instead — while everything else said mid-reply (statements, backchannel, noise) continues to be ignored exactly as it is today.

**Architecture:** Twilio's TwiML config is unchanged (`interruptible="none"`, `report_input_during_agent_speech="speech"` in `app.py`) — Twilio itself never auto-pauses on caller speech. A new pure-function classifier module, `barge_in.py`, decides whether a transcript heard mid-reply should trigger an interrupt. When it does, `app.py`'s WebSocket handler cancels the in-flight reply task and starts a fresh one for the new utterance. Playback is actually cut off using Conversation Relay's `preemptible` flag on outgoing `text` frames — confirmed via Twilio's docs that `preemptible: true` must be set on the *currently playing* turn's own frames (not the new turn's), since it declares "this playback may be replaced by whatever comes after it." So every frame `respond_to()` sends gets `preemptible: true` unconditionally; this is a no-op in the normal (non-interrupting) case and is what lets a later interrupting turn cut off a still-playing one.

**Tech Stack:** Python 3, FastAPI, `pytest` (new dev dependency for this feature — no test framework exists in the repo yet).

## Global Constraints

- No TwiML/`interruptible` attribute changes — stays `"none"` (per spec's "Non-goals").
- `barge_in.py` must be pure / I/O-free, matching `fillers.py`'s existing style (no Twilio/GuideAnts knowledge, unit-testable in isolation).
- `should_interrupt`'s question-detection must reuse `fillers.looks_like_question` rather than duplicating a second question classifier (per spec section 1).
- `st.messages` must never contain filler text or unresolved/backchannel utterances — only real user prompts and real (GuideAnts-sourced) assistant text, matching the existing invariant documented in `app.py`'s module docstring. On an interrupt-cancelled turn, only the *real reply* text streamed so far (never the filler) is appended.
- New env var: `EXTRA_STOP_PHRASES`, comma-separated, same parsing pattern as the existing `EXTRA_BACKCHANNEL_PHRASES` in `config.py`.
- This project has no venv committed but `.gitignore` already expects one at `.venv/` (and already ignores `.pytest_cache/`) — create it locally, don't commit it.

---

## Current relevant code (for reference — do not re-derive, just read)

`app.py`'s `prompt` handler today (mid-reply branch always logs and ignores):

```python
            elif msg_type == "prompt":
                text = msg.get("voicePrompt", "") or ""
                if text.strip():
                    if st.task and not st.task.done():
                        logger.info("Ignored caller speech during active reply (not acted on): %r", text)
                    elif fillers.is_backchannel(text, config.EXTRA_BACKCHANNEL_PHRASES):
                        logger.info("Ignored backchannel utterance (not acted on): %r", text)
                    else:
                        start_reply(text)
```

`app.py`'s `respond_to`/`start_reply`/`CallState` today:

```python
@dataclass
class CallState:
    messages: list = field(default_factory=list)
    task: object = None  # asyncio.Task | None


    async def respond_to(filler: str | None) -> None:
        reply_text = ""
        try:
            if filler:
                await websocket.send_json({"type": "text", "token": filler + " ", "last": False})
            async for delta in stream_reply(st.messages):
                await websocket.send_json({"type": "text", "token": delta, "last": False})
                reply_text += delta
            await websocket.send_json({"type": "text", "token": "", "last": True})
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Error while streaming guide reply")
            try:
                await websocket.send_json(
                    {
                        "type": "text",
                        "token": "Sorry, I'm having trouble right now.",
                        "last": True,
                    }
                )
            except Exception:
                pass
            return
        if reply_text:
            st.messages.append({"role": "assistant", "content": reply_text})

    def start_reply(user_text: str) -> None:
        st.messages.append({"role": "user", "content": user_text})
        filler = fillers.pick(config.FILLER_PHRASES) if fillers.looks_like_question(user_text) else None
        st.task = asyncio.create_task(respond_to(filler))

    async def _cancel_and_await(task) -> None:
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def cancel_task() -> None:
        t, st.task = st.task, None
        await _cancel_and_await(t)
```

`config.py`'s existing `EXTRA_BACKCHANNEL_PHRASES` (the pattern to copy):

```python
EXTRA_BACKCHANNEL_PHRASES = [
    p.strip().lower()
    for p in os.environ.get("EXTRA_BACKCHANNEL_PHRASES", "").split(",")
    if p.strip()
]
```

`fillers.py`'s `looks_like_question` signature (consumed by `barge_in.py`): `looks_like_question(text: str) -> bool`.

---

### Task 1: `barge_in.py` — stop-command classifier + tests

**Files:**
- Create: `barge_in.py`
- Create: `test_barge_in.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `barge_in.STOP_PHRASES: frozenset[str]`, `barge_in.is_stop_command(text: str, extra_phrases: Iterable[str] = ()) -> bool`.

- [ ] **Step 1: Set up a venv and install dependencies + pytest**

```bash
cd "/Users/jacksonfalgoust/Documents/Internship/Twillio Demo"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

- [ ] **Step 2: Add `pytest` to `requirements.txt`**

Append this line to `requirements.txt`:

```
pytest>=8.0
```

Then run:

```bash
pip install pytest>=8.0
```

- [ ] **Step 3: Write the failing tests for `is_stop_command`**

Create `test_barge_in.py`:

```python
import barge_in


def test_is_stop_command_matches_bare_phrase():
    assert barge_in.is_stop_command("stop") is True


def test_is_stop_command_strips_punctuation_and_case():
    assert barge_in.is_stop_command("Stop.") is True


def test_is_stop_command_strips_leading_fillers():
    assert barge_in.is_stop_command("okay stop") is True


def test_is_stop_command_matches_multiword_phrase_prefix():
    assert barge_in.is_stop_command("hold on a second") is True


def test_is_stop_command_matches_phrase_followed_by_more_words():
    assert barge_in.is_stop_command("wait a second") is True


def test_is_stop_command_false_for_unrelated_text():
    assert barge_in.is_stop_command("what time do you close") is False


def test_is_stop_command_false_for_empty_text():
    assert barge_in.is_stop_command("") is False


def test_is_stop_command_checks_extra_phrases():
    assert barge_in.is_stop_command("cancel please", extra_phrases=["cancel"]) is True
    assert barge_in.is_stop_command("cancel please") is False
```

- [ ] **Step 4: Run tests to verify they fail**

```bash
cd "/Users/jacksonfalgoust/Documents/Internship/Twillio Demo"
source .venv/bin/activate
pytest test_barge_in.py -v
```

Expected: `ModuleNotFoundError: No module named 'barge_in'` (or collection error) — `barge_in.py` doesn't exist yet.

- [ ] **Step 5: Create `barge_in.py` with `STOP_PHRASES` and `is_stop_command`**

```python
"""Heuristics for selective barge-in.

Decides whether a caller's utterance heard while a reply is already
streaming should cancel and restart it (a stop/wait command, or a new
question -- see `should_interrupt`) versus be ignored (backchannel,
statement, noise). Pure functions only, no I/O, no Twilio/GuideAnts
knowledge -- mirrors the role fillers.py plays for the filler-phrase
feature. Used by app.py's `prompt` handler.
"""

import re
import string
from typing import Iterable

STOP_PHRASES = frozenset(
    {
        "stop",
        "wait",
        "hold on",
        "hang on",
        "hold up",
        "one moment",
        "one second",
        "just a second",
        "just a moment",
        "pause",
        "shut up",
        "be quiet",
        "quiet",
        "enough",
        "that's enough",
        "never mind",
        "nevermind",
        "excuse me",
        "no",
        "no no",
        "stop talking",
        "listen",
    }
)

# Stripped from the front before the stop-phrase check, so "okay stop" is
# evaluated as "stop".
LEADING_FILLERS = frozenset(
    {"um", "uh", "er", "ah", "okay", "ok", "so", "well", "hey", "yeah", "like", "oh"}
)

_PUNCT_TABLE = str.maketrans("", "", string.punctuation)
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    text = text.lower().translate(_PUNCT_TABLE)
    return _WHITESPACE_RE.sub(" ", text).strip()


def _strip_leading_fillers(words: list) -> list:
    i = 0
    while i < len(words) and words[i] in LEADING_FILLERS:
        i += 1
    return words[i:]


def is_stop_command(text: str, extra_phrases: Iterable[str] = ()) -> bool:
    """True if the utterance is a command to stop/pause talking."""
    words = _strip_leading_fillers(_normalize(text).split())
    if not words:
        return False
    normalized = " ".join(words)
    phrases = STOP_PHRASES | frozenset(extra_phrases)
    return any(
        normalized == phrase or normalized.startswith(phrase + " ") for phrase in phrases
    )
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest test_barge_in.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add barge_in.py test_barge_in.py requirements.txt
git commit -m "Add barge_in.is_stop_command classifier with tests"
```

---

### Task 2: `barge_in.should_interrupt` — combine stop-command + question detection

**Files:**
- Modify: `barge_in.py`
- Modify: `test_barge_in.py`

**Interfaces:**
- Consumes: `fillers.looks_like_question(text: str) -> bool` (existing).
- Produces: `barge_in.should_interrupt(text: str, extra_phrases: Iterable[str] = ()) -> bool`.

- [ ] **Step 1: Write the failing tests**

Append to `test_barge_in.py`:

```python
def test_should_interrupt_true_for_stop_command():
    assert barge_in.should_interrupt("stop") is True


def test_should_interrupt_true_for_question():
    assert barge_in.should_interrupt("what time do you close") is True


def test_should_interrupt_true_for_question_mark():
    assert barge_in.should_interrupt("are you open on Sundays?") is True


def test_should_interrupt_false_for_statement():
    assert barge_in.should_interrupt("I think that's fine") is False


def test_should_interrupt_false_for_backchannel_like_text():
    assert barge_in.should_interrupt("okay yeah") is False


def test_should_interrupt_passes_through_extra_phrases():
    assert barge_in.should_interrupt("cancel please", extra_phrases=["cancel"]) is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest test_barge_in.py -v
```

Expected: `AttributeError: module 'barge_in' has no attribute 'should_interrupt'`.

- [ ] **Step 3: Add `should_interrupt` to `barge_in.py`**

Add the import at the top of `barge_in.py` (with the other imports):

```python
import fillers
```

Add this function at the end of `barge_in.py`:

```python
def should_interrupt(text: str, extra_phrases: Iterable[str] = ()) -> bool:
    """True if this utterance, heard mid-reply, should cancel and restart it."""
    return is_stop_command(text, extra_phrases) or fillers.looks_like_question(text)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest test_barge_in.py -v
```

Expected: all 14 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add barge_in.py test_barge_in.py
git commit -m "Add barge_in.should_interrupt combining stop commands and questions"
```

---

### Task 3: Wire the interrupt into `app.py` + `config.py`

**Files:**
- Modify: `config.py`
- Modify: `.env.example`
- Modify: `app.py`

**Interfaces:**
- Consumes: `barge_in.should_interrupt(text, extra_phrases=()) -> bool` (Task 2).
- Produces: `config.EXTRA_STOP_PHRASES: list[str]`; `CallState.partial_reply: str` (new field, tracks the real-reply text streamed so far this turn, reset at the start of every `start_reply`).

- [ ] **Step 1: Add `EXTRA_STOP_PHRASES` to `config.py`**

Add this to `config.py`, directly after the existing `EXTRA_BACKCHANNEL_PHRASES` block:

```python
# Extra phrases (beyond barge_in.STOP_PHRASES) that should also cancel and
# restart an in-flight reply when heard mid-reply.
EXTRA_STOP_PHRASES = [
    p.strip().lower()
    for p in os.environ.get("EXTRA_STOP_PHRASES", "").split(",")
    if p.strip()
]
```

- [ ] **Step 2: Verify `config.py` still imports cleanly**

```bash
cd "/Users/jacksonfalgoust/Documents/Internship/Twillio Demo"
source .venv/bin/activate
python -c "import config; print(config.EXTRA_STOP_PHRASES)"
```

Expected: `[]` (no error).

- [ ] **Step 3: Document the new env var in `.env.example`**

Add this block to `.env.example`, directly after the existing `EXTRA_BACKCHANNEL_PHRASES` line:

```
# Extra comma-separated phrases (beyond the built-in barge_in.STOP_PHRASES)
# that, if heard while the assistant is mid-reply, cancel and restart it.
#EXTRA_STOP_PHRASES=cancel that,forget it
```

- [ ] **Step 4: Import `barge_in` in `app.py`**

In `app.py`, change:

```python
import config
import fillers
from guide_client import stream_reply
```

to:

```python
import barge_in
import config
import fillers
from guide_client import stream_reply
```

- [ ] **Step 5: Add `partial_reply` to `CallState`**

In `app.py`, change:

```python
@dataclass
class CallState:
    messages: list = field(default_factory=list)
    task: object = None  # asyncio.Task | None
```

to:

```python
@dataclass
class CallState:
    messages: list = field(default_factory=list)
    task: object = None  # asyncio.Task | None
    partial_reply: str = ""  # real reply text streamed so far this turn (never the filler)
```

- [ ] **Step 6: Mark every outgoing `text` frame `preemptible`, and track `partial_reply`, in `respond_to`**

In `app.py`, change:

```python
    async def respond_to(filler: str | None) -> None:
        reply_text = ""
        try:
            if filler:
                await websocket.send_json({"type": "text", "token": filler + " ", "last": False})
            async for delta in stream_reply(st.messages):
                await websocket.send_json({"type": "text", "token": delta, "last": False})
                reply_text += delta
            await websocket.send_json({"type": "text", "token": "", "last": True})
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Error while streaming guide reply")
            try:
                await websocket.send_json(
                    {
                        "type": "text",
                        "token": "Sorry, I'm having trouble right now.",
                        "last": True,
                    }
                )
            except Exception:
                pass
            return
        if reply_text:
            st.messages.append({"role": "assistant", "content": reply_text})
```

to:

```python
    async def respond_to(filler: str | None) -> None:
        # Every frame is marked preemptible so that if this turn is still
        # playing when a later trigger-interrupted turn starts, Twilio drops
        # this audio and switches to the new turn's audio immediately. This
        # is a no-op in the normal (non-interrupting) case, since by the
        # time a new turn starts normally the previous one has already
        # finished.
        reply_text = ""
        try:
            if filler:
                await websocket.send_json(
                    {"type": "text", "token": filler + " ", "last": False, "preemptible": True}
                )
            async for delta in stream_reply(st.messages):
                await websocket.send_json(
                    {"type": "text", "token": delta, "last": False, "preemptible": True}
                )
                reply_text += delta
                st.partial_reply = reply_text
            await websocket.send_json({"type": "text", "token": "", "last": True, "preemptible": True})
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Error while streaming guide reply")
            try:
                await websocket.send_json(
                    {
                        "type": "text",
                        "token": "Sorry, I'm having trouble right now.",
                        "last": True,
                        "preemptible": True,
                    }
                )
            except Exception:
                pass
            return
        if reply_text:
            st.messages.append({"role": "assistant", "content": reply_text})
```

- [ ] **Step 7: Reset `partial_reply` at the start of every turn**

In `app.py`, change:

```python
    def start_reply(user_text: str) -> None:
        st.messages.append({"role": "user", "content": user_text})
        filler = fillers.pick(config.FILLER_PHRASES) if fillers.looks_like_question(user_text) else None
        st.task = asyncio.create_task(respond_to(filler))
```

to:

```python
    def start_reply(user_text: str) -> None:
        st.messages.append({"role": "user", "content": user_text})
        st.partial_reply = ""
        filler = fillers.pick(config.FILLER_PHRASES) if fillers.looks_like_question(user_text) else None
        st.task = asyncio.create_task(respond_to(filler))
```

- [ ] **Step 8: Handle the trigger in the `prompt` mid-reply branch**

In `app.py`, change:

```python
            elif msg_type == "prompt":
                text = msg.get("voicePrompt", "") or ""
                if text.strip():
                    if st.task and not st.task.done():
                        # Logged only, never added to st.messages: GuideAnts
                        # never receives or persists this utterance, so
                        # recording it locally would desync our history from
                        # GuideAnts' and break conversation matching on the
                        # next turn (see module docstring).
                        logger.info("Ignored caller speech during active reply (not acted on): %r", text)
                    elif fillers.is_backchannel(text, config.EXTRA_BACKCHANNEL_PHRASES):
```

to:

```python
            elif msg_type == "prompt":
                text = msg.get("voicePrompt", "") or ""
                if text.strip():
                    if st.task and not st.task.done():
                        if barge_in.should_interrupt(text, config.EXTRA_STOP_PHRASES):
                            logger.info("Interrupting active reply for trigger utterance: %r", text)
                            await cancel_task()
                            # Only the real reply text streamed so far goes
                            # into st.messages -- never the filler -- same
                            # invariant as a normal completed turn (see
                            # module docstring).
                            if st.partial_reply:
                                st.messages.append({"role": "assistant", "content": st.partial_reply})
                                st.partial_reply = ""
                            start_reply(text)
                        else:
                            # Logged only, never added to st.messages: GuideAnts
                            # never receives or persists this utterance, so
                            # recording it locally would desync our history from
                            # GuideAnts' and break conversation matching on the
                            # next turn (see module docstring).
                            logger.info("Ignored caller speech during active reply (not acted on): %r", text)
                    elif fillers.is_backchannel(text, config.EXTRA_BACKCHANNEL_PHRASES):
```

- [ ] **Step 9: Update the module docstring**

In `app.py`, change:

```python
Conversation Relay is configured `interruptible="none"`, so caller speech
never stops TTS playback; it still arrives here as "prompt" messages
(`report_input_during_agent_speech="speech"`) and is logged but not acted
on mid-reply. When a caller's utterance looks like a question or request
(see fillers.py), a short filler phrase is spoken immediately, before the
real GuideAnts reply, to mask lookup latency.
```

to:

```python
Conversation Relay is configured `interruptible="none"`, so Twilio itself
never pauses TTS playback on caller speech; it still arrives here as
"prompt" messages (`report_input_during_agent_speech="speech"`). Most
mid-reply speech (statements, backchannel, noise) is logged but not acted
on. The exception is a trigger utterance -- a stop/wait phrase or a new
question, per barge_in.should_interrupt() -- which cancels the in-flight
reply and immediately starts a fresh one for what the caller just said.
Playback is actually cut over using Conversation Relay's per-frame
`preemptible` flag (see respond_to()), not Twilio-native interruption.
When a caller's utterance looks like a question or request (see
fillers.py), a short filler phrase is spoken immediately, before the real
GuideAnts reply, to mask lookup latency.
```

- [ ] **Step 10: Verify `app.py` still imports cleanly**

```bash
cd "/Users/jacksonfalgoust/Documents/Internship/Twillio Demo"
source .venv/bin/activate
python -c "import app"
```

Expected: no error/traceback.

- [ ] **Step 11: Boot the server and sanity-check `/twiml` still renders**

```bash
cd "/Users/jacksonfalgoust/Documents/Internship/Twillio Demo"
source .venv/bin/activate
uvicorn app:app --port 8080 &
sleep 1
curl -s -X POST -H "Host: localhost:8080" http://localhost:8080/twiml
kill %1
```

Expected: XML output containing `<ConversationRelay` with `interruptible="none"` and `reportInputDuringAgentSpeech="speech"` — unchanged from before this task, confirming the TwiML path wasn't broken by the `app.py` edits.

- [ ] **Step 12: Re-run the full `barge_in` test suite (regression check)**

```bash
pytest test_barge_in.py -v
```

Expected: all 14 tests still PASS (this task didn't touch `barge_in.py`, but confirms nothing else broke).

- [ ] **Step 13: Commit**

```bash
git add config.py .env.example app.py
git commit -m "Wire selective barge-in trigger detection into the prompt handler"
```

---

### Task 4: Update docs (`ARCHITECTURE.md`, `README.md`)

**Files:**
- Modify: `ARCHITECTURE.md`
- Modify: `README.md`

**Interfaces:** none (docs only).

- [ ] **Step 1: Update `ARCHITECTURE.md`'s intro paragraph and file map**

In `ARCHITECTURE.md`, change:

```markdown
The whole app is four files. There is no database, no session store outside
memory, and no business logic — this is purely a **protocol bridge** between
Twilio Conversation Relay's WebSocket protocol and GuideAnts' OpenAI-compatible
chat API. `fillers.py` is the one exception to "no business logic": it holds
the pure, I/O-free heuristics that decide whether a caller's utterance looks
like a question/request worth masking with a spoken filler phrase before the
real reply.
```

to:

```markdown
There is no database, no session store outside memory — this is purely a
**protocol bridge** between Twilio Conversation Relay's WebSocket protocol
and GuideAnts' OpenAI-compatible chat API. `fillers.py` and `barge_in.py` are
the exceptions to "no business logic": pure, I/O-free heuristics that decide
whether a caller's utterance warrants a spoken filler phrase (`fillers.py`)
or should cancel and restart an in-flight reply (`barge_in.py`).
```

In the file map table, change:

```markdown
| [fillers.py](fillers.py) | Pure functions used by `app.py` to decide the filler-phrase behavior: `looks_like_question` classifies a caller utterance as question/request-like (warrants a filler) or not, `pick` returns a random filler phrase from a list, and `is_backchannel` classifies an utterance as pure acknowledgment noise (e.g. "ok", "yeah") that should never get a guide reply. No I/O, no Twilio/GuideAnts knowledge. |
| [app.py](app.py) | FastAPI app with the two endpoints Twilio talks to: `POST /twiml` and `WS /ws`. All call-handling logic lives here. |
```

to:

```markdown
| [fillers.py](fillers.py) | Pure functions used by `app.py` to decide the filler-phrase behavior: `looks_like_question` classifies a caller utterance as question/request-like (warrants a filler) or not, `pick` returns a random filler phrase from a list, and `is_backchannel` classifies an utterance as pure acknowledgment noise (e.g. "ok", "yeah") that should never get a guide reply. No I/O, no Twilio/GuideAnts knowledge. |
| [barge_in.py](barge_in.py) | Pure functions used by `app.py` to decide selective barge-in: `is_stop_command` matches a caller utterance against a built-in stop/wait phrase list, and `should_interrupt` (= `is_stop_command` or `fillers.looks_like_question`) decides whether an utterance heard mid-reply should cancel and restart the in-flight reply. No I/O, no Twilio/GuideAnts knowledge — unit-tested directly in `test_barge_in.py`. |
| [app.py](app.py) | FastAPI app with the two endpoints Twilio talks to: `POST /twiml` and `WS /ws`. All call-handling logic lives here. |
```

- [ ] **Step 2: Add `EXTRA_STOP_PHRASES` to the config table**

In `ARCHITECTURE.md`'s config table, add this row directly after the `EXTRA_BACKCHANNEL_PHRASES` row:

```markdown
| `EXTRA_STOP_PHRASES` | `EXTRA_STOP_PHRASES` | `[]` (empty) | `app.py` (via `barge_in.should_interrupt`) — comma-separated phrases, on top of the built-in `barge_in.STOP_PHRASES`, that also cancel and restart an in-flight reply when heard mid-reply. |
```

- [ ] **Step 3: Rewrite the `interrupt` row and add the trigger-interrupt behavior to the `WS /ws` section**

In `ARCHITECTURE.md`, change the `prompt` and `interrupt` table rows:

```markdown
| `prompt` | `voicePrompt` (caller's transcribed speech) | If a reply *is* already streaming, the text is appended to `st.interjections` and logged — not spoken, not acted on. Otherwise, if `fillers.is_backchannel()` says it's pure acknowledgment noise (e.g. "ok", "yeah"), it's recorded straight into `messages` with no reply — this also covers the case where STT finishes transcribing a short "ok" just *after* the reply already finished. Otherwise a new reply starts (`start_reply()`), which also decides via `fillers.looks_like_question()` whether to prepend a filler phrase. See "Filler phrases and uninterruptible replies" below. |
| `interrupt` | `utteranceUntilInterrupt` | Not expected given `interruptible="none"` — logged only, no state change. Caller speech during agent speech arrives as `prompt` instead (see above). |
```

to:

```markdown
| `prompt` | `voicePrompt` (caller's transcribed speech) | If a reply *is* already streaming: `barge_in.should_interrupt()` checks whether this is a stop/wait phrase or a new question. If so, the in-flight reply is cancelled and a fresh one starts for this utterance (see "Selective barge-in" below). Otherwise the text is just logged — not spoken, not acted on, not recorded. If no reply is streaming: `fillers.is_backchannel()` catches pure acknowledgment noise (e.g. "ok", "yeah") and records it into `messages` with no reply — this also covers the case where STT finishes transcribing a short "ok" just *after* the reply already finished. Otherwise a new reply starts (`start_reply()`), which also decides via `fillers.looks_like_question()` whether to prepend a filler phrase. |
| `interrupt` | `utteranceUntilInterrupt` | Not expected given `interruptible="none"` — logged only, no state change. Caller speech during agent speech arrives as `prompt` instead (see above); Twilio itself never auto-pauses. |
```

Then, directly after the "Filler phrases and uninterruptible replies" section (before "## The GuideAnts endpoint this app depends on"), add a new section:

```markdown
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
```

- [ ] **Step 4: Update the "Full call sequence" and "Per-connection state" sections**

In `ARCHITECTURE.md`, change:

```markdown
6. If the caller talks during the reply, Twilio still transcribes it and sends it as another `prompt` (`report_input_during_agent_speech="speech"`) rather than an `interrupt`. Since a reply is already active, the app does not act on it — the text is appended to `st.interjections` and logged, and the current reply keeps playing to the end.
```

to:

```markdown
6. If the caller talks during the reply, Twilio still transcribes it and sends it as another `prompt` (`report_input_during_agent_speech="speech"`) rather than an `interrupt`. If it's a stop/wait phrase or a new question (`barge_in.should_interrupt()`), the in-flight reply is cancelled and a fresh reply starts for it immediately (repeat from step 4). Otherwise the current reply keeps playing to the end and the utterance is just logged.
```

Also, in the "Per-connection state" bullet list, change:

```markdown
- `task` — the `asyncio.Task` currently generating/streaming a reply, if any; also doubles as the "is a reply active right now" flag (`st.task and not st.task.done()`).
- `interjections: list[str]` — caller utterances heard (as `prompt`) while a reply is already streaming. Buffered here and flushed into `messages` as `{"role": "user", ...}` entries once the in-flight reply finishes; never acted on while buffered.
```

to:

```markdown
- `task` — the `asyncio.Task` currently generating/streaming a reply, if any; also doubles as the "is a reply active right now" flag (`st.task and not st.task.done()`).
- `partial_reply: str` — the real (GuideAnts-sourced) reply text streamed so far in the current turn, never including the filler. Reset to `""` at the start of every turn; read and appended to `st.messages` if a trigger utterance cancels the turn before it finishes.
```

(Note: this plan's version of `app.py` never had an `interjections` buffer — that description in the pre-existing `ARCHITECTURE.md` didn't match the actual code even before this feature. This step corrects it to match reality.)

- [ ] **Step 5: Update `README.md`'s file table and step 5 of the call flow**

In `README.md`, change:

```markdown
| `fillers.py` | Pure logic for the filler-phrase feature: `looks_like_question` decides whether a caller's utterance looks like a question or request that warrants a short filler phrase before the real reply; `pick` returns a random filler phrase from a list; `is_backchannel` decides whether an utterance (e.g. "ok", "yeah") is pure acknowledgment noise that should never get a guide reply. |
```

to:

```markdown
| `fillers.py` | Pure logic for the filler-phrase feature: `looks_like_question` decides whether a caller's utterance looks like a question or request that warrants a short filler phrase before the real reply; `pick` returns a random filler phrase from a list; `is_backchannel` decides whether an utterance (e.g. "ok", "yeah") is pure acknowledgment noise that should never get a guide reply. |
| `barge_in.py` | Pure logic for selective barge-in: `should_interrupt` decides whether a caller's utterance heard mid-reply (a stop/wait phrase, or a new question) should cancel the in-flight reply and start a fresh one. |
```

And change:

```markdown
5. If a `prompt` arrives *while* a reply is already streaming, Twilio does not
   stop or pause TTS (`interruptible="none"`) and this app doesn't act on it
   either — the reply always plays to completion. The caller's words are just
   recorded into the conversation history and only reach GuideAnts as context
   on the *next* turn. This means even a genuine new question asked mid-reply
   won't be answered until the caller repeats it after the current answer
   finishes — see [ARCHITECTURE.md](ARCHITECTURE.md) for the full model and
   why.
```

to:

```markdown
5. If a `prompt` arrives *while* a reply is already streaming, Twilio does not
   stop or pause TTS on its own (`interruptible="none"`) — but this app does
   act on it if it's a stop/wait phrase ("stop", "wait", "hold on", ...) or a
   new question: the in-flight reply is cancelled and a fresh reply starts
   immediately for what the caller just said, cutting over playback via
   Conversation Relay's `preemptible` flag. Anything else said mid-reply
   (statements, backchannel, noise) is just logged and the current reply
   keeps playing to the end — see [ARCHITECTURE.md](ARCHITECTURE.md) for the
   full model and why.
```

- [ ] **Step 6: Commit**

```bash
git add ARCHITECTURE.md README.md
git commit -m "Update docs for selective barge-in"
```

---

## Self-Review Notes

- **Spec coverage:** barge_in.py classifier (Task 1-2), app.py wiring + preemptible mechanism (Task 3), config env var (Task 3), history bookkeeping caveat (Task 3 step 8 comment + Task 4 doc caveat), testing (Task 1-2), docs (Task 4) — all spec sections covered. The spec's "Open risk (accepted)" is carried into the docs update verbatim as a caveat, not re-litigated.
- **Corrected from spec:** the spec said to mark the *new* turn's first frame `preemptible`. Verified against Twilio's docs during planning that the flag actually belongs on the *currently playing* turn's frames (it declares "I can be replaced by what comes next"), so the plan instead marks every frame of every turn unconditionally — functionally achieves the same goal (a later interrupt can cut off an earlier still-playing turn) without needing to special-case which call to `respond_to()` is "the interrupting one."
- **Placeholder scan:** no TBD/TODO; all code blocks are complete and exact.
- **Type consistency:** `barge_in.should_interrupt(text, extra_phrases=())` signature matches between Task 2's definition and Task 3's call site (`barge_in.should_interrupt(text, config.EXTRA_STOP_PHRASES)`). `CallState.partial_reply` name matches between Task 3 steps 5, 6, 7, 8.
