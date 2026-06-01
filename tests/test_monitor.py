"""L2 monitor: mark-to-market, profit-take, time-stop, expiry, drawdown→kill-rule."""

from datetime import UTC, datetime, timedelta

import state
from clock import FixedClock
from convexity_data import StaticQuoteProvider
from monitor import intrinsic_value, monitor_positions
from paper_loop import kill_rule_status

CONFIG = {
    "convexity_book": {"account_equity": 100_000.0, "book_fraction": 0.10,
                       "per_name_fraction": 0.01, "max_open_positions": 15},
    "convexity_exits": {"profit_take_multiple": 4.0, "time_stop_dte": 21},
    "kill_rule": {"book_drawdown_halt": 0.20, "dry_months_halt": 9},
}
NOW = datetime(2026, 6, 1, tzinfo=UTC)
CLOCK = FixedClock(NOW)


def _open(conn, *, contract, entry_pc, contracts=1, expiry="2026-12-18", strike=80.0, kind="C", symbol="FCX"):
    return state.record_convexity_position(
        conn, run_id=None, opened_at="2026-01-01T00:00:00+00:00", theme="t", symbol=symbol,
        direction="bullish", structure_kind=kind, contract_symbol=contract, expiry=expiry,
        strike=strike, dte=270, moneyness=0.25, contracts=contracts,
        entry_premium_per_contract=entry_pc, total_premium=entry_pc * contracts,
    )


def test_intrinsic_value():
    assert intrinsic_value("C", 80.0, 100.0) == 20.0
    assert intrinsic_value("C", 80.0, 70.0) == 0.0
    assert intrinsic_value("P", 80.0, 70.0) == 10.0
    assert intrinsic_value("C", 80.0, None) == 0.0


def test_mark_updates_and_no_exit(convexity_db):
    pid = _open(convexity_db, contract="FCX261218C00080000", entry_pc=758.0)
    qp = StaticQuoteProvider({"FCX261218C00080000": 9.0})  # mid 9 → $900 < 4× $758
    res = monitor_positions(conn=convexity_db, clock=CLOCK, quote_provider=qp, config=CONFIG)
    assert res.marked == 1 and res.closed == 0
    row = convexity_db.execute("SELECT mark, status FROM convexity_positions WHERE id=?", (pid,)).fetchone()
    assert row["mark"] == 9.0 and row["status"] == "open"


def test_profit_take(convexity_db):
    pid = _open(convexity_db, contract="FCX261218C00080000", entry_pc=200.0)  # $2/ct entry
    qp = StaticQuoteProvider({"FCX261218C00080000": 9.0})  # $900 ≥ 4× $200 → take
    res = monitor_positions(conn=convexity_db, clock=CLOCK, quote_provider=qp, config=CONFIG)
    assert res.profit_taken == 1 and res.closed == 1
    row = convexity_db.execute("SELECT status, realized_pnl, exit_reason FROM convexity_positions WHERE id=?", (pid,)).fetchone()
    assert row["status"] == "closed"
    assert row["realized_pnl"] == (9.0 * 100 - 200.0) * 1  # $700
    assert "profit_take" in row["exit_reason"]


def test_time_stop(convexity_db):
    # expiry 10 days out (< 21 DTE) → time-stop at current mid.
    exp = (NOW.date() + timedelta(days=10)).isoformat()
    pid = _open(convexity_db, contract="FCX260611C00080000", entry_pc=200.0, expiry=exp)
    qp = StaticQuoteProvider({"FCX260611C00080000": 1.0})  # $100 mark
    res = monitor_positions(conn=convexity_db, clock=CLOCK, quote_provider=qp, config=CONFIG)
    assert res.time_stopped == 1 and res.closed == 1
    row = convexity_db.execute("SELECT status, realized_pnl, exit_reason FROM convexity_positions WHERE id=?", (pid,)).fetchone()
    assert row["status"] == "closed" and "time_stop" in row["exit_reason"]
    assert row["realized_pnl"] == (1.0 * 100 - 200.0)  # −$100


def test_expiry_closes_at_intrinsic_otm_is_minus_premium(convexity_db):
    exp = (NOW.date() - timedelta(days=1)).isoformat()  # already expired
    pid = _open(convexity_db, contract="FCX260531C00080000", entry_pc=758.0, expiry=exp, strike=80.0)
    # underlying below strike → far-OTM call expires worthless → realized = −premium.
    res = monitor_positions(conn=convexity_db, clock=CLOCK, quote_provider=StaticQuoteProvider({}),
                            config=CONFIG, underlying_price_of=lambda s: 66.0)
    assert res.expired == 1 and res.closed == 1
    row = convexity_db.execute("SELECT status, realized_pnl FROM convexity_positions WHERE id=?", (pid,)).fetchone()
    assert row["status"] == "closed" and row["realized_pnl"] == -758.0


def test_expiry_itm_realizes_intrinsic(convexity_db):
    exp = (NOW.date() - timedelta(days=1)).isoformat()
    pid = _open(convexity_db, contract="FCX260531C00080000", entry_pc=200.0, expiry=exp, strike=80.0)
    res = monitor_positions(conn=convexity_db, clock=CLOCK, quote_provider=StaticQuoteProvider({}),
                            config=CONFIG, underlying_price_of=lambda s: 100.0)  # ITM by $20
    assert res.expired == 1
    row = convexity_db.execute("SELECT realized_pnl FROM convexity_positions WHERE id=?", (pid,)).fetchone()
    assert row["realized_pnl"] == (20.0 * 100 - 200.0)  # $1800


def test_unmarked_when_no_quote(convexity_db):
    _open(convexity_db, contract="FCX261218C00080000", entry_pc=758.0)
    res = monitor_positions(conn=convexity_db, clock=CLOCK, quote_provider=StaticQuoteProvider({}), config=CONFIG)
    assert res.unmarked == 1 and res.marked == 0


def test_drawdown_marks_trip_kill_rule(convexity_db):
    # Book budget = $10k. One position $758 entry; mark it down hard so the OPEN-book
    # drawdown crosses 20% of the $10k budget → kill rule trips on the next cycle.
    # Need (entry − marked) ≥ 0.20·10000 = $2000. Use a big position to make marks bite.
    _open(convexity_db, contract="FCX261218C00080000", entry_pc=300.0, contracts=10)  # $3000 at risk
    qp = StaticQuoteProvider({"FCX261218C00080000": 0.10})  # mark $10/ct → marked $100, loss ~$2900
    monitor_positions(conn=convexity_db, clock=CLOCK, quote_provider=qp, config=CONFIG)
    krs = kill_rule_status(convexity_db, CONFIG, CLOCK)
    assert krs.tripped is True
    assert krs.book_drawdown >= 0.20


def test_drawdown_not_tripped_when_marks_healthy(convexity_db):
    _open(convexity_db, contract="FCX261218C00080000", entry_pc=300.0, contracts=10)
    qp = StaticQuoteProvider({"FCX261218C00080000": 3.0})  # mark == entry → no drawdown
    monitor_positions(conn=convexity_db, clock=CLOCK, quote_provider=qp, config=CONFIG)
    krs = kill_rule_status(convexity_db, CONFIG, CLOCK)
    assert krs.tripped is False
