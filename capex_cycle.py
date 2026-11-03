"""Capex-cycle telemetry per correlation cluster (D5 step 1, records/2026-11-03_profit_program_DRAFTS.md).

Greenwood & Hanson (2015) and the capital-cycle literature: an industry's own capex boom precedes its poor returns
("competition neglect"), and tight supply with falling capex precedes good ones. This turns the quarterly capex we
already pull from SEC XBRL (``data/fundamentals.py`` CONCEPT_TAGS["capex"], the same extraction the council corpus
uses) into one reading per cluster: trailing-twelve-month capex summed over the members, its YoY change, and its
acceleration (YoY now minus YoY two quarters earlier).

**Telemetry only.** Nothing here gates an entry or reaches a council prompt (that would be D5 step 2, a prompt change
with its own record segment). The L1 writes one dated record per day; the dashboard reads it.
"""

from __future__ import annotations

import logging
from datetime import datetime

from data.fundamentals import (
    CONCEPT_TAGS,
    IFRS_CONCEPT_TAGS,
    _d,
    _pick_tag,
    ytd_cashflow_series,
)

log = logging.getLogger("capex_cycle")

SOURCE = "capex_cycle"
KEY = "clusters"
ACCEL_LAG_Q = 2   # acceleration = TTM YoY now − TTM YoY two quarters earlier


def quarterly_capex(facts_json: dict | None, as_of: datetime) -> list[dict]:
    """Quarterly capex points ``{start, end, val, filed}`` visible as of ``as_of`` (us-gaap, else ifrs-full)."""
    facts = (facts_json or {}).get("facts") or {}
    best: list[dict] = []
    for tax, tags in (("us-gaap", CONCEPT_TAGS), ("ifrs-full", IFRS_CONCEPT_TAGS)):
        ft = facts.get(tax)
        if not ft or "capex" not in tags:
            continue
        _tag, raw = _pick_tag(ft, tags["capex"], as_of)
        q = ytd_cashflow_series(raw)
        if len(q) > len(best):
            best = q
    return best


def ttm_at(points: list[dict], idx: int) -> float | None:
    """Sum of the 4 consecutive quarters ending at ``points[idx]`` (adjacent ends 70–115 days apart), else None."""
    if idx < 3:
        return None
    window = points[idx - 3: idx + 1]
    for a, b in zip(window, window[1:], strict=False):
        if not 70 <= (_d(b["end"]) - _d(a["end"])).days <= 115:
            return None
    return float(sum(abs(p["val"]) for p in window))   # capex is reported positive; abs() guards a signed filer


def _year_ago_idx(points: list[dict], idx: int) -> int | None:
    target = _d(points[idx]["end"])
    for j in range(idx - 1, -1, -1):
        gap = (target - _d(points[j]["end"])).days
        if 320 <= gap <= 410:
            return j
        if gap > 410:
            break
    return None


def name_cycle(points: list[dict]) -> dict | None:
    """``{period_end, ttm_now, ttm_ago, yoy, yoy_prev, prev_now, prev_ago}`` for one name (``prev_*`` = the TTM pair
    two quarters earlier), or None without two comparable TTMs."""
    if not points:
        return None
    i = len(points) - 1

    def yoy_at(k: int) -> tuple[float | None, float | None, float | None]:
        j = _year_ago_idx(points, k) if k >= 0 else None
        now = ttm_at(points, k) if k >= 0 else None
        ago = ttm_at(points, j) if j is not None else None
        return now, ago, (now / ago - 1.0 if now is not None and ago else None)

    now, ago, yoy = yoy_at(i)
    if yoy is None:
        return None
    p_now, p_ago, yoy_prev = yoy_at(i - ACCEL_LAG_Q)
    return {"period_end": points[i]["end"], "ttm_now": now, "ttm_ago": ago, "yoy": yoy, "yoy_prev": yoy_prev,
            "prev_now": p_now if yoy_prev is not None else None, "prev_ago": p_ago if yoy_prev is not None else None}


