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


# ── two-sided real-submit exits (T2.5; broker supplied, dry_run=False) ─────────

class _FakeBroker:
    """Records SELL_TO_CLOSE submits; returns a configurable Fill + order statuses."""

    def __init__(self, *, sell=None):
        from broker import Fill
        self.sells = []
        self.cancelled = []
        self._statuses = {}
        self._sell = sell or Fill(True, 0.0, 1, "submitted (resting)", order_id="cl-1", pending=True)

    def account_equity(self):
        return 100000.0

    def submit_paper(self, *, contract_symbol, qty, side, limit_price, client_order_id=None):
        self.sells.append({"contract": contract_symbol, "side": side, "limit": limit_price, "coid": client_order_id,
                           "qty": qty})
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
    assert broker.sells[0]["side"] == "sell" and broker.sells[0]["coid"].startswith("do-close-")
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
    broker._statuses["cl-1"] = {"state": "canceled"}   # read back after the cancel (#445): nothing filled
    res = monitor_positions(conn=convexity_db, clock=past, quote_provider=StaticQuoteProvider({}),
                            config=CONFIG, broker=broker, dry_run=False, underlying_price_of=lambda s: 100.0)
    assert res.expired == 1 and res.closed == 1 and broker.cancelled == ["cl-1"]
    row = _row(convexity_db, pid, "status, mark")
    assert row["status"] == "closed" and row["mark"] == 20.0  # intrinsic 100−80


def _dead_or(price):
    # #440: a price provider that RAISES for a dead symbol (ATKR after its take-private) and prices the rest
    def f(sym):
        if sym == "DEAD":
            raise RuntimeError("no bars for DEAD")
        return price
    return f


def test_a_raising_expiry_price_leaves_that_position_open_and_closes_the_rest(convexity_db):
    exp = (NOW.date() - timedelta(days=1)).isoformat()
    dead = _open(convexity_db, contract="DEAD260531C00080000", entry_pc=200.0, expiry=exp, symbol="DEAD")
    live = _open(convexity_db, contract="FCX260531C00080000", entry_pc=200.0, expiry=exp)
    res = monitor_positions(conn=convexity_db, clock=CLOCK, quote_provider=StaticQuoteProvider({}),
                            config=CONFIG, underlying_price_of=_dead_or(100.0))
    assert res.expired == 1 and res.unmarked == 1
    assert convexity_db.execute("SELECT status FROM convexity_positions WHERE id=?", (dead,)).fetchone()[0] == "open"
    row = convexity_db.execute("SELECT status, realized_pnl FROM convexity_positions WHERE id=?", (live,)).fetchone()
    assert row["status"] == "closed" and row["realized_pnl"] == (20.0 * 100 - 200.0)


def test_an_in_db_close_waits_when_the_price_lookup_raises(convexity_db):
    # nothing is transmitted on the in-DB path, so the row stays open (retried next cycle) rather than closing with an
    # outcome that could never be scored
    exp = (NOW.date() + timedelta(days=10)).isoformat()             # ≤ 21 DTE → time-stop at the mark
    pid = _open(convexity_db, contract="DEAD260611C00080000", entry_pc=200.0, expiry=exp, symbol="DEAD")
    res = monitor_positions(conn=convexity_db, clock=CLOCK, quote_provider=StaticQuoteProvider({"DEAD260611C00080000": 1.0}),
                            config=CONFIG, underlying_price_of=_dead_or(100.0))
    assert res.time_stopped == 0 and res.closed == 0 and res.marked == 1
    assert convexity_db.execute("SELECT status FROM convexity_positions WHERE id=?", (pid,)).fetchone()[0] == "open"


