import re
import time

import pytest
from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator

from app import config, local_demo_api
from app.local_call import TurnResult
from app.main import app

client = TestClient(app)

RECORDING_URL = "https://api.twilio.com/2010-04-01/Accounts/AC1/Recordings/RE1"


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    """These caches are module-level and outlive a single request, so they
    must not leak between tests."""
    local_demo_api._sessions.clear()
    local_demo_api._audio.clear()
    local_demo_api._greetings.clear()
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "")  # signature check off
    monkeypatch.setattr(config, "LOCAL_RECORD_SILENCE_SECONDS", 3)
    monkeypatch.setattr(config, "LOCAL_RECORD_MAX_SECONDS", 30)

    async def fake_greeting_for(from_number):
        return "Thanks for calling!"

    async def fake_synthesize(text):
        return b"WAV:" + text.encode()

    monkeypatch.setattr(local_demo_api, "greeting_for", fake_greeting_for)
    monkeypatch.setattr(local_demo_api.local_audio_client, "synthesize", fake_synthesize)


def audio_url_in(body):
    match = re.search(r"<Play>(.*?)</Play>", body)
    return match.group(1) if match else None


def say_text_in(body):
    match = re.search(r"<Say>(.*?)</Say>", body)
    return match.group(1) if match else None


def test_twiml_greets_and_starts_recording():
    response = client.post(
        "/local/twiml", data={"CallSid": "CA1", "From": "+15551234567"}
    )

    assert response.status_code == 200
    assert 'action="/local/turn"' in response.text
    assert 'timeout="3"' in response.text
    assert 'maxLength="30"' in response.text
    assert 'playBeep="false"' in response.text
    assert audio_url_in(response.text).startswith("https://testserver/local/audio/")


def test_greeting_audio_is_served_once_then_404s():
    response = client.post("/local/twiml", data={"CallSid": "CA1", "From": "+1555"})
    url = audio_url_in(response.text)

    first = client.get(url)
    assert first.status_code == 200
    assert first.content == b"WAV:Thanks for calling!"
    assert first.headers["content-type"] == "audio/wav"

    assert client.get(url).status_code == 404


def test_unknown_audio_id_404s():
    assert client.get("/local/audio/does-not-exist").status_code == 404


def test_greeting_synthesis_failure_still_answers_the_call(monkeypatch):
    async def failing_synthesize(text):
        raise RuntimeError("tts down")

    monkeypatch.setattr(local_demo_api.local_audio_client, "synthesize", failing_synthesize)

    response = client.post("/local/twiml", data={"CallSid": "CA1", "From": "+1555"})

    assert response.status_code == 200
    assert "<Play>" not in response.text
    assert "<Record" in response.text
    # GuideAnts' own TTS is down, but the caller still hears the greeting --
    # via Twilio's built-in <Say>, as a last resort so the line isn't silent.
    assert say_text_in(response.text) == "Thanks for calling!"


def test_turn_plays_the_reply_and_records_again(monkeypatch):
    async def fake_run_turn(recording_url, session):
        assert recording_url == RECORDING_URL
        return TurnResult("hello", "We open at nine.", b"WAV:reply", "ok")

    monkeypatch.setattr(local_demo_api.local_call, "run_turn", fake_run_turn)

    response = client.post(
        "/local/turn",
        data={"CallSid": "CA1", "From": "+1555", "RecordingUrl": RECORDING_URL},
    )

    assert response.status_code == 200
    assert 'action="/local/turn"' in response.text
    assert client.get(audio_url_in(response.text)).content == b"WAV:reply"


def test_turn_without_a_recording_url_speaks_the_no_speech_fallback(monkeypatch):
    called = {"run_turn": False}

    async def fake_run_turn(recording_url, session):
        called["run_turn"] = True
        return TurnResult("", "", None, "ok")

    async def fake_no_speech_turn():
        return TurnResult("", "Say again?", b"WAV:again", "no_speech")

    monkeypatch.setattr(local_demo_api.local_call, "run_turn", fake_run_turn)
    monkeypatch.setattr(local_demo_api.local_call, "no_speech_turn", fake_no_speech_turn)

    response = client.post("/local/turn", data={"CallSid": "CA1", "From": "+1555"})

    assert called["run_turn"] is False
    assert client.get(audio_url_in(response.text)).content == b"WAV:again"


def test_turn_with_no_audio_at_all_still_records_again(monkeypatch):
    async def fake_run_turn(recording_url, session):
        return TurnResult("hello", "", None, "error")

    monkeypatch.setattr(local_demo_api.local_call, "run_turn", fake_run_turn)

    response = client.post(
        "/local/turn",
        data={"CallSid": "CA1", "From": "+1555", "RecordingUrl": RECORDING_URL},
    )

    assert response.status_code == 200
    assert "<Play>" not in response.text
    assert "<Record" in response.text


