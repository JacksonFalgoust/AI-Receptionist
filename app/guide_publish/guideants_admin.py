"""The only module that talks to GuideAnts' *authoring* API.

Two credentials exist and they are easy to confuse:
  - config.GUIDEANTS_API_KEY  -> the PUBLISHED guide's key, used by
    app/guide_client.py on calls.
  - the admin email/password here -> a GuideAnts user with the Admin role.
    /api/guides is RequireAuthorization("RequireAdmin").

Login returns the user in the response body but issues the JWT as an
HTTP-only cookie; the bearer handler falls back to that cookie when no
Authorization header is present. So this client holds a cookie jar. The
token has a finite lifetime, hence the single re-login-and-retry on 401.
"""

from __future__ import annotations

import logging

import httpx

from .. import config

logger = logging.getLogger(__name__)

_LOGIN_PATH = "/api/auth/login"
_IMPORT_PATH = "/api/guides/import"

# Cached across publishes so a burst of them does not re-authenticate each
# time. Cleared on 401 and by reset_session() in tests.
_cookies: dict[str, str] | None = None


class GuideAntsAdminError(RuntimeError):
    """A call to GuideAnts' authoring API failed."""


class GuideAntsNotConfigured(GuideAntsAdminError):
    """No admin credentials are configured, so publishing is unavailable."""


def is_configured() -> bool:
    return bool(config.GUIDEANTS_ADMIN_EMAIL and config.GUIDEANTS_ADMIN_PASSWORD)


def reset_session() -> None:
    global _cookies
    _cookies = None


async def _login(client: httpx.AsyncClient) -> dict[str, str]:
    try:
        response = await client.post(
            f"{config.GUIDEANTS_BASE_URL}{_LOGIN_PATH}",
            json={
                "email": config.GUIDEANTS_ADMIN_EMAIL,
                "password": config.GUIDEANTS_ADMIN_PASSWORD,
            },
        )
    except httpx.HTTPError as exc:
        raise GuideAntsAdminError(f"GuideAnts unreachable at login: {exc}") from exc
    if response.status_code != 200:
        raise GuideAntsAdminError(
            f"could not log in to GuideAnts as {config.GUIDEANTS_ADMIN_EMAIL} "
            f"(HTTP {response.status_code}) -- check GUIDEANTS_ADMIN_EMAIL/"
            "GUIDEANTS_ADMIN_PASSWORD and that the account has the Admin role"
        )
    return dict(response.cookies)


async def _post_bundle(
    client: httpx.AsyncClient, cookies: dict[str, str], zip_bytes: bytes
) -> httpx.Response:
    try:
        return await client.post(
            f"{config.GUIDEANTS_BASE_URL}{_IMPORT_PATH}",
            cookies=cookies,
            files={"file": ("guide.zip", zip_bytes, "application/zip")},
        )
    except httpx.HTTPError as exc:
        raise GuideAntsAdminError(f"GuideAnts unreachable on import: {exc}") from exc


async def import_bundle(zip_bytes: bytes) -> dict:
    """Uploads a bundle, updating the live guide in place. Returns
    GuideAnts' ImportGuideResultDto as a dict (its `warnings` matter --
    surface them)."""
    global _cookies
    if not is_configured():
        raise GuideAntsNotConfigured(
            "GUIDEANTS_ADMIN_EMAIL and GUIDEANTS_ADMIN_PASSWORD are not set, "
            "so publishing to GuideAnts is disabled"
        )

    async with httpx.AsyncClient(timeout=config.GUIDEANTS_TIMEOUT_SECONDS) as client:
        cookies = _cookies or await _login(client)
        response = await _post_bundle(client, cookies, zip_bytes)

        if response.status_code == 401:
            # Token expired between publishes: re-authenticate once.
            logger.info("GuideAnts import returned 401; re-authenticating once")
            cookies = await _login(client)
            response = await _post_bundle(client, cookies, zip_bytes)

        if response.status_code == 401:
            _cookies = None
            raise GuideAntsAdminError(
                "GuideAnts rejected the import with 401 after re-authenticating"
            )
        if response.status_code >= 400:
            detail = ""
            try:
                detail = response.json().get("error", "")
            except ValueError:
                detail = response.text
            raise GuideAntsAdminError(
                f"GuideAnts rejected the import (HTTP {response.status_code}): {detail}"
            )

        _cookies = cookies
        return response.json()
