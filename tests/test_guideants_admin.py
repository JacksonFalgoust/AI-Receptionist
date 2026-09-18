"""The client for GuideAnts' authoring API.

Auth is unusual and worth stating: POST /api/auth/login returns the user in
the response BODY but delivers the JWT as an HTTP-only cookie, and the
bearer handler falls back to that cookie when no Authorization header is
present. So the client keeps a cookie jar rather than reading a token out
of the response.

Fakes are hand-rolled, matching tests/test_postmark_client.py -- this repo
adds no HTTP-mocking dependency.
"""

import asyncio

import pytest

from app import config
from app.guide_publish import guideants_admin


class FakeResponse:
    def __init__(self, status_code, json_data=None, cookies=None):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.cookies = cookies or {}
        self.text = str(json_data)

    def json(self):
        return self._json_data


class FakeAsyncClient:
    """Records calls and replays a scripted sequence of responses."""

    calls = []
    responses = []

    def __init__(self, *args, **kwargs):
        self.cookies = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, **kwargs):
        FakeAsyncClient.calls.append({"url": url, **kwargs})
        response = FakeAsyncClient.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture(autouse=True)
def _client(monkeypatch):
    FakeAsyncClient.calls = []
    FakeAsyncClient.responses = []
    monkeypatch.setattr(guideants_admin.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(config, "GUIDEANTS_ADMIN_EMAIL", "svc@example.com")
    monkeypatch.setattr(config, "GUIDEANTS_ADMIN_PASSWORD", "secret")
    guideants_admin.reset_session()
    yield


def test_not_configured_when_credentials_are_unset(monkeypatch):
    monkeypatch.setattr(config, "GUIDEANTS_ADMIN_EMAIL", "")
    assert guideants_admin.is_configured() is False


def test_configured_when_credentials_are_set():
    assert guideants_admin.is_configured() is True


def test_import_logs_in_then_uploads():
    FakeAsyncClient.responses = [
        FakeResponse(200, {"email": "svc@example.com"}, cookies={"auth": "jwt"}),
        FakeResponse(200, {"guideId": "abc", "warnings": []}),
    ]
    result = asyncio.run(guideants_admin.import_bundle(b"PK\x03\x04"))

    assert result["guideId"] == "abc"
    assert FakeAsyncClient.calls[0]["url"].endswith("/api/auth/login")
    assert FakeAsyncClient.calls[1]["url"].endswith("/api/guides/import")
    # The zip is sent as multipart, under the field name the endpoint binds.
    assert "files" in FakeAsyncClient.calls[1]


def test_a_401_triggers_exactly_one_relogin_and_retry():
    FakeAsyncClient.responses = [
        FakeResponse(200, {}, cookies={"auth": "jwt"}),   # login
        FakeResponse(401, {"error": "expired"}),           # import -> token expired
        FakeResponse(200, {}, cookies={"auth": "jwt2"}),  # re-login
        FakeResponse(200, {"guideId": "abc"}),             # import retry
    ]
    result = asyncio.run(guideants_admin.import_bundle(b"PK\x03\x04"))
    assert result["guideId"] == "abc"
    assert len(FakeAsyncClient.calls) == 4


def test_a_second_401_gives_up():
    FakeAsyncClient.responses = [
        FakeResponse(200, {}, cookies={"auth": "jwt"}),
        FakeResponse(401, {"error": "expired"}),
        FakeResponse(200, {}, cookies={"auth": "jwt2"}),
        FakeResponse(401, {"error": "expired"}),
    ]
    with pytest.raises(guideants_admin.GuideAntsAdminError, match="401"):
        asyncio.run(guideants_admin.import_bundle(b"PK\x03\x04"))


def test_failed_login_raises_clearly():
    FakeAsyncClient.responses = [FakeResponse(401, {"message": "Invalid email or password."})]
    with pytest.raises(guideants_admin.GuideAntsAdminError, match="log in"):
        asyncio.run(guideants_admin.import_bundle(b"PK\x03\x04"))


def test_import_rejection_surfaces_the_server_message():
    FakeAsyncClient.responses = [
        FakeResponse(200, {}, cookies={"auth": "jwt"}),
        FakeResponse(400, {"error": "Invalid guide export: manifest.json not found"}),
    ]
    with pytest.raises(guideants_admin.GuideAntsAdminError, match="manifest.json not found"):
        asyncio.run(guideants_admin.import_bundle(b"PK\x03\x04"))


def test_unreachable_host_raises_a_clean_error():
    import httpx

    FakeAsyncClient.responses = [httpx.ConnectError("refused")]
    with pytest.raises(guideants_admin.GuideAntsAdminError, match="unreachable"):
        asyncio.run(guideants_admin.import_bundle(b"PK\x03\x04"))


def test_unconfigured_import_raises_not_configured(monkeypatch):
    monkeypatch.setattr(config, "GUIDEANTS_ADMIN_PASSWORD", "")
    with pytest.raises(guideants_admin.GuideAntsNotConfigured):
        asyncio.run(guideants_admin.import_bundle(b"PK\x03\x04"))


@pytest.mark.parametrize("body", ["Guide import failed.", ["manifest.json not found"]])
def test_a_non_dict_error_body_still_raises_a_recorded_admin_error(body):
    """publisher.publish() catches only GuideAntsAdminError. An
    AttributeError from .get() on a bare string or list body would escape
    uncaught, roll back the GuidePublication's failure row, and return an
    unrecorded 500 -- defeating "every failure is recorded"."""
    FakeAsyncClient.responses = [
        FakeResponse(200, {}, cookies={"auth": "jwt"}),
        FakeResponse(400, body),
    ]
    with pytest.raises(guideants_admin.GuideAntsAdminError) as excinfo:
        asyncio.run(guideants_admin.import_bundle(b"PK\x03\x04"))

    assert not isinstance(excinfo.value, AttributeError)
    assert "HTTP 400" in str(excinfo.value)
    # The body is still surfaced rather than swallowed.
    assert str(body) in str(excinfo.value) or body in str(excinfo.value)


def test_an_unparseable_error_body_falls_back_to_the_raw_text():
    class NotJson(FakeResponse):
        def json(self):
            raise ValueError("no JSON")

    FakeAsyncClient.responses = [
        FakeResponse(200, {}, cookies={"auth": "jwt"}),
        NotJson(500, "<html>502 Bad Gateway</html>"),
    ]
    with pytest.raises(guideants_admin.GuideAntsAdminError, match="Bad Gateway"):
        asyncio.run(guideants_admin.import_bundle(b"PK\x03\x04"))