def test_turn_with_no_audio_but_known_text_falls_back_to_say(monkeypatch):
    """local_call.run_turn keeps the intended phrase in reply_text even when
    GuideAnts couldn't synthesize it (see test_local_call.py's
    test_fallback_synthesis_failing_still_returns_a_result) -- this app must
    still speak *something* rather than leave the caller in silence."""

    async def fake_run_turn(recording_url, session):
        return TurnResult("hello", "Trouble.", None, "error")

    monkeypatch.setattr(local_demo_api.local_call, "run_turn", fake_run_turn)

    response = client.post(
        "/local/turn",
        data={"CallSid": "CA1", "From": "+1555", "RecordingUrl": RECORDING_URL},
    )

    assert response.status_code == 200
    assert "<Play>" not in response.text
    assert say_text_in(response.text) == "Trouble."
    assert "<Record" in response.text


def test_same_call_sid_reuses_one_guide_session(monkeypatch):
    seen = []

    async def fake_run_turn(recording_url, session):
        seen.append(session)
        session.conversation_id = "conv-1"
        return TurnResult("hi", "reply", b"WAV:reply", "ok")

    monkeypatch.setattr(local_demo_api.local_call, "run_turn", fake_run_turn)

    data = {"CallSid": "CA1", "From": "+15551234567", "RecordingUrl": RECORDING_URL}
    client.post("/local/turn", data=data)
    client.post("/local/turn", data=data)

    assert seen[0] is seen[1]
    assert seen[0].conversation_id == "conv-1"
    assert seen[0].caller_phone == "+15551234567"


def test_different_call_sids_get_separate_sessions(monkeypatch):
    seen = []

    async def fake_run_turn(recording_url, session):
        seen.append(session)
        return TurnResult("hi", "reply", b"WAV:reply", "ok")

    monkeypatch.setattr(local_demo_api.local_call, "run_turn", fake_run_turn)

    client.post("/local/turn", data={"CallSid": "CA1", "RecordingUrl": RECORDING_URL})
    client.post("/local/turn", data={"CallSid": "CA2", "RecordingUrl": RECORDING_URL})

    assert seen[0] is not seen[1]


def test_hangup_evicts_the_session_and_stops_recording():
    client.post("/local/twiml", data={"CallSid": "CA1", "From": "+1555"})
    assert "CA1" in local_demo_api._sessions

    response = client.post(
        "/local/turn", data={"CallSid": "CA1", "Digits": "hangup"}
    )

    assert response.status_code == 200
    assert "<Record" not in response.text
    assert "CA1" not in local_demo_api._sessions


def test_endpoints_reject_a_bad_signature_when_enforcement_is_on(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-auth-token")

    assert (
        client.post(
            "/local/twiml",
            data={"CallSid": "CA1", "From": "+1555"},
            headers={"X-Twilio-Signature": "wrong"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/local/turn",
            data={"CallSid": "CA1", "RecordingUrl": RECORDING_URL},
            headers={"X-Twilio-Signature": "wrong"},
        ).status_code
        == 403
    )


def test_sweep_evicts_stale_sessions_on_a_later_request(monkeypatch):
    monkeypatch.setattr(config, "LOCAL_SESSION_TTL_SECONDS", 0)

    client.post("/local/twiml", data={"CallSid": "CA-stale", "From": "+1555"})
    assert "CA-stale" in local_demo_api._sessions

    # Any later request triggers _sweep(); a different CallSid so this isn't
    # exercising the same session being touched/refreshed.
    client.post("/local/twiml", data={"CallSid": "CA-fresh", "From": "+1555"})

    assert "CA-stale" not in local_demo_api._sessions
    assert "CA-fresh" in local_demo_api._sessions


def test_sweep_evicts_stale_audio_on_a_later_request(monkeypatch):
    monkeypatch.setattr(config, "LOCAL_AUDIO_TTL_SECONDS", 0)

    stale_id = local_demo_api._store_audio(b"WAV:stale")
    # Force it past its TTL without sleeping: back-date its creation time.
    wav, _created = local_demo_api._audio[stale_id]
    local_demo_api._audio[stale_id] = (wav, time.monotonic() - 100)
    assert stale_id in local_demo_api._audio

    # Any request that reaches _session_for (which calls _sweep()) should
    # evict it -- use a turn request so we don't also touch _store_audio again.
    client.post(
        "/local/turn",
        data={"CallSid": "CA1", "From": "+1555"},
    )

    assert stale_id not in local_demo_api._audio


def test_valid_signature_is_accepted(monkeypatch):
    token_secret = "test-auth-token"
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", token_secret)

    params = {"CallSid": "CA1", "From": "+15551234567"}
    signature = RequestValidator(token_secret).compute_signature(
        "https://testserver/local/twiml", params
    )

    response = client.post(
        "/local/twiml", data=params, headers={"X-Twilio-Signature": signature}
    )

    assert response.status_code == 200
