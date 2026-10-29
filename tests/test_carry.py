"""#386 carry-over: an L1 entry unfilled at the close is re-gated and resubmitted the next session, walking from
mid to the ask, through the same run_paper_cycle pipeline as an L1 entry, and cancelled at 15:30 ET."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

import carry
import paper_loop
import risk
import state
from broker import Fill, PaperBroker
from clock import FixedClock
from convexity_data import SyntheticChainProvider
from monitor import reconcile_pending
from themes import Theme

ET_OFF = {"EDT": "-04:00", "EST": "-05:00"}


def _utc(et_iso: str) -> datetime:
    return datetime.fromisoformat(et_iso).astimezone(UTC)


CFG = {"convexity_book": {"account_equity": 100_000.0, "book_fraction": 0.10, "per_name_fraction": 0.01,
                          "max_open_positions": 15},
       "convexity_gate": {"iv_rv_max": 1.2, "otm_skew_max_volpts": 10.0, "rv_window_days": 252,
                          "tenor_min_days": 180, "tenor_max_days": 365, "target_moneyness": 0.25},
       "eligibility": {"live": {"min_option_open_interest": 50, "max_bid_ask_pct": 0.25}},
       "kill_rule": {"book_drawdown_halt": 0.20, "dry_months_halt": 9},
       "execution": {"cancel_unfilled": True, "carry_unfilled": True}}


class Venue(PaperBroker):
    """A real venue's shape: limits rest (pending) until the test fills them; a cancel is reported back."""

    def __init__(self):
        super().__init__(100_000.0)
        self.orders: dict[str, dict] = {}
        self.submitted: list[dict] = []
        self.cancelled: list[str] = []

    def submit_paper(self, *, contract_symbol, qty, side, limit_price, client_order_id=None):
        oid = f"o{len(self.submitted) + 1}"
        self.submitted.append({"oid": oid, "contract": contract_symbol, "qty": qty, "limit": round(limit_price, 2),
                               "coid": client_order_id})
        self.orders[oid] = {"state": "new"}
        return Fill(True, float(limit_price), int(qty), "SUBMITTED (resting)", order_id=oid, pending=True)

    def order_status(self, oid):
        return self.orders.get(oid)

    def cancel_order(self, oid):
        self.cancelled.append(oid)
        if self.orders.get(oid, {}).get("state") == "new":
            self.orders[oid] = {"state": "canceled"}

    def fill(self, oid, px):
        self.orders[oid] = {"state": "filled", "filled_avg_price": px, "filled_qty": 1}


@pytest.fixture
def env(convexity_db, monkeypatch):
    import notify
    monkeypatch.delenv("KILL", raising=False)
    monkeypatch.setattr(risk, "KILL_FILE", Path("/nonexistent/KILL"))
    pages: list[tuple] = []
    monkeypatch.setattr(notify, "send", lambda *a, **k: pages.append(a))
    return convexity_db, Venue(), pages


def _l1_entry(conn, venue, at_et="2026-01-02T15:45:00-05:00"):
    clock = FixedClock(_utc(at_et))
    res = paper_loop.run_paper_cycle(config=CFG, conn=conn, clock=clock,
                                     provider=SyntheticChainProvider(as_of=clock.now().date()), broker=venue,
                                     themes=[Theme("copper", "FCX", "bullish", "cheap")], run_id=None)
    assert res.opened == 1
    return conn.execute("SELECT * FROM convexity_positions ORDER BY id DESC LIMIT 1").fetchone()


def _tick(conn, venue, at_et, *, market_open=True, entries_ok=True):
    clock = FixedClock(_utc(at_et))
    reconcile_pending(conn=conn, broker=venue, clock=clock, config=CFG)
    return carry.work_carried(conn, config=CFG, clock=clock, provider=SyntheticChainProvider(as_of=clock.now().date()),
                              broker=venue, run_id=None, market_open=market_open, entries_ok=entries_ok)


def _row(conn, pid):
    return conn.execute("SELECT * FROM convexity_positions WHERE id=?", (pid,)).fetchone()


# ── the window ─────────────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("opened_et, day, start_et, until_et", [
    ("2026-10-29T15:48:00-04:00", "2026-10-30", "10:00", "15:30"),    # Thu → Fri (EDT)
    ("2026-10-30T15:48:00-04:00", "2026-11-02", "10:00", "15:30"),    # Fri → Mon, across the fall-back
    ("2026-11-25T15:48:00-05:00", "2026-11-27", "10:00", "12:30"),    # Thanksgiving skipped; half day ends 12:30
    ("2026-12-24T12:00:00-05:00", "2026-12-28", "10:00", "15:30"),    # Christmas + weekend skipped
])
def test_the_window_is_the_next_trading_day_and_half_days_end_early(opened_et, day, start_et, until_et):
    w = carry.window(opened_et, carry.settings(CFG))
    assert w["day"] == day
    assert datetime.fromisoformat(w["start"]).astimezone(carry._ET).strftime("%H:%M") == start_et
    assert datetime.fromisoformat(w["until"]).astimezone(carry._ET).strftime("%H:%M") == until_et


