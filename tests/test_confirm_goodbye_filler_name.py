"""18:46 review fixes: recap + yes before booking, goodbye before hanging
up, neutral send filler, business name kept whole for TTS."""

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config, fillers, guide_client, main, twilio_auth
from app.guide_client import Delta, GuideSession
from app.guide_publish import render
from app.spoken_text import PhraseJoiner

TEMPLATE = Path(__file__).resolve().parents[1] / "guide-demo" / "template" / "instructions.template.md"


# --- 1) recap + yes before booking ------------------------------------------------

def _session(prev, user):
    s = GuideSession(caller_phone="+15550003374")
    s.prev_round_text, s.turn_user_text = prev, user
    return s


RECAP = ("Declare victory. The Downtown Dash on Wednesday, October 14th at ten A M, sixty-nine dollars. "
         "Booking under Eric Smith, shall I go ahead?")


@pytest.mark.parametrize("prev,user,ok", [
    (RECAP, "Yes.", True),
    (RECAP, "[Note: x] Yeah, go ahead.", True),
    (RECAP, "Okay, book it.", True),
    ("Shall I go ahead and book it for you?", "Yes please", True),
    (RECAP, "No.", False),
    (RECAP, "Wait, what time was that?", False),
    ("What time would you like to pick it up?", "10.", False),   # 18:46: booked right after the time
    ("Great, that's the Downtown Dash. What time tomorrow?", "Yes.", False),
    ("", "Yes.", False),
])
def test_booking_confirmed(prev, user, ok):
    assert guide_client.booking_confirmed(_session(prev, user)) is ok


def _create(s, monkeypatch):
    async def fake_create(client, **kw):
        return {"order_id": "o"}

    monkeypatch.setattr(config, "BOOKING_CONFIRM_GUARD_ENABLED", True)
    monkeypatch.setattr(guide_client, "BooqableClient", lambda: object())
    monkeypatch.setattr(guide_client.reservations, "create_reservation", fake_create)
    s.location_cache = {"id": "loc"}
    return asyncio.run(guide_client._run_reservation_tool("createReservation", {
        "customer_name": "Eric Smith", "customer_phone": "+15550003374", "starts_at": "x",
        "stops_at": "y", "items": [{"product_id": "p", "quantity": 1}]}, s))


def test_create_refused_without_recap_yes(monkeypatch):
    out = _create(_session("What time would you like to pick it up?", "10."), monkeypatch)
    assert out["booked"] is False and out["error"].startswith("NOT BOOKED: confirm details with caller first")


def test_create_allowed_after_recap_yes(monkeypatch):
    assert _create(_session(RECAP, "Yes."), monkeypatch) == {"order_id": "o"}


def test_turn_tracking_sets_prev_and_user(monkeypatch):
    rounds = iter(["Declare victory. " + RECAP, "Declare victory. Done."])

    async def fake_turn(client, inp, session, outcome):
        yield next(rounds)

    monkeypatch.setattr(guide_client, "_stream_turn", fake_turn)
    s = GuideSession()

    async def run(text):
        return [e async for e in guide_client._stream_reply_with_tools(None, text, s)]

    asyncio.run(run("A bike tomorrow at ten"))
    asyncio.run(run("Yes."))
    assert "Booking under Eric Smith" in s.prev_round_text and s.turn_user_text == "Yes."


def test_known_caller_note_still_requires_recap():
    s = GuideSession(caller_phone="+15550003374")
    s.known_customer = {"id": "c1", "attributes": {"name": "Eric Smith"}}
    note = guide_client.known_caller_note(s)
    assert "does NOT skip the recap" in note and "Booking under Eric Smith, shall I go ahead?" in note


def test_template_and_spec_recap_rules():
    t = TEMPLATE.read_text(encoding="utf-8")
    assert "Booking under Eric Smith, shall I go ahead?" in t
    assert "must still do the recap in step 8" in t
    spec = json.loads((TEMPLATE.parent / "OpenAPI" / "voice-receptionist.json").read_text(encoding="utf-8"))
    assert "NOT BOOKED: confirm details with caller first" in spec["paths"]["/"]["post"]["description"]


# --- 3) neutral send filler ------------------------------------------------------------

def test_send_filler_never_claims_sending():
    for _ in range(20):
        phrase = fillers.pick_for_tools(["sendPaymentLink"], ["x"])
        assert phrase in fillers.ACTION_FILLERS["message"]
        assert "send" not in phrase.lower()


# --- 4) business name kept whole ----------------------------------------------------

def _stream(joiner, tokens):
    out = [joiner.feed(t) for t in tokens] + [joiner.flush()]
    return [o for o in out if o]


def test_joiner_sends_name_in_one_frame():
    j = PhraseJoiner(["Peach tree Pedals"])
    frames = _stream(j, ["Thanks for calling ", "Pe", "ach", " tree", " Ped", "als", ". Goodbye."])
    assert "".join(frames) == "Thanks for calling Peach tree Pedals. Goodbye."
    assert any("Peach tree Pedals" in f for f in frames)


def test_joiner_releases_non_matching_text():
    j = PhraseJoiner(["Peach tree Pedals"])
    frames = _stream(j, ["I love ", "Pe", "aches", " and more."])
    assert "".join(frames) == "I love Peaches and more."


def test_joiner_flushes_partial_at_end():
    j = PhraseJoiner(["Peach tree Pedals"])
    assert "".join(_stream(j, ["Thanks, Pe"])) == "Thanks, Pe"


def test_joiner_no_phrases_passthrough():
    assert PhraseJoiner([]).feed("Pe") == "Pe"


def test_spoken_name_default():
    assert render.spoken_name("Peachtree Pedals") == "Peach tree Pedals"


# --- 2) goodbye before hanging up (websocket) -------------------------------------------

def _drain(ws, timeout=1.5):
    from tests.test_streaming_and_tool_barge_in import _read_or_timeout
    out = []
    while (f := _read_or_timeout(ws, timeout=timeout)) is not None:
        out.append(f)
    return out


def test_silent_endcall_plays_ready_made_goodbye(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-ws-secret")
    monkeypatch.setattr(config, "TURN_PAUSE_SECONDS", 0.01)
    monkeypatch.setattr(config, "END_CALL_AFTER_PLAYBACK_SECONDS", 0.0)
    monkeypatch.setattr(config, "TTS_WORDS_PER_SECOND", 1000.0)

    async def fake(input_text, guide):
        guide.end_call_requested = True  # guide called endCall, said nothing
        if False:
            yield Delta("")

    monkeypatch.setattr(main, "stream_reply", fake)
    sid = "CA_silent_end"
    with TestClient(main.app).websocket_connect(f"/ws?token={twilio_auth.mint_ws_token(sid)}") as ws:
        ws.send_json({"type": "setup", "callSid": sid, "from": "+15551234567", "to": "+15557654321"})
        ws.send_json({"type": "prompt", "voicePrompt": "Let me call you back.", "last": True})
        frames = _drain(ws)
    texts = [f["token"] for f in frames if f["type"] == "text" and f["token"].strip()]
    assert config.CANNED_GOODBYE_TEXT in texts
    assert any(f["type"] == "end" for f in frames)
    assert frames.index(next(f for f in frames if f.get("token") == config.CANNED_GOODBYE_TEXT)) < \
        frames.index(next(f for f in frames if f["type"] == "end"))