def test_a_filled_sell_is_booked_even_when_the_exit_spot_lookup_raises(convexity_db):
    # #440 review: on main a raise after a FILLED SELL_TO_CLOSE left a sold position 'open' in the journal
    from broker import Fill
    exp = (NOW.date() + timedelta(days=10)).isoformat()
    pid = _open(convexity_db, contract="DEAD260611C00080000", entry_pc=200.0, expiry=exp, symbol="DEAD")
    broker = _FakeBroker(sell=Fill(True, 1.0, 1, "filled", order_id="cl-9", pending=False))
    res = monitor_positions(conn=convexity_db, clock=CLOCK,
                            quote_provider=StaticQuoteProvider({"DEAD260611C00080000": 1.0}), config=CONFIG,
                            broker=broker, dry_run=False, underlying_price_of=_dead_or(100.0))
    assert len(broker.sells) == 1 and res.closed == 1
    assert _row(convexity_db, pid, "status")["status"] == "closed"


def test_expiry_while_closing_with_a_raising_price_stays_closing_then_closes(convexity_db, monkeypatch):
    import notify
    pages = []
    monkeypatch.setattr(notify, "send", lambda t, m, priority=0: pages.append(t) or True)
    exp = (NOW.date() + timedelta(days=5)).isoformat()
    pid = _open(convexity_db, contract="DEAD260606C00080000", entry_pc=500.0, expiry=exp, symbol="DEAD")
    state.begin_close_convexity_position(convexity_db, pid, close_order_id="cl-1", reason="time_stop_21dte", as_of="t")
    past = FixedClock(NOW + timedelta(days=10))
    broker = _FakeBroker()
    broker._statuses["cl-1"] = {"state": "canceled"}
    res = monitor_positions(conn=convexity_db, clock=past, quote_provider=StaticQuoteProvider({}), config=CONFIG,
                            broker=broker, dry_run=False, underlying_price_of=_dead_or(100.0))
    assert res.unmarked == 1 and res.closed == 0 and broker.cancelled == ["cl-1"]
    assert _row(convexity_db, pid, "status")["status"] == "closing"
    assert pages == ["EXPIRY PRICE LOOKUP FAILED"]
    res2 = monitor_positions(conn=convexity_db, clock=past, quote_provider=StaticQuoteProvider({}), config=CONFIG,
                             broker=broker, dry_run=False, underlying_price_of=lambda s: 100.0)
    assert res2.expired == 1 and _row(convexity_db, pid, "status")["status"] == "closed"


# ── #445: expiry while closing settles the cancel before booking ───────────────────────────────

def _closing_at_expiry(conn, *, contracts=2, entry_pc=500.0):
    exp = (NOW.date() + timedelta(days=5)).isoformat()
    pid = _open(conn, contract="FCX260606C00080000", entry_pc=entry_pc, expiry=exp, strike=80.0, contracts=contracts)
    state.begin_close_convexity_position(conn, pid, close_order_id="cl-1", reason="time_stop_21dte", as_of="t")
    return pid, FixedClock(NOW + timedelta(days=10))


def test_a_sell_that_filled_before_the_cancel_books_its_fill_not_intrinsic(convexity_db):
    pid, past = _closing_at_expiry(convexity_db)
    broker = _FakeBroker()
    broker._statuses["cl-1"] = {"state": "filled", "filled_avg_price": "21.40", "filled_qty": "2"}
    res = monitor_positions(conn=convexity_db, clock=past, quote_provider=StaticQuoteProvider({}), config=CONFIG,
                            broker=broker, dry_run=False, underlying_price_of=lambda s: 100.0)
    row = _row(convexity_db, pid, "status, realized_pnl, exit_reason")
    assert res.closed == 1 and res.expired == 0 and broker.cancelled == ["cl-1"]
    assert row["status"] == "closed" and row["exit_reason"] == "time_stop_21dte"
    assert row["realized_pnl"] == (21.40 * 100 - 500.0) * 2          # the fill, not intrinsic 20.00


