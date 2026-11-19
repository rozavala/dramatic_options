"""#537: a profit-take needs a sellable bid (≥ ``convexity_exits.min_close_bid``) at the tick that triggers it, in every
book.

#535's no-arbitrage bound rejects a mark above what the option can be worth, but a junk quote whose mid lands between
10× entry and the bound still passes: a $0.30 call on a $50 stock quoted bid 0 / ask 10 marks 5.00, and bid 0.01 /
ask 10 marks 5.005. On main the null books (shadow, 3A, 3B) booked that as a 10× profit-take at the mark, and the real
book orphaned it (#527). Now none of them acts on it that tick (counted ``pt_unsellable_bid``, the row stays open, its
mark is stored) and the next tick re-evaluates it. The floor is the real book's own sell floor (0.05), so the null
books never book a profit-take the real book could not sell. Expiry and the time-stop (with its #444 orphan) are
unchanged. Every quote goes through the real quote path (``AlpacaQuoteProvider`` over a fake chain).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

import fixed_basket
import shadow_book
import state
from clock import FixedClock
from convexity_data import AlpacaQuoteProvider, StaticQuoteProvider
from mark_bound import min_close_bid_of, sellable_bid
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

ZERO_BID = (0.0, 10.0)      # mid 5.00: ≥ 10× entry, under the $50 bound → passes #535
PENNY_BID = (0.01, 10.0)    # mid 5.005: a bid, but under min_close_bid (review N4)
FLOOR_BID = (0.05, 9.95)    # mid 5.00: the bid exactly at min_close_bid → sellable (boundary)
SELLABLE = (4.0, 6.0)       # mid 5.00 with a real bid
LOW_ZERO_BID = (0.0, 0.2)   # mid 0.10: no profit-take trigger; a worthless far-OTM quote
UNSELLABLE = pytest.mark.parametrize("quote", [ZERO_BID, PENNY_BID], ids=["zero-bid", "penny-bid"])


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


def _real_tick(conn, qp, *, broker=None, dry_run=False, mark_only=False, clock=CLOCK, config=CFG):
    return monitor_positions(conn=conn, clock=clock, quote_provider=qp, config=config, broker=broker,
                             dry_run=dry_run, mark_only=mark_only, underlying_price_of=_spot)


@UNSELLABLE
def test_real_unsellable_10x_is_not_a_profit_take_no_orphan_no_sell(convexity_db, quote):
    pid = _open_real(convexity_db)
    broker = _FakeBroker()
    res = _real_tick(convexity_db, _qp(quote), broker=broker)
    row = _row(convexity_db, pid, "status, mark, exit_reason, rationale")
    assert broker.sells == [], "an unsellable quote reached the broker"
    assert row["status"] == "open" and row["exit_reason"] is None and row["mark"] == pytest.approx(sum(quote) / 2)
    assert "orphaned" not in (row["rationale"] or ""), "an unsellable trigger was orphaned instead of not triggering"
    assert (res.pt_unsellable_bid, res.profit_taken, res.orphaned, res.closed, res.marked) == (1, 0, 0, 0, 1)


@UNSELLABLE
def test_real_unsellable_10x_is_not_booked_in_dry_run_either(convexity_db, quote):
    pid = _open_real(convexity_db)
    res = _real_tick(convexity_db, _qp(quote), dry_run=True)
    assert _row(convexity_db, pid, "status")["status"] == "open"
    assert (res.pt_unsellable_bid, res.profit_taken, res.closed) == (1, 0, 0)


@pytest.mark.parametrize("quote", [SELLABLE, FLOOR_BID], ids=["sellable", "bid-at-floor"])
def test_real_sellable_10x_still_sells(convexity_db, quote):
    pid = _open_real(convexity_db)
    broker = _FakeBroker()
    res = _real_tick(convexity_db, _qp(quote), broker=broker)
    assert [s["limit"] for s in broker.sells] == [quote[0]]
    assert res.profit_taken == 1 and res.pt_unsellable_bid == 0 and res.closing == 1
    assert _row(convexity_db, pid, "status")["status"] == "closing"


def test_real_unsellable_trigger_is_re_evaluated_next_tick(convexity_db):
    pid = _open_real(convexity_db)
    _real_tick(convexity_db, _qp(PENNY_BID), dry_run=True)
    res = _real_tick(convexity_db, _qp(SELLABLE), dry_run=True)
    assert res.profit_taken == 1 and res.closed == 1
    row = _row(convexity_db, pid, "status, exit_reason")
    assert row["status"] == "closed" and row["exit_reason"] == "profit_take_10x"


@UNSELLABLE
def test_real_unsellable_trigger_inside_the_time_stop_window_does_nothing_this_tick(convexity_db, quote):
    # Review N2: the junk mark that cannot profit-take must not fall through to a time-stop (which would orphan it on
    # a real submit) — the tick acts on nothing.
    pid = _open_real(convexity_db, expiry=NEAR)
    broker = _FakeBroker()
    res = _real_tick(convexity_db, _qp(quote), broker=broker)
    row = _row(convexity_db, pid, "status, rationale")
    assert row["status"] == "open" and broker.sells == [] and "orphaned" not in (row["rationale"] or "")
    assert (res.pt_unsellable_bid, res.time_stopped, res.orphaned, res.closed) == (1, 0, 0, 0)


def test_real_unsellable_is_counted_before_the_mark_only_deferral(convexity_db):
    # Review N2: on a mark-only tick an unsellable trigger counts as pt_unsellable_bid, not deferred; a sellable one
    # is deferred as before (#451).
    pid = _open_real(convexity_db)
    res = _real_tick(convexity_db, _qp(PENNY_BID), mark_only=True)
    assert (res.pt_unsellable_bid, res.deferred) == (1, 0)
    res = _real_tick(convexity_db, _qp(SELLABLE), mark_only=True)
    assert (res.pt_unsellable_bid, res.deferred) == (0, 1)
    assert _row(convexity_db, pid, "status")["status"] == "open"


def test_real_time_stop_with_an_unsellable_bid_is_unchanged(convexity_db):
    # No profit-take trigger: the time-stop fires as before — in-DB in DRY_RUN, orphaned on a real submit (#444).
    dry = _open_real(convexity_db, expiry=NEAR)
    res = _real_tick(convexity_db, _qp(LOW_ZERO_BID), dry_run=True)
    assert res.time_stopped == 1 and res.pt_unsellable_bid == 0
    assert _row(convexity_db, dry, "exit_reason")["exit_reason"] == "time_stop_21dte"

    real = _open_real(convexity_db, expiry=NEAR)
    res = _real_tick(convexity_db, _qp(LOW_ZERO_BID), broker=_FakeBroker())
    assert res.orphaned == 1 and res.pt_unsellable_bid == 0
    assert "time_stop_21dte" in _row(convexity_db, real, "rationale")["rationale"]


def test_real_expiry_with_a_zero_bid_settles_at_intrinsic(convexity_db):
    pid = _open_real(convexity_db, expiry=TODAY)
    res = _real_tick(convexity_db, _qp(ZERO_BID), broker=_FakeBroker())
    row = _row(convexity_db, pid, "status, exit_reason, mark")
    assert row["status"] == "closed" and row["exit_reason"] == "expiry" and row["mark"] == 0.0   # $50 < the $55 strike
    assert res.expired == 1 and res.pt_unsellable_bid == 0


def test_real_vertical_needs_its_long_leg_bid_at_the_floor(convexity_db):
    # A debit call vertical (+55/-60, width 5): spread mark = long mid − short mid = 5.0 − 0.1 ≈ 4.9 ≥ 10× 0.30.
    short = "FCX261218C00060000"
    pid = _open_real(convexity_db, short=short)
    res = _real_tick(convexity_db, _qp(PENNY_BID, **{short: (0.05, 0.15)}), dry_run=True)
    assert res.pt_unsellable_bid == 1 and res.profit_taken == 0
    assert _row(convexity_db, pid, "status")["status"] == "open"
    # A sellable long-leg bid is enough, even when the SHORT leg has no bid.
    res = _real_tick(convexity_db, _qp(SELLABLE, **{short: (0.0, 0.2)}), dry_run=True)
    assert res.profit_taken == 1 and res.pt_unsellable_bid == 0
    assert _row(convexity_db, pid, "exit_reason")["exit_reason"] == "profit_take_10x"


# ── the shadow null book ───────────────────────────────────────────────────────────────────────────────────────────

def _shadow(conn, expiry=FAR):
    return _insert_shadow(conn, contract=C, entry_pc=ENTRY_PC, contracts=2, expiry=expiry, strike=55.0)


def _shadow_tick(conn, qp, config=CFG, **kw):
    return shadow_book.mark_shadow_positions(conn=conn, clock=CLOCK, quote_provider=qp, config=config,
                                             underlying_price_of=_spot, **kw)


def _shadow_row(conn, pid):
    return conn.execute("SELECT status, mark, exit_reason FROM shadow_positions WHERE id=?", (pid,)).fetchone()


@UNSELLABLE
def test_shadow_unsellable_10x_stays_open(convexity_db, quote):
    pid = _shadow(convexity_db)
    res = _shadow_tick(convexity_db, _qp(quote))
    row = _shadow_row(convexity_db, pid)
    assert row["status"] == "open", "the shadow book booked a phantom 10x win the real book could not sell"
    assert row["exit_reason"] is None and row["mark"] == pytest.approx(sum(quote) / 2)
    assert (res.pt_unsellable_bid, res.profit_taken, res.closed, res.marked) == (1, 0, 0, 1)


@pytest.mark.parametrize("quote", [SELLABLE, FLOOR_BID], ids=["sellable", "bid-at-floor"])
def test_shadow_sellable_10x_profit_takes(convexity_db, quote):
    pid = _shadow(convexity_db)
    res = _shadow_tick(convexity_db, _qp(quote))
    assert res.profit_taken == 1 and res.pt_unsellable_bid == 0
    assert _shadow_row(convexity_db, pid)["exit_reason"] == "profit_take_10x"


def test_shadow_reads_the_floor_from_config(convexity_db):
    pid = _shadow(convexity_db)
    low = {"convexity_exits": {**CFG["convexity_exits"], "min_close_bid": 0.01}}
    res = _shadow_tick(convexity_db, _qp(PENNY_BID), config=low)
    assert res.profit_taken == 1 and _shadow_row(convexity_db, pid)["status"] == "closed"


def test_shadow_unsellable_trigger_is_re_evaluated_next_tick(convexity_db):
    pid = _shadow(convexity_db)
    _shadow_tick(convexity_db, _qp(PENNY_BID))
    res = _shadow_tick(convexity_db, _qp(SELLABLE))
    assert res.profit_taken == 1 and _shadow_row(convexity_db, pid)["status"] == "closed"


def test_shadow_unsellable_is_counted_before_the_mark_only_deferral(convexity_db):
    pid = _shadow(convexity_db)
    res = _shadow_tick(convexity_db, _qp(PENNY_BID), mark_only=True)
    assert (res.pt_unsellable_bid, res.deferred) == (1, 0)
    res = _shadow_tick(convexity_db, _qp(SELLABLE), mark_only=True)
    assert (res.pt_unsellable_bid, res.deferred) == (0, 1)
    assert _shadow_row(convexity_db, pid)["status"] == "open"


def test_shadow_time_stop_and_expiry_with_a_zero_bid_are_unchanged(convexity_db):
    ts = _shadow(convexity_db, expiry=NEAR)
    ex = _shadow(convexity_db, expiry=TODAY)
    res = _shadow_tick(convexity_db, _qp(LOW_ZERO_BID))
    assert _shadow_row(convexity_db, ts)["exit_reason"] == "time_stop_21dte"
    assert _shadow_row(convexity_db, ex)["exit_reason"] == "expiry"
    assert (res.time_stopped, res.expired, res.pt_unsellable_bid) == (1, 1, 0)


@UNSELLABLE
def test_shadow_unsellable_trigger_inside_the_time_stop_window_books_nothing_this_tick(convexity_db, quote):
    # The junk mark that cannot profit-take must not be booked as a time-stop either: the tick acts on nothing.
    pid = _shadow(convexity_db, expiry=NEAR)
    res = _shadow_tick(convexity_db, _qp(quote))
    assert _shadow_row(convexity_db, pid)["status"] == "open"
    assert (res.pt_unsellable_bid, res.time_stopped, res.closed) == (1, 0, 0)


# ── the 3A / 3B no-gate null books ─────────────────────────────────────────────────────────────────────────────────

def _fb(conn, book, expiry=FAR):
    return _insert_fb(conn, symbol="FCX", total_premium=2 * ENTRY_PC, contract=C, expiry=expiry, strike=55.0,
                      contracts=2, book=book)


def _fb_tick(conn, qp, config=CFG):
    return fixed_basket.mark_fixed_basket_positions(conn=conn, clock=CLOCK, quote_provider=qp, config=config,
                                                    underlying_price_of=_spot)


def _fb_row(conn, pid):
    return conn.execute("SELECT status, mark, exit_reason FROM fixed_basket_positions WHERE id=?", (pid,)).fetchone()


BOOKS = (fixed_basket.BOOK_UNION_NOGATE, fixed_basket.BOOK_BASKET_NOGATE)


@UNSELLABLE
def test_3a_3b_unsellable_10x_stays_open(convexity_db, quote):
    pids = [_fb(convexity_db, b) for b in BOOKS]
    res = _fb_tick(convexity_db, _qp(quote))
    for pid in pids:
        row = _fb_row(convexity_db, pid)
        assert row["status"] == "open", "a no-gate book booked a phantom 10x win the real book could not sell"
        assert row["exit_reason"] is None and row["mark"] == pytest.approx(sum(quote) / 2)
    assert (res.pt_unsellable_bid, res.profit_taken, res.closed, res.marked) == (2, 0, 0, 2)


@pytest.mark.parametrize("quote", [SELLABLE, FLOOR_BID], ids=["sellable", "bid-at-floor"])
def test_3a_3b_sellable_10x_profit_takes(convexity_db, quote):
    pids = [_fb(convexity_db, b) for b in BOOKS]
    res = _fb_tick(convexity_db, _qp(quote))
    assert res.profit_taken == 2 and res.pt_unsellable_bid == 0
    assert [_fb_row(convexity_db, p)["exit_reason"] for p in pids] == ["profit_take_10x"] * 2


def test_3a_3b_read_the_floor_from_config(convexity_db):
    pids = [_fb(convexity_db, b) for b in BOOKS]
    low = {"convexity_exits": {**CFG["convexity_exits"], "min_close_bid": 0.01}}
    res = _fb_tick(convexity_db, _qp(PENNY_BID), config=low)
    assert res.profit_taken == 2 and [_fb_row(convexity_db, p)["status"] for p in pids] == ["closed"] * 2


@UNSELLABLE
def test_3a_3b_unsellable_trigger_inside_the_time_stop_window_books_nothing_this_tick(convexity_db, quote):
    pids = [_fb(convexity_db, b, expiry=NEAR) for b in BOOKS]
    res = _fb_tick(convexity_db, _qp(quote))
    assert [_fb_row(convexity_db, p)["status"] for p in pids] == ["open"] * 2
    assert (res.pt_unsellable_bid, res.time_stopped, res.closed) == (2, 0, 0)


def test_3a_3b_time_stop_and_expiry_with_a_zero_bid_are_unchanged(convexity_db):
    ts = [_fb(convexity_db, b, expiry=NEAR) for b in BOOKS]
    ex = [_fb(convexity_db, b, expiry=TODAY) for b in BOOKS]
    res = _fb_tick(convexity_db, _qp(LOW_ZERO_BID))
    assert [_fb_row(convexity_db, p)["exit_reason"] for p in ts] == ["time_stop_21dte"] * 2
    assert [_fb_row(convexity_db, p)["exit_reason"] for p in ex] == ["expiry"] * 2
    assert (res.time_stopped, res.expired, res.pt_unsellable_bid) == (2, 2, 0)


# ── the rule itself ────────────────────────────────────────────────────────────────────────────────────────────────

def _pos(short=None):
    return {"id": 7, "symbol": "FCX", "contract_symbol": C, "short_contract_symbol": short}


def _ok(pos, bids, floor=0.05):
    return sellable_bid(pos, StaticQuoteProvider({C: 5.0}, bids=bids), book="t", mid=5.0, min_close_bid=floor)


def test_sellable_bid_reads_the_single_leg_or_the_long_leg_against_the_floor():
    short = "FCX261218C00060000"
    assert _ok(_pos(), {C: 0.05}) and _ok(_pos(), {C: 4.0})
    assert not _ok(_pos(), {C: 0.04}) and not _ok(_pos(), {C: 0.01}) and not _ok(_pos(), {C: 0.0})
    assert not _ok(_pos(), {})
    assert _ok(_pos(), {C: 0.01}, floor=0.01)
    assert not _ok(_pos(short), {C: 0.01, short: 1.0})
    assert _ok(_pos(short), {C: 0.05, short: 0.0})


def test_a_failing_bid_read_is_not_sellable():
    class _Boom(StaticQuoteProvider):
        def option_bid(self, contract_symbol):
            raise TimeoutError("quote endpoint down")

    assert not sellable_bid(_pos(), _Boom({C: 5.0}), book="t", mid=5.0, min_close_bid=0.05)


def test_the_floor_is_min_close_bid_with_the_monitors_default():
    assert min_close_bid_of({}) == 0.05 and min_close_bid_of({"convexity_exits": {}}) == 0.05
    assert min_close_bid_of({"convexity_exits": {"min_close_bid": 0.10}}) == 0.10


def test_the_null_exits_stamp_carries_both_rules():
    assert shadow_book.NULL_EXITS_STAMP == "closed_tick_mark_only_v1+sellable_bid_pt_v1"
