"""Divergence scorer (plan §B7, task 1.5) — the core edge.

Combines the story side (:mod:`narrative`) and the delivery side (:mod:`substance`) into a
signed, cross-sectionally-normalized **divergence** per name, then aggregates to theme.

Sign convention (used everywhere downstream): ``divergence = z(narrative) − z(substance)``.
- ``divergence > 0`` → story outrunning delivery → **FADE** (hype exceeding substance).
- ``divergence < 0`` → delivery outrunning story → **LONG** (under-the-radar acceleration).
The directional *trade signal* is therefore ``s = −divergence`` (see backtest metrics).

Cross-sectional z is computed **at a single as_of across the names present that date** —
never full-sample, never trailing — and is skipped entirely when fewer than ``n_min`` names
have both components (z-scoring across 4–6 names is meaningless; plan §A5).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from narrative import score_narrative
from substance import has_events, score_substance

LONG, FADE, NEUTRAL = "LONG", "FADE", "NEUTRAL"


@dataclass
class NameSignal:
    symbol: str
    theme: str | None
    narrative_raw: float
    substance_raw: float
    narrative_z: float
    substance_z: float
    divergence: float
    direction: str
    has_substance_event: bool = False
    rationale: dict[str, Any] = field(default_factory=dict)


@dataclass
class ThemeSignal:
    theme: str
    divergence: float
    direction: str
    n_members: int
    members: list[str] = field(default_factory=list)


@dataclass
class Panel:
    as_of: datetime
    names: list[NameSignal]
    themes: list[ThemeSignal]
    n_valid: int
    n_substance_nonzero: int
    skipped: bool
    reason: str = ""


def _z(values: dict[str, float]) -> dict[str, float]:
    xs = list(values.values())
    mean = statistics.fmean(xs)
    std = statistics.pstdev(xs)
    if std < 1e-9:
        return {k: 0.0 for k in values}
    return {k: (v - mean) / std for k, v in values.items()}


def _direction(divergence: float, threshold: float) -> str:
    if divergence > threshold:
        return FADE
    if divergence < -threshold:
        return LONG
    return NEUTRAL


def build_panel(
    as_of: datetime,
    symbols: list[str],
    theme_of: dict[str, str],
    *,
    news: Any,
    filings: Any,
    config: dict[str, Any],
    insider: Any | None = None,
) -> Panel:
    """Compute the divergence panel for ``symbols`` as-of ``as_of``.

    ``news`` and ``filings`` are the as-of adapters (:class:`data.news.NewsData`,
    :class:`data.filings.FilingsData`); ``insider`` (optional, :class:`data.insider.
    InsiderData`) supplies signed net-buy events for the refined substance score. Callers
    pass the already-eligibility-filtered symbol list (eligibility uses price+ADV from
    market data, owned by the caller — plan §B1).
    """
    sig = config.get("signal", {})
    narr_params = sig.get("narrative", {})
    subst_params = sig.get("substance", {})
    div_params = sig.get("divergence", {})
    n_min = int(div_params.get("n_min_cross_section", 8))
    threshold = float(div_params.get("neutral_threshold", 0.5))

    narr_raw: dict[str, float] = {}
    subst_raw: dict[str, float] = {}
    rationale_bits: dict[str, dict[str, Any]] = {}
    has_event: dict[str, bool] = {}
    n_substance_nonzero = 0

    for sym in symbols:
        news_recs = news.headlines_asof(sym, as_of)
        filing_recs = filings.filings_asof(sym, as_of)
        insider_recs = insider.netbuy_asof(sym, as_of) if insider is not None else None
        ns = score_narrative(sym, news_recs, as_of, narr_params)
        ss = score_substance(sym, filing_recs, as_of, subst_params, insider_records=insider_recs)
        if ns.score is None or ss.score is None:
            continue
        narr_raw[sym] = ns.score
        subst_raw[sym] = ss.score
        has_event[sym] = has_events(filing_recs, as_of, subst_params, insider_records=insider_recs)
        if has_event[sym]:
            n_substance_nonzero += 1
        rationale_bits[sym] = {
            "narrative": {
                "count_recent": ns.count_recent,
                "acceleration": ns.acceleration,
                "breadth": ns.breadth,
                "top_headlines": ns.top_headlines,
            },
            "substance": {"n_events": ss.n_events, "top_events": ss.contributions},
        }

    n_valid = len(narr_raw)
    if n_valid < n_min:
        return Panel(
            as_of=as_of, names=[], themes=[], n_valid=n_valid,
            n_substance_nonzero=n_substance_nonzero, skipped=True,
            reason=f"n_valid={n_valid} < n_min={n_min}",
        )

    narr_z = _z(narr_raw)
    subst_z = _z(subst_raw)
    names: list[NameSignal] = []
    for sym in narr_raw:
        divergence = narr_z[sym] - subst_z[sym]
        names.append(
            NameSignal(
                symbol=sym,
                theme=theme_of.get(sym),
                narrative_raw=narr_raw[sym],
                substance_raw=subst_raw[sym],
                narrative_z=narr_z[sym],
                substance_z=subst_z[sym],
                divergence=divergence,
                direction=_direction(divergence, threshold),
                has_substance_event=has_event.get(sym, False),
                rationale=rationale_bits[sym],
            )
        )
    names.sort(key=lambda n: n.divergence)  # most-LONG first, most-FADE last
    themes = aggregate_themes(names, threshold)
    return Panel(
        as_of=as_of, names=names, themes=themes, n_valid=n_valid,
        n_substance_nonzero=n_substance_nonzero, skipped=False,
    )


def aggregate_themes(names: list[NameSignal], threshold: float) -> list[ThemeSignal]:
    """Theme divergence = median of member name divergences (plan §A3 — reported, not gated)."""
    by_theme: dict[str, list[NameSignal]] = {}
    for n in names:
        if n.theme:
            by_theme.setdefault(n.theme, []).append(n)
    out: list[ThemeSignal] = []
    for theme, members in by_theme.items():
        div = statistics.median(m.divergence for m in members)
        out.append(
            ThemeSignal(
                theme=theme,
                divergence=div,
                direction=_direction(div, threshold),
                n_members=len(members),
                members=[m.symbol for m in members],
            )
        )
    out.sort(key=lambda t: t.divergence)
    return out
