"""#451: a closed-market L2 tick outside DRY_RUN is MARK-ONLY — a triggered exit is deferred, never booked unsold.

On main the orchestrator ran the closed-market monitor with ``dry_run`` forced, and the monitor's DRY_RUN path books
every triggered profit-take / time-stop in the journal at the mark with no sell, so the journal said "closed" while
the contract stayed at the broker. Every real time-stop is first seen on the 09:00 ET (pre-market) tick. These tests
drive the orchestrator's own mode decision (``monitor_mode``) into the real ``monitor_positions``."""

from datetime import UTC, datetime, timedelta

import orchestrator
import state
from broker import Fill, PaperBroker
from clock import FixedClock
from convexity_data import StaticQuoteProvider
from monitor import monitor_positions
from tests.test_monitor import CONFIG, NOW, _FakeBroker, _open, _row

CLOSED = FixedClock(NOW, market_open=False)
OPEN = FixedClock(NOW + timedelta(minutes=30), market_open=True)
TS_EXP = (NOW.date() + timedelta(days=10)).isoformat()        # ≤ 21 DTE → time-stop
TS_CONTRACT = "FCX260611C00080000"


def _tick(conn, clock, qp, broker, *, dry_run=False, demo=False, **kw):
    """One L2 monitor pass, wired as the orchestrator wires it."""
    mdry, mark_only = orchestrator.monitor_mode(dry_run=dry_run, market_open=orchestrator._safe_market_open(clock),
                                                demo=demo)
    return monitor_positions(conn=conn, clock=clock, quote_provider=qp, config=CONFIG, broker=broker,
                             dry_run=mdry, mark_only=mark_only, underlying_price_of=lambda s: 100.0, **kw)


def _ts_qp(bid=1.9):
    return StaticQuoteProvider({TS_CONTRACT: 2.0}, bids={TS_CONTRACT: bid})


def test_closed_tick_leaves_a_triggered_time_stop_open_with_no_sell(convexity_db):
    pid = _open(convexity_db, contract=TS_CONTRACT, entry_pc=200.0, expiry=TS_EXP)
    broker = _FakeBroker()
    res = _tick(convexity_db, CLOSED, _ts_qp(), broker)
    assert broker.sells == []
    row = _row(convexity_db, pid, "status, mark, exit_reason, realized_pnl")
    assert row["status"] == "open", "a closed-market time-stop was booked in the journal without a sale"
    assert row["mark"] == 2.0 and row["exit_reason"] is None and row["realized_pnl"] is None
    assert res.marked == 1 and res.deferred == 1 and res.closed == 0 and res.time_stopped == 0


def test_the_next_open_market_tick_submits_the_deferred_time_stop(convexity_db):
    pid = _open(convexity_db, contract=TS_CONTRACT, entry_pc=200.0, expiry=TS_EXP)
    broker = _FakeBroker()
    _tick(convexity_db, CLOSED, _ts_qp(), broker)
    res = _tick(convexity_db, OPEN, _ts_qp(), broker)
    assert len(broker.sells) == 1 and broker.sells[0]["side"] == "sell" and broker.sells[0]["limit"] == 1.9
    assert res.time_stopped == 1 and res.closing == 1 and res.deferred == 0
    row = _row(convexity_db, pid, "status, close_order_id, exit_reason")
    assert row["status"] == "closing" and row["close_order_id"] == "cl-1" and row["exit_reason"].startswith("time_stop")


def test_closed_tick_defers_a_profit_take_then_the_open_tick_sells_it(convexity_db):
    contract = "FCX261218C00080000"
    pid = _open(convexity_db, contract=contract, entry_pc=200.0)          # $900 ≥ 4× $200 → profit-take
    qp = StaticQuoteProvider({contract: 9.0}, bids={contract: 8.9})
    broker = _FakeBroker(sell=Fill(True, 8.9, 1, "filled", order_id="cl-2", pending=False))
    res = _tick(convexity_db, CLOSED, qp, broker)
    assert _row(convexity_db, pid, "status")["status"] == "open", "a closed-market profit-take was booked unsold"
    assert broker.sells == [] and res.deferred == 1 and res.profit_taken == 0
    res = _tick(convexity_db, OPEN, qp, broker)
    assert len(broker.sells) == 1 and res.profit_taken == 1 and res.closed == 1
    row = _row(convexity_db, pid, "status, realized_pnl, exit_reason")
    assert row["status"] == "closed" and row["realized_pnl"] == (8.9 * 100 - 200.0)   # the fill, not the mark
    assert row["exit_reason"].startswith("profit_take")


