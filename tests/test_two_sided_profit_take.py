"""#537: a profit-take needs a two-sided quote (bid > 0) at the tick that triggers it, in every book.

#535's no-arbitrage bound rejects a mark above what the option can be worth, but a zero-bid quote whose mid lands
between 10× entry and the bound still passes: a $0.30 call on a $50 stock quoted bid 0 / ask 10 marks 5.00. On main
the null books (shadow, 3A, 3B) booked that as a 10× profit-take at the mark, and the real book orphaned it (#527).
Now none of them acts on it that tick (counted ``pt_one_sided``, the row stays open, its mark is stored) and the next
tick re-evaluates it. Expiry and the time-stop are unchanged by a zero bid. Every quote here goes through the real
quote path (``AlpacaQuoteProvider`` over a fake chain), so bid 0 is the provider's own zero bid.
"""

from __future__ import annotations

from datetime import UTC, datetime

import fixed_basket
import shadow_book
import state
from clock import FixedClock
from convexity_data import AlpacaQuoteProvider, StaticQuoteProvider
from mark_bound import two_sided
from monitor import monitor_positions
from tests.test_fixed_basket import _insert_fb
from tests.test_mark_bound import _Chain
from tests.test_monitor import _FakeBroker, _row
from tests.test_shadow_book import _insert_shadow

NOW = datetime(2026, 6, 1, 15, 0, tzinfo=UTC)            # Mon 11:00 ET
CLOCK = FixedClock(NOW, market_open=True)
CFG = {"convexity_exits": {"profit_take_multiple": 10.0, "time_stop_dte": 21, "min_close_bid": 0.05}}
C = "FCX261218C00055000"                                  # a $55 call; spot $50 bounds its mark at 50
FAR, NEAR, TODAY = "2026-12-18", "2026-06-10", "2026-06-01"   # far expiry · 9 DTE (≤ 21: time-stop) · expires today
ENTRY_PC = 30.0                                           # $0.30/share → 10× = a 3.00 mark
SPOT = 50.0

ONE_SIDED = (0.0, 10.0)     # mid 5.00: ≥ 10× entry, under the $50 bound → passes #535
TWO_SIDED = (4.0, 6.0)      # mid 5.00 with a real bid
LOW_ONE_SIDED = (0.0, 0.2)  # mid 0.10: no profit-take trigger; a worthless far-OTM quote


def _qp(quote: tuple[float, float], contract: str = C, **legs) -> AlpacaQuoteProvider:
    return AlpacaQuoteProvider(_Chain({contract: quote, **legs}))


def _spot(_sym: str) -> float:
    return SPOT


# ── the real monitor ───────────────────────────────────────────────────────────────────────────────────────────────

def _open_real(conn, *, expiry=FAR, short=None):
    return state.record_convexity_position(
        conn, run_id=None, opened_at="2026-01-02T00:00:00+00:00", theme="t", symbol="FCX", direction="bullish",
        structure_kind="C", contract_symbol=C, expiry=expiry, strike=55.0, dte=200, moneyness=0.10, contracts=2,
        entry_premium_per_contract=ENTRY_PC, total_premium=2 * ENTRY_PC,
        short_contract_symbol=short, short_strike=(60.0 if short else None))


def _real_tick(conn, qp, *, broker=None, dry_run=False, mark_only=False, clock=CLOCK):
    return monitor_positions(conn=conn, clock=clock, quote_provider=qp, config=CFG, broker=broker,
                             dry_run=dry_run, mark_only=mark_only, underlying_price_of=_spot)


def test_real_zero_bid_10x_is_not_a_profit_take_no_orphan_no_sell(convexity_db):
    pid = _open_real(convexity_db)
    broker = _FakeBroker()
    res = _real_tick(convexity_db, _qp(ONE_SIDED), broker=broker)
    row = _row(convexity_db, pid, "status, mark, exit_reason, rationale")
    assert broker.sells == [], "a one-sided quote reached the broker"
    assert row["status"] == "open" and row["exit_reason"] is None and row["mark"] == 5.0
    assert "orphaned" not in (row["rationale"] or ""), "a zero-bid trigger was orphaned instead of not triggering"
    assert (res.pt_one_sided, res.profit_taken, res.orphaned, res.closed, res.marked) == (1, 0, 0, 0, 1)


def test_real_zero_bid_10x_is_not_booked_in_dry_run_either(convexity_db):
    pid = _open_real(convexity_db)
    res = _real_tick(convexity_db, _qp(ONE_SIDED), dry_run=True)
    assert _row(convexity_db, pid, "status")["status"] == "open"
    assert (res.pt_one_sided, res.profit_taken, res.closed) == (1, 0, 0)


def test_real_two_sided_10x_still_sells(convexity_db):
    pid = _open_real(convexity_db)
    broker = _FakeBroker()
    res = _real_tick(convexity_db, _qp(TWO_SIDED), broker=broker)
    assert [s["limit"] for s in broker.sells] == [4.0]
    assert res.profit_taken == 1 and res.pt_one_sided == 0 and res.closing == 1
    assert _row(convexity_db, pid, "status")["status"] == "closing"


