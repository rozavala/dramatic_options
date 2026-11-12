"""§6 kill rule made operational (operator word 2026-11-12; #465, #472): the dry leg (clock A from the first real fill,
payoff P1), the cumulative drawdown leg, and a trip that halts the real book but not the null books."""

import inspect
from datetime import UTC, datetime
from pathlib import Path

import fixed_basket
import risk
import shadow_book
import shares_basket
import state
from broker import PaperBroker
from clock import FixedClock
from convexity_data import SyntheticChainProvider
from paper_loop import kill_rule_status, run_paper_cycle
from themes import Theme

CONFIG = {
    "convexity_book": {"account_equity": 100_000.0, "book_fraction": 0.10, "per_name_fraction": 0.01,
                       "max_open_positions": 15},
    "convexity_gate": {"iv_rv_max": 1.2, "otm_skew_max_volpts": 10.0, "rv_window_days": 252,
                       "tenor_min_days": 180, "tenor_max_days": 365, "target_moneyness": 0.25},
    "convexity_exits": {"profit_take_multiple": 10.0, "time_stop_dte": 21, "min_close_bid": 0.05},
    "eligibility": {"live": {"min_option_open_interest": 50, "max_bid_ask_pct": 0.25}},
    "kill_rule": {"book_drawdown_halt": 0.20, "dry_months_halt": 9},
    "discovery": {"sentinel_max_slots": 6},
    "themes_path": "themes.json",
}


def _clock(y, m, d, hour=20):          # 20:00 UTC = 15:00/16:00 ET, the same ET date
    return FixedClock(datetime(y, m, d, hour, tzinfo=UTC))


def _pos(conn, *, opened_at, status="open", premium=690.0, mark=None, realized=None, closed_at=None, symbol="PL"):
    pid = state.record_convexity_position(
        conn, run_id=None, opened_at=opened_at, theme="t", symbol=symbol, direction="bullish", structure_kind="C",
        contract_symbol=f"{symbol}270115C00040000", expiry="2027-01-15", strike=40.0, dte=200, moneyness=0.3,
        contracts=1, entry_premium_per_contract=premium, total_premium=premium, status="open")
    if mark is not None:
        state.mark_convexity_position(conn, pid, mark=mark, as_of=opened_at)
    if status == "closed":
        state.close_convexity_position(conn, pid, exit_price=mark or 0.0, realized_pnl=realized, reason="time_stop",
                                       as_of=closed_at)
    elif status == "cancelled":
        state.drop_convexity_position(conn, pid, reason="cancelled_unfilled")
    return pid


# ── the dry leg ──────────────────────────────────────────────────────────────────────────────────

def test_the_dry_leg_binds_nine_calendar_months_after_the_first_real_fill(convexity_db):
    _pos(convexity_db, opened_at="2026-07-01T19:45:00+00:00")                       # PL, 2026-07-01
    before = kill_rule_status(convexity_db, CONFIG, _clock(2027, 3, 31))
    assert before.tripped is False and before.dry_since == "2026-07-01" and before.dry_binds_on == "2027-04-01"
    assert before.months_dry == 8.0
    on = kill_rule_status(convexity_db, CONFIG, _clock(2027, 4, 1))
    assert on.tripped is True and on.reasons == ("book dry since 2026-07-01 (>= 9 months, no realized payoff)",)


def test_a_profitable_close_restarts_the_clock(convexity_db):
    _pos(convexity_db, opened_at="2026-07-01T19:45:00+00:00")
    _pos(convexity_db, opened_at="2026-08-01T19:45:00+00:00", status="closed", mark=30.0, realized=2310.0,
         closed_at="2027-01-10T20:00:00+00:00", symbol="FLNC")                       # P1: realized_pnl > 0
    krs = kill_rule_status(convexity_db, CONFIG, _clock(2027, 4, 1))
    assert krs.tripped is False and krs.dry_since == "2027-01-10" and krs.dry_binds_on == "2027-10-10"


def test_a_losing_close_does_not_restart_it(convexity_db):
    _pos(convexity_db, opened_at="2026-07-01T19:45:00+00:00", status="closed", mark=0.015, realized=-688.5,
         closed_at="2026-12-28T15:00:00+00:00")
    assert kill_rule_status(convexity_db, CONFIG, _clock(2027, 4, 1)).dry_since == "2026-07-01"


def test_a_cancelled_order_never_starts_the_clock_and_no_fill_means_off(convexity_db):
    _pos(convexity_db, opened_at="2026-01-02T20:00:00+00:00", status="cancelled")
    krs = kill_rule_status(convexity_db, CONFIG, _clock(2027, 6, 1))
    assert krs.tripped is False and krs.dry_since is None and krs.months_dry == 0.0


