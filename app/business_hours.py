"""Business-hours guard for reservations, in the business's local time.

Hours come from the last successfully published business profile (what the
live guide was told), falling back to config.DEFAULT_BUSINESS_PROFILE. Day
indexes follow app/guide_publish/hours.py: 0 = Sunday ... 6 = Saturday.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from . import config

logger = logging.getLogger("voice_receptionist")

# A booking may start this many minutes in the past (the caller says "now").
PAST_TOLERANCE_MINUTES = 15
_CACHE: dict[str, Any] = {"at": 0.0, "hours": None}
_CACHE_SECONDS = 60.0


def _tz() -> ZoneInfo:
    return ZoneInfo(config.BOOQABLE_TIMEZONE)


def _published_hours() -> list[dict] | None:
    try:
        from . import db as db_module
        from .guide_publish import publisher

        session = db_module.SessionLocal()
        try:
            pub = publisher.latest_succeeded(session)
            if pub:
                return ((pub.published_config or {}).get("business_profile") or {}).get("hours")
        finally:
            session.close()
    except Exception:  # noqa: BLE001 -- fall back to defaults
        logger.info("Business hours: using defaults (published profile unavailable)")
    return None


_NAME_CACHE: dict[str, Any] = {"at": 0.0, "name": None}


def _published_name() -> str | None:
    try:
        from . import db as db_module
        from .guide_publish import publisher

        session = db_module.SessionLocal()
        try:
            pub = publisher.latest_succeeded(session)
            if pub:
                return ((pub.published_config or {}).get("business_profile") or {}).get("name")
        finally:
            session.close()
    except Exception:  # noqa: BLE001 -- fall back to defaults
        logger.info("Business name: using default (published profile unavailable)")
    return None


def business_name() -> str:
    """Written business name from the last published profile (cached 60 s)."""
    now = time.monotonic()
    if _NAME_CACHE["name"] is None or now - _NAME_CACHE["at"] > _CACHE_SECONDS:
        _NAME_CACHE["name"] = (_published_name() or config.DEFAULT_BUSINESS_PROFILE.get("name") or "").strip()
        _NAME_CACHE["at"] = now
    return _NAME_CACHE["name"]


def current_hours() -> list[dict]:
    now = time.monotonic()
    if _CACHE["hours"] is None or now - _CACHE["at"] > _CACHE_SECONDS:
        _CACHE["hours"] = _published_hours() or config.DEFAULT_BUSINESS_PROFILE["hours"]
        _CACHE["at"] = now
    return _CACHE["hours"]


def _sunday_index(dt: datetime) -> int:
    return (dt.weekday() + 1) % 7  # Python Monday=0 -> Sunday=0


def _hm(value: str) -> tuple[int, int]:
    h, m = value.split(":")[:2]
    return int(h), int(m)


def day_window(day: datetime, hours: list[dict]) -> tuple[datetime, datetime] | None:
    """(open, close) local datetimes for `day`'s date, or None when closed."""
    entry = {e["day"]: e for e in hours}.get(_sunday_index(day))
    if not entry or entry.get("closed") or not entry.get("open") or not entry.get("close"):
        return None
    oh, om = _hm(entry["open"])
    ch, cm = _hm(entry["close"])
    base = day.replace(hour=0, minute=0, second=0, microsecond=0)
    return base.replace(hour=oh, minute=om), base.replace(hour=ch, minute=cm)


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _spoken_time(dt: datetime) -> str:
    hour = dt.hour % 12 or 12
    suffix = "AM" if dt.hour < 12 else "PM"
    return f"{hour} {suffix}" if dt.minute == 0 else f"{hour}:{dt.minute:02d} {suffix}"


def _spoken_date(dt: datetime) -> str:
    return f"{dt:%A}, {dt:%B} {_ordinal(dt.day)}"


def now_local(now: datetime | None = None) -> datetime:
    return (now or datetime.now(_tz())).astimezone(_tz())


def next_open(now: datetime | None = None, hours: list[dict] | None = None) -> datetime | None:
    """The next opening time at or after `now` (today's opening if not yet open)."""
    hours = hours or current_hours()
    now = now_local(now)
    for offset in range(8):
        day = now + timedelta(days=offset)
        window = day_window(day, hours)
        if window is None:
            continue
        opens, closes = window
        if offset == 0:
            if now < opens:
                return opens
            continue  # today: already open or closed -> next day
        return opens
    return None


def _parse(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_tz())
    return dt.astimezone(_tz())


