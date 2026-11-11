"""GET /api/bookings -- read-only console view of Booqable orders. Only GETs
against Booqable; every upstream failure is surfaced as 502 (never Booqable's
own 401/403, which the console's http layer would mistake for an expired
console session)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app import config
from app.booking.booqable_client import BooqableClient
from app.booking.orders import (
    Booking,
    booqable_url,
    fetch_line_items,
    load_orders,
    sort_for_view,
    summarize,
    to_bookings,
)
from app.console.auth import sessions as auth

logger = logging.getLogger(__name__)

router = APIRouter()


def _now() -> datetime:
    return datetime.now(UTC)


class BookingItemOut(BaseModel):
    name: str | None = None
    quantity: int | None = None


class BookingOut(BaseModel):
    id: str
    number: int | None = None
    label: str | None = None
    customerName: str | None = None
    customerPhone: str | None = None
    customerEmail: str | None = None
    items: list[BookingItemOut] | None = None
    itemCount: int | None = None
    startsAt: str | None = None
    stopsAt: str | None = None
    totalCents: int
    payment: str
    booqableUrl: str


class SummaryOut(BaseModel):
    pickupsToday: int
    returnsToday: int
    next7Days: int
    unpaid: int


class BookingsPageOut(BaseModel):
    summary: SummaryOut
    items: list[BookingOut]
    page: int
    pageSize: int
    total: int
    fetchedAt: str


def _to_out(booking: Booking, items: list[dict] | None) -> BookingOut:
    return BookingOut(
        id=booking.id,
        number=booking.number,
        label=booking.label,
        customerName=booking.customer_name,
        customerPhone=booking.customer_phone,
        customerEmail=booking.customer_email,
        items=None if items is None else [BookingItemOut(**item) for item in items],
        itemCount=booking.item_count,
        startsAt=booking.starts_at.isoformat() if booking.starts_at else None,
        stopsAt=booking.stops_at.isoformat() if booking.stops_at else None,
        totalCents=booking.total_cents,
        payment=booking.payment,
        booqableUrl=booqable_url(booking.id),
    )


@router.get("/api/bookings", response_model=BookingsPageOut)
async def list_bookings(
    view: Literal["upcoming", "past"] = "upcoming",
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    refresh: bool = False,
    _session=Depends(auth.require_auth),
) -> BookingsPageOut:
    try:
        client = BooqableClient()
        orders, included, fetched_at = await load_orders(client, refresh=refresh)
        now = _now()
        bookings = to_bookings(orders, included, now=now)
        summary = summarize(bookings, now, ZoneInfo(config.BOOQABLE_TIMEZONE))
        ordered = sort_for_view(bookings, view)
        start = (page - 1) * pageSize
        page_bookings = ordered[start : start + pageSize]
        line_items = await fetch_line_items(client, [b.id for b in page_bookings])
    except Exception as exc:  # noqa: BLE001 -- every upstream failure is a 502
        logger.exception("Bookings load failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return BookingsPageOut(
        summary=SummaryOut(
            pickupsToday=summary.pickups_today,
            returnsToday=summary.returns_today,
            next7Days=summary.next_7_days,
            unpaid=summary.unpaid,
        ),
        items=[_to_out(b, line_items.get(b.id)) for b in page_bookings],
        page=page,
        pageSize=pageSize,
        total=len(ordered),
        fetchedAt=fetched_at.isoformat(),
    )
