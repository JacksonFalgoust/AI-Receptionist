import asyncio

import pytest

from app import config, recording_fetch
from app.recording_fetch import RecordingUnavailable, fetch_recording_wav

RECORDING_URL = "https://api.twilio.com/2010-04-01/Accounts/AC1/Recordings/RE1"


class FakeResponse:
    def __init__(self, status_code, content=b"", text=""):
        self.status_code = status_code
        self.content = content
        self.text = text


class FakeAsyncClient:
    calls = []
    responses = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, *, auth=None):
        FakeAsyncClient.calls.append({"url": url, "auth": auth})
        return FakeAsyncClient.responses.pop(0)


@pytest.fixture(autouse=True)
def twilio_config(monkeypatch):
    FakeAsyncClient.calls = []
    FakeAsyncClient.responses = []
    monkeypatch.setattr(config, "TWILIO_ACCOUNT_SID", "AC1")
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "tok")
    monkeypatch.setattr(config, "LOCAL_RECORDING_FETCH_ATTEMPTS", 3)
    monkeypatch.setattr(config, "LOCAL_RECORDING_FETCH_DELAY_SECONDS", 0.0)
    monkeypatch.setattr(
        recording_fetch, "httpx", type("_M", (), {"AsyncClient": FakeAsyncClient})
    )


def test_appends_wav_and_uses_basic_auth():
    FakeAsyncClient.responses = [FakeResponse(200, content=b"RIFFrecording")]

    result = asyncio.run(fetch_recording_wav(RECORDING_URL))

    assert result == b"RIFFrecording"
    call = FakeAsyncClient.calls[0]
    assert call["url"] == RECORDING_URL + ".wav"
    assert call["auth"] == ("AC1", "tok")


def test_retries_while_media_is_not_yet_completed():
    FakeAsyncClient.responses = [
        FakeResponse(404, text="not found"),
        FakeResponse(404, text="not found"),
        FakeResponse(200, content=b"RIFFrecording"),
    ]

    result = asyncio.run(fetch_recording_wav(RECORDING_URL))

    assert result == b"RIFFrecording"
    assert len(FakeAsyncClient.calls) == 3


def test_gives_up_after_configured_attempts():
    FakeAsyncClient.responses = [FakeResponse(404, text="not found")] * 3

    with pytest.raises(RecordingUnavailable):
        asyncio.run(fetch_recording_wav(RECORDING_URL))

    assert len(FakeAsyncClient.calls) == 3


def test_non_404_error_fails_immediately_without_retrying():
    FakeAsyncClient.responses = [FakeResponse(401, text="unauthorized")]

    with pytest.raises(RecordingUnavailable):
        asyncio.run(fetch_recording_wav(RECORDING_URL))

    assert len(FakeAsyncClient.calls) == 1


def test_raises_when_credentials_unset(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "")

    with pytest.raises(RecordingUnavailable):
        asyncio.run(fetch_recording_wav(RECORDING_URL))

    assert FakeAsyncClient.calls == []
