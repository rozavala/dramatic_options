"""READ-ONLY #462 market-wide convexity regime series, step 1 (PREREG_CONVEXITY_REGIME_SERIES, FROZEN 2026-11-18). The
thin CLI is ``scripts/probe_regime_series.py``.

Derived at read time from the nightly term records (§6; no writer). One row per sweep night over R, the 49 universe
names frozen at adoption (§3; a name that dies stays in R and stops counting):

- **S1 (series of record):** per name, the ATM IV per expiry (mean of ``atm_c`` / ``atm_p``), total variance σ²·T
  interpolated linearly in days between the two expiries bracketing 270 days, σ₂₇₀ = √(var₂₇₀ / 270), divided by the
  record's ``rv`` (RV252). p25 / p50 / p75 across R with n.
- **S2:** the term slope (``iv_history.term_slope_volpts``), p25 / p50 / p75.
- **S3:** the 25%-OTM skew at the expiry in 180–365 days nearest 270, calls (``otm_c − atm_c``) and puts
  (``otm_p − atm_p``) separately in vol points: p50 and n per side, plus the share of R whose sweep side is the put.
- **S4:** σ₂₇₀ itself, and σ₂₇₀ ÷ RV63 (the #455 capture's ``rv63``), p50.
- **S5 (display only):** the gate's own share cheap and median ``iv_rv`` over R from ``gate_dualread``, with the
  night's ``frame_version``.
- **Coverage guard:** a night counts only if ≥ 70% of R has a 270-day bracket; else ``coverage_low`` (shown, never in a
  percentile history).
- **Percentiles (§5):** each of S1/S2/S4's medians ranked in its own in-segment history (``iv_history.pct_rank``),
  expanding to 250 nights then trailing 250; nothing before 120 in-segment nights ("accruing k of 120"). Segments
  move on R, ``rv_window_days`` or the record's ``term_version`` (a ``frame_version`` move segments S5 only).

Quantiles: ``numpy.percentile`` (linear), rounded to 4 decimals. Measurement only: nothing in the gates, the backfill
rank, sizing or the council may import this module (an import-graph test pins it).
"""

from __future__ import annotations

import math
import sqlite3
from datetime import date

import numpy as np

from iv_history import MIN_PCTILE_SESSIONS, TERM_VERSION, _atm, pct_rank, term_slope_volpts

# R, frozen on the adoption date 2026-11-18 (config.universe.themes, 49 names after ATKR's removal on 11-09). A re-pin is
# a dated amendment and starts a new segment; never topped up.
R_ADOPTED = "2026-11-18"
R = ("AG", "AMSC", "BWXT", "CC", "CCJ", "CDE", "CEG", "CF", "ERO", "ETN", "FCX", "FIG", "FLNC", "FLY", "FRO", "GEV",
     "HBM", "HL", "IRDM", "KKR", "KLAR", "KTOS", "LHX", "LMT", "LUNR", "MOS", "MRK", "NEE", "NNE", "NOC", "NTSK",
     "NVDA", "NXE", "PAAS", "PL", "PWR", "RDW", "RKLB", "RTX", "SMCI", "SMR", "STUB", "TGB", "TITN", "UEC", "UROY",
     "UUUU", "VIAV", "VRT")
CM_DAYS = 270
COVERAGE_MIN = 0.70
HISTORY_MAX = 250
SKEW_LO, SKEW_HI = 180, 365


def sigma_270(rec: dict) -> float | None:
    """The 270-day constant-maturity ATM IV: total variance interpolated linearly between the bracketing expiries."""
    exps = sorted(((e["dte"], _atm(e)) for e in rec.get("expiries", []) if _atm(e) is not None), key=lambda x: x[0])
    exact = [iv for d, iv in exps if d == CM_DAYS]
    if exact:
        return float(exact[0])
    lo = [(d, iv) for d, iv in exps if d < CM_DAYS]
    hi = [(d, iv) for d, iv in exps if d > CM_DAYS]
    if not lo or not hi:
        return None
    (d1, s1), (d2, s2) = lo[-1], hi[0]
    v1, v2 = s1 * s1 * d1, s2 * s2 * d2
    v = v1 + (v2 - v1) * (CM_DAYS - d1) / (d2 - d1)
    return math.sqrt(v / CM_DAYS) if v > 0 else None


def _q(vals: list[float]) -> dict:
    if not vals:
        return {"p25": None, "p50": None, "p75": None, "n": 0}
    p = np.percentile(vals, [25, 50, 75])
    return {"p25": round(float(p[0]), 4), "p50": round(float(p[1]), 4), "p75": round(float(p[2]), 4), "n": len(vals)}


def _skew(rec: dict) -> tuple[float | None, float | None]:
    exps = [e for e in rec.get("expiries", []) if SKEW_LO <= e["dte"] <= SKEW_HI]
    if not exps:
        return None, None
    e = min(exps, key=lambda x: abs(x["dte"] - CM_DAYS))
    c = (e["otm_c"] - e["atm_c"]) * 100.0 if e.get("otm_c") is not None and e.get("atm_c") is not None else None
    p = (e["otm_p"] - e["atm_p"]) * 100.0 if e.get("otm_p") is not None and e.get("atm_p") is not None else None
    return c, p


