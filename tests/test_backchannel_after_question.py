"""Reproduces the bug where a caller's short affirmative ("yeah", "yep",
etc.) answering a yes/no question the guide just asked and is waiting on
gets swallowed by fillers.is_backchannel() instead of being treated as the
caller's turn -- see app/main.py's `prompt` handler and app/fillers.py's
module docstring for the (deliberate, but overly broad) "late backchannel"
handling this collides with.
"""

import queue
import threading
import time

from fastapi.testclient import TestClient

from app import config, twilio_auth
from app import main
from app.guide_client import Delta
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


def test_yeah_answers_a_pending_guide_question_instead_of_being_ignored(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-ws-secret")
    monkeypatch.setattr(config, "TURN_PAUSE_SECONDS", 0.01)
    # Collapses the post-reply playback hold to effectively nothing so the
    # first turn's task is done well before the second prompt arrives.
    monkeypatch.setattr(config, "TTS_WORDS_PER_SECOND", 10_000.0)

    calls = []

    async def _fake_stream_reply(input_text, guide):
        calls.append(input_text)
        if len(calls) == 1:
            yield Delta("Would you like the 9am slot?")
        else:
            yield Delta("Great, you're booked for 9am.")

    monkeypatch.setattr(main, "stream_reply", _fake_stream_reply)

    call_sid = "CA_yeah_answers_question"
    token = twilio_auth.mint_ws_token(call_sid)

    with client.websocket_connect(f"/ws?token={token}") as websocket:
        websocket.send_json(
            {"type": "setup", "callSid": call_sid, "from": "+15551234567", "to": "+15557654321"}
        )
        websocket.send_json(
            {"type": "prompt", "voicePrompt": "book me a slot tomorrow", "last": True}
        )
        first = _read_or_timeout(websocket)
        assert first is not None and "9am slot" in first["token"]
        # Drain the empty last=True frame respond_to() sends after the loop
        # ends, so it isn't mistaken below for a reply to the second prompt.
        if not first.get("last"):
            trailer = _read_or_timeout(websocket)
            assert trailer is not None and trailer.get("last")
        # The server sets CallState.guide_awaiting_answer (and finishes its
        # post-reply playback hold) in the same coroutine just after sending
        # that last=True frame, with no further await in between on the fast
        # path -- give it a moment to actually get there before the second
        # prompt arrives, mirroring the real gap before a caller answers.
        time.sleep(0.1)

        websocket.send_json({"type": "prompt", "voicePrompt": "yeah", "last": True})
        second = _read_or_timeout(websocket, timeout=1.0)

    assert second is not None, (
        "caller's 'yeah' answering the guide's pending question was ignored as backchannel noise"
    )
    assert "booked" in second["token"]
