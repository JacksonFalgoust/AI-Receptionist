"""Tests for /ws token verification (app/twilio_auth.verify_ws_token wired
into conversation_relay_ws's `setup` message branch, app/main.py).

TestClient.websocket_connect isn't used elsewhere in this repo yet. The
server never replies to a `setup` message on its own, so "the connection
stays open" can't be observed by waiting for a reply -- instead each test
reads the next frame in a background thread with a short timeout: a prompt
reply within that window means the server closed the socket (and, per
_await_close_or_timeout, surfaces the WebSocketDisconnect it raised);
silence for the whole window means the server is still blocked waiting for
more input, i.e. the connection is still open.
"""

import queue
import threading

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import config, twilio_auth
from app import main
from app.main import app

client = TestClient(app)

CLOSE_WAIT_SECONDS = 0.5


def _await_close_or_timeout(websocket, timeout: float = CLOSE_WAIT_SECONDS):
    """Read the next WS frame in a background thread. Returns the
    WebSocketDisconnect the server raised if one arrives within `timeout`
    seconds (connection closed), or None if nothing arrives in time
    (connection still open, blocked waiting for more input)."""
    result: "queue.Queue" = queue.Queue(maxsize=1)

    def _reader() -> None:
        try:
            websocket.receive_text()
            result.put(None)
        except WebSocketDisconnect as exc:
            result.put(exc)
        except Exception:
            # The "stays open" cases leave this thread blocked on receive()
            # past the timeout below; when the `with websocket_connect(...)`
            # block then exits and tears down the test session's transport
            # streams, that pending call raises (anyio.EndOfStream) well
            # after this test has already read its result and moved on.
            # Nothing to report by then -- just don't let it surface as an
            # unhandled thread exception in the pytest run.
            pass

    reader = threading.Thread(target=_reader, daemon=True)
    reader.start()
    try:
        return result.get(timeout=timeout)
    except queue.Empty:
        return None


