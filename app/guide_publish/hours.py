"""BusinessHours[] -> a sentence a text-to-speech engine reads correctly.

Pure and I/O-free, in the same tradition as app/speech_timing.py: the
call-flow modules stay testable because the hard formatting decisions live
in functions that take data and return strings.

Every output here is SPOKEN. "9:00 AM - 5:30 PM" is wrong no matter how
readable it looks; "nine A M to five thirty P M" is what a caller needs to
hear. instructions.md states the same rule for the guide itself.
"""

from __future__ import annotations

_ONES = [
    "", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
]
_TENS = {2: "twenty", 3: "thirty", 4: "forty", 5: "fifty"}

_DAY_NAMES = [
    "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
]


def _number_words(value: int) -> str:
    if value < 20:
        return _ONES[value]
    tens, ones = divmod(value, 10)
    return _TENS[tens] + (f" {_ONES[ones]}" if ones else "")


def time_prose(hhmm: str) -> str:
    """"09:00" -> "nine A M". Spelled-out A M / P M with spaces is
    deliberate: TTS engines read "AM" as a word."""
    hour, minute = int(hhmm[:2]), int(hhmm[3:5])
    if minute == 0 and hour == 12:
        return "noon"
    if minute == 0 and hour == 0:
        return "midnight"
    suffix = "A M" if hour < 12 else "P M"
    words = _number_words(hour % 12 or 12)
    if minute:
        words += " " + (f"oh {_number_words(minute)}" if minute < 10 else _number_words(minute))
    return f"{words} {suffix}"


def _normalize(hours: list[dict]) -> list[dict]:
    by_day = {entry["day"]: entry for entry in hours}
    if set(by_day) != set(range(7)):
        raise ValueError("business hours must cover all seven days")
    ordered = [by_day[day] for day in range(7)]
    for entry in ordered:
        if not entry.get("closed") and not (entry.get("open") and entry.get("close")):
            raise ValueError(
                f"{_DAY_NAMES[entry['day']]} is open but has no open and close time"
            )
    return ordered


def _key(entry: dict) -> tuple:
    if entry.get("closed"):
        return ("closed",)
    return ("open", entry["open"], entry["close"])


def _day_phrase(start: int, end: int) -> str:
    if start == end:
        return _DAY_NAMES[start]
    if end < start:  # wrap-around (e.g., Saturday 6 to Sunday 0)
        if start == 6 and end == 0:
            return f"{_DAY_NAMES[start]} and {_DAY_NAMES[end]}"
        # For other wrap-arounds like Wednesday (3) to Sunday (0)
        return f"{_DAY_NAMES[start]} through {_DAY_NAMES[end]}"
    if end - start == 1:
        return f"{_DAY_NAMES[start]} and {_DAY_NAMES[end]}"
    return f"{_DAY_NAMES[start]} through {_DAY_NAMES[end]}"


def hours_prose(hours: list[dict]) -> str:
    """Consecutive days sharing the same hours are collapsed into one
    phrase, so a caller hears "Monday through Friday" rather than five
    near-identical sentences."""
    ordered = _normalize(hours)

    if all(not entry.get("closed") for entry in ordered) and len({_key(e) for e in ordered}) == 1:
        first = ordered[0]
        return f"every day, {time_prose(first['open'])} to {time_prose(first['close'])}"
    if all(entry.get("closed") for entry in ordered):
        return "closed every day"

    runs: list[tuple[int, int, dict]] = []
    for index, entry in enumerate(ordered):
        if runs and _key(entry) == _key(runs[-1][2]) and index == runs[-1][1] + 1:
            runs[-1] = (runs[-1][0], index, runs[-1][2])
        else:
            runs.append((index, index, entry))

    # Handle Sunday (0) and Saturday (6) wrap-around: merge them if they have the same status
    if len(runs) > 1 and runs[0][0] == 0 and runs[-1][1] == 6 and _key(runs[0][2]) == _key(runs[-1][2]):
        # Pop Sunday run and Saturday run, then merge them
        first_run = runs.pop(0)
        last_run = runs.pop()
        # Merge: start from Saturday, end at Sunday (creating a wrap-around)
        merged_run = (last_run[0], first_run[1], last_run[2])
        runs.append(merged_run)

    segments = []
    for start, end, entry in runs:
        days = _day_phrase(start, end)
        if entry.get("closed"):
            segments.append(f"Closed {days}")
        else:
            segments.append(
                f"{days}, {time_prose(entry['open'])} to {time_prose(entry['close'])}"
            )
    return ". ".join(segments)
