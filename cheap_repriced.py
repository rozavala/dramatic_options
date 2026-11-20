"""READ-ONLY #455 cheap-then-repriced report (PREREG_CHEAP_THEN_REPRICED §4.2–§7, FROZEN 2026-11-18). The thin CLI is
``scripts/probe_cheap_repriced.py``.

No ledger file and no writer (§4.3): the unit rows are derived on every read from two persisted inputs,
``gate_dualread`` (the OPRA sweep rows, append-only) and the nightly term records (``iv_term_snapshot``), whose
``quotes`` field (the §4.1 capture) carries the same contract's bid / ask / IV night after night.

- **Unit:** one row per universe name per ISO week; the unit date is that week's first sweep date. Exposure is that
  date's last OPRA sweep row (structured, with an ``iv_rv``). **The cohort at t is the sweep's own population at t**
  (every name with an OPRA ``source='sweep'`` row that date — the nightly sweep covers the scan universe, no benchmark,
  no skip), never today's config, so a later universe edit cannot re-cut a past date's terciles (§4.2, §10). Only unit dates on or after the first night the capture
  is live (a term record with ``quotes``) give rows (§4.2 first row).
- **Excluded from every read:** a wing more than 40% OTM at t (from the OCC strike and the record's spot), and a row
  with no term record at t. Each counted.
- **Splits (§5):** E1 the cheapest ``iv_rv`` tercile of the unit date (the lowest ⌈n/3⌉ rows, ties broken by
  symbol) vs the rest; E2 among gate-cheap rows, RV252-dependent (``atm_iv / rv63 > iv_rv_max``, ``atm_iv = iv_rv ×
  rv``) vs the rest, rows without ``rv63`` counted and excluded; E3 cheap vs not-cheap, counts only.
- **Outcomes at h ∈ {21, 42, 63} sweep sessions (§6):** O1 the same contract's mid multiple (printed with unquoted
  rows excluded, and with them set to 0), the realizable multiple ``bid(t+h) / ask(t)`` beside it, O2 the same
  contract's IV change (vol points), O3 the underlying's directional return from the stored spots (a missing spot at
  t+h resolves at the last earlier record), O4 Δ``iv_rv`` of the name; ``paid`` = O1 ≥ 2.0, ``repriced`` = O2 ≥ +3.0.
- **One pinned first read per horizon (§7):** the fourth unit week after the first row (the first NYSE session of the
  ISO week three weeks after the first unit date's), plus h NYSE sessions, then the Sunday after that date. Before it a
  contrast prints counts only (``pinned first read <date>``), whatever its n; E1 is not read earlier than E2. For a
  first row on Mon 2026-11-23 this gives 2027-01-17 / 02-21 / 03-21, the prereg's dates.
- **Inference (§7):** difference in medians with a name-blocked bootstrap 95% CI (resample names, 2,000 iterations,
  seed 0), the Mann–Whitney U beside it labelled "rows overlap; not independent"; binary companions with the same CI
  and the two-proportion z. A side of a split prints only with ≥ 20 matured rows and ≥ 8 distinct names (``n<20``).
- **No lookahead:** a row at t reads only the term record dated t (its exposure) and the one dated exactly at the h-th
  sweep session after t; nothing dated after the report's ``as_of`` is loaded.
- **Aggregate-only output (§10):** no symbol, no per-name value is ever printed.

Measurement only: no output reaches discovery, the council, the gate, sizing, an exit or a prompt.
"""

from __future__ import annotations

import math
import random
import sqlite3
import statistics
from collections import Counter
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from options_tradability import parse_osi

HORIZONS = (21, 42, 63)
MIN_ROWS, MIN_NAMES = 20, 8
MAX_OTM = 0.40
PAID, REPRICED = 2.0, 3.0
BOOT_ITERS, BOOT_SEED = 2000, 0
GUARD = "n<20"
FIRST_READ_UNIT_WEEK = 4   # §7: the first read is set by E2's ~four unit weeks
_ET = ZoneInfo("America/New_York")


