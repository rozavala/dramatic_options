"""Gate pass-reason audit (#454, M2) — a READ-ONLY measurement of why the cheapness gate passes what it passes.

PREREG_THEMATIC_CONVEXITY §1/§4 call the cheapness gate (``IV_atm / RV252 <= iv_rv_max`` and ``wing − ATM <=
otm_skew_max_volpts``) "the edge", yet the weekly sweeps pass almost every structured name (2026-11-08: universe
structured 35 → gate-cheap 34, records/2026-11-08_sunday_w45.md). The suspected mechanism: trailing 252-day realized
vol is inflated for names that recently moved, so they read cheap for the wrong reason. This module measures that and
nothing else. It changes no rule, adds no config key, renders no dashboard panel, and is never imported by the loop.

Per sweep date, over the OPRA arm of ``gate_dualread`` (the gate of record; the last read per symbol per date, as
``iv_history.gate_history`` takes it, but keeping the non-structured rows so the vetoes can be classified):

a. the pass rate among structured rows, and the min/quartiles/max of ``iv_rv`` and ``otm_skew`` against the
   thresholds, with the headroom of the median pass;
b. realized vol recomputed from closes AS OF the sweep date (``convexity_gate.realized_vol`` at 252, 63 and 21),
   ATM IV backed out as ``iv_rv × RV252``, then ``IV/RV63``, ``IV/RV21`` and the trailing 63-session absolute return.
   A pass "depends on elevated trailing RV" when ``IV/RV252 <= iv_rv_max`` but ``IV/RV63 > iv_rv_max``; the reverse
   (an iv/rv veto that would read cheap on RV63) is counted too;
c. which leg binds for each veto: iv_rv, skew, both, a structured row the gate failed closed on, or a non-structured
   row (broken down by its ``note``);
d. a HYPOTHETICAL table: how many names would pass if only the cheapest 25/50/75% by ``iv_rv`` were admitted (the
   skew leg still applied). A table only — it proposes nothing.

Cohorts: the config universe (``config.universe.themes`` members) vs every other name the OPRA arm read that date
(inline-evaluated candidates outside the universe). The weekly miss-baserate MARKET sample is not in
``gate_dualread``: ``scripts/probe_miss_baserate.py`` writes it only to the sealed ``records/miss_baserate/
ledger.csv``, and the sweep that writes ``gate_dualread`` (``gate_dualread.sweep_universe``, called from
``orchestrator.py`` with ``_scan_universe(config)``) covers the universe only. Its sealed keys are never joined
to symbols here (PREREG_MISS_BASERATE §3).

Point in time: only closes whose bar date (New York) is on or before the sweep date are used, whatever the closes
source returns. A name with no bars, or fewer than 253 closes by that date, is counted as UNKNOWN for part (b); no
value is ever substituted.

The dated record (#454) needs the DEV database. Run on DEV, from the live checkout:

    cd ~/dramatic_options && PYTHONPATH=. venv/bin/python scripts/probe_gate_pass_reasons.py --last 5
    cd ~/dramatic_options && PYTHONPATH=. venv/bin/python scripts/probe_gate_pass_reasons.py --last 5 --json
"""

from __future__ import annotations

import math
import sqlite3
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from convexity_gate import realized_vol

_ET = ZoneInfo("America/New_York")
RV_WINDOWS = (252, 63, 21)
RET_WINDOW = 63
HYPOTHETICAL_SHARES = (0.25, 0.50, 0.75)
COHORTS = ("universe", "other")
MARKET_SAMPLE_NOTE = ("The miss-baserate market sample is not in gate_dualread (it is written only to the sealed "
                      "records/miss_baserate/ledger.csv); 'other' is the non-universe names the OPRA arm read "
                      "inline, not the market sample.")

# closes_for(symbol, sweep_date) -> [(bar timestamp, close)] or None when the source has no bars for the name.
ClosesFor = Callable[[str, date], "list[tuple[datetime, float]] | None"]


