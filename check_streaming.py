"""Diagnostic: shows whether a GuideAnts guide streams SSE deltas
incrementally or buffers the whole reply into one burst.

Run from this repo root (needs guide_client.py + a filled-in .env):
python check_streaming.py "some prompt that produces a long reply"

Not part of the app -- safe to delete once you're done comparing models.
"""
import asyncio
import sys
import time

import guide_client


async def run_turn(label: str, user_text: str, session: guide_client.GuideSession) -> None:
    """Drive one turn through the real guide_client.stream_reply path (the
    same function app.py calls) and report per-delta timing, so it's visible
    whether *this* turn streamed incrementally or arrived as one burst."""
    print(f"=== {label}: {user_text!r} ===")
    start = time.monotonic()
    delta_times = []
    async for delta in guide_client.stream_reply(user_text, session):
        t = time.monotonic() - start
        delta_times.append(t)
        print(f"{t:6.3f}s  delta_len={len(delta):<4} {delta!r}")

    print(f"conversation id after {label}: {session.conversation_id!r}")
    if not delta_times:
        print(f"RESULT ({label}): 0 delta events -- empty reply.")
    elif len(delta_times) == 1:
        print(f"RESULT ({label}): 1 delta event -- buffered / not incremental.")
    else:
        span = delta_times[-1] - delta_times[0]
        print(f"RESULT ({label}): {len(delta_times)} delta events spread over {span:.3f}s -- incremental streaming.")
    print()


async def main():
    prompt = sys.argv[1] if len(sys.argv) > 1 else (
        "Describe your full menu in extreme, exhaustive detail, at least 10 sentences."
    )

    session = guide_client.GuideSession()
    await run_turn("turn 1", "Describe your full menu in extreme, exhaustive detail, at least 10 sentences.", session)

    if session.conversation_id is None:
        print(
            "RESULT: streamed turn 1 carried no conversation id -- old "
            "GuideAnts build? (see stream_missing_conversation fallback in "
            "guide_client.py)"
        )
        sys.exit(1)

    await run_turn("turn 2", prompt, session)


asyncio.run(main())
