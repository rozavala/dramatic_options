"""Narrative scorer (plan §B6, task 1.4) — the "story" side of the divergence edge.

Deterministic, cheap text-intensity from news headlines — **not** the council (Phase 3).
The score leans on the robust components — coverage **intensity**, **acceleration**, and
**breadth** — each normalized against the name's *own* trailing baseline so a perpetually
well-covered name doesn't dominate a name whose coverage just jumped (coverage-bias control,
plan §A/§B6). A small built-in finance lexicon contributes **low-weight, diagnostic-only**
sentiment, because lexicon polarity on headlines is noisy ("beats but guides down").

Pure functions over the as-of news records produced by :mod:`data.news` — no I/O here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

# Small finance-tilted sentiment lexicon (low-weight / diagnostic — see module docstring).
_POS = {
    "surge", "soar", "beat", "beats", "record", "growth", "wins", "win", "award", "awarded",
    "contract", "approval", "approved", "upgrade", "raises", "raised", "strong", "demand",
    "partnership", "expands", "milestone", "breakthrough", "profit", "profitable",
}
_NEG = {
    "miss", "misses", "plunge", "slump", "downgrade", "cuts", "cut", "lawsuit", "probe",
    "recall", "halts", "halt", "delay", "delayed", "dilution", "offering", "bankruptcy",
    "investigation", "warning", "weak", "loss", "losses", "fraud", "decline", "slashes",
}


@dataclass
class NarrativeScore:
    symbol: str
    score: float | None
    count_recent: int
    count_z: float | None
    acceleration: float | None
    breadth: float | None
    sentiment: float | None
    top_headlines: list[str] = field(default_factory=list)


def _as_dt(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def _lexicon_sentiment(headline: str) -> float:
    words = {w.strip(".,!:;\"'()").lower() for w in headline.split()}
    pos = len(words & _POS)
    neg = len(words & _NEG)
    if pos == 0 and neg == 0:
        return 0.0
    return (pos - neg) / (pos + neg)


def score_narrative(
    symbol: str,
    records: list[dict[str, Any]],
    as_of: datetime,
    params: dict[str, Any],
) -> NarrativeScore:
    """Compute the story-intensity score for one name from its as-of news records."""
    cw = int(params.get("count_window_days", 21))
    bw = int(params.get("baseline_window_days", 126))
    span = int(params.get("ewma_span_days", 10))
    lex_w = float(params.get("lexicon_weight", 0.15))

    times = [_as_dt(r["ts"]) for r in records]
    recent_cut = as_of - timedelta(days=cw)
    baseline_cut = as_of - timedelta(days=bw)

    recent = [r for r, t in zip(records, times, strict=True) if t > recent_cut]
    count_recent = len(recent)

    # ── own-baseline z of the windowed count (bins of size cw over the baseline span) ──
    base = [t for t in times if baseline_cut < t <= recent_cut]
    count_z: float | None = None
    n_bins = max(1, (bw - cw) // cw)
    if base and n_bins >= 2:
        bins = [0] * n_bins
        for t in base:
            age = (recent_cut - t).days
            idx = min(n_bins - 1, age // cw)
            bins[idx] += 1
        mean = sum(bins) / n_bins
        var = sum((b - mean) ** 2 for b in bins) / n_bins
        std = var ** 0.5
        count_z = (count_recent - mean) / std if std > 1e-9 else (count_recent - mean)

    # ── acceleration: recent EWMA of daily counts vs the baseline-span mean ──
    acceleration = _acceleration([t for t in times if t > baseline_cut], as_of, span, bw)

    # ── breadth: fraction of distinct days covered in the recent window ──
    distinct_days = {(_as_dt(r["ts"])).date() for r in recent}
    breadth = len(distinct_days) / cw if cw else 0.0

    # ── sentiment (low-weight / diagnostic) ──
    sentiment = (
        sum(_lexicon_sentiment(r.get("headline", "")) for r in recent) / count_recent
        if count_recent
        else 0.0
    )

    # If a name has no usable baseline, fall back to a raw-but-bounded intensity.
    intensity = count_z if count_z is not None else float(count_recent)
    score = (
        intensity
        + 0.5 * (acceleration or 0.0)
        + 0.5 * (breadth or 0.0)
        + lex_w * (sentiment or 0.0)
    )
    top = [r.get("headline", "") for r in recent[-3:]]
    return NarrativeScore(
        symbol=symbol,
        score=score,
        count_recent=count_recent,
        count_z=count_z,
        acceleration=acceleration,
        breadth=breadth,
        sentiment=sentiment,
        top_headlines=top,
    )


def _acceleration(times: list[datetime], as_of: datetime, span: int, window: int) -> float | None:
    """Recent EWMA of daily article counts vs the window mean, as a ratio."""
    if not times:
        return 0.0
    counts: dict[int, int] = {}
    for t in times:
        day = (as_of.date() - t.date()).days
        if 0 <= day < window:
            counts[day] = counts.get(day, 0) + 1
    if not counts:
        return 0.0
    # EWMA walking from oldest day → today (day 0 is most recent).
    alpha = 2.0 / (span + 1)
    ewma = 0.0
    for day in range(window - 1, -1, -1):
        ewma = alpha * counts.get(day, 0) + (1 - alpha) * ewma
    mean = sum(counts.values()) / window
    return (ewma - mean) / (mean + 1e-9)
