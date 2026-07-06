"""The frozen READ-LAYER pins (records/2026-07-04_read_layer_pins_PREREG_DRAFT.md, FROZEN
2026-07-04 v3) — report-time ONLY, one module, zero booking-path imports.

Implements the four pins over the persisted record:
  §1  leg-aware fill-realism band (frictionless vs conservative at h = half the eligibility
      spread cap; expiry-settled positions pay the entry leg only),
  §2  cluster-blocked bootstrap CIs (blocks = the deterministic ``clusters.py`` map;
      n_blocks displayed, <5 ⇒ "unstable"),
  §3  the resolution calendar (expiry − 21d per open position) + the minimum-n floor
      (n ≥ 10 resolved per compared book ∧ ≥ 3 clusters, else the verbatim "accruing" string),
  §4  the counterfactual-mandate ledger (V1–V4 enforcement-layer replays from the recorded
      strategist fields; boolean coercions pinned; shadow matching = symbol AND direction
      within ±5 weekdays; per-vintage match rates).

Everything here READS; nothing books, sizes, pages, or edits config — the §10-style seam for
the read layer. Consumed by reports/dashboard; never by the trade cycle.
"""

from __future__ import annotations

import json
import logging
import random
import sqlite3
from datetime import datetime, timedelta

import clusters
import state

log = logging.getLogger("read_layer")

# §1 — half of the 25% eligibility spread/mid cap (verified vs options_tradability.spread_pct).
H_BOUND = 0.125
# §3 — the pre-registered floor.
FLOOR_N = 10
FLOOR_CLUSTERS = 3
ACCRUING = "accruing — below the pre-registered floor"
# §4 — shadow-match window (weekdays) and the vintage-2b boundary (the fork activation deploy).
MATCH_TD = 5
VINTAGE_2B_ISO = "2026-07-03"


# ── §1: leg-aware fill-realism band ──────────────────────────────────────────────────────────────


def haircut_multiple(multiple: float, exit_reason: str | None, h: float = H_BOUND) -> float:
    """§1: the conservative column for ONE resolved position. ``expiry``-settled positions settle
    at intrinsic and cross NO exit spread → entry leg only (÷(1+h)); every other resolution is a
    market close → both legs (×(1−h)/(1+h)). Unknown/absent reasons take BOTH legs — the
    conservative direction, never the flattering one."""
    m = float(multiple)
    if str(exit_reason or "") == "expiry":
        return m / (1.0 + h)
    return m * (1.0 - h) / (1.0 + h)


def band(rows: list[tuple[float, str | None]], h: float = H_BOUND) -> dict:
    """§1: the two-column band over resolved (multiple, exit_reason) rows. Both columns share the
    tail_summary shape; ABSOLUTE and SIM-VS-REAL claims must hold under BOTH (the frozen rule).
    The uniform part of the haircut cannot reorder sim-vs-sim books — stated in the pre-reg."""
    from shadow_book import tail_summary

    return {
        "h": h,
        "frictionless": tail_summary([m for m, _ in rows]),
        "conservative": tail_summary([haircut_multiple(m, r, h) for m, r in rows]),
    }


# ── §2: cluster-blocked bootstrap ────────────────────────────────────────────────────────────────


def cluster_blocked_ci(rows: list[tuple[str, float]], cluster_map: dict, *, q: float = 0.95,
                       iters: int = 2000, seed: int = 0) -> dict:
    """§2: bootstrap CI for the q-quantile, resampling CLUSTER-BLOCKS (a symbol outside every
    cluster = its own singleton block) with replacement, pooling their positions. Returns
    n / n_blocks / lo / hi / point, with ``unstable=True`` at n_blocks < 5 (such a CI cannot
    carry a directional claim on its own — composes with the §3 floor)."""
    if not rows:
        return {"n": 0, "n_blocks": 0, "point": 0.0, "lo": 0.0, "hi": 0.0, "unstable": True}
    blocks: dict[str, list[float]] = {}
    for sym, m in rows:
        key = clusters.cluster_of(sym.upper(), cluster_map) or f"__single_{sym.upper()}"
        blocks.setdefault(key, []).append(float(m))
    names = sorted(blocks)
    xs_all = sorted(m for ms in blocks.values() for m in ms)

    def _q(xs: list[float]) -> float:
        return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]

    rng = random.Random(seed)
    stats = []
    for _ in range(iters):
        pooled: list[float] = []
        for _ in range(len(names)):
            pooled.extend(blocks[names[rng.randrange(len(names))]])
        stats.append(_q(sorted(pooled)))
    stats.sort()
    return {
        "n": len(xs_all), "n_blocks": len(names), "point": _q(xs_all),
        "lo": stats[int(0.025 * (len(stats) - 1))], "hi": stats[int(0.975 * (len(stats) - 1))],
        "unstable": len(names) < 5,
    }


