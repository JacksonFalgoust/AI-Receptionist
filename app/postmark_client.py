"""Outbound email via Postmark's Email API. Postmark is plain HTTP/JSON, so
unlike twilio_client.py (a blocking SDK offloaded via asyncio.to_thread) this
uses httpx.AsyncClient directly, the same way booqable_client.py does."""

from __future__ import annotations

from typing import Any

import httpx

from . import config


class PostmarkError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        error_code: int | None = None,
        payload: Any = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.payload = payload


class PostmarkClient:
    def __init__(
        self,
        server_token: str | None = None,
        from_email: str | None = None,
        message_stream: str | None = None,
        base_url: str | None = None,
    ):
        self.server_token = server_token or config.POSTMARK_SERVER_TOKEN
        self.from_email = from_email or config.POSTMARK_FROM_EMAIL
        self.message_stream = message_stream or config.POSTMARK_MESSAGE_STREAM
        self.base_url = (base_url or config.POSTMARK_API_URL).rstrip("/")
        if not (self.server_token and self.from_email):
            raise PostmarkError(
                "POSTMARK_SERVER_TOKEN/POSTMARK_FROM_EMAIL are not configured"
            )

    async def send_email(
        self,
        *,
        to: str,
        subject: str,
        text_body: str,
        html_body: str | None = None,
        tag: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "From": self.from_email,
            "To": to,
            "Subject": subject,
            "TextBody": text_body,
            "MessageStream": self.message_stream,
        }
        if html_body is not None:
            payload["HtmlBody"] = html_body
        if tag is not None:
            payload["Tag"] = tag

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/email",
                headers={
                    "X-Postmark-Server-Token": self.server_token,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json=payload,
            )

        try:
            body = response.json()
        except Exception:
            body = {"raw": response.text}

        error_code = body.get("ErrorCode") if isinstance(body, dict) else None
        if response.status_code >= 400 or (error_code not in (None, 0)):
            message = body.get("Message") if isinstance(body, dict) else body
            raise PostmarkError(
                f"Postmark send failed (HTTP {response.status_code}, ErrorCode {error_code}): {message}",
                status_code=response.status_code,
                error_code=error_code,
                payload=body,
            )
        return {
            "message_id": body["MessageID"],
            "to": body["To"],
            "submitted_at": body["SubmittedAt"],
        }
