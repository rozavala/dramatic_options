"""Per-name booking-attempt telemetry for the capped null books (migration 0018).

Why: the 2026-07-02 burst grade could not attribute UROY's terminal veto (aggregate counters
only) and the box journal rotates in ~2 weeks, while the cap-regime-bundled ``real − shadow``
read must stay replayable for months. One row per candidate the pass touches, in walk order:
terminal outcome + premium-at-attempt. Telemetry is FAIL-SOFT — a write failure logs and never
blocks the booking pass — and never touches the never-broker invariant.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import fixed_basket
import risk
import shadow_book
import state
from clock import FixedClock
from convexity_data import SyntheticChainProvider
from themes import Theme

CLOCK = FixedClock(datetime(2026, 1, 2, tzinfo=UTC))
CONFIG = {
    "convexity_book": {"account_equity": 100_000.0, "book_fraction": 0.10,
                       "per_name_fraction": 0.01, "max_open_positions": 15},
    "convexity_gate": {"iv_rv_max": 1.2, "otm_skew_max_volpts": 10.0, "rv_window_days": 252,
                       "tenor_min_days": 180, "tenor_max_days": 365, "target_moneyness": 0.25},
    "convexity_exits": {"profit_take_multiple": 10.0, "time_stop_dte": 21, "min_close_bid": 0.05},
    "eligibility": {"live": {"min_option_open_interest": 50, "max_bid_ask_pct": 0.25}},
    "kill_rule": {"book_drawdown_halt": 0.20, "dry_months_halt": 9},
    "discovery": {"sentinel_max_slots": 6},
    "themes_path": "themes.json",
}


def _no_kill(monkeypatch):
    monkeypatch.delenv("KILL", raising=False)
    monkeypatch.setattr(risk, "KILL_FILE", Path("/nonexistent/KILL"))


def _attempts(conn, book):
    return [dict(r) for r in conn.execute(
        "SELECT attempt_idx, symbol, outcome, entry_premium_per_contract AS pc, origin "
        "FROM null_book_attempts WHERE book=? ORDER BY attempt_idx", (book,))]


def test_shadow_attempts_record_walk_order_outcome_and_premium(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    # FCX open already (skip); CCJ cheap (books); NVDA rich (not_cheap, premium known).
    state.record_shadow_position(
        convexity_db, run_id=None, origin="hand_seed", opened_at="2026-01-01T00:00:00+00:00",
        theme="t", symbol="FCX", direction="bullish", structure_kind="C",
        contract_symbol="FCX261218C00080000", expiry="2026-12-18", strike=80.0, dte=300,
        moneyness=0.25, contracts=1, entry_premium_per_contract=200.0, total_premium=200.0,
        entry_spot=45.0)
    shadow_book.run_shadow_cycle(
        config=CONFIG, conn=convexity_db, clock=CLOCK,
        provider=SyntheticChainProvider(as_of=CLOCK.now().date()), run_id=None,
        candidates=[Theme("copper", "FCX", "bullish", "open-already"),
                    Theme("nuclear", "CCJ", "bullish", "cheap"),
                    Theme("hype", "NVDA", "bullish", "rich")])
    rows = _attempts(convexity_db, "shadow")
    assert [(r["attempt_idx"], r["symbol"], r["outcome"]) for r in rows] == [
        (0, "FCX", "skip_open"), (1, "CCJ", "booked"), (2, "NVDA", "not_cheap")]
    assert rows[0]["pc"] is None                      # skip: no structure selected
    assert rows[1]["pc"] and rows[1]["pc"] > 0        # booked: premium at attempt
    assert rows[2]["pc"] and rows[2]["pc"] > 0        # not_cheap: structure existed → premium known
    # The booked attempt's premium matches the persisted position (replayability).
    pos = state.open_shadow_positions(convexity_db)
    ccj = next(p for p in pos if p["symbol"] == "CCJ")
    assert abs(ccj["entry_premium_per_contract"] - rows[1]["pc"]) < 1e-9


def test_3a_attempts_symmetric(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    fixed_basket.run_fixed_basket_3a_cycle(
        config=CONFIG, conn=convexity_db, clock=CLOCK,
        provider=SyntheticChainProvider(as_of=CLOCK.now().date()), run_id=None,
        candidates=[Theme("nuclear", "CCJ", "bullish", "cheap"),
                    Theme("hype", "NVDA", "bullish", "rich-but-gate-off")])
    rows = _attempts(convexity_db, "3A")
    # Gate OFF: both structure → both book (NVDA's richness is invisible to 3A by design).
    assert [(r["symbol"], r["outcome"]) for r in rows] == [("CCJ", "booked"), ("NVDA", "booked")]
    assert all(r["pc"] > 0 for r in rows)


def test_attempt_write_failure_never_blocks_the_pass(convexity_db, monkeypatch):
    _no_kill(monkeypatch)

    def _boom(*a, **k):
        raise RuntimeError("telemetry down")

    monkeypatch.setattr(state, "record_null_attempt", _boom)
    res = shadow_book.run_shadow_cycle(
        config=CONFIG, conn=convexity_db, clock=CLOCK,
        provider=SyntheticChainProvider(as_of=CLOCK.now().date()), run_id=None,
        candidates=[Theme("nuclear", "CCJ", "bullish", "cheap")])
    assert res.booked == 1          # the booking pass is untouched
    assert res.errors == 0          # a telemetry failure is not an eval error


def test_attempts_table_is_telemetry_only_never_broker():
    # The 0018 substrate must not open a broker path: neither null-book module imports broker,
    # and the writer is a plain INSERT (no order/submit surface).
    import inspect

    for mod in (shadow_book, fixed_basket):
        assert "import broker" not in inspect.getsource(mod)
    src = inspect.getsource(state.record_null_attempt)
    assert "INSERT INTO null_book_attempts" in src and "submit" not in src.lower()
