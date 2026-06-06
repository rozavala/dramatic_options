"""The hard seam (PREREG §2): the council PROPOSES, the deterministic gates DISPOSE.

These are the load-bearing guarantees — conviction can never buy expensive convexity, breach a
cap, change sizing, or defeat the kill switch; over-budget / failure fail closed to zero entries;
and every proposal + agent output is persisted (forward-scoring substrate). All offline.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from dramatic_options import risk, state
from dramatic_options.clock import FixedClock
from dramatic_options.convexity_data import StaticQuoteProvider, SyntheticChainProvider
from dramatic_options.council.router import FakeRouter, _parse_candidate_header
from dramatic_options.council.wiring import council_to_themes
from dramatic_options.monitor import monitor_positions
from dramatic_options.paper_loop import run_paper_cycle
from dramatic_options.themes import Theme

CLOCK = FixedClock(datetime(2026, 1, 2, tzinfo=UTC))
COUNCIL = {
    "enabled": True, "conviction_floor": "MODERATE", "max_candidates": 50, "news_lookback_days": 90,
    "conviction_to_prob": {"LOW": 0.55, "MODERATE": 0.65, "HIGH": 0.75, "EXTREME": 0.85},
}
CONFIG = {
    "convexity_book": {"account_equity": 100_000.0, "book_fraction": 0.10,
                       "per_name_fraction": 0.01, "max_open_positions": 15},
    "convexity_gate": {"iv_rv_max": 1.2, "otm_skew_max_volpts": 10.0, "rv_window_days": 252,
                       "tenor_min_days": 180, "tenor_max_days": 365, "target_moneyness": 0.25},
    "eligibility": {"live": {"min_option_open_interest": 50, "max_bid_ask_pct": 0.25}},
    "kill_rule": {"book_drawdown_halt": 0.20, "dry_months_halt": 9},
    "convexity_exits": {"profit_take_multiple": 4.0, "time_stop_dte": 21},
    "council": COUNCIL,
    "themes_path": "themes.json",
}


def _no_kill(monkeypatch):
    monkeypatch.delenv("KILL", raising=False)
    monkeypatch.setattr(risk, "KILL_FILE", Path("/nonexistent/KILL"))


def _provider():
    return SyntheticChainProvider(as_of=CLOCK.now().date())


def _conviction_responder(by_symbol: dict):
    """FakeRouter responder that sets each agent's conviction by candidate symbol."""

    def responder(role, system, user):
        c = _parse_candidate_header(user)
        conv = by_symbol.get(c["symbol"], "HIGH")
        if role == "proposer":
            return json.dumps({"theme": c["theme"], "symbol": c["symbol"], "direction": c["direction"],
                               "structural_vs_fad": "structural", "inflection_thesis": "t",
                               "confidence": conv, "cited": []})
        if role == "adversary":
            return json.dumps({"counter_case": "c", "weakest_point": "w", "is_fad": False,
                               "already_consensus": False, "confidence": "MODERATE", "cited": []})
        return json.dumps({"include": True, "theme": c["theme"], "symbol": c["symbol"],
                           "direction": c["direction"], "conviction": conv,
                           "structural_vs_fad": "structural", "weakest_point": "w", "summary": "s"})

    return responder


def _decisions(conn):
    return {r["symbol"]: r["decision"]
            for r in conn.execute("SELECT symbol, decision FROM convexity_eval ORDER BY id")}


# ── 1. Conviction can never buy expensive convexity ──────────────────────────