def cluster_cycle(by_symbol: dict[str, dict | None]) -> dict:
    """Aggregate members: Σ TTM now ÷ Σ TTM a year ago − 1, and the same two quarters back (names with both)."""
    have = {s: c for s, c in by_symbol.items() if c}
    out = {"members": sorted(by_symbol), "n_with_data": len(have), "missing": sorted(s for s, c in by_symbol.items()
                                                                                     if not c),
           "ttm_now_musd": None, "yoy": None, "yoy_prev": None, "accel": None, "latest_period": None}
    if not have:
        return out
    now = sum(c["ttm_now"] for c in have.values())
    ago = sum(c["ttm_ago"] for c in have.values())
    out["ttm_now_musd"] = round(now / 1e6, 1)
    out["yoy"] = round(now / ago - 1.0, 4) if ago else None
    # Acceleration only over the SAME member set at both points (a name missing the earlier pair would otherwise
    # change the basket between the two readings and show up as fake acceleration).
    if all(c.get("prev_now") is not None and c.get("prev_ago") for c in have.values()):
        p_now = sum(c["prev_now"] for c in have.values())
        p_ago = sum(c["prev_ago"] for c in have.values())
        out["yoy_prev"] = round(p_now / p_ago - 1.0, 4) if p_ago else None
        if out["yoy"] is not None and out["yoy_prev"] is not None:
            out["accel"] = round(out["yoy"] - out["yoy_prev"], 4)
    out["latest_period"] = max(c["period_end"] for c in have.values())
    return out


def phase(c: dict) -> str:
    """A plain-language label for the dashboard (descriptive; no threshold here gates anything)."""
    yoy, acc = c.get("yoy"), c.get("accel")
    if yoy is None:
        return "no data"
    if yoy > 0.15:
        return "capex boom, accelerating" if (acc or 0) > 0 else "capex boom, slowing"
    if yoy < -0.05:
        return "capex falling" + (", turning up" if (acc or 0) > 0 else "")
    return "capex flat"


def compute(cluster_map: dict, facts_of, as_of: datetime) -> dict:
    """``{cluster: reading}`` for every cluster. ``facts_of(symbol)`` returns companyfacts JSON or None; a name that
    errors is just missing data (fail-soft)."""
    out = {}
    for name, members in sorted(cluster_map.items()):
        per = {}
        for s in sorted(members):
            try:
                per[s] = name_cycle(quarterly_capex(facts_of(s), as_of))
            except Exception as e:  # noqa: BLE001 — telemetry never breaks the cycle
                log.warning("capex cycle %s failed (non-fatal): %s", s, e)
                per[s] = None
        reading = cluster_cycle(per)
        reading["phase"] = phase(reading)
        out[name] = reading
    return out


def record_daily(cache, cluster_map: dict, facts_of, as_of: datetime) -> dict | None:
    """Compute and append today's record (one per calendar day; a re-run the same day is skipped)."""
    existing = cache.read_between(SOURCE, KEY, None, as_of)
    if any(str(r["ts"])[:10] == as_of.date().isoformat() for r in existing):
        return None
    rec = {"ts": as_of.isoformat(), "clusters": compute(cluster_map, facts_of, as_of)}
    records = [*existing, rec]
    cache.write(SOURCE, KEY, records, coverage_from=datetime.fromisoformat(records[0]["ts"]), coverage_through=as_of)
    return rec


def panel(cache, *, now: datetime | None = None) -> dict:
    """The latest record plus each cluster's YoY one record earlier (read-only, no fetch)."""
    now = now or datetime.now().astimezone()
    try:
        recs = cache.read_between(SOURCE, KEY, None, now)
    except Exception:  # noqa: BLE001
        recs = []
    if not recs:
        return {"as_of": None, "rows": [], "note": "no capex-cycle record yet (written at the next L1)"}
    last = recs[-1]
    rows = [{"cluster": k, **v} for k, v in sorted(last["clusters"].items())]
    return {"as_of": last["ts"], "records": len(recs), "rows": rows,
            "note": "Telemetry only (D5 step 1): TTM capex summed over each cluster's members, from SEC XBRL. "
                    "Nothing here gates an entry or reaches a council prompt."}
