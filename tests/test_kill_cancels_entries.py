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
    assert pages and pages[0][0][0] == "KILL: resting entry orders" and pages[0][1] == {"priority": 1}
    assert "cancelled 1" in pages[0][0][1]


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


def test_an_intent_outlives_kill_ticks_until_its_attempt_is_confirmed_cancelled(kill):
    # #391 review (HIGH): ending the intent first orphaned an unconfirmed attempt once KILL was lifted
    conn, venue, pages = kill
    intent = _row(conn, status="carried", rationale={"carry_intent": {"day": "2026-11-02"}})
    att = _row(conn, status="pending", oid="o4", rationale={"carry": {"of": intent, "step": 1}})
    venue.orders["o4"] = {"state": "pending_cancel"}
    orchestrator.run_once()
    assert _status(conn, intent)["status"] == "carried" and _status(conn, att)["status"] == "pending"
    assert pages and "UNCONFIRMED 1" in pages[0][0][1]            # an unconfirmed cancel is never silent
    import json
    assert json.loads(conn.execute("SELECT rationale FROM convexity_positions WHERE id=?",
                                   (intent,)).fetchone()[0])["carry_intent"]["killed"] is True
    venue.orders["o4"] = {"state": "canceled"}                     # the next tick confirms it
    orchestrator.run_once()
    assert tuple(_status(conn, att))[:2] == ("cancelled", "kill_cancelled")
    assert tuple(_status(conn, intent))[:2] == ("cancelled", "kill_cancelled")


def test_an_intent_with_no_attempt_ends_at_once(kill):
    conn, _, _ = kill
    intent = _row(conn, status="carried", rationale={"carry_intent": {"day": "2026-11-02"}})
    orchestrator.run_once()
    assert tuple(_status(conn, intent))[:2] == ("cancelled", "kill_cancelled")


def test_a_credentials_error_changes_nothing(kill, monkeypatch):
    conn, venue, _ = kill
    intent = _row(conn, status="carried", rationale={"carry_intent": {"day": "2026-11-02"}})
    att = _row(conn, status="pending", oid="o6", rationale={"carry": {"of": intent, "step": 0}})

    def boom(cfg):
        raise RuntimeError("no keys")
    monkeypatch.setattr(orchestrator, "require_alpaca_credentials", boom)
    assert orchestrator.run_once() == 0
    assert _status(conn, intent)["status"] == "carried" and _status(conn, att)["status"] == "pending"


def test_an_order_on_the_other_venue_is_never_sent_to_the_wrong_endpoint(kill):
    conn, venue, pages = kill
    run_id = state.record_run(conn, mode="LIVE", equity=10000.0, note="t")
    pid = _row(conn, status="pending", oid="o7")
    conn.execute("UPDATE convexity_positions SET run_id=? WHERE id=?", (run_id, pid))
    conn.commit()
    venue.orders["o7"] = {"state": "new"}
    orchestrator.run_once()                                        # config is paper (live_allowed False)
    assert venue.cancelled == [] and _status(conn, pid)["status"] == "pending"
    assert pages and "another venue" in pages[0][0][0] and "o7" in pages[0][0][1]


def test_reconcile_settles_an_attempt_whose_intent_has_ended(convexity_db):
    # the orphan defense: an attempt is the carry worker's only while its intent is alive
    from datetime import UTC, datetime

    from clock import FixedClock
    from monitor import reconcile_pending
    intent = _row(convexity_db, status="cancelled", rationale={"carry_intent": {"day": "2026-11-02"}})
    att = _row(convexity_db, status="pending", oid="o8", rationale={"carry": {"of": intent, "step": 2}})
    venue = Venue({"o8": {"state": "new"}})
    cfg = {"execution": {"cancel_unfilled": True, "carry_unfilled": True}}
    reconcile_pending(conn=convexity_db, broker=venue, clock=FixedClock(datetime(2026, 11, 2, 18, tzinfo=UTC)),
                      config=cfg)
    assert venue.cancelled == ["o8"] and _status(convexity_db, att)["status"] == "cancelled"


