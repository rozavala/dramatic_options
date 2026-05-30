"""Substance scorer (plan §B5, task 1.3) — the "delivery" side of the divergence edge.

Deterministic, point-in-time **event-intensity** from EDGAR filings. An exponentially
**decayed** signed sum of tangible-event weights (so substance is a smooth running series
like narrative, not a mostly-zero spiky one that would collapse divergence into narrative —
plan §B5). Events and weights come from config.

**Honest framing (plan §A5):** v1 substance is *tangible-event presence*, NOT *good*
delivery — an 8-K 1.01 can be a great contract or a dilutive financing; an 8-K 2.02 fires on
a beat or a miss; Form-4 presence ignores buy/sell direction. Sign refinement (insider
net-buy via :func:`data.filings.form4_net_shares`, 10b5-1 filtering, beat/miss) is the
designated first iteration knob, not a v1 deliverable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


@dataclass
class SubstanceScore:
    symbol: str
    score: float | None
    n_events: int
    contributions: list[dict[str, Any]] = field(default_factory=list)


def _as_dt(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def _event_keys(form: str, items: list[str]) -> list[str]:
    """Map a filing record to the weight keys it triggers."""
    form = (form or "").upper()
    keys: list[str] = []
    if form.startswith("8-K"):
        keys.extend(f"8-K:{it}" for it in items)
    elif form == "4":
        keys.append("FORM4")
    elif form.startswith("SC 13D"):
        keys.append("SC 13D")
    elif form.startswith("SC 13G"):
        keys.append("SC 13G")
    elif form.startswith("S-1"):
        keys.append("S-1")
    elif form.startswith("424B"):
        keys.append("424B")
    return keys


def score_substance(
    symbol: str,
    records: list[dict[str, Any]],
    as_of: datetime,
    params: dict[str, Any],
) -> SubstanceScore:
    """Compute the delivery-intensity score for one name from its as-of filing records."""
    weights: dict[str, float] = params.get("event_weights", {})
    span = float(params.get("ewma_span_days", 30))
    lookback = int(params.get("lookback_days", 120))
    cut = as_of - timedelta(days=lookback)

    score = 0.0
    n_events = 0
    contributions: list[dict[str, Any]] = []
    for r in records:
        ts = _as_dt(r["ts"])
        if ts <= cut or ts > as_of:
            continue
        keys = _event_keys(r.get("form", ""), r.get("items", []))
        matched = [(k, weights[k]) for k in keys if k in weights]
        if not matched:
            continue
        n_events += 1
        age_days = (as_of - ts).days
        decay = math.exp(-age_days / span) if span > 0 else 1.0
        for key, w in matched:
            contribution = w * decay
            score += contribution
            contributions.append(
                {"key": key, "weight": w, "age_days": age_days, "value": round(contribution, 4)}
            )

    contributions.sort(key=lambda c: abs(c["value"]), reverse=True)
    return SubstanceScore(
        symbol=symbol,
        score=score if n_events else 0.0,
        n_events=n_events,
        contributions=contributions[:5],
    )


def has_events(records: list[dict[str, Any]], as_of: datetime, params: dict[str, Any]) -> bool:
    """Whether the name has ≥1 weight-matching filing event in the lookback (for the
    substance non-zero-density diagnostic, plan §A1 crit. 5 / §B5)."""
    weights = params.get("event_weights", {})
    lookback = int(params.get("lookback_days", 120))
    cut = as_of - timedelta(days=lookback)
    for r in records:
        ts = _as_dt(r["ts"])
        if cut < ts <= as_of and any(k in weights for k in _event_keys(r.get("form", ""), r.get("items", []))):
            return True
    return False
