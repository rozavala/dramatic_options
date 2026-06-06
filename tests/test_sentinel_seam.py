"""The hard seam for discovery (T3): discovery PROPOSES, the council JUDGES, the gates DISPOSE.

The decisive guard: a discovered candidate carrying the strongest possible conviction, on a
richly-priced name, is STILL vetoed by the deterministic IV/cheap-convexity gate — exactly as a
council proposal is (PREREG §2). Discovery can never buy expensive convexity. Plus kill-before-spend
on the discovery scan itself.
"""

from datetime import UTC, datetime
from pathlib import Path

from dramatic_options import orchestrator, risk, state
from dramatic_options.broker import PaperBroker
from dramatic_options.clock import FixedClock
from dramatic_options.convexity_data import StaticQuoteProvider, SyntheticChainProvider
from dramatic_options.monitor import monitor_positions
from dramatic_options.paper_loop import run_paper_cycle
from dramatic_options.themes import Theme

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


def test_sentinel_slot_reservation_vetoes_when_full(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    conn = convexity_db
    cfg = {**CONFIG, "discovery": {"sentinel_max_slots": 1}}
    # One open sentinel-origin position already (its proposal carries sentinel_id).
    sid = state.record_sentinel_candidate(conn, run_id=None, as_of=CLOCK.now().isoformat(),
                                          symbol="OLD", direction="bullish", basket="ai_compute",
                                          inflection_score=0.5, markers={})
    pid = state.record_council_proposal(conn, run_id=None, as_of=CLOCK.now().isoformat(),
                                        theme="ai_compute", symbol="OLD", direction="bullish",
                                        conviction="HIGH", sentinel_id=sid)
    state.record_convexity_position(conn, run_id=None, opened_at=CLOCK.now().isoformat(),
                                    theme="ai_compute", symbol="OLD", direction="bullish",
                                    structure_kind="C", contract_symbol="OLD_x", expiry="2026-09-30",
                                    strike=1.0, dte=270, moneyness=0.25, contracts=1,
                                    entry_premium_per_contract=10.0, total_premium=10.0, proposal_id=pid)
    assert state.count_open_sentinel_positions(conn) == 1
    # The reservation (1 >= 1) vetoes a NEW cheap discovered name BEFORE the gate even runs.
    fcx = Theme("ai_compute", "FCX", "bullish", "discovery", source="sentinel", sentinel_id=999)
    res = run_paper_cycle(config=cfg, conn=conn, clock=CLOCK,
                          provider=SyntheticChainProvider(as_of=CLOCK.now().date()),
                          broker=PaperBroker(100_000.0), themes=[fcx], run_id=None)
    assert res.opened == 0 and res.vetoed == 1
    row = conn.execute("SELECT decision FROM convexity_eval ORDER BY id DESC LIMIT 1").fetchone()
    assert row["decision"] == "veto-sentinel-slots"


def test_traded_sentinel_resolves_at_close(convexity_db):
    conn = convexity_db
    mcfg = {**CONFIG, "convexity_exits": {"profit_take_multiple": 4.0, "time_stop_dte": 21}}
    sid = state.record_sentinel_candidate(conn, run_id=None, as_of="2026-01-01T00:00:00+00:00",
                                          symbol="FCX", direction="bullish", basket="ai_compute",
                                          inflection_score=0.5, markers={})
    pid = state.record_council_proposal(conn, run_id=None, as_of="2026-01-01T00:00:00+00:00",
                                        theme="ai_compute", symbol="FCX", direction="bullish",
                                        conviction="HIGH", sentinel_id=sid)
    state.link_sentinel_proposal(conn, sid, pid)  # the sentinel traded
    state.record_convexity_position(conn, run_id=None, opened_at="2026-01-01T00:00:00+00:00",
                                    theme="ai_compute", symbol="FCX", direction="bullish",
                                    structure_kind="C", contract_symbol="FCX261218C00080000",
                                    expiry="2026-12-18", strike=80.0, dte=270, moneyness=0.25,
                                    contracts=1, entry_premium_per_contract=200.0, total_premium=200.0,
                                    proposal_id=pid, entry_spot=60.0)
    qp = StaticQuoteProvider({"FCX261218C00080000": 20.0})  # $2000 mark ≥ 4× $200 → profit-take
    res = monitor_positions(conn=conn, clock=FixedClock(datetime(2026, 6, 1, tzinfo=UTC)),
                            quote_provider=qp, config=mcfg)
    assert res.profit_taken == 1
    row = state.sentinel_by_id(conn, sid)
    assert row["outcome"] == 1                                  # profit-take = favorable
    assert row["realized_multiple"] is not None and abs(row["realized_multiple"] - 10.0) < 1e-6
    assert row["terminal_event"] == "traded"