# ── inputs ───────────────────────────────────────────────────────────────────────────────────────────────────────
def sweep_rows(conn: sqlite3.Connection, *, upto: date) -> dict[str, dict[str, dict]]:
    """{date: {SYMBOL: last OPRA sweep row of that date}} for dates ≤ ``upto``, with the run's frame_version."""
    out: dict[str, dict[str, dict]] = {}
    for r in conn.execute(
            "SELECT substr(g.evaluated_at, 1, 10) AS d, upper(g.symbol) AS sym, g.structured, g.iv_rv, g.cheap, "
            "g.wing, r.frame_version FROM gate_dualread g LEFT JOIN runs r ON r.id = g.run_id "
            "WHERE g.feed = 'opra' AND g.source = 'sweep' AND substr(g.evaluated_at, 1, 10) <= ? ORDER BY g.id",
            (upto.isoformat(),)):
        out.setdefault(r[0], {})[r[1]] = {"structured": bool(r[2]), "iv_rv": r[3], "cheap": r[4], "wing": r[5],
                                         "frame_version": r[6]}
    return out


def load_terms(cache, symbols, *, upto: date) -> dict[str, dict[str, dict]]:
    """{SYMBOL: {date: term record}} for records dated ≤ ``upto`` (the end of that ET day): no later record loads."""
    from iv_history import TERM_SOURCE

    end = datetime.combine(upto, time(23, 59, 59), tzinfo=_ET)
    out: dict[str, dict[str, dict]] = {}
    for sym in symbols:
        try:
            recs = cache.read_between(TERM_SOURCE, sym.upper(), None, end)
        except Exception:  # noqa: BLE001 — a missing/unreadable file is just no records
            recs = []
        out[sym.upper()] = {str(r["ts"])[:10]: r for r in recs if str(r.get("ts", ""))[:10] <= upto.isoformat()}
    return out


def unit_dates(dates) -> list[str]:
    """The first sweep date of each ISO week, ascending."""
    weeks: dict[tuple[int, int], str] = {}
    for d in sorted(dates):
        weeks.setdefault(date.fromisoformat(d).isocalendar()[:2], d)
    return sorted(weeks.values())


def wing_otm(wing: str, spot: float | None) -> tuple[str, float] | None:
    info = parse_osi(wing)
    if info is None or not spot or spot <= 0:
        return None
    k = info["strike"]
    return info["kind"], ((k - spot) / spot if info["kind"] == "C" else (spot - k) / spot)


def _quote(rec: dict | None, wing: str):
    if rec is None or "quotes" not in rec:
        return None, "no capture"
    q = (rec.get("quotes") or {}).get(wing)
    if q is None:
        return None, "contract missing"
    return q, None


def _mid(q) -> float | None:
    bid, ask = q[0], q[1]
    return (bid + ask) / 2.0 if bid is not None and ask is not None and bid > 0 and ask > 0 else None


# ── the unit rows ────────────────────────────────────────────────────────────────────────────────────────────────
def first_reads(first_unit: str) -> dict[int, str]:
    """§7: per horizon, the Sunday after the date the fourth unit week matures at h NYSE sessions. The fourth unit week
    is the first NYSE session of the ISO week three weeks after ``first_unit``'s (NYSE calendar, "assuming no skipped
    sweep", as the prereg computes its dates)."""
    from datetime import timedelta

    from nyse_calendar import is_trading_day

    d0 = date.fromisoformat(first_unit)
    monday = d0 - timedelta(days=d0.weekday()) + timedelta(weeks=FIRST_READ_UNIT_WEEK - 1)
    unit4 = next(monday + timedelta(days=i) for i in range(7) if is_trading_day(monday + timedelta(days=i)))
    out: dict[int, str] = {}
    for h in HORIZONS:
        d, n = unit4, 0
        while n < h:
            d += timedelta(days=1)
            if is_trading_day(d):
                n += 1
        out[h] = (d + timedelta(days=(6 - d.weekday()) or 7)).isoformat()   # the Sunday AFTER the maturity date
    return out


