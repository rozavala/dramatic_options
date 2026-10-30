"""#389 (operator word 2026-10-29, option a): under the KILL switch, cancel this project's own resting ENTRY orders
so nothing new can fill after a kill. Exits are never touched, and the halt holds whatever happens."""
from __future__ import annotations

import pytest

import orchestrator
import state


class Venue:
    def __init__(self, orders):
        self.orders, self.cancelled = orders, []

    def order_status(self, oid):
        return self.orders.get(oid)

    def cancel_order(self, oid):
        self.cancelled.append(oid)
        o = self.orders.get(oid, {})
        if o.get("state") in ("new", "partially_filled"):
            self.orders[oid] = {**o, "state": "canceled"}


def _row(conn, *, status, oid=None, close_oid=None, contracts=3, rationale=None):
    pid = state.record_convexity_position(
        conn, run_id=None, opened_at="2026-10-30T19:48:00+00:00", theme="t", symbol="AG", direction="bullish",
        structure_kind="C", contract_symbol="AG270617C00020000", expiry="2027-06-17", strike=20.0, dte=230,
        moneyness=0.2, contracts=contracts, entry_premium_per_contract=148.0, total_premium=148.0 * contracts,
        status=status, order_id=oid, rationale=rationale or {})
    if close_oid:
        conn.execute("UPDATE convexity_positions SET close_order_id=? WHERE id=?", (close_oid, pid))
        conn.commit()
    return pid


@pytest.fixture
def kill(convexity_db, monkeypatch):
    import notify
    path = convexity_db.execute("PRAGMA database_list").fetchone()[2]
    pages = []
    monkeypatch.setattr(notify, "send", lambda *a, **k: pages.append((a, k)))
    monkeypatch.setattr(orchestrator, "kill_switch_active", lambda: True)
    monkeypatch.setattr(orchestrator, "load_config", lambda: {"safety": {"dry_run": False}})
    monkeypatch.setattr(orchestrator, "get_db", lambda cfg: state.connect(path))
    monkeypatch.setattr(orchestrator, "require_alpaca_credentials", lambda cfg: ("k", "s"))
    venue = Venue({})
    monkeypatch.setattr(orchestrator, "_select_broker", lambda cfg, **kw: venue)
    return convexity_db, venue, pages


def _status(conn, pid):
    return conn.execute("SELECT status, exit_reason, contracts FROM convexity_positions WHERE id=?", (pid,)).fetchone()


def test_kill_cancels_resting_entries_and_still_halts(kill):
    conn, venue, pages = kill
    pid = _row(conn, status="pending", oid="o1")
    venue.orders["o1"] = {"state": "new"}
    assert orchestrator.run_once() == 0
    assert venue.cancelled == ["o1"] and tuple(_status(conn, pid))[:2] == ("cancelled", "kill_cancelled")
    assert pages and pages[0][0][0] == "KILL: resting entry orders cancelled" and pages[0][1] == {"priority": 1}


def test_a_fill_found_at_the_kill_cancel_is_kept(kill):
    conn, venue, _ = kill
    pid = _row(conn, status="pending", oid="o2")
    venue.orders["o2"] = {"state": "partially_filled", "filled_qty": "2", "filled_avg_price": 1.5}
    orchestrator.run_once()
    r = _status(conn, pid)
    assert r["status"] == "open" and r["contracts"] == 2


def test_an_exit_order_is_never_touched(kill):
    conn, venue, _ = kill
    pid = _row(conn, status="closing", oid="o3", close_oid="c3")
    venue.orders["c3"] = {"state": "new"}
    orchestrator.run_once()
    assert venue.cancelled == [] and _status(conn, pid)["status"] == "closing"


def test_carry_intents_end_and_an_unconfirmed_cancel_is_left_for_the_next_tick(kill):
    conn, venue, _ = kill
    intent = _row(conn, status="carried", rationale={"carry_intent": {"day": "2026-11-02"}})
    stuck = _row(conn, status="pending", oid="o4", rationale={"carry": {"of": intent, "step": 1}})
    venue.orders["o4"] = {"state": "pending_cancel"}
    orchestrator.run_once()
    assert tuple(_status(conn, intent))[:2] == ("cancelled", "kill_cancelled")
    assert _status(conn, stuck)["status"] == "pending"            # not dropped while it may still be live


def test_demo_and_an_empty_journal_do_nothing(kill, monkeypatch):
    conn, venue, pages = kill
    assert orchestrator._cancel_resting_entries_on_kill(False, demo=True) == 0
    monkeypatch.setattr(orchestrator, "_select_broker", lambda *a, **k: pytest.fail("no broker needed"))
    assert orchestrator._cancel_resting_entries_on_kill(False, demo=False) == 0 and pages == []


def test_an_error_never_breaks_the_halt(kill, monkeypatch):
    conn, venue, _ = kill
    _row(conn, status="pending", oid="o5")

    def boom(cfg):
        raise RuntimeError("no keys")
    monkeypatch.setattr(orchestrator, "require_alpaca_credentials", boom)
    assert orchestrator.run_once() == 0                           # KILL still halts, nothing raised
