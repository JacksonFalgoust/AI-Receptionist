"""GET /api/customers -- read-only console view of Booqable customers. Only GETs
against Booqable; every upstream failure is surfaced as 502 (never Booqable's
own 401/403, which the console's http layer would mistake for an expired
console session)."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app import config
from app.booking.booqable_client import BooqableClient
from app.booking.orders import Booking, load_orders, to_bookings
from app.booking.reservations import _customer_phone
from app.console.bookings.api import BookingOut
from app.console.bookings.api import _to_out as _booking_out
from app.console.auth import sessions as auth

logger = logging.getLogger(__name__)

router = APIRouter()

CACHE_TTL_SECONDS = 30

_cache: tuple[float, list[dict[str, Any]], datetime] | None = None


def clear_cache() -> None:
    global _cache
    _cache = None


class CustomerOut(BaseModel):
    id: str
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    createdAt: str | None = None
    booqableUrl: str
    # None when bookings could not be loaded (the list still renders).
    bookingCount: int | None = None
    lastBookingAt: str | None = None


class CustomerDetailOut(BaseModel):
    customer: CustomerOut
    bookings: list[BookingOut]
    fetchedAt: str


class CustomersPageOut(BaseModel):
    items: list[CustomerOut]
    page: int
    pageSize: int
    total: int
    fetchedAt: str


async def _load(client: BooqableClient, *, refresh: bool) -> tuple[list[dict[str, Any]], datetime]:
    global _cache
    if not refresh and _cache is not None and time.monotonic() - _cache[0] < CACHE_TTL_SECONDS:
        return _cache[1], _cache[2]
    customers = await client.list_all("customers")
    fetched_at = datetime.now(UTC)
    _cache = (time.monotonic(), customers, fetched_at)
    return customers, fetched_at


def _to_out(resource: dict[str, Any]) -> CustomerOut:
    attrs = resource.get("attributes") or {}
    return CustomerOut(
        id=resource["id"],
        name=attrs.get("name"),
        email=attrs.get("email"),
        phone=_customer_phone(attrs),
        createdAt=attrs.get("created_at"),
        booqableUrl=f"{config.BOOQABLE_COMPANY_URL}/customers/{resource['id']}",
    )


async def _bookings_by_customer(
    client: BooqableClient, *, refresh: bool
) -> dict[str, list[Booking]] | None:
    """Bookings grouped by customer id, or None if Booqable's orders can't be read --
    the customer list is still useful without counts."""
    try:
        orders, included, _ = await load_orders(client, refresh=refresh)
    except Exception:  # noqa: BLE001
        logger.exception("Booking counts unavailable")
        return None
    grouped: dict[str, list[Booking]] = defaultdict(list)
    for booking in to_bookings(orders, included, now=datetime.now(UTC)):
        if booking.customer_id:
            grouped[booking.customer_id].append(booking)
    return grouped


def _matches(customer: CustomerOut, term: str) -> bool:
    return any(term in (value or "").lower() for value in (customer.name, customer.email, customer.phone))


@router.get("/api/customers", response_model=CustomersPageOut)
async def list_customers(
    q: str = "",
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    refresh: bool = False,
    _session=Depends(auth.require_auth),
) -> CustomersPageOut:
    try:
        client = BooqableClient()
        customers, fetched_at = await _load(client, refresh=refresh)
    except Exception as exc:  # noqa: BLE001 -- every upstream failure is a 502
        logger.exception("Customers load failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    rows = [_to_out(c) for c in customers]
    by_customer = await _bookings_by_customer(client, refresh=refresh)
    if by_customer is not None:
        for row in rows:
            mine = by_customer.get(row.id, [])
            row.bookingCount = len(mine)
            starts = [b.starts_at for b in mine if b.starts_at]
            row.lastBookingAt = max(starts).isoformat() if starts else None
    term = q.strip().lower()
    if term:
        rows = [r for r in rows if _matches(r, term)]
    rows.sort(key=lambda r: ((r.name or "").lower(), r.id))
    start = (page - 1) * pageSize
    return CustomersPageOut(
        items=rows[start : start + pageSize],
        page=page,
        pageSize=pageSize,
        total=len(rows),
        fetchedAt=fetched_at.isoformat(),
    )


@router.get("/api/customers/{customer_id}", response_model=CustomerDetailOut)
async def get_customer(
    customer_id: str,
    refresh: bool = False,
    _session=Depends(auth.require_auth),
) -> CustomerDetailOut:
    try:
        client = BooqableClient()
        customers, fetched_at = await _load(client, refresh=refresh)
        resource = next((c for c in customers if c["id"] == customer_id), None)
        if resource is None:
            raise HTTPException(status_code=404, detail="Customer not found")
        orders, included, _ = await load_orders(client, refresh=refresh)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 -- every upstream failure is a 502
        logger.exception("Customer load failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    mine = [b for b in to_bookings(orders, included, now=datetime.now(UTC)) if b.customer_id == customer_id]
    mine.sort(key=lambda b: b.starts_at or datetime.min.replace(tzinfo=UTC), reverse=True)
    out = _to_out(resource)
    out.bookingCount = len(mine)
    out.lastBookingAt = mine[0].starts_at.isoformat() if mine and mine[0].starts_at else None
    return CustomerDetailOut(
        customer=out,
        bookings=[_booking_out(b, None) for b in mine],
        fetchedAt=fetched_at.isoformat(),
    )
