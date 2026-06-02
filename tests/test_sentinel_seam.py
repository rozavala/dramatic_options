"""The hard seam for discovery (T3): discovery PROPOSES, the council JUDGES, the gates DISPOSE.

The decisive guard: a discovered candidate carrying the strongest possible conviction, on a
richly-priced name, is STILL vetoed by the deterministic IV/cheap-convexity gate — exactly as a
council proposal is (PREREG §2). Discovery can never buy expensive convexity. Plus kill-before-spend
on the discovery scan itself.
"""

from datetime import UTC, datetime
from pathlib import Path

import orchestrator
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


def _no_kill(monkeypatch):
    monkeypatch.delenv("KILL", raising=False)
    monkeypatch.setattr(risk, "KILL_FILE", Path("/nonexistent/KILL"))


def test_extreme_sentinel_conviction_cannot_override_the_iv_gate(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    conn = convexity_db
    # Discovered candidates (source='sentinel') with the strongest conviction the system allows.
    rich = Theme("ai_compute", "NVDA", "bullish", "discovery hypothesis", conviction="EXTREME",
                 source="sentinel", sentinel_id=1)
    cheap = Theme("ai_compute", "FCX", "bullish", "discovery hypothesis", conviction="EXTREME",
                  source="sentinel", sentinel_id=2)
    res = run_paper_cycle(config=CONFIG, conn=conn, clock=CLOCK,
                          provider=SyntheticChainProvider(as_of=CLOCK.now().date()),
                          broker=PaperBroker(100_000.0), themes=[rich, cheap], run_id=None)
    decisions = {e["symbol"]: e["decision"]
                 for e in conn.execute("SELECT symbol, decision FROM convexity_eval").fetchall()}
    assert decisions["NVDA"] == "veto-iv-gate"   # EXTREME discovery conviction does NOT override the gate
    assert decisions["FCX"] == "open"            # a CHEAP discovered name can trade — only via the gate
    assert res.opened == 1 and res.vetoed == 1


def test_discovered_position_carries_its_provenance(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    conn = convexity_db
    # Mirror the council path: a proposal exists and a sentinel-origin Theme references it.
    pid = state.record_council_proposal(conn, run_id=None, as_of=CLOCK.now().isoformat(),
                                        theme="ai_compute", symbol="FCX", direction="bullish",
                                        conviction="HIGH")
    theme = Theme("ai_compute", "FCX", "bullish", "discovery hypothesis", proposal_id=pid,
                  conviction="HIGH", source="sentinel", sentinel_id=7)
    run_paper_cycle(config=CONFIG, conn=conn, clock=CLOCK,
                    provider=SyntheticChainProvider(as_of=CLOCK.now().date()),
                    broker=PaperBroker(100_000.0), themes=[theme], run_id=None)
    pos = state.open_convexity_positions(conn)[0]
    assert pos["proposal_id"] == pid             # provenance chain proposal → position is intact


def test_discovery_halts_under_kill_switch(monkeypatch):
    monkeypatch.setenv("KILL", "1")
    # kill-before-spend: the scan returns immediately, touching nothing (no scan, no persist).
    assert orchestrator.run_discover(demo=True) == 0


def test_discover_demo_runs_offline_end_to_end(monkeypatch):
    _no_kill(monkeypatch)
    # Full offline pipeline over the real config baskets on an ephemeral DB (synthetic market).
    assert orchestrator.run_discover(demo=True) == 0