@dataclass(frozen=True)
class GateRead:
    """One OPRA-arm read: the last row for (symbol, sweep date)."""

    symbol: str
    sweep_date: str
    source: str | None
    structured: bool
    iv_rv: float | None
    otm_skew: float | None
    cheap: bool
    note: str | None


# ── inputs ────────────────────────────────────────────────────────────────────────────────────────
def last_reads(conn: sqlite3.Connection) -> dict[str, list[GateRead]]:
    """{sweep date: [GateRead]} from the OPRA arm, the LAST read per symbol per date (by id), symbols sorted.

    Unlike ``iv_history.gate_history`` this keeps non-structured rows: a veto's binding leg includes "no structure"."""
    by: dict[str, dict[str, GateRead]] = {}
    for r in conn.execute(
            "SELECT symbol, substr(evaluated_at, 1, 10), source, structured, iv_rv, otm_skew, cheap, note "
            "FROM gate_dualread WHERE feed = 'opra' ORDER BY id"):
        sym, d = str(r[0]).upper(), str(r[1])
        by.setdefault(d, {})[sym] = GateRead(
            symbol=sym, sweep_date=d, source=r[2], structured=bool(r[3]),
            iv_rv=None if r[4] is None else float(r[4]), otm_skew=None if r[5] is None else float(r[5]),
            cheap=bool(r[6]), note=r[7])
    return {d: [rows[s] for s in sorted(rows)] for d, rows in sorted(by.items())}


def universe_symbols(config: dict) -> set[str]:
    """The config universe, read the way ``orchestrator._scan_universe`` reads it (``_``-prefixed keys are comments)."""
    themes = (config.get("universe", {}) or {}).get("themes", {}) or {}
    return {str(s).upper() for k, v in themes.items() if not str(k).startswith("_") for s in v}


