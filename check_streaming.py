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


async def main():
    prompt = sys.argv[1] if len(sys.argv) > 1 else (
        "Describe your full menu in extreme, exhaustive detail, at least 10 sentences."
    )

    session = guide_client.GuideSession()
    async for _ in guide_client.stream_reply("Hi, my name is Jackson.", session):
        pass  # turn 1: just establish a conversation id

    client = guide_client._get_client()
    start = time.monotonic()
    stream = await client.responses.create(
        model=guide_client.config.GUIDEANTS_MODEL,
        input=prompt,
        conversation=session.conversation_id,
        stream=True,
    )

    delta_events = []
    async with stream:
        async for event in stream:
            t = time.monotonic() - start
            etype = getattr(event, "type", "")
            delta = getattr(event, "delta", None)
            dlen = len(delta) if delta else 0
            print(f"{t:6.3f}s  {etype:35s} delta_len={dlen}")
            if etype == "response.output_text.delta":
                delta_events.append(t)

    print()
    if len(delta_events) <= 1:
        print(f"RESULT: {len(delta_events)} delta event(s) -- buffered / not incremental.")
    else:
        span = delta_events[-1] - delta_events[0]
        print(f"RESULT: {len(delta_events)} delta events spread over {span:.3f}s -- incremental streaming.")


asyncio.run(main())