# ── §3: resolution calendar + the floor ──────────────────────────────────────────────────────────


def _expiry_minus_21(expiry: str | None) -> str | None:
    try:
        d = datetime.fromisoformat(str(expiry)).date()
    except (TypeError, ValueError):
        return None
    return (d - timedelta(days=21)).isoformat()


def resolution_calendar(conn: sqlite3.Connection) -> dict:
    """§3: per book, each open position's expected-LATEST resolution (the 21-DTE time-stop date =
    expiry − 21d). Sim books resolve exactly-or-earlier; the REAL book can lag on a dead-bid
    close (reported as lagging, never back-dated — the pre-reg clause). Also the by-month
    histogram the 2026-11-02 checkpoint reads its denominator from."""
    q = {
        "real": "SELECT symbol, expiry FROM convexity_positions WHERE status='open'",
        "shadow": "SELECT symbol, expiry FROM shadow_positions WHERE status='open'",
        "3A": "SELECT symbol, expiry FROM fixed_basket_positions WHERE status='open' AND book='union_nogate'",
        "3B": "SELECT symbol, expiry FROM fixed_basket_positions WHERE status='open' AND book='basket_nogate'",
    }
    out: dict[str, dict] = {}
    for book, sql in q.items():
        rows = [(r[0], _expiry_minus_21(r[1])) for r in conn.execute(sql)]
        dates = sorted(d for _, d in rows if d)
        by_month: dict[str, int] = {}
        for d in dates:
            by_month[d[:7]] = by_month.get(d[:7], 0) + 1
        out[book] = {"n_open": len(rows), "earliest": dates[0] if dates else None,
                     "latest": dates[-1] if dates else None, "by_month": by_month}
    return out


def directional_floor(resolved_a: list[tuple[str, float]], resolved_b: list[tuple[str, float]],
                      cluster_map: dict) -> dict:
    """§3: the pre-registered floor for ANY directional claim between two books: n ≥ 10 resolved
    in EACH ∧ ≥ 3 distinct clusters among them. Below → the verbatim accruing string."""
    def _nc(rows):
        return len({clusters.cluster_of(s.upper(), cluster_map) or f"__single_{s.upper()}"
                    for s, _ in rows})

    met = (len(resolved_a) >= FLOOR_N and len(resolved_b) >= FLOOR_N
           and _nc(resolved_a) >= FLOOR_CLUSTERS and _nc(resolved_b) >= FLOOR_CLUSTERS)
    return {"met": met, "n_a": len(resolved_a), "n_b": len(resolved_b),
            "clusters_a": _nc(resolved_a), "clusters_b": _nc(resolved_b),
            "verdict": ("floor met" if met else ACCRUING)}


# ── §4: the counterfactual-mandate ledger ────────────────────────────────────────────────────────


def _strategist_fields(rationale_raw) -> dict | None:
    """The §4 pinned coercions. Returns None for non-deliberated rows (no strategist stage).
    ``structural`` := (structural_vs_fad == "structural"); the booleans are taken as persisted
    ``true``/``false`` ONLY; an absent required field on a deliberated row is the §10.9
    MISSING class — flagged, excluded from every variant, counted separately (never coerced)."""
    try:
        rat = json.loads(rationale_raw) if isinstance(rationale_raw, str) else (rationale_raw or {})
    except (TypeError, ValueError):
        return None
    strat = rat.get("strategist")
    if not isinstance(strat, dict):
        return None
    out = {
        "include": strat.get("include"),
        "conviction": strat.get("conviction"),
        "structural": (strat.get("structural_vs_fad") == "structural"
                       if "structural_vs_fad" in strat else None),
        "under_narrated": strat.get("under_narrated"),
        "at_inflection": strat.get("at_inflection"),
    }
    out["missing"] = any(
        v is None for k, v in out.items() if k in ("include", "under_narrated", "at_inflection",
                                                   "structural"))
    return out


