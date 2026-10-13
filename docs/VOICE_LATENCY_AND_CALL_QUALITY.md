# Voice latency and call quality

This document covers the voice-path changes made on `perf/voice-latency`
(commits `dc22b5d` through `d083948`) after a series of live test calls
against the Twilio ConversationRelay + GuideAnts + Booqable stack. Each
section lists the problem seen on a call, the fix, and the switch that turns
it off. Phone numbers in logs and tool output are masked to the last four
digits.

## Summary

| Area | Before | After |
|---|---|---|
| Plain answer, first spoken token | 1.4–3.0 s (long replies up to 171 words) | 0.6–1.3 s, replies 11–75 words |
| Dated `listCatalog` tool time (median) | 5.04 s | 1.58 s (parallel groups + call-setup prefetch) |
| Catalog answer, end to end | ~6.5 s | ~3 s expected |
| Model round after a tool returns | — | 0.62–0.72 s (not the bottleneck) |
| Booking (`createReservation`) | ~3 s of Booqable writes | unchanged (writes stay sequential) |

Measured with `scripts/measure_latency.py` (text-only, no phone calls) and a
local tool timing harness against live read-only Booqable calls.

## Changes by area

### Turn-taking and fillers (`dc22b5d`, `ecae296`, `1dd224b`)
- **Problem:** the agent waited too long after the caller stopped, said
  "let me check" before answers that needed no lookup, and repeated the same
  filler back to back.
- **Fix:** grace period lowered to 0.6 s. Fillers are only spoken while a client
  tool runs, after 0.3 s. Phrases are chosen per action (booking, message,
  lookup) and never repeated back to back. There is no filler for `endCall` or
  after the model's own lead-in.
- **Switches:** `TURN_RESUME_GRACE_SECONDS`, `FILLER_ONLY_FOR_TOOL_CALLS`, `FILLER_DELAY_SECONDS`.

### Shorter replies and inlined facts (`dc22b5d`)
- **Problem:** long, list-like answers took up to 5 s to finish.
- **Fix:** the instructions ask for brief spoken replies, and the publisher
  inlines the core business facts into the instructions, so common questions
  don't need a file search.

### Caller identity and phone handling (`af9f3bd`, `c5dd163`, `ce8b3b4`)
- Confirm the caller's name, and reuse the confirmed phone number.
  `get_caller_phone_number` returns `last_four`, and the agent only ever says
  the last four digits.
- The SMS greeting uses the caller's first name.
- Phone numbers are masked in logs, and log lines are timestamped.
- Per-call catalog and location cache. `createReservation` reuses the caller
  lookup.

### Hanging up (`ce8b3b4`, `c5dd163`, `1dd224b`)
- **Problem:** calls stayed open after the goodbye, or the goodbye was cut off.
- **Fix:**
  - New `endCall` tool, which hangs up after the goodbye has finished playing,
    plus `END_CALL_AFTER_PLAYBACK_SECONDS`.
  - Server-side backup (`app/call_end.py`) for when the model says goodbye
    without calling `endCall`.
  - A ready-made goodbye when the caller says they're done after "anything else?".
- **Switches:** `AUTO_END_CALL_ENABLED`, `CANNED_GOODBYE_ENABLED`, `CANNED_GOODBYE_TEXT`.

### Speech-to-text (`af9f3bd`, `c5dd163`, `1e15880`, `b622e95`)
- **Problem:** "nine" was heard as "none", weekdays and dates were misheard,
  and "text or email" was garbled.
- **Fix:**
  - Deepgram `nova-3-general` with `en-US`.
  - STT hints for times, weekdays, dates, product names and "text"/"email".
  - `app/stt_fixups.py` corrects known mis-hearings.
- **Switches:** `STT_SPEECH_MODEL`, `STT_LANGUAGE`, `STT_HINTS`.

### Working sound and stuck-audio recovery (`ce8b3b4`, `c5dd163`, `1e15880`, `1dd224b`)
- **Background:** a soft looping chime played during slow tools.
- **Problem:** on some turns, Twilio's playback stalled behind the chime.
- **Fix:**
  - The chime is interruptible and plays once after the filler.
  - If playback hasn't started within 3 s, the reply is resent without the
    chime. This recovery only applies to chime turns, to avoid false resends.
- **Switches:** `WORKING_SOUND_ENABLED`, `WORKING_SOUND_TOOLS`, `STUCK_AUDIO_RECOVERY_SECONDS`.
- See Known limits for why the chime is now disabled.

