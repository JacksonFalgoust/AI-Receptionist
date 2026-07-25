import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from twilio.request_validator import RequestValidator

from app import config, twilio_auth


def test_enforcement_enabled_true(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-token")
    assert twilio_auth.enforcement_enabled() is True


def test_enforcement_enabled_false(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "")
    assert twilio_auth.enforcement_enabled() is False


def test_mint_and_verify_ws_token_roundtrip(monkeypatch):
    token_secret = "test-secret-token"
    call_sid = "CA1234567890abcdef"
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", token_secret)
    monkeypatch.setattr(config, "WS_TOKEN_TTL_SECONDS", 120)

    token = twilio_auth.mint_ws_token(call_sid)
    assert twilio_auth.verify_ws_token(token, call_sid) is True


def test_verify_ws_token_wrong_call_sid(monkeypatch):
    token_secret = "test-secret-token"
    call_sid = "CA1234567890abcdef"
    wrong_call_sid = "CA0000000000xxxxxx"
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", token_secret)
    monkeypatch.setattr(config, "WS_TOKEN_TTL_SECONDS", 120)

    token = twilio_auth.mint_ws_token(call_sid)
    assert twilio_auth.verify_ws_token(token, wrong_call_sid) is False


def test_verify_ws_token_tampered_mac(monkeypatch):
    token_secret = "test-secret-token"
    call_sid = "CA1234567890abcdef"
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", token_secret)
    monkeypatch.setattr(config, "WS_TOKEN_TTL_SECONDS", 120)

    token = twilio_auth.mint_ws_token(call_sid)
    expiry, mac = token.split(".", 1)
    tampered_token = f"{expiry}.{'0' * len(mac)}"
    assert twilio_auth.verify_ws_token(tampered_token, call_sid) is False


def test_verify_ws_token_malformed_no_separator(monkeypatch):
    token_secret = "test-secret-token"
    call_sid = "CA1234567890abcdef"
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", token_secret)

    malformed_token = "noseparatorhere"
    assert twilio_auth.verify_ws_token(malformed_token, call_sid) is False


def test_verify_ws_token_malformed_non_integer_expiry(monkeypatch):
    token_secret = "test-secret-token"
    call_sid = "CA1234567890abcdef"
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", token_secret)

    malformed_token = "notanint.somemac"
    assert twilio_auth.verify_ws_token(malformed_token, call_sid) is False


def test_verify_ws_token_expired(monkeypatch):
    token_secret = "test-secret-token"
    call_sid = "CA1234567890abcdef"
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", token_secret)
    monkeypatch.setattr(config, "WS_TOKEN_TTL_SECONDS", 120)

    token = twilio_auth.mint_ws_token(call_sid)

    future_time = time.time() + 200
    monkeypatch.setattr(twilio_auth, "time", MagicMock())
    twilio_auth.time.time.return_value = future_time

    assert twilio_auth.verify_ws_token(token, call_sid) is False


def test_verify_ws_token_not_enforced(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "")

    garbage_token = "garbage_token_that_should_be_invalid"
    assert twilio_auth.verify_ws_token(garbage_token, "any_call_sid") is True


def test_validate_twiml_request_not_enforced(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "")

    async def run_test():
        fake_request = MagicMock()
        result = await twilio_auth.validate_twiml_request(fake_request)
        assert result is True

    asyncio.run(run_test())


def test_validate_twiml_request_valid_signature(monkeypatch):
    token_secret = "test-auth-token"
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", token_secret)

    async def run_test():
        url = "https://example.com/twiml"
        params = {"CallSid": "CA1234567890abcdef", "From": "+15551234567"}

        validator = RequestValidator(token_secret)
        signature = validator.compute_signature(url, params)

        fake_form = AsyncMock(return_value=params)
        fake_request = SimpleNamespace(
            headers={"host": "example.com", "X-Twilio-Signature": signature},
            url=SimpleNamespace(path="/twiml", hostname="example.com"),
            form=fake_form,
        )

        result = await twilio_auth.validate_twiml_request(fake_request)
        assert result is True

    asyncio.run(run_test())


def test_validate_twiml_request_invalid_signature(monkeypatch):
    token_secret = "test-auth-token"
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", token_secret)

    async def run_test():
        url = "https://example.com/twiml"
        params = {"CallSid": "CA1234567890abcdef", "From": "+15551234567"}

        fake_form = AsyncMock(return_value=params)
        fake_request = SimpleNamespace(
            headers={
                "host": "example.com",
                "X-Twilio-Signature": "invalid_signature_here",
            },
            url=SimpleNamespace(path="/twiml", hostname="example.com"),
            form=fake_form,
        )

        result = await twilio_auth.validate_twiml_request(fake_request)
        assert result is False

    asyncio.run(run_test())


def test_validate_twiml_request_uses_x_forwarded_proto(monkeypatch):
    token_secret = "test-auth-token"
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", token_secret)

    async def run_test():
        url = "http://example.com/twiml"
        params = {"CallSid": "CA1234567890abcdef"}

        validator = RequestValidator(token_secret)
        signature = validator.compute_signature(url, params)

        fake_form = AsyncMock(return_value=params)
        fake_request = SimpleNamespace(
            headers={
                "host": "example.com",
                "x-forwarded-proto": "http",
                "X-Twilio-Signature": signature,
            },
            url=SimpleNamespace(path="/twiml", hostname="example.com"),
            form=fake_form,
        )

        result = await twilio_auth.validate_twiml_request(fake_request)
        assert result is True

    asyncio.run(run_test())


def test_validate_twiml_request_missing_headers_defaults(monkeypatch):
    token_secret = "test-auth-token"
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", token_secret)

    async def run_test():
        url = "https://example.com/twiml"
        params = {"CallSid": "CA1234567890abcdef"}

        validator = RequestValidator(token_secret)
        signature = validator.compute_signature(url, params)

        fake_form = AsyncMock(return_value=params)
        fake_request = SimpleNamespace(
            headers={"X-Twilio-Signature": signature},
            url=SimpleNamespace(path="/twiml", hostname="example.com"),
            form=fake_form,
        )

        result = await twilio_auth.validate_twiml_request(fake_request)
        assert result is True

    asyncio.run(run_test())
