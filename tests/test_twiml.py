import asyncio

from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator

from app import config
from app.main import app, reservations

client = TestClient(app)

TWIML_URL = "https://testserver/twiml"


def test_twiml_valid_signature_returns_200_with_token(monkeypatch):
    token_secret = "test-auth-token"
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", token_secret)

    params = {"CallSid": "CA1234567890abcdef", "From": "+15551234567"}
    signature = RequestValidator(token_secret).compute_signature(TWIML_URL, params)

    response = client.post(
        "/twiml", data=params, headers={"X-Twilio-Signature": signature}
    )

    assert response.status_code == 200
    assert "wss://testserver/ws?token=" in response.text


def test_twiml_missing_or_wrong_signature_returns_403(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-auth-token")

    params = {"CallSid": "CA1234567890abcdef", "From": "+15551234567"}

    response = client.post(
        "/twiml", data=params, headers={"X-Twilio-Signature": "wrong-signature"}
    )
    assert response.status_code == 403

    response = client.post("/twiml", data=params)
    assert response.status_code == 403


def test_twiml_no_enforcement_returns_200_regardless_of_signature(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "")

    params = {"CallSid": "CA1234567890abcdef", "From": "+15551234567"}

    response = client.post(
        "/twiml", data=params, headers={"X-Twilio-Signature": "garbage"}
    )

    assert response.status_code == 200
    assert "wss://testserver/ws" in response.text


def test_twiml_known_customer_gets_personalized_greeting(monkeypatch):
    token_secret = "test-auth-token"
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", token_secret)
    monkeypatch.setattr(config, "BOOQABLE_API_KEY", "test-booqable-key")

    async def fake_find_customer(client, *, email=None, phone=None):
        return {"id": "cust_1", "attributes": {"name": "Jane Doe"}}

    monkeypatch.setattr(reservations, "find_customer", fake_find_customer)

    params = {"CallSid": "CA1234567890abcdef", "From": "+15551234567"}
    signature = RequestValidator(token_secret).compute_signature(TWIML_URL, params)

    response = client.post(
        "/twiml", data=params, headers={"X-Twilio-Signature": signature}
    )

    assert response.status_code == 200
    assert "wss://testserver/ws?token=" in response.text
    assert config.WELCOME_BACK_GREETING_TEMPLATE.format(name="Jane") in response.text


def test_twiml_unknown_customer_falls_back_to_default_greeting(monkeypatch):
    token_secret = "test-auth-token"
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", token_secret)
    monkeypatch.setattr(config, "BOOQABLE_API_KEY", "test-booqable-key")

    async def fake_find_customer(client, *, email=None, phone=None):
        return None

    monkeypatch.setattr(reservations, "find_customer", fake_find_customer)

    params = {"CallSid": "CA1234567890abcdef", "From": "+15559999999"}
    signature = RequestValidator(token_secret).compute_signature(TWIML_URL, params)

    response = client.post(
        "/twiml", data=params, headers={"X-Twilio-Signature": signature}
    )

    assert response.status_code == 200
    assert "wss://testserver/ws?token=" in response.text
    assert config.WELCOME_GREETING in response.text


def test_twiml_lookup_raises_falls_back_to_default_greeting(monkeypatch):
    token_secret = "test-auth-token"
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", token_secret)
    monkeypatch.setattr(config, "BOOQABLE_API_KEY", "test-booqable-key")

    async def fake_find_customer(client, *, email=None, phone=None):
        raise RuntimeError("Booqable is down")

    monkeypatch.setattr(reservations, "find_customer", fake_find_customer)

    params = {"CallSid": "CA1234567890abcdef", "From": "+15551112222"}
    signature = RequestValidator(token_secret).compute_signature(TWIML_URL, params)

    response = client.post(
        "/twiml", data=params, headers={"X-Twilio-Signature": signature}
    )

    assert response.status_code == 200
    assert "wss://testserver/ws?token=" in response.text
    assert config.WELCOME_GREETING in response.text


def test_twiml_lookup_timeout_falls_back_to_default_greeting(monkeypatch):
    token_secret = "test-auth-token"
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", token_secret)
    monkeypatch.setattr(config, "BOOQABLE_API_KEY", "test-booqable-key")
    monkeypatch.setattr(config, "CALLER_LOOKUP_TIMEOUT_SECONDS", 0.01)

    async def fake_find_customer(client, *, email=None, phone=None):
        await asyncio.sleep(0.5)
        return {"id": "cust_1", "attributes": {"name": "Jane Doe"}}

    monkeypatch.setattr(reservations, "find_customer", fake_find_customer)

    params = {"CallSid": "CA1234567890abcdef", "From": "+15553334444"}
    signature = RequestValidator(token_secret).compute_signature(TWIML_URL, params)

    response = client.post(
        "/twiml", data=params, headers={"X-Twilio-Signature": signature}
    )

    assert response.status_code == 200
    assert "wss://testserver/ws?token=" in response.text
    assert config.WELCOME_GREETING in response.text