def test_closed_tick_defers_an_unsellable_time_stop_too(convexity_db):
    # the bid-below-min_close_bid branch books in-DB at the mark on an open tick; on a closed tick it waits as well
    pid = _open(convexity_db, contract=TS_CONTRACT, entry_pc=500.0, expiry=TS_EXP)
    broker = _FakeBroker()
    res = _tick(convexity_db, CLOSED, _ts_qp(bid=0.0), broker)
    assert _row(convexity_db, pid, "status")["status"] == "open", "a closed-market unsellable exit was booked"
    assert res.deferred == 1
    _tick(convexity_db, OPEN, _ts_qp(bid=0.0), broker)
    row = _row(convexity_db, pid, "status, exit_reason")
    assert broker.sells == [] and row["status"] == "closed" and "unsellable" in row["exit_reason"]


def test_dry_run_still_books_the_exit_in_db_on_a_closed_tick(convexity_db):
    pid = _open(convexity_db, contract=TS_CONTRACT, entry_pc=200.0, expiry=TS_EXP)
    broker = _FakeBroker()
    res = _tick(convexity_db, CLOSED, _ts_qp(), broker, dry_run=True)
    assert broker.sells == [] and res.deferred == 0 and res.time_stopped == 1 and res.closed == 1
    row = _row(convexity_db, pid, "status, exit_reason")
    assert row["status"] == "closed" and row["exit_reason"].startswith("time_stop")


def test_demo_still_books_the_exit_in_db(convexity_db):
    # the demo's FixedClock always reads closed; it is an offline simulation with a PaperBroker, as before
    pid = _open(convexity_db, contract=TS_CONTRACT, entry_pc=200.0, expiry=TS_EXP)
    res = _tick(convexity_db, CLOSED, _ts_qp(), PaperBroker(100_000.0), demo=True)
    assert res.deferred == 0 and _row(convexity_db, pid, "status")["status"] == "closed"


def test_expiry_still_settles_at_intrinsic_on_a_closed_tick(convexity_db):
    exp = (NOW.date() - timedelta(days=1)).isoformat()
    pid = _open(convexity_db, contract="FCX260531C00080000", entry_pc=200.0, expiry=exp, strike=80.0)
    broker = _FakeBroker()
    res = _tick(convexity_db, CLOSED, StaticQuoteProvider({}), broker)
    assert broker.sells == [] and res.expired == 1 and res.closed == 1 and res.deferred == 0
    row = _row(convexity_db, pid, "status, mark, exit_reason")
    assert row["status"] == "closed" and row["exit_reason"] == "expiry" and row["mark"] == 20.0   # 100 − 80


def test_a_resting_close_is_not_reconciled_on_a_closed_tick(convexity_db):
    # unchanged from main: _reconcile_closing needs a real submit, so a closed tick leaves 'closing' rows to the next
    # open-market tick (no order-status read, no cancel)
    pid = _open(convexity_db, contract="FCX261218C00080000", entry_pc=200.0)
    state.begin_close_convexity_position(convexity_db, pid, close_order_id="cl-1", reason="profit_take_4x", as_of="t")
    broker = _FakeBroker()
    broker._statuses["cl-1"] = {"state": "filled", "filled_avg_price": "8.50"}
    _tick(convexity_db, CLOSED, StaticQuoteProvider({}), broker)
    assert _row(convexity_db, pid, "status")["status"] == "closing" and broker.cancelled == []
    _tick(convexity_db, OPEN, StaticQuoteProvider({}), broker)
    assert _row(convexity_db, pid, "status")["status"] == "closed"


class _RaisingClock:
    def now(self):
        return NOW

    def is_market_open(self):
        raise RuntimeError("alpaca clock unreachable")


def test_a_failed_clock_read_neither_sells_nor_books(convexity_db):
    pid = _open(convexity_db, contract=TS_CONTRACT, entry_pc=200.0, expiry=TS_EXP)
    broker = _FakeBroker()
    res = _tick(convexity_db, _RaisingClock(), _ts_qp(), broker)
    assert _row(convexity_db, pid, "status")["status"] == "open", "an unconfirmed market state booked an exit unsold"
    assert broker.sells == [] and res.deferred == 1


