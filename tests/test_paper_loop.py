"""End-to-end paper loop (offline): cheap theme opens, rich theme vetoes, fail-closed."""

from datetime import UTC, datetime
from pathlib import Path

import risk
import state
from broker import PaperBroker
from clock import FixedClock
from convexity_data import SyntheticChainProvider
from paper_loop import run_paper_cycle
from themes import Theme

CONFIG = {
    "convexity_book": {"account_equity": 100_000.0, "book_fraction": 0.10,
                       "per_name_fraction": 0.01, "max_open_positions": 15},
    "convexity_gate": {"iv_rv_max": 1.2, "otm_skew_max_volpts": 10.0, "rv_window_days": 252,
                       "tenor_min_days": 180, "tenor_max_days": 365, "target_moneyness": 0.25},
    "eligibility": {"live": {"min_option_open_interest": 50, "max_bid_ask_pct": 0.25}},
    "kill_rule": {"book_drawdown_halt": 0.20, "dry_months_halt": 9},
    "themes_path": "themes.json",
}
CLOCK = FixedClock(datetime(2026, 1, 2, tzinfo=UTC))
THEMES = [
    Theme("copper_electrification", "FCX", "bullish", "cheap industrial tailwind"),
    Theme("hype_rich", "NVDA", "bullish", "crowded, richly-priced"),
]


def _no_kill(monkeypatch):
    monkeypatch.delenv("KILL", raising=False)
    monkeypatch.setattr(risk, "KILL_FILE", Path("/nonexistent/KILL"))


def _provider():
    return SyntheticChainProvider(as_of=CLOCK.now().date())


def test_cycle_opens_cheap_and_vetoes_rich(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    conn = convexity_db
    res = run_paper_cycle(config=CONFIG, conn=conn, clock=CLOCK, provider=_provider(),
                          broker=PaperBroker(100_000.0), themes=THEMES, run_id=None)
    assert res.opened == 1
    assert res.vetoed == 1
    assert res.errors == 0
    assert not res.halted

    positions = state.open_convexity_positions(conn)
    assert len(positions) == 1
    p = positions[0]
    assert p["symbol"] == "FCX" and p["structure_kind"] == "C" and p["contracts"] >= 1
    assert p["total_premium"] > 0

    evals = conn.execute("SELECT symbol, decision FROM convexity_eval ORDER BY id").fetchall()
    decisions = {e["symbol"]: e["decision"] for e in evals}
    assert decisions["FCX"] == "open"
    assert decisions["NVDA"] == "veto-iv-gate"


def test_kill_switch_halts_entries(convexity_db, monkeypatch):
    monkeypatch.setenv("KILL", "1")
    res = run_paper_cycle(config=CONFIG, conn=convexity_db, clock=CLOCK, provider=_provider(),
                          broker=PaperBroker(100_000.0), themes=THEMES, run_id=None)
    assert res.halted is True
    assert res.opened == 0
    assert state.count_open_convexity_positions(convexity_db) == 0


def test_provider_error_is_logged_not_raised(convexity_db, monkeypatch):
    _no_kill(monkeypatch)

    class BoomProvider:
        def underlying_price(self, s):
            return 50.0

        def chain(self, s):
            raise RuntimeError("boom")

        def closes(self, s, *, window):
            return [50.0] * (window + 1)

    res = run_paper_cycle(config=CONFIG, conn=convexity_db, clock=CLOCK, provider=BoomProvider(),
                          broker=PaperBroker(100_000.0),
                          themes=[Theme("boom", "BOOM", "bullish", "x")], run_id=None)
    assert res.errors == 1
    assert res.opened == 0
    row = convexity_db.execute("SELECT decision, reasons FROM convexity_eval").fetchone()
    assert row["decision"] == "error" and "boom" in row["reasons"]


def test_dedup_skips_already_open_theme(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    conn = convexity_db
    # FCX already has an open position → re-running must not stack a duplicate.
    state.record_convexity_position(
        conn, run_id=None, opened_at="2026-01-01T00:00:00+00:00", theme="copper_electrification",
        symbol="FCX", direction="bullish", structure_kind="C", contract_symbol="FCX_x",
        expiry="2026-09-30", strike=56.0, dte=270, moneyness=0.25, contracts=1,
        entry_premium_per_contract=200.0, total_premium=200.0,
    )
    res = run_paper_cycle(config=CONFIG, conn=conn, clock=CLOCK, provider=_provider(),
                          broker=PaperBroker(100_000.0), themes=[THEMES[0]], run_id=None)
    assert res.skipped == 1 and res.opened == 0
    assert state.count_open_convexity_positions(conn) == 1  # unchanged
    row = conn.execute("SELECT decision FROM convexity_eval ORDER BY id DESC LIMIT 1").fetchone()
    assert row["decision"] == "skip-already-open"


def test_book_sized_off_config_not_broker_equity(convexity_db, monkeypatch):
    """The convexity book uses the config notional, not the (arbitrary) broker paper equity."""
    _no_kill(monkeypatch)
    # Broker reports a tiny equity that would size the book to ~nothing; config says 100k.
    res = run_paper_cycle(config=CONFIG, conn=convexity_db, clock=CLOCK, provider=_provider(),
                          broker=PaperBroker(500.0), themes=[THEMES[0]], run_id=None)
    assert res.opened == 1  # used config 100k, so FCX still sizes to ≥1 contract


def test_chain_cache_accrual(convexity_db, monkeypatch, tmp_path):
    from convexity_data import SNAPSHOT_SOURCE
    from data.cache import PointInTimeCache

    _no_kill(monkeypatch)
    cache = PointInTimeCache(tmp_path)
    run_paper_cycle(config=CONFIG, conn=convexity_db, clock=CLOCK, provider=_provider(),
                    broker=PaperBroker(100_000.0), themes=THEMES, run_id=None, chain_cache=cache)
    # Both evaluated themes' chains are persisted (even NVDA, which the IV gate vetoes).
    fcx = cache.read_between(SNAPSHOT_SOURCE, "FCX", None, CLOCK.now())
    nvda = cache.read_between(SNAPSHOT_SOURCE, "NVDA", None, CLOCK.now())
    assert len(fcx) == 1 and len(nvda) == 1
    assert fcx[0]["surface"]


def test_sizing_veto_when_concurrency_full(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    conn = convexity_db
    for i in range(15):  # fill the max-open slots
        state.record_convexity_position(
            conn, run_id=None, opened_at="2026-01-02T00:00:00+00:00", theme="f", symbol="F",
            direction="bullish", structure_kind="C", contract_symbol=f"F{i}", expiry="2026-09-30",
            strike=1.0, dte=270, moneyness=0.25, contracts=1, entry_premium_per_contract=10.0,
            total_premium=10.0,
        )
    res = run_paper_cycle(config=CONFIG, conn=conn, clock=CLOCK, provider=_provider(),
                          broker=PaperBroker(100_000.0),
                          themes=[THEMES[0]], run_id=None)
    assert res.opened == 0 and res.vetoed == 1
    row = conn.execute("SELECT decision FROM convexity_eval ORDER BY id DESC LIMIT 1").fetchone()
    assert row["decision"] == "veto-sizing"
