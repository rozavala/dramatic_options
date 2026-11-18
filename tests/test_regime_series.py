"""#462 convexity regime series (PREREG_CONVEXITY_REGIME_SERIES §3–§5): the 270-day constant maturity, the statistics
over the frozen R, the 70% coverage guard, the in-segment percentiles (none before 120 nights), and the import graph."""

from __future__ import annotations

import math
import re
from datetime import date, timedelta
from pathlib import Path

import pytest

import regime_series as rs

ROOT = Path(__file__).resolve().parents[1]


def _rec(dte_atm: list[tuple[int, float]], *, rv=0.5, rv63=None, skew=None, version=None):
    exps = [{"expiry": "x", "dte": d, "atm_c": a, "atm_p": a, "otm_c": None, "otm_p": None} for d, a in dte_atm]
    if skew:
        for e in exps:
            if e["dte"] == skew[0]:
                e["otm_c"], e["otm_p"] = skew[1], skew[2]
    r = {"ts": "t", "spot": 100.0, "rv": rv, "expiries": exps}
    if rv63 is not None:
        r["rv63"] = rv63
    if version is not None:
        r["term_version"] = version
    return r


def test_sigma_270_interpolates_total_variance():
    rec = _rec([(180, 0.40), (360, 0.50)])
    # v1 = 0.16·180 = 28.8; v2 = 0.25·360 = 90; v270 = 28.8 + 61.2·(90/180) = 59.4; σ = √(59.4/270)
    assert rs.sigma_270(rec) == pytest.approx(math.sqrt(59.4 / 270))
    assert rs.sigma_270(_rec([(100, 0.3), (180, 0.40), (270, 0.45), (400, 0.6)])) == pytest.approx(0.45)  # exact
    assert rs.sigma_270(_rec([(100, 0.3), (200, 0.4)])) is None                                     # no bracket
    # the nearest expiry on each side is the bracket
    assert rs.sigma_270(_rec([(30, 9.0), (180, 0.40), (360, 0.50), (500, 9.0)])) == pytest.approx(math.sqrt(59.4 / 270))


def test_one_night_over_r_and_the_coverage_guard():
    names = rs.R[:40]                                    # 40 of 49 = 81.6% ≥ 70%
    recs = {s: _rec([(180, 0.40), (360, 0.50)], rv=0.5, rv63=0.25, skew=(180, 0.40, 0.40)) for s in names}
    recs["NOT_IN_R"] = _rec([(180, 9.0), (360, 9.0)])
    for s in names[:2]:   # a 240-day expiry for S3, still bracketed
        recs[s] = _rec([(180, 0.40), (240, 0.44), (360, 0.50)], rv=0.5, skew=(240, 0.47, 0.50))
    n = rs.night(recs)
    assert n["coverage"] == round(40 / 49, 4) and n["coverage_low"] is False
    s1 = n["S1_cm270_iv_over_rv252"]
    assert s1["n"] == 40                                  # NOT_IN_R never counts
    assert s1["p50"] == pytest.approx(round(math.sqrt(59.4 / 270) / 0.5, 4))
    assert n["S3_skew_calls_vp"] == {"p50": pytest.approx(0.0), "n": 40}   # 38 at 0.0 vp, 2 at +3.0 vp
    assert n["S4_cm270_iv_over_rv63"]["n"] == 38
    low = rs.night({s: recs[s] for s in rs.R[:34]})       # 34 of 49 = 69.4% < 70%
    assert low["coverage_low"] is True


def test_s3_put_share_and_s5_from_the_sweep():
    recs = {s: _rec([(180, 0.40), (360, 0.50)]) for s in rs.R}
    sweep = {"AG": {"structured": True, "iv_rv": 1.0, "cheap": 1, "wing": "AG270917P00010000", "frame_version": "f"},
             "CC": {"structured": True, "iv_rv": 0.8, "cheap": 1, "wing": "CC270917C00010000", "frame_version": "f"},
             "CF": {"structured": True, "iv_rv": 1.3, "cheap": 0, "wing": "CF270917C00010000", "frame_version": "f"},
             "XXX": {"structured": True, "iv_rv": 9.0, "cheap": 1, "wing": "XXX270917P00010000", "frame_version": "f"}}
    n = rs.night(recs, sweep)
    assert n["S3_put_side_share"] == round(1 / 3, 4)
    assert n["S5_display_only"] == {"share_cheap": round(2 / 3, 4), "median_iv_rv": 1.0, "n": 3, "frame_version": ["f"]}


def _terms(nights: int, *, low_on=(), version_from=None):
    terms: dict[str, dict] = {s: {} for s in rs.R}
    d = date(2026, 11, 3)
    for i in range(nights):
        day = (d + timedelta(days=i)).isoformat()
        for j, s in enumerate(rs.R):
            if i in low_on and j >= 20:
                continue
            v = version_from is not None and i >= version_from
            terms[s][day] = _rec([(180, 0.40 + i / 1000.0), (360, 0.50 + i / 1000.0)],
                                 version=2 if v else None)
    return terms


def test_percentiles_accrue_to_120_in_segment_and_skip_coverage_low():
    rows = rs.series(_terms(122, low_on={5}))
    assert rows[5]["coverage_low"] is True and rows[5]["percentile"]["S1"] == "excluded (coverage_low)"
    assert rows[118]["percentile"]["S1"] == "accruing 118 of 120"     # 119 nights, one of them coverage_low
    assert rows[120]["percentile"]["S1"] == 1.0                        # the 120th counted night; a rising series
    assert rows[121]["percentile"]["S1"] == 1.0


def test_history_trails_250_nights():
    rows = rs.series(_terms(260))
    assert rows[-1]["percentile"]["S1"] == 1.0
    terms = _terms(260)
    for s in rs.R:                                    # make the last night the lowest of the trailing 250 but not of all
        terms[s]["2027-07-20"] = _rec([(180, 0.405), (360, 0.505)])
    last = rs.series(terms)[-1]
    assert last["percentile"]["S1"] == pytest.approx(round(1 / 250, 4))   # night 0..5 fell out of the 250 window


def test_a_term_version_change_starts_a_new_segment():
    rows = rs.series(_terms(130, version_from=10))
    assert rows[9]["segment"].endswith("term v1") and rows[10]["segment"].endswith("term v2")
    assert rows[129]["percentile"]["S1"] == 1.0                        # the 120th v2 night
    assert rows[128]["percentile"]["S1"] == "accruing 119 of 120"       # v2 history restarted at night 10


def test_r_is_the_frozen_49():
    assert len(rs.R) == 49 == len(set(rs.R)) and "ATKR" not in rs.R and rs.R_ADOPTED == "2026-11-18"


def test_nothing_that_decides_imports_the_measurement_modules():
    """§8: nothing in the gates, the backfill rank, sizing or the council imports regime_series (nor the #455 report)."""
    deciders = [ROOT / f for f in ("convexity_gate.py", "structure.py", "paper_loop.py", "backfill.py",
                                   "convexity_sizing.py", "risk.py", "shadow_book.py", "fixed_basket.py",
                                   "gate_dualread.py", "orchestrator.py")] + sorted((ROOT / "council").glob("*.py"))
    pat = re.compile(r"^\s*(from|import)\s+(regime_series|cheap_repriced)\b", re.M)
    hits = [p.name for p in deciders if p.exists() and pat.search(p.read_text())]
    assert hits == []
