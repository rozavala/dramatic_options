"""#480: the monitor and the null books decide expiry and DTE on the ET trading date, not the UTC date.

``LiveClock.now()`` is UTC. After 19:00 ET (20:00 ET under EDT) its date is already tomorrow, so on ``main`` an
evening pass (a ``Persistent=true`` catch-up after downtime, a manual ``--monitor`` run, the #466 drill) on the
evening before expiry booked ``expiry`` at intrinsic, from that evening's price, with a full session still to trade.
Each test drives the real exit function with a FixedClock at 01:00 UTC on the expiry date (20:00 ET the evening
before)."""

from datetime import UTC, date, datetime

import fixed_basket
import shadow_book
from clock import FixedClock, et_date
from convexity_data import StaticQuoteProvider
from monitor import monitor_positions
from tests.test_fixed_basket import CONFIG as FB_CONFIG
from tests.test_fixed_basket import _insert_fb
from tests.test_monitor import CONFIG, _FakeBroker, _open, _row
from tests.test_shadow_book import CONFIG as SB_CONFIG
from tests.test_shadow_book import _insert_shadow

EXPIRY = "2026-12-18"                                                         # a Friday (EST, UTC-5)
EVENING_BEFORE = FixedClock(datetime(2026, 12, 18, 1, 0, tzinfo=UTC))        # Thu 12-17 20:00 ET
EXPIRY_CLOSE = FixedClock(datetime(2026, 12, 18, 21, 30, tzinfo=UTC))        # Fri 12-18 16:30 ET
CONTRACT = "FCX261218C00080000"


def test_et_date_is_the_new_york_calendar_date():
    assert et_date(datetime(2026, 12, 18, 1, 0, tzinfo=UTC)) == date(2026, 12, 17)      # EST: UTC-5
    assert et_date(datetime(2026, 12, 18, 4, 59, tzinfo=UTC)) == date(2026, 12, 17)
    assert et_date(datetime(2026, 12, 18, 5, 0, tzinfo=UTC)) == date(2026, 12, 18)
    assert et_date(datetime(2026, 7, 1, 3, 59, tzinfo=UTC)) == date(2026, 6, 30)        # EDT: UTC-4
    assert et_date(datetime(2026, 7, 1, 4, 0, tzinfo=UTC)) == date(2026, 7, 1)
    assert et_date(datetime(2026, 12, 18, 1, 0)) == date(2026, 12, 17)                  # naive = UTC


def test_real_book_evening_pass_does_not_book_tomorrows_expiry(convexity_db):
    pid = _open(convexity_db, contract=CONTRACT, entry_pc=200.0, expiry=EXPIRY)
    qp = StaticQuoteProvider({CONTRACT: 2.0}, bids={CONTRACT: 1.9})
    res = monitor_positions(conn=convexity_db, clock=EVENING_BEFORE, quote_provider=qp, config=CONFIG,
                            broker=_FakeBroker(), dry_run=False, mark_only=True,
                            underlying_price_of=lambda s: 100.0)
    row = _row(convexity_db, pid, "status, exit_reason")
    assert res.expired == 0, "an evening pass booked expiry a session early (UTC date)"
    assert row["status"] == "open" and row["exit_reason"] is None
    assert res.deferred == 1          # DTE 1 ≤ 21: the time-stop triggers and, closed market, waits for the open


def test_real_book_books_expiry_on_the_expiry_date(convexity_db):
    pid = _open(convexity_db, contract=CONTRACT, entry_pc=200.0, expiry=EXPIRY)
    res = monitor_positions(conn=convexity_db, clock=EXPIRY_CLOSE, quote_provider=StaticQuoteProvider({}),
                            config=CONFIG, broker=_FakeBroker(), dry_run=False, mark_only=True,
                            underlying_price_of=lambda s: 100.0)
    assert res.expired == 1
    assert _row(convexity_db, pid, "status, exit_reason")["exit_reason"] == "expiry"


def test_shadow_book_evening_pass_does_not_book_tomorrows_expiry(convexity_db):
    pid = _insert_shadow(convexity_db, contract=CONTRACT, expiry=EXPIRY)
    res = shadow_book.mark_shadow_positions(conn=convexity_db, clock=EVENING_BEFORE,
                                            quote_provider=StaticQuoteProvider({CONTRACT: 2.0}), config=SB_CONFIG,
                                            underlying_price_of=lambda s: 100.0)
    assert res.expired == 0, "the shadow book booked expiry a session early (UTC date)"
    assert res.time_stopped == 1      # DTE 1, the same rule the real book applies in session
    reason = convexity_db.execute("SELECT exit_reason FROM shadow_positions WHERE id=?", (pid,)).fetchone()[0]
    assert reason.startswith("time_stop")


def test_fixed_basket_evening_pass_does_not_book_tomorrows_expiry(convexity_db):
    _insert_fb(convexity_db, symbol="FCX", contract=CONTRACT, total_premium=200.0, expiry=EXPIRY)
    res = fixed_basket.mark_fixed_basket_positions(conn=convexity_db, clock=EVENING_BEFORE,
                                                   quote_provider=StaticQuoteProvider({CONTRACT: 2.0}),
                                                   config=FB_CONFIG, underlying_price_of=lambda s: 100.0)
    assert res.expired == 0, "a fixed-basket book booked expiry a session early (UTC date)"
    assert res.time_stopped == 1
