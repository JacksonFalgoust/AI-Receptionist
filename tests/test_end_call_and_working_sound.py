"""endCall hang-up and the looping 'working' sound during slow tool calls."""

import asyncio
import json

from fastapi.testclient import TestClient

from app import config, guide_client, main, twilio_auth
from app.guide_client import Delta, GuideSession, ToolCallStarted
from app.main import app
from tests.test_streaming_and_tool_barge_in import _read_or_timeout

client = TestClient(app)


def _frames(ws, timeout=1.5):
    out = []
    while (f := _read_or_timeout(ws, timeout=timeout)) is not None:
        out.append(f)
    return out


def _call(monkeypatch, fake, prompt, sid):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-ws-secret")
    monkeypatch.setattr(config, "TURN_PAUSE_SECONDS", 0.01)
    monkeypatch.setattr(config, "END_CALL_AFTER_PLAYBACK_SECONDS", 0.0)
    monkeypatch.setattr(config, "TTS_WORDS_PER_SECOND", 1000.0)
    monkeypatch.setattr(main, "stream_reply", fake)
    token = twilio_auth.mint_ws_token(sid)
    with client.websocket_connect(f"/ws?token={token}") as ws:
        ws.send_json({"type": "setup", "callSid": sid, "from": "+15551234567", "to": "+15557654321"})
        ws.send_json({"type": "prompt", "voicePrompt": prompt, "last": True})
        return _frames(ws)


def test_end_call_tool_sets_flag():
    s = GuideSession()
    out = json.loads(asyncio.run(guide_client._execute_tool("endCall", "{}", s)))
    assert out["ok"] is True and s.end_call_requested


def test_goodbye_then_end_message_after_reply(monkeypatch):
    async def fake(input_text, guide):
        guide.end_call_requested = True  # what _execute_tool does for endCall
        yield ToolCallStarted(("endCall",))
        yield Delta("Thanks for calling, goodbye!")

    frames = _call(monkeypatch, fake, "no that's all thank you", "CA_end_1")
    types = [f["type"] for f in frames]
    assert "end" in types
    end_at = types.index("end")
    assert any(f["type"] == "text" and f.get("last") for f in frames[:end_at])  # goodbye fully sent first
    assert json.loads(frames[end_at]["handoffData"])["reasonCode"] == "caller-done"


def test_no_end_message_without_end_call(monkeypatch):
    async def fake(input_text, guide):
        yield Delta("Sure, what day?")

    frames = _call(monkeypatch, fake, "I want to rent a bike", "CA_end_2")
    assert all(f["type"] != "end" for f in frames)


def test_working_sound_plays_during_slow_tool_and_stops_for_reply(monkeypatch):
    monkeypatch.setattr(config, "FILLER_DELAY_SECONDS", 0.05)
    monkeypatch.setattr(config, "FILLER_PHRASES", ["One moment."])

    async def fake(input_text, guide):
        yield ToolCallStarted(("createReservation",))
        await asyncio.sleep(1.5)
        yield Delta("You're all set.")

    frames = _call(monkeypatch, fake, "Yes.", "CA_work_1")  # not a question
    types = [f["type"] for f in frames]
    assert "play" in types
    play = frames[types.index("play")]
    assert play["source"].endswith(config.WORKING_SOUND_PATH) and play["loop"] == 1 and play["preemptible"] is True
    filler = next(f for f in frames if f["type"] == "text" and "One moment" in f["token"])
    assert frames.index(filler) < types.index("play") < next(
        i for i, f in enumerate(frames) if f["type"] == "text" and "all set" in f["token"]
    )
    assert types.count("play") == 1


def test_no_working_sound_for_fast_turn(monkeypatch):
    monkeypatch.setattr(config, "FILLER_DELAY_SECONDS", 0.05)

    async def fake(input_text, guide):
        yield Delta("We open at nine.")

    frames = _call(monkeypatch, fake, "When do you open?", "CA_work_2")
    assert all(f["type"] != "play" for f in frames)


def test_working_sound_served_and_twiml_hangs_up(monkeypatch):
    r = client.get(config.WORKING_SOUND_PATH)
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and len(r.content) > 1000
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "")
    monkeypatch.setattr(config, "BOOQABLE_API_KEY", "")
    t = client.post("/twiml", data={"CallSid": "CA1", "From": "+15551234567"}).text
    assert t.index("</Connect>") < t.index("<Hangup")