def test_a_partial_fill_before_the_cancel_blends_fill_and_intrinsic(convexity_db):
    pid, past = _closing_at_expiry(convexity_db)
    broker = _FakeBroker()
    broker._statuses["cl-1"] = {"state": "canceled", "filled_avg_price": "22.00", "filled_qty": "1"}   # 1 of 2
    monitor_positions(conn=convexity_db, clock=past, quote_provider=StaticQuoteProvider({}), config=CONFIG,
                      broker=broker, dry_run=False, underlying_price_of=lambda s: 100.0)
    row = _row(convexity_db, pid, "status, realized_pnl, exit_reason")
    assert row["status"] == "closed" and row["exit_reason"] == "expiry"
    assert abs(row["realized_pnl"] - ((22.00 * 100 - 500.0) + (20.00 * 100 - 500.0))) < 1e-6


def test_an_unknown_cancel_outcome_leaves_the_row_closing_pages_then_books_once_read(convexity_db, monkeypatch):
    import notify
    pages = []
    monkeypatch.setattr(notify, "send", lambda t, m, priority=0: pages.append(t) or True)
    pid, past = _closing_at_expiry(convexity_db)
    broker = _FakeBroker()                                            # order_status → None (pending_cancel / unread)
    res = monitor_positions(conn=convexity_db, clock=past, quote_provider=StaticQuoteProvider({}), config=CONFIG,
                            broker=broker, dry_run=False, underlying_price_of=lambda s: 100.0)
    assert res.closed == 0 and res.unmarked == 1 and broker.cancelled == ["cl-1"]
    assert _row(convexity_db, pid, "status")["status"] == "closing" and pages == ["EXPIRY CANCEL OUTCOME UNKNOWN"]
    broker._statuses["cl-1"] = {"state": "filled", "filled_avg_price": "21.40", "filled_qty": "2"}   # read next cycle
    res2 = monitor_positions(conn=convexity_db, clock=past, quote_provider=StaticQuoteProvider({}), config=CONFIG,
                             broker=broker, dry_run=False, underlying_price_of=lambda s: 100.0)
    row = _row(convexity_db, pid, "status, realized_pnl")
    assert res2.closed == 1 and row["status"] == "closed" and row["realized_pnl"] == (21.40 * 100 - 500.0) * 2


def test_a_fill_with_no_reported_price_falls_back_to_the_entry_price_not_zero(convexity_db):
    pid, past = _closing_at_expiry(convexity_db)
    broker = _FakeBroker()
    broker._statuses["cl-1"] = {"state": "filled", "filled_qty": "2"}           # no filled_avg_price
    monitor_positions(conn=convexity_db, clock=past, quote_provider=StaticQuoteProvider({}), config=CONFIG,
                      broker=broker, dry_run=False, underlying_price_of=lambda s: 100.0)
    assert _row(convexity_db, pid, "realized_pnl")["realized_pnl"] == 0.0        # (5.00·100 − 500)·2, as reconciled


# ── #449: a close that partly filled, then ended, books what sold and reopens only the rest ────────

def test_a_partly_filled_then_expired_close_reopens_only_the_rest(convexity_db):
    pid = _open(convexity_db, contract="FCX261218C00080000", entry_pc=500.0, contracts=3)   # $1,500 at risk
    state.begin_close_convexity_position(convexity_db, pid, close_order_id="cl-1", reason="time_stop_21dte", as_of="t")
    broker = _FakeBroker()
    broker._statuses["cl-1"] = {"state": "expired", "filled_avg_price": "7.00", "filled_qty": "2"}   # DAY order: 2 of 3
    res = monitor_positions(conn=convexity_db, clock=CLOCK, quote_provider=StaticQuoteProvider({}), config=CONFIG,
                            broker=broker, dry_run=False)
    row = _row(convexity_db, pid, "status, contracts, total_premium, close_order_id, realized_pnl")
    assert row["status"] == "open" and row["contracts"] == 1 and row["close_order_id"] is None
    assert abs(row["total_premium"] - 500.0) < 1e-9 and row["realized_pnl"] is None           # still open
    assert res.realized_pnl == (7.00 * 100 - 500.0) * 2                                        # the sold part, $400