def build_rows(sweeps: dict[str, dict[str, dict]], terms: dict[str, dict[str, dict]], cohort=None, *,
               iv_rv_max: float = 1.2) -> tuple[list[dict], Counter]:
    """The unit rows. The cohort at each t is ``sweeps[t]``'s own names; ``cohort`` (tests only) narrows it further."""
    excluded: Counter = Counter()
    sessions = sorted(sweeps)
    pos = {d: i for i, d in enumerate(sessions)}
    live = sorted(d for recs in terms.values() for d, r in recs.items() if "quotes" in r)
    if not live:
        return [], excluded
    start = live[0]
    only = None if cohort is None else {s.upper() for s in cohort}
    rows: list[dict] = []
    for t in (d for d in unit_dates(sessions) if d >= start):
        today = [(s, r) for s, r in sweeps[t].items() if (only is None or s in only) and r["structured"]
                 and r["iv_rv"] is not None and r["wing"]]
        kept = []
        for sym, r in today:
            rec_t = terms.get(sym, {}).get(t)
            if rec_t is None:
                excluded["no term record at t"] += 1
                continue
            km = wing_otm(r["wing"], rec_t.get("spot"))
            if km is None:
                excluded["wing unparseable"] += 1
                continue
            if km[1] > MAX_OTM + 1e-9:
                excluded["wing > 40% OTM at t"] += 1
                continue
            rv, rv63 = rec_t.get("rv"), rec_t.get("rv63")
            atm_iv = float(r["iv_rv"]) * float(rv) if rv else None
            kept.append({"symbol": sym, "t": t, "kind": km[0], "iv_rv": float(r["iv_rv"]), "cheap": bool(r["cheap"]),
                         "wing": r["wing"], "frame_version": r["frame_version"], "spot_t": rec_t.get("spot"),
                         "rv63": rv63, "atm_iv": atm_iv,
                         "dependent": (None if (atm_iv is None or not rv63) else atm_iv / float(rv63) > iv_rv_max),
                         "q_t": _quote(rec_t, r["wing"])})
        kept.sort(key=lambda x: (x["iv_rv"], x["symbol"]))
        cut = math.ceil(len(kept) / 3)
        for i, row in enumerate(kept):
            row["tercile_cheapest"] = i < cut
            row["outcomes"] = {h: _outcome(row, h, sessions, pos, sweeps, terms) for h in HORIZONS}
        rows.extend(kept)
    return rows, excluded


def _outcome(row: dict, h: int, sessions, pos, sweeps, terms) -> dict | None:
    i = pos[row["t"]] + h
    if i >= len(sessions):
        return None                                   # not matured
    th = sessions[i]
    recs = terms.get(row["symbol"], {})
    rec_h = recs.get(th)
    q_t, why_t = row["q_t"]
    q_h, why_h = _quote(rec_h, row["wing"]) if rec_h is not None else (None, "no record (terminated?)")
    out: dict = {"o1": None, "unquoted": None, "realizable": None, "o2": None, "o3": None, "o4": None}
    mt = _mid(q_t) if q_t else None
    mh = _mid(q_h) if q_h else None
    if mt is None:
        out["unquoted"] = why_t or "no two-sided quote at t"
    elif mh is None:
        out["unquoted"] = why_h or "no two-sided quote at t+h"
    else:
        out["o1"] = mh / mt
    if q_t and q_h and q_t[1] and q_t[1] > 0 and q_h[0] is not None:
        out["realizable"] = q_h[0] / q_t[1]
    if q_t and q_h and q_t[2] is not None and q_h[2] is not None:
        out["o2"] = (q_h[2] - q_t[2]) * 100.0
    spot_h = None   # a terminated series resolves at its last record on or before t+h
    for d in sorted(d for d in recs if row["t"] < d <= th):
        if recs[d].get("spot"):
            spot_h = recs[d]["spot"]
    if row["spot_t"] and spot_h:
        ret = spot_h / row["spot_t"] - 1.0
        out["o3"] = -ret if row["kind"] == "P" else ret
    later = sweeps.get(th, {}).get(row["symbol"])
    if later and later["structured"] and later["iv_rv"] is not None:
        out["o4"] = float(later["iv_rv"]) - row["iv_rv"]
    return out


# ── statistics ───────────────────────────────────────────────────────────────────────────────────────────────────
def _values(rows, h, key, *, worst=False):
    vals = []
    for r in rows:
        o = r["outcomes"][h]
        v = o[key]
        if v is None and worst and key == "o1" and o["unquoted"]:
            v = 0.0
        if v is not None:
            vals.append((r["symbol"], v))
    return vals


def mann_whitney_u(a: list[float], b: list[float]) -> float:
    return sum(1.0 if x > y else 0.5 if x == y else 0.0 for x in a for y in b)


def _boot(a: list[tuple[str, float]], b: list[tuple[str, float]], stat) -> tuple[float, float] | None:
    names = sorted({s for s, _ in a} | {s for s, _ in b})
    by_a: dict[str, list[float]] = {}
    by_b: dict[str, list[float]] = {}
    for s, v in a:
        by_a.setdefault(s, []).append(v)
    for s, v in b:
        by_b.setdefault(s, []).append(v)
    rng = random.Random(BOOT_SEED)
    diffs = []
    for _ in range(BOOT_ITERS):
        pick = [rng.choice(names) for _ in names]
        xa = [v for s in pick for v in by_a.get(s, [])]
        xb = [v for s in pick for v in by_b.get(s, [])]
        if xa and xb:
            diffs.append(stat(xa) - stat(xb))
    if not diffs:
        return None
    diffs.sort()
    return (round(diffs[int(0.025 * (len(diffs) - 1))], 4), round(diffs[int(0.975 * (len(diffs) - 1))], 4))