### Booking correctness (`c5dd163`, `1e15880`, `b622e95`, `d083948`)
- **Problem:** the agent offered or booked out-of-stock items, offered
  accessories as rentals, sent payment links before the caller chose a
  channel, and said an item "will be reserved" before the booking existed.
- **Fix:**
  - `listCatalog` accepts a date and returns stock for that time.
  - Accessories (`ACCESSORY_KEYWORDS`) are listed separately.
  - A server-side guard refuses bookings for unavailable items and returns
    `NOT BOOKED: ...`.
  - Payment links are only sent after the caller answers text or email.
  - Booking order is day first.
  - The instructions forbid saying "reserved"/"booked" until
    `createReservation` succeeds.
- No cut-off after tool calls, and the agent's reply text is logged.

### Name capture (`d083948`)
- **Problem:** after "what's your full name?", callers pause between first
  and last name, and the agent took the turn after the first name.
- **Fix:** wait an extra `NAME_EXTRA_WAIT_SECONDS` (1.0 s) when the pending
  reply is one word and the last agent line asked for a name (and not for
  spelling).

### Fast tools (`d083948`)
- **Finding:** a timing harness showed that Booqable reads, not the model,
  were the bottleneck.
- **Fix:**
  - Product groups are fetched in parallel (5.04 → 4.12 s).
  - The catalog and location are prefetched at call setup, and `listCatalog`
    uses the prefetch (→ 1.58 s).
  - Read-only tool calls in one round run concurrently. Writes stay sequential.
- **Switch:** `FAST_TOOLS_ENABLED`.

### Startup warm-up (`1e15880`)
- **Fix:** one throwaway GuideAnts request at startup, so the first call
  isn't a cold start.
- **Switch:** `GUIDE_WARMUP_ON_STARTUP`.

### Publishing (`c5dd163`, `1293055`)
- **Problem:** republishing didn't update tool sources that had changed.
- **Fix:** the publisher now updates changed tool sources and verifies that
  all 10 client tools are live. GuideAnts' derived `toolCount` is ignored
  when a source is added or replaced.

## Configuration

| Variable | Default | Effect |
|---|---|---|
| `TURN_RESUME_GRACE_SECONDS` | 0.6 | Pause after the caller stops before the agent replies |
| `NAME_EXTRA_WAIT_SECONDS` | 1.0 | Extra wait for a one-word reply to a name question (0 = off) |
| `FILLER_ONLY_FOR_TOOL_CALLS` | true | Only speak fillers while a tool runs |
| `FILLER_DELAY_SECONDS` | 0.3 | Delay before a filler |
| `WORKING_SOUND_ENABLED` | true (code), **false recommended** | Chime during slow tools |
| `WORKING_SOUND_TOOLS` | the 8 Booqable/payment tools | Tools that get the chime |
| `STUCK_AUDIO_RECOVERY_SECONDS` | 3.0 | Resend a reply without the chime if playback stalls (0 = off) |
| `STT_SPEECH_MODEL` | nova-3-general | ConversationRelay STT model |
| `STT_LANGUAGE` | en-US | STT language |
| `STT_HINTS` | built-in list | STT hints (empty = off) |
| `END_CALL_AFTER_PLAYBACK_SECONDS` | 0.4 | Margin after the goodbye before hanging up |
| `AUTO_END_CALL_ENABLED` | true | Server-side hang-up backup |
| `CANNED_GOODBYE_ENABLED` | true | Ready-made goodbye after "anything else?" → done |
| `CANNED_GOODBYE_TEXT` | "You're welcome! Thanks for calling…" | The goodbye text |
| `ACCESSORY_KEYWORDS` | helmet,lock,basket,light,bell,accessory,child seat | Accessory detection |
| `FAST_TOOLS_ENABLED` | true | Parallel/prefetched Booqable reads |
| `GUIDE_WARMUP_ON_STARTUP` | true | GuideAnts warm-up at startup |

## Guide changes

The publisher reads `guide-demo/template/instructions.template.md` and
`guide-demo/template/OpenAPI/{voice-receptionist,caller-phone}.json`. The
copies in `guide-demo/tools/` must stay byte-identical (a test enforces this),
and the template stays generic ("item"). Republish after changing either.

## Known limits

- **Working chime disabled.** During test calls, Twilio never fetched
  `/audio/working.mp3`, and the reply after the chime stalled.
  `WORKING_SOUND_ENABLED=false` is the recommended setting until the cause is
  found. Tests pin it to true so that code path stays covered.
- **Bookings are still about 3 s** of sequential Booqable writes.
- **The first model round** to a tool call takes 1.8–2.5 s (model-bound).
- **One test is flaky:** the greeting-activation test occasionally fails in a
  full run and passes on rerun.
