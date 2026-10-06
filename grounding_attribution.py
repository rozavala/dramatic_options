"""§5b grounding outcome attribution (PREREG_EVIDENCE_GROUNDING §5b) — the ONE added read.

The includes-make-money question is OWNED by the existing pre-registered instruments
(`PREREG_FIXED_BASKET_NULL`'s council = real − shadow, the never-traded reference sweep, Brier /
agent-contribution). This module ADDS exactly one finer read on the SAME machinery: the
**proposal-level contrast — include=true vs DELIBERATED-but-rejected vs controls** — on the
{180, 270, 365} reference-return horizons + the §6 terminal-event guard, **tail (p95) not mean**.

Read-only, NEVER a gate, **compute-when-mature**: the book is empty and selections take ~180d+ to
resolve, so it renders an "accruing" empty-state today. **Citation threshold (pinned): not citable in
EITHER direction below 10 includes.** Cohorts are **deduped by symbol** (R2-#7 — a name that is both a
hand-seed and a surfaced sentinel on one day must not double-weight). Caps/affordability never touch it.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from sentinel_scoring import reference_return_from_bars

DEFAULT_HORIZONS = (180, 270, 365)
CITE_MIN_INCLUDES = 10

CAVEATS = (
    "Forward, compute-when-mature; the includes-make-money VERDICT is owned by real−shadow / the "
    "reference sweep / Brier — this is the finer proposal-level read, never a gate (PREREG §5b).",
    "NOT citable in either direction below 10 includes; ~180d+ of corpus-influenced selections accrue "
    "before the first judgment-quality read matures (the same horizon clock as Brier).",
    "p95 TAIL, never the mean (a convex book's value is the tail); cohorts deduped by symbol.",
)


def _deliberated(rationale) -> bool | None:
    """True = a full round-trip (the strategist deliberated then rejected); False = an early-exit drop
    (ungrounded / proposer-abstain — NOT a deliberated reject); None = unparseable."""
    if not rationale:
        return None
    try:
        d = json.loads(rationale) if isinstance(rationale, str) else rationale
    except Exception:  # noqa: BLE001
        return None
    if "strategist" in d:
        return True
    if "dropped" in d:
        return False
    return None


def _ts(bar) -> datetime | None:
    try:
        return datetime.fromisoformat(bar["ts"])
    except (ValueError, TypeError, KeyError):
        return None


def _entry_close(market, symbol: str, as_of: datetime) -> float | None:
    """The last bar close at/before the proposal's as_of (the reference entry — proposals don't store
    a spot; this reconstructs it PIT from the cache)."""
    bars = market.cache.read_between("bars", symbol, as_of - timedelta(days=10), as_of)
    closes = [b["close"] for b in bars if (_ts(b) is not None and _ts(b) <= as_of)]
    return float(closes[-1]) if closes else None


def _dedup_latest(rows: list[tuple]) -> list[tuple]:
    """Keep one (symbol, as_of, direction) per SYMBOL — the latest as_of (R2-#7 dedup)."""
    by_sym: dict[str, tuple] = {}
    for r in rows:
        if r[0] not in by_sym or r[1] > by_sym[r[0]][1]:
            by_sym[r[0]] = r
    return list(by_sym.values())


def _p95(xs: list[float]) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    i = min(len(s) - 1, int(round(0.95 * (len(s) - 1))))
    return s[i]


def _cohort_tails(rows: list[tuple], market, *, now: datetime, horizons) -> dict:
    """Per-horizon {n, p95} for one deduped cohort, signed by direction, terminal-guarded."""
    rows = _dedup_latest(rows)
    per_h: dict[int, list[float]] = {h: [] for h in horizons}
    for symbol, as_of, direction in rows:
        entry = _entry_close(market, symbol, as_of)
        if entry is None:
            continue
        is_bull = direction == "bullish"
        fwd = [float(b["close"]) for b in market.cache.read_between("bars", symbol, as_of, now)
               if (_ts(b) is not None and _ts(b) > as_of)]
        for h in horizons:
            terminated = now >= as_of + timedelta(days=int(h * 1.6) + 4) and 0 < len(fwd) < h
            raw, _tag = reference_return_from_bars(entry, fwd, h, terminated=terminated)
            if raw is None:
                continue
            per_h[h].append(raw if is_bull else -raw)
    return {"n_names": len(rows),
            "horizons": {f"h{h}": {"n": len(per_h[h]), "p95": _p95(per_h[h])} for h in horizons}}


def grounding_attribution_report(conn, market, *, now: datetime, horizons=DEFAULT_HORIZONS) -> dict:
    """The §5b proposal-level contrast. Read-only; compute-when-mature (renders ``citable=False`` until
    ≥10 includes resolve). ``market`` is a NO-FETCH ``MarketData`` over the cache (the dashboard's)."""
    horizons = list(horizons)
    include_rows: list[tuple] = []
    reject_rows: list[tuple] = []
    for p in conn.execute(
        "SELECT symbol, as_of, direction, status, rationale FROM council_proposals"
    ).fetchall():
        try:
            as_of = datetime.fromisoformat(p["as_of"])
        except (ValueError, TypeError):
            continue
        row = (p["symbol"], as_of, p["direction"])
        if p["status"] == "proposed":
            include_rows.append(row)              # include=true (passed the conviction floor)
        elif _deliberated(p["rationale"]):
            reject_rows.append(row)               # deliberated-but-rejected (full round-trip, below floor)

    control_rows: list[tuple] = []
    for c in conn.execute(
        "SELECT symbol, discovered_at, direction FROM sentinel_candidates WHERE status = 'control'"
    ).fetchall():
        try:
            control_rows.append((c["symbol"], datetime.fromisoformat(c["discovered_at"]), c["direction"]))
        except (ValueError, TypeError):
            continue

    n_includes = len(_dedup_latest(include_rows))
    return {
        "caveats": list(CAVEATS),
        "n_includes": n_includes,
        "citable": n_includes >= CITE_MIN_INCLUDES,
        "cohorts": {
            "include": _cohort_tails(include_rows, market, now=now, horizons=horizons),
            "deliberated_reject": _cohort_tails(reject_rows, market, now=now, horizons=horizons),
            "control": _cohort_tails(control_rows, market, now=now, horizons=horizons),
        },
    }
