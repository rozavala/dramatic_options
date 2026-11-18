"""§10.13 §3 (#508): the per-position held-read timeline panel (dashboard_data.held_reads_panel). Read-only,
fail-soft, display-only: no trend, no "thesis broken" badge, no colour keyed to exit."""

from __future__ import annotations

import json

import pytest

import dashboard_data as dd
import state

ENTRY_AS_OF = "2026-11-03T20:45:00+00:00"


def _prop(conn, *, run_id, as_of, symbol="FLNC", direction="bearish", conviction="LOW", sentinel_id=None,
          strategist=None, selection=None, status="dropped"):
    rat = {"order": "for_first", "strategist": strategist or {"include": False, "under_narrated": True,
                                                              "at_inflection": False}}
    if selection:
        rat["selection"] = selection
    return state.record_council_proposal(conn, run_id=run_id, as_of=as_of, theme="t", symbol=symbol,
                                         direction=direction, conviction=conviction, structural_vs_fad="structural",
                                         rationale=rat, status=status, sentinel_id=sentinel_id)


def _held(conn, *, position_id, run_id, created_at, conviction="LOW", include=0, dropped=None, mark=1.5,
          lineage="candidate", as_of="2026-11-16T20:45:00+00:00"):
    with conn:
        conn.execute(
            "INSERT INTO held_reads (position_id, run_id, proposal_id, symbol, direction, as_of, origin, lineage_status, "
            "conviction, include, structural_vs_fad, under_narrated, at_inflection, dropped, mark_multiple, "
            "created_at) VALUES (?, ?, 1, 'FLNC', 'bearish', ?, 'sentinel', ?, ?, ?, 'structural', 1, 0, ?, ?, ?)",
            (position_id, run_id, as_of, lineage, conviction, include, dropped, mark, created_at))


@pytest.fixture
def seeded(convexity_db):
    conn = convexity_db
    with conn:
        for rid in (1900, 1918, 2055, 2056, 2073, 2090):
            conn.execute("INSERT INTO runs (id, started_at, mode) VALUES (?, '2026-11-01 20:45:00', 'PAPER')", (rid,))
    entry = _prop(conn, run_id=1918, as_of=ENTRY_AS_OF, conviction="MODERATE", status="traded",
                  strategist={"include": True, "under_narrated": True, "at_inflection": True}, selection="rank")
    pid = state.record_convexity_position(
        conn, run_id=1918, opened_at="2026-11-04T19:50:00+00:00", theme="t", symbol="FLNC", direction="bearish",
        structure_kind="P", contract_symbol="FLNC270521P00010000", expiry="2027-05-21", strike=10.0, dte=200,
        moneyness=-0.3, contracts=1, entry_premium_per_contract=100.0, total_premium=100.0, proposal_id=entry,
        rationale={"origin": "backfill"})
    with conn:
        conn.execute("UPDATE convexity_positions SET mark = 1.776 WHERE id = ?", (pid,))
    _prop(conn, run_id=1900, as_of="2026-11-01T20:45:00+00:00")                 # before entry: not a seating
    _prop(conn, run_id=2055, as_of="2026-11-13T20:45:00+00:00", selection="fairness")   # after entry: a seating
    _prop(conn, run_id=2056, as_of="2026-11-14T20:45:00+00:00", direction="bullish")    # other direction: not shown
    _held(conn, position_id=pid, run_id=2073, created_at="2026-11-16 21:10:50", mark=0.0168)   # pre-#511 row
    _held(conn, position_id=pid, run_id=2090, created_at="2026-11-17 21:10:42", mark=1.776,
          dropped="proposer abstained (NEUTRAL)", conviction="NEUTRAL", lineage="dormant",
          as_of="2026-11-17T20:45:00+00:00")
    closed = state.record_convexity_position(
        conn, run_id=1918, opened_at="2026-11-04T19:50:00+00:00", theme="t", symbol="ZZZ", direction="bullish",
        structure_kind="C", contract_symbol="ZZZ270521C00010000", expiry="2027-05-21", strike=10.0, dte=200,
        moneyness=0.3, contracts=1, entry_premium_per_contract=100.0, total_premium=100.0, status="closed")
    return conn, pid, entry, closed


