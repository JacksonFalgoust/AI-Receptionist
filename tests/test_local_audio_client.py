import asyncio

import pytest

from app import config, local_audio_client
from app.local_audio_client import GuideAudioError, synthesize, transcribe


class FakeResponse:
    def __init__(self, status_code, json_data=None, content=b"", text=""):
        self.status_code = status_code
        self._json_data = json_data
        self.content = content
        self.text = text or str(json_data)

    def json(self):
        if self._json_data is None:
            raise ValueError("not json")
        return self._json_data


class FakeAsyncClient:
    calls = []
    response = None
    init_kwargs = {}

    def __init__(self, *args, **kwargs):
        FakeAsyncClient.init_kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, *, headers=None, files=None, data=None, json=None):
        FakeAsyncClient.calls.append(
            {"url": url, "headers": headers, "files": files, "data": data, "json": json}
        )
        return FakeAsyncClient.response


@pytest.fixture(autouse=True)
def guideants_config(monkeypatch):
    FakeAsyncClient.calls = []
    monkeypatch.setattr(config, "GUIDEANTS_BASE_URL", "http://guideants.test")
    monkeypatch.setattr(config, "GUIDEANTS_PUB_ID", "pub-123")
    monkeypatch.setattr(config, "GUIDEANTS_API_KEY", "secret-key")
    monkeypatch.setattr(config, "GUIDEANTS_TRANSCRIPTION_MODEL", "transcription")
    monkeypatch.setattr(config, "GUIDEANTS_SPEECH_MODEL", "speech")
    monkeypatch.setattr(config, "GUIDEANTS_SPEECH_VOICE", "")
    monkeypatch.setattr(
        local_audio_client, "httpx", type("_M", (), {"AsyncClient": FakeAsyncClient})
    )


def test_transcribe_posts_multipart_named_audio_wav():
    FakeAsyncClient.response = FakeResponse(200, {"text": "  I need a bike  "})

    result = asyncio.run(transcribe(b"RIFFfake"))

    assert result == "I need a bike"
    call = FakeAsyncClient.calls[0]
    assert call["url"] == "http://guideants.test/api/published/openai/pub-123/v1/audio/transcriptions"
    assert call["headers"]["Authorization"] == "Bearer secret-key"
    # The filename extension is load-bearing: GuideAnts rejects an
    # unrecognized one with provider_not_ready.
    assert call["files"]["file"][0] == "audio.wav"
    assert call["files"]["file"][1] == b"RIFFfake"
    assert call["files"]["file"][2] == "audio/wav"
    assert call["data"]["model"] == "transcription"
    assert FakeAsyncClient.init_kwargs["timeout"] == config.GUIDEANTS_TIMEOUT_SECONDS


def test_transcribe_raises_on_http_error():
    FakeAsyncClient.response = FakeResponse(503, text="provider_not_ready")

    with pytest.raises(GuideAudioError) as exc_info:
        asyncio.run(transcribe(b"RIFFfake"))

    assert exc_info.value.status_code == 503


def test_transcribe_raises_when_body_has_no_text():
    FakeAsyncClient.response = FakeResponse(200, {"unexpected": "shape"})

    with pytest.raises(GuideAudioError):
        asyncio.run(transcribe(b"RIFFfake"))


def test_synthesize_posts_json_and_returns_bytes():
    FakeAsyncClient.response = FakeResponse(200, content=b"RIFFaudio")

    result = asyncio.run(synthesize("We open at nine."))

    assert result == b"RIFFaudio"
    call = FakeAsyncClient.calls[0]
    assert call["url"] == "http://guideants.test/api/published/openai/pub-123/v1/audio/speech"
    assert call["json"] == {
        "model": "speech",
        "input": "We open at nine.",
        "responseFormat": "wav",
    }


def test_synthesize_includes_voice_when_configured(monkeypatch):
    monkeypatch.setattr(config, "GUIDEANTS_SPEECH_VOICE", "amy")
    FakeAsyncClient.response = FakeResponse(200, content=b"RIFFaudio")

    asyncio.run(synthesize("Hello."))

    assert FakeAsyncClient.calls[0]["json"]["voice"] == "amy"


def test_synthesize_raises_on_empty_audio():
    FakeAsyncClient.response = FakeResponse(200, content=b"")

    with pytest.raises(GuideAudioError):
        asyncio.run(synthesize("Hello."))


def test_raises_when_pub_id_unset(monkeypatch):
    monkeypatch.setattr(config, "GUIDEANTS_PUB_ID", "")

    with pytest.raises(GuideAudioError):
        asyncio.run(transcribe(b"RIFFfake"))
