"""dashboard_data — the read-only data layer for the §5b dashboard.

Two test classes: STRUCTURAL (the safety contract + empty/accruing + seeded rows surface) and the
HAND-CHECKED VALUE set (the anti-HARK discipline — every net-new number asserted to an exact, hand-computed
value; PREREG_CONVEXITY_CALIBRATION §6). The fixture `convexity_db` (conftest) is a migrated schema-12 DB.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

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


def test_schema_behind_warning(convexity_db, monkeypatch):
    # DB BEHIND what a panel renders (expected ahead of the DB) → warn (rendered data missing).
    monkeypatch.setattr(dd, "SCHEMA_EXPECTED", 99)
    h = dd.header_status(convexity_db)
    assert h["schema_ok"] is False and h["schema_warning"]


def test_schema_db_ahead_is_fine_no_false_warning(convexity_db, monkeypatch):
    # DB AHEAD of expected (a landed-but-unrendered migration, e.g. the live 15-vs-14 after 0015) is
    # FINE — extra migrations don't break older panels. The prior `==` tripwire false-warned here.
    sv = state.schema_version(convexity_db)
    monkeypatch.setattr(dd, "SCHEMA_EXPECTED", sv - 1)
    h = dd.header_status(convexity_db)
    assert h["schema_ok"] is True and h["schema_warning"] is None


def test_staleness_flag(convexity_db):
    # market-aware CYCLE beat (L2 RTH grid) — pin `now` to a weekday mid-session so it's deterministic
    # (the old flat-26h test would flip ONLINE↔STALE depending on the wall-clock day it ran).
    now = datetime(2026, 6, 9, 12, 0, tzinfo=ZoneInfo("America/New_York"))  # Tue, mid-session
    assert dd.header_status(convexity_db, now=now)["cycle"]["status"] == "OFFLINE"  # no runs → never ran
    convexity_db.execute("INSERT INTO runs(started_at, mode) VALUES('2026-06-09T09:00:00-04:00','PAPER')")
    convexity_db.commit()
    cyc = dd.header_status(convexity_db, now=now)["cycle"]  # 3h-old intraday run → STALE
    assert cyc["stale"] is True and cyc["status"] == "STALE"
    convexity_db.execute("INSERT INTO runs(started_at, mode) VALUES('2026-06-09T11:45:00-04:00','PAPER')")
    convexity_db.commit()
    cyc = dd.header_status(convexity_db, now=now)["cycle"]  # 15-min-old run → ONLINE
    assert cyc["stale"] is False and cyc["status"] == "ONLINE"


# ── account + regime (PR-C: journal-sourced balance + the configuration-of-record readout) ──────

def _ins_run(conn, started_at, mode="PAPER", equity=None, data_feed=None, model_mix=None,
             council_health=None, frame_version=None):
    conn.execute("INSERT INTO runs(started_at, mode, equity, data_feed, model_mix, council_health, "
                 "frame_version) VALUES(?,?,?,?,?,?,?)",
                 (started_at, mode, equity, data_feed, model_mix, council_health, frame_version))
    conn.commit()


def test_account_panel_hand_checked(convexity_db):
    from datetime import UTC

    now = datetime(2026, 6, 10, 21, 45, 4, tzinfo=UTC)
    _ins_run(convexity_db, "2026-06-09 14:00:00", equity=99980.00)
    _ins_run(convexity_db, "2026-06-09 19:45:00", equity=99975.50)            # later same UTC day wins
    _ins_run(convexity_db, "2026-06-09T21:30:00-04:00", equity=99970.00)      # = 2026-06-10T01:30Z → UTC day 06-10
    _ins_run(convexity_db, "2026-06-10 12:00:00", mode="DISCOVERY", equity=None)  # excluded (mode + null)
    _ins_run(convexity_db, "2026-06-10 19:45:04", equity=99971.79)            # native SQLite format, latest
    a = dd.account_panel(convexity_db, CONFIG, now=now)
    # hand-checked: broker = the latest journal equity; delta = 99971.79 − 100000 = −28.21;
    # age = 19:45:04 → 21:45:04 = 2.0h (naive timestamps parse as UTC)
    assert a["broker_equity"] == 99971.79 and a["as_of"] == "2026-06-10 19:45:04"
    assert a["age_hours"] == 2.0 and a["delta_vs_frame"] == -28.21
    # per-UTC-day LAST equity: day 06-09 → 99975.50 (later row wins); the −04:00 row crosses into
    # UTC day 06-10 and is then superseded by the higher-id native row → 99971.79
    assert a["equity_series"] == [{"day": "2026-06-09", "equity": 99975.50},
                                  {"day": "2026-06-10", "equity": 99971.79}]
    assert a["frame"] == {"frame_equity": 100000.0, "book_budget": 10000.0, "per_name_cap": 1000.0,
                          "cluster_cap": 2000.0, "max_open": 15}
    assert a["headroom"] == 10000.0  # empty book: budget − 0


def test_account_panel_empty_db(convexity_db):
    a = dd.account_panel(convexity_db, CONFIG)
    assert a["broker_equity"] is None and a["delta_vs_frame"] is None and a["equity_series"] == []


def test_regime_panel_split_read_live_shape(convexity_db):
    # The LIVE shape (the P1 pin): L2 fires every ~30min and never stamps council fields — the
    # newest row is an L2 row; council regime must come from the OLDER council-stamped row.
    from datetime import UTC

    now = datetime(2026, 6, 11, 12, 0, tzinfo=UTC)
    df = ('{"equity_bars": "sip", "option_gate": "opra", "option_monitor": "indicative", '
          '"dualread_disagree_veto_until": "2026-07-10"}')
    mm = ('{"proposer": "gemini/g", "adversary": "xai/x", "strategist": "anthropic/o", '
          '"prompts": "aaa/bbb/ccc"}')
    _ins_run(convexity_db, "2026-06-10 19:45:04", equity=99971.79, data_feed=df, model_mix=mm,
             council_health="ok", frame_version="fv1")                         # the L1 council row
    _ins_run(convexity_db, "2026-06-10 20:30:03", equity=99971.79, data_feed=df,
             frame_version="fv1")                                              # NEWER L2: council NULL
    r = dd.regime_panel(convexity_db, CONFIG, now=now)
    assert r["feeds"]["run_id"] > r["council"]["run_id"]   # two provenance anchors, split-read
    assert r["feeds"]["option_gate"] == "opra" and r["feeds"]["equity_bars"] == "sip"
    assert r["feeds"]["option_monitor"] == "indicative" and r["feeds"]["frame_version"] == "fv1"
    assert r["council"]["council_health"] == "ok"
    assert r["council"]["models"] == {"proposer": "gemini/g", "adversary": "xai/x",
                                      "strategist": "anthropic/o"}
    assert r["council"]["extras"] == {"prompts": "aaa/bbb/ccc"}  # generic non-role pass-through
    assert r["dualread_veto"] == {"until": "2026-07-10", "active": True, "days_remaining": 29}


def test_regime_panel_veto_boundary_and_failsoft(convexity_db):
    from datetime import UTC

    df = '{"option_gate": "opra", "dualread_disagree_veto_until": "2026-07-10"}'
    _ins_run(convexity_db, "2026-07-10 14:00:00", equity=1.0, data_feed=df)
    on_date = dd.regime_panel(convexity_db, CONFIG, now=datetime(2026, 7, 10, 12, 0, tzinfo=UTC))
    assert on_date["dualread_veto"]["active"] is True            # inclusive end date (canonical rule)
    assert on_date["dualread_veto"]["days_remaining"] == 0
    lapsed = dd.regime_panel(convexity_db, CONFIG, now=datetime(2026, 7, 11, 12, 0, tzinfo=UTC))
    assert lapsed["dualread_veto"]["active"] is False
    assert lapsed["dualread_veto"]["days_remaining"] is None     # never renders negative
    # pre-0013 NULL stamp → Nones, fail-soft
    _ins_run(convexity_db, "2026-07-11 19:45:00", equity=1.0, data_feed=None)
    r = dd.regime_panel(convexity_db, CONFIG, now=datetime(2026, 7, 12, 12, 0, tzinfo=UTC))
    assert r["feeds"]["option_gate"] is None and r["feeds"]["run_id"] is not None
    # health-only stamp (cost_cap with model_mix=None) → honest "health cost_cap · models —"
    _ins_run(convexity_db, "2026-07-12 19:45:00", equity=1.0, council_health="cost_cap",
             model_mix=None)
    # malformed data_feed JSON on the newest row → Nones, never a raise
    _ins_run(convexity_db, "2026-07-12 20:00:00", equity=1.0, data_feed="{not json")
    r = dd.regime_panel(convexity_db, CONFIG, now=datetime(2026, 7, 13, 12, 0, tzinfo=UTC))
    assert r["feeds"]["option_gate"] is None and r["feeds"]["dualread_veto_until"] is None
    assert r["council"]["council_health"] == "cost_cap"
    assert r["council"]["models"] == {} and r["council"]["extras"] == {}


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


def _seed_council_stage_run(conn):
    """8 proposals covering every stage + BOTH status arms of the bridge (the SOLE proof — #182 has these
    stages at 0). Returns the run_id."""
    rid = state.record_run(conn, mode="PAPER", equity=None)
    a = "2026-06-16T00:00:00+00:00"

    def prop(sym, conv, sf, rat, status):
        state.record_council_proposal(conn, run_id=rid, as_of=a, theme="t", symbol=sym, direction="bullish",
                                      conviction=conv, structural_vs_fad=sf, rationale=rat, status=status)

    def strat(include, un, at, veto):
        return {"strategist": {"include": include, "under_narrated": un, "at_inflection": at,
                               "criteria_veto": veto}}
    prop("UNGR", "NEUTRAL", None, {"dropped": "ungrounded (no numeric evidence)"}, "dropped")
    prop("ABST", "NEUTRAL", None, {"dropped": "proposer abstained (NEUTRAL)"}, "dropped")
    prop("DLOW", "LOW", "structural", strat(False, True, False, False), "dropped")     # under_narrated T
    prop("DFAD", "LOW", "fad", strat(False, False, False, False), "dropped")           # structural=fad
    prop("TRAD", "MODERATE", "structural", strat(True, True, True, False), "traded")   # bridge: traded arm
    prop("PROP", "MODERATE", "structural", strat(True, True, True, False), "proposed") # bridge: proposed arm (gate-vetoed)
    prop("VETO", "HIGH", "structural", strat(False, True, False, True), "dropped")     # criteria-veto (production shape)
    prop("BFLR", "LOW", "structural", strat(True, True, True, False), "dropped")       # include∧LOW → below-floor
    return rid


def test_council_stage_funnel_exact(convexity_db):
    _seed_council_stage_run(convexity_db)
    r = dd.council_stage_funnel(convexity_db, {"council": {"conviction_floor": "MODERATE"}})
    assert r["empty"] is False and r["floor"] == "MODERATE"
    assert r["stages"] == {"proposed": 8, "asserted": 6, "ungrounded": 1, "proposer_abstained": 1,
                           "other": 0, "strategist_include_raw": 4, "criteria_vetoed": 1,
                           "post_veto_include": 3, "below_floor": 1, "to_gate": 2}
    assert r["bridge"] == {"to_gate": 2, "survivors_by_status": 2, "ok": True}  # BOTH arms (traded+proposed)
    assert r["legs"] == {"n_deliberated": 6, "structural": 5, "under_narrated": 5, "at_inflection": 3}


def test_council_stage_funnel_tracks_config_floor(convexity_db):
    _seed_council_stage_run(convexity_db)
    r = dd.council_stage_funnel(convexity_db, {"council": {"conviction_floor": "HIGH"}})
    # all three post-veto includes (2×MODERATE + 1×LOW) are now below the HIGH floor → 0 to gate.
    assert r["stages"]["below_floor"] == 3 and r["stages"]["to_gate"] == 0


def test_council_stage_funnel_empty(convexity_db):
    assert dd.council_stage_funnel(convexity_db, {"council": {}}) == {"run_id": None, "empty": True}


def test_council_stage_funnel_malformed_rationale_is_failsoft(convexity_db):
    rid = state.record_run(convexity_db, mode="PAPER", equity=None)
    state.record_council_proposal(convexity_db, run_id=rid, as_of="t", theme="t", symbol="X",
                                  direction="bullish", conviction="LOW", rationale="not json{", status="dropped")
    r = dd.council_stage_funnel(convexity_db, {"council": {}})  # must NOT raise
    assert r["stages"]["proposed"] == 1 and r["stages"]["other"] == 1  # malformed → counted as 'other'


def test_council_drop_string_contract_via_run_candidate():
    # The two drop literals the breakout keys on ORIGINATE in run_candidate (not _neutral_proposal) —
    # drive both early-exit paths so a reword can't silently re-bucket drops to 'other'.
    import json as _json
    import random

    from council.context import ContextPack, synthetic_context_pack
    from council.debate import run_candidate
    from council.router import FakeRouter
    from themes import Theme
    cand = Theme("t", "X", "bullish", "thesis")
    ungrounded = ContextPack("X", "t", "bullish", "thesis")  # coverage 0, has_numeric False → not grounded
    p1 = run_candidate(cand, ungrounded, FakeRouter(), rng=random.Random(0))
    assert p1.rationale["dropped"] == "ungrounded (no numeric evidence)"

    def _neutral_proposer(role, system, user):
        return _json.dumps({"confidence": "NEUTRAL", "inflection_thesis": "x"})
    p2 = run_candidate(cand, synthetic_context_pack(cand), FakeRouter(responder=_neutral_proposer),
                       rng=random.Random(0))
    assert p2.rationale["dropped"] == "proposer abstained (NEUTRAL)"


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


# ── market-aware staleness (pure datetime matrices — the whole point is to NOT false-alarm) ───────
_ET = ZoneInfo("America/New_York")


@pytest.mark.parametrize("last, now, expected", [
    ("2026-06-05T15:45:30-04:00", datetime(2026, 6, 7, 12, 0, tzinfo=_ET), "ONLINE"),    # Fri run, Sun now (weekend)
    ("2026-06-05T15:45:30-04:00", datetime(2026, 6, 8, 17, 0, tzinfo=_ET), "STALE"),     # Fri run, Mon eve (missed Mon)
    ("2026-06-05T15:45:30-04:00", datetime(2026, 6, 8, 10, 0, tzinfo=_ET), "ONLINE"),    # Fri run, Mon AM (slot not due)
    ("2026-06-08T15:45:05-04:00", datetime(2026, 6, 8, 15, 46, tzinfo=_ET), "ONLINE"),   # right after the 15:45 run
    ("2026-06-08T09:00:00-04:00", datetime(2026, 6, 8, 17, 0, tzinfo=_ET), "ONLINE"),    # Persistent catch-up, same day
    ("2026-03-06T15:45:00-05:00", datetime(2026, 3, 8, 12, 0, tzinfo=_ET), "ONLINE"),    # spring-DST weekend
    ("2026-10-30T15:45:00-04:00", datetime(2026, 11, 1, 12, 0, tzinfo=_ET), "ONLINE"),   # fall-DST weekend
    (None, datetime(2026, 6, 8, 17, 0, tzinfo=_ET), "OFFLINE"),
])
def test_council_session_stale_matrix(last, now, expected):
    assert dd.council_session_stale(last, now=now) == expected


def test_council_session_stale_holiday_is_accepted_false_stale():
    # A weekday holiday with no run is the documented benign false-STALE (no holiday calendar is modeled).
    # Pin it so the behavior is explicit: MLK Mon 2026-01-19, last run the prior Fri → STALE (accepted; raw
    # age is shown beside it). A static holiday set is the deferred mitigation.
    assert dd.council_session_stale("2026-01-16T15:45:00-05:00",
                                    now=datetime(2026, 1, 19, 17, 0, tzinfo=_ET)) == "STALE"


@pytest.mark.parametrize("last, now, expected", [
    ("2026-06-09T09:30:00-04:00", datetime(2026, 6, 9, 11, 0, tzinfo=_ET), "STALE"),     # intraday stall (90m)
    ("2026-06-09T10:45:00-04:00", datetime(2026, 6, 9, 11, 0, tzinfo=_ET), "ONLINE"),    # just ticked (15m)
    ("2026-06-05T16:00:00-04:00", datetime(2026, 6, 7, 12, 0, tzinfo=_ET), "ONLINE"),    # weekend → not expected
    ("2026-06-08T16:00:00-04:00", datetime(2026, 6, 9, 9, 10, tzinfo=_ET), "ONLINE"),    # pre-open (before tick+slack)
    ("2026-06-09T15:30:00-04:00", datetime(2026, 6, 9, 20, 0, tzinfo=_ET), "ONLINE"),    # after close → not expected
    (None, datetime(2026, 6, 9, 11, 0, tzinfo=_ET), "OFFLINE"),
])
def test_cycle_session_stale_matrix(last, now, expected):
    assert dd.cycle_session_stale(last, now=now) == expected


# ── system_status banner collapser (selection incl. an errored panel) ─────────────────────────────
def test_system_status_green_when_all_nominal():
    snap = {
        "header": {"kill_switch_engaged": False, "cycle": {"status": "ONLINE", "age_hours": 3.0},
                   "council": {"status": "ONLINE"}, "discovery": {"status": "ONLINE"}},
        "risk": {"kill_rule": {"tripped": False}, "cost_cap": {"tripped": False}, "book": {"open": 0, "max": 15}},
        "council": {"health": {"verdict": "ROUNDTRIP_CONFIRMED"}},
    }
    assert dd.system_status(snap)["level"] == "success"


def test_system_status_red_on_kill():
    s = dd.system_status({"header": {"kill_switch_engaged": True}, "risk": {}, "council": {}})
    assert s["level"] == "error" and any("KILL" in i for i in s["issues"])


def test_system_status_warn_on_stale_beat():
    snap = {"header": {"kill_switch_engaged": False, "cycle": {"status": "STALE"}}, "risk": {}, "council": {}}
    assert dd.system_status(snap)["level"] == "warn"


def test_system_status_degrades_on_errored_panel():
    # A fail-soft panel that returned {"error":…} must pull the banner off green (no green-over-error-boxes).
    snap = {"header": {"kill_switch_engaged": False}, "risk": {}, "council": {}, "performance": {"error": "boom"}}
    s = dd.system_status(snap)
    assert s["level"] == "warn" and any("unavailable" in i for i in s["issues"])


# ── recent_council_health + cond-1 redefinition + deliberation + provenance ───────────────────────
def _roundtrip(conn, run_id, symbol, direction, *, adv_stance, strat_conv="MODERATE", cost=0.003):
    pid = state.record_council_proposal(conn, run_id=run_id, as_of="t", theme="x", symbol=symbol,
                                        direction=direction, conviction=strat_conv, status="proposed")
    state.record_agent_output(conn, proposal_id=pid, role="proposer", provider="gemini", model="m",
                              confidence="MODERATE", stance=direction,
                              raw={"confidence": "MODERATE", "inflection_thesis": "real"}, cost_usd=cost)
    state.record_agent_output(conn, proposal_id=pid, role="adversary", provider="xai", model="m",
                              confidence="MODERATE", stance=adv_stance,
                              raw={"confidence": "MODERATE", "counter_case": "c"}, cost_usd=cost)
    state.record_agent_output(conn, proposal_id=pid, role="strategist", provider="anthropic", model="m",
                              confidence=strat_conv, stance=direction,
                              raw={"conviction": strat_conv, "summary": "s"}, cost_usd=cost)
    return pid


def _confirmed_run(conn, symbol="SMCI"):
    rid = state.record_run(conn, mode="PAPER", equity=10000)
    state.update_run_council_health(conn, rid, council_health="ok")
    _roundtrip(conn, rid, symbol, "bearish", adv_stance="bullish")   # adversary = bull case on a bear → dir-relative
    return rid


def _degraded_run(conn, symbol="SMCI"):
    rid = state.record_run(conn, mode="PAPER", equity=10000)
    state.update_run_council_health(conn, rid, council_health="ok")   # stamped 'ok' but NOT direction-relative
    _roundtrip(conn, rid, symbol, "bearish", adv_stance="bearish")
    return rid


def _parsefail_run(conn):
    rid = state.record_run(conn, mode="PAPER", equity=10000)
    state.update_run_council_health(conn, rid, council_health="parse_fail")
    return rid


def test_recent_council_health_anchored_and_shaped(convexity_db):
    conn = convexity_db
    state.record_run(conn, mode="PAPER", equity=10000)               # a bare L2-style run, no council_health
    r = _confirmed_run(conn, "SMCI")
    win = dd.recent_council_health(conn)
    assert [w["run_id"] for w in win] == [r]                          # the null-health run is excluded
    w = win[-1]
    assert w["council_health"] == "ok" and w["verdict"] == "ROUNDTRIP_CONFIRMED"
    assert w["by_provider"]["gemini"] == {"calls": 1, "parse_error": 0, "parse_error_rate": 0.0}
    assert dd.council_panel(conn, CONFIG)["by_provider"] == w["by_provider"]   # window[-1] is the drop-in


def test_recent_council_health_ordering_oldest_to_newest(convexity_db):
    a = _confirmed_run(convexity_db, "AAA")
    b = _confirmed_run(convexity_db, "BBB")
    assert [w["run_id"] for w in dd.recent_council_health(convexity_db)] == [a, b]


def _cond1(conn):
    return next(c for c in dd.t4_scoreboard(conn, CONFIG)["conditions"] if c["id"] == 1)


def test_cond1_met_censors_parsefail_and_requires_two_confirmed(convexity_db):
    conn = convexity_db
    _parsefail_run(conn)            # the pre-fix bug run — censored, not counted against MET
    _confirmed_run(conn, "AAA")
    _confirmed_run(conn, "BBB")
    c1 = _cond1(conn)
    assert c1["verdict"] == "MET" and "censored" in c1["detail"]


def test_cond1_not_met_on_ok_but_degraded(convexity_db):
    conn = convexity_db
    _confirmed_run(conn, "AAA")
    _degraded_run(conn, "BBB")      # stamped 'ok' but DEGRADED → not all-CONFIRMED → NOT_OK
    assert _cond1(conn)["verdict"] == "NOT_OK"


def test_cond1_not_met_on_single_confirmed(convexity_db):
    _confirmed_run(convexity_db, "AAA")   # only ONE clean run → the ≥2 rule fails
    assert _cond1(convexity_db)["verdict"] == "NOT_OK"


def test_cond1_detail_names_the_blocker(convexity_db):
    # Legibility: a NOT_OK must say WHICH run breaks all-CONFIRMED (the "3-of-4 confirmed but NOT_OK" confusion)
    # and state the rule as whole-window-confirmed, not "≥2 confirmed exist".
    conn = convexity_db
    _confirmed_run(conn, "AAA")
    bid = _degraded_run(conn, "BBB")        # ok-but-DEGRADED → a blocker, not a censored bug
    c1 = _cond1(conn)
    assert c1["verdict"] == "NOT_OK"
    assert "ALL ROUNDTRIP_CONFIRMED" in c1["detail"]     # the clarified rule (not "≥2 exist")
    assert f"blocked by #{bid}" in c1["detail"]          # names the specific breaker


def test_latest_run_deliberation_shape(convexity_db):
    rid = _confirmed_run(convexity_db, "SMCI")
    delib = dd.latest_run_deliberation(convexity_db)
    assert len(delib) == 1
    row = delib[0]
    assert row["symbol"] == "SMCI" and row["proposer_direction"] == "bearish"
    assert row["adversary_stance"] == "bullish" and row["strategist_conviction"] == "MODERATE"
    assert row["run_id"] == rid


def test_position_provenance_columns(convexity_db):
    conn = convexity_db
    rid = state.record_run(conn, mode="PAPER", equity=10000)
    pp = state.record_council_proposal(conn, run_id=rid, as_of="t", theme="ai_compute", symbol="VRT",
                                       direction="bullish", conviction="HIGH")
    _pos(conn, "VRT", 1000.0, status="open", run_id=rid, proposal_id=pp)
    real_open = dd.positions_panel(conn)["real_open"]
    assert len(real_open) == 1
    assert real_open[0]["origin_run"] == rid and real_open[0]["origin_conviction"] == "HIGH"


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
             "cheapness_watch.py", "state.py", "council_health_report.py", "council/scoring.py",
             "council/proposal.py"]
    offenders = [m for m in graph if "load_dotenv" in (root / m).read_text()]
    assert not offenders, f"dashboard graph modules call load_dotenv (must stay keyless): {offenders}"


def test_cheapness_watch_panel(convexity_db):
    # the finding-#1 panel: cheapness_report verdict + per-name latest cheap state (read-only)
    conn = convexity_db
    with conn:
        conn.execute(
            "INSERT INTO cheapness_watch (run_id, as_of, symbol, cheap, iv_rv, rv_rising, mom_recent, "
            "marker_age_days, created_at) VALUES "
            "(NULL,'2026-03-01','AG',1,1.0,0.05,0.05,25,datetime('now')),"
            "(NULL,'2026-03-02','AG',1,1.1,0.05,0.05,26,datetime('now'))")
    p = dd.cheapness_watch_panel(conn)
    assert p["verdict"] == "insufficient_N"                    # no qualifying breaks → no decision off noise
    assert [r["symbol"] for r in p["latest_by_name"]] == ["AG"]
    assert p["latest_by_name"][0]["as_of"] == "2026-03-02"     # the MAX(as_of) row (latest cheap state)


def test_build_screen_command_sanitizes_shell_meta():
    # the rendered command is pasted into a shell → only clean tickers survive; shell-meta tokens dropped
    out = dd.build_screen_command("amba, mbly, cf, $(whoami), /etc, a-b")
    assert out["tickers"] == ["AMBA", "MBLY", "CF"]
    assert out["dropped"] == 3
    assert out["command"].endswith("probe_basket_feasibility.py AMBA MBLY CF")


def test_build_screen_command_empty_is_blank():
    out = dd.build_screen_command("   ")
    assert out["tickers"] == [] and out["command"] == ""


def test_build_theme_entry_valid_shape():
    te = dd.build_theme_entry(name="AV Autonomy", cluster="ai_compute", thesis="robotaxi inflection",
                              falsifier="IV stays rich; no scaling", source="https://x/holdings.csv",
                              today="2026-06-27")
    assert te["valid"] and te["key"] == "av_autonomy"
    e = te["entry"]
    assert e["provenance"] == "operator" and e["sources"] == ["https://x/holdings.csv"]
    assert e["cluster_default"] == "ai_compute" and e["thesis"] and e["falsifier"]
    assert "av_autonomy" in te["json"]


def test_build_theme_entry_requires_thesis_falsifier_source():
    te = dd.build_theme_entry(name="x9", cluster="", thesis="", falsifier="", source="", today="2026-06-27")
    assert not te["valid"] and len(te["problems"]) == 3        # thesis, falsifier, source all missing
    assert te["entry"]["cluster_default"] == "x9"              # empty cluster → defaults to the theme name
