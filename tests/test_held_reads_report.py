"""§10.13 §4 (#508): the read-only scoring of held reads at close — the last 3 NON-dropped reads (2026-11-17 pin), the
backfill convention, the < 3 bin, the ≥10× column, model_mix segments (a close spanning two is "mixed"), and no
rate before 20 scored closes."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

import held_reads_report as hr
import state

ROOT = Path(__file__).resolve().parents[1]
MIX_A = json.dumps({"strategist": "anthropic/claude-opus-4-8", "prompts": "a"})
MIX_B = json.dumps({"strategist": "anthropic/claude-opus-5-5", "prompts": "b"})


def _pos(pid=1, *, pnl=50.0, prem=100.0, backfill=False, closed_at="2026-12-20T20:00:00+00:00"):
    return {"id": pid, "symbol": f"S{pid}", "direction": "bullish", "total_premium": prem, "realized_pnl": pnl,
            "closed_at": closed_at, "backfill": backfill}


def _r(conv, *, day, include=1, dropped=None, mix=MIX_A, run=None):
    return {"run_id": run or int(day.replace("-", "")[-4:]), "conviction": conv, "include": include, "dropped": dropped,
            "model_mix": mix, "created_at": f"{day} 21:10:00"}


def test_intact_and_broken_on_the_last_three():
    reads = [_r("LOW", day="2026-12-01"), _r("MODERATE", day="2026-12-02"), _r("HIGH", day="2026-12-03"),
             _r("LOW", day="2026-12-04")]
    c = hr.classify(_pos(), reads)
    assert c["bin"] == "scored" and c["verdict"] == "intact" and c["reads_used"] == [1202, 1203, 1204]
    reads[1]["conviction"] = "LOW"
    assert hr.classify(_pos(), reads)["verdict"] == "broken"                 # only 1 of the last 3 ≥ MODERATE


def test_dropped_reads_are_excluded_and_counted():
    """2026-11-17 pin (decision A): a drop is the debate declining to judge — it neither counts as below the floor
    nor occupies a slot in the last 3; the 3 non-dropped reads before it decide."""
    reads = [_r("MODERATE", day="2026-12-01"), _r("MODERATE", day="2026-12-02"), _r("LOW", day="2026-12-03"),
             _r("NEUTRAL", day="2026-12-04", dropped="proposer abstained (NEUTRAL)", include=0),
             _r("NEUTRAL", day="2026-12-05", dropped="ungrounded (no numeric evidence)", include=0)]
    c = hr.classify(_pos(), reads)
    assert c["verdict"] == "intact" and c["dropped"] == 2 and c["reads_used"] == [1201, 1202, 1203]


def test_fewer_than_three_non_dropped_reads_go_to_their_own_bin():
    reads = [_r("HIGH", day="2026-12-01"), _r("HIGH", day="2026-12-02"),
             _r("NEUTRAL", day="2026-12-03", dropped="ungrounded", include=0)]
    c = hr.classify(_pos(), reads)
    assert c["bin"] == "lt3" and c["verdict"] is None and c["dropped"] == 1


def test_reads_after_the_close_do_not_count():
    reads = [_r("LOW", day="2026-12-01"), _r("LOW", day="2026-12-02"), _r("LOW", day="2026-12-03"),
             _r("HIGH", day="2026-12-21"), _r("HIGH", day="2026-12-22")]
    assert hr.classify(_pos(), reads)["verdict"] == "broken"


def test_backfill_origin_uses_include_at_low_or_higher():
    reads = [_r("LOW", day="2026-12-01", include=1), _r("LOW", day="2026-12-02", include=1),
             _r("MODERATE", day="2026-12-03", include=0)]
    assert hr.classify(_pos(backfill=True), reads)["verdict"] == "intact"    # 2 include=true at LOW
    assert hr.classify(_pos(backfill=False), reads)["verdict"] == "broken"   # only 1 ≥ MODERATE
    reads = [_r("NEUTRAL", day="2026-12-01", include=1), _r("MODERATE", day="2026-12-02", include=0),
             _r("HIGH", day="2026-12-03", include=0)]
    assert hr.classify(_pos(backfill=True), reads)["verdict"] == "broken"    # include=false never counts; NEUTRAL < LOW


def test_outcome_multiple_and_tenx():
    reads = [_r("HIGH", day=f"2026-12-0{i}") for i in (1, 2, 3)]
    assert hr.classify(_pos(pnl=-100.0), reads)["multiple"] == pytest.approx(0.0)
    c = hr.classify(_pos(pnl=900.0), reads)
    assert c["multiple"] == pytest.approx(10.0) and c["tenx"] is True
    assert hr.classify(_pos(pnl=None), reads)["bin"] == "no_outcome"


def test_segments_and_the_mixed_bin():
    pos = [_pos(1, pnl=50), _pos(2, pnl=-80), _pos(3, pnl=50)]
    reads = {1: [_r("HIGH", day=f"2026-12-0{i}") for i in (1, 2, 3)],
             2: [_r("LOW", day=f"2026-12-0{i}", mix=MIX_B) for i in (1, 2, 3)],
             3: [_r("HIGH", day="2026-12-01"), _r("HIGH", day="2026-12-02", mix=MIX_B), _r("HIGH", day="2026-12-03")]}
    rep = hr.report_from(pos, reads)
    a, b = hr.segment_label(MIX_A), hr.segment_label(MIX_B)
    assert a != b and a.startswith("anthropic/claude-opus-4-8 · ")
    assert set(rep["segments"]) == {a, b, "mixed"}
    assert rep["segments"][a]["intact"]["ge1"] == 1 and rep["segments"][b]["broken"]["lt1"] == 1
    assert rep["segments"]["mixed"]["n"] == 1 and rep["all"]["n"] == 3


def test_no_rate_before_twenty_scored_closes():
    def run(n):
        pos = [_pos(i, pnl=50.0 if i % 2 else -50.0) for i in range(1, n + 1)]
        reads = {i: [_r("HIGH" if i % 4 else "LOW", day=f"2026-12-0{d}") for d in (1, 2, 3)] for i in range(1, n + 1)}
        return hr.report_from(pos, reads)["all"]

    t = run(19)
    assert t["rates"] is None and t["rates_withheld"] == "rates withheld: 19/20"
    t = run(20)
    assert t["rates_withheld"] is None
    ge1 = t["intact"]["ge1"] + t["broken"]["ge1"]
    assert t["rates"]["false_alarm_p_broken_given_ge1"] == pytest.approx(t["broken"]["ge1"] / ge1)
    assert "rates withheld: 19/20" in hr.render({**hr.report_from([], {}), "all": run(19)})


def test_report_from_the_db_and_the_cli_are_read_only(convexity_db, monkeypatch, capsys):
    conn = convexity_db
    with conn:
        for rid in (1, 2, 3):
            conn.execute("INSERT INTO runs (id, started_at, mode) VALUES (?, '2026-11-01 20:45:00', 'PAPER')", (rid,))
    pid = state.record_convexity_position(
        conn, run_id=1, opened_at="2026-11-04T19:50:00+00:00", theme="t", symbol="AAA", direction="bullish",
        structure_kind="C", contract_symbol="AAA270521C00010000", expiry="2027-05-21", strike=10.0, dte=200,
        moneyness=0.3, contracts=1, entry_premium_per_contract=100.0, total_premium=100.0, status="closed",
        rationale={"origin": "backfill"})
    with conn:
        conn.execute("UPDATE convexity_positions SET realized_pnl = 1000.0, closed_at = '2026-12-20T20:00:00+00:00' "
                     "WHERE id = ?", (pid,))
        for rid, day, conv, inc in ((1, "2026-12-01", "LOW", 1), (2, "2026-12-02", "LOW", 1), (3, "2026-12-03", "LOW", 0)):
            conn.execute("INSERT INTO held_reads (position_id, run_id, symbol, direction, as_of, conviction, include, "
                         "model_mix, created_at) VALUES (?, ?, 'AAA', 'bullish', 'x', ?, ?, ?, ?)",
                         (pid, rid, conv, inc, MIX_A, f"{day} 21:10:00"))
    rep = hr.report(conn)
    c = rep["closes"][0]
    assert c["backfill"] is True and c["verdict"] == "intact" and c["tenx"] is True    # 11× outcome
    assert rep["all"]["intact"]["ge10x"] == 1 and rep["all"]["rates_withheld"] == "rates withheld: 1/20"

    conn.commit()
    db = conn.execute("PRAGMA database_list").fetchone()["file"]
    monkeypatch.setenv("DRAMATIC_DB", db)
    spec = importlib.util.spec_from_file_location("probe_held_reads_report", ROOT / "scripts" / "probe_held_reads_report.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    calls = []
    real = mod.connect_ro
    monkeypatch.setattr(mod, "connect_ro", lambda p: calls.append(p) or real(p))
    assert mod.main(["--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["all"]["n"] == 1 and calls == [str(Path(db).resolve())]


def test_report_without_the_table(convexity_db):
    with convexity_db:
        convexity_db.execute("DROP TABLE held_reads")
    assert "error" in hr.report(convexity_db)