def test_ws_setup_with_no_token_is_closed(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-ws-secret")

    with client.websocket_connect("/ws") as websocket:
        websocket.send_json({"type": "setup", "callSid": "CA1111111111"})
        outcome = _await_close_or_timeout(websocket)

    assert isinstance(outcome, WebSocketDisconnect)
    assert outcome.code == 1008


def test_ws_setup_with_wrong_call_sid_for_token_is_closed(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-ws-secret")

    token = twilio_auth.mint_ws_token("CA_the_real_call")

    with client.websocket_connect(f"/ws?token={token}") as websocket:
        websocket.send_json({"type": "setup", "callSid": "CA_a_different_call"})
        outcome = _await_close_or_timeout(websocket)

    assert isinstance(outcome, WebSocketDisconnect)
    assert outcome.code == 1008


def test_ws_setup_with_expired_token_is_closed(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-ws-secret")
    monkeypatch.setattr(config, "WS_TOKEN_TTL_SECONDS", -10)  # already expired

    call_sid = "CA_expired_call"
    token = twilio_auth.mint_ws_token(call_sid)

    with client.websocket_connect(f"/ws?token={token}") as websocket:
        websocket.send_json({"type": "setup", "callSid": call_sid})
        outcome = _await_close_or_timeout(websocket)

    assert isinstance(outcome, WebSocketDisconnect)
    assert outcome.code == 1008


def test_ws_setup_with_matching_token_stays_open(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-ws-secret")

    call_sid = "CA_matching_call"
    token = twilio_auth.mint_ws_token(call_sid)

    with client.websocket_connect(f"/ws?token={token}") as websocket:
        websocket.send_json(
            {"type": "setup", "callSid": call_sid, "from": "+15551234567", "to": "+15557654321"}
        )
        outcome = _await_close_or_timeout(websocket)

    assert outcome is None


def test_ws_setup_with_no_enforcement_and_no_token_stays_open(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "")

    with client.websocket_connect("/ws") as websocket:
        websocket.send_json({"type": "setup", "callSid": "CA_whatever"})
        outcome = _await_close_or_timeout(websocket)

    assert outcome is None


def test_ws_setup_missing_call_sid_requires_hmac_for_empty_string(monkeypatch):
    # Edge case flagged during Task 2 review: a /twiml request that passes
    # signature validation but has no CallSid in its form body mints a
    # token bound to call_sid="" (see app/main.py's
    # `call_sid = (await request.form()).get("CallSid", "")`). A `setup`
    # frame with a missing/empty callSid must NOT get a free pass just
    # because both sides happen to be empty strings -- the token still has
    # to carry a correct HMAC for call_sid="".
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-ws-secret")

    with client.websocket_connect("/ws?token=9999999999.notarealmac") as websocket:
        websocket.send_json({"type": "setup"})  # no callSid at all
        outcome = _await_close_or_timeout(websocket)

    assert isinstance(outcome, WebSocketDisconnect)
    assert outcome.code == 1008


def test_ws_setup_missing_call_sid_with_correctly_minted_empty_token_stays_open(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-ws-secret")

    token = twilio_auth.mint_ws_token("")  # matches app/main.py's CallSid-less /twiml case

    with client.websocket_connect(f"/ws?token={token}") as websocket:
        websocket.send_json({"type": "setup"})  # no callSid at all -> defaults to ""
        outcome = _await_close_or_timeout(websocket)

    assert outcome is None


def test_ws_prompt_before_setup_is_rejected_and_never_reaches_guide(monkeypatch):
    """The Critical bug a reviewer caught: token verification originally
    lived only inside the `setup` branch, so a client that skips `setup`
    entirely and sends `prompt` first sailed straight through to
    schedule_turn -> start_reply -> respond_to -> stream_reply, driving the
    guide (and any tools it calls) with zero authentication -- exactly the
    threat this whole feature exists to stop. The message loop must now
    reject *any* non-setup frame before an authenticated setup has been
    verified, not just fail to authenticate the setup frame itself.

    Proves both halves: the connection is closed (1008), and stream_reply
    -- the guide entry point everything else in this handler funnels
    through -- is never even called.
    """
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-ws-secret")

    calls = []

    def _fake_stream_reply(input_text, guide):
        # Records the call the instant stream_reply is invoked, regardless
        # of whether the returned generator is ever iterated -- if this
        # runs at all, the bypass succeeded.
        calls.append(input_text)

        async def _gen():
            yield "should never run"

        return _gen()

    monkeypatch.setattr(main, "stream_reply", _fake_stream_reply)

    with client.websocket_connect("/ws") as websocket:  # no token, no setup
        websocket.send_json({"type": "prompt", "voicePrompt": "cancel my reservation"})
        outcome = _await_close_or_timeout(websocket)

    assert isinstance(outcome, WebSocketDisconnect)
    assert outcome.code == 1008
    assert calls == []


def test_ws_prompt_after_valid_setup_gets_a_real_reply(monkeypatch):
    """Strengthens the "stays open" signal from
    test_ws_setup_with_matching_token_stays_open, which only proves the
    server didn't close the socket within CLOSE_WAIT_SECONDS -- silence
    that a hung or silently-erroring server would also produce. This test
    stubs guide_client.stream_reply (imported into app.main) and asserts an
    actual `text` reply frame comes back after a valid setup + prompt, a
    real positive signal instead of an absence-of-negative one.
    """
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-ws-secret")
    # Turn buffering normally waits TURN_PAUSE_SECONDS of silence before
    # committing a turn (see schedule_turn/_arm_commit in app/main.py); drop
    # it to keep the test fast without changing the behavior under test.
    monkeypatch.setattr(config, "TURN_PAUSE_SECONDS", 0.01)

    async def _fake_stream_reply(input_text, guide):
        yield "Hello from the guide"

    monkeypatch.setattr(main, "stream_reply", _fake_stream_reply)

    call_sid = "CA_prompt_after_setup"
    token = twilio_auth.mint_ws_token(call_sid)

    with client.websocket_connect(f"/ws?token={token}") as websocket:
        websocket.send_json(
            {"type": "setup", "callSid": call_sid, "from": "+15551234567", "to": "+15557654321"}
        )
        websocket.send_json({"type": "prompt", "voicePrompt": "hi there", "last": True})
        frame = websocket.receive_json()

    assert frame["type"] == "text"
    assert "Hello from the guide" in frame["token"]
