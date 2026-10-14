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

### Cancel handling, spoken times, goodbye and known callers (Oct 13 17:52 test call)

Problems seen on the 17:52 call, and their fixes:

- **"No, I need to cancel" after a booking recap cancelled an older order.**
  The guide treated "cancel" as "cancel an existing reservation", looked one up
  and cancelled it on "cancel that too". The instructions now have a
  DECLINING A PENDING BOOKING rule: a no/cancel after the recap just drops the
  pending request (nothing was booked, and no lookup or cancel tool runs). An
  existing reservation is only cancelled when the caller separately asks for
  that and says yes to that specific reservation. The findReservations and
  cancelReservation tool descriptions say the same thing.
- **Wrong reservation time ("1 PM" for a 9 AM order).** Booqable returns UTC,
  and the guide read it as-is. findReservations, cancelReservation and
  createReservation now also return `date_spoken` ("Saturday, October 17th"),
  `start_time_spoken` / `end_time_spoken` (local, `BOOQABLE_TIMEZONE`) and
  `starts_local` / `stops_local`, and the guide is told to say only those.
  This also fixes ordinals being split ("sevent e enth").
- **Booking filler while cancelling** ("Just a moment while I get that
  booked"). cancelReservation now has its own filler pool ("One moment while I
  cancel that.").
- **"I have you down for…" before a booking existed.** Added to the phrases
  the guide must not use before createReservation succeeds.
- **"Peachtree Pedals" mispronounced.** There is a new `{{business.spoken_name}}`
  template slot (the business name after `SPOKEN_NAME_ALIASES`, default
  `Peachtree=Peach tree`), which the guide uses whenever it says the name.
- **No ready-made goodbye after "Okay, thank you."** Leading acknowledgments
  (okay, alright, great…) are now stripped before matching done-phrases. More
  phrases count as done, and "any other questions" counts as "anything else?".
- **Double goodbye** (17:49:48 call). The guide said goodbye, called endCall,
  then said goodbye again in the follow-up round. When a round has already
  spoken a goodbye and calls only endCall, the follow-up round is now consumed
  silently.
- **Known caller asked for their name.** The greeting's Booqable lookup
  happens in `/twiml` and was never passed to the guide. The guide was told to
  call get_caller_phone_number before asking for a name, but it asked first
  ("Can I get your full name…?") and only called the tool after the caller
  said "You have my name". Now the call-setup step starts the same lookup
  (`lookup_known_caller`), and the caller's first turn carries a one-time note
  naming the known customer (last four digits only), so the guide confirms
  the name instead of asking for it. The instructions also say never to ask a
  known customer's name. `KNOWN_CALLER_NOTE_ENABLED` turns this off.

### Business hours, direct booking for known callers, email confirmation (Oct 13 18:20 test call)

- **A booking was offered for "today" after closing.** At 6:20 PM (the shop
  closes at 6 PM) the guide checked stock for 9 AM-6 PM today, Booqable said
  in stock, and the agent offered bikes "available today". Hours were only in
  the instructions; no tool checked them. Now `app/business_hours.py` checks
  windows against the published business profile's hours in
  `BOOQABLE_TIMEZONE`:
  - createReservation refuses a start in the past (15 min grace), before
    opening, at or after closing, a closed day, or a return after closing:
    `NOT BOOKED: outside business hours -- … Next open: Wednesday, October
    14th at 9 AM.`
  - Dated listCatalog/checkAvailability return `closed: true` with no items
    and `next_open_spoken` for a closed day, a past day, or today once it's
    past closing. A whole-day check earlier today is still fine while the
    shop is open.
  - The caller's first turn carries a note with the current local date and
    time and whether the shop is open, closed for today or not yet open (with
    the next opening). The instructions say: closed today means say so and
    offer the next open day.
- **Known callers book directly.** The first-turn note tells the guide to
  call createReservation with the known name and no phone. The app fills in
  the calling number, so there's no separate get_caller_phone_number turn
  (about 1.5 s saved). get_caller_phone_number never gets a filler.
- **Recap:** it ends with "Booking under <name>?". After a decline and a
  change of mind, the details are read back again before booking.
- **Unclear "text":** "6", "six", "next", "tax" and "tech" after "text or
  email?" no longer become "Text."; the guide is told to ask once "By text,
  right?". Clear forms ("tex", "texts") are still mapped.
- **Bare first greeting:** a lone "hi"/"hello" as the first caller turn is
  ignored once (`IGNORE_FIRST_BARE_GREETING`), so the agent doesn't greet
  twice over a caller who is just starting.
- **Pronunciation:** `SPOKEN_NAME_ALIASES` default adds `Pedals=Peddles`
  ("Pedals" came out as "Pen-o-lose").

### Text-only booking confirmation (Oct 13 18:46 test call)

Email payment links were removed. On the 18:46 call, choosing email took
about 90 s and five round trips. Spelled addresses were misheard
differently each time ("brackens", "drackins", "b b rackins"). The
model twice tried to send before the caller said yes (an earlier
email-confirmation guard blocked both). When the caller finally confirmed,
Postmark rejected the send (HTTP 401, invalid server token). Now:

- sendPaymentLink sends **by text only**, to the calling number unless the
  caller confirmed a different one. Any email channel or address gets
  `NOT SENT: payment links are only sent by text message`. The tool spec's
  channel enum is just `sms`, with no email field.
- The text is a professional booking confirmation: "Hi Eric, your
  reservation with Peachtree Pedals is confirmed. Confirmation number: #54.
  You can pay securely ahead of your visit here: <link> Thank you!" The
  confirmation number is the Booqable order number, and the tool returns it
  as `confirmation_id`.
- The agent offers "a booking confirmation with your confirmation number
  and a secure payment link", and says the confirmation number after
  sending. It never calls it just "a payment link".

### Recap before booking, goodbye before hang-up, neutral send filler, business name (Oct 13 18:46 review)

- **Booked without a recap or a yes.** For a known caller, the guide called
  createReservation right after the caller gave a time. The known-caller
  note now says skipping the name and phone questions does not skip the
  recap. The recap ends "Booking under <name>, shall I go ahead?". Server
  guard: createReservation returns `NOT BOOKED: confirm details with caller
  first` unless the previous agent turn was a recap or book-it question and
  the caller's reply is a clear yes (`BOOKING_CONFIRM_GUARD_ENABLED`).
- **Hung up without a goodbye.** When the guide calls endCall and says
  nothing, the ready-made goodbye now plays before the session ends.
- **"Sending that now" before a refused send.** Send fillers are now neutral
  ("One moment."), and the guide's own reply says the text went out once it
  actually did.
- **Business name mispronounced** ("Ped-allies", "P. had less"). The cause
  was the name arriving at TTS split into sub-word frames ("Ped" + "als",
  "P" + "edd" + "les"), not the spelling. Offline, every candidate spelling
  ("Pedals", "Peddles", "Peddals", "Pedduls", "Pedalls", "Peddulls") came
  out the same and transcribed back as "Peachtree Petals". That test used a
  local Piper voice, because the ElevenLabs voice runs inside Twilio and
  there is no ElevenLabs key to call it directly. Now the app holds back
  text until any `SPOKEN_JOIN_PHRASES` phrase is complete, so the business
  name always reaches TTS in one frame. The alias is back to
  `Peachtree=Peach tree` only ("Peach tree" sounded right on the 18:19 call),
  so the spoken name is "Peach tree Pedals".

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
| `CANNED_GOODBYE_TEXT` | "You're welcome! Thanks for calling {business}, …" | The goodbye text; `{business}` = spoken business name (one TTS frame) |
| `SPOKEN_NAME_ALIASES` | Peachtree=Peach tree | `word=spoken` pairs for the business name the guide says |
| `BUSINESS_HOURS_GUARD_ENABLED` | true | Refuse catalog/availability/booking outside business hours |
| `NOW_NOTE_ENABLED` | true | Current local date/time and open state in the first-turn note |
| `IGNORE_FIRST_BARE_GREETING` | true | Don't answer a lone "hi" first turn with another greeting |
| `SPOKEN_JOIN_PHRASES` | Peach tree Pedals,Peachtree Pedals | Phrases always sent to TTS in one frame |
| `BOOKING_CONFIRM_GUARD_ENABLED` | true | Refuse a booking without a recap + yes |
| `KNOWN_CALLER_NOTE_ENABLED` | true | Tell the guide who a known caller is on the first turn |
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

### Neutral booking filler, one confirmation, business name in the goodbye (Oct 13 21:20 review)
- **Booking filler is neutral.** On the 21:20 call "Just a moment while I get that booked" played, and then the confirm guard refused the booking. The booking pool is now "One moment." / "Just a moment." / "Bear with me one second." (same as the send pool). Only the guide's reply after a real order says it's booked.
- **No separate time confirmation.** Booking step 4 now takes a clear time as given. The guide asks a clarifying question only when something is actually ambiguous (an hour that could be morning or evening, a time outside opening hours). Step 8's recap ending "Booking under <name>, shall I go ahead?" is the single confirmation, which saves one round (about 12 s on the 21:20 call).
- **Goodbye names the business.** `CANNED_GOODBYE_TEXT` takes `{business}`, filled with the published business name in its spoken form (`SPOKEN_NAME_ALIASES`: "Peach tree Pedals"). The name is cached for 60 s and falls back to the default profile. It goes out in one text frame, so it is never split into sub-word tokens. Every call that ends with "no, that's all" now speaks the name, which makes pronunciation checkable on each recording.
