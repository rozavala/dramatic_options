"""L2 monitor: mark-to-market, profit-take, time-stop, expiry, drawdown→kill-rule."""

from datetime import UTC, datetime, timedelta

from dramatic_options import state
from dramatic_options.clock import FixedClock
from dramatic_options.convexity_data import StaticQuoteProvider
from dramatic_options.monitor import intrinsic_value, monitor_positions
from dramatic_options.paper_loop import kill_rule_status

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


# ── two-sided real-submit exits (T2.5; broker supplied, dry_run=False) ─────────

class _FakeBroker:
    """Records SELL_TO_CLOSE submits; returns a configurable Fill + order statuses."""

    def __init__(self, *, sell=None):
        from dramatic_options.broker import Fill
        self.sells = []
        self.cancelled = []
        self._statuses = {}
        self._sell = sell or Fill(True, 0.0, 1, "submitted (resting)", order_id="cl-1", pending=True)

    def account_equity(self):
        return 100000.0

    def submit_paper(self, *, contract_symbol, qty, side, limit_price, client_order_id=None):
        self.sells.append({"contract": contract_symbol, "side": side, "limit": limit_price, "coid": client_order_id})
        return self._sell

    def order_status(self, oid):
        return self._statuses.get(oid)

    def cancel_order(self, oid):
        self.cancelled.append(oid)


def _row(conn, pid, cols):
    return conn.execute(f"SELECT {cols} FROM convexity_positions WHERE id=?", (pid,)).fetchone()


def test_profit_take_real_submit_sends_sell_and_marks_closing(convexity_db):
    pid = _open(convexity_db, contract="FCX261218C00080000", entry_pc=200.0)  # $900 ≥ 4×$200 → PT
    qp = StaticQuoteProvider({"FCX261218C00080000": 9.0}, bids={"FCX261218C00080000": 8.9})  # marketable
    broker = _FakeBroker()
    res = monitor_positions(conn=convexity_db, clock=CLOCK, quote_provider=qp, config=CONFIG,
                            broker=broker, dry_run=False)
    assert res.profit_taken == 1 and res.closing == 1 and res.closed == 0  # resting, not booked
    assert broker.sells[0]["side"] == "sell" and broker.sells[0]["coid"].startswith("close-")
    row = _row(convexity_db, pid, "status, close_order_id")
    assert row["status"] == "closing" and row["close_order_id"] == "cl-1"


def test_closing_fill_books_actual_exit_price(convexity_db):
    pid = _open(convexity_db, contract="FCX261218C00080000", entry_pc=200.0)
    state.begin_close_convexity_position(convexity_db, pid, close_order_id="cl-1",
                                         reason="profit_take_4x", as_of="t")
    broker = _FakeBroker()
    broker._statuses["cl-1"] = {"state": "filled", "filled_avg_price": "8.50"}  # real fill below mid
    res = monitor_positions(conn=convexity_db, clock=CLOCK, quote_provider=StaticQuoteProvider({}),
                            config=CONFIG, broker=broker, dry_run=False)
    assert res.closed == 1
    row = _row(convexity_db, pid, "status, mark, realized_pnl")
    assert row["status"] == "closed" and row["mark"] == 8.5
    assert row["realized_pnl"] == (8.5 * 100 - 200.0)  # honest fill, not the mid


def test_unsellable_time_stop_books_in_db_no_churn(convexity_db):
    exp = (NOW.date() + timedelta(days=9)).isoformat()
    pid = _open(convexity_db, contract="FCX260610C00080000", entry_pc=500.0, expiry=exp)
    qp = StaticQuoteProvider({"FCX260610C00080000": 0.10}, bids={"FCX260610C00080000": 0.0})  # bid<floor
    broker = _FakeBroker()
    res = monitor_positions(conn=convexity_db, clock=CLOCK, quote_provider=qp, config=CONFIG,
                            broker=broker, dry_run=False)
    assert res.time_stopped == 1 and res.closed == 1 and res.closing == 0 and broker.sells == []
    row = _row(convexity_db, pid, "status, exit_reason")
    assert row["status"] == "closed" and row["exit_reason"].startswith("time_stop") and "unsellable" in row["exit_reason"]


def test_closing_terminal_reopens_to_retry(convexity_db):
    pid = _open(convexity_db, contract="FCX261218C00080000", entry_pc=200.0)
    state.begin_close_convexity_position(convexity_db, pid, close_order_id="cl-1",
                                         reason="profit_take_4x", as_of="t")
    broker = _FakeBroker()
    broker._statuses["cl-1"] = {"state": "canceled"}
    monitor_positions(conn=convexity_db, clock=CLOCK, quote_provider=StaticQuoteProvider({}),
                      config=CONFIG, broker=broker, dry_run=False)
    row = _row(convexity_db, pid, "status, close_order_id")
    assert row["status"] == "open" and row["close_order_id"] is None  # fresh id next time


def test_expiry_while_closing_cancels_and_books_intrinsic(convexity_db):
    exp = (NOW.date() + timedelta(days=5)).isoformat()
    pid = _open(convexity_db, contract="FCX260606C00080000", entry_pc=500.0, expiry=exp, strike=80.0)
    state.begin_close_convexity_position(convexity_db, pid, close_order_id="cl-1",
                                         reason="time_stop_21dte", as_of="t")
    past = FixedClock(NOW + timedelta(days=10))  # now past expiry
    broker = _FakeBroker()
    res = monitor_positions(conn=convexity_db, clock=past, quote_provider=StaticQuoteProvider({}),
                            config=CONFIG, broker=broker, dry_run=False, underlying_price_of=lambda s: 100.0)
    assert res.expired == 1 and res.closed == 1 and broker.cancelled == ["cl-1"]
    row = _row(convexity_db, pid, "status, mark")
    assert row["status"] == "closed" and row["mark"] == 20.0  # intrinsic 100−80
