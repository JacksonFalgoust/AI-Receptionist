"""Stuck-audio recovery, interruptible chime, STT date hints, startup warm-up."""

import asyncio

from fastapi.testclient import TestClient

from app import config, main, twilio_auth
from app.guide_client import Delta, ToolCallStarted
from app.main import app
from tests.test_streaming_and_tool_barge_in import _read_or_timeout

client = TestClient(app)
AGENT_ON = {"type": "info", "name": "agentSpeaking", "value": "on"}


def _frames(ws, timeout=1.5):
    out = []
    while (f := _read_or_timeout(ws, timeout=timeout)) is not None:
        out.append(f)
    return out


def _setup(monkeypatch, fake):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-ws-secret")
    monkeypatch.setattr(config, "TURN_PAUSE_SECONDS", 0.01)
    monkeypatch.setattr(config, "END_CALL_AFTER_PLAYBACK_SECONDS", 0.0)
    monkeypatch.setattr(config, "TTS_WORDS_PER_SECOND", 1000.0)
    monkeypatch.setattr(config, "FILLER_DELAY_SECONDS", 0.05)
    monkeypatch.setattr(config, "STUCK_AUDIO_RECOVERY_SECONDS", 0.3)
    monkeypatch.setattr(main, "stream_reply", fake)


def _slow_booking():
    async def fake(input_text, guide):
        yield ToolCallStarted(("createReservation",))
        await asyncio.sleep(1.0)
        yield Delta("You're all set.")
    return fake


def test_stuck_chime_resends_reply_without_chime(monkeypatch):
    _setup(monkeypatch, _slow_booking())
    sid = "CA_stuck_1"
    with client.websocket_connect(f"/ws?token={twilio_auth.mint_ws_token(sid)}") as ws:
        ws.send_json({"type": "setup", "callSid": sid, "from": "+15551234567", "to": "+15557654321"})
        ws.send_json(AGENT_ON)  # greeting played: speaker events work on this call
        ws.send_json({"type": "prompt", "voicePrompt": "Yes.", "last": True})
        frames = _frames(ws, timeout=2.0)
    types = [f["type"] for f in frames]
    play = frames[types.index("play")]
    assert play["interruptible"] is True and play["preemptible"] is True
    full = [f for f in frames if f["type"] == "text" and f.get("last") and "all set" in f.get("token", "")]
    assert full, "reply should be resent as one fresh talk cycle"
    assert types.index("play") < frames.index(full[0])


def test_no_resend_when_call_never_reported_speaker_events(monkeypatch):
    _setup(monkeypatch, _slow_booking())
    sid = "CA_stuck_2"
    with client.websocket_connect(f"/ws?token={twilio_auth.mint_ws_token(sid)}") as ws:
        ws.send_json({"type": "setup", "callSid": sid, "from": "+15551234567", "to": "+15557654321"})
        ws.send_json({"type": "prompt", "voicePrompt": "Yes.", "last": True})
        frames = _frames(ws, timeout=2.0)
    assert not [f for f in frames if f["type"] == "text" and f.get("last") and "all set" in f.get("token", "")]


def test_no_resend_for_fast_reply_that_started_playing(monkeypatch):
    async def fake(input_text, guide):
        yield Delta("We open at nine.")
    _setup(monkeypatch, fake)
    sid = "CA_stuck_3"
    with client.websocket_connect(f"/ws?token={twilio_auth.mint_ws_token(sid)}") as ws:
        ws.send_json({"type": "setup", "callSid": sid, "from": "+15551234567", "to": "+15557654321"})
        ws.send_json(AGENT_ON)
        ws.send_json({"type": "prompt", "voicePrompt": "When do you open?", "last": True})
        first = _read_or_timeout(ws, timeout=1.0)
        assert first is not None
        ws.send_json(AGENT_ON)  # Twilio started playing it
        frames = [first] + _frames(ws, timeout=1.0)
    assert not [f for f in frames if f["type"] == "text" and f.get("last") and "nine" in f.get("token", "")]


def test_disabled_recovery_never_resends(monkeypatch):
    _setup(monkeypatch, _slow_booking())
    monkeypatch.setattr(config, "STUCK_AUDIO_RECOVERY_SECONDS", 0.0)
    sid = "CA_stuck_4"
    with client.websocket_connect(f"/ws?token={twilio_auth.mint_ws_token(sid)}") as ws:
        ws.send_json({"type": "setup", "callSid": sid, "from": "+15551234567", "to": "+15557654321"})
        ws.send_json(AGENT_ON)
        ws.send_json({"type": "prompt", "voicePrompt": "Yes.", "last": True})
        frames = _frames(ws, timeout=2.0)
    assert not [f for f in frames if f["type"] == "text" and f.get("last") and "all set" in f.get("token", "")]


def test_stt_hints_include_weekdays_and_dates():
    hints = [h.strip() for h in config.STT_HINTS.split(",")]
    for w in ("Monday", "Tuesday", "Saturday", "Sunday", "tomorrow", "next week", "October"):
        assert w in hints


def test_warmup_runs_one_turn_and_swallows_errors(monkeypatch):
    calls = []

    async def ok(text, guide):
        calls.append(text)
        yield Delta("OK")

    async def boom(text, guide):
        raise RuntimeError("down")
        yield  # pragma: no cover

    monkeypatch.setattr(main, "stream_reply", ok)
    asyncio.run(main._warm_up_guide())
    assert len(calls) == 1
    monkeypatch.setattr(main, "stream_reply", boom)
    asyncio.run(main._warm_up_guide())  # must not raise
