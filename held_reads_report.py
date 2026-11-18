"""READ-ONLY §4 scoring of the #464 held-name reads (PREREG_COUNCIL_GATE_SEPARATION §10.13;
records/2026-11-16_held_name_thesis_tracking_optionB_PREREG.md §4, with the 2026-11-17 dropped-read pin). The thin
CLI is ``scripts/probe_held_reads_report.py``.

For each CLOSED real position with held reads:
- take its held reads before ``closed_at``; **drop the ``dropped`` ones** (a NEUTRAL early exit — the debate declined
  to judge; pinned 2026-11-17, #508 decision A) and count them beside the table;
- the last 3 NON-dropped reads decide: **intact** if at least 2 are at or above the floor (MODERATE conviction), else
  **broken**. A backfill-origin position uses the persistence-watch convention instead: a read counts when
  ``include = true`` at LOW or higher;
- a close with fewer than 3 non-dropped reads goes in the ``< 3 reads`` bin, never in the table;
- outcome: realized multiple ``(total_premium + realized_pnl) / total_premium`` ≥ 1.0 vs < 1.0, with ≥ 10× alongside.

A 2 × 2 table of counts per ``model_mix`` segment (the per-row stamp). **A close whose last 3 reads span two segments
goes in a "mixed" bin** (its own table), so no table pools across a stamp. **No rate prints for a table before it has
20 scored closes** ("rates withheld: N/20"); the rate it will feed is the false-alarm rate P(broken | outcome ≥ 1.0)
(Rule S). Counts only, measured at close; nothing here acts on any position (§5).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter

from council.proposal import passes_floor

FLOOR = "MODERATE"
BACKFILL_FLOOR = "LOW"
MIN_CLOSES = 20
TENX = 10.0
LAST_N = 3


def _parse(ts):
    from dashboard_data import _parse_dt

    return _parse_dt(ts)


def read_counts(read: dict, *, backfill: bool) -> bool:
    """Whether one non-dropped held read is at or above the floor (§4). A backfill-origin position: include = true at
    LOW or higher (the persistence-watch convention); otherwise conviction ≥ MODERATE."""
    if backfill:
        return bool(read.get("include")) and passes_floor(read.get("conviction"), BACKFILL_FLOOR)
    return passes_floor(read.get("conviction"), FLOOR)


def segment_label(model_mix: str | None) -> str:
    """A short, stable label for a ``runs.model_mix`` stamp: the strategist model plus an 8-hex digest of the whole
    (canonical) stamp, so any change in the stamp is a different segment."""
    try:
        mix = json.loads(model_mix) if model_mix else {}
    except (TypeError, ValueError):
        mix = {"_raw": str(model_mix)}
    digest = hashlib.sha1(json.dumps(mix, sort_keys=True, default=str).encode()).hexdigest()[:8]
    return f"{mix.get('strategist', 'unknown')} · {digest}" if mix else "unstamped"


def classify(position: dict, reads: list[dict]) -> dict:
    """One close: ``{bin, verdict, multiple, tenx, dropped, segment, reads_used}``. ``reads`` are this position's held
    reads, any order; only those created before ``closed_at`` count. ``bin`` is ``scored`` | ``lt3`` | ``no_outcome``."""
    closed = _parse(position.get("closed_at"))
    before = sorted((r for r in reads if closed is None or (_parse(r.get("created_at")) or closed) < closed),
                    key=lambda r: (str(r.get("created_at") or ""), int(r.get("run_id") or 0)))
    dropped = sum(1 for r in before if r.get("dropped"))
    kept = [r for r in before if not r.get("dropped")]
    last = kept[-LAST_N:]
    prem = position.get("total_premium")
    pnl = position.get("realized_pnl")
    multiple = (float(prem) + float(pnl)) / float(prem) if prem and pnl is not None and float(prem) > 0 else None
    out = {"position_id": position.get("id"), "symbol": position.get("symbol"), "direction": position.get("direction"),
           "dropped": dropped, "non_dropped": len(kept), "multiple": multiple,
           "tenx": multiple is not None and multiple >= TENX, "verdict": None, "segment": None,
           "reads_used": [r.get("run_id") for r in last], "backfill": bool(position.get("backfill"))}
    if len(last) < LAST_N:
        return {**out, "bin": "lt3"}
    segs = {segment_label(r.get("model_mix")) for r in last}
    hits = sum(1 for r in last if read_counts(r, backfill=bool(position.get("backfill"))))
    out.update(verdict="intact" if hits >= 2 else "broken", segment=segs.pop() if len(segs) == 1 else "mixed")
    if multiple is None:
        return {**out, "bin": "no_outcome"}
    return {**out, "bin": "scored"}


def table(closes: list[dict]) -> dict:
    """The 2 × 2 of scored closes + ≥10× alongside; rates only at ≥ MIN_CLOSES."""
    cells = Counter((c["verdict"], "ge1" if c["multiple"] >= 1.0 else "lt1") for c in closes)
    tenx = Counter(c["verdict"] for c in closes if c["tenx"])
    n = len(closes)
    t = {"n": n,
         "intact": {"ge1": cells[("intact", "ge1")], "lt1": cells[("intact", "lt1")], "ge10x": tenx["intact"]},
         "broken": {"ge1": cells[("broken", "ge1")], "lt1": cells[("broken", "lt1")], "ge10x": tenx["broken"]}}
    if n < MIN_CLOSES:
        t["rates"] = None
        t["rates_withheld"] = f"rates withheld: {n}/{MIN_CLOSES}"
    else:
        ge1 = t["intact"]["ge1"] + t["broken"]["ge1"]
        t["rates"] = {"false_alarm_p_broken_given_ge1": (t["broken"]["ge1"] / ge1) if ge1 else None}
        t["rates_withheld"] = None
    return t


def report_from(positions: list[dict], reads_by_position: dict[int, list[dict]]) -> dict:
    """Pure: the §4 report over closed positions and their held reads."""
    closes = [classify(p, reads_by_position.get(int(p["id"]), [])) for p in positions
              if reads_by_position.get(int(p["id"]))]
    scored = [c for c in closes if c["bin"] == "scored"]
    segments = sorted({c["segment"] for c in scored})
    return {
        "closes_with_held_reads": len(closes),
        "segments": {s: table([c for c in scored if c["segment"] == s]) for s in segments},
        "all": table(scored),
        "lt3": [c for c in closes if c["bin"] == "lt3"],
        "no_outcome": [c for c in closes if c["bin"] == "no_outcome"],
        "dropped_reads": sum(c["dropped"] for c in closes),
        "closes": closes,
        "definitions": ("last 3 non-dropped held reads before closed_at; dropped reads excluded and counted (2026-11-17 "
                        "pin); intact = >=2 at or above MODERATE (backfill origin: include=true at >=LOW); outcome = "
                        "(total_premium + realized_pnl) / total_premium vs 1.0, >=10x alongside; a close whose last 3 "
                        "span two model_mix segments is in the 'mixed' segment; no rate before 20 scored closes"),
    }


def report(conn: sqlite3.Connection) -> dict:
    """Read-only: closed real positions with held reads → ``report_from``."""
    import backfill

    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='held_reads'").fetchone() is None:
        return {"error": "no held_reads table (migration 0023 not applied)"}
    positions = []
    for r in conn.execute("SELECT * FROM convexity_positions WHERE status = 'closed' ORDER BY id"):
        p = dict(r)
        p["backfill"] = backfill._origin(p.get("rationale")) == backfill.ORIGIN
        positions.append(p)
    reads: dict[int, list[dict]] = {}
    for r in conn.execute("SELECT position_id, run_id, conviction, include, dropped, model_mix, created_at "
                          "FROM held_reads ORDER BY id"):
        reads.setdefault(int(r["position_id"]), []).append(dict(r))
    return report_from(positions, reads)


def render(rep: dict) -> str:
    if "error" in rep:
        return f"held reads report: {rep['error']}"
    lines = ["§10.13 held-name reads — §4 scoring (counts only; measurement only, never acted on)", "",
             f"closed real positions with held reads: {rep['closes_with_held_reads']}; dropped reads excluded: "
             f"{rep['dropped_reads']}; < 3 reads bin: {len(rep['lt3'])}; no outcome: {len(rep['no_outcome'])}"]
    blocks = [(f"segment {s}", t) for s, t in rep["segments"].items()] + [("ALL segments", rep["all"])]
    for title, t in blocks:
        lines += ["", f"{title} (n={t['n']})",
                  f"  {'':8} {'>=1.0x':>7} {'<1.0x':>7} {'>=10x':>7}",
                  f"  {'intact':8} {t['intact']['ge1']:>7} {t['intact']['lt1']:>7} {t['intact']['ge10x']:>7}",
                  f"  {'broken':8} {t['broken']['ge1']:>7} {t['broken']['lt1']:>7} {t['broken']['ge10x']:>7}",
                  "  " + (t["rates_withheld"] or
                          f"false-alarm P(broken | >=1.0x) = {t['rates']['false_alarm_p_broken_given_ge1']}")]
    lines += ["", f"Definitions: {rep['definitions']}"]
    return "\n".join(lines)
