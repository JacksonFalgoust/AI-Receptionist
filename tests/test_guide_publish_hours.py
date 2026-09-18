"""Spoken-prose rendering of business hours. Every string here is read
aloud by Twilio's TTS, so the assertions are about what a caller hears --
never about a display format."""

import pytest

from app.guide_publish.hours import hours_prose, time_prose


def _day(day, open_=None, close=None, closed=False):
    return {"day": day, "open": open_, "close": close, "closed": closed}


@pytest.mark.parametrize(
    "hhmm,expected",
    [
        ("09:00", "nine A M"),
        ("18:00", "six P M"),
        ("08:30", "eight thirty A M"),
        ("17:30", "five thirty P M"),
        ("16:00", "four P M"),
        ("12:00", "noon"),
        ("00:00", "midnight"),
        ("09:05", "nine oh five A M"),
        ("23:45", "eleven forty five P M"),
    ],
)
def test_time_prose(hhmm, expected):
    assert time_prose(hhmm) == expected


def test_all_seven_days_identical_collapses_to_every_day():
    """This exact string appears in today's authored instructions.md --
    the golden test in Task 5 depends on it byte-for-byte."""
    hours = [_day(d, "09:00", "18:00") for d in range(7)]
    assert hours_prose(hours) == "every day, nine A M to six P M"


def test_weekday_run_and_closed_weekend():
    hours = [
        _day(0, closed=True),
        *[_day(d, "08:30", "17:30") for d in range(1, 5)],
        _day(5, "08:30", "16:00"),
        _day(6, closed=True),
    ]
    assert hours_prose(hours) == (
        "Monday through Thursday, eight thirty A M to five thirty P M. "
        "Friday, eight thirty A M to four P M. "
        "Closed Saturday and Sunday"
    )


def test_two_day_run_uses_and_not_through():
    hours = [_day(d, closed=True) for d in range(7)]
    hours[1] = _day(1, "09:00", "17:00")
    hours[2] = _day(2, "09:00", "17:00")
    assert hours_prose(hours) == (
        "Monday and Tuesday, nine A M to five P M. "
        "Closed Wednesday through Sunday"
    )


def test_closed_every_day():
    assert hours_prose([_day(d, closed=True) for d in range(7)]) == "closed every day"


def test_rejects_incomplete_week():
    with pytest.raises(ValueError, match="seven days"):
        hours_prose([_day(0, "09:00", "18:00")])


def test_rejects_open_day_missing_times():
    with pytest.raises(ValueError, match="open and close"):
        hours_prose([_day(d, "09:00", "18:00") for d in range(6)] + [_day(6)])