def _passes(rows, h) -> bool:
    m = [r for r in rows if r["outcomes"][h] is not None]
    return len(m) >= MIN_ROWS and len({r["symbol"] for r in m}) >= MIN_NAMES


def contrast(a_rows: list[dict], b_rows: list[dict], h: int, *, first_read: str | None = None,
             as_of: date | None = None) -> dict:
    """One split at one horizon. Aggregates only. Before the horizon's pinned first read (``first_read``) it returns
    counts only, whatever the guard says. From that date on it carries ``look``: ``"first read"`` on the pinned date,
    ``"re-print"`` after it (§7)."""
    ma = [r for r in a_rows if r["outcomes"][h] is not None]
    mb = [r for r in b_rows if r["outcomes"][h] is not None]
    out: dict = {"n": [len(ma), len(mb)], "names": [len({r["symbol"] for r in ma}), len({r["symbol"] for r in mb})],
                 "unquoted": [sum(1 for r in ma if r["outcomes"][h]["unquoted"]),
                              sum(1 for r in mb if r["outcomes"][h]["unquoted"])]}
    if first_read is not None and as_of is not None and as_of.isoformat() < first_read:
        out["guard"] = f"pinned first read {first_read}"
        return out
    if first_read is not None and as_of is not None:
        # §7: a print after the pinned first read is "labelled a re-print of the same pinned look, never a new look".
        # The look is a function of the report date alone (no ledger, §4.3): the pinned date itself is the first read.
        out["look"] = "first read" if as_of.isoformat() == first_read else "re-print"
    if not (_passes(a_rows, h) and _passes(b_rows, h)):
        out["guard"] = GUARD
        return out
    med = statistics.median
    for label, key, worst in (("o1_mid_multiple", "o1", False), ("o1_unquoted_as_0", "o1", True),
                              ("realizable_multiple", "realizable", False), ("o2_iv_change_vp", "o2", False),
                              ("o3_directional_return", "o3", False), ("o4_delta_iv_rv", "o4", False)):
        va, vb = _values(ma, h, key, worst=worst), _values(mb, h, key, worst=worst)
        if not va or not vb:
            out[label] = None
            continue
        xa, xb = [v for _, v in va], [v for _, v in vb]
        out[label] = {"median": [round(med(xa), 4), round(med(xb), 4)], "diff": round(med(xa) - med(xb), 4),
                      "ci95_name_blocked": _boot(va, vb, med),
                      "mann_whitney_u": mann_whitney_u(xa, xb), "u_note": "rows overlap; not independent"}
    from miss_baserate import two_proportion_z

    for label, key, thr in (("paid", "o1", PAID), ("repriced", "o2", REPRICED)):
        va = [(s, 1.0 if v >= thr else 0.0) for s, v in _values(ma, h, key, worst=(key == "o1"))]
        vb = [(s, 1.0 if v >= thr else 0.0) for s, v in _values(mb, h, key, worst=(key == "o1"))]
        if not va or not vb:
            out[label] = None
            continue
        pa, pb = sum(v for _, v in va) / len(va), sum(v for _, v in vb) / len(vb)
        z = two_proportion_z(int(sum(v for _, v in va)), len(va), int(sum(v for _, v in vb)), len(vb))
        out[label] = {"share": [round(pa, 4), round(pb, 4)], "diff": round(pa - pb, 4),
                      "ci95_name_blocked": _boot(va, vb, lambda x: sum(x) / len(x)),
                      "two_proportion_z": None if z is None else round(z, 4), "z_note": "rows overlap; not independent"}
    return out


