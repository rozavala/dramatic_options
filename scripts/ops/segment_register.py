#!/usr/bin/env python3
"""READ-ONLY: the record segments that the `runs` stamps define, checked against records/segment_register.md (#470).

Boundary B (STANDING_STATE, 2026-11-12) batches record-segmenting changes onto one day a month; the operator chose
"the segment register only, with no CI fingerprint check". The register is the dated, hand-written record of each
boundary's cause. This script is the machine half: it reads `runs` and prints

- every stamp move it can see: `frame_version` and `data_feed` (every run), `discovery_funnel` (L0 runs), and each
  `model_mix` key (council L1 runs only, i.e. runs whose `model_mix` names a strategist);
- the council-L1 segments those moves cut (a maximal run of L1s with one stamp tuple): first/last run, sessions, real
  entries (not cancelled; a carry fill counts in the segment of the latest L1 at or before its run);
- with `--check`, every stamp move that has no register row, so a review adds the row in its records PR.

A register row matches a move when one line holds both `run #<first run id>` and the stamp name in backticks.
No network, no writes; the DB is opened `?mode=ro`.

    PYTHONPATH=. venv/bin/python scripts/ops/segment_register.py --db <live db> [--check] [--since RUN_ID]
    # exit 0 = in sync (or no --check), 1 = a move with no register row, 2 = cannot read
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

WHOLE_RUN_STAMPS = ("frame_version", "data_feed", "discovery_funnel")


def _mix(raw: str | None) -> dict | None:
    """A council L1's model_mix as a dict; None for a non-council run (NULL, unparseable, or a cheapness-watch-only
    `clock_basis` merge with no strategist key)."""
    if not raw:
        return None
    try:
        m = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return m if isinstance(m, dict) and "strategist" in m else None


def load_runs(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT id, started_at, mode, frame_version, model_mix, data_feed, discovery_funnel "
                        "FROM runs ORDER BY id").fetchall()
    return [{"id": r[0], "started_at": str(r[1] or ""), "mode": r[2], "frame_version": r[3],
             "model_mix": _mix(r[4]), "data_feed": r[5], "discovery_funnel": r[6]} for r in rows]


def load_entries(conn: sqlite3.Connection) -> list[dict]:
    """Real-book entries (not cancelled): run_id and whether the rationale marks a backfill."""
    rows = conn.execute("SELECT run_id, rationale FROM convexity_positions "
                        "WHERE status IS NULL OR status != 'cancelled'").fetchall()
    return [{"run_id": r[0], "backfill": '"origin": "backfill"' in str(r[1] or "")} for r in rows]


def boundaries(runs: list[dict]) -> list[dict]:
    """Pure: each stamp move, in run order. The first value a stamp ever takes is a move from None."""
    out: list[dict] = []
    prev: dict[str, object] = {}
    for r in runs:
        for key in WHOLE_RUN_STAMPS:
            v = r.get(key)
            if v is None:
                continue  # not stamped on this kind of run (e.g. discovery_funnel off L0); not a move
            if prev.get(key) != v:
                out.append({"key": key, "run_id": r["id"], "started_at": r["started_at"],
                            "old": prev.get(key), "new": v})
            prev[key] = v
        mix = r.get("model_mix")
        if mix is None:
            continue
        old_mix = prev.get("model_mix") or {}
        for k in sorted(set(mix) | set(old_mix)):
            if mix.get(k) != old_mix.get(k):
                out.append({"key": k, "run_id": r["id"], "started_at": r["started_at"],
                            "old": old_mix.get(k), "new": mix.get(k)})
        prev["model_mix"] = mix
    return out


def segments(runs: list[dict], entries: list[dict] | None = None) -> list[dict]:
    """Pure: maximal runs of council L1s with one (frame_version, data_feed, model_mix) tuple."""
    l1 = [r for r in runs if r.get("model_mix") is not None]
    segs: list[dict] = []
    for r in l1:
        tup = (r.get("frame_version"), r.get("data_feed"), json.dumps(r["model_mix"], sort_keys=True))
        if segs and segs[-1]["_tup"] == tup:
            s = segs[-1]
            s["last_run"], s["last_at"], s["sessions"] = r["id"], r["started_at"], s["sessions"] + 1
            continue
        changed: list[str] = []
        if segs:
            p = segs[-1]["_tup"]
            changed += [k for k, a, b in (("frame_version", p[0], tup[0]), ("data_feed", p[1], tup[1])) if a != b]
            pm, nm = json.loads(p[2]), r["model_mix"]
            changed += [k for k in sorted(set(pm) | set(nm)) if pm.get(k) != nm.get(k)]
        segs.append({"_tup": tup, "first_run": r["id"], "first_at": r["started_at"], "last_run": r["id"],
                     "last_at": r["started_at"], "sessions": 1, "changed": changed, "entries": 0, "backfill": 0})
    for e in entries or []:
        home = None
        for s in segs:  # the segment of the latest council L1 at or before the entry's run (carry fills included)
            if e["run_id"] is not None and s["first_run"] <= e["run_id"]:
                home = s
        if home is not None:
            home["entries"] += 1
            home["backfill"] += int(e["backfill"])
    for s in segs:
        del s["_tup"]
    return segs


def missing_from_register(bounds: list[dict], register_text: str) -> list[dict]:
    """Pure: the moves no register line names (`run #<id>` and the backticked stamp on one line)."""
    lines = register_text.splitlines()
    out = []
    for b in bounds:
        run_pat = re.compile(rf"run #{b['run_id']}\b")
        if not any(run_pat.search(ln) and f"`{b['key']}`" in ln for ln in lines):
            out.append(b)
    return out


def _short(v: object, n: int = 48) -> str:
    s = "—" if v is None else str(v)
    return s if len(s) <= n else s[: n - 1] + "…"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Record segments from runs stamps (#470), read-only")
    ap.add_argument("--db", default=os.environ.get("DRAMATIC_DB", "data/dramatic_options.db"))
    ap.add_argument("--register", default=str(Path(__file__).resolve().parents[2] / "records/segment_register.md"))
    ap.add_argument("--check", action="store_true", help="exit 1 if a stamp move has no register row")
    ap.add_argument("--since", type=int, default=0, help="print moves and segments from this run id on")
    a = ap.parse_args(argv)
    try:
        if not Path(a.db).exists():
            raise FileNotFoundError(a.db)
        conn = sqlite3.connect(f"file:{Path(a.db).resolve()}?mode=ro", uri=True)
        try:
            runs, entries = load_runs(conn), load_entries(conn)
        finally:
            conn.close()
        register = Path(a.register).read_text() if a.check else ""
    except Exception as e:  # noqa: BLE001 — a reporting tool: say it couldn't read, never guess
        print(f"segment-register: cannot read ({type(e).__name__}: {e})")
        return 2
    bounds = boundaries(runs)
    print("Stamp moves (first run carrying the new value):")
    for b in bounds:
        if b["run_id"] >= a.since:
            print(f"  run #{b['run_id']:<5} {b['started_at'][:16]:16}  {b['key']:18} "
                  f"{_short(b['old'])} -> {_short(b['new'])}")
    print("\nCouncil-L1 segments (one stamp tuple each):")
    print(f"  {'first':>11} {'date':10}  {'last':>11} {'date':10}  {'L1s':>4} {'entries':>7} {'bkfl':>4}  changed")
    for s in segments(runs, entries):
        if s["last_run"] >= a.since:
            print(f"  run #{s['first_run']:<5} {s['first_at'][:10]:10}  run #{s['last_run']:<5} {s['last_at'][:10]:10}  "
                  f"{s['sessions']:>4} {s['entries']:>7} {s['backfill']:>4}  {', '.join(s['changed']) or '(first)'}")
    if not a.check:
        return 0
    miss = missing_from_register(bounds, register)
    if miss:
        print(f"\nDRIFT: {len(miss)} stamp move(s) with no row in {a.register}:")
        for b in miss:
            print(f"  run #{b['run_id']} {b['started_at'][:10]} `{b['key']}` {_short(b['old'])} -> {_short(b['new'])}")
        return 1
    print(f"\nOK: every stamp move has a row in {a.register}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
