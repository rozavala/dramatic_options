"""The two post-reserve dashboard panels (read-only aggregation over migration-0018 +
rationale-JSON provenance) — every net-new number pinned to a HAND-CHECKED value
(the PR-A anti-HARK discipline, PREREG_CONVEXITY_CALIBRATION §6)."""

from __future__ import annotations

import json

import dashboard_data
import state


def _run(conn, rid, started="2026-07-06 19:45:00", model_mix=None):
    conn.execute("INSERT OR IGNORE INTO runs (id, started_at, mode, model_mix) VALUES (?,?,'PAPER',?)",
                 (rid, started, json.dumps(model_mix) if model_mix else None))


def _attempt(conn, rid, book, idx, sym, outcome, pc=None):
    state.record_null_attempt(conn, run_id=rid, book=book, attempt_idx=idx, symbol=sym,
                              direction="bullish", origin="sentinel", outcome=outcome,
                              entry_premium_per_contract=pc, as_of="2026-07-06T19:48:00+00:00")


def test_null_attempts_panel_hand_checked(convexity_db):
    _run(convexity_db, 500)
    _attempt(convexity_db, 500, "shadow", 0, "PAAS", "booked", 315.0)
    _attempt(convexity_db, 500, "shadow", 1, "UROY", "no_structure", None)
    _attempt(convexity_db, 500, "shadow", 2, "NVDA", "not_cheap", 1455.0)
    _attempt(convexity_db, 500, "3A", 0, "PAAS", "booked", 315.0)
    p = dashboard_data.null_attempts_panel(convexity_db)
    assert p["run_id"] == 500
    sh = p["books"]["shadow"]
    # HAND-CHECKED: 3 shadow rows in walk order; counts booked=1, no_structure=1, not_cheap=1.
    assert [r["symbol"] for r in sh["rows"]] == ["PAAS", "UROY", "NVDA"]
    assert sh["counts"] == {"booked": 1, "no_structure": 1, "not_cheap": 1}
    assert sh["rows"][0]["entry_premium_per_contract"] == 315.0
    assert sh["rows"][1]["entry_premium_per_contract"] is None
    assert p["books"]["3A"]["counts"] == {"booked": 1}


def test_null_attempts_panel_empty_is_explicit(convexity_db):
    p = dashboard_data.null_attempts_panel(convexity_db)
    assert p["run_id"] is None and p["books"] == {} and "no attempt rows" in p["note"]


def test_reserve_panel_hand_checked(convexity_db):
    _run(convexity_db, 501, model_mix={"proposer": "x", "union_rank": "cheap_reserve_v1"})
    for sym, sel, conv in (("IRDM", "reserve", "NEUTRAL"), ("FRO", "reserve", "LOW"),
                           ("RKLB", "rank", "NEUTRAL")):
        state.record_council_proposal(
            convexity_db, run_id=501, as_of="2026-07-06T19:47:00+00:00", theme="t", symbol=sym,
            direction="bullish", conviction=conv, structural_vs_fad=None, weakest_point=None,
            rationale={"selection": sel}, strategist_summary=None, cost_usd=0.0, model_mix={},
            status="dropped")
    p = dashboard_data.reserve_panel(convexity_db)
    # HAND-CHECKED: stamp present; 2 reserve (IRDM, FRO), 1 rank (RKLB), 0 unlabeled.
    assert p["run_id"] == 501 and p["stamp"] == "cheap_reserve_v1"
    assert [e["symbol"] for e in p["reserve"]] == ["IRDM", "FRO"]
    assert [e["symbol"] for e in p["rank"]] == ["RKLB"]
    assert p["unlabeled"] == []


def test_reserve_panel_pre_reserve_run_reads_off(convexity_db):
    # A pre-deploy run: no stamp, no selection keys → everything 'unlabeled', stamp None —
    # the panel must read OFF, not invent provenance.
    _run(convexity_db, 502, model_mix={"proposer": "x"})
    state.record_council_proposal(
        convexity_db, run_id=502, as_of="2026-07-01T19:47:00+00:00", theme="t", symbol="PL",
        direction="bullish", conviction="MODERATE", structural_vs_fad=None, weakest_point=None,
        rationale={"order": "for_first"}, strategist_summary=None, cost_usd=0.0, model_mix={},
        status="traded")
    p = dashboard_data.reserve_panel(convexity_db, run_id=502)
    assert p["stamp"] is None and p["reserve"] == [] and p["rank"] == []
    assert [e["symbol"] for e in p["unlabeled"]] == ["PL"]