def test_demo_and_an_empty_journal_do_nothing(kill, monkeypatch):
    conn, venue, pages = kill
    pid = _row(conn, status="pending", oid="o9")
    venue.orders["o9"] = {"state": "new"}
    assert orchestrator._cancel_resting_entries_on_kill(False, demo=True) == 0
    assert venue.cancelled == [] and _status(conn, pid)["status"] == "pending"   # the demo guard matters
    conn.execute("DELETE FROM convexity_positions")
    conn.commit()
    monkeypatch.setattr(orchestrator, "_select_broker", lambda *a, **k: pytest.fail("no broker needed"))
    assert orchestrator._cancel_resting_entries_on_kill(False, demo=False) == 0 and pages == []


def test_an_error_never_breaks_the_halt(kill, monkeypatch):
    conn, venue, _ = kill
    _row(conn, status="pending", oid="o5")

    def boom(cfg):
        raise RuntimeError("no keys")
    monkeypatch.setattr(orchestrator, "require_alpaca_credentials", boom)
    assert orchestrator.run_once() == 0                           # KILL still halts, nothing raised



def test_a_killed_intent_never_places_a_new_attempt_after_kill_is_lifted(kill, monkeypatch):
    # #391 re-review: KILL lifted before the next tick — the carry worker must wind the intent down, not resume it
    from datetime import UTC, datetime

    import carry
    from clock import FixedClock
    from monitor import reconcile_pending
    conn, venue, _ = kill
    intent = _row(conn, status="carried",
                  rationale={"carry_intent": {"day": "2026-11-02", "start": "2026-11-02T15:00:00+00:00",
                                              "until": "2026-11-02T20:30:00+00:00"}})
    att = _row(conn, status="pending", oid="a1", rationale={"carry": {"of": intent, "step": 1}})
    venue.orders["a1"] = {"state": "pending_cancel"}
    orchestrator.run_once()                                        # KILL: cancel unconfirmed → intent marked killed
    venue.orders["a1"] = {"state": "canceled"}                     # KILL lifted; the cancel lands
    cfg = {"execution": {"cancel_unfilled": True, "carry_unfilled": True}, "forward_enabled": True}
    clock = FixedClock(datetime(2026, 11, 2, 17, 0, tzinfo=UTC))   # 12:00 ET, inside the window
    reconcile_pending(conn=conn, broker=venue, clock=clock, config=cfg)
    placed = carry.work_carried(conn, config=cfg, clock=clock, provider=None, broker=venue, run_id=None,
                                market_open=True, entries_ok=True)
    assert placed == 0
    assert tuple(_status(conn, intent))[:2] == ("cancelled", "kill_cancelled")
    assert _status(conn, att)["status"] == "cancelled"


def test_a_fill_found_under_kill_ends_its_intent_as_filled(kill):
    conn, venue, _ = kill
    intent = _row(conn, status="carried", rationale={"carry_intent": {"day": "2026-11-02"}})
    att = _row(conn, status="pending", oid="f1", rationale={"carry": {"of": intent, "step": 2}})
    venue.orders["f1"] = {"state": "filled", "filled_qty": "3", "filled_avg_price": 1.5}
    orchestrator.run_once()
    assert _status(conn, att)["status"] == "open"
    assert tuple(_status(conn, intent))[:2] == ("cancelled", "carry_filled")


def test_a_matching_venue_row_with_a_real_run_is_cancelled(kill):
    conn, venue, _ = kill
    run_id = state.record_run(conn, mode="PAPER", equity=100000.0, note="t")
    pid = _row(conn, status="pending", oid="m1")
    conn.execute("UPDATE convexity_positions SET run_id=? WHERE id=?", (run_id, pid))
    conn.commit()
    venue.orders["m1"] = {"state": "new"}
    orchestrator.run_once()
    assert venue.cancelled == ["m1"] and tuple(_status(conn, pid))[:2] == ("cancelled", "kill_cancelled")
