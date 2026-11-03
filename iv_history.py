"""IV history telemetry (D4 step 1, records/2026-11-03_profit_program_DRAFTS.md) — measurement only.

Three option-side readings the literature says carry information (records/2026-11-03_literature_review.md §1),
built from data we accrue ourselves. Nothing here is gated or rendered to the council; it is a dashboard panel
and a CLI.

1. **Own-history percentile of the gate's IV/RV and skew** — from ``gate_dualread`` (the OPRA arm), the nightly
   whole-universe sweep that has been the IV baseline of record since 2026-06-10. Where a name's IV/RV sits in
   its own history (Goyal & Saretto's cheapness, made name-relative). Null until ``MIN_PCTILE_SESSIONS``.
2. **Term slope** — ATM IV at the longest expiry ≤ 550 d minus ATM IV at the nearest expiry ≥ 30 d, in vol
   points (Vasquez 2017). From the compact ``iv_term_snapshot`` record the sweep writes from 2026-11-03.
3. **21-session ΔIV, ATM call and ATM put**, at the expiry nearest 180 d (An, Ang, Bali & Cakici 2014: rising
   call IV leads the stock up, rising put IV leads it down). Same source; null until 21 sessions accrue.

The term record is deliberately small (per expiry: ATM call/put IV and the 25%-OTM call/put IV), unlike the
entry-path ``option_chain_snapshot`` full surface, because it is rewritten nightly for every universe name.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from typing import Any

from convexity_gate import Contract, occ_root

TERM_SOURCE = "iv_term_snapshot"
MIN_PCTILE_SESSIONS = 120
DIV_LAG_SESSIONS = 21
TERM_MIN_DTE, TERM_MAX_DTE, CONST_DTE = 30, 550, 180


# ── the nightly term record (written by gate_dualread.sweep_universe) ───────────────────────────
def _iv_near(chain: list[Contract], *, kind: str, expiry: date, target: float, root: str) -> float | None:
    cands = [c for c in chain if c.kind == kind and c.expiry == expiry and c.iv and c.iv > 0
             and occ_root(c.symbol) == root]
    if not cands:
        return None
    return float(min(cands, key=lambda c: abs(c.strike - target)).iv)


def term_record(symbol: str, chain: list[Contract], *, spot: float | None, rv: float | None,
                as_of_dt: datetime) -> dict:
    """Per expiry in [30, 550] d: ATM call/put IV and 25%-OTM call/put IV (standard OCC class only)."""
    as_of = as_of_dt.date()
    rows = []
    if spot and spot > 0:
        root = symbol.upper().replace(".", "")
        for exp in sorted({c.expiry for c in chain}):
            dte = (exp - as_of).days
            if not TERM_MIN_DTE <= dte <= TERM_MAX_DTE:
                continue
            r = {"expiry": exp.isoformat(), "dte": dte,
                 "atm_c": _iv_near(chain, kind="C", expiry=exp, target=spot, root=root),
                 "atm_p": _iv_near(chain, kind="P", expiry=exp, target=spot, root=root),
                 "otm_c": _iv_near(chain, kind="C", expiry=exp, target=spot * 1.25, root=root),
                 "otm_p": _iv_near(chain, kind="P", expiry=exp, target=spot * 0.75, root=root)}
            if any(r[k] is not None for k in ("atm_c", "atm_p")):
                rows.append(r)
    return {"ts": as_of_dt.isoformat(), "symbol": symbol.upper(), "spot": spot, "rv": rv, "expiries": rows}


def persist_term_record(cache, record: dict, as_of_dt: datetime) -> None:
    """Read-append-write, one record per calendar day (a same-day re-run replaces it)."""
    sym = record["symbol"]
    existing = cache.read_between(TERM_SOURCE, sym, None, as_of_dt)
    day = as_of_dt.date().isoformat()
    records = [r for r in existing if str(r["ts"])[:10] != day] + [record]
    cache.write(TERM_SOURCE, sym, records, coverage_from=datetime.fromisoformat(records[0]["ts"]),
                coverage_through=as_of_dt)


# ── readings ──────────────────────────────────────────────────────────────────────────────────
def pct_rank(history: list[float], value: float) -> float:
    """Share of the history at or below ``value`` (the latest value included), in (0, 1]."""
    return round(sum(1 for h in history if h <= value) / len(history), 4)


def gate_history(conn: sqlite3.Connection) -> dict[str, list[tuple[str, float, float | None]]]:
    """{symbol: [(date, iv_rv, otm_skew)]} from the OPRA arm, the last read per date, oldest first."""
    by: dict[str, dict[str, tuple[float, float | None]]] = {}
    for r in conn.execute(
            "SELECT symbol, substr(evaluated_at, 1, 10) AS d, iv_rv, otm_skew FROM gate_dualread "
            "WHERE feed = 'opra' AND structured = 1 AND iv_rv IS NOT NULL ORDER BY id"):
        by.setdefault(str(r[0]).upper(), {})[r[1]] = (float(r[2]), None if r[3] is None else float(r[3]))
    return {s: [(d, v[0], v[1]) for d, v in sorted(days.items())] for s, days in by.items()}


def _atm(e: dict) -> float | None:
    vals = [v for v in (e.get("atm_c"), e.get("atm_p")) if v is not None]
    return sum(vals) / len(vals) if vals else None


def term_slope_volpts(rec: dict) -> float | None:
    exps = [e for e in rec.get("expiries", []) if _atm(e) is not None]
    if len(exps) < 2:
        return None
    near = min(exps, key=lambda e: e["dte"])
    far = max(exps, key=lambda e: e["dte"])
    if far["dte"] <= near["dte"]:
        return None
    return round((_atm(far) - _atm(near)) * 100.0, 2)


def _const(rec: dict, key: str) -> float | None:
    exps = [e for e in rec.get("expiries", []) if e.get(key) is not None]
    if not exps:
        return None
    return float(min(exps, key=lambda e: abs(e["dte"] - CONST_DTE))[key])


def delta_iv_volpts(records: list[dict], key: str, lag: int = DIV_LAG_SESSIONS) -> float | None:
    """Change in ``key`` (atm_c / atm_p at the expiry nearest 180 d) over ``lag`` recorded sessions."""
    if len(records) <= lag:
        return None
    now, then = _const(records[-1], key), _const(records[-1 - lag], key)
    if now is None or then is None:
        return None
    return round((now - then) * 100.0, 2)


def name_reading(symbol: str, hist: list[tuple[str, float, float | None]], term: list[dict]) -> dict[str, Any]:
    n = len(hist)
    out: dict[str, Any] = {"symbol": symbol, "sessions": n, "last_date": hist[-1][0] if hist else None,
                           "iv_rv": None, "iv_rv_pct": None, "skew": None, "skew_pct": None,
                           "term_sessions": len(term), "term_slope": None, "d_iv_call": None, "d_iv_put": None}
    if hist:
        _, ivrv, skew = hist[-1]
        out["iv_rv"], out["skew"] = round(ivrv, 4), (None if skew is None else round(skew, 2))
        if n >= MIN_PCTILE_SESSIONS:
            out["iv_rv_pct"] = pct_rank([h[1] for h in hist], ivrv)
            skews = [h[2] for h in hist if h[2] is not None]
            if skew is not None and len(skews) >= MIN_PCTILE_SESSIONS:
                out["skew_pct"] = pct_rank(skews, skew)
    if term:
        out["term_slope"] = term_slope_volpts(term[-1])
        out["d_iv_call"] = delta_iv_volpts(term, "atm_c")
        out["d_iv_put"] = delta_iv_volpts(term, "atm_p")
    return out


def panel(conn: sqlite3.Connection, cache=None, *, now: datetime | None = None) -> dict:
    """Per-name readings for every name the sweep has read. ``cache`` (a PointInTimeCache) supplies the term
    records; without it the term columns stay null."""
    now = now or datetime.now().astimezone()
    hist = gate_history(conn)
    rows = []
    for sym in sorted(hist):
        term = []
        if cache is not None:
            try:
                term = cache.read_between(TERM_SOURCE, sym, None, now)
            except Exception:  # noqa: BLE001 — a missing or unreadable record is a null column, never an error
                term = []
        rows.append(name_reading(sym, hist[sym], term))
    sessions = max((r["sessions"] for r in rows), default=0)
    term_sessions = max((r["term_sessions"] for r in rows), default=0)
    return {
        "rows": rows,
        "min_pctile_sessions": MIN_PCTILE_SESSIONS, "div_lag_sessions": DIV_LAG_SESSIONS,
        "max_sessions": sessions, "max_term_sessions": term_sessions,
        "status": (f"percentiles live ({sessions} sessions)" if sessions >= MIN_PCTILE_SESSIONS
                   else f"percentiles accruing: {sessions} of {MIN_PCTILE_SESSIONS} sessions"),
        "note": "Telemetry only (D4 step 1): nothing here gates an entry or reaches a council prompt.",
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    from config_loader import load_config
    from data.cache import PointInTimeCache
    from state import get_db

    ap = argparse.ArgumentParser(description="IV history telemetry (D4)")
    ap.parse_args(argv)
    config = load_config()
    conn = get_db(config)
    cache = PointInTimeCache(config.get("cache", {}).get("dir", "data/cache"), offline=True)
    p = panel(conn, cache)
    print(p["status"])
    print(f"{'sym':6} {'n':>4} {'iv/rv':>6} {'pct':>5} {'skew':>6} {'pct':>5} {'slope':>6} {'dIVc':>6} {'dIVp':>6}")
    f = lambda v, w=6: ("-" if v is None else f"{v:.2f}").rjust(w)  # noqa: E731
    for r in p["rows"]:
        print(f"{r['symbol']:6} {r['sessions']:>4} {f(r['iv_rv'])} {f(r['iv_rv_pct'], 5)} {f(r['skew'])} "
              f"{f(r['skew_pct'], 5)} {f(r['term_slope'])} {f(r['d_iv_call'])} {f(r['d_iv_put'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
