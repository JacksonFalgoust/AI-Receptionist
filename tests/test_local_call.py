import asyncio

import pytest

from app import config, local_call
from app.guide_client import Delta, GuideSession, ToolCallStarted

RECORDING_URL = "https://api.twilio.com/2010-04-01/Accounts/AC1/Recordings/RE1"


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    """Default happy-path doubles; individual tests override what they need."""
    monkeypatch.setattr(config, "LOCAL_TURN_BUDGET_SECONDS", 5.0)
    monkeypatch.setattr(config, "LOCAL_NO_SPEECH_PHRASE", "Say again?")
    monkeypatch.setattr(config, "LOCAL_ERROR_PHRASE", "Trouble.")
    monkeypatch.setattr(config, "LOCAL_TIMEOUT_PHRASE", "Too slow.")

    async def fake_fetch(recording_url):
        return b"RIFFrecording"

    async def fake_transcribe(wav):
        return "when do you open"

    async def fake_synthesize(text):
        return b"WAV:" + text.encode()

    async def fake_stream_reply(user_text, session):
        yield Delta(text="We open ")
        yield Delta(text="at nine.")

    monkeypatch.setattr(local_call, "fetch_recording_wav", fake_fetch)
    monkeypatch.setattr(local_call.local_audio_client, "transcribe", fake_transcribe)
    monkeypatch.setattr(local_call.local_audio_client, "synthesize", fake_synthesize)
    monkeypatch.setattr(local_call, "stream_reply", fake_stream_reply)


def test_happy_path_returns_transcript_reply_and_audio():
    result = asyncio.run(local_call.run_turn(RECORDING_URL, GuideSession()))

    assert result.outcome == "ok"
    assert result.transcript == "when do you open"
    assert result.reply_text == "We open at nine."
    assert result.reply_wav == b"WAV:We open at nine."


def test_tool_call_events_are_ignored_and_only_deltas_are_spoken(monkeypatch):
    async def fake_stream_reply(user_text, session):
        yield ToolCallStarted(names=("checkAvailability",))
        yield Delta(text="Yes, we have one.")

    monkeypatch.setattr(local_call, "stream_reply", fake_stream_reply)

    result = asyncio.run(local_call.run_turn(RECORDING_URL, GuideSession()))

    assert result.outcome == "ok"
    assert result.reply_text == "Yes, we have one."


def test_empty_transcript_short_circuits_before_the_guide(monkeypatch):
    guide_called = False

    async def fake_transcribe(wav):
        return "   "

    async def fake_stream_reply(user_text, session):
        nonlocal guide_called
        guide_called = True
        yield Delta(text="should not happen")

    monkeypatch.setattr(local_call.local_audio_client, "transcribe", fake_transcribe)
    monkeypatch.setattr(local_call, "stream_reply", fake_stream_reply)

    result = asyncio.run(local_call.run_turn(RECORDING_URL, GuideSession()))

    assert guide_called is False
    assert result.outcome == "no_speech"
    assert result.reply_text == "Say again?"
    assert result.reply_wav == b"WAV:Say again?"


def test_recording_fetch_failure_becomes_a_spoken_error(monkeypatch):
    async def fake_fetch(recording_url):
        raise RuntimeError("recording gone")

    monkeypatch.setattr(local_call, "fetch_recording_wav", fake_fetch)

    result = asyncio.run(local_call.run_turn(RECORDING_URL, GuideSession()))

    assert result.outcome == "error"
    assert result.reply_wav == b"WAV:Trouble."


def test_guide_failure_becomes_a_spoken_error(monkeypatch):
    async def fake_stream_reply(user_text, session):
        raise RuntimeError("guide exploded")
        yield  # pragma: no cover -- makes this an async generator

    monkeypatch.setattr(local_call, "stream_reply", fake_stream_reply)

    result = asyncio.run(local_call.run_turn(RECORDING_URL, GuideSession()))

    assert result.outcome == "error"
    assert result.reply_wav == b"WAV:Trouble."


def test_guide_producing_no_text_becomes_a_spoken_error(monkeypatch):
    async def fake_stream_reply(user_text, session):
        yield Delta(text="   ")

    monkeypatch.setattr(local_call, "stream_reply", fake_stream_reply)

    result = asyncio.run(local_call.run_turn(RECORDING_URL, GuideSession()))

    assert result.outcome == "error"


def test_exceeding_the_budget_becomes_a_spoken_timeout(monkeypatch):
    monkeypatch.setattr(config, "LOCAL_TURN_BUDGET_SECONDS", 0.05)

    async def slow_fetch(recording_url):
        await asyncio.sleep(0.5)
        return b"RIFFrecording"

    monkeypatch.setattr(local_call, "fetch_recording_wav", slow_fetch)

    result = asyncio.run(local_call.run_turn(RECORDING_URL, GuideSession()))

    assert result.outcome == "timeout"
    assert result.reply_wav == b"WAV:Too slow."


def test_fallback_synthesis_failing_still_returns_a_result(monkeypatch):
    async def fake_fetch(recording_url):
        raise RuntimeError("recording gone")

    async def failing_synthesize(text):
        raise RuntimeError("tts down")

    monkeypatch.setattr(local_call, "fetch_recording_wav", fake_fetch)
    monkeypatch.setattr(local_call.local_audio_client, "synthesize", failing_synthesize)

    result = asyncio.run(local_call.run_turn(RECORDING_URL, GuideSession()))

    assert result.outcome == "error"
    assert result.reply_wav is None
    # The phrase survives even though GuideAnts couldn't speak it, so the
    # caller of run_turn can still fall back to Twilio's own <Say> instead of
    # leaving the caller in silence -- see local_demo_api._turn_response.
    assert result.reply_text == "Trouble."


def test_no_speech_turn_speaks_the_no_speech_phrase():
    result = asyncio.run(local_call.no_speech_turn())

    assert result.outcome == "no_speech"
    assert result.reply_wav == b"WAV:Say again?"


def test_session_is_passed_through_to_the_guide(monkeypatch):
    seen = {}

    async def fake_stream_reply(user_text, session):
        seen["text"] = user_text
        seen["session"] = session
        yield Delta(text="ok")

    monkeypatch.setattr(local_call, "stream_reply", fake_stream_reply)
    session = GuideSession(caller_phone="+15551234567")

    asyncio.run(local_call.run_turn(RECORDING_URL, session))

    assert seen["text"] == "when do you open"
    assert seen["session"] is session
