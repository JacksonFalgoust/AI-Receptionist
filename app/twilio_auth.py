import hashlib
import hmac
import logging
import time
from typing import TYPE_CHECKING

from twilio.request_validator import RequestValidator

from . import config

if TYPE_CHECKING:
    from fastapi import Request

logger = logging.getLogger("voice_receptionist")


def enforcement_enabled() -> bool:
    return bool(config.TWILIO_AUTH_TOKEN)


async def validate_twiml_request(request: "Request") -> bool:
    if not enforcement_enabled():
        logger.warning("TWILIO_AUTH_TOKEN not set; skipping /twiml signature validation")
        return True

    scheme = request.headers.get("x-forwarded-proto", "https")
    host = request.headers.get("host", request.url.hostname)
    url = f"{scheme}://{host}{request.url.path}"

    params = dict(await request.form())

    signature = request.headers.get("X-Twilio-Signature", "")

    return RequestValidator(config.TWILIO_AUTH_TOKEN).validate(url, params, signature)


def mint_ws_token(call_sid: str) -> str:
    expiry = int(time.time()) + config.WS_TOKEN_TTL_SECONDS
    mac = hmac.new(
        config.TWILIO_AUTH_TOKEN.encode(),
        f"{expiry}.{call_sid}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{expiry}.{mac}"


def verify_ws_token(token: str, call_sid: str) -> bool:
    if not enforcement_enabled():
        return True

    try:
        expiry_str, provided_mac = token.split(".", 1)
        expiry = int(expiry_str)
    except (ValueError, IndexError):
        return False

    if expiry < time.time():
        return False

    expected_mac = hmac.new(
        config.TWILIO_AUTH_TOKEN.encode(),
        f"{expiry}.{call_sid}".encode(),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(provided_mac, expected_mac)
