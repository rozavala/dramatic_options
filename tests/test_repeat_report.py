"""#456 repeat-probe report (repeat_report.py + scripts/probe_repeat_report.py): statistics on synthetic fixtures with
hand-computed expected values, the two pre-stated reads at their thresholds, and a read-only DB round trip."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

import repeat_report as rr
import state

REPO = Path(__file__).resolve().parent.parent
T, F = True, False


def _v(**kw) -> rr.Verdict:
    base = dict(structural=T, under_narrated=T, at_inflection=T, include=T, floor=F)
    base.update(kw)
    return rr.Verdict(**base)


def _ns(record: dict, repeats: list[dict], run_id: int = 1, pid: int = 1) -> rr.NameSession:
    return rr.NameSession(run_id, pid, f"S{pid}", "2026-12-08", _v(**record), [_v(**r) for r in repeats])


def test_fleiss_kappa_hand_computed():
    # S1 4T/1F: P=(16+1-5)/20=0.6 · S2 2T/3F: P=(4+9-5)/20=0.4 · S3 0T/5F: P=1.0 → P̄=2/3
    # p_T=6/15=0.4 → P_e=0.16+0.36=0.52 → κ=(2/3-0.52)/0.48 = 11/36
    subjects = [[T, T, T, T, F], [T, T, F, F, F], [F] * 5]
    assert rr.fleiss_kappa(subjects) == pytest.approx(11 / 36)
    # perfect agreement on both categories → κ = 1
    assert rr.fleiss_kappa([[T] * 5, [F] * 5]) == pytest.approx(1.0)
    # every rating identical → P_e = 1 → undefined
    assert rr.fleiss_kappa([[F] * 5, [F] * 5]) is None
    # variable raters: S1 3T/1F (n=4): P=(9+1-4)/12=0.5 · S2 1T/1F (n=2): P=(1+1-2)/2=0 · a 1-rater subject is dropped
    # P̄=0.25, p_T=4/6 → P_e=4/9+1/9=5/9 → κ=(0.25-5/9)/(4/9) = -11/16
    assert rr.fleiss_kappa([[T, T, T, F], [T, F], [T]]) == pytest.approx(-11 / 16)
    assert rr.fleiss_kappa([[T]]) is None


def test_item_stats_agreement_majority_and_ties():
    names = [
        _ns({"include": T}, [{"include": v} for v in (T, T, T, T, F)], pid=1),   # agree .8, maj T = rec → match
        _ns({"include": T}, [{"include": v} for v in (T, T, F, F, F)], pid=2),   # agree .4, maj F ≠ rec
        _ns({"include": F}, [{"include": F}] * 5, pid=3),                        # agree 1.0, match
        _ns({"include": T}, [{"include": v} for v in (T, T, F, F)], pid=4),      # tie (an exclusion left 4) → non-match
        _ns({"include": T}, [], pid=5),                                          # no counted repeat → not in stats
    ]
    st = rr.item_stats(names, "include")
    assert st["n_names"] == 4
    assert st["agreement"] == pytest.approx((0.8 + 0.4 + 1.0 + 0.5) / 4)
    assert st["majority_match"] == pytest.approx(2 / 4)
    assert st["ties"] == 1
    # κ over S1..S4: P = .6, .4, 1.0, (4+4-4)/12=1/3 → P̄ = (0.6+0.4+1+1/3)/4 = 7/12;
    # p_T = (4+2+0+2)/19 = 8/19 → P_e = (64+121)/361 = 185/361 → κ = (7/12 - 185/361)/(176/361)
    exp = (7 / 12 - 185 / 361) / (176 / 361)
    assert st["kappa"] == pytest.approx(exp)


def test_floor_item_uses_moderate():
    assert rr.verdict(structural_vs_fad="structural", under_narrated=True, at_inflection=True, include=True,
                      conviction="MODERATE").floor is True
    assert rr.verdict(structural_vs_fad="fad", under_narrated="true", at_inflection=None, include=None,
                      conviction="LOW") == rr.Verdict(F, F, F, F, F)


def _floor_names(n_contact: int, n_match: int, n_quiet: int = 3) -> list[rr.NameSession]:
    out = []
    for i in range(n_contact):
        if i < n_match:   # record LOW, 1/5 repeats MODERATE → majority below floor = record → match
            out.append(_ns({"floor": F}, [{"floor": T}] + [{"floor": F}] * 4, pid=i))
        else:             # record LOW, 3/5 repeats MODERATE → majority above floor ≠ record
            out.append(_ns({"floor": F}, [{"floor": T}] * 3 + [{"floor": F}] * 2, pid=i))
    out += [_ns({"floor": F}, [{"floor": F}] * 5, pid=100 + i) for i in range(n_quiet)]   # never in contact
    return out


def test_read1_thresholds():
    r = rr.read1(_floor_names(4, 0))
    assert r == {"floor_contact_names": 4, "majority_match": None, "verdict": "not evaluable"}
    r = rr.read1(_floor_names(5, 3))                        # 3/5 = 60% < 70% → look owed
    assert r["floor_contact_names"] == 5 and r["majority_match"] == pytest.approx(0.6)
    assert r["verdict"].startswith("look owed")
    r = rr.read1(_floor_names(10, 7))                       # exactly 70% → not below → no trigger
    assert r["majority_match"] == pytest.approx(0.7) and r["verdict"] == "no trigger"


def _include_names(n: int, n_match: int) -> list[rr.NameSession]:
    out = []
    for i in range(n):
        reps = [{"include": T}] * 4 + [{"include": F}] if i < n_match else [{"include": F}] * 5
        out.append(_ns({"include": T}, reps, pid=i))
    return out


def test_read2_thresholds():
    r = rr.read2(_include_names(29, 29))
    assert r["name_sessions"] == 29 and r["verdict"] == "not evaluable"
    r = rr.read2(_include_names(30, 23))                    # 23/30 = 76.7% < 80%
    assert r["majority_match"] == pytest.approx(23 / 30)
    assert r["verdict"].startswith("below 80%")
    assert r["any_disagreement"] == pytest.approx(23 / 30)  # the 4T/1F names split; the 0/5 ones do not
    r = rr.read2(_include_names(30, 24))                    # exactly 80% → at or above
    assert r["verdict"] == "at or above 80%"


def _seed(conn):
    """One session, two names. Record rows written directly (test setup), reads as the probe writes them."""
    rid = state.record_run(conn, mode="PAPER", equity=1)
    pids = []
    for sym, conv, strat in (("AAA", "MODERATE", {"include": True, "under_narrated": True, "at_inflection": True}),
                             ("BBB", "LOW", {"include": False, "under_narrated": False, "at_inflection": True})):
        pids.append(state.record_council_proposal(
            conn, run_id=rid, as_of="2026-12-08T20:45:00+00:00", theme="t", symbol=sym, direction="bullish",
            conviction=conv, structural_vs_fad="structural",
            rationale={"order": "for_first", "strategist": strat}))
    with conn:
        conn.execute("INSERT INTO council_repeat_sessions (run_id, session_date_et, status, k, names_captured, "
                     "names_probed, repeats, summary, cost_usd, started_at) "
                     "VALUES (?, '2026-12-08', 'done', 5, 2, 2, 10, '{}', 0.2, '2026-12-08 21:10:00')", (rid,))
        reps = {pids[0]: [("MODERATE", 1), ("LOW", 1), ("MODERATE", 1), ("LOW", 0), ("MODERATE", 1)],
                pids[1]: [("LOW", 0), ("LOW", 0), ("MODERATE", 1), ("LOW", 0), ("LOW", 0)]}
        for pid, rows in reps.items():
            for i, (conv, inc) in enumerate(rows):
                conn.execute(
                    "INSERT INTO council_repeat_reads (session_id, run_id, proposal_id, symbol, repeat_idx, provider, "
                    "model, conviction, include, structural_vs_fad, under_narrated, at_inflection, criteria_veto, "
                    "cost_usd, excluded_reason, created_at) VALUES (1, ?, ?, 'X', ?, 'fake', 'm', ?, ?, "
                    "'structural', 1, 1, 0, 0.02, NULL, '2026-12-08 21:11:00')", (rid, pid, i, conv, inc))
        conn.execute("INSERT INTO council_repeat_reads (session_id, run_id, proposal_id, symbol, repeat_idx, provider, "
                     "model, conviction, cost_usd, excluded_reason, created_at) VALUES (1, ?, ?, 'X', 5, 'under', "
                     "'u', 'HIGH', 0.01, 'understudy', '2026-12-08 21:12:00')", (rid, pids[1]))
    return rid


def test_report_from_the_db(convexity_db):
    _seed(convexity_db)
    rep = rr.report(convexity_db)
    assert rep["excluded_by_reason"] == {"understudy": 1}
    floor = rep["pooled"]["floor"]
    # AAA: record ≥floor, repeats 3/5 → agree .6, maj T → match. BBB: record <floor, 1/5 → agree .8, maj F → match.
    assert floor["n_names"] == 2 and floor["agreement"] == pytest.approx(0.7) and floor["majority_match"] == 1.0
    inc = rep["pooled"]["include"]
    # AAA: rec T, repeats 4/5 T → .8 match; BBB: rec F, 1/5 T → .8 match
    assert inc["agreement"] == pytest.approx(0.8) and inc["majority_match"] == 1.0
    un = rep["pooled"]["under_narrated"]   # AAA rec T, all T → 1.0; BBB rec F, all T → 0.0 → maj mismatch
    assert un["agreement"] == pytest.approx(0.5) and un["majority_match"] == pytest.approx(0.5)
    assert rep["read1"] == {"floor_contact_names": 2, "majority_match": None, "verdict": "not evaluable"}
    assert rep["read2"]["name_sessions"] == 2 and rep["read2"]["verdict"] == "not evaluable"
    assert len(rep["per_session"]) == 1 and rep["per_session"][0]["name_sessions"] == 2
    text = rr.render(rep)
    assert "Read 1 (entry)" in text and "Read 2 (include)" in text and "understudy" in text


def test_cli_is_read_only(convexity_db, tmp_path, monkeypatch, capsys):
    _seed(convexity_db)
    convexity_db.commit()
    db = convexity_db.execute("PRAGMA database_list").fetchone()["file"]
    monkeypatch.setenv("DRAMATIC_DB", db)
    spec = importlib.util.spec_from_file_location("probe_repeat_report", REPO / "scripts" / "probe_repeat_report.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    calls = []
    real = mod.connect_ro
    monkeypatch.setattr(mod, "connect_ro", lambda p: calls.append(p) or real(p))
    assert mod.main(["--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["excluded_by_reason"] == {"understudy": 1} and calls == [str(Path(db).resolve())]
