"""Time-to-first-spoken-token and full reply time through guide_client.stream_reply
(the exact path app/main.py uses). Usage: python scripts/measure_latency.py [label]

Also runs a multi-turn tool conversation in ONE session (listCatalog, then
checkAvailability, then listCatalog again) so per-call caching shows up.
Read-only: never books, never sends."""
import asyncio, sys, time, json
sys.path.insert(0, ".")
from app.guide_client import GuideSession, Delta, ToolCallStarted, stream_reply

PROMPTS = [
    ("hours", "What are your hours today?"),
    ("rental", "How do bike rentals work, what do I need to bring?"),
    ("reservation", "I'd like to reserve a bike for this Saturday."),
    ("cancellation", "What's your cancellation policy?"),
    ("lookup", "What bikes do you have available and how much are they?"),
]

TOOL_TURNS = [
    ("tool-catalog", "What bikes do you have and how much are they?"),
    ("tool-availability", "Is your cheapest bike available tomorrow for one person? Please check."),
    ("tool-catalog-again", "Remind me, what does your most expensive bike cost? Please check the catalog."),
]

async def one(name, text, s=None):
    s = s or GuideSession(caller_phone="+15555550100")
    t0 = time.perf_counter(); first = None; tools = []; out = ""
    async for ev in stream_reply(text, s):
        if isinstance(ev, ToolCallStarted):
            tools += list(ev.names); continue
        if first is None and ev.text.strip():
            first = time.perf_counter() - t0
        out += ev.text
    total = time.perf_counter() - t0
    return {"prompt": name, "ttft": round(first or total, 2), "total": round(total, 2),
            "tools": tools, "words": len(out.split()), "reply": out.strip()[:160]}

async def main():
    rows = []
    for n, t in PROMPTS:
        rows.append(await one(n, t))
        print(json.dumps(rows[-1]), flush=True)
    s = GuideSession(caller_phone="+15555550100")
    for n, t in TOOL_TURNS:
        rows.append(await one(n, t, s))
        print(json.dumps(rows[-1]), flush=True)
    with open(f"latency-{sys.argv[1] if len(sys.argv)>1 else 'run'}.json", "w") as f:
        json.dump(rows, f, indent=1)

asyncio.run(main())