def test_the_clock_uses_the_us_eastern_date(convexity_db):
    _pos(convexity_db, opened_at="2026-07-01T02:00:00+00:00")       # 2026-06-30 22:00 ET
    assert kill_rule_status(convexity_db, CONFIG, _clock(2027, 3, 31)).dry_binds_on == "2027-03-30"


def test_the_leg_is_off_without_dry_months_halt(convexity_db):
    _pos(convexity_db, opened_at="2026-07-01T19:45:00+00:00")
    cfg = {**CONFIG, "kill_rule": {"book_drawdown_halt": 0.20}}
    assert kill_rule_status(convexity_db, cfg, _clock(2028, 1, 1)).tripped is False


# ── the drawdown leg (cumulative) ────────────────────────────────────────────────────────────────

def test_a_closed_loss_stays_in_the_drawdown_and_adds_to_open_marks(convexity_db):
    # PL closes at −$688.50; FLNC+TITN cost $1,780 and are marked $480 (−$1,300): net −$1,988.50 on a $10k budget
    _pos(convexity_db, opened_at="2026-07-01T19:45:00+00:00", status="closed", mark=0.015, realized=-688.5,
         closed_at="2026-12-28T15:00:00+00:00")
    _pos(convexity_db, opened_at="2026-11-04T15:30:00+00:00", premium=1780.0, mark=4.80, symbol="FLNC")
    krs = kill_rule_status(convexity_db, CONFIG, _clock(2027, 1, 5))
    assert abs(krs.book_drawdown - 0.19885) < 1e-9 and krs.tripped is False
    _pos(convexity_db, opened_at="2026-11-11T20:49:00+00:00", premium=100.0, mark=0.80, symbol="RDW")   # −$20 more
    krs = kill_rule_status(convexity_db, CONFIG, _clock(2027, 1, 5))
    assert krs.tripped is True and krs.reasons[0] == "book drawdown 20% >= 20%"


def test_a_partial_close_counts_while_the_row_is_still_open(convexity_db):
    pid = _pos(convexity_db, opened_at="2026-11-04T15:30:00+00:00", premium=1500.0, symbol="FLNC")
    convexity_db.execute("UPDATE convexity_positions SET contracts = 3, entry_premium_per_contract = 500.0 WHERE id = ?",
                         (pid,))
    state.begin_close_convexity_position(convexity_db, pid, close_order_id="cl-1", reason="time_stop", as_of="t")
    state.record_partial_close(convexity_db, pid, sold_qty=2, exit_price=1.0, reason="time_stop_partial", as_of="t")
    state.mark_convexity_position(convexity_db, pid, mark=5.0, as_of="t")
    # sold 2 at $100 against $500 cost each (−$800); the remaining 1 is marked $500 against $500 (0)
    dd, have = state.convexity_book_drawdown(convexity_db, 10_000.0)
    assert have is True and abs(dd - 0.08) < 1e-9


# ── a trip halts the real book, not the null books; KILL still halts everything ──────────────────

def _no_kill(monkeypatch):
    monkeypatch.delenv("KILL", raising=False)
    monkeypatch.setattr(risk, "KILL_FILE", Path("/nonexistent/KILL"))


def test_a_rule_trip_halts_the_real_book_but_the_shadow_book_keeps_booking(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    _pos(convexity_db, opened_at="2026-01-02T20:00:00+00:00", premium=3000.0, mark=5.0)    # −$2,500: 25% dd
    clock = _clock(2026, 1, 5)
    assert kill_rule_status(convexity_db, CONFIG, clock).tripped is True
    real = run_paper_cycle(config=CONFIG, conn=convexity_db, clock=clock,
                           provider=SyntheticChainProvider(as_of=clock.now().date()), broker=PaperBroker(100_000.0),
                           themes=[Theme("c", "FCX", "bullish", "x")], run_id=None)
    assert real.halted is True and real.opened == 0
    shadow = shadow_book.run_shadow_cycle(config=CONFIG, conn=convexity_db, clock=clock,
                                          provider=SyntheticChainProvider(as_of=clock.now().date()),
                                          candidates=[Theme("c", "FCX", "bullish", "x")])
    assert shadow.halted is False and shadow.booked == 1


def test_the_kill_switch_still_halts_the_null_books(convexity_db, monkeypatch):
    monkeypatch.setenv("KILL", "1")
    clock = _clock(2026, 1, 5)
    res = shadow_book.run_shadow_cycle(config=CONFIG, conn=convexity_db, clock=clock,
                                       provider=SyntheticChainProvider(as_of=clock.now().date()),
                                       candidates=[Theme("c", "FCX", "bullish", "x")])
    assert res.halted is True and res.booked == 0


def test_no_null_book_reads_the_kill_rule():
    # the null books' only halt is the KILL switch; the real book, the council and L0 still read kill_rule_status
    for mod in (shadow_book, fixed_basket, shares_basket):
        src = inspect.getsource(mod)
        assert "kill_rule_status" not in src and "kill_switch_active()" in src, mod.__name__