def _bar_date(ts: datetime) -> date:
    """A bar's trading date in New York (a naive timestamp is taken as UTC, as the cache stores it)."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ZoneInfo("UTC"))
    return ts.astimezone(_ET).date()


def closes_on_or_before(series: Iterable[tuple[datetime, float]], sweep_date: date) -> list[float]:
    """The closes dated on or before ``sweep_date``, oldest first. The point-in-time guard lives HERE, not in the
    source: a source that returns a later bar must not change the reading (tests/test_gate_audit lookahead probe)."""
    kept = sorted((ts, float(c)) for ts, c in series if c is not None and _bar_date(ts) <= sweep_date)
    return [c for _, c in kept]


# ── readings ──────────────────────────────────────────────────────────────────────────────────────
def quantiles(values: list[float]) -> dict[str, float | None]:
    """min / q1 / median / q3 / max by linear interpolation (numpy's default); all None when empty."""
    xs = sorted(values)
    if not xs:
        return {"n": 0, "min": None, "q1": None, "median": None, "q3": None, "max": None}

    def q(p: float) -> float:
        pos = p * (len(xs) - 1)
        lo = math.floor(pos)
        hi = min(lo + 1, len(xs) - 1)
        return round(xs[lo] + (xs[hi] - xs[lo]) * (pos - lo), 4)

    return {"n": len(xs), "min": round(xs[0], 4), "q1": q(0.25), "median": q(0.5), "q3": q(0.75),
            "max": round(xs[-1], 4)}


def rv_reading(closes: list[float] | None, iv_rv: float, iv_rv_max: float) -> dict[str, Any]:
    """Part (b) for one structured row. ``closes`` must already be point-in-time.

    Unknown (``status`` != "ok") when there are fewer than 253 closes: ``realized_vol`` would quietly compute RV252
    over a shorter window, and a short-window number labelled 252 is exactly the substitution this audit refuses."""
    if not closes:
        return {"status": "unknown_no_bars"}
    if len(closes) < max(RV_WINDOWS) + 1:
        return {"status": "unknown_short_history", "n_closes": len(closes)}
    rv = {w: realized_vol(closes, window=w) for w in RV_WINDOWS}
    if any(v is None or v <= 0 for v in rv.values()):
        return {"status": "unknown_no_rv", "n_closes": len(closes)}
    iv = iv_rv * rv[252]
    ivrv63, ivrv21 = iv / rv[63], iv / rv[21]
    return {
        "status": "ok",
        "rv252": round(rv[252], 4), "rv63": round(rv[63], 4), "rv21": round(rv[21], 4),
        "atm_iv": round(iv, 4), "iv_rv252": round(iv_rv, 4), "iv_rv63": round(ivrv63, 4), "iv_rv21": round(ivrv21, 4),
        "abs_ret63": round(abs(closes[-1] / closes[-1 - RET_WINDOW] - 1.0), 4),
        # the pass that exists only because the 252-day window still holds an old, large move
        "elevated_rv_pass": iv_rv <= iv_rv_max < ivrv63,
        # the reverse: vetoed on the 252-day read, cheap on the recent one
        "recent_rv_cheap_veto": ivrv63 <= iv_rv_max < iv_rv,
    }


def veto_leg(r: GateRead, iv_rv_max: float, skew_max: float) -> str | None:
    """Which leg binds for a veto (None for a pass). The legs mirror ``is_cheap_convexity`` exactly."""
    if r.cheap:
        return None
    if not r.structured:
        return "not_structured"
    if r.iv_rv is None or r.otm_skew is None:
        return "fail_closed_structured"  # the gate's missing-input fail-close (no rv / atm iv / wing iv)
    iv_bad, skew_bad = r.iv_rv > iv_rv_max, r.otm_skew > skew_max
    if iv_bad and skew_bad:
        return "both"
    if iv_bad:
        return "iv_rv"
    if skew_bad:
        return "skew"
    return "unexplained"  # recorded cheap=0 with both legs inside: should not happen; surfaced, never hidden


def note_class(note: str | None) -> str:
    """The class prefix of a non-structured row's note (``entitlement:`` / ``transient:`` / a structural reason)."""
    if not note:
        return "(no note)"
    return note.split(":", 1)[0].strip() or "(no note)"


def hypothetical_cutoffs(rows: list[GateRead], skew_max: float) -> list[dict[str, Any]]:
    """HYPOTHETICAL: admit only the cheapest ``share`` of structured rows by iv_rv (ceil, ties in symbol order), the
    skew leg still applied. A measurement of how much the iv/rv leg could separate — not a proposed rule."""
    scored = sorted((r for r in rows if r.structured and r.iv_rv is not None), key=lambda r: (r.iv_rv, r.symbol))
    out = []
    for share in HYPOTHETICAL_SHARES:
        k = math.ceil(share * len(scored))
        kept = scored[:k]
        out.append({"share": share, "admitted_by_iv_rv": k,
                    "iv_rv_cut": round(kept[-1].iv_rv, 4) if kept else None,
                    "pass_count": sum(1 for r in kept if r.otm_skew is not None and r.otm_skew <= skew_max)})
    return out


def cohort_report(rows: list[GateRead], closes_for: ClosesFor, sweep_date: date, iv_rv_max: float,
                  skew_max: float) -> dict[str, Any]:
    """Parts (a)–(d) for one cohort on one sweep date."""
    structured = [r for r in rows if r.structured]
    passes = [r for r in structured if r.cheap]
    names: list[dict[str, Any]] = []
    rv_status: Counter[str] = Counter()
    for r in structured:
        entry: dict[str, Any] = {"symbol": r.symbol, "cheap": r.cheap, "iv_rv": r.iv_rv, "otm_skew": r.otm_skew}
        if r.iv_rv is None:
            entry["rv"] = {"status": "unknown_no_iv_rv"}
        else:
            try:
                series = closes_for(r.symbol, sweep_date)
            except Exception:  # noqa: BLE001 — a cache miss or unreadable payload is an unknown, never a value
                series = None
            closes = closes_on_or_before(series, sweep_date) if series else None
            entry["rv"] = rv_reading(closes, r.iv_rv, iv_rv_max)
        rv_status[entry["rv"]["status"]] += 1
        names.append(entry)
    known = [n for n in names if n["rv"]["status"] == "ok"]
    known_pass = [n for n in known if n["cheap"]]
    legs = Counter(leg for r in rows if (leg := veto_leg(r, iv_rv_max, skew_max)) is not None)
    pass_ivrv = quantiles([r.iv_rv for r in passes if r.iv_rv is not None])
    pass_skew = quantiles([r.otm_skew for r in passes if r.otm_skew is not None])
    return {
        "n_read": len(rows), "n_structured": len(structured), "n_pass": len(passes),
        "pass_rate": round(len(passes) / len(structured), 4) if structured else None,
        "iv_rv": quantiles([r.iv_rv for r in structured if r.iv_rv is not None]),
        "otm_skew": quantiles([r.otm_skew for r in structured if r.otm_skew is not None]),
        "pass_headroom": {
            "iv_rv": None if pass_ivrv["median"] is None else round(iv_rv_max - pass_ivrv["median"], 4),
            "otm_skew": None if pass_skew["median"] is None else round(skew_max - pass_skew["median"], 4)},
        "rv": {
            "status": dict(sorted(rv_status.items())),
            "unknown": sum(v for k, v in rv_status.items() if k != "ok"),
            "iv_rv63": quantiles([n["rv"]["iv_rv63"] for n in known]),
            "iv_rv21": quantiles([n["rv"]["iv_rv21"] for n in known]),
            "abs_ret63": quantiles([n["rv"]["abs_ret63"] for n in known]),
            "passes_known": len(known_pass),
            "elevated_rv_pass": sum(1 for n in known_pass if n["rv"]["elevated_rv_pass"]),
            "elevated_rv21_pass": sum(1 for n in known_pass if n["rv"]["iv_rv21"] > iv_rv_max),
            "recent_rv_cheap_veto": sum(1 for n in known if n["rv"]["recent_rv_cheap_veto"]),
        },
        "veto_leg": dict(sorted(legs.items())),
        "not_structured_notes": dict(sorted(Counter(note_class(r.note) for r in rows if not r.structured).items())),
        "hypothetical_cutoffs": hypothetical_cutoffs(rows, skew_max),
        "names": names,
    }


def audit(conn: sqlite3.Connection, config: dict, closes_for: ClosesFor, *,
          dates: Iterable[str] | None = None, last: int | None = None) -> dict[str, Any]:
    """The whole report. ``dates`` restricts to those sweep dates; ``last`` keeps the most recent N of what remains."""
    gate = config.get("convexity_gate", {}) or {}
    iv_rv_max, skew_max = float(gate["iv_rv_max"]), float(gate["otm_skew_max_volpts"])
    universe = universe_symbols(config)
    reads = last_reads(conn)
    wanted = sorted(reads if dates is None else set(dates) & set(reads))
    if last is not None:
        wanted = wanted[-last:] if last > 0 else []
    sweeps = []
    for d in wanted:
        sd = date.fromisoformat(d)
        rows = reads[d]
        split = {"universe": [r for r in rows if r.symbol in universe],
                 "other": [r for r in rows if r.symbol not in universe]}
        sweeps.append({"date": d, "cohorts": {c: cohort_report(split[c], closes_for, sd, iv_rv_max, skew_max)
                                              for c in COHORTS}})
    return {"thresholds": {"iv_rv_max": iv_rv_max, "otm_skew_max_volpts": skew_max},
            "universe_size": len(universe), "market_sample": MARKET_SAMPLE_NOTE,
            "missing_dates": sorted(set(dates or ()) - set(reads)), "sweeps": sweeps}


# ── rendering ─────────────────────────────────────────────────────────────────────────────────────
def _fmt(v: Any) -> str:
    if v is None:
        return "-"
    return f"{v:.2f}" if isinstance(v, float) else str(v)


def _dist(q: dict) -> str:
    return " / ".join(_fmt(q[k]) for k in ("min", "q1", "median", "q3", "max"))


def render(report: dict[str, Any], *, names: bool = False) -> str:
    th = report["thresholds"]
    out = [f"Gate pass-reason audit (#454) — read-only. Thresholds: iv_rv <= {th['iv_rv_max']:g}, "
           f"otm_skew <= {th['otm_skew_max_volpts']:g} vp (config.json:convexity_gate). "
           f"Universe {report['universe_size']} names.",
           report["market_sample"]]
    if report["missing_dates"]:
        out.append(f"No OPRA reads on: {', '.join(report['missing_dates'])}")
    if not report["sweeps"]:
        out.append("No sweep dates selected.")
    for s in report["sweeps"]:
        out.append(f"\n== {s['date']} ==")
        for c in COHORTS:
            r = s["cohorts"][c]
            rv = r["rv"]
            out.append(f"[{c}] read {r['n_read']}  structured {r['n_structured']}  pass {r['n_pass']}  "
                       f"pass rate {_fmt(r['pass_rate'])}")
            if not r["n_read"]:
                continue
            out.append(f"  iv_rv    min/q1/med/q3/max {_dist(r['iv_rv'])}   median-pass headroom "
                       f"{_fmt(r['pass_headroom']['iv_rv'])}")
            out.append(f"  otm_skew min/q1/med/q3/max {_dist(r['otm_skew'])}   median-pass headroom "
                       f"{_fmt(r['pass_headroom']['otm_skew'])} vp")
            out.append(f"  IV/RV63  {_dist(rv['iv_rv63'])}   IV/RV21 {_dist(rv['iv_rv21'])}   "
                       f"|ret63| {_dist(rv['abs_ret63'])}")
            out.append(f"  passes with known bars {rv['passes_known']}: depend on elevated RV252 (IV/RV63 > max) "
                       f"{rv['elevated_rv_pass']}; IV/RV21 > max {rv['elevated_rv21_pass']}.  "
                       f"iv_rv vetoes cheap on RV63 {rv['recent_rv_cheap_veto']}")
            unknown = {k: v for k, v in rv["status"].items() if k != "ok"}
            out.append(f"  unknown (bars) {rv['unknown']}" + (f" {unknown}" if unknown else ""))
            out.append(f"  veto leg {r['veto_leg'] or '{}'}   not-structured notes {r['not_structured_notes'] or '{}'}")
            hyp = "; ".join(f"cheapest {int(h['share'] * 100)}% → {h['admitted_by_iv_rv']} admitted "
                            f"(cut {_fmt(h['iv_rv_cut'])}), {h['pass_count']} pass"
                            for h in r["hypothetical_cutoffs"])
            out.append(f"  HYPOTHETICAL cut-offs (not a rule): {hyp}")
            if names:
                for n in r["names"]:
                    x = n["rv"]
                    flag = ("ELEVATED-RV PASS" if x.get("elevated_rv_pass")
                            else "recent-rv-cheap veto" if x.get("recent_rv_cheap_veto") else "")
                    out.append(f"    {n['symbol']:<6} cheap={int(n['cheap'])} iv/rv252 {_fmt(n['iv_rv'])} "
                               f"iv/rv63 {_fmt(x.get('iv_rv63'))} iv/rv21 {_fmt(x.get('iv_rv21'))} "
                               f"|ret63| {_fmt(x.get('abs_ret63'))} {x['status'] if x['status'] != 'ok' else flag}")
    return "\n".join(out)
