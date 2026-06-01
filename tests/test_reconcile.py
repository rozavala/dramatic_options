"""Reconciliation of pending real orders: fill→open, terminal→cancelled, resting→cancel."""

from datetime import UTC, datetime

import state
from clock import FixedClock
from monitor import reconcile_pending

CONFIG = {"execution": {"cancel_unfilled": True}}
CLOCK = FixedClock(datetime(2026, 6, 1, tzinfo=UTC))


class FakeBroker:
    def __init__(self, statuses):
        self._statuses = statuses  # order_id -> dict
        self.cancelled = []

    def order_status(self, oid):
        return self._statuses.get(oid)

    def cancel_order(self, oid):
        self.cancelled.append(oid)


def _pending(conn, *, contract, oid, contracts=1, entry_pc=200.0):
    return state.record_convexity_position(
        conn, run_id=None, opened_at="2026-06-01T00:00:00+00:00", theme="t", symbol="FCX",
        direction="bullish", structure_kind="C", contract_symbol=contract, expiry="2026-12-18",
        strike=80.0, dte=270, moneyness=0.25, contracts=contracts,
        entry_premium_per_contract=entry_pc, total_premium=entry_pc * contracts,
        status="pending", order_id=oid,
    )


def test_fill_confirms_open(convexity_db):
    pid = _pending(convexity_db, contract="FCX261218C00080000", oid="o1", contracts=2)
    broker = FakeBroker({"o1": {"state": "filled", "filled_avg_price": 3.10, "filled_qty": 2}})
    n = reconcile_pending(conn=convexity_db, broker=broker, clock=CLOCK, config=CONFIG)
    assert n == 1
    row = convexity_db.execute("SELECT status, entry_premium_per_contract, total_premium FROM convexity_positions WHERE id=?", (pid,)).fetchone()
    assert row["status"] == "open"
    assert row["entry_premium_per_contract"] == 310.0  # 3.10 × 100
    assert row["total_premium"] == 620.0


def test_terminal_status_drops(convexity_db):
    pid = _pending(convexity_db, contract="FCX261218C00080000", oid="o2")
    broker = FakeBroker({"o2": {"state": "rejected"}})
    n = reconcile_pending(conn=convexity_db, broker=broker, clock=CLOCK, config=CONFIG)
    assert n == 1
    row = convexity_db.execute("SELECT status FROM convexity_positions WHERE id=?", (pid,)).fetchone()
    assert row["status"] == "cancelled"


def test_resting_order_cancelled_when_configured(convexity_db):
    pid = _pending(convexity_db, contract="FCX261218C00080000", oid="o3")
    broker = FakeBroker({"o3": {"state": "new"}})
    n = reconcile_pending(conn=convexity_db, broker=broker, clock=CLOCK, config=CONFIG)
    assert n == 1 and broker.cancelled == ["o3"]
    row = convexity_db.execute("SELECT status FROM convexity_positions WHERE id=?", (pid,)).fetchone()
    assert row["status"] == "cancelled"


def test_no_status_left_pending(convexity_db):
    pid = _pending(convexity_db, contract="FCX261218C00080000", oid="o4")
    broker = FakeBroker({})  # order_status returns None
    n = reconcile_pending(conn=convexity_db, broker=broker, clock=CLOCK, config=CONFIG)
    assert n == 0
    row = convexity_db.execute("SELECT status FROM convexity_positions WHERE id=?", (pid,)).fetchone()
    assert row["status"] == "pending"


def test_broker_without_status_surface_is_noop(convexity_db):
    _pending(convexity_db, contract="FCX261218C00080000", oid="o5")
    n = reconcile_pending(conn=convexity_db, broker=object(), clock=CLOCK, config=CONFIG)
    assert n == 0
