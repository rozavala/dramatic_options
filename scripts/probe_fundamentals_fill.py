"""STEP 0 — the §9 grounding pre-freeze FILL-RATE AUDIT (read-only availability inspection).

Leash-compatible by construction: inspects input AVAILABILITY (which pinned concepts render a
line per name), never outcomes/judgments. Imports the SHIPPING extractors
(`data.fundamentals.corpus_asof` et al.) — a reimplemented audit would validate nothing.

Decides operator pick 1 of PREREG_EVIDENCE_GROUNDING (5 concepts vs leaner 3) on data: if the
two fragile shapes (capex YTD-differencing, gross-margin pairing) fill <~40%, the leaner set
answers itself. Also dry-runs all three extraction shapes against real filings BEFORE the
design freezes around them, and surfaces IFRS/foreign filers (us-gaap returns nothing there —
out of scope v1, must fail visibly).

Run from the repo root with the worktree venv (PYTHONPATH=. venv/bin/python
scripts/probe_fundamentals_fill.py); fetches ~45 companyfacts JSONs from SEC (free, throttled,
TEMP cache — the live cache is never touched). TEE THE OUTPUT to records/.
"""
from __future__ import annotations

import tempfile
import time
from datetime import UTC, datetime

from dotenv import load_dotenv

load_dotenv("/home/rodrigo/dramatic_options/.env")

import orchestrator  # noqa: E402
from config_loader import load_config  # noqa: E402
from data.filings import EdgarClient  # noqa: E402
from data.fundamentals import CONCEPT_TAGS, FundamentalsData  # noqa: E402

# The CGS §5 pinned 16 (probe_rescore_thesis_only.UNIVERSE) — kept verbatim.
PINNED_16 = ["NVDA", "SMCI", "VRT", "ETN", "GEV", "CEG", "CCJ", "FCX",
             "NEE", "PWR", "RKLB", "LMT", "NOC", "LHX", "RTX", "KTOS"]

config = load_config()
ua = config.get("edgar", {}).get("user_agent", "")
assert ua, "EDGAR_USER_AGENT missing"
baskets, _bench = orchestrator._scan_universe(config)
universe = sorted({s for members in baskets.values() for s in members} | set(PINNED_16))
as_of = datetime.now(UTC)
metrics = ["ttm_yoy", "qtr_yoy", "qtr_yoy_accel", "delta_pts", "capex_qtr_yoy", "rpo_yoy"]

with tempfile.TemporaryDirectory() as tmp:
    edgar = EdgarClient(ua, cache_dir=tmp)
    fd = FundamentalsData(cache=None, edgar=edgar, fetch_end=as_of, ua=ua,
                          cache_dir=tmp, max_raw_age_days=7)
    print(f"=== §9 STEP-0 FILL AUDIT — {len(universe)} names "
          f"(pinned 16 ∪ live universe), as_of {as_of.isoformat()} ===")
    print("concept tag lists:", {k: v for k, v in CONCEPT_TAGS.items()})
    print(f"{'sym':6} {'cik':5} {'n':>2}  {'rev_ttm':7} {'qtr_yoy':7} {'accel':5} "
          f"{'gm_d':5} {'capex':5} {'rpo':5}")
    fill: dict[str, int] = dict.fromkeys(metrics, 0)
    no_cik, empty = [], []
    for sym in universe:
        time.sleep(0.15)  # SEC fair-use
        out = fd.corpus_asof(sym, as_of)
        have = {(ln["concept"], ln["metric"]) for ln in out["lines"]}
        row = {
            "ttm_yoy": ("revenue", "ttm_yoy") in have,
            "qtr_yoy": ("revenue", "qtr_yoy") in have,
            "qtr_yoy_accel": ("revenue", "qtr_yoy_accel") in have,
            "delta_pts": ("gross_margin", "delta_pts") in have,
            "capex_qtr_yoy": ("capex", "qtr_yoy") in have,
            "rpo_yoy": ("rpo", "yoy") in have,
        }
        for k, v in row.items():
            fill[k] += int(v)
        cik = fd._cik(sym)
        if cik is None:
            no_cik.append(sym)
        elif out["n_lines"] == 0:
            empty.append(sym)
        mark = lambda b: "  Y  " if b else "  .  "  # noqa: E731
        print(f"{sym:6} {'ok ' if cik else 'NO ':5} {out['n_lines']:>2} "
              f" {mark(row['ttm_yoy']):7} {mark(row['qtr_yoy']):7} {mark(row['qtr_yoy_accel']):5} "
              f"{mark(row['delta_pts']):5} {mark(row['capex_qtr_yoy']):5} {mark(row['rpo_yoy']):5}")
    n = len(universe)
    print("\n=== PER-CONCEPT FILL (share of names with the line rendered, as-of-valid) ===")
    for k in metrics:
        print(f"  {k:14} {fill[k]:>2}/{n}  ({fill[k] / n:.0%})")
    print(f"\nno CIK: {no_cik or '—'}")
    print(f"CIK ok but ZERO lines (likely IFRS/foreign or sparse filer): {empty or '—'}")
    print("\nNOTE: availability only — no outcomes, no judgments, no gate reads (leash §6).")
