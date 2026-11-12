"""Analyst-coverage history and trend (D6 step 1, records/2026-11-03_profit_program_DRAFTS.md) — telemetry only.

The council's ``under_narrated`` input is the analyst-coverage meter (``data/analyst_coverage.py``, ``analyst_v2``),
but that cache keeps only the latest snapshot, so nobody can see coverage *changing*. Hong, Lim & Stein (2000) found
information diffuses slowest in low-coverage names, and a name whose coverage starts to rise is a narrative forming
(records/2026-11-03_literature_review.md §2). This keeps a dated daily record of the counts the council already
fetched for the names it judged that night (no extra requests), and reports each name's latest count, its change over
~90 days, and a descriptive label.

**Telemetry only.** Nothing here gates an entry or reaches a council prompt. Per record §19 the count measures
*attention*, never "under-narrated at an inflection".
"""

from __future__ import annotations

import logging
from datetime import datetime

log = logging.getLogger("attention")

SOURCE = "attention_history"
KEY = "analyst_counts"
TREND_DAYS = 90
TREND_MIN_AGE_DAYS = 80     # the comparison record must be at least this old
QUIET_MAX, CROWDED_MIN, RISING_MIN = 5, 15, 2   # descriptive bands for the label; nothing gates on them


def record_daily(cache, symbols, count_of, as_of: datetime) -> dict | None:
    """Append today's counts for ``symbols`` (one record per calendar day; a same-day re-run merges new names into
    the day's record). ``count_of(symbol)`` returns an int or None; None and errors are left out (fail-soft)."""
    counts: dict[str, int] = {}
    for s in sorted({str(x).upper() for x in symbols}):
        try:
            n = count_of(s)
        except Exception as e:  # noqa: BLE001 — telemetry never breaks the cycle
            log.warning("analyst count %s failed (non-fatal): %s", s, e)
            continue
        if n is not None:
            counts[s] = int(n)
    if not counts:
        return None
    existing = cache.read_between(SOURCE, KEY, None, as_of)
    day = as_of.date().isoformat()
    today = next((r for r in existing if str(r["ts"])[:10] == day), None)
    if today is not None:
        merged = {**today["counts"], **counts}
        if merged == today["counts"]:
            return None
        rec = {"ts": today["ts"], "counts": merged}
        records = [r for r in existing if r is not today] + [rec]
    else:
        rec = {"ts": as_of.isoformat(), "counts": counts}
        records = [*existing, rec]
    records.sort(key=lambda r: r["ts"])
    cache.write(SOURCE, KEY, records, coverage_from=datetime.fromisoformat(records[0]["ts"]), coverage_through=as_of)
    return rec


def label(count: int | None, change: int | None) -> str:
    if count is None:
        return "unknown"
    band = "quiet" if count <= QUIET_MAX else ("crowded" if count >= CROWDED_MIN else "covered")
    if change is not None and change >= RISING_MIN:
        return f"{band}, coverage rising"
    if change is not None and change <= -RISING_MIN:
        return f"{band}, coverage falling"
    return band


def readings(records: list[dict], *, now: datetime) -> list[dict]:
    """Per name: the latest count and date, the count on the newest record at least TREND_MIN_AGE_DAYS older (within
    TREND_DAYS + 30 days), the change, and the label."""
    latest: dict[str, tuple[str, int]] = {}
    for r in records:
        for s, n in r["counts"].items():
            latest[s] = (r["ts"], n)
    out = []
    for s, (ts, n) in sorted(latest.items()):
        t = datetime.fromisoformat(ts)
        old = None
        for r in records:
            age = (t - datetime.fromisoformat(r["ts"])).days
            if TREND_MIN_AGE_DAYS <= age <= TREND_DAYS + 30 and s in r["counts"]:
                old = (r["ts"], r["counts"][s])      # records are sorted, so the last match is the newest qualifying
        change = (n - old[1]) if old else None
        out.append({"symbol": s, "count": n, "as_of": ts[:10], "count_then": old[1] if old else None,
                    "then": old[0][:10] if old else None, "change": change, "label": label(n, change),
                    "stale_days": (now - t).days})
    return out


def panel(cache, *, now: datetime | None = None) -> dict:
    now = now or datetime.now().astimezone()
    try:
        recs = cache.read_between(SOURCE, KEY, None, now)
    except Exception:  # noqa: BLE001
        recs = []
    first = recs[0]["ts"][:10] if recs else None
    days = (now - datetime.fromisoformat(recs[0]["ts"])).days if recs else 0
    return {
        "rows": readings(recs, now=now), "records": len(recs), "since": first,
        "status": (f"trend live ({days} days of history)" if days >= TREND_MIN_AGE_DAYS
                   else f"trend accruing: {days} of {TREND_MIN_AGE_DAYS} days"),
        "note": "Telemetry only (D6 step 1): analyst counts the council already fetched for the names it judged, "
                "kept daily. Coverage measures attention, never 'under-narrated at an inflection'.",
    }