def test_real_one_sided_trigger_is_re_evaluated_next_tick(convexity_db):
    pid = _open_real(convexity_db)
    _real_tick(convexity_db, _qp(ONE_SIDED), dry_run=True)
    res = _real_tick(convexity_db, _qp(TWO_SIDED), dry_run=True)
    assert res.profit_taken == 1 and res.closed == 1
    row = _row(convexity_db, pid, "status, exit_reason")
    assert row["status"] == "closed" and row["exit_reason"] == "profit_take_10x"


def test_real_time_stop_with_a_zero_bid_is_unchanged(convexity_db):
    # No profit-take trigger: the time-stop fires as before — in-DB in DRY_RUN, orphaned on a real submit (#444).
    dry = _open_real(convexity_db, expiry=NEAR)
    res = _real_tick(convexity_db, _qp(LOW_ONE_SIDED), dry_run=True)
    assert res.time_stopped == 1 and res.pt_one_sided == 0
    assert _row(convexity_db, dry, "exit_reason")["exit_reason"] == "time_stop_21dte"

    real = _open_real(convexity_db, expiry=NEAR)
    res = _real_tick(convexity_db, _qp(LOW_ONE_SIDED), broker=_FakeBroker())
    assert res.orphaned == 1 and res.pt_one_sided == 0
    assert "time_stop_21dte" in _row(convexity_db, real, "rationale")["rationale"]


def test_real_expiry_with_a_zero_bid_settles_at_intrinsic(convexity_db):
    pid = _open_real(convexity_db, expiry=TODAY)
    res = _real_tick(convexity_db, _qp(ONE_SIDED), broker=_FakeBroker())
    row = _row(convexity_db, pid, "status, exit_reason, mark")
    assert row["status"] == "closed" and row["exit_reason"] == "expiry" and row["mark"] == 0.0   # $50 < the $55 strike
    assert res.expired == 1 and res.pt_one_sided == 0


def test_real_vertical_needs_its_long_leg_bid(convexity_db):
    # A debit call vertical (+55/-60, width 5): spread mark = long mid − short mid = 5.0 − 0.1 = 4.9 ≥ 10× 0.30.
    short = "FCX261218C00060000"
    one = _open_real(convexity_db, short=short)
    res = _real_tick(convexity_db, _qp(ONE_SIDED, **{short: (0.05, 0.15)}), dry_run=True)
    assert res.pt_one_sided == 1 and res.profit_taken == 0
    assert _row(convexity_db, one, "status")["status"] == "open"
    # A long-leg bid makes it two-sided even when the SHORT leg has none.
    res = _real_tick(convexity_db, _qp(TWO_SIDED, **{short: (0.0, 0.2)}), dry_run=True)
    assert res.profit_taken == 1 and res.pt_one_sided == 0
    assert _row(convexity_db, one, "exit_reason")["exit_reason"] == "profit_take_10x"


# ── the shadow null book ───────────────────────────────────────────────────────────────────────────────────────────

def _shadow(conn, expiry=FAR):
    return _insert_shadow(conn, contract=C, entry_pc=ENTRY_PC, contracts=2, expiry=expiry, strike=55.0)


def _shadow_tick(conn, qp, **kw):
    return shadow_book.mark_shadow_positions(conn=conn, clock=CLOCK, quote_provider=qp, config=CFG,
                                             underlying_price_of=_spot, **kw)


def _shadow_row(conn, pid):
    return conn.execute("SELECT status, mark, exit_reason FROM shadow_positions WHERE id=?", (pid,)).fetchone()


def test_shadow_zero_bid_10x_stays_open(convexity_db):
    pid = _shadow(convexity_db)
    res = _shadow_tick(convexity_db, _qp(ONE_SIDED))
    row = _shadow_row(convexity_db, pid)
    assert row["status"] == "open", "the shadow book booked a phantom 10x win on a zero-bid quote"
    assert row["exit_reason"] is None and row["mark"] == 5.0
    assert (res.pt_one_sided, res.profit_taken, res.closed, res.marked) == (1, 0, 0, 1)


def test_shadow_two_sided_10x_profit_takes(convexity_db):
    pid = _shadow(convexity_db)
    res = _shadow_tick(convexity_db, _qp(TWO_SIDED))
    assert res.profit_taken == 1 and res.pt_one_sided == 0
    assert _shadow_row(convexity_db, pid)["exit_reason"] == "profit_take_10x"


def test_shadow_one_sided_trigger_is_re_evaluated_next_tick(convexity_db):
    pid = _shadow(convexity_db)
    _shadow_tick(convexity_db, _qp(ONE_SIDED))
    res = _shadow_tick(convexity_db, _qp(TWO_SIDED))
    assert res.profit_taken == 1 and _shadow_row(convexity_db, pid)["status"] == "closed"


