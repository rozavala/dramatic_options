"""dashboard_data — the read-only data layer for the §5b dashboard.

Two test classes: STRUCTURAL (the safety contract + empty/accruing + seeded rows surface) and the
HAND-CHECKED VALUE set (the anti-HARK discipline — every net-new number asserted to an exact, hand-computed
value; PREREG_CONVEXITY_CALIBRATION §6). The fixture `convexity_db` (conftest) is a migrated schema-12 DB.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

import config_loader
import dashboard_data as dd
import state

CONFIG = {
    "database": {"path": "data/dramatic_options.db"},
    "cache": {"dir": "data/cache"},
    "convexity_book": {
        "account_equity": 100000.0, "book_fraction": 0.10, "per_name_fraction": 0.01,
        "max_open_positions": 15, "cluster_fraction": 0.02,
        "clusters": {"ai_capex_power": ["VRT", "PWR", "GEV"], "space_defense": ["RKLB", "KTOS"]},
    },
    "kill_rule": {"book_drawdown_halt": 0.20},
    "council": {"cost_cap_usd": 5.0},
}


def _pos(conn, symbol, total_premium, *, opened_at="2026-06-01T00:00:00+00:00", status="open",
         run_id=None, proposal_id=None, contracts=1, mark=None, realized_pnl=None, closed_at=None,
         direction="bullish", theme="ai_compute"):
    pid = state.record_convexity_position(
        conn, run_id=run_id, opened_at=opened_at, theme=theme, symbol=symbol, direction=direction,
        structure_kind="long_call", contract_symbol=f"{symbol}C", expiry="2027-01-15", strike=100.0,
        dte=300, moneyness=0.25, contracts=contracts, entry_premium_per_contract=total_premium / contracts,
        total_premium=total_premium, status="open", proposal_id=proposal_id,
    )
    if mark is not None and status != "closed":
        state.mark_convexity_position(conn, pid, mark=mark, as_of=opened_at)
    if status == "closed":
        state.close_convexity_position(conn, pid, exit_price=(mark or 0.0), realized_pnl=(realized_pnl or 0.0),
                                       reason="expiry", as_of=(closed_at or opened_at))
    return pid


# ── structural / safety ─────────────────────────────────────────────────────────────────────────
def test_connect_ro_rejects_writes(tmp_path):
    p = tmp_path / "x.db"
    c = state.connect(p)
    c.execute("CREATE TABLE t(x)")
    c.commit()
    c.close()
    ro = dd.connect_ro(p)
    with pytest.raises(sqlite3.OperationalError):
        ro.execute("INSERT INTO t(x) VALUES (1)")
    ro.close()


def test_resolve_paths_env_override(monkeypatch):
    assert dd.resolve_paths(CONFIG)["from_env"] is False
    monkeypatch.setenv("DRAMATIC_DB", "/tmp/live.db")
    r = dd.resolve_paths(CONFIG)
    assert r["db_path"].endswith("live.db") and r["from_env"] is True


def test_safe_wraps_exceptions():
    out = dd.safe(lambda: 1 / 0)
    assert "error" in out and "ZeroDivisionError" in out["error"]


def test_header_empty(convexity_db, monkeypatch):
    # The fixture applies migrations via bare apply() and does NOT populate the schema_version tracking
    # table (the migration RUNNER does that on the live DB), so align EXPECTED to test the match-path.
    monkeypatch.setattr(dd, "SCHEMA_EXPECTED", state.schema_version(convexity_db))
    h = dd.header_status(convexity_db)
    assert h["schema_ok"] is True and h["schema_warning"] is None
    assert h["cycle"]["stale"] is True  # no runs yet


def test_schema_ahead_warning(convexity_db, monkeypatch):
    monkeypatch.setattr(dd, "SCHEMA_EXPECTED", 99)
    h = dd.header_status(convexity_db)
    assert h["schema_ok"] is False and h["schema_warning"]


def test_staleness_flag(convexity_db):
    # no runs → OFFLINE (never ran), distinct from STALE
    assert dd.header_status(convexity_db)["cycle"]["status"] == "OFFLINE"
    convexity_db.execute("INSERT INTO runs(started_at, mode) VALUES('2020-01-01T00:00:00+00:00','PAPER')")
    convexity_db.commit()
    cyc = dd.header_status(convexity_db)["cycle"]
    assert cyc["stale"] is True and cyc["status"] == "STALE"
    state.record_run(convexity_db, mode="PAPER", equity=None)
    cyc = dd.header_status(convexity_db)["cycle"]
    assert cyc["stale"] is False and cyc["status"] == "ONLINE"


def test_performance_empty_accruing(convexity_db):
    perf = dd.performance_panel(convexity_db)
    assert perf["tails"]["real"]["n"] == 0
    assert "accruing" in perf["p95_ci"]["real"]["flag"]


def test_performance_seeded_shadow_tail(convexity_db):
    for i in range(2):
        sid = state.record_shadow_position(
            convexity_db, run_id=None, origin="hand_seed", opened_at="2026-06-01T00:00:00+00:00",
            theme="ai_compute", symbol=f"S{i}", direction="bullish", structure_kind="long_call",
            contract_symbol=f"S{i}C", expiry="2027-01-15", strike=100.0, dte=300, moneyness=0.25,
            contracts=1, entry_premium_per_contract=1000.0, total_premium=1000.0,
        )
        state.close_shadow_position(convexity_db, sid, exit_price=2.0, realized_pnl=1000.0,
                                    realized_multiple=2.0, reason="profit_take", as_of="2026-12-01T00:00:00+00:00")
    assert dd.performance_panel(convexity_db)["tails"]["shadow_all"]["n"] == 2


def test_per_origin_left_join_handseed_vs_sentinel(convexity_db):
    rid = state.record_run(convexity_db, mode="PAPER", equity=None)
    # hand_seed: no proposal row at all
    _pos(convexity_db, "VRT", 1000.0, status="closed", realized_pnl=1000.0, run_id=rid)
    # sentinel: a proposal carrying a sentinel_id, linked to the position
    pp = state.record_council_proposal(convexity_db, run_id=rid, as_of="2026-06-01T00:00:00+00:00",
                                       theme="ai_compute", symbol="PWR", direction="bullish",
                                       conviction="HIGH", sentinel_id=7)
    _pos(convexity_db, "PWR", 1000.0, status="closed", realized_pnl=1000.0, run_id=rid, proposal_id=pp)
    split = dd.performance_panel(convexity_db)["real_by_origin"]
    assert split["hand_seed"]["n"] == 1 and split["sentinel"]["n"] == 1


def test_small_n_ci_suppressed(convexity_db):
    out = dd._bootstrap_p95_ci([1.0, 2.0, 3.0])
    assert out["n"] == 3 and out["ci90"] is None and "small-n" in out["flag"]


def test_curation_none_is_accruing(convexity_db):
    c = dd.curation_panel(convexity_db, CONFIG, market=None)
    assert "error" in c["cluster"] and "error" in c["basket"]


# ── hand-checked VALUE set (the anti-HARK discipline) ─────────────────────────────────────────────
def test_premium_bled_exact(convexity_db):
    # A: paid 1000, closed at exit 300 (realized_pnl −700) → bled 700.
    # B: paid 1000, OPEN, mark 6.0/share·100 = $600 value → bled 400.
    _pos(convexity_db, "VRT", 1000.0, status="closed", realized_pnl=-700.0)
    _pos(convexity_db, "PWR", 1000.0, status="open", mark=6.0)
    b = dd.premium_bled(convexity_db)
    assert b["paid"] == 2000.0
    assert b["realized_bled"] == 700.0
    assert b["running_bled"] == 1100.0
    assert b["running_fraction"] == 0.55
    assert b["realized_fraction"] == 0.35


def test_pnl_attribution_exact(convexity_db):
    _pos(convexity_db, "VRT", 1000.0, status="closed", realized_pnl=-700.0, theme="ai_compute")
    _pos(convexity_db, "PWR", 1000.0, status="open", mark=6.0, theme="ai_compute")
    a = dd.attribution_panel(convexity_db, CONFIG)
    assert a["pnl_by_theme"]["ai_compute"] == {"realized": -700.0, "running": -1100.0, "n": 2}
    assert a["pnl_by_cluster"]["ai_capex_power"] == {"realized": -700.0, "running": -1100.0, "n": 2}


def test_role_contribution_brier_exact(convexity_db):
    rid = state.record_run(convexity_db, mode="PAPER", equity=None)
    pp = state.record_council_proposal(convexity_db, run_id=rid, as_of="2026-06-01T00:00:00+00:00",
                                       theme="ai_compute", symbol="VRT", direction="bullish", conviction="HIGH")
    state.resolve_proposal(convexity_db, pp, outcome=1, brier=0.1, resolved_at="2026-12-01T00:00:00+00:00")
    state.record_agent_output(convexity_db, proposal_id=pp, role="proposer", provider="gemini",
                              model="m", confidence="HIGH", stance="bullish")
    a = dd.attribution_panel(convexity_db, CONFIG)
    # proposer bullish on a bullish proposal, HIGH→0.75, outcome 1 → brier (0.75−1)² = 0.0625
    assert a["role_contribution_brier"]["proposer"] == {"n": 1, "mean": 0.0625}
    assert a["proposal_brier"] == {"n": 1, "mean": 0.1}  # strategist final (the persisted column)


def test_funnel_exact(convexity_db):
    rid = state.record_run(convexity_db, mode="PAPER", equity=None)
    for sym in ("VRT", "PWR"):
        state.record_council_proposal(convexity_db, run_id=rid, as_of="2026-06-01T00:00:00+00:00",
                                      theme="ai_compute", symbol=sym, direction="bullish", conviction="HIGH")
    pp = state.record_council_proposal(convexity_db, run_id=rid, as_of="2026-06-01T00:00:00+00:00",
                                       theme="ai_compute", symbol="GEV", direction="bullish", conviction="HIGH")
    _common = dict(run_id=rid, as_of="2026-06-01T00:00:00+00:00", theme="ai_compute", direction="bullish")
    state.record_convexity_eval(convexity_db, symbol="VRT", decision="open", **_common)
    state.record_convexity_eval(convexity_db, symbol="PWR", decision="veto-iv-gate", proposal_id=pp,
                                eligible=True, gate_cheap=False, iv_rv=1.5, **_common)
    state.record_convexity_eval(convexity_db, symbol="GEV", decision="veto-eligibility", proposal_id=pp,
                                eligible=False, **_common)
    f = dd.funnel_panel(convexity_db)["l1_decision"]
    assert f["proposed"] == 3 and f["evaluated"] == 3 and f["opened"] == 1
    assert f["wasted_llm_spend"] == 2  # the iv-gate + eligibility vetoes that had a proposal


def test_gate_reasons_failclosed_vs_real(convexity_db):
    _common = dict(run_id=None, as_of="2026-06-01T00:00:00+00:00", theme="ai_compute", direction="bullish")
    state.record_convexity_eval(convexity_db, symbol="VRT", decision="veto-iv-gate", iv_rv=None, **_common)  # fail-closed
    state.record_convexity_eval(convexity_db, symbol="PWR", decision="veto-iv-gate", iv_rv=1.7, **_common)   # real veto
    g = dd.gate_reasons(convexity_db)
    assert g["iv_gate"] == {"total": 2, "fail_closed_missing_data": 1, "real_veto": 1}


def test_cap_binding_flow_exact(convexity_db):
    state.record_convexity_eval(convexity_db, run_id=None, as_of="2026-06-01T00:00:00+00:00", theme="ai_compute",
                                symbol="VRT", direction="bullish", decision="veto-cluster-cap",
                                eligible=True, gate_cheap=True)
    assert dd.cap_binding_flow(convexity_db)["cluster_cap_rejections_of_passing"] == 1


def test_cost_ledger_exact(convexity_db):
    state.record_council_proposal(convexity_db, run_id=None, as_of="2026-06-01T00:00:00+00:00", theme="ai_compute",
                                  symbol="VRT", direction="bullish", conviction="HIGH", cost_usd=0.12)
    state.record_sentinel_candidate(convexity_db, run_id=None, as_of="2026-06-01T00:00:00+00:00", symbol="PWR",
                                    direction="bullish", basket="ai_compute", inflection_score=1.0,
                                    markers={"m": 1}, cost_usd=0.002)
    c = dd.cost_ledger(convexity_db)
    assert c["l1_council_usd"] == 0.12 and c["l0_framer_usd"] == 0.002 and c["cumulative_usd"] == 0.122


def test_censor_count_in_null_hierarchy(convexity_db):
    rid = state.record_run(convexity_db, mode="PAPER", equity=None)
    state.update_run_council_health(convexity_db, rid, council_health="parse_fail")
    nh = dd.null_hierarchy(convexity_db)
    council_step = next(s for s in nh["steps"] if s["name"].startswith("council"))
    assert council_step["censored_parse_fail_runs"] == 1


def test_t4_scoreboard_breach_cell(convexity_db):
    t4 = dd.t4_scoreboard(convexity_db, CONFIG)
    cond3 = next(c for c in t4["conditions"] if c["id"] == 3)
    assert cond3["verdict"] == "VACUOUS"  # empty book → 0/0 is vacuous, not a pass
    cond1 = next(c for c in t4["conditions"] if c["id"] == 1)
    assert cond1["verdict"] == "NOT_OK"  # no healthy council runs yet
    assert cond1["checkable"] is True and next(c for c in t4["conditions"] if c["id"] == 2)["checkable"] is False


# ── keyless dashboard invariants (S1: the dashboard process must hold NO broker/LLM secrets) ──────
_KEY_VARS = ("ALPACA_API_KEY", "ALPACA_SECRET_KEY", "GEMINI_API_KEY", "XAI_API_KEY",
             "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "PERPLEXITY_API_KEY")


def test_dotenv_optout_keeps_config_keyless(monkeypatch, tmp_path):
    envf = tmp_path / ".env"
    envf.write_text("ALPACA_API_KEY=SECRET\nGEMINI_API_KEY=G\n")
    monkeypatch.setattr(config_loader, "ENV_PATH", envf)
    for k in _KEY_VARS:
        monkeypatch.delenv(k, raising=False)
    try:
        monkeypatch.setenv("DRAMATIC_SKIP_DOTENV", "1")  # the dashboard's flag → .env is NOT read
        config_loader.load_config.cache_clear()
        cfg = config_loader.load_config()
        assert cfg["alpaca"]["api_key"] is None
        assert cfg["llm_keys"]["gemini"] is None
        assert os.getenv("ALPACA_API_KEY") is None  # load_dotenv never ran → nothing injected
        # control: WITHOUT the flag the SAME .env IS read (proves the test .env is wired, not vacuous)
        monkeypatch.delenv("DRAMATIC_SKIP_DOTENV", raising=False)
        config_loader.load_config.cache_clear()
        assert config_loader.load_config()["alpaca"]["api_key"] == "SECRET"
    finally:
        for k in _KEY_VARS:
            os.environ.pop(k, None)
        config_loader.load_config.cache_clear()  # don't poison other tests with the temp config


def test_dashboard_graph_has_no_ungated_dotenv():
    # The dashboard's data-layer import graph must stay keyless: no module may call load_dotenv at import,
    # which would bypass the config_loader DRAMATIC_SKIP_DOTENV gate and re-introduce secrets. The only
    # permitted reader is config_loader (gated), which the graph imports LAZILY, never at module load.
    root = Path(config_loader.__file__).resolve().parent
    graph = ["dashboard_data.py", "breach_audit.py", "clusters.py", "fixed_basket.py", "shadow_book.py",
             "state.py", "council_health_report.py", "council/scoring.py", "council/proposal.py"]
    offenders = [m for m in graph if "load_dotenv" in (root / m).read_text()]
    assert not offenders, f"dashboard graph modules call load_dotenv (must stay keyless): {offenders}"