_CONV_ORDER = {"LOW": 1, "MODERATE": 2, "HIGH": 3, "EXTREME": 4}


def _variant_pass(f: dict, variant: str) -> bool:
    """§4 variants — ENFORCEMENT layer only, all other rules identical (include required;
    floor MODERATE except V3=HIGH). V1 any-2-of-3; V2 drops at_inflection; V4 identity."""
    if not f["include"]:
        return False
    conv = _CONV_ORDER.get(str(f["conviction"] or "").upper(), 0)
    floor = 3 if variant == "V3" else 2
    if conv < floor:
        return False
    crits = [bool(f["structural"]), bool(f["under_narrated"]), bool(f["at_inflection"])]
    if variant == "V1":
        return sum(crits) >= 2
    if variant == "V2":
        return crits[0] and crits[1]
    return all(crits)  # V3 / V4


def mandate_ledger(conn: sqlite3.Connection, *, match_td: int = MATCH_TD) -> dict:
    """§4: the offline enforcement-replay. Per variant: the would-have-included set, the
    per-vintage shadow match rate (symbol AND direction, ±match_td weekdays), and the matched
    resolved multiples (fed to §1/§2 by the caller). Judgments held fixed — the validity scope
    is pinned in the pre-reg; V1/V2 are LOWER BOUNDS (stated on every read)."""
    shadow = [dict(r) for r in conn.execute(
        "SELECT symbol, direction, opened_at, realized_multiple, exit_reason, status "
        "FROM shadow_positions")]
    props = conn.execute(
        "SELECT id, run_id, as_of, symbol, direction, rationale FROM council_proposals ORDER BY id"
    ).fetchall()

    def _match(sym: str, direction: str, as_of: str):
        try:
            p_date = datetime.fromisoformat(str(as_of).replace("Z", "+00:00")).date()
        except (TypeError, ValueError):
            return None
        best = None
        for s in shadow:
            if s["symbol"].upper() != sym.upper() or str(s["direction"]).lower() != str(direction).lower():
                continue
            try:
                o = datetime.fromisoformat(str(s["opened_at"]).replace("Z", "+00:00")).date()
            except (TypeError, ValueError):
                continue
            lo, hi = sorted((o, p_date))
            if state._weekday_age(lo, hi) <= match_td and (best is None or o <= p_date):
                best = s
        return best

    variants = {v: {"set": [], "matched": [], "unresolved": 0, "by_vintage": {"v1_2a": 0, "v2b": 0},
                    "matched_by_vintage": {"v1_2a": 0, "v2b": 0}} for v in ("V1", "V2", "V3", "V4")}
    n_deliberated = n_missing = 0
    for p in props:
        f = _strategist_fields(p["rationale"])
        if f is None:
            continue
        n_deliberated += 1
        if f["missing"]:
            n_missing += 1
            continue
        for v, acc in variants.items():
            if not _variant_pass(f, v):
                continue
            vintage = "v2b" if str(p["as_of"])[:10] >= VINTAGE_2B_ISO else "v1_2a"
            acc["set"].append({"proposal_id": p["id"], "run_id": p["run_id"],
                               "symbol": p["symbol"], "as_of": p["as_of"]})
            acc["by_vintage"][vintage] += 1
            m = _match(p["symbol"], p["direction"], p["as_of"])
            if m is None:
                continue
            acc["matched_by_vintage"][vintage] += 1
            if m["status"] == "closed" and m["realized_multiple"] is not None:
                acc["matched"].append((m["symbol"], float(m["realized_multiple"]),
                                       m["exit_reason"]))
            else:
                acc["unresolved"] += 1
    for v, acc in variants.items():
        n_set = len(acc["set"])
        n_matched = acc["matched_by_vintage"]["v1_2a"] + acc["matched_by_vintage"]["v2b"]
        acc["n_set"] = n_set
        acc["match_rate"] = (n_matched / n_set) if n_set else 0.0
        acc["n_resolved_matches"] = len(acc["matched"])
    return {
        "n_deliberated": n_deliberated,
        "n_missing_class": n_missing,   # §10.9 — excluded from every variant, never coerced
        "variants": variants,
        "note": ("ENFORCEMENT-layer replay, judgments held fixed; V1/V2 are LOWER BOUNDS "
                 "(include/conviction were formed under the strict mandate). Matched outcomes "
                 "are read through the §1 band + §2 blocked CIs, subject to the §3 floor."),
    }