def test_shadow_time_stop_and_expiry_with_a_zero_bid_are_unchanged(convexity_db):
    ts = _shadow(convexity_db, expiry=NEAR)
    ex = _shadow(convexity_db, expiry=TODAY)
    res = _shadow_tick(convexity_db, _qp(LOW_ONE_SIDED))
    assert _shadow_row(convexity_db, ts)["exit_reason"] == "time_stop_21dte"
    assert _shadow_row(convexity_db, ex)["exit_reason"] == "expiry"
    assert (res.time_stopped, res.expired, res.pt_one_sided) == (1, 1, 0)


def test_shadow_one_sided_trigger_inside_the_time_stop_window_books_nothing_this_tick(convexity_db):
    # The junk mark that cannot profit-take must not be booked as a time-stop either: the tick acts on nothing.
    pid = _shadow(convexity_db, expiry=NEAR)
    res = _shadow_tick(convexity_db, _qp(ONE_SIDED))
    assert _shadow_row(convexity_db, pid)["status"] == "open"
    assert (res.pt_one_sided, res.time_stopped, res.closed) == (1, 0, 0)


# ── the 3A / 3B no-gate null books ─────────────────────────────────────────────────────────────────────────────────

def _fb(conn, book, expiry=FAR):
    return _insert_fb(conn, symbol="FCX", total_premium=2 * ENTRY_PC, contract=C, expiry=expiry, strike=55.0,
                      contracts=2, book=book)


def _fb_tick(conn, qp):
    return fixed_basket.mark_fixed_basket_positions(conn=conn, clock=CLOCK, quote_provider=qp, config=CFG,
                                                    underlying_price_of=_spot)


def _fb_row(conn, pid):
    return conn.execute("SELECT status, mark, exit_reason FROM fixed_basket_positions WHERE id=?", (pid,)).fetchone()


BOOKS = (fixed_basket.BOOK_UNION_NOGATE, fixed_basket.BOOK_BASKET_NOGATE)


def test_3a_3b_zero_bid_10x_stays_open(convexity_db):
    pids = [_fb(convexity_db, b) for b in BOOKS]
    res = _fb_tick(convexity_db, _qp(ONE_SIDED))
    for pid in pids:
        row = _fb_row(convexity_db, pid)
        assert row["status"] == "open", "a no-gate book booked a phantom 10x win on a zero-bid quote"
        assert row["exit_reason"] is None and row["mark"] == 5.0
    assert (res.pt_one_sided, res.profit_taken, res.closed, res.marked) == (2, 0, 0, 2)


def test_3a_3b_two_sided_10x_profit_takes(convexity_db):
    pids = [_fb(convexity_db, b) for b in BOOKS]
    res = _fb_tick(convexity_db, _qp(TWO_SIDED))
    assert res.profit_taken == 2 and res.pt_one_sided == 0
    assert [_fb_row(convexity_db, p)["exit_reason"] for p in pids] == ["profit_take_10x"] * 2


def test_3a_3b_time_stop_and_expiry_with_a_zero_bid_are_unchanged(convexity_db):
    ts = [_fb(convexity_db, b, expiry=NEAR) for b in BOOKS]
    ex = [_fb(convexity_db, b, expiry=TODAY) for b in BOOKS]
    res = _fb_tick(convexity_db, _qp(LOW_ONE_SIDED))
    assert [_fb_row(convexity_db, p)["exit_reason"] for p in ts] == ["time_stop_21dte"] * 2
    assert [_fb_row(convexity_db, p)["exit_reason"] for p in ex] == ["expiry"] * 2
    assert (res.time_stopped, res.expired, res.pt_one_sided) == (2, 2, 0)


# ── the rule itself ────────────────────────────────────────────────────────────────────────────────────────────────

def _pos(short=None):
    return {"id": 7, "symbol": "FCX", "contract_symbol": C, "short_contract_symbol": short}


def test_two_sided_reads_the_single_leg_or_the_long_leg_bid():
    short = "FCX261218C00060000"
    assert two_sided(_pos(), StaticQuoteProvider({C: 5.0}, bids={C: 0.01}), book="t", mid=5.0)
    assert not two_sided(_pos(), StaticQuoteProvider({C: 5.0}, bids={C: 0.0}), book="t", mid=5.0)
    assert not two_sided(_pos(), StaticQuoteProvider({C: 5.0}, bids={}), book="t", mid=5.0)
    assert not two_sided(_pos(short), StaticQuoteProvider({}, bids={C: 0.0, short: 1.0}), book="t", mid=5.0)
    assert two_sided(_pos(short), StaticQuoteProvider({}, bids={C: 1.0, short: 0.0}), book="t", mid=5.0)


def test_a_failing_bid_read_is_not_two_sided():
    class _Boom(StaticQuoteProvider):
        def option_bid(self, contract_symbol):
            raise TimeoutError("quote endpoint down")

    assert not two_sided(_pos(), _Boom({C: 5.0}), book="t", mid=5.0)


def test_the_null_exits_stamp_carries_both_rules():
    assert shadow_book.NULL_EXITS_STAMP == "closed_tick_mark_only_v1+two_sided_pt_v1"
