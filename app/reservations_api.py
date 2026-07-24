"""Booqable connectivity check for this app -- the actual reservation
operations (catalog, availability, customers, create/cancel/pay) are no
longer an HTTP surface at all. They're executed in-process by
app/guide_client.py as GuideAnts Client Actions tool calls (see
guide-demo/reservations-client-tool.json and docs/ARCHITECTURE.md's
"Client-side tool calls" section) instead of being called by GuideAnts over
HTTP, so there's no `/api/reservations/*` endpoint left for anyone but this
app to invoke them through.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from . import config
from .booqable_client import BooqableClient, BooqableError

router = APIRouter()


@router.get("/api/booqable/ping")
async def ping_booqable() -> dict[str, Any]:
    """Pre-demo connectivity check: confirms BOOQABLE_API_KEY/BOOQABLE_COMPANY_URL
    are correct before relying on them for a live call."""
    try:
        client = BooqableClient()
        locations = await client.get("locations", params={"page[size]": 1})
        company = await client.get("companies/current")
        attrs = client.attrs(company.get("data") or {})
        return {
            "ok": True,
            "company_url": config.BOOQABLE_COMPANY_URL,
            "sample_location_count": len(locations.get("data") or []),
            "company_timezone": attrs.get("default_timezone"),
            "configured_timezone": config.BOOQABLE_TIMEZONE,
        }
    except BooqableError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
