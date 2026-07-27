import asyncio

import pytest

from app import config, postmark_client
from app.postmark_client import PostmarkClient, PostmarkError


class FakeResponse:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json_data = json_data
        self.text = str(json_data)

    def json(self):
        return self._json_data


class FakeAsyncClient:
    calls = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, *, headers=None, json=None):
        FakeAsyncClient.calls.append({"url": url, "headers": headers, "json": json})
        return FakeAsyncClient.response


def test_raises_when_unconfigured(monkeypatch):
    monkeypatch.setattr(config, "POSTMARK_SERVER_TOKEN", "")
    monkeypatch.setattr(config, "POSTMARK_FROM_EMAIL", "")
    with pytest.raises(PostmarkError):
        PostmarkClient()


def test_raises_when_missing_from_email(monkeypatch):
    monkeypatch.setattr(config, "POSTMARK_SERVER_TOKEN", "server-token")
    monkeypatch.setattr(config, "POSTMARK_FROM_EMAIL", "")
    with pytest.raises(PostmarkError):
        PostmarkClient()


def test_send_email_happy_path(monkeypatch):
    FakeAsyncClient.calls = []
    FakeAsyncClient.response = FakeResponse(
        200,
        {
            "To": "jane@example.com",
            "SubmittedAt": "2026-07-27T12:00:00Z",
            "MessageID": "msg-123",
            "ErrorCode": 0,
            "Message": "OK",
        },
    )
    monkeypatch.setattr(postmark_client, "httpx", type("_M", (), {"AsyncClient": FakeAsyncClient}))

    client = PostmarkClient(server_token="tok", from_email="receptionist@example.com")
    result = asyncio.run(
        client.send_email(
            to="jane@example.com",
            subject="Your payment link",
            text_body="Here's your link: https://example.com/pay/order_1",
        )
    )

    assert result == {
        "message_id": "msg-123",
        "to": "jane@example.com",
        "submitted_at": "2026-07-27T12:00:00Z",
    }
    call = FakeAsyncClient.calls[0]
    assert call["url"] == "https://api.postmarkapp.com/email"
    assert call["headers"]["X-Postmark-Server-Token"] == "tok"
    assert call["json"]["From"] == "receptionist@example.com"
    assert call["json"]["To"] == "jane@example.com"
    assert call["json"]["Subject"] == "Your payment link"
    assert call["json"]["TextBody"] == "Here's your link: https://example.com/pay/order_1"
    assert call["json"]["MessageStream"] == "outbound"


def test_send_email_wraps_http_error(monkeypatch):
    FakeAsyncClient.calls = []
    FakeAsyncClient.response = FakeResponse(
        422, {"ErrorCode": 300, "Message": "Invalid email request"}
    )
    monkeypatch.setattr(postmark_client, "httpx", type("_M", (), {"AsyncClient": FakeAsyncClient}))

    client = PostmarkClient(server_token="tok", from_email="receptionist@example.com")
    with pytest.raises(PostmarkError) as exc_info:
        asyncio.run(client.send_email(to="not-an-email", subject="hi", text_body="hi"))

    assert exc_info.value.status_code == 422
    assert exc_info.value.error_code == 300


def test_send_email_raises_on_200_with_nonzero_error_code(monkeypatch):
    FakeAsyncClient.calls = []
    FakeAsyncClient.response = FakeResponse(
        200, {"ErrorCode": 406, "Message": "You tried to send to a recipient that has been marked as inactive"}
    )
    monkeypatch.setattr(postmark_client, "httpx", type("_M", (), {"AsyncClient": FakeAsyncClient}))

    client = PostmarkClient(server_token="tok", from_email="receptionist@example.com")
    with pytest.raises(PostmarkError) as exc_info:
        asyncio.run(client.send_email(to="bounced@example.com", subject="hi", text_body="hi"))

    assert exc_info.value.error_code == 406