def _next_open_fields(now: datetime, hours: list[dict]) -> dict[str, Any]:
    nxt = next_open(now, hours)
    if not nxt:
        return {}
    return {
        "next_open_local": nxt.isoformat(),
        "next_open_spoken": f"{_spoken_date(nxt)} at {_spoken_time(nxt)}",
    }


def check_window(
    starts_at: str,
    stops_at: str | None = None,
    *,
    now: datetime | None = None,
    hours: list[dict] | None = None,
    for_booking: bool = True,
) -> dict[str, Any] | None:
    """None if the window is within business hours, else a dict with
    `reason` (past / closed_day / before_open / after_close / stop_after_close)
    plus the next opening time. For a dated catalog/availability check
    (`for_booking=False`) a start earlier today is fine as long as the shop is
    still open now -- the guide often checks the whole day before it knows
    the caller's time."""
    hours = hours or current_hours()
    now = now_local(now)
    start = _parse(starts_at)
    stop = _parse(stops_at) if stops_at else None
    reason = None
    window = day_window(start, hours)
    if window is None:
        reason = "closed_day"
    else:
        opens, closes = window
        if for_booking:
            if start < now - timedelta(minutes=PAST_TOLERANCE_MINUTES):
                reason = "past"
            elif start < opens:
                reason = "before_open"
            elif start >= closes:
                reason = "after_close"
        else:
            if start.date() < now.date() or (start.date() == now.date() and now >= closes):
                reason = "past" if start.date() < now.date() else "after_close"
            elif start >= closes:
                reason = "after_close"
            elif stop is not None and stop <= opens:
                reason = "before_open"
        if reason is None and stop is not None:
            stop_window = day_window(stop, hours)
            if stop_window is None or stop > stop_window[1] or stop < stop_window[0]:
                reason = "stop_after_close"
    if reason is None:
        return None
    out: dict[str, Any] = {"reason": reason, "now_local": now.isoformat()}
    if window is not None:
        out["hours_that_day"] = f"{_spoken_time(window[0])} to {_spoken_time(window[1])}"
    out.update(_next_open_fields(now, hours))
    return out


def now_note(now: datetime | None = None, hours: list[dict] | None = None) -> str:
    """One-line note giving the guide today's date/time and whether the shop
    is open, closed for today, or not yet open."""
    hours = hours or current_hours()
    now = now_local(now)
    window = day_window(now, hours)
    text = f"[Note: it is now {_spoken_date(now)}, {_spoken_time(now)} local time."
    if window is None:
        state = "The shop is closed today."
    elif now < window[0]:
        state = f"The shop opens today at {_spoken_time(window[0])}."
    elif now >= window[1]:
        state = f"The shop is closed for today (it closed at {_spoken_time(window[1])})."
    else:
        state = f"The shop is open today until {_spoken_time(window[1])}."
    nxt = next_open(now, hours)
    tail = f" Next opening: {_spoken_date(nxt)} at {_spoken_time(nxt)}." if nxt and (window is None or now >= window[1] or now < window[0]) else ""
    return f"{text} {state}{tail}]"


_REASON_TEXT = {
    "past": "that time has already passed",
    "closed_day": "the shop is closed that day",
    "before_open": "that is before opening time",
    "after_close": "that is at or after closing time",
    "stop_after_close": "the rental would end outside business hours",
}


def not_booked_message(problem: dict[str, Any]) -> str:
    hours = f" (open {problem['hours_that_day']} that day)" if problem.get("hours_that_day") else ""
    nxt = f" Next open: {problem['next_open_spoken']}." if problem.get("next_open_spoken") else ""
    return (
        f"NOT BOOKED: outside business hours -- {_REASON_TEXT.get(problem['reason'], problem['reason'])}"
        f"{hours}.{nxt} No reservation was made. Tell the caller and offer a time within business "
        "hours, such as the next open time."
    )


def closed_result(problem: dict[str, Any]) -> dict[str, Any]:
    """Dated catalog/availability answer for a window outside business hours:
    no items at all, so nothing can be offered for it."""
    reason = _REASON_TEXT.get(problem["reason"], problem["reason"])
    nxt = problem.get("next_open_spoken")
    return {
        "closed": True,
        "products": [],
        "unavailable": [],
        "accessories": [],
        "status": "closed",
        "reason": problem["reason"],
        **{k: v for k, v in problem.items() if k != "reason"},
        "note": (
            f"Closed: {reason}. Nothing can be rented for that time -- do not offer any item. "
            + (f"Tell the caller and offer the next open time: {nxt}." if nxt else "Tell the caller.")
        ),
    }
