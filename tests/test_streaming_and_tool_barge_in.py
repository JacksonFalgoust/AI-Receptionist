"""Covers the live-token-streaming change: guide_client now yields every
delta live (see app/guide_client.py's Delta/ToolCallStarted contract), which
means a client-side tool call can leave the caller hearing silence mid-turn
while it runs. These tests prove app.py's defenses around that gap --
softened barge-in while a tool call is in flight, and the filler phrase not
stacking on top of narration that's already playing -- using the same
TestClient + monkeypatch.setattr(main, "stream_reply", ...) harness as
tests/test_backchannel_after_question.py.
"""

import asyncio
import queue
import threading

from fastapi.testclient import TestClient

from app import config, twilio_auth
from app import main
from app.guide_client import Delta, ToolCallStarted
from app.main import app

client = TestClient(app)


def _read_or_timeout(websocket, timeout: float = 1.0):
    result: "queue.Queue" = queue.Queue(maxsize=1)

    def _reader() -> None:
        try:
            result.put(websocket.receive_json())
        except Exception as exc:
            result.put(exc)

    reader = threading.Thread(target=_reader, daemon=True)
    reader.start()
    try:
        return result.get(timeout=timeout)
    except queue.Empty:
        return None


def _drain_until_last(websocket, timeout: float = 1.0) -> list:
    """Read frames until one with last=True arrives (or the read times out),
    returning everything collected so far."""
    frames = []
    while True:
        frame = _read_or_timeout(websocket, timeout=timeout)
        if frame is None:
            return frames
        frames.append(frame)
        if frame.get("last"):
            return frames