def report_from(rows: list[dict], excluded: Counter, *, as_of: date) -> dict:
    if not rows:
        return {"as_of": as_of.isoformat(), "status": "no outcome rows yet", "rows": 0,
                "excluded": dict(excluded)}
    e1a = [r for r in rows if r["tercile_cheapest"]]
    e1b = [r for r in rows if not r["tercile_cheapest"]]
    cheap = [r for r in rows if r["cheap"]]
    e2_ok = [r for r in cheap if r["dependent"] is not None]
    e2a = [r for r in e2_ok if r["dependent"]]
    e2b = [r for r in e2_ok if not r["dependent"]]
    notcheap = [r for r in rows if not r["cheap"]]
    fr = first_reads(min(r["t"] for r in rows))
    e3 = {}
    for h in HORIZONS:
        mc = sum(1 for r in cheap if r["outcomes"][h] is not None)
        mn = sum(1 for r in notcheap if r["outcomes"][h] is not None)
        e3[h] = {"cheap": mc, "not_cheap": mn, "filled": _passes(cheap, h) and _passes(notcheap, h)}
    return {
        "as_of": as_of.isoformat(), "status": "ok", "rows": len(rows), "unit_dates": len({r["t"] for r in rows}),
        "names": len({r["symbol"] for r in rows}), "excluded": dict(excluded),
        "by_frame_version": dict(Counter(str(r["frame_version"]) for r in rows)),
        "first_read": fr,
        "E1_cheapest_tercile_vs_rest": {h: contrast(e1a, e1b, h, first_read=fr[h], as_of=as_of) for h in HORIZONS},
        "E2_rv252_dependent_vs_rest_among_cheap": {h: contrast(e2a, e2b, h, first_read=fr[h], as_of=as_of)
                                                   for h in HORIZONS},
        "E2_no_rv63": len(cheap) - len(e2_ok),
        "E3_cheap_vs_not_cheap_counts": e3,
        "E3_never_filled_by": None if any(v["filled"] for v in e3.values()) else as_of.isoformat(),
        "note": "report-not-gate; aggregate only; no per-name values (§10)",
    }


def report(conn: sqlite3.Connection, cache, config: dict, *, as_of: date) -> dict:
    gate = config.get("convexity_gate", {}) or {}
    sweeps = sweep_rows(conn, upto=as_of)
    names = sorted({s for day in sweeps.values() for s in day})   # the sweep's own populations, not today's config
    terms = load_terms(cache, names, upto=as_of)
    rows, excluded = build_rows(sweeps, terms, iv_rv_max=float(gate.get("iv_rv_max", 1.2)))
    return report_from(rows, excluded, as_of=as_of)


def render(rep: dict) -> str:
    lines = [f"#455 cheap-then-repriced — report-not-gate (as of {rep['as_of']})"]
    if rep["status"] != "ok":
        lines.append(f"{rep['status']} (excluded: {rep['excluded'] or 'none'})")
        return "\n".join(lines)
    lines.append(f"pinned first reads (h: date): {rep['first_read']}")
    lines.append(f"rows {rep['rows']} over {rep['unit_dates']} unit date(s), {rep['names']} names; excluded "
                 f"{rep['excluded'] or 'none'}; frame_version {rep['by_frame_version']}")
    for title, key in (("E1 cheapest iv_rv tercile vs rest", "E1_cheapest_tercile_vs_rest"),
                       ("E2 RV252-dependent vs rest (gate-cheap rows)", "E2_rv252_dependent_vs_rest_among_cheap")):
        lines.append(f"\n{title}")
        for h, c in rep[key].items():
            look = f" [{c['look']} of the {rep['first_read'][h]} look]" if "look" in c else ""
            if "guard" in c:
                lines.append(f"  h={h}: {c['guard']}{look} (n {c['n']}, names {c['names']})")
                continue
            o1, o10 = c["o1_mid_multiple"], c["o1_unquoted_as_0"]
            lines.append(f"  h={h}{look}: n {c['n']} names {c['names']} unquoted {c['unquoted']}; O1 median "
                         f"{o1 and o1['median']} diff {o1 and o1['diff']} CI {o1 and o1['ci95_name_blocked']} "
                         f"(unquoted as 0: {o10 and o10['diff']}); realizable "
                         f"{c['realizable_multiple'] and c['realizable_multiple']['median']}; O2 diff "
                         f"{c['o2_iv_change_vp'] and c['o2_iv_change_vp']['diff']} vp; paid "
                         f"{c['paid'] and c['paid']['share']}; repriced {c['repriced'] and c['repriced']['share']}")
    lines.append(f"\nE2 gate-cheap rows without rv63 (excluded): {rep['E2_no_rv63']}")
    lines.append("E3 cheap vs not-cheap (counts only): " + "; ".join(
        f"h={h} {v['cheap']}/{v['not_cheap']}" for h, v in rep["E3_cheap_vs_not_cheap_counts"].items())
                 + (f" — never filled by {rep['E3_never_filled_by']}" if rep["E3_never_filled_by"] else ""))
    lines.append(rep["note"])
    return "\n".join(lines)
