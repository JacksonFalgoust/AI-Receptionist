from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator

from app import config
from app.main import app

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
