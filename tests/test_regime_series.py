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
    assert rs.night(recs) == rs.night(recs, population=rs.R)   # the series of record is R by default (#539 review)
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


# ── the dashboard card's panel (#462 §8): synthetic records only; never the live series ────────────────────────────

def _write_terms(cache, nights: int, *, low_last: bool = False, start=date(2026, 11, 3)):
    from datetime import datetime

    from iv_history import TERM_SOURCE

    for j, s in enumerate(rs.R):
        recs = []
        for i in range(nights):
            if low_last and i == nights - 1 and j >= 20:      # the last night: only 20 of 49 names (41% < 70%)
                continue
            day = (start + timedelta(days=i)).isoformat()
            r = _rec([(180, 0.40 + i / 1000.0), (360, 0.50 + i / 1000.0)], rv=0.5, rv63=0.25, skew=(180, 0.45, 0.50))
            r["ts"], r["symbol"] = f"{day}T20:45:00+00:00", s
            recs.append(r)
        if recs:
            cache.write(TERM_SOURCE, s, recs, coverage_from=datetime.fromisoformat(recs[0]["ts"]),
                        coverage_through=datetime.fromisoformat(recs[-1]["ts"]))


def _cfg(extra=()):
    return {"universe": {"themes": {"t": list(rs.R[:20]) + list(extra)}}, "convexity_gate": {"rv_window_days": 252}}


def _panel(tmp_path, convexity_db, nights, **kw):
    from data.cache import PointInTimeCache

    cache = PointInTimeCache(tmp_path / "c")
    _write_terms(cache, nights, **kw)
    return rs.panel(convexity_db, PointInTimeCache(tmp_path / "c", offline=True), _cfg(("NEWCO",)),
                    as_of=date(2026, 11, 3) + timedelta(days=nights - 1))


def test_panel_before_the_first_record_is_honest_unknown(convexity_db, tmp_path):
    from data.cache import PointInTimeCache

    p = rs.panel(convexity_db, PointInTimeCache(tmp_path / "c", offline=True), _cfg(), as_of=date(2026, 11, 20))
    assert p["status"] == "no term records yet" and "S1" not in p and p["nights"] == 0 and p["R"] == 49


def test_panel_accruing_state_reads_k_of_120_and_no_percentile(convexity_db, tmp_path):
    p = _panel(tmp_path, convexity_db, 3)
    assert p["status"] == "ok" and p["date"] == "2026-11-05" and p["nights"] == 3 and p["coverage_low"] is False
    assert p["S1_percentile"] is None and p["S1_accruing"] == {"k": 3, "of": 120}
    # night 2: σ(180)=0.402, σ(360)=0.502 -> the 270-day interpolation over RV252 0.5; every name identical
    assert p["S1"]["n"] == 49 and p["S1"]["p25"] == p["S1"]["p50"] == p["S1"]["p75"]
    exp = math.sqrt((0.402**2 * 180 + (0.502**2 * 360 - 0.402**2 * 180) * 0.5) / 270) / 0.5
    assert p["S1"]["p50"] == pytest.approx(round(exp, 4))
    assert [x["d"] for x in p["spark"]] == ["2026-11-03", "2026-11-04", "2026-11-05"] and not any(x["low"] for x in p["spark"])
    assert p["S2_term_slope_vp_p50"] == pytest.approx(10.0) and p["S3_skew_calls_vp_p50"] == pytest.approx(4.8, abs=0.2)
    assert p["S4_cm270_iv_p50"] is not None and p["S4_cm270_iv_over_rv63_p50"] == pytest.approx(
        round(p["S4_cm270_iv_p50"] / 0.25, 4), abs=1e-3)
    assert p["S5_display_only"]["n"] == 0                                 # no sweep rows: S5 reads as unknown, not zero
    live = p["live_companion_display_only"]                               # 20 of the 21 current names have records
    assert live["names"] == 21 and live["coverage"] == round(20 / 21, 4) and live["S1"]["n"] == 20


def test_panel_prints_a_percentile_only_from_the_120th_in_segment_night(convexity_db, tmp_path):
    assert _panel(tmp_path / "a", convexity_db, 119)["S1_percentile"] is None
    assert _panel(tmp_path / "a", convexity_db, 119)["S1_accruing"] == {"k": 119, "of": 120}
    p = _panel(tmp_path / "b", convexity_db, 120)
    assert p["S1_accruing"] is None and p["S1_percentile"] == 1.0         # a rising series ranks at its own top
    assert len(p["spark"]) == 120


def test_panel_coverage_low_night_keeps_its_numbers_but_no_percentile(convexity_db, tmp_path):
    p = _panel(tmp_path, convexity_db, 122, low_last=True)
    assert p["coverage_low"] is True and p["coverage"] == round(20 / 49, 4) and p["coverage_min"] == 0.70
    assert p["S1_percentile"] is None and p["S1"]["n"] == 20                        # shown, excluded from the history
    assert p["S1_accruing"] is None and p["spark"][-1]["low"] is True               # 121 counted nights: past the minimum
    assert [x["low"] for x in p["spark"]].count(True) == 1


def test_panel_wiring_is_fail_soft_and_reads_nothing_after_as_of(convexity_db, tmp_path):
    import dashboard_data as dd
    from data.cache import PointInTimeCache

    _write_terms(PointInTimeCache(tmp_path / "c"), 5)
    early = dd.regime_series_panel(convexity_db, tmp_path / "c", _cfg(), as_of=date(2026, 11, 4))
    assert early["date"] == "2026-11-04" and early["nights"] == 2                 # the later records never load
    assert dd.regime_series_panel(convexity_db, tmp_path / "none", _cfg(), as_of=date(2026, 11, 4))["status"] == \
        "no term records yet"
    cfg, day = _cfg(), date(2026, 11, 4)
    assert "error" in dd.safe(dd.regime_series_panel, None, tmp_path / "c", cfg, as_of=day)


def test_panel_carries_the_measurement_only_note(convexity_db, tmp_path):
    p = _panel(tmp_path, convexity_db, 2)
    assert p["note"].startswith("measurement only") and "never a gate or quota input" in p["note"]
