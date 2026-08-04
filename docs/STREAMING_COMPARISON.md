# Comparing main vs feature/live-token-streaming vs feature/trigger-phrase

Three branches take different approaches to the same problem: this app can only speak text
it's sure is the caller-facing final answer, because every Twilio Conversation Relay frame
carries `preemptible: true` -- a later frame (even from the same reply, after a tool call's real
silence) cuts off whatever's still playing mid-word.

| Branch | Rule |
| --- | --- |
| `main` | Buffer a whole round; flush only if it didn't end in a tool call. Zero streaming. |
| `feature/live-token-streaming` | Buffer the first `STREAM_COMMIT_CHARS` (120) of a round, then stream live. A bet against length. |
| `feature/trigger-phrase` | Withhold text until the guide speaks `config.FINAL_ANSWER_SENTINEL` ("declare victory"), then stream live with no further delay. A marker, not a bet. |

This doc is the **live-call** half of the comparison -- what a caller actually hears, which the
offline harness (`scripts/compare_streaming.py` / `scripts/compare_branches.py`) can't measure.
Run the offline harness first (`python scripts/compare_branches.py --pub-id-trigger <uuid> --reps
5`, from a checkout of `feature/trigger-phrase`) for the latency numbers, then work through this
checklist once per branch for what those numbers don't show: whether a caller ever hears a word
start and then get cut off.

## Setup

- `feature/trigger-phrase` needs its own published GuideAnts guide (a clone of the demo guide
  with the "FINAL ANSWER MARKER" paragraph added to its instructions -- see
  `guide-demo/Twillio demo agent/instructions.md`). Point that branch's `.env`
  `GUIDEANTS_PUB_ID` at it; leave `main` and `feature/live-token-streaming`'s `.env` on the
  original guide (no marker instruction, since neither branch acts on it).
- One phone call per branch, same script, same person reading it if possible -- so timing
  differences come from the branch, not from how the caller happened to speak.
- Watch the server logs live during each call (`uvicorn app.main:app --port 8080 --log-level
  info` or your deployment's log stream) -- the TIMING/RESULT/WARNING lines below are how you'll
  actually catch a cutoff, not just how it sounds.

## Script (run once per branch)

1. **"What are your hours?"** -- no tool call. Note how long after you finish speaking the reply
   starts. This is `t_first_spoken` from the offline harness's `no_tool` turn, but heard live.
2. **"What bikes do you have to rent?"** -- one tool call (`listCatalog`). Listen for any word or
   partial phrase spoken *before* the answer, that then gets cut off once the catalog result
   comes back. `main` should never do this (it never speaks before the tool call resolves);
   `feature/live-token-streaming` can if the pre-tool narration happens to cross 120 characters;
   `feature/trigger-phrase` can only if the guide says the marker before it should have.
3. **Book a full reservation through to the payment link** -- several tool-call rounds
   (`checkAvailability`, `createReservation`, `sendPaymentLink`). Count every mid-word cutoff
   across the whole booking, not just the first tool call.
4. **During the silence in step 3** (right after you hear the filler phrase, before the next real
   reply), say **"are you still there?"** -- on `feature/live-token-streaming` and
   `feature/trigger-phrase` this must **not** cancel the in-flight turn
   (`config.TOOL_CALL_BARGE_IN_GRACE_SECONDS` softens barge-in for exactly this gap); `main` has
   no such softening, so note what it actually does (it may cancel and start a fresh, unrelated
   reply).
5. **Immediately after**, say **"stop"** -- must cut playback over to the local acknowledgment
   instantly on all three branches; this path never depends on GuideAnts, so branch shouldn't
   matter here.
6. **`feature/trigger-phrase` only**: confirm "declare victory" is never audible, in any of the
   above turns, including the failsafe case (ask something oddly phrased enough that the guide
   might forget the marker -- if it does, the whole reply arrives as one un-gated burst, same as
   `main`, and should still never include the marker text itself).

## Log lines to harvest per call

All emitted by the app already -- no extra instrumentation needed. Copy each call's relevant
lines out of the server log after the call:

| Log line (grep-friendly fragment) | What it tells you |
| --- | --- |
| `TIMING: GuideAnts request sent -> first token ready to send to Twilio` | Time to first spoken token, this app's side. |
| `TIMING: first frame sent to Twilio -> last frame` | How long handing the reply to Twilio took -- near-zero means it went as one burst. |
| `TIMING: last frame sent to Twilio -> Twilio agent-start` | Twilio's own pickup latency -- should be similar across branches; a large branch-to-branch gap here would point at something other than this app. |
| `RESULT: reply handed to Twilio as one burst` / `incrementally` | This app's own classification of whether that reply streamed. |
| `Discarding intermediate-round narration ahead of another tool call` (`main`) | `main`'s buffer-and-discard catching pre-tool narration. |
| `Discarding pre-trigger narration ahead of a tool call` (`feature/trigger-phrase`) | Same idea, gate-based. |
| `Committed round text was followed by a tool call` (`feature/live-token-streaming`) | The 120-char bet went wrong this round -- a real mid-word cutoff happened. |
| `Trigger phrase appeared in a round that then called` (`feature/trigger-phrase`) | The marker fired too early -- also a real mid-word cutoff, but should be rare (the guide is instructed not to do this) rather than a threshold artifact. |
| `No trigger phrase this turn; speaking the round unstreamed (failsafe)` (`feature/trigger-phrase`) | The guide forgot the marker -- this turn behaved exactly like `main`. |
| `Ignoring caller speech while a tool result is pending` | The barge-in grace period (step 4) actually engaged. |

## Results

Fill in per branch after each pass. "Cutoffs" = number of times in the whole script (steps 1-3)
a word was audibly started and then cut off.

| Branch | Step 1 time-to-speech | Step 2 cutoffs | Step 3 cutoffs | Step 4 (grace works?) | Notes |
| --- | --- | --- | --- | --- | --- |
| `main` | | | | N/A (no grace period) | |
| `feature/live-token-streaming` | | | | | |
| `feature/trigger-phrase` | | | | | |

## What "best" means here

Fewest cutoffs matters more than fastest time-to-speech -- a cut-off word reads as broken in a
way a caller notices immediately, while an extra half-second of silence just reads as a normal
pause. Use the offline harness's `t_first_spoken` numbers to compare speed once cutoff behavior
is a tie.