def test_monitor_mode_table():
    m = orchestrator.monitor_mode
    assert m(dry_run=False, market_open=True, demo=False) == (False, False)    # open: real exits
    assert m(dry_run=True, market_open=True, demo=False) == (True, False)      # DRY_RUN: simulated exits
    assert m(dry_run=False, market_open=False, demo=False) == (True, True)     # closed: no transmit, no booking
    assert m(dry_run=True, market_open=False, demo=False) == (True, False)     # closed DRY_RUN: books in-DB, as before
    assert m(dry_run=False, market_open=False, demo=True) == (True, False)     # demo: as before


def test_closed_tick_defers_a_vertical_then_the_open_tick_closes_it_in_one_order(convexity_db, monkeypatch):
    from tests.test_vertical_order_path import EXP, OverCapProvider, _cycle, _no_kill, _on

    _no_kill(monkeypatch)
    p = OverCapProvider()
    _cycle(convexity_db, _on(), provider=p)

    class Rec(PaperBroker):
        def __init__(self):
            super().__init__(100_000.0)
            self.spreads = []

        def submit_spread(self, **kw):
            self.spreads.append(kw)
            return super().submit_spread(**kw)

        def submit_paper(self, **kw):
            raise AssertionError("a vertical close must never be legged")
    b = Rec()
    late = datetime.combine(EXP - timedelta(days=10), datetime.min.time(), UTC)      # ≤ 21 DTE → time-stop
    for clock in (FixedClock(late, market_open=False), FixedClock(late + timedelta(minutes=30), market_open=True)):
        mdry, mark_only = orchestrator.monitor_mode(dry_run=False, market_open=clock.is_market_open(), demo=False)
        res = monitor_positions(conn=convexity_db, clock=clock, quote_provider=p, config=_on(), broker=b,
                                dry_run=mdry, mark_only=mark_only, underlying_price_of=lambda s: 100.0)
        r = convexity_db.execute("SELECT status, exit_reason FROM convexity_positions "
                                 "WHERE status != 'cancelled'").fetchone()
        if not clock.is_market_open():
            assert r["status"] == "open", "a closed-market vertical time-stop was booked without a sale"
            assert b.spreads == [] and res.deferred == 1
    assert len(b.spreads) == 1 and b.spreads[0]["action"] == "close"
    assert r["status"] == "closed" and r["exit_reason"].startswith("time_stop")


def test_run_once_wires_monitor_mode_into_the_monitor_pass():
    # #451 review: the tests above drive monitor_mode themselves; this pins that run_once really uses it
    import inspect
    src = inspect.getsource(orchestrator.run_once)
    assert "dry_run=dry_run or not market_open" not in src, "run_once still forces dry_run without mark_only"
    assert "monitor_dry_run, mark_only = monitor_mode(dry_run=dry_run, market_open=market_open, demo=demo)" in src
    call = src[src.index("mres = monitor_positions("):]
    call = call[:call.index(")\n")]
    assert "dry_run=monitor_dry_run" in call and "mark_only=mark_only" in call
    assert src.index("market_open = _safe_market_open(clock)") < src.index("monitor_mode(") < src.index(
        "mres = monitor_positions(")


def test_mark_only_alone_transmits_nothing_and_skips_the_closing_reconcile(convexity_db, monkeypatch):
    # #451 review: mark_only blocks real submits even if a caller passes dry_run=False — no sell, and no
    # _reconcile_closing (no order-status read, no cancel) — on a real-shaped (non-dry) Alpaca paper broker
    from tests.test_broker import _broker

    b, fake = _broker(monkeypatch, dry_run=False)
    calls = []
    for name in ("submit_paper", "submit_spread", "order_status", "cancel_order"):
        real = getattr(b, name)
        monkeypatch.setattr(b, name, lambda *a, _n=name, _r=real, **k: calls.append(_n) or _r(*a, **k))
    ts = _open(convexity_db, contract=TS_CONTRACT, entry_pc=200.0, expiry=TS_EXP)
    closing = _open(convexity_db, contract="FCX261218C00080000", entry_pc=200.0)
    state.begin_close_convexity_position(convexity_db, closing, close_order_id="cl-1", reason="profit_take_4x",
                                         as_of="t")
    res = monitor_positions(conn=convexity_db, clock=CLOSED, quote_provider=_ts_qp(), config=CONFIG, broker=b,
                            dry_run=False, mark_only=True, underlying_price_of=lambda s: 100.0)
    assert calls == [] and fake.submitted == [] and fake.cancelled == [], \
        "mark_only with dry_run=False still reached the broker"
    assert _row(convexity_db, ts, "status")["status"] == "open" and res.deferred == 1
    assert _row(convexity_db, closing, "status")["status"] == "closing"
