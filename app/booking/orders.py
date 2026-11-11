"""Classify Booqable orders into console bookings and compute the page summary.

Pure logic plus read-only (GET) Booqable loading; called only by
app/console/bookings/api.py.
"""

import asyncio
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from datetime import time as day_time
from typing import Any, Literal
from zoneinfo import ZoneInfo

import httpx

from app import config
from app.booking.booqable_client import BooqableClient, BooqableError
from app.booking.reservations import _customer_phone, _order_line_items

View = Literal["upcoming", "past"]
Label = Literal["out_now", "overdue", "not_picked_up", "returned", "canceled"]
PaymentLabel = Literal["paid", "unpaid", "partly_paid"]

HIDDEN_STATUSES = frozenset({"draft", "new", "archived"})


@dataclass(frozen=True)
class Booking:
    id: str
    number: int | None
    view: View
    label: Label | None
    starts_at: datetime | None
    stops_at: datetime | None
    customer_name: str | None
    customer_phone: str | None
    customer_email: str | None
    total_cents: int
    payment: PaymentLabel
    item_count: int | None
    customer_id: str | None = None


@dataclass(frozen=True)
class BookingSummary:
    pickups_today: int
    returns_today: int
    next_7_days: int
    unpaid: int


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def classify(
    status: str | None, stops_at: datetime | None, now: datetime
) -> tuple[View, Label | None] | None:
    if status in HIDDEN_STATUSES:
        return None
    if status == "canceled":
        return ("past", "canceled")
    if status == "stopped":
        return ("past", "returned")
    if status == "started":
        if stops_at is not None and stops_at <= now:
            return ("upcoming", "overdue")
        return ("upcoming", "out_now")
    still_ahead = stops_at is not None and stops_at > now
    if status == "reserved":
        return ("upcoming", None) if still_ahead else ("past", "not_picked_up")
    return ("upcoming", None) if still_ahead else ("past", None)


def payment_label(payment_status: str | None) -> PaymentLabel:
    if payment_status in ("paid", "overpaid"):
        return "paid"
    if payment_status and "partial" in payment_status:
        return "partly_paid"
    return "unpaid"


def to_bookings(orders: list[dict[str, Any]], included: list[dict[str, Any]], now: datetime) -> list[Booking]:
    customers = {item["id"]: item for item in included if item.get("type") == "customers"}
    bookings: list[Booking] = []
    for order in orders:
        attrs = order.get("attributes") or {}
        starts_at = parse_timestamp(attrs.get("starts_at"))
        stops_at = parse_timestamp(attrs.get("stops_at"))
        classified = classify(attrs.get("status"), stops_at, now)
        if classified is None:
            continue
        view, label = classified
        customer_attrs = (customers.get(attrs.get("customer_id")) or {}).get("attributes") or {}
        bookings.append(
            Booking(
                id=order["id"],
                number=attrs.get("number"),
                view=view,
                label=label,
                starts_at=starts_at,
                stops_at=stops_at,
                customer_name=customer_attrs.get("name"),
                customer_phone=_customer_phone(customer_attrs),
                customer_email=customer_attrs.get("email"),
                total_cents=attrs.get("grand_total_in_cents") or 0,
                payment=payment_label(attrs.get("payment_status")),
                item_count=attrs.get("item_count"),
                customer_id=attrs.get("customer_id"),
            )
        )
    return bookings


def sort_for_view(bookings: list[Booking], view: View) -> list[Booking]:
    chosen = [b for b in bookings if b.view == view]
    dated = [b for b in chosen if b.starts_at is not None]
    undated = [b for b in chosen if b.starts_at is None]
    dated.sort(key=lambda b: b.starts_at, reverse=(view == "past"))
    return dated + undated


def summarize(bookings: list[Booking], now: datetime, tz: ZoneInfo) -> BookingSummary:
    today = now.astimezone(tz).date()
    window_start = datetime.combine(today, day_time.min, tzinfo=tz)
    window_end = datetime.combine(today + timedelta(days=7), day_time.min, tzinfo=tz)
    upcoming = [b for b in bookings if b.view == "upcoming"]
    return BookingSummary(
        pickups_today=sum(1 for b in upcoming if b.starts_at and b.starts_at.astimezone(tz).date() == today),
        returns_today=sum(1 for b in upcoming if b.stops_at and b.stops_at.astimezone(tz).date() == today),
        next_7_days=sum(1 for b in upcoming if b.starts_at and window_start <= b.starts_at < window_end),
        unpaid=sum(1 for b in upcoming if b.payment != "paid"),
    )


# --- loading (read-only GETs against Booqable) ---

CACHE_TTL_SECONDS = 30
LINE_FETCH_CONCURRENCY = 5

_cache: tuple[float, list[dict[str, Any]], list[dict[str, Any]], datetime] | None = None


def clear_cache() -> None:
    global _cache
    _cache = None


async def load_orders(
    client: BooqableClient, *, refresh: bool = False
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], datetime]:
    """(orders, included, fetched_at). Cached for CACHE_TTL_SECONDS; fetched_at is
    when Booqable was actually queried, not when this request arrived."""
    global _cache
    if not refresh and _cache is not None and time.monotonic() - _cache[0] < CACHE_TTL_SECONDS:
        return _cache[1], _cache[2], _cache[3]
    data, included = await client.list_all_with_included("orders", params={"include": "customer"})
    fetched_at = datetime.now(UTC)
    _cache = (time.monotonic(), data, included, fetched_at)
    return data, included, fetched_at


async def fetch_line_items(
    client: BooqableClient, order_ids: list[str]
) -> dict[str, list[dict[str, Any]] | None]:
    """Booked-product lines per order id; an id whose fetch fails maps to None."""
    semaphore = asyncio.Semaphore(LINE_FETCH_CONCURRENCY)

    async def one(order_id: str) -> tuple[str, list[dict[str, Any]] | None]:
        async with semaphore:
            try:
                payload = await client.get(f"orders/{order_id}", params={"include": "lines"})
            except (BooqableError, httpx.HTTPError):
                return order_id, None
        return order_id, _order_line_items(client, payload.get("included") or [])

    return dict(await asyncio.gather(*(one(i) for i in order_ids)))


def booqable_url(order_id: str) -> str:
    return f"{config.BOOQABLE_COMPANY_URL}/orders/{order_id}"
