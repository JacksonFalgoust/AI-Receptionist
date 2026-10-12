"""Server-side hang-up backup, mediaPlaying handling, chime timing, STT hints."""

import asyncio
import threading

from fastapi.testclient import TestClient

from app import call_end, config, main, twilio_auth
from app.guide_client import Delta, ToolCallStarted
from app.main import app
from tests.test_streaming_and_tool_barge_in import _read_or_timeout

client = TestClient(app)


def test_should_end_rules():
    asked = "You're all set. Is there anything else I can help you with?"
    bye = "Thanks for calling Peachtree Pedals. Have a wonderful day!"
    assert call_end.should_end(asked, "No.", bye)
    assert call_end.should_end(asked, "No, that's it.", bye)
    assert call_end.should_end(asked, "Thank you.", bye)
    assert call_end.should_end("What time works?", "Goodbye.", bye)  # explicit goodbye
    assert not call_end.should_end("What time would you like?", "No.", bye)  # 'no' to a different question
    assert not call_end.should_end(asked, "None.", bye)  # unclear reply
    assert not call_end.should_end(asked, "No.", "Okay! Would you like a receipt?")  # reply asks something
    assert not call_end.should_end(asked, "Actually, can I add a helmet?", bye)


def _session(monkeypatch, fake, sid):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-ws-secret")
    monkeypatch.setattr(config, "TURN_PAUSE_SECONDS", 0.01)
    monkeypatch.setattr(config, "END_CALL_AFTER_PLAYBACK_SECONDS", 0.0)
    monkeypatch.setattr(config, "TTS_WORDS_PER_SECOND", 1000.0)
    monkeypatch.setattr(main, "stream_reply", fake)
    token = twilio_auth.mint_ws_token(sid)
    ws_cm = client.websocket_connect(f"/ws?token={token}")
    ws = ws_cm.__enter__()
    ws.send_json({"type": "setup", "callSid": sid, "from": "+15551234567", "to": "+15557654321"})
    return ws_cm, ws


def _drain(ws, timeout=1.0):
    out = []
    while (f := _read_or_timeout(ws, timeout=timeout)) is not None:
        out.append(f)
    return out


def test_backup_hangup_after_anything_else_then_no(monkeypatch):
    replies = iter(["You're booked. Is there anything else I can help you with?",
                    "Thanks for calling. Have a great day!"])

    async def fake(input_text, guide):
        yield Delta(next(replies))

    cm, ws = _session(monkeypatch, fake, "CA_auto_end")
    try:
        ws.send_json({"type": "prompt", "voicePrompt": "book it", "last": True})
        first = _drain(ws)
        assert all(f["type"] != "end" for f in first)
        ws.send_json({"type": "prompt", "voicePrompt": "No.", "last": True})
        second = _drain(ws)
        assert any(f["type"] == "end" for f in second)
    finally:
        cm.__exit__(None, None, None)


def test_no_backup_hangup_when_reply_asks_a_question(monkeypatch):
    replies = iter(["Is there anything else I can help you with?", "Sure, what day would you like?"])

    async def fake(input_text, guide):
        yield Delta(next(replies))

    cm, ws = _session(monkeypatch, fake, "CA_auto_end_no")
    try:
        ws.send_json({"type": "prompt", "voicePrompt": "hi", "last": True})
        _drain(ws)
        ws.send_json({"type": "prompt", "voicePrompt": "No.", "last": True})
        assert all(f["type"] != "end" for f in _drain(ws))
    finally:
        cm.__exit__(None, None, None)


def test_chime_skipped_when_answer_arrives_during_filler(monkeypatch):
    monkeypatch.setattr(config, "FILLER_DELAY_SECONDS", 0.05)
    monkeypatch.setattr(config, "FILLER_PHRASES", ["One moment please while I look."])

    async def fake(input_text, guide):
        yield ToolCallStarted(("checkAvailability",))
        await asyncio.sleep(0.15)  # back before the filler would have finished
        yield Delta("It's available.")

    cm, ws = _session(monkeypatch, fake, "CA_chime_skip")
    monkeypatch.setattr(config, "TTS_WORDS_PER_SECOND", 2.0)  # filler ~3s
    try:
        ws.send_json({"type": "prompt", "voicePrompt": "Yes.", "last": True})
        frames = _drain(ws, timeout=1.5)
    finally:
        cm.__exit__(None, None, None)
    assert any(f["type"] == "text" and "One moment" in f["token"] for f in frames)
    assert all(f["type"] != "play" for f in frames)


def test_media_playing_after_reply_is_cut_and_not_warned(monkeypatch, caplog):
    monkeypatch.setattr(config, "FILLER_DELAY_SECONDS", 0.05)
    monkeypatch.setattr(config, "FILLER_PHRASES", ["Hm."])
    gate = threading.Event()

    async def fake(input_text, guide):
        yield ToolCallStarted(("createReservation",))
        await asyncio.sleep(0.5)
        yield Delta("You're all set.")
        while not gate.is_set():
            await asyncio.sleep(0.01)

    cm, ws = _session(monkeypatch, fake, "CA_media_cut")
    try:
        ws.send_json({"type": "prompt", "voicePrompt": "Yes.", "last": True})
        frames = []
        while not any(f["type"] == "text" and "all set" in f.get("token", "") for f in frames):
            f = _read_or_timeout(ws, timeout=2.0)
            assert f is not None
            frames.append(f)
        assert any(f["type"] == "play" for f in frames)
        ws.send_json({"type": "info", "name": "mediaPlaying", "value": "on"})
        cut = _read_or_timeout(ws, timeout=1.0)
        gate.set()
        assert cut == {"type": "text", "token": " ", "last": True, "preemptible": True}
    finally:
        gate.set()
        cm.__exit__(None, None, None)
    assert "Unhandled message type" not in caplog.text


def test_caller_phone_is_not_a_slow_tool_and_twiml_has_hints(monkeypatch):
    assert "get_caller_phone_number" not in config.WORKING_SOUND_TOOLS
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "")
    monkeypatch.setattr(config, "BOOQABLE_API_KEY", "")
    t = client.post("/twiml", data={"CallSid": "CA1", "From": "+15551234567"}).text
    assert 'hints="' in t and "nine AM" in t
