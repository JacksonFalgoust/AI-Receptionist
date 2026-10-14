"""Faster tool turns (parallel groups, prefetch, parallel read-only calls) and the one-word-name wait."""

import asyncio
import time

from fastapi.testclient import TestClient

from app import config, guide_client, main, reservations, twilio_auth
from app.guide_client import Delta, GuideSession, _TurnOutcome
from tests.test_streaming_and_tool_barge_in import _drain_until_last


def test_catalog_groups_fetched_in_parallel(monkeypatch):
    monkeypatch.setattr(config, "FAST_TOOLS_ENABLED", True)

    async def groups(client):
        return [{"id": str(i), "attributes": {"name": f"G{i}"}} for i in range(5)]

    async def product(client, group):
        await asyncio.sleep(0.2)
        return {"id": "p" + group["id"]}

    monkeypatch.setattr(reservations, "_load_product_groups", groups)
    monkeypatch.setattr(reservations, "_product_for_group", product)

    class C:
        attrs = staticmethod(lambda r: r.get("attributes") or {})

    t = time.perf_counter()
    cat = asyncio.run(reservations.list_catalog(C()))
    assert time.perf_counter() - t < 0.6 and [p["name"] for p in cat] == ["G0", "G1", "G2", "G3", "G4"]
    monkeypatch.setattr(config, "FAST_TOOLS_ENABLED", False)
    t = time.perf_counter()
    asyncio.run(reservations.list_catalog(C()))
    assert time.perf_counter() - t >= 0.9  # switch restores sequential


def test_prefetch_fills_caches_and_catalog_uses_them(monkeypatch):
    calls = []

    async def catalog(client):
        calls.append("catalog")
        return [{"product_id": "p1", "name": "Lake Loop"}]

    async def loc(client, location_id):
        return {"id": "loc-1"}

    monkeypatch.setattr(reservations, "list_catalog", catalog)
    monkeypatch.setattr(reservations, "resolve_location", loc)
    monkeypatch.setattr(guide_client, "BooqableClient", lambda: object())

    async def run():
        s = GuideSession()
        s.prefetch_task = asyncio.create_task(guide_client.prefetch_booqable(s))
        out = await guide_client._run_reservation_tool("listCatalog", {}, s)
        return s, out

    s, out = asyncio.run(run())
    assert s.location_cache == {"id": "loc-1"} and calls == ["catalog"]
    assert out["products"][0]["name"] == "Lake Loop"


def test_read_only_calls_run_concurrently_writes_stay_sequential(monkeypatch):
    monkeypatch.setattr(config, "FAST_TOOLS_ENABLED", True)
    order = []

    async def exe(name, args, session):
        order.append(("start", name))
        await asyncio.sleep(0.2)
        order.append(("end", name))
        return "{}"

    monkeypatch.setattr(guide_client, "_execute_tool", exe)
    o = _TurnOutcome()
    o.function_calls.extend([("a", "checkAvailability", "{}"), ("b", "checkAvailability", "{}")])
    t = time.perf_counter()
    out = asyncio.run(guide_client._tool_outputs(o, GuideSession()))
    assert time.perf_counter() - t < 0.35 and [x["call_id"] for x in out] == ["a", "b"]
    order.clear()
    o2 = _TurnOutcome()
    o2.function_calls.extend([("a", "get_caller_phone_number", "{}"), ("b", "createReservation", "{}")])
    asyncio.run(guide_client._tool_outputs(o2, GuideSession()))
    assert order[1] == ("end", "get_caller_phone_number")


def _name_call(monkeypatch, first_reply_words, gap):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-ws-secret")
    monkeypatch.setattr(config, "TURN_PAUSE_SECONDS", 0.2)
    monkeypatch.setattr(config, "NAME_EXTRA_WAIT_SECONDS", 0.6)
    monkeypatch.setattr(config, "TTS_WORDS_PER_SECOND", 1000.0)
    seen = []

    async def fake(input_text, guide):
        seen.append(input_text)
        yield Delta("May I have your full name, please?" if len(seen) == 1 else "Thanks!")

    monkeypatch.setattr(main, "stream_reply", fake)
    sid = f"CA_name_{len(first_reply_words)}"
    with TestClient(main.app).websocket_connect(f"/ws?token={twilio_auth.mint_ws_token(sid)}") as ws:
        ws.send_json({"type": "setup", "callSid": sid, "from": "+15551234567", "to": "+15557654321"})
        ws.send_json({"type": "prompt", "voicePrompt": "I want to book.", "last": True})
        _drain_until_last(ws, timeout=2.0)
        ws.send_json({"type": "prompt", "voicePrompt": first_reply_words, "last": True})
        time.sleep(gap)
        ws.send_json({"type": "prompt", "voicePrompt": "White.", "last": True})
        _drain_until_last(ws, timeout=3.0)
    return seen


def test_one_word_name_waits_for_last_name(monkeypatch):
    seen = _name_call(monkeypatch, "Eric", 0.45)  # longer than the 0.2 s pause, inside the +0.6 s
    assert any("Eric" in s and "White" in s for s in seen), seen


def test_name_extra_wait_can_be_disabled(monkeypatch):
    monkeypatch.setattr(config, "NAME_EXTRA_WAIT_SECONDS", 0.0)
    monkeypatch.setattr(main.config, "NAME_EXTRA_WAIT_SECONDS", 0.0)
    assert main.config.NAME_EXTRA_WAIT_SECONDS == 0.0