def night(records: dict[str, dict], sweep: dict[str, dict] | None = None) -> dict:
    """One night's statistics over R. ``records``: {SYMBOL: that night's term record}; ``sweep``: {SYMBOL: the night's
    last OPRA sweep row} for S3's put share and S5."""
    s1, s2, s4, s4_63, sc, sp = [], [], [], [], [], []
    bracket = 0
    versions = set()
    for sym in R:
        rec = records.get(sym)
        if rec is None:
            continue
        versions.add(int(rec.get("term_version", 1)))
        sig = sigma_270(rec)
        if sig is not None:
            bracket += 1
            s4.append(sig)
            if rec.get("rv"):
                s1.append(sig / float(rec["rv"]))
            if rec.get("rv63"):
                s4_63.append(sig / float(rec["rv63"]))
        sl = term_slope_volpts(rec)
        if sl is not None:
            s2.append(sl)
        c, p = _skew(rec)
        if c is not None:
            sc.append(c)
        if p is not None:
            sp.append(p)
    sweep = sweep or {}
    in_r = [sweep[s] for s in R if s in sweep]
    sides = [str(r["wing"])[-9] for r in in_r if r.get("structured") and r.get("wing") and len(str(r["wing"])) >= 15]
    struct = [r for r in in_r if r.get("structured") and r.get("iv_rv") is not None]
    return {
        "coverage": round(bracket / len(R), 4), "coverage_low": bracket / len(R) < COVERAGE_MIN,
        "term_version": max(versions) if versions else TERM_VERSION,
        "S1_cm270_iv_over_rv252": _q(s1), "S2_term_slope_vp": _q(s2),
        "S3_skew_calls_vp": {"p50": _q(sc)["p50"], "n": len(sc)}, "S3_skew_puts_vp": {"p50": _q(sp)["p50"], "n": len(sp)},
        "S3_put_side_share": round(sum(1 for x in sides if x == "P") / len(sides), 4) if sides else None,
        "S4_cm270_iv": {"p50": _q(s4)["p50"], "n": len(s4)},
        "S4_cm270_iv_over_rv63": {"p50": _q(s4_63)["p50"], "n": len(s4_63)},
        "S5_display_only": {
            "share_cheap": round(sum(1 for r in struct if r.get("cheap")) / len(struct), 4) if struct else None,
            "median_iv_rv": _q([float(r["iv_rv"]) for r in struct])["p50"], "n": len(struct),
            "frame_version": sorted({str(r.get("frame_version")) for r in in_r}) or None},
    }


def series(terms: dict[str, dict[str, dict]], sweeps: dict[str, dict[str, dict]] | None = None, *,
           rv_window_days: int = 252) -> list[dict]:
    """One row per night (every date with a term record for an R name), oldest first, with in-segment percentiles."""
    sweeps = sweeps or {}
    nights = sorted({d for sym in R for d in terms.get(sym, {})})
    out: list[dict] = []
    hist: dict[tuple, dict[str, list[float]]] = {}
    for d in nights:
        row = {"date": d, **night({s: terms[s][d] for s in R if d in terms.get(s, {})}, sweeps.get(d))}
        seg = (R_ADOPTED, rv_window_days, row["term_version"])
        row["segment"] = f"R {R_ADOPTED} · rv{rv_window_days} · term v{row['term_version']}"
        h = hist.setdefault(seg, {"S1": [], "S2": [], "S4": []})
        pct = {}
        for key, val in (("S1", row["S1_cm270_iv_over_rv252"]["p50"]), ("S2", row["S2_term_slope_vp"]["p50"]),
                         ("S4", row["S4_cm270_iv"]["p50"])):
            if row["coverage_low"] or val is None:
                pct[key] = "excluded (coverage_low)" if row["coverage_low"] else None
                continue
            h[key].append(val)
            h[key] = h[key][-HISTORY_MAX:]
            k = len(h[key])
            pct[key] = pct_rank(h[key], val) if k >= MIN_PCTILE_SESSIONS else f"accruing {k} of {MIN_PCTILE_SESSIONS}"
        row["percentile"] = pct
        out.append(row)
    return out


def report(conn: sqlite3.Connection, cache, config: dict, *, as_of: date) -> dict:
    from cheap_repriced import load_terms, sweep_rows

    terms = load_terms(cache, R, upto=as_of)
    rows = series(terms, sweep_rows(conn, upto=as_of),
                  rv_window_days=int((config.get("convexity_gate", {}) or {}).get("rv_window_days", 252)))
    return {"as_of": as_of.isoformat(), "R": len(R), "R_adopted": R_ADOPTED, "nights": len(rows), "rows": rows,
            "note": "measurement only; no colour scale, no 'cheap regime'; never a gate or quota input"}


def render(rep: dict) -> str:
    lines = [f"#462 convexity regime series (R = {rep['R']} names frozen {rep['R_adopted']}; as of {rep['as_of']})"]
    if not rep["rows"]:
        return "\n".join(lines + ["no term records yet"])
    last = rep["rows"][-1]
    s1 = last["S1_cm270_iv_over_rv252"]
    lines.append(f"nights {rep['nights']}; latest {last['date']}: S1 p25/p50/p75 {s1['p25']}/{s1['p50']}/{s1['p75']} "
                 f"(n {s1['n']}), coverage {last['coverage']}{' LOW' if last['coverage_low'] else ''}, percentile "
                 f"{last['percentile']['S1']}")
    lines.append(f"S2 slope p50 {last['S2_term_slope_vp']['p50']} vp · S3 skew calls {last['S3_skew_calls_vp']['p50']}"
                 f" / puts {last['S3_skew_puts_vp']['p50']} vp, put share {last['S3_put_side_share']} · S4 σ270 p50 "
                 f"{last['S4_cm270_iv']['p50']}, ÷RV63 {last['S4_cm270_iv_over_rv63']['p50']}")
    lines.append(f"S5 (display only): share cheap {last['S5_display_only']['share_cheap']}, median iv_rv "
                 f"{last['S5_display_only']['median_iv_rv']}")
    lines.append(rep["note"])
    return "\n".join(lines)
