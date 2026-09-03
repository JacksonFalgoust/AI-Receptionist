import asyncio

import httpx
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
    # Optional queue of FakeResponse/Exception instances, consumed one per
    # call -- lets a test script a failure followed by a success. When unset,
    # every call just returns `response`.
    responses = None
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
        if FakeAsyncClient.responses is not None:
            next_item = FakeAsyncClient.responses.pop(0)
            if isinstance(next_item, Exception):
                raise next_item
            return next_item
        return FakeAsyncClient.response


@pytest.fixture(autouse=True)
def guideants_config(monkeypatch):
    FakeAsyncClient.calls = []
    FakeAsyncClient.responses = None
    monkeypatch.setattr(config, "GUIDEANTS_BASE_URL", "http://guideants.test")
    monkeypatch.setattr(config, "GUIDEANTS_PUB_ID", "pub-123")
    monkeypatch.setattr(config, "GUIDEANTS_API_KEY", "secret-key")
    monkeypatch.setattr(config, "GUIDEANTS_TRANSCRIPTION_MODEL", "transcription")
    monkeypatch.setattr(config, "GUIDEANTS_SPEECH_MODEL", "speech")
    monkeypatch.setattr(config, "GUIDEANTS_SPEECH_VOICE", "")
    # Real delay would make every retry test slow for no reason; the retry
    # count is what these tests check, not the backoff timing.
    monkeypatch.setattr(config, "GUIDEANTS_RETRY_DELAY_SECONDS", 0.0)
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


# --- Retry on GuideAnts' transient reconcile-cycle failures -----------------
# GuideAnts periodically reloads its local ASR/TTS engines without waiting
# out an in-flight request first, so a request whose timing overlaps that
# cycle can have its connection dropped or get a 5xx moments before the
# engine is healthy again. One retry rides past it.


def test_transcribe_retries_once_on_connection_error_then_succeeds():
    FakeAsyncClient.responses = [
        httpx.RequestError("Remote end closed connection without response"),
        FakeResponse(200, {"text": "I need a bike"}),
    ]

    result = asyncio.run(transcribe(b"RIFFfake"))

    assert result == "I need a bike"
    assert len(FakeAsyncClient.calls) == 2


def test_transcribe_gives_up_after_one_retry_on_repeated_connection_error():
    FakeAsyncClient.responses = [
        httpx.RequestError("Remote end closed connection without response"),
        httpx.RequestError("Remote end closed connection without response"),
    ]

    with pytest.raises(GuideAudioError):
        asyncio.run(transcribe(b"RIFFfake"))

    assert len(FakeAsyncClient.calls) == 2


def test_synthesize_retries_once_on_503_then_succeeds():
    FakeAsyncClient.responses = [
        FakeResponse(503, text="model_not_loaded"),
        FakeResponse(200, content=b"RIFFaudio"),
    ]

    result = asyncio.run(synthesize("We open at nine."))

    assert result == b"RIFFaudio"
    assert len(FakeAsyncClient.calls) == 2


def test_synthesize_does_not_retry_on_non_retryable_4xx():
    FakeAsyncClient.responses = [FakeResponse(400, text="bad request")]

    with pytest.raises(GuideAudioError):
        asyncio.run(synthesize("We open at nine."))

    assert len(FakeAsyncClient.calls) == 1