def test_the_final_close_books_the_whole_bet_once(convexity_db):
    pid = _open(convexity_db, contract="FCX261218C00080000", entry_pc=500.0, contracts=3)
    state.begin_close_convexity_position(convexity_db, pid, close_order_id="cl-1", reason="time_stop_21dte", as_of="t")
    broker = _FakeBroker()
    broker._statuses["cl-1"] = {"state": "canceled", "filled_avg_price": "7.00", "filled_qty": "2"}
    monitor_positions(conn=convexity_db, clock=CLOCK, quote_provider=StaticQuoteProvider({}), config=CONFIG,
                      broker=broker, dry_run=False)
    # the retry sells the remaining 1 contract
    state.begin_close_convexity_position(convexity_db, pid, close_order_id="cl-2", reason="time_stop_21dte", as_of="t2")
    broker._statuses["cl-2"] = {"state": "filled", "filled_avg_price": "4.00", "filled_qty": "1"}
    monitor_positions(conn=convexity_db, clock=CLOCK, quote_provider=StaticQuoteProvider({}), config=CONFIG,
                      broker=broker, dry_run=False)
    row = _row(convexity_db, pid, "status, contracts, total_premium, realized_pnl, mark")
    assert row["status"] == "closed" and row["contracts"] == 3 and abs(row["total_premium"] - 1500.0) < 1e-9
    assert row["realized_pnl"] == (7.00 * 100 - 500.0) * 2 + (4.00 * 100 - 500.0) * 1          # $400 − $100 = $300
    assert abs(row["mark"] - (2 * 7.00 + 1 * 4.00) / 3) < 1e-9                                  # blended exit


def test_the_retry_sells_only_the_remainder_and_the_sentinel_scores_the_whole_bet(convexity_db):
    # #449 review: the retry's size at the broker surface, and the traded sentinel's multiple on the whole premium
    from broker import Fill
    sid = state.record_sentinel_candidate(convexity_db, run_id=None, as_of="2026-01-01T00:00:00+00:00", symbol="FCX",
                                          direction="bullish", basket="ai_compute", inflection_score=0.5, markers={})
    prop = state.record_council_proposal(convexity_db, run_id=None, as_of="2026-01-01T00:00:00+00:00",
                                         theme="ai_compute", symbol="FCX", direction="bullish", conviction="HIGH",
                                         sentinel_id=sid)
    state.link_sentinel_proposal(convexity_db, sid, prop)
    exp = (NOW.date() + timedelta(days=10)).isoformat()                       # ≤ 21 DTE → the time-stop re-fires
    pid = state.record_convexity_position(
        convexity_db, run_id=None, opened_at="2026-01-01T00:00:00+00:00", theme="ai_compute", symbol="FCX",
        direction="bullish", structure_kind="C", contract_symbol="FCX260611C00080000", expiry=exp, strike=80.0,
        dte=270, moneyness=0.25, contracts=3, entry_premium_per_contract=500.0, total_premium=1500.0,
        proposal_id=prop, entry_spot=60.0)
    state.begin_close_convexity_position(convexity_db, pid, close_order_id="cl-1", reason="time_stop_21dte", as_of="t")
    broker = _FakeBroker(sell=Fill(True, 4.00, 1, "filled", order_id="cl-2", pending=False))
    broker._statuses["cl-1"] = {"state": "expired", "filled_avg_price": "7.00", "filled_qty": "2"}
    monitor_positions(conn=convexity_db, clock=CLOCK, quote_provider=StaticQuoteProvider({"FCX260611C00080000": 4.0}),
                      config=CONFIG, broker=broker, dry_run=False, underlying_price_of=lambda s: 60.0)
    assert [s["qty"] for s in broker.sells] == [1]                            # the retry sells what the venue holds
    row = _row(convexity_db, pid, "status, contracts, total_premium, realized_pnl")
    assert row["status"] == "closed" and row["contracts"] == 3 and row["realized_pnl"] == 300.0
    assert abs(state.sentinel_by_id(convexity_db, sid)["realized_multiple"] - (1500.0 + 300.0) / 1500.0) < 1e-9
