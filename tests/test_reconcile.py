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
        if (self._statuses.get(oid) or {}).get("state") in ("new", "accepted", "pending_new", "partially_filled"):
            self._statuses[oid] = {"state": "canceled"}   # the real venue reports the cancel


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


def test_fill_pages(convexity_db, monkeypatch):
    # The 07-01 PL fill reconciled SILENTLY and went unnoticed for three days
    # (records/2026-07-04_first_real_entry_ERRATUM.md §3.2) — a real-book fill must page.
    import notify

    sent = []
    monkeypatch.setattr(notify, "send", lambda title, body: sent.append((title, body)))
    _pending(convexity_db, contract="FCX261218C00080000", oid="o9", contracts=2)
    broker = FakeBroker({"o9": {"state": "filled", "filled_avg_price": 3.10, "filled_qty": 2}})
    reconcile_pending(conn=convexity_db, broker=broker, clock=CLOCK, config=CONFIG)
    assert len(sent) == 1 and sent[0][0] == "REAL-BOOK FILL"
    assert "FCX261218C00080000" in sent[0][1]


def test_fill_page_failure_never_breaks_reconcile(convexity_db, monkeypatch):
    import notify

    def _boom(*a, **k):
        raise RuntimeError("pushover down")

    monkeypatch.setattr(notify, "send", _boom)
    pid = _pending(convexity_db, contract="FCX261218C00080000", oid="o10")
    broker = FakeBroker({"o10": {"state": "filled", "filled_avg_price": 3.10, "filled_qty": 1}})
    n = reconcile_pending(conn=convexity_db, broker=broker, clock=CLOCK, config=CONFIG)
    assert n == 1
    row = convexity_db.execute(
        "SELECT status FROM convexity_positions WHERE id=?", (pid,)).fetchone()
    assert row["status"] == "open"



# ── #386: a cancel is always followed by a status read ─────────────────────────────────────────────────────────

class RacingBroker(FakeBroker):
    """The order fills between the status read and the cancel: the venue then reports it filled."""

    def cancel_order(self, oid):
        self.cancelled.append(oid)
        self._statuses[oid] = {"state": "filled", "filled_avg_price": 2.05, "filled_qty": 1}


def test_a_fill_that_races_the_cancel_is_confirmed_not_dropped(convexity_db):
    pid = _pending(convexity_db, contract="FCX261218C00080000", oid="r1")
    broker = RacingBroker({"r1": {"state": "new"}})
    reconcile_pending(conn=convexity_db, broker=broker, clock=CLOCK, config=CONFIG)
    row = convexity_db.execute("SELECT status, entry_premium_per_contract FROM convexity_positions WHERE id=?",
                               (pid,)).fetchone()
    assert broker.cancelled == ["r1"] and row["status"] == "open"
    assert abs(row["entry_premium_per_contract"] - 205.0) < 1e-6


def test_an_unconfirmed_cancel_leaves_the_order_pending(convexity_db):
    class Sticky(FakeBroker):
        def cancel_order(self, oid):
            self.cancelled.append(oid)
            self._statuses[oid] = {"state": "pending_cancel"}
    pid = _pending(convexity_db, contract="FCX261218C00080000", oid="s1")
    reconcile_pending(conn=convexity_db, broker=Sticky({"s1": {"state": "new"}}), clock=CLOCK, config=CONFIG)
    assert convexity_db.execute("SELECT status FROM convexity_positions WHERE id=?", (pid,)).fetchone()[0] == "pending"