def test_panel_shape_and_contents(seeded, tmp_path):
    conn, pid, entry, closed = seeded
    ledger = tmp_path / "falsifier_ledger.csv"
    ledger.write_text("read_at,spec_id,theme,symbol,direction,metric,threshold,period_end,filed,value,fired,entry_close\n"
                      "2026-11-10,f-grid,grid,FLNC,bearish,qtr_yoy,0.0,2026-09-30,2026-11-05,0.12,0,10.1\n"
                      "2026-11-10,f-grid,grid,OTHER,bearish,qtr_yoy,0.0,2026-09-30,2026-11-05,0.12,1,10.1\n")
    p = dd.held_reads_panel(conn, ledger_path=ledger)
    assert p["note"] == "measurement only — never acted on (§10.13)" and p["held_reads_table"] is True
    assert p["falsifier_status"] == "ok"
    assert [x["position_id"] for x in p["positions"]] == [pid]                          # open/closing only
    x = p["positions"][0]
    assert x["mark_multiple"] == pytest.approx(1.776) and x["origin"] == "backfill"
    assert x["entry"] == {"proposal_id": entry, "run_id": 1918, "day": "2026-11-03", "conviction": "MODERATE",
                          "include": True, "structural": True, "under_narrated": True, "at_inflection": True,
                          "status": "traded", "source": "hand-seed · rank"}
    r0, r1 = x["reads"]
    assert (r0["run_id"], r0["mark_multiple"], r0["mark_corrected"]) == (2073, pytest.approx(1.68), True)   # ×100
    assert (r1["run_id"], r1["mark_multiple"], r1["mark_corrected"]) == (2090, pytest.approx(1.776), False)
    assert r1["dropped"] == "proposer abstained (NEUTRAL)" and r1["lineage_status"] == "dormant"
    assert (r0["structural"], r0["under_narrated"], r0["at_inflection"], r0["include"]) == (True, True, False, False)
    assert [s["run_id"] for s in x["seatings"]] == [2055]
    assert x["seatings"][0]["source"] == "hand-seed · fairness"
    assert x["falsifiers"] == [{"read_at": "2026-11-10", "spec_id": "f-grid", "metric": "qtr_yoy", "value": "0.12",
                                "threshold": "0.0", "period_end": "2026-09-30", "fired": False}]


def test_no_forbidden_element_in_the_panel(seeded, tmp_path):
    """Pinned (§3): no trend line, no "thesis broken" badge, no colour keyed to exit — so the data carries no such
    field: no verdict, trend, slope, colour/level or exit hint."""
    conn, *_ = seeded
    blob = json.dumps(dd.held_reads_panel(conn, ledger_path=tmp_path / "none.csv")).lower()
    for word in ("broken", "intact", "trend", "slope", "colour", "color", "level", "badge", "exit", "signal", "sell"):
        assert f'"{word}' not in blob, word


def test_fail_soft_without_table_or_ledger(convexity_db, tmp_path):
    conn = convexity_db
    with conn:
        conn.execute("DROP TABLE held_reads")
    p = dd.held_reads_panel(conn, ledger_path=tmp_path / "absent.csv")
    assert p["held_reads_table"] is False and p["falsifier_status"] == "no ledger file" and p["positions"] == []
    bad = tmp_path / "dir.csv"
    bad.mkdir()
    assert dd.held_reads_panel(conn, ledger_path=bad)["falsifier_status"].startswith("unreadable")
    assert "error" in dd.safe(dd.held_reads_panel, None)                               # one panel fails, not the page


def test_snapshot_carries_the_panel():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard_web" / "api"))
    import snapshot

    assert "held_reads" in snapshot.PANEL_KEYS
    src = (Path(__file__).resolve().parents[1] / "dashboard_web" / "api" / "snapshot.py").read_text()
    assert '"held_reads": dd.safe(dd.held_reads_panel, conn)' in src