def test_question_during_tool_call_does_not_cancel_the_turn(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-ws-secret")
    monkeypatch.setattr(config, "TURN_PAUSE_SECONDS", 0.01)
    monkeypatch.setattr(config, "TOOL_CALL_BARGE_IN_GRACE_SECONDS", 5.0)

    calls = []
    tool_call_started = threading.Event()
    release_tool = threading.Event()

    async def _fake_stream_reply(input_text, guide):
        calls.append(input_text)
        yield ToolCallStarted(("checkAvailability",))
        tool_call_started.set()
        while not release_tool.is_set():
            await asyncio.sleep(0.01)
        yield Delta("It's available.")

    monkeypatch.setattr(main, "stream_reply", _fake_stream_reply)

    call_sid = "CA_question_during_tool_call"
    token = twilio_auth.mint_ws_token(call_sid)

    with client.websocket_connect(f"/ws?token={token}") as websocket:
        websocket.send_json(
            {"type": "setup", "callSid": call_sid, "from": "+15551234567", "to": "+15557654321"}
        )
        websocket.send_json(
            {"type": "prompt", "voicePrompt": "is the cruiser available Saturday", "last": True}
        )
        assert tool_call_started.wait(timeout=1.0)

        # The caller talks into the tool-call silence -- this must not
        # cancel the in-flight turn the way a genuine new question would.
        websocket.send_json(
            {"type": "prompt", "voicePrompt": "are you still there", "last": True}
        )

        release_tool.set()
        frames = _drain_until_last(websocket, timeout=2.0)

    assert any("available" in f["token"] for f in frames)
    assert calls == ["is the cruiser available Saturday"]


def test_stop_command_during_tool_call_still_cancels(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-ws-secret")
    monkeypatch.setattr(config, "TURN_PAUSE_SECONDS", 0.01)
    monkeypatch.setattr(config, "TOOL_CALL_BARGE_IN_GRACE_SECONDS", 5.0)
    monkeypatch.setattr(config, "STOP_ACK_PHRASES", ["Okay."])

    tool_call_started = threading.Event()

    async def _fake_stream_reply(input_text, guide):
        yield ToolCallStarted(("checkAvailability",))
        tool_call_started.set()
        await asyncio.sleep(10)  # cancelled well before this would fire
        yield Delta("It's available.")

    monkeypatch.setattr(main, "stream_reply", _fake_stream_reply)

    call_sid = "CA_stop_during_tool_call"
    token = twilio_auth.mint_ws_token(call_sid)

    with client.websocket_connect(f"/ws?token={token}") as websocket:
        websocket.send_json(
            {"type": "setup", "callSid": call_sid, "from": "+15551234567", "to": "+15557654321"}
        )
        websocket.send_json(
            {"type": "prompt", "voicePrompt": "is the cruiser available Saturday", "last": True}
        )
        assert tool_call_started.wait(timeout=1.0)

        websocket.send_json({"type": "prompt", "voicePrompt": "stop", "last": True})
        frame = _read_or_timeout(websocket, timeout=1.0)

    assert frame is not None
    assert frame["token"] == "Okay."
    assert frame["last"] is True


def test_tool_call_grace_expires_and_barge_in_works_again(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-ws-secret")
    monkeypatch.setattr(config, "TURN_PAUSE_SECONDS", 0.01)
    monkeypatch.setattr(config, "TOOL_CALL_BARGE_IN_GRACE_SECONDS", 0.05)

    calls = []
    tool_call_started = threading.Event()

    async def _fake_stream_reply(input_text, guide):
        calls.append(input_text)
        if len(calls) == 1:
            yield ToolCallStarted(("checkAvailability",))
            tool_call_started.set()
            await asyncio.sleep(10)  # never resolves within this test
        else:
            yield Delta("Second turn reply.")

    monkeypatch.setattr(main, "stream_reply", _fake_stream_reply)

    call_sid = "CA_grace_expires"
    token = twilio_auth.mint_ws_token(call_sid)

    with client.websocket_connect(f"/ws?token={token}") as websocket:
        websocket.send_json(
            {"type": "setup", "callSid": call_sid, "from": "+15551234567", "to": "+15557654321"}
        )
        websocket.send_json(
            {"type": "prompt", "voicePrompt": "is the cruiser available Saturday", "last": True}
        )
        assert tool_call_started.wait(timeout=1.0)

        # Wait out the (short) grace window before asking again.
        import time as _time

        _time.sleep(0.2)

        websocket.send_json(
            {"type": "prompt", "voicePrompt": "what time do you close", "last": True}
        )
        frames = _drain_until_last(websocket, timeout=2.0)

    assert any("Second turn reply." in f["token"] for f in frames)
    assert calls == ["is the cruiser available Saturday", "what time do you close"]


def test_filler_is_not_stacked_on_narration_already_playing(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-ws-secret")
    monkeypatch.setattr(config, "TURN_PAUSE_SECONDS", 0.01)
    monkeypatch.setattr(config, "FILLER_DELAY_SECONDS", 0.05)
    monkeypatch.setattr(config, "FILLER_PHRASES", ["FILLERMARK"])
    monkeypatch.setattr(config, "TTS_WORDS_PER_SECOND", 2.5)

    async def _fake_stream_reply(input_text, guide):
        # ~40 words of narration -> ~16s of estimated queued audio at the
        # default TTS rate, comfortably outlasting the sleep below.
        yield Delta(
            "Sure, let me take a look at that for you, it will just take "
            "a moment while I check on the availability for that date "
            "and let you know what I find as soon as I have it."
        )
        await asyncio.sleep(0.3)
        yield Delta(" It's available.")

    monkeypatch.setattr(main, "stream_reply", _fake_stream_reply)

    call_sid = "CA_no_filler_stack"
    token = twilio_auth.mint_ws_token(call_sid)

    with client.websocket_connect(f"/ws?token={token}") as websocket:
        websocket.send_json(
            {"type": "setup", "callSid": call_sid, "from": "+15551234567", "to": "+15557654321"}
        )
        websocket.send_json(
            {"type": "prompt", "voicePrompt": "is the cruiser available Saturday", "last": True}
        )
        frames = _drain_until_last(websocket, timeout=2.0)

    assert not any("FILLERMARK" in f["token"] for f in frames)
    assert any("available" in f["token"] for f in frames)


def test_filler_still_spoken_when_nothing_has_been_sent_yet(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-ws-secret")
    monkeypatch.setattr(config, "TURN_PAUSE_SECONDS", 0.01)
    monkeypatch.setattr(config, "FILLER_DELAY_SECONDS", 0.05)
    monkeypatch.setattr(config, "FILLER_PHRASES", ["FILLERMARK"])

    async def _fake_stream_reply(input_text, guide):
        await asyncio.sleep(0.2)  # slower than FILLER_DELAY_SECONDS
        yield Delta("Here you go.")

    monkeypatch.setattr(main, "stream_reply", _fake_stream_reply)

    call_sid = "CA_filler_still_spoken"
    token = twilio_auth.mint_ws_token(call_sid)

    with client.websocket_connect(f"/ws?token={token}") as websocket:
        websocket.send_json(
            {"type": "setup", "callSid": call_sid, "from": "+15551234567", "to": "+15557654321"}
        )
        websocket.send_json(
            {"type": "prompt", "voicePrompt": "is the cruiser available Saturday", "last": True}
        )
        frames = _drain_until_last(websocket, timeout=2.0)

    assert any("FILLERMARK" in f["token"] for f in frames)


def test_round_boundary_inserts_a_separating_space(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-ws-secret")
    monkeypatch.setattr(config, "TURN_PAUSE_SECONDS", 0.01)
    monkeypatch.setattr(config, "FILLER_DELAY_SECONDS", 5.0)

    async def _fake_stream_reply(input_text, guide):
        yield Delta("Let me check that for you.")
        yield ToolCallStarted(("checkAvailability",))
        yield Delta("It's available.")

    monkeypatch.setattr(main, "stream_reply", _fake_stream_reply)

    call_sid = "CA_round_boundary_space"
    token = twilio_auth.mint_ws_token(call_sid)

    with client.websocket_connect(f"/ws?token={token}") as websocket:
        websocket.send_json(
            {"type": "setup", "callSid": call_sid, "from": "+15551234567", "to": "+15557654321"}
        )
        websocket.send_json(
            {"type": "prompt", "voicePrompt": "is the cruiser available Saturday", "last": True}
        )
        frames = _drain_until_last(websocket, timeout=2.0)

    full_text = "".join(f["token"] for f in frames)
    assert "you.It's" not in full_text
    assert "you. It's" in full_text