# ── the 16:00 reconcile turns an unfilled L1 entry into an intent ──────────────────────────────────────────────

def test_an_unfilled_l1_entry_becomes_a_carry_intent_not_a_drop(env):
    conn, venue, pages = env
    entry = _l1_entry(conn, venue)
    _tick(conn, venue, "2026-01-02T16:00:05-05:00", market_open=False, entries_ok=False)
    row = _row(conn, entry["id"])
    assert row["status"] == "carried" and venue.cancelled == ["o1"]
    intent = json.loads(row["rationale"])["carry_intent"]
    assert intent["day"] == "2026-01-05" and intent["l1_order_id"] == "o1"
    assert any(p[0] == "REAL-BOOK ORDER CARRIED" for p in pages)
    assert state.count_committed_positions(conn) == 0      # an intent holds no order and no exposure


def test_with_the_switch_off_the_entry_is_dropped_as_before(env):
    conn, venue, _ = env
    entry = _l1_entry(conn, venue)
    off = {**CFG, "execution": {"cancel_unfilled": True, "carry_unfilled": False}}
    reconcile_pending(conn=conn, broker=venue, clock=FixedClock(_utc("2026-01-02T16:00:05-05:00")), config=off)
    row = _row(conn, entry["id"])
    assert row["status"] == "cancelled" and row["exit_reason"] == "cancelled_unfilled"


def test_an_expired_day_order_is_carried_too(env):
    conn, venue, _ = env
    entry = _l1_entry(conn, venue)
    venue.orders["o1"] = {"state": "expired"}
    _tick(conn, venue, "2026-01-02T16:30:05-05:00", market_open=False, entries_ok=False)
    assert _row(conn, entry["id"])["status"] == "carried"


# ── the next session: re-gate, walk to the ask, lapse at 15:30 ───────────────────────────────────────────────

def test_the_walk_from_mid_to_the_ask_then_the_lapse(env):
    conn, venue, pages = env
    entry = _l1_entry(conn, venue)
    _tick(conn, venue, "2026-01-02T16:00:05-05:00", market_open=False, entries_ok=False)
    assert _tick(conn, venue, "2026-01-05T09:30:05-05:00") == 0                 # before 10:00: nothing
    assert _tick(conn, venue, "2026-01-05T10:00:05-05:00") == 1                 # step 0 at mid
    a0 = venue.submitted[-1]
    # re-selected on the fresh chain (the synthetic chain's expiries move with its date; a real chain's don't)
    assert a0["coid"].endswith("-c0") and a0["contract"].startswith("FCX") and "C" in a0["contract"][3:]
    assert _tick(conn, venue, "2026-01-05T10:30:05-05:00") == 0                 # step 0 still working
    assert _tick(conn, venue, "2026-01-05T11:00:05-05:00") == 1                 # step 1 replaces step 0
    assert venue.cancelled[-1] == a0["oid"] and venue.submitted[-1]["coid"].endswith("-c1")
    _tick(conn, venue, "2026-01-05T12:00:05-05:00")
    _tick(conn, venue, "2026-01-05T13:00:05-05:00")                             # step 3 = the ask
    _tick(conn, venue, "2026-01-05T14:00:05-05:00")                             # capped at 3: no new order
    limits = [s["limit"] for s in venue.submitted[1:]]
    assert len(limits) == 4 and limits == sorted(limits) and limits[0] < limits[-1]
    chain = SyntheticChainProvider(as_of=datetime(2026, 1, 5).date()).chain("FCX")
    ask = next(c.ask for c in chain if c.symbol == venue.submitted[-1]["contract"])
    assert limits[-1] == pytest.approx(ask) and all(x <= ask + 1e-9 for x in limits)
    _tick(conn, venue, "2026-01-05T15:30:05-05:00")                             # the cancel time
    intent = _row(conn, entry["id"])
    assert intent["status"] == "cancelled" and intent["exit_reason"] == "carry_lapsed"
    assert state.count_committed_positions(conn) == 0
    assert any(p[0] == "REAL-BOOK ORDER NOT FILLED" and "carry lapsed" in p[1] for p in pages)


