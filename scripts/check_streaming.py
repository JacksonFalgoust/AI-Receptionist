"""Diagnostic: shows whether this app hands the guide's reply to Twilio
incrementally (token by token, as GuideAnts produces it) or as one burst.

Default prompts trigger a reservation tool call (listCatalog / checkAvailability)
so both rounds of a tool-call turn are visible -- useful for confirming the
guide obeys instructions.md's "do it silently: never announce it or narrate
what you're about to do... never stall with filler like 'let me check that'"
rule, since any narration ahead of the tool call would show up as text this
script prints but that guide_client.py discards before it reaches Twilio.

Run from this repo root:
python -m scripts.check_streaming "some prompt that triggers a tool call"

It also works run directly (python scripts/check_streaming.py ...) or from an
IDE's "Run" button -- the sys.path fixup below adds the repo root so `from
app import guide_client` resolves either way.

Not part of the app -- safe to delete once you're done comparing models.

This drives guide_client.stream_reply -- the exact function app/main.py's
respond_to() calls to get deltas to speak to the caller -- so the timings
below are what actually reaches Twilio, not GuideAnts' raw SSE timing.
Since commit 4e95865, _stream_reply_with_tools (which stream_reply wraps)
buffers a whole round's deltas locally and only yields them in a tight loop
once the round is fully complete (so it can discard narration ahead of a
tool call). That means many "delta events" can still show up all clustered
within a couple milliseconds of each other even though GuideAnts streamed
token-by-token upstream -- from Twilio's perspective that round arrived as
one burst, not incrementally. The classification below requires a real gap
between first and last delta before calling it "incremental"; a tiny total
span is reported as buffered even if there were many delta events.
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import guide_client

# Below this, a run of deltas is treated as having arrived in one burst
# (this app's internal yield loop, not real GuideAnts pacing) rather than
# genuinely incremental streaming.
_INCREMENTAL_SPAN_THRESHOLD_SECONDS = 0.05


async def run_turn(label: str, user_text: str, session: guide_client.GuideSession) -> None:
    """Drive one turn through the real guide_client.stream_reply path (the
    same function app/main.py calls) and report per-delta timing, so it's
    visible whether *this* turn reached Twilio incrementally or as one
    burst.

    `request_sent` is stamped immediately before the first await on the
    stream_reply generator -- calling stream_reply() itself just builds the
    generator object, so no HTTP request has actually gone out yet; the
    request is sent once the `async for` below drives the generator's first
    step. Time-to-first-token and time-to-last-token are both measured from
    that point. Note that a turn needing a tool call is really >=2
    responses.create() round trips to GuideAnts internally
    (_stream_reply_with_tools), and any round before the last one is
    discarded narration rather than yielded here (see module docstring) --
    so "first token" below means the first token of the round that was
    actually kept, not necessarily the first token GuideAnts produced for
    the turn overall."""
    print(f"=== {label}: {user_text!r} ===")
    request_sent = time.monotonic()
    delta_times = []
    async for delta in guide_client.stream_reply(user_text, session):
        t = time.monotonic() - request_sent
        delta_times.append(t)
        print(f"{t:6.3f}s  delta_len={len(delta):<4} {delta!r}")

    print(f"conversation id after {label}: {session.conversation_id!r}")
    if not delta_times:
        print(f"TIMING ({label}): request sent, but 0 tokens received -- empty reply.")
        print(f"RESULT ({label}): 0 delta events -- empty reply.")
    else:
        print(f"TIMING ({label}): request sent -> first token received by app: {delta_times[0]:.3f}s")
        print(f"TIMING ({label}): request sent -> last token received by app:  {delta_times[-1]:.3f}s")
        if len(delta_times) == 1:
            print(f"RESULT ({label}): 1 delta event -- buffered / not incremental.")
        else:
            span = delta_times[-1] - delta_times[0]
            if span < _INCREMENTAL_SPAN_THRESHOLD_SECONDS:
                print(
                    f"RESULT ({label}): {len(delta_times)} delta events but only "
                    f"{span:.3f}s apart -- arrived as one burst (buffered), not "
                    f"incremental, even though there were multiple events."
                )
            else:
                print(f"RESULT ({label}): {len(delta_times)} delta events spread over {span:.3f}s -- incremental streaming.")
    print()


async def main():
    prompt = sys.argv[1] if len(sys.argv) > 1 else (
        "Do you have any mountain bikes available this Saturday from ten AM to two PM?"
    )

    session = guide_client.GuideSession()
    await run_turn("turn 1", "What bikes do you have available to rent?", session)

    if session.conversation_id is None:
        print(
            "RESULT: streamed turn 1 carried no conversation id -- old "
            "GuideAnts build? (see stream_missing_conversation fallback in "
            "guide_client.py)"
        )
        sys.exit(1)

    await run_turn("turn 2", prompt, session)


asyncio.run(main())
