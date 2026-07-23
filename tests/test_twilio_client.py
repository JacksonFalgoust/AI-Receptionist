import asyncio
from unittest.mock import MagicMock

import pytest
from twilio.base.exceptions import TwilioRestException

from app import config, twilio_client
from app.twilio_client import TwilioSmsClient, TwilioSmsError


def test_raises_when_unconfigured(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_ACCOUNT_SID", "")
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "")
    monkeypatch.setattr(config, "TWILIO_FROM_NUMBER", "")
    with pytest.raises(TwilioSmsError):
        TwilioSmsClient()


def test_raises_when_partially_configured(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_ACCOUNT_SID", "ACxxxx")
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "")
    monkeypatch.setattr(config, "TWILIO_FROM_NUMBER", "+15555550100")
    with pytest.raises(TwilioSmsError):
        TwilioSmsClient()


def test_send_sms_happy_path(monkeypatch):
    fake_message = MagicMock(sid="SM123", status="queued")
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_message
    monkeypatch.setattr(twilio_client, "Client", lambda sid, token: fake_client)

    client = TwilioSmsClient(account_sid="ACxxxx", auth_token="tok", from_number="+15555550100")
    result = asyncio.run(
        client.send_sms(to="+15555550199", body="Pay here: https://example.com/pay/order_1")
    )

    assert result == {"sid": "SM123", "status": "queued"}
    fake_client.messages.create.assert_called_once_with(
        to="+15555550199", from_="+15555550100", body="Pay here: https://example.com/pay/order_1"
    )


def test_send_sms_wraps_twilio_error(monkeypatch):
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = TwilioRestException(
        status=400, uri="/Messages", msg="Invalid 'To' Phone Number", code=21211
    )
    monkeypatch.setattr(twilio_client, "Client", lambda sid, token: fake_client)

    client = TwilioSmsClient(account_sid="ACxxxx", auth_token="tok", from_number="+15555550100")
    with pytest.raises(TwilioSmsError) as exc_info:
        asyncio.run(client.send_sms(to="not-a-number", body="hi"))

    assert exc_info.value.status_code == 400
