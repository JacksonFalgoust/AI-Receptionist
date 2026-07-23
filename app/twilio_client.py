from __future__ import annotations

import asyncio
from typing import Any

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from . import config


class TwilioSmsError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class TwilioSmsClient:
    """Outbound SMS via Twilio's REST API. The twilio SDK is synchronous
    (built on requests), unlike the httpx.AsyncClient used for Booqable --
    send_sms offloads the blocking call via asyncio.to_thread so it doesn't
    stall the event loop that also serves the live voice WebSocket bridge."""

    def __init__(
        self,
        account_sid: str | None = None,
        auth_token: str | None = None,
        from_number: str | None = None,
    ):
        self.account_sid = account_sid or config.TWILIO_ACCOUNT_SID
        self.auth_token = auth_token or config.TWILIO_AUTH_TOKEN
        self.from_number = from_number or config.TWILIO_FROM_NUMBER
        if not (self.account_sid and self.auth_token and self.from_number):
            raise TwilioSmsError(
                "TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN/TWILIO_FROM_NUMBER are not configured"
            )
        self._client = Client(self.account_sid, self.auth_token)

    async def send_sms(self, to: str, body: str) -> dict[str, Any]:
        try:
            message = await asyncio.to_thread(
                self._client.messages.create, to=to, from_=self.from_number, body=body
            )
        except TwilioRestException as exc:
            raise TwilioSmsError(str(exc), status_code=exc.status) from exc
        return {"sid": message.sid, "status": message.status}
