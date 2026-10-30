"""Pure, read-only NYSE session calendar (full-day holidays + 13:00 ET early closes).

Display logic only: the dashboard's STALE heartbeats use it to know when a session was never going to run
(holiday) or ends early (half day). It touches NO order path, orchestrator gate or kill rule, and makes no
network calls — the table below is hard-coded from the NYSE's published holiday schedule.

Coverage is 2026–2027. Outside the table the calendar is *unknown*, so ``is_trading_day`` degrades to the old
weekday-only rule (``covers`` says whether a date is inside the table); a test pins that the table is not
silently exhausted near the present — extend ``_HOLIDAYS`` / ``_EARLY_CLOSES`` before 2027 ends.
"""

from __future__ import annotations

from datetime import date, time

REGULAR_CLOSE = time(16, 0)  # ET
EARLY_CLOSE = time(13, 0)    # ET

COVERED_YEARS = (2026, 2027)

# Full-day closures (weekday dates only — NYSE observes a weekend holiday on the nearest weekday).
_HOLIDAYS: dict[date, str] = {
    # 2026
    date(2026, 1, 1): "New Year's Day",
    date(2026, 1, 19): "Martin Luther King Jr. Day",
    date(2026, 2, 16): "Washington's Birthday",
    date(2026, 4, 3): "Good Friday",
    date(2026, 5, 25): "Memorial Day",
    date(2026, 6, 19): "Juneteenth",
    date(2026, 7, 3): "Independence Day (observed)",
    date(2026, 9, 7): "Labor Day",
    date(2026, 11, 26): "Thanksgiving Day",
    date(2026, 12, 25): "Christmas Day",
    # 2027
    date(2027, 1, 1): "New Year's Day",
    date(2027, 1, 18): "Martin Luther King Jr. Day",
    date(2027, 2, 15): "Washington's Birthday",
    date(2027, 3, 26): "Good Friday",
    date(2027, 5, 31): "Memorial Day",
    date(2027, 6, 18): "Juneteenth (observed)",
    date(2027, 7, 5): "Independence Day (observed)",
    date(2027, 9, 6): "Labor Day",
    date(2027, 11, 25): "Thanksgiving Day",
    date(2027, 12, 24): "Christmas Day (observed)",
}

# Early (13:00 ET) closes.
_EARLY_CLOSES: dict[date, time] = {
    date(2026, 11, 27): EARLY_CLOSE,  # day after Thanksgiving
    date(2026, 12, 24): EARLY_CLOSE,  # Christmas Eve
    date(2027, 11, 26): EARLY_CLOSE,  # day after Thanksgiving
}


def covers(d: date) -> bool:
    """True iff ``d`` falls in a year the table knows."""
    return d.year in COVERED_YEARS


def holiday_name(d: date) -> str | None:
    """The NYSE holiday on ``d`` (weekday full-day closure), else None."""
    return _HOLIDAYS.get(d)


def is_trading_day(d: date) -> bool:
    """Weekday and not an NYSE holiday. Outside the covered years only the weekend rule applies."""
    return d.weekday() < 5 and d not in _HOLIDAYS


def is_early_close(d: date) -> bool:
    return is_trading_day(d) and d in _EARLY_CLOSES


def session_close(d: date) -> time | None:
    """Regular-session close (ET) for ``d``: 16:00, 13:00 on an early close, None when the market is shut."""
    if not is_trading_day(d):
        return None
    return _EARLY_CLOSES.get(d, REGULAR_CLOSE)
