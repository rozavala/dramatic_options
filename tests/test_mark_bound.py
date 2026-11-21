"""#533: no book marks a position above its option's no-arbitrage bound.

The 2026-11-18 incident: a broken opening quote (bid 0, ask 20.2) marked the real book's $6-strike RDW put at 10.10,
crossing the 10× profit-take; its bid was under ``min_close_bid``, so the journal booked a phantom +$9,150 close.
Each test drives the real quote path (``AlpacaQuoteProvider`` over a fake chain client) through a book's mark pass.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import fixed_basket
import shadow_book
import state
from clock import FixedClock
from convexity_data import AlpacaQuoteProvider, StaticQuoteProvider
from mark_bound import BoundedMarker
from monitor import monitor_positions

RDW_PUT = "RDW270521P00006000"
RDW_CALL = "RDW270521C00010000"
CLOCK = FixedClock(datetime(2026, 11, 18, 14, 30, tzinfo=UTC))
CONFIG = {"convexity_exits": {"profit_take_multiple": 10.0, "time_stop_dte": 21, "min_close_bid": 0.05}}
PRIOR_MARK = 1.07   # the last sane mark; the 11-17 close marked it at ≈1.13× entry


class _Chain:
    """The read-only client surface ``AlpacaQuoteProvider`` uses: one chain pull per underlying."""

    def __init__(self, quotes: dict[str, tuple[float | None, float | None]]) -> None:
        self._quotes = quotes
        self.pulls = 0

    def option_quote_tuples(self, underlying, **_kw):
        self.pulls += 1
        return [{"symbol": s, "bid": b, "ask": a} for s, (b, a) in self._quotes.items() if s.startswith(underlying)]


class _Broker:
    """Records any order. The bounded path must never reach it."""

    def __init__(self) -> None:
        self.submits: list[dict] = []

    def submit_paper(self, **kw):
        self.submits.append(kw)
        raise AssertionError(f"no order may be sent on a rejected mark: {kw}")


def _qp(bid: float, ask: float, contract: str = RDW_PUT) -> AlpacaQuoteProvider:
    return AlpacaQuoteProvider(_Chain({contract: (bid, ask)}))


def _open_real(conn, *, contract=RDW_PUT, kind="P", strike=6.0) -> int:
    pid = state.record_convexity_position(
        conn, run_id=None, opened_at="2026-11-13T18:30:02+00:00", theme="space_smallcap", symbol="RDW",
        direction="bearish" if kind == "P" else "bullish", structure_kind=kind, contract_symbol=contract,
        expiry="2027-05-21", strike=strike, dte=189, moneyness=-0.20, contracts=10,
        entry_premium_per_contract=95.0, total_premium=950.0)
    state.mark_convexity_position(conn, pid, mark=PRIOR_MARK, as_of="2026-11-17T21:00:00+00:00")
    return pid


def _real_row(conn, pid):
    return conn.execute("SELECT status, mark, marked_at, realized_pnl, exit_reason FROM convexity_positions "
                        "WHERE id = ?", (pid,)).fetchone()


# ── the real monitor ───────────────────────────────────────────────────────────────────────────────────────────────

def test_real_monitor_rdw_shape_is_unmarked_not_profit_taken(convexity_db, caplog):
    pid = _open_real(convexity_db)
    with caplog.at_level(logging.WARNING):
        res = monitor_positions(conn=convexity_db, clock=CLOCK, quote_provider=_qp(0.0, 20.2), config=CONFIG)
    assert (res.unmarked, res.marked, res.profit_taken, res.closed, res.realized_pnl) == (1, 0, 0, 0, 0.0)
    row = _real_row(convexity_db, pid)
    assert row["status"] == "open" and row["exit_reason"] is None and row["realized_pnl"] is None
    assert row["mark"] == PRIOR_MARK and row["marked_at"] == "2026-11-17T21:00:00+00:00"   # stored mark kept
    msg = next(r.getMessage() for r in caplog.records if "REJECTED" in r.getMessage())
    assert "bid 0.00" in msg and "ask 20.20" in msg and "bound 6.00" in msg and RDW_PUT in msg


def test_real_monitor_rdw_shape_real_submit_sends_nothing_books_nothing(convexity_db):
    # The incident's own path: a broker, outside DRY_RUN, bid under min_close_bid.
    pid = _open_real(convexity_db)
    broker = _Broker()
    res = monitor_positions(conn=convexity_db, clock=CLOCK, quote_provider=_qp(0.0, 20.2), config=CONFIG,
                            broker=broker, dry_run=False)
    assert res.unmarked == 1 and res.closed == 0 and res.profit_taken == 0 and broker.submits == []
    assert _real_row(convexity_db, pid)["status"] == "open"


def test_real_monitor_sane_put_quote_unchanged(convexity_db):
    pid = _open_real(convexity_db)
    res = monitor_positions(conn=convexity_db, clock=CLOCK, quote_provider=_qp(0.95, 1.05), config=CONFIG)
    assert res.marked == 1 and res.unmarked == 0 and res.closed == 0
    assert _real_row(convexity_db, pid)["mark"] == 1.0


def test_real_monitor_put_mid_at_its_strike_is_kept(convexity_db):
    # The bound is inclusive: a deep-ITM put worth its strike is a legal (if extreme) mark.
    pid = _open_real(convexity_db)
    res = monitor_positions(conn=convexity_db, clock=CLOCK, quote_provider=_qp(5.9, 6.1), config=CONFIG)
    assert res.marked == 1 and res.unmarked == 0
    assert abs(_real_row(convexity_db, pid)["mark"] - 6.0) < 1e-9


def test_real_monitor_call_above_spot_is_rejected(convexity_db):
    pid = _open_real(convexity_db, contract=RDW_CALL, kind="C", strike=10.0)
    lookups: list[str] = []

    def spot(sym):
        lookups.append(sym)
        return 7.5

    res = monitor_positions(conn=convexity_db, clock=CLOCK, quote_provider=_qp(0.0, 20.2, RDW_CALL), config=CONFIG,
                            underlying_price_of=spot)
    assert res.unmarked == 1 and res.closed == 0 and res.profit_taken == 0
    assert _real_row(convexity_db, pid)["mark"] == PRIOR_MARK and lookups == ["RDW"]


def test_real_monitor_call_without_a_spot_keeps_todays_behaviour(convexity_db):
    # No underlying price → no bound is invented for a call: marked (and here profit-taken) exactly as before #533.
    # (A two-sided quote: since #537 a zero-bid quote never triggers a profit-take, bound or no bound.)
    pid = _open_real(convexity_db, contract=RDW_CALL, kind="C", strike=10.0)
    res = monitor_positions(conn=convexity_db, clock=CLOCK, quote_provider=_qp(0.2, 20.0, RDW_CALL), config=CONFIG)
    assert res.marked == 1 and res.profit_taken == 1
    assert _real_row(convexity_db, pid)["status"] == "closed"


# ── the null books ─────────────────────────────────────────────────────────────────────────────────────────────────

def test_shadow_book_rdw_shape_is_unmarked_not_profit_taken(convexity_db):
    pid = state.record_shadow_position(
        convexity_db, run_id=None, origin="sentinel", opened_at="2026-11-13T18:30:02+00:00", theme="t",
        symbol="RDW", direction="bearish", structure_kind="P", contract_symbol=RDW_PUT, expiry="2027-05-21",
        strike=6.0, dte=189, moneyness=-0.20, contracts=10, entry_premium_per_contract=95.0, total_premium=950.0,
        entry_spot=7.5)
    state.mark_shadow_position(convexity_db, pid, mark=PRIOR_MARK, as_of="2026-11-17T21:00:00+00:00")
    res = shadow_book.mark_shadow_positions(conn=convexity_db, clock=CLOCK, quote_provider=_qp(0.0, 20.2),
                                            config=CONFIG)
    assert (res.unmarked, res.marked, res.profit_taken, res.closed) == (1, 0, 0, 0)
    row = convexity_db.execute("SELECT status, mark FROM shadow_positions WHERE id = ?", (pid,)).fetchone()
    assert row["status"] == "open" and row["mark"] == PRIOR_MARK


def test_fixed_basket_rdw_shape_is_unmarked_not_profit_taken(convexity_db):
    pid = state.record_fixed_basket_position(
        convexity_db, run_id=None, book="3a", origin="sentinel", opened_at="2026-11-13T18:30:02+00:00", theme="t",
        symbol="RDW", direction="bearish", structure_kind="P", contract_symbol=RDW_PUT, expiry="2027-05-21",
        strike=6.0, dte=189, moneyness=-0.20, contracts=10, entry_premium_per_contract=95.0, total_premium=950.0,
        entry_spot=7.5)
    state.mark_fixed_basket_position(convexity_db, pid, mark=PRIOR_MARK, as_of="2026-11-17T21:00:00+00:00")
    res = fixed_basket.mark_fixed_basket_positions(conn=convexity_db, clock=CLOCK, quote_provider=_qp(0.0, 20.2),
                                                   config=CONFIG)
    assert (res.unmarked, res.marked, res.profit_taken, res.closed) == (1, 0, 0, 0)
    row = convexity_db.execute("SELECT status, mark FROM fixed_basket_positions WHERE id = ?", (pid,)).fetchone()
    assert row["status"] == "open" and row["mark"] == PRIOR_MARK


def test_vertical_above_its_width_is_unmarked(convexity_db):
    # A debit call vertical is worth at most its strike width; a junk long-leg ask breaches it with no spot needed.
    pid = state.record_shadow_position(
        convexity_db, run_id=None, origin="sentinel", opened_at="2026-11-13T18:30:02+00:00", theme="t",
        symbol="RDW", direction="bullish", structure_kind="C", contract_symbol=RDW_CALL, expiry="2027-05-21",
        strike=10.0, dte=189, moneyness=0.25, contracts=1, entry_premium_per_contract=50.0, total_premium=50.0,
        entry_spot=7.5, short_contract_symbol="RDW270521C00013000", short_strike=13.0)
    qp = AlpacaQuoteProvider(_Chain({RDW_CALL: (0.0, 20.2), "RDW270521C00013000": (0.05, 0.15)}))
    res = shadow_book.mark_shadow_positions(conn=convexity_db, clock=CLOCK, quote_provider=qp, config=CONFIG)
    assert res.unmarked == 1 and res.closed == 0
    assert convexity_db.execute("SELECT status FROM shadow_positions WHERE id = ?", (pid,)).fetchone()[0] == "open"


# ── the marker itself ──────────────────────────────────────────────────────────────────────────────────────────────

def _pos(contract, symbol="RDW", pid=1):
    return {"id": pid, "symbol": symbol, "contract_symbol": contract, "short_contract_symbol": None}


def test_spot_is_fetched_once_per_underlying_and_only_for_calls():
    calls: list[str] = []
    qp = StaticQuoteProvider({RDW_CALL: 1.0, "RDW270521C00012000": 0.5, RDW_PUT: 1.0})
    m = BoundedMarker(qp, lambda s: calls.append(s) or 7.5, book="t")
    assert m.mark(_pos(RDW_CALL)) == 1.0 and m.mark(_pos("RDW270521C00012000")) == 0.5 and m.mark(_pos(RDW_PUT)) == 1.0
    assert calls == ["RDW"]


def test_a_failed_spot_lookup_stops_lookups_for_the_pass_and_marks_unbounded():
    calls: list[str] = []

    def boom(sym):
        calls.append(sym)
        raise TimeoutError("data down")

    qp = StaticQuoteProvider({RDW_CALL: 50.0, "FCX270521C00060000": 2.0})
    m = BoundedMarker(qp, boom, book="t")
    assert m.mark(_pos(RDW_CALL)) == 50.0                       # no spot → no invented bound
    assert m.mark(_pos("FCX270521C00060000", "FCX")) == 2.0
    assert calls == ["RDW"]                                     # one failure, then no more lookups this pass


def test_adjusted_class_call_is_not_bounded_by_the_ticker_price():
    m = BoundedMarker(StaticQuoteProvider({"CDE2270115C00012000": 20.0}), lambda s: 7.5, book="t")
    assert m.mark(_pos("CDE2270115C00012000", "CDE")) == 20.0
