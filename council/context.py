"""ContextPack — the grounded evidence a council agent reasons over (T2 + the §9 corpus).

A candidate is a ``themes.Theme`` from the operator's watchlist (themes.json) or a T3 sentinel.
For each, we assemble **current** evidence — recent news headlines via ``data/news.py:NewsData``
(hand-seeds) or deterministic markers (sentinels) — plus the §9 evidence-grounding corpus
(``data/fundamentals.py``: filed XBRL numbers) and the §19 sell-side **analyst-coverage** count
(``data/analyst_coverage.py``). The pack carries the operator's seed thesis as the *hypothesis to
test*, kept separate from the *evidence* used for grounding.

**§9 (PREREG_EVIDENCE_GROUNDING) — evidence, never permission:**
- ``fundamentals`` (the pinned corpus lines) + the ``analyst_count`` coverage proxy enrich every
  pack; they NEVER loosen a floor/criterion/gate/cap.
- The ONE behavior change is origin-scoped: a thin-news **hand-seed** with fundamentals-present is
  now ``grounded`` (the OR-leg — it deliberates instead of $0-dropping). A **sentinel**'s
  ``grounded`` is byte-unchanged (markers ⇔ grounded).

**§19 (accel-feed record, 2026-06-30) — analyst-coverage replaces news-count as the coverage
proxy:** the ``under_narrated`` attention input is now the sell-side analyst count (a materially
better meter than the sparse free news feed — Jaccard ~0.46 vs news-quiet), rendered as the
``ANALYST_COVERAGE`` line. News HEADLINES still ground the pack (``coverage_count``/``has_numeric``
→ ``grounded``); only the trailing news *counts* are retired as the attention signal. Attention,
not inflection — a low count is a quietness proxy, never proof of an inflection (record §19 caveat).

**Framer byte-identity (§6 leash):** the T3 framer builds its pack via ``sentinel_context_pack``
with no corpus (``fundamentals=None``, ``analyst_count=None``), so ``as_prompt_block`` renders
exactly as it did pre-§9 (the ``NEWS_COVERAGE: N article(s)`` fallback). The FUNDAMENTALS /
ANALYST_COVERAGE lines are purely conditional (rendered only when present), so the framer's prompt
is unchanged. (§2 pins FUNDAMENTALS after the headlines block and the coverage line stays in place —
order pinned in the tests; the anti-HARK purpose [a fixed, stamped order] is preserved.)
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
    # §9 corpus (default-empty/None ⇒ pre-§9 behavior; the framer pack carries none → byte-identical)
    fundamentals: list[dict] = field(default_factory=list)
    fundamentals_status: str | None = None     # corpus_asof's empty|partial|ok (reused, not redefined)
    # §19 analyst-coverage proxy — None = "not fetched" (framer / feed outage); int (even 0) = fetched
    analyst_count: int | None = None
    origin: str = "hand-seed"                  # "hand-seed" | "sentinel" — gates the grounded OR-leg

    @property
    def fundamentals_present(self) -> bool:
        """§3 pin: ≥1 revenue-family line OR ≥2 lines total — counting only lines that actually
        RENDER (``value is not None``), so the grounding gate matches the rendered evidence."""
        present = [ln for ln in self.fundamentals if ln.get("value") is not None]
        return sum(1 for ln in present if ln.get("concept") == "revenue") >= 1 or len(present) >= 2

    @property
    def grounded(self) -> bool:
        """Evidence sufficient for a data-dependent agent to form a non-NEUTRAL view.

        §3 OR-leg, origin-scoped: a **hand-seed** grounds on news-numerics OR fundamentals-present
        (the thin-news fix); a **sentinel** grounds on markers ALONE (byte-unchanged — fundamentals
        enrich, never gate)."""
        base = self.coverage_count > 0 and self.has_numeric
        return (base or self.fundamentals_present) if self.origin == "hand-seed" else base

    def as_prompt_block(self) -> str:
        lines = [
            f"CANDIDATE: {self.symbol} {self.direction} {self.theme}",
            f"OPERATOR_THESIS: {self.operator_thesis}",
        ]
        # ANALYST_COVERAGE (§19) — the sell-side attention proxy; conditional so the framer pack
        # (analyst_count None) is byte-identical to pre-§9 (the article-count fallback below):
        if self.analyst_count is not None:
            lines.append(f"ANALYST_COVERAGE: {self.analyst_count} analyst(s) covering "
                         "(sell-side attention; fewer = more under-covered — a quietness proxy, "
                         "not an inflection signal)")
        else:
            lines.append(f"NEWS_COVERAGE: {self.coverage_count} article(s)"
                         + (f" as of {self.as_of.date().isoformat()}" if self.as_of else ""))
        if self.headlines:
            lines.append("RECENT_HEADLINES:")
            lines.extend(f"  - {h}" for h in self.headlines)
        else:
            lines.append("RECENT_HEADLINES: (none)")
        # §9 FUNDAMENTALS — appended after headlines, rendered only when present (framer → none):
        rendered = [r for r in (_fmt_fundamental_line(ln) for ln in self.fundamentals) if r]
        if rendered:
            lines.append("FUNDAMENTALS:")
            lines.extend(rendered)
        if not self.grounded:
            lines.append("GROUNDING: INSUFFICIENT (no numeric evidence) — return NEUTRAL.")
        return "\n".join(lines)


def _fmt_fundamental_line(ln: dict) -> str | None:
    """Render one §9 corpus line — metric-aware, NEVER raises (the render runs inside
    ``run_candidate``, which ``propose`` does not guard for a formatting error; §9 is
    ``corpus_asof``'s first live run). A line with no ``value`` is skipped, not crashed.

    Unit keyed on the METRIC (not a concept/metric hybrid): ttm_yoy/qtr_yoy/yoy → %; delta_pts →
    pts; qtr_yoy_accel (and any future unitless) → plain signed. The concept drives only the label
    + the parenthetical: $-concepts → ``($Xm vs $Ym)``; gross_margin carries margin-% in the _musd
    fields → ``(X% vs Y% margin)``; accel has ``latest_musd=None`` → no parenthetical."""
    vtxt = _fmt_value(ln)
    if vtxt is None:
        return None
    concept = ln.get("concept", "?")
    metric = ln.get("metric", "")
    latest, base = ln.get("latest_musd"), ln.get("base_musd")
    if latest is None:
        paren = ""
    elif concept == "gross_margin":
        paren = f" ({latest}% vs {base}% margin)" if base is not None else f" ({latest}% margin)"
    else:
        paren = f" (${latest}M vs ${base}M)" if base is not None else f" (${latest}M)"
    cadence = " (annual)" if metric == "rev_annual_yoy" else ""
    return f"- {concept} {metric} {vtxt}{paren}; period {ln.get('period_end')}{cadence}, filed {ln.get('filed')}"


def _fmt_value(ln: dict) -> str | None:
    """The agent-facing value token for one corpus line (unit keyed on the METRIC). None when the
    line has no ``value`` (skip — never raise). Shared by the renderer and the authenticity-filter
    evidence pool so a REAL citation ("12.3%") matches what was rendered, not the raw ratio."""
    value = ln.get("value")
    if value is None:
        return None
    metric = ln.get("metric", "")
    if metric in ("ttm_yoy", "qtr_yoy", "yoy", "rev_annual_yoy"):
        return f"{value:+.1%}"
    if metric == "delta_pts":
        return f"{value:+.1f}pts"
    return f"{value:+.3f}"  # qtr_yoy_accel + any future unitless metric


def fundamental_evidence_tokens(pack) -> list[str]:
    """The §9 corpus NUMERIC tokens the council may legitimately cite — the formatted value (as
    rendered) + the $M/margin figures + the §19 analyst-coverage count. DATES are excluded on
    purpose (``period_end``/``filed`` are pure digit-noise that would let a fabricated number pass
    ``authenticity_scan``'s digit-substring match). Used by ``filters.evidence_text``."""
    toks: list[str] = []
    for ln in getattr(pack, "fundamentals", None) or []:
        v = _fmt_value(ln)
        if v is not None:
            toks.append(v)
        for k in ("latest_musd", "base_musd"):
            x = ln.get(k)
            if x is not None:
                toks.append(str(x))
    ac = getattr(pack, "analyst_count", None)
    if ac is not None:
        toks.append(str(ac))
    return toks


def _has_numeric(texts: list[str]) -> bool:
    return any(any(ch.isdigit() for ch in t) for t in texts)


def _marker_evidence(markers: dict) -> list[str]:
    """Turn a sentinel's deterministic markers into numeric evidence strings (the grounding
    corpus). These carry digits, so a pre-news discovered name is `grounded` on facts, not news.

    Each marker is rendered with an explicit HORIZON LABEL (PREREG_FRESH_INFLECTION_FUNNEL §7) so
    at_inflection can read the recent-vs-trailing contrast the fresh-inflection re-target hinges on —
    `momentum_12m` (a big trailing move may be BEHIND the name) vs `momentum_recent_3m` (the move is
    happening NOW). The display labels carry the horizon; the underlying markers-dict keys are
    unchanged. Contrasting pairs are rendered adjacent."""
    lines: list[str] = []
    for key, label in (
        ("momentum", "momentum_12m"),          # trailing 12-1 (252d, skip 21)
        ("mom_recent", "momentum_recent_3m"),  # recent 63d, no skip (freshness)
        ("rel_strength", "rel_strength_12m"),
        ("rv_slope", "rv_reexpansion_1y"),     # rv_21 vs rv_252
        ("rv_rising", "rv_accel_3m"),          # rv_21 vs rv_63 (freshness)
        ("rv", "rv_annualized"),
    ):
        v = markers.get(key)
        if isinstance(v, (int, float)):
            lines.append(f"{label} {v:+.3f}")
    if markers.get("has_event"):
        lines.append(f"structural_event {markers.get('event_kind') or 'present'}")
    px, adv = markers.get("price"), markers.get("adv_usd")
    if isinstance(px, (int, float)):
        lines.append(f"price {px:.2f}")
    if isinstance(adv, (int, float)):
        lines.append(f"adv_usd {adv:.0f}")
    return lines


def _analyst_count(analyst, symbol: str, as_of: datetime) -> int | None:
    """Sell-side covering-analyst count (§19 — the coverage/under-narration proxy that replaced
    news-count as a materially better attention meter). ``analyst`` is a duck-typed
    ``data/analyst_coverage.py:AnalystCoverageData`` exposing ``count_asof(symbol, as_of)``.
    Fail-soft: analyst None or any error → None = "not fetched" (the framer / a feed outage),
    which renders as the pre-§19 NEWS_COVERAGE article-count line."""
    if analyst is None:
        return None
    try:
        return analyst.count_asof(symbol, as_of)
    except Exception:  # noqa: BLE001 — best-effort; absent → pre-§19 line
        return None


def _fundamentals_corpus(fundamentals, symbol: str, as_of: datetime, *, force_refresh: bool
                         ) -> tuple[list[dict], str | None]:
    """The §9 corpus lines + status for one name. Fail-soft: ``fundamentals`` None or any error →
    ([], None) so the pack degrades to pre-§9 grounding, never raising into the cycle. (``corpus_asof``
    is itself fail-soft; this is belt-and-suspenders + the None-provider case.)"""
    if fundamentals is None:
        return [], None
    try:
        res = fundamentals.corpus_asof(symbol, as_of, force_refresh=force_refresh)
        return list(res.get("lines", [])), res.get("status")
    except Exception:  # noqa: BLE001
        return [], None


def sentinel_context_pack(
    candidate: Theme, *, as_of: datetime,
    fundamentals: list[dict] | None = None, fundamentals_status: str | None = None,
    analyst_count: int | None = None,
) -> ContextPack:
    """Origin-aware grounding for a DISCOVERED (source='sentinel') candidate: ground on its
    deterministic MARKERS, not news (T3 PR2). Without this both the framer and the council would
    NEUTRAL-drop every pre-news discovery for lack of coverage. ``grounded`` ⇔ markers present
    ("something is actually inflecting"), the correct early-exit — not "no news".

    **§9/§19:** the enrichment params default None/[] → the T3 FRAMER (which calls this directly with
    none) gets a byte-identical pack; the COUNCIL path (``build_context_pack``) passes the fetched
    corpus + the analyst count so a council sentinel pack carries markers + FUNDAMENTALS + the
    coverage proxy (§3). ``grounded`` stays markers-only (origin='sentinel' → no OR-leg)."""
    # KNOWN LIMITATION (PREREG_FRESH_INFLECTION_FUNNEL §7.1): these markers are the PERSISTED ones from the
    # last L0 that surfaced the name into the top-K — NOT recomputed at the daily L1 (compute_markers runs
    # only in the discovery path), while build_context_pack fetches news + fundamentals FRESH each cycle. So
    # the binding `at_inflection` leg is grounded on STALE markers. See §7.1 for the MEASURED magnitude
    # (TTL-bounded; weeks) — kept there as the single source of truth so the number can't drift. Decoupled.
    markers = (getattr(candidate, "markers", None) or {})
    lines = _marker_evidence(markers)
    return ContextPack(
        symbol=candidate.symbol, theme=candidate.name, direction=candidate.direction,
        operator_thesis=candidate.thesis or "discovery hypothesis (markers-grounded)",
        headlines=lines, coverage_count=len(lines), has_numeric=_has_numeric(lines),
        as_of=as_of, notes=["sentinel: grounded on deterministic markers, not news"],
        fundamentals=fundamentals or [], fundamentals_status=fundamentals_status,
        analyst_count=analyst_count, origin="sentinel",
    )


def build_context_pack(
    candidate: Theme,
    *,
    news,
    as_of: datetime,
    lookback_days: int = 90,
    max_headlines: int = 12,
    fundamentals=None,
    analyst=None,
) -> ContextPack:
    """Assemble current grounding for one candidate. ``news`` is a duck-typed object exposing
    ``headlines_asof(symbol, as_of) -> list[{'headline': str, 'ts': str, ...}]``
    (``data/news.py:NewsData``); ``fundamentals`` is a ``data/fundamentals.py:FundamentalsData``
    (None = pre-§9); ``analyst`` is a ``data/analyst_coverage.py:AnalystCoverageData`` exposing
    ``count_asof`` (None = pre-§19). Fail-soft: any provider error → degrades grounding, never raises.

    **§9/§19:** fetches the corpus + the analyst-coverage count and forwards them to BOTH origin
    branches — the SENTINEL branch must forward them too (else the council's live sentinels, and the
    gated 16-sentinel re-score, are enrichment-blind). ``force_refresh`` on a fresh filing event
    (markers.has_event — sentinels only; the None-guard makes it False for markerless hand-seeds)."""
    force_refresh = bool((getattr(candidate, "markers", None) or {}).get("has_event"))
    fund_lines, fund_status = _fundamentals_corpus(fundamentals, candidate.symbol, as_of,
                                                   force_refresh=force_refresh)
    analyst_count = _analyst_count(analyst, candidate.symbol, as_of)

    if getattr(candidate, "source", "hand-seed") == "sentinel":
        return sentinel_context_pack(
            candidate, as_of=as_of, fundamentals=fund_lines, fundamentals_status=fund_status,
            analyst_count=analyst_count,
        )

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
        fundamentals=fund_lines, fundamentals_status=fund_status,
        analyst_count=analyst_count, origin="hand-seed",
    )


def synthetic_context_pack(candidate: Theme, *, as_of: datetime | None = None) -> ContextPack:
    """Deterministic grounded pack for ``--demo`` / tests (mirrors SyntheticChainProvider).

    Provides two numeric headlines so the early-exit rule passes and the offline pipeline runs
    end-to-end. The IV/cheap-convexity gate — not the council — decides cheapness downstream.
    **§9/§19 untouched:** no corpus, ``analyst_count=None`` → renders the pre-§9 NEWS_COVERAGE line.
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
