"""ContextPack — the grounded evidence a council agent reasons over (T2).

A candidate is a ``themes.Theme`` from the operator's watchlist (themes.json). For each, we
assemble **current** evidence — recent news headlines via ``data/news.py:NewsData`` constructed
with ``fetch_end = as_of = clock.now()`` (verified to fetch fresh, not replay-only). The pack
carries the operator's seed thesis as the *hypothesis to test*, kept separate from the news
*evidence* used for grounding.

**Early-exit rule (SPEC §5):** if the evidence lacks numeric content, the agent must not
manufacture a confident view — the candidate resolves to NEUTRAL and is dropped. On the free
Alpaca feed coverage is often ~0, so "the council proposed nothing this cycle" is a common,
healthy fail-closed outcome, not a bug. (Filing-event grounding via ``data/filings.py`` needs
ticker→CIK resolution — a deferred enrichment hook, not wired here.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from themes import Theme


@dataclass(frozen=True)
class ContextPack:
    symbol: str
    theme: str
    direction: str
    operator_thesis: str            # the hypothesis to test (NOT counted as grounding evidence)
    headlines: list[str] = field(default_factory=list)
    coverage_count: int = 0
    has_numeric: bool = False
    as_of: datetime | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def grounded(self) -> bool:
        """Evidence sufficient for a data-dependent agent to form a non-NEUTRAL view."""
        return self.coverage_count > 0 and self.has_numeric

    def as_prompt_block(self) -> str:
        lines = [
            f"CANDIDATE: {self.symbol} {self.direction} {self.theme}",
            f"OPERATOR_THESIS: {self.operator_thesis}",
            f"NEWS_COVERAGE: {self.coverage_count} article(s)"
            + (f" as of {self.as_of.date().isoformat()}" if self.as_of else ""),
        ]
        if self.headlines:
            lines.append("RECENT_HEADLINES:")
            lines.extend(f"  - {h}" for h in self.headlines)
        else:
            lines.append("RECENT_HEADLINES: (none)")
        if not self.grounded:
            lines.append("GROUNDING: INSUFFICIENT (no numeric evidence) — return NEUTRAL.")
        return "\n".join(lines)


def _has_numeric(texts: list[str]) -> bool:
    return any(any(ch.isdigit() for ch in t) for t in texts)


def build_context_pack(
    candidate: Theme,
    *,
    news,
    as_of: datetime,
    lookback_days: int = 90,
    max_headlines: int = 12,
) -> ContextPack:
    """Assemble current grounding for one candidate. ``news`` is a duck-typed object exposing
    ``headlines_asof(symbol, as_of) -> list[{'headline': str, ...}]`` (``data/news.py:NewsData``).
    Fail-soft: any news error → an ungrounded pack (→ NEUTRAL), never raises into the cycle."""
    headlines: list[str] = []
    notes: list[str] = []
    try:
        recs = news.headlines_asof(candidate.symbol, as_of) if news is not None else []
        cutoff = as_of - timedelta(days=lookback_days)
        for r in recs:
            ts = r.get("ts")
            if ts:
                try:
                    if datetime.fromisoformat(ts) < cutoff:
                        continue
                except ValueError:
                    pass
            h = (r.get("headline") or "").strip()
            if h:
                headlines.append(h)
        headlines = headlines[-max_headlines:]
    except Exception as e:  # noqa: BLE001 — grounding is best-effort; absent evidence → NEUTRAL
        notes.append(f"news error: {e}")

    return ContextPack(
        symbol=candidate.symbol, theme=candidate.name, direction=candidate.direction,
        operator_thesis=candidate.thesis, headlines=headlines,
        coverage_count=len(headlines), has_numeric=_has_numeric(headlines),
        as_of=as_of, notes=notes,
    )


def synthetic_context_pack(candidate: Theme, *, as_of: datetime | None = None) -> ContextPack:
    """Deterministic grounded pack for ``--demo`` / tests (mirrors SyntheticChainProvider).

    Provides two numeric headlines so the early-exit rule passes and the offline pipeline runs
    end-to-end. The IV/cheap-convexity gate — not the council — decides cheapness downstream.
    """
    headlines = [
        f"{candidate.symbol} names cited as a {candidate.direction} expression of {candidate.name}; "
        f"shares moved 3% on the session",
        f"Analysts flag {candidate.name} demand up ~12% YoY against constrained supply",
    ]
    return ContextPack(
        symbol=candidate.symbol, theme=candidate.name, direction=candidate.direction,
        operator_thesis=candidate.thesis, headlines=headlines,
        coverage_count=len(headlines), has_numeric=True, as_of=as_of,
        notes=["synthetic (demo) grounding"],
    )