def test_a_fill_during_the_walk_opens_the_position_and_ends_the_intent(env):
    conn, venue, pages = env
    entry = _l1_entry(conn, venue)
    _tick(conn, venue, "2026-01-02T16:00:05-05:00", market_open=False, entries_ok=False)
    _tick(conn, venue, "2026-01-05T10:00:05-05:00")
    venue.fill(venue.submitted[-1]["oid"], 2.0)
    _tick(conn, venue, "2026-01-05T10:30:05-05:00")
    assert conn.execute("SELECT COUNT(*) FROM convexity_positions WHERE status='open'").fetchone()[0] == 1
    assert _row(conn, entry["id"])["exit_reason"] == "carry_filled"
    assert any(p[0] == "REAL-BOOK FILL" for p in pages)


def test_a_fill_that_races_a_step_cancel_is_kept(env):
    conn, venue, _ = env
    entry = _l1_entry(conn, venue)
    _tick(conn, venue, "2026-01-02T16:00:05-05:00", market_open=False, entries_ok=False)
    _tick(conn, venue, "2026-01-05T10:00:05-05:00")
    oid = venue.submitted[-1]["oid"]
    real_cancel = venue.cancel_order

    def racing_cancel(o):
        real_cancel(o)
        venue.fill(o, 2.1)   # it filled just before the cancel arrived
    venue.cancel_order = racing_cancel
    n_before = len(venue.submitted)
    _tick(conn, venue, "2026-01-05T11:00:05-05:00")
    assert len(venue.submitted) == n_before                                     # no second order
    assert conn.execute("SELECT COUNT(*) FROM convexity_positions WHERE status='open'").fetchone()[0] == 1
    assert _row(conn, entry["id"])["exit_reason"] == "carry_filled" and oid in venue.cancelled


def test_a_veto_at_re_gate_drops_the_intent_and_submits_nothing(env, monkeypatch):
    conn, venue, _ = env
    entry = _l1_entry(conn, venue)
    _tick(conn, venue, "2026-01-02T16:00:05-05:00", market_open=False, entries_ok=False)

    class NotCheap:
        cheap, iv_rv_ratio, otm_skew_volpts, reasons, rv, atm_iv, wing_iv = False, 1.5, 2.0, ["iv/rv 1.50 > 1.20"], .5, .6, .6
    monkeypatch.setattr(paper_loop, "is_cheap_convexity", lambda *a, **k: NotCheap())
    n_before = len(venue.submitted)
    _tick(conn, venue, "2026-01-05T10:00:05-05:00")
    assert len(venue.submitted) == n_before
    assert _row(conn, entry["id"])["exit_reason"] == "carry_veto:veto-iv-gate"


def test_nothing_is_placed_while_the_market_is_closed_or_entries_are_off(env):
    conn, venue, _ = env
    _l1_entry(conn, venue)
    _tick(conn, venue, "2026-01-02T16:00:05-05:00", market_open=False, entries_ok=False)
    n = len(venue.submitted)
    assert _tick(conn, venue, "2026-01-05T10:00:05-05:00", market_open=False) == 0
    assert _tick(conn, venue, "2026-01-05T10:30:05-05:00", entries_ok=False) == 0
    assert len(venue.submitted) == n


def test_one_carry_only_an_attempt_is_never_carried_again(env):
    conn, venue, _ = env
    _l1_entry(conn, venue)
    _tick(conn, venue, "2026-01-02T16:00:05-05:00", market_open=False, entries_ok=False)
    _tick(conn, venue, "2026-01-05T10:00:05-05:00")
    attempt = conn.execute("SELECT * FROM convexity_positions WHERE status='pending'").fetchone()
    assert carry.make_intent(conn, attempt, CFG, _utc("2026-01-05T16:00:05-05:00")) is False
    venue.orders[attempt["order_id"]] = {"state": "expired"}
    reconcile_pending(conn=conn, broker=venue, clock=FixedClock(_utc("2026-01-05T16:00:05-05:00")), config=CFG)
    assert _row(conn, attempt["id"])["status"] == "cancelled"


def test_a_working_order_reserves_sizing_budget():
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE convexity_positions (id INTEGER PRIMARY KEY, status TEXT, total_premium REAL)")
    conn.executemany("INSERT INTO convexity_positions(status, total_premium) VALUES(?, ?)",
                     [("open", 500.0), ("pending", 800.0), ("carried", 900.0), ("cancelled", 700.0)])
    assert state.count_committed_positions(conn) == 2 and state.committed_book_premium(conn) == 1300.0
    assert state.count_open_convexity_positions(conn) == 1     # the kill rule / dashboard view is unchanged
