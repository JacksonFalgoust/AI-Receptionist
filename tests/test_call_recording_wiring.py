"""Covers app/main.py's call into call_recording.record_call() in the /ws
handler's disconnect teardown (see app/call_recording.py)."""

import queue
import threading
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app import config, twilio_auth
from app import main
from app.guide_client import Delta
from app.main import app

client = TestClient(app)


def _drain_until_last(websocket, timeout: float = 1.0) -> list:
    frames = []
    while True:
        result: "queue.Queue" = queue.Queue(maxsize=1)

        def _reader() -> None:
            try:
                result.put(websocket.receive_json())
            except Exception as exc:
                result.put(exc)

        reader = threading.Thread(target=_reader, daemon=True)
        reader.start()
        try:
            frame = result.get(timeout=timeout)
        except queue.Empty:
            return frames
        frames.append(frame)
        if frame.get("last"):
            return frames


def test_disconnect_persists_the_call(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-ws-secret")
    monkeypatch.setattr(config, "TURN_PAUSE_SECONDS", 0.01)

    async def _fake_stream_reply(input_text, guide):
        yield Delta("Sure, how can I help?")

    monkeypatch.setattr(main, "stream_reply", _fake_stream_reply)
    record_call = AsyncMock()
    monkeypatch.setattr(main.call_recording, "record_call", record_call)

    call_sid = "CA_disconnect_persists"
    token = twilio_auth.mint_ws_token(call_sid)

    with client.websocket_connect(f"/ws?token={token}") as websocket:
        websocket.send_json(
            {"type": "setup", "callSid": call_sid, "from": "+15551234567", "to": "+15557654321"}
        )
        websocket.send_json({"type": "prompt", "voicePrompt": "hi", "last": True})
        _drain_until_last(websocket, timeout=2.0)

    record_call.assert_awaited_once()


def test_persistence_failure_does_not_crash_teardown(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-ws-secret")
    monkeypatch.setattr(config, "TURN_PAUSE_SECONDS", 0.01)

    async def _fake_stream_reply(input_text, guide):
        yield Delta("Sure, how can I help?")

    monkeypatch.setattr(main, "stream_reply", _fake_stream_reply)
    monkeypatch.setattr(
        main.call_recording, "record_call", AsyncMock(side_effect=RuntimeError("db is down"))
    )

    call_sid = "CA_persistence_failure"
    token = twilio_auth.mint_ws_token(call_sid)

    # Must not raise -- the WS handler's own try/except around record_call()
    # is what this asserts, by simply completing without error.
    with client.websocket_connect(f"/ws?token={token}") as websocket:
        websocket.send_json(
            {"type": "setup", "callSid": call_sid, "from": "+15551234567", "to": "+15557654321"}
        )
        websocket.send_json({"type": "prompt", "voicePrompt": "hi", "last": True})
        _drain_until_last(websocket, timeout=2.0)


def test_unauthenticated_connection_does_not_persist_a_call(monkeypatch):
    # A connection whose `setup` frame never carries a valid token must never
    # reach call_recording.record_call() -- otherwise anyone who can reach the
    # public /ws endpoint could write unbounded rows with zero credentials.
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-ws-secret")

    record_call = AsyncMock()
    monkeypatch.setattr(main.call_recording, "record_call", record_call)

    call_sid = "CA_unauthenticated"

    with client.websocket_connect("/ws?token=not-a-valid-token") as websocket:
        websocket.send_json({"type": "setup", "callSid": call_sid, "from": "+15551234567"})
        # The server closes the socket (policy violation) in response; give it
        # a moment to run its disconnect teardown before asserting.
        try:
            websocket.receive_text()
        except Exception:
            pass

    record_call.assert_not_awaited()