def test_extreme_conviction_on_rich_name_still_vetoed(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    conn = convexity_db
    candidates = [Theme("copper", "FCX", "bullish", "cheap"), Theme("hype", "NVDA", "bullish", "rich")]
    router = FakeRouter(responder=_conviction_responder({"NVDA": "EXTREME", "FCX": "HIGH"}))
    themes = council_to_themes(conn, candidates=candidates, router=router, config=CONFIG,
                               clock=CLOCK, demo=True, run_id=None)
    assert {t.symbol for t in themes} == {"FCX", "NVDA"}  # both passed the council
    run_paper_cycle(config=CONFIG, conn=conn, clock=CLOCK, provider=_provider(),
                    broker=_broker(), themes=themes, run_id=None)
    # The IV gate vetoes NVDA despite EXTREME conviction — the hard seam holds.
    assert _decisions(conn)["NVDA"] == "veto-iv-gate"
    assert "NVDA" not in state.open_position_symbols(conn)
    nvda = conn.execute("SELECT conviction FROM council_proposals WHERE symbol='NVDA'").fetchone()
    assert nvda["conviction"] == "EXTREME"  # recorded for forward scoring, not honored by the gate


# ── 2. Conviction can never breach the portfolio caps ────────────────────────

def test_council_flood_is_bounded_by_caps(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    conn = convexity_db
    candidates = [Theme(f"theme{i}", f"SYM{i:02d}", "bullish", "cheap default") for i in range(30)]
    themes = council_to_themes(conn, candidates=candidates, router=FakeRouter(), config=CONFIG,
                               clock=CLOCK, demo=True, run_id=None)
    assert len(themes) == 30  # council proposed all 30
    res = run_paper_cycle(config=CONFIG, conn=conn, clock=CLOCK, provider=_provider(),
                          broker=_broker(), themes=themes, run_id=None)
    # …but the deterministic caps bind: ≤ max_open_positions and within the book budget.
    assert 0 < res.opened <= CONFIG["convexity_book"]["max_open_positions"] < 30
    budget = 100_000.0 * 0.10
    assert state.convexity_book_open_premium(conn) <= budget + 1e-6


# ── 3. Conviction never changes sizing (flat-by-slots, PREREG §5) ────────────

def test_conviction_does_not_change_sizing(convexity_db):
    def contracts_for(conviction):
        conn = state.connect(":memory:")
        for m in ("0001_initial.py", "0003_convexity.py", "0004_convexity_mtm.py", "0005_council.py"):
            _apply(conn, m)
        theme = Theme("copper", "FCX", "bullish", "t", proposal_id=None, conviction=conviction)
        run_paper_cycle(config=CONFIG, conn=conn, clock=CLOCK, provider=_provider(),
                        broker=_broker(), themes=[theme], run_id=None)
        row = conn.execute("SELECT contracts FROM convexity_positions WHERE symbol='FCX'").fetchone()
        conn.close()
        return row["contracts"] if row else None

    assert contracts_for("HIGH") == contracts_for("MODERATE") is not None


# ── 4. Over-budget / failure fails closed to zero entries ────────────────────

def test_over_budget_yields_zero_entries(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    conn = convexity_db
    candidates = [Theme("copper", "FCX", "bullish", "cheap")]
    themes = council_to_themes(conn, candidates=candidates, router=FakeRouter(cap_usd=0.0),
                               config=CONFIG, clock=CLOCK, demo=True, run_id=None)
    assert themes == []  # over-budget → nothing proposed
    assert conn.execute("SELECT COUNT(*) c FROM council_proposals").fetchone()["c"] == 0
    res = run_paper_cycle(config=CONFIG, conn=conn, clock=CLOCK, provider=_provider(),
                          broker=_broker(), themes=themes, run_id=None)
    assert res.opened == 0


# ── 5. KILL → the council is never invoked (orchestrator path) ───────────────

def test_kill_switch_means_council_never_invoked(monkeypatch):
    from dramatic_options import orchestrator

    calls = {"n": 0}

    def _spy(*a, **k):
        calls["n"] += 1
        return []

    monkeypatch.setattr(orchestrator, "council_to_themes", _spy)

    _no_kill(monkeypatch)
    assert orchestrator.run_once(demo=True) == 0
    assert calls["n"] == 1  # sanity: without KILL the council IS invoked

    monkeypatch.setenv("KILL", "1")
    assert orchestrator.run_once(demo=True) == 0
    assert calls["n"] == 1  # with KILL, no further invocation — no LLM spend


# ── 6. Every proposal + agent output is persisted; trades thread proposal_id ──

def test_end_to_end_persists_proposals_and_threads_ids(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    conn = convexity_db
    candidates = [Theme("copper", "FCX", "bullish", "cheap"), Theme("hype", "NVDA", "bullish", "rich")]
    themes = council_to_themes(conn, candidates=candidates, router=FakeRouter(), config=CONFIG,
                               clock=CLOCK, demo=True, run_id=None)
    assert conn.execute("SELECT COUNT(*) c FROM council_proposals").fetchone()["c"] == 2
    assert conn.execute("SELECT COUNT(*) c FROM council_agent_outputs").fetchone()["c"] == 6  # 3 × 2

    run_paper_cycle(config=CONFIG, conn=conn, clock=CLOCK, provider=_provider(),
                    broker=_broker(), themes=themes, run_id=None)

    fcx = conn.execute("SELECT proposal_id, entry_spot FROM convexity_positions WHERE symbol='FCX'").fetchone()
    assert fcx["proposal_id"] is not None and fcx["entry_spot"] == 45.0  # synthetic FCX spot
    # survivorship eval carries the proposal too
    nvda_eval = conn.execute("SELECT proposal_id, decision FROM convexity_eval WHERE symbol='NVDA'").fetchone()
    assert nvda_eval["proposal_id"] is not None and nvda_eval["decision"] == "veto-iv-gate"
    # statuses: FCX traded (linked), NVDA reached the gates but was vetoed (still 'proposed')
    statuses = {r["symbol"]: r["status"] for r in conn.execute("SELECT symbol, status FROM council_proposals")}
    assert statuses["FCX"] == "traded" and statuses["NVDA"] == "proposed"


# ── 7-8. Forward resolution fires at close (and stays unresolved without spot) ─

def _open_linked(conn, *, conviction, entry_pc, expiry, contract="FCX261218C00080000"):
    pid = state.record_council_proposal(conn, run_id=None, as_of="2026-01-02T00:00:00+00:00",
                                        theme="copper", symbol="FCX", direction="bullish",
                                        conviction=conviction)
    pos = state.record_convexity_position(
        conn, run_id=None, opened_at="2026-01-02T00:00:00+00:00", theme="copper", symbol="FCX",
        direction="bullish", structure_kind="C", contract_symbol=contract, expiry=expiry,
        strike=56.0, dte=270, moneyness=0.25, contracts=1, entry_premium_per_contract=entry_pc,
        total_premium=entry_pc, proposal_id=pid, entry_spot=45.0)
    state.link_proposal_position(conn, pid, pos)
    return pid


def test_resolution_fires_at_profit_take(convexity_db):
    conn = convexity_db
    clock = FixedClock(datetime(2026, 6, 1, tzinfo=UTC))
    pid = _open_linked(conn, conviction="HIGH", entry_pc=200.0, expiry="2026-12-18")
    qp = StaticQuoteProvider({"FCX261218C00080000": 9.0})  # $900 ≥ 4× $200 → profit-take
    monitor_positions(conn=conn, clock=clock, quote_provider=qp, config=CONFIG,
                      underlying_price_of=lambda s: 60.0)
    prop = state.council_proposal_by_id(conn, pid)
    assert prop["outcome"] == 1 and prop["brier"] == 0.0625 and prop["resolved_at"] is not None


def test_resolution_unresolved_without_underlying(convexity_db):
    conn = convexity_db
    clock = FixedClock(datetime(2026, 6, 1, tzinfo=UTC))
    # Expiry soon → time-stop; no underlying_price_of supplied → spot unavailable.
    pid = _open_linked(conn, conviction="HIGH", entry_pc=500.0, expiry="2026-06-10")
    qp = StaticQuoteProvider({"FCX261218C00080000": 6.0})  # $600 < 4× $500 → not a profit-take
    monitor_positions(conn=conn, clock=clock, quote_provider=qp, config=CONFIG)
    prop = state.council_proposal_by_id(conn, pid)
    assert prop["outcome"] is None and prop["resolved_at"] is not None  # recorded, never fabricated


# ── test helpers ─────────────────────────────────────────────────────────────

def _broker():
    from dramatic_options.broker import PaperBroker

    return PaperBroker(100_000.0)


def _apply(conn, name):
    import importlib.util

    p = Path(__file__).resolve().parent.parent / "scripts" / "migrations" / name
    spec = importlib.util.spec_from_file_location(p.stem, p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.apply(conn)
