"""nyse_calendar — the pure NYSE holiday / early-close table (#367). Read-only display logic."""

from __future__ import annotations

from datetime import date, time, timedelta

import pytest

import nyse_calendar as cal


@pytest.mark.parametrize("d, trading, close", [
    (date(2026, 11, 26), False, None),             # Thanksgiving
    (date(2026, 11, 27), True, time(13, 0)),       # day after: early close
    (date(2026, 12, 24), True, time(13, 0)),       # Christmas Eve: early close
    (date(2026, 12, 25), False, None),             # Christmas
    (date(2026, 10, 27), True, time(16, 0)),       # normal day
    (date(2026, 10, 24), False, None),             # Saturday
    (date(2026, 7, 3), False, None),               # July 4 observed (Sat → Fri)
    (date(2027, 11, 25), False, None),             # 2027 Thanksgiving
    (date(2027, 11, 26), True, time(13, 0)),       # 2027 day after
    (date(2027, 12, 24), False, None),             # Christmas observed (Sat → Fri)
    (date(2027, 12, 31), True, time(16, 0)),       # NYSE stays open when Jan 1 falls on Saturday
])
def test_session_close(d, trading, close):
    assert cal.is_trading_day(d) is trading
    assert cal.session_close(d) == close


def test_early_close_and_holiday_name():
    assert cal.is_early_close(date(2026, 11, 27)) and not cal.is_early_close(date(2026, 11, 26))
    assert cal.holiday_name(date(2026, 11, 26)) == "Thanksgiving Day"
    assert cal.holiday_name(date(2026, 10, 27)) is None


def test_table_is_sane():
    assert all(d.weekday() < 5 for d in cal._HOLIDAYS)  # weekend holidays are stored on the observed weekday
    assert all(d.weekday() < 5 for d in cal._EARLY_CLOSES)
    assert not set(cal._HOLIDAYS) & set(cal._EARLY_CLOSES)
    assert {d.year for d in cal._HOLIDAYS} == set(cal.COVERED_YEARS)
    for y in cal.COVERED_YEARS:  # NYSE has 10 full-day closures a year (the 2027 count includes the observed Dec 24)
        assert sum(1 for d in cal._HOLIDAYS if d.year == y) == 10


def test_unknown_years_degrade_to_weekday_rule():
    assert not cal.covers(date(2028, 1, 3)) and cal.covers(date(2027, 6, 1))
    assert cal.is_trading_day(date(2028, 11, 23))   # weekday, table silent
    assert not cal.is_trading_day(date(2028, 11, 25))  # Saturday


def test_table_not_exhausted_soon():
    # Fails when the calendar's last covered year is less than ~2 months away, forcing an extension in time.
    assert date.today() + timedelta(days=60) <= date(max(cal.COVERED_YEARS), 12, 31)
