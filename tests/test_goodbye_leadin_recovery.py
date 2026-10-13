"""Ready-made goodbye, no filler after the model's own lead-in, recovery only on chime turns."""

import asyncio
import json

from fastapi.testclient import TestClient

from app import config, main, twilio_auth
from app.guide_client import Delta, ToolCallStarted
from app.main import app
from tests.test_streaming_and_tool_barge_in import _drain_until_last, _read_or_timeout

client = TestClient(app)
AGENT_ON = {"type": "info", "name": "agentSpeaking", "value": "on"}


def _frames(ws, timeout=1.0):
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


def _open(sid):
    ws = client.websocket_connect(f"/ws?token={twilio_auth.mint_ws_token(sid)}")
    return ws


def _two_turns(monkeypatch, second, sid):
    calls = []

    async def fake(input_text, guide):
        calls.append(input_text)
        if len(calls) == 1:
            yield Delta("You're all set. Is there anything else I can help with?")
        else:
            yield Delta("Sure, what else?")

    _setup(monkeypatch, fake)
    with _open(sid) as ws:
        ws.send_json({"type": "setup", "callSid": sid, "from": "+15551234567", "to": "+15557654321"})
        ws.send_json({"type": "prompt", "voicePrompt": "Book it please.", "last": True})
        _drain_until_last(ws)
        ws.send_json({"type": "prompt", "voicePrompt": second, "last": True})
        frames = _frames(ws, timeout=1.5)
    return calls, frames


def test_canned_goodbye_after_anything_else(monkeypatch):
    for i, said in enumerate(["No.", "No, that's it. Thank you.", "Bye."]):
        calls, frames = _two_turns(monkeypatch, said, f"CA_bye_{i}")
        assert len(calls) == 1, said  # no model round trip for the goodbye
        texts = [f for f in frames if f["type"] == "text"]
        assert texts and texts[0]["token"] == config.CANNED_GOODBYE_TEXT and texts[0]["last"]
        end = [f for f in frames if f["type"] == "end"]
        assert end and json.loads(end[0]["handoffData"])["reasonCode"] == "caller-done"


def test_real_request_after_anything_else_goes_to_model(monkeypatch):
    calls, frames = _two_turns(monkeypatch, "Yes, what time do you close?", "CA_bye_x")
    assert len(calls) == 2 and not [f for f in frames if f["type"] == "end"]


def test_no_canned_goodbye_mid_booking(monkeypatch):
    calls = []

    async def fake(input_text, guide):
        calls.append(input_text)
        yield Delta("Would you like a payment link?")

    _setup(monkeypatch, fake)
    sid = "CA_bye_mid"
    with _open(sid) as ws:
        ws.send_json({"type": "setup", "callSid": sid, "from": "+15551234567", "to": "+15557654321"})
        ws.send_json({"type": "prompt", "voicePrompt": "Book it.", "last": True})
        _drain_until_last(ws)
        ws.send_json({"type": "prompt", "voicePrompt": "No.", "last": True})
        frames = _frames(ws)
    assert len(calls) == 2 and not [f for f in frames if f["type"] == "end"]


def test_canned_goodbye_can_be_disabled(monkeypatch):
    monkeypatch.setattr(config, "CANNED_GOODBYE_ENABLED", False)
    calls, _ = _two_turns(monkeypatch, "No.", "CA_bye_off")
    assert len(calls) == 2


def test_no_filler_after_models_own_lead_in(monkeypatch):
    monkeypatch.setattr(config, "FILLER_PHRASES", ["FILLERMARK"])

    async def fake(input_text, guide):
        yield Delta("Let me check that for you.")
        yield ToolCallStarted(("checkAvailability",))
        await asyncio.sleep(0.4)
        yield Delta(" It's available.")

    _setup(monkeypatch, fake)
    monkeypatch.setattr(config, "TTS_WORDS_PER_SECOND", 1000.0)
    sid = "CA_leadin"
    with _open(sid) as ws:
        ws.send_json({"type": "setup", "callSid": sid, "from": "+15551234567", "to": "+15557654321"})
        ws.send_json({"type": "prompt", "voicePrompt": "Is it free Monday?", "last": True})
        frames = _frames(ws)
    tokens = [f.get("token", "") for f in frames if f["type"] == "text"]
    assert not any("FILLERMARK" in t for t in tokens) and not any(
        "Let me check." == t.strip() or "check." in t and "One moment" in t for t in tokens
    )


def test_no_resend_on_non_chime_turn_even_without_new_agent_start(monkeypatch):
    async def fake(input_text, guide):
        yield ToolCallStarted(("checkAvailability",))
        await asyncio.sleep(0.4)
        yield Delta("It's available at eleven.")

    _setup(monkeypatch, fake)
    monkeypatch.setattr(config, "WORKING_SOUND_ENABLED", False)  # chime off, as on the Dell
    sid = "CA_noresend"
    with _open(sid) as ws:
        ws.send_json({"type": "setup", "callSid": sid, "from": "+15551234567", "to": "+15557654321"})
        ws.send_json(AGENT_ON)  # greeting, then the filler keeps playing into the reply
        ws.send_json({"type": "prompt", "voicePrompt": "Is eleven free?", "last": True})
        frames = _frames(ws, timeout=1.5)
    assert all(f["type"] != "play" for f in frames)
    assert not [f for f in frames if f["type"] == "text" and f.get("last") and "eleven" in f.get("token", "")]
