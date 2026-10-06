"""Sentinel inflection discovery — the deterministic prescreen (T3, PR1).

PREREG_THEMATIC_CONVEXITY §2 hard seam: discovery **proposes** candidate names; the council
**judges**; the deterministic Layer-1 gates **dispose**. This module is the funnel that surfaces
candidates — it makes **no alpha / cheapness claim** (cheapness is the IV gate's job, fresh and
authoritative; ranking the prescreen on it would pre-select for gate-pass and defeat the gate's
independence). The prescreen claims only "**something is happening here**".

Two design rules learned in plan-review and enforced here:

1. **Surface = a disjunctive GATE on ABSOLUTE floors, not a weighted blend.** A name surfaces iff a
   structural event is present OR a FRESH inflection (``|mom_recent| ≥ fresh_mom_floor`` AND
   ``rv_rising ≥ fresh_rv_rising_floor``) OR ``|mom_12-1| ≥ mom_floor`` OR ``rv_slope ≥ rv_slope_floor``
   (the freshness leg = PREREG_FRESH_INFLECTION_FUNNEL §4; checked before the trailing legs, §8.1).
   Heterogeneous markers (a continuous z vs a 0/1 filing flag) are **never summed** into the
   surface decision — that has no principled exchange rate and collapses into whatever you weighted
   (the FSSD friction-composite-→-smallness failure). Absolute floors are also the only thing that
   delivers "a dead week surfaces nothing" — a relative z always has a top-of-distribution name.

2. **Within-basket z only RANKS the names that already cleared the gate** (ordering / top-K).
   Pooling heterogeneous baskets into one z would bury a low-vol basket's real inflection under a
   high-vol basket's raw magnitudes — so z is computed **per basket**. The rank is the within-basket
   FRESHNESS composite (``z(rv_rising) + z(|mom_recent|)``) — trailing magnitude removed so the top-K
   is the freshest names, not the biggest movers (PREREG_FRESH_INFLECTION_FUNNEL §5).

Two-sided: the sign of the motion sets direction (tailwind → bullish/calls, rollover →
bearish/puts). Pure functions over an injected ``MarketData`` + an optional structural-event
provider → fully offline-testable.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol

from convexity_gate import realized_vol

log = logging.getLogger("discovery")

# The live discovery-prescreen funnel version, stamped per discovery run into runs.discovery_funnel
# (migration 0015) so the forward-scored layers segment OLD vs NEW funnels (PREREG_FRESH_INFLECTION_FUNNEL
# §8). Bump this string when the funnel's surface/rank knobs change in a record-segmenting way.
# fresh_v1→fresh_v2: the lone-basket rank fix (a <2-clearer basket fell to a degenerate within-basket
# z of 0.0 → blind to its own freshness; now cross-section-z fallback, PREREG_FRESH_INFLECTION_FUNNEL
# §5.1). A rank change → it can move which names reach the council top-K → record-segmenting, so bump.
DISCOVERY_FUNNEL_VERSION = "fresh_v2"


# ── marker computation ───────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MarkerParams:
    """Prescreen tunables (config.discovery.markers). Funnel knobs, NOT a frozen gate."""

    mom_lookback: int = 252
    mom_skip: int = 21
    mom_recent_lookback: int = 63    # the recent-move window (~3mo), skip 0 — the freshness leg (§3)
    rv_recent: int = 21
    rv_base: int = 252
    rv_mid_window: int = 63          # rv_rising = rv_21 vs rv_63 (vol accelerating, not post-spike fade)
    adv_window: int = 20
    # absolute floors — the disjunctive surface gate
    mom_floor: float = 0.15          # |12-1 return| ≥ 15% = a real move
    rv_slope_floor: float = 0.25     # realized vol rose ≥ 25% recent-vs-baseline
    fresh_mom_floor: float = 0.20        # |recent move| for the freshness surface leg (§4)
    fresh_rv_rising_floor: float = 0.10  # rv_21/rv_63 − 1 ≥ 10% = vol rising (§4)
    dir_recent_epsilon: float = 0.02     # |mom_recent| ≥ this sets direction from the recent move (§6)
    event_bonus: float = 1.0         # fixed rank boost for a structural event (NOT a surface blend)
    min_price: float = 3.0
    min_adv_usd: float = 3_000_000.0


@dataclass(frozen=True)
class MarkerSet:
    """The deterministic markers for one name — also the framer/council grounding corpus (PR2)."""

    symbol: str
    basket: str
    momentum: float | None
    rel_strength: float | None
    rv: float | None
    rv_slope: float | None
    has_event: bool
    event_kind: str | None
    news_count: int
    price: float | None
    adv_usd: float | None
    notes: tuple[str, ...] = ()
    mom_recent: float | None = None      # recent-window return, skip 0 (§3 freshness re-target)
    rv_rising: float | None = None       # (rv_21 − rv_63)/rv_63 — vol accelerating (§3)

    @property
    def eligible(self) -> bool:
        """Price+ADV floor — the population the control cohort is drawn from."""
        return (
            self.price is not None and self.price > 0
            and self.adv_usd is not None
        )


class EventProvider(Protocol):
    """Structural-event source (EDGAR 424B5/13D/S-1, Form-4 clusters, revenue YoY jump).

    PR1 injects a synthetic/None provider; PR2 wires the real EDGAR-backed one behind the
    per-scan fetch budget (bars first). Returns (present, kind)."""

    def has_structural_event(self, symbol: str, as_of: datetime) -> tuple[bool, str | None]: ...


def compute_markers(
    symbol: str,
    as_of: datetime,
    *,
    market,
    benchmark: str | None,
    params: MarkerParams,
    basket: str = "",
    event_provider: EventProvider | None = None,
) -> MarkerSet:
    """Compute one name's markers as-of ``as_of`` from bars (+ an optional event provider).

    All reads are as-of (the point-in-time cache). Fail-soft: a missing series → None markers
    (the gate simply won't fire on them), never an exception into the scan."""
    try:
        closes = [c for _, c in market.closes_asof(symbol, as_of)]
    except Exception as e:  # noqa: BLE001 — a cold/missing name must not break the scan
        return MarkerSet(symbol, basket, None, None, None, None, False, None, 0, None, None,
                         (f"bars error: {e}",))
    price = closes[-1] if closes else None
    mom = market.momentum(symbol, as_of, lookback=params.mom_lookback, skip=params.mom_skip)
    rel = None
    if benchmark:
        try:
            bmom = market.momentum(benchmark, as_of, lookback=params.mom_lookback, skip=params.mom_skip)
        except Exception:  # noqa: BLE001 — a missing benchmark series just drops rel_strength
            bmom = None
        if mom is not None and bmom is not None:
            rel = mom - bmom
    rv_recent = realized_vol(closes[-(params.rv_recent + 1):], window=params.rv_recent) if closes else None
    rv_base = realized_vol(closes, window=params.rv_base) if closes else None
    rv_slope = ((rv_recent - rv_base) / rv_base) if (rv_recent and rv_base and rv_base > 0) else None
    # freshness markers (§3): recent move (skip 0) + vol accelerating (rv_21 vs rv_63)
    mom_recent = market.momentum(symbol, as_of, lookback=params.mom_recent_lookback, skip=0)
    rv_mid = realized_vol(closes[-(params.rv_mid_window + 1):], window=params.rv_mid_window) if closes else None
    rv_rising = ((rv_recent - rv_mid) / rv_mid) if (rv_recent and rv_mid and rv_mid > 0) else None
    adv = market.adv_usd(symbol, as_of, window=params.adv_window)
    has_event, ev_kind = (False, None)
    if event_provider is not None:
        try:
            has_event, ev_kind = event_provider.has_structural_event(symbol, as_of)
        except Exception as e:  # noqa: BLE001 — enrichment is best-effort
            has_event, ev_kind = False, None
            log.debug("event provider failed for %s: %s", symbol, e)
    return MarkerSet(symbol, basket, mom, rel, rv_base, rv_slope, bool(has_event), ev_kind,
                     0, price, adv, mom_recent=mom_recent, rv_rising=rv_rising)


# ── the disjunctive surface gate + direction ───────────────────────────────────────────────────


def clears_gate(m: MarkerSet, params: MarkerParams) -> tuple[bool, str | None]:
    """Surface iff a structural event is present OR raw motion clears an ABSOLUTE floor.

    Disjunction, never a blend — this is what makes a dead basket surface nothing."""
    if not m.eligible:
        return False, None
    if m.has_event:
        return True, f"event:{m.event_kind or 'structural'}"
    # the FRESHNESS leg — a recent move AND vol rising together (§4). Checked BEFORE the trailing
    # legs so the `fresh` reason labels the whole fresh cohort (a name clearing both fresh and
    # momentum reads `fresh`, not `momentum`) — needed for the §8.1 "fresh cohort enters" telemetry.
    if (m.mom_recent is not None and abs(m.mom_recent) >= params.fresh_mom_floor
            and m.rv_rising is not None and m.rv_rising >= params.fresh_rv_rising_floor):
        return True, "fresh"
    if m.momentum is not None and abs(m.momentum) >= params.mom_floor:
        return True, "momentum"
    if m.rv_slope is not None and m.rv_slope >= params.rv_slope_floor:
        return True, "rv_slope"
    return False, None


def direction_of(m: MarkerSet, params: MarkerParams | None = None) -> str:
    """Motion sign → direction. Tailwind (up) → bullish/calls; rollover (down) → bearish/puts.

    The fresh-inflection re-target (§6) keys direction on the RECENT move when ``params`` is supplied
    (the surfaced-sentinel path) — so a fresh rollover surfaces bearish/puts. Without ``params`` (the
    null books' motion-direction callers, e.g. 3B/shares) the trailing-momentum behavior is unchanged.
    Relative strength breaks a flat tie; defaults bullish only if truly undetermined."""
    eps = params.dir_recent_epsilon if params is not None else None
    if eps is not None and m.mom_recent is not None and abs(m.mom_recent) >= eps:
        return "bullish" if m.mom_recent > 0 else "bearish"
    if m.momentum is not None and abs(m.momentum) > 1e-9:
        return "bullish" if m.momentum > 0 else "bearish"
    if m.rel_strength is not None and abs(m.rel_strength) > 1e-9:
        return "bullish" if m.rel_strength > 0 else "bearish"
    return "bullish"


# ── within-basket ranking (orders the gate-clearers only) ──────────────────────────────────────


def _zmap(values: dict[str, float]) -> dict[str, float]:
    """Population z of a {symbol: value} map; flat dispersion → all zeros."""
    if not values:
        return {}
    xs = list(values.values())
    mean = sum(xs) / len(xs)
    var = sum((x - mean) ** 2 for x in xs) / len(xs)
    std = var ** 0.5
    if std < 1e-9:
        return {k: 0.0 for k in values}
    return {k: (v - mean) / std for k, v in values.items()}


def rank_basket(cleared: list[MarkerSet], params: MarkerParams) -> dict[str, float]:
    """inflection_score per cleared name = WITHIN-BASKET z of the FRESHNESS markers
    (rv_rising, |mom_recent|) + a fixed event bonus. Ordering only — not a signal
    (PREREG_FRESH_INFLECTION_FUNNEL §5): the trailing |momentum|/|rel_strength| magnitude terms are
    removed so the top-K is the *relatively* freshest names, not the biggest movers; rv_slope is
    dropped from the rank too (it shares the rv_21 numerator with rv_rising → double-weights vol, and
    stays high for a still-elevated post-spike monster → re-imports magnitude). NOTE (§8.1): z is
    within-basket/relative, so on an all-monster basket the *least-stale* name still ranks — the rank
    prefers freshness, it cannot manufacture it; the §10 yield band is the guard."""
    z_rvr = _zmap({m.symbol: m.rv_rising for m in cleared if m.rv_rising is not None})
    z_mr = _zmap({m.symbol: abs(m.mom_recent) for m in cleared if m.mom_recent is not None})
    out: dict[str, float] = {}
    for m in cleared:
        score = z_rvr.get(m.symbol, 0.0) + z_mr.get(m.symbol, 0.0)
        if m.has_event:
            score += params.event_bonus
        out[m.symbol] = score
    return out


def rank_scores(cleared_by_basket: dict[str, list[MarkerSet]], params: MarkerParams) -> dict[str, float]:
    """inflection_score for every cleared name across all baskets (the union order).

    A basket with **≥2 clearers** is ranked WITHIN-BASKET (``rank_basket`` — §5: freshness-z relative to
    same-theme peers; byte-identical to the prior per-basket path). A basket with **<2 clearers** has no
    within-basket peers, so ``_zmap`` collapses to 0.0 → the lone name would score 0.0 **however hard it
    breaks** (the ``seaborne_freight``/FRO defect: a curation artifact that makes the rank blind to a real
    fresh leg). For those names we fall back to a **CROSS-SECTION z** over all clearers.

    This fallback is a **DOCUMENTED §5 DEPARTURE** (PREREG_FRESH_INFLECTION_FUNNEL §5.1), *not* §5
    compliance: §5 chose within-basket relativity precisely to avoid cross-theme vol-regime comparison; a
    lone-basket name has no within-basket answer, so we accept the cross-theme / mixed-scale impurity over
    a permanent 0.0. The principled dissolution is curation (a second name in the basket removes the n<2
    case). The cross-section z is computed lazily — only when a <2-clearer basket exists."""
    out: dict[str, float] = {}
    cross: dict[str, float] | None = None
    for cleared in cleared_by_basket.values():
        if len(cleared) >= 2:
            out.update(rank_basket(cleared, params))
        elif cleared:  # lone-basket name → cross-section fallback (§5.1)
            if cross is None:
                cross = rank_basket([m for ms in cleared_by_basket.values() for m in ms], params)
            for m in cleared:
                out[m.symbol] = cross.get(m.symbol, 0.0)
    return out


# ── scan orchestration ─────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Surfaced:
    markers: MarkerSet
    direction: str
    inflection_score: float
    gate_reason: str


@dataclass
class DiscoveryResult:
    surfaced: list[Surfaced] = field(default_factory=list)     # top-K novel, ranked across baskets
    controls: list[MarkerSet] = field(default_factory=list)    # random eligible-but-not-surfaced
    n_scanned: int = 0
    n_cleared: int = 0
    by_basket: dict[str, int] = field(default_factory=dict)    # basket → # cleared


def scan_baskets(
    baskets: dict[str, list[str]],
    as_of: datetime,
    *,
    market,
    benchmark: str | None,
    params: MarkerParams,
    exclude_symbols: set[str] | None = None,
    event_provider: EventProvider | None = None,
    max_scan_names: int = 200,
    top_k: int = 8,
    n_controls: int = 5,
    rng: random.Random | None = None,
) -> DiscoveryResult:
    """Scan curated baskets → ranked top-K novel candidates + a random control cohort.

    ``exclude_symbols`` (themes.json names + open positions + active sentinels) are skipped for
    novelty **and excluded from the control cohort** (an already-tracked name is not a
    "didn't-surface" counterfactual). ``max_scan_names`` bounds the deterministic pass at the
    basket level (the cold-cache cost guard, C1) — whole baskets are processed until the budget is
    reached. Within-basket z ranks only the names that already cleared the absolute gate.
    """
    rng = rng or random.Random()
    exclude = {s.upper() for s in (exclude_symbols or set())}
    result = DiscoveryResult()

    scored: list[Surfaced] = []
    eligible_unsurfaced: list[MarkerSet] = []
    surfaced_syms: set[str] = set()

    cleared_by_basket: dict[str, list[MarkerSet]] = {}
    for basket, members in baskets.items():
        if result.n_scanned >= max_scan_names:
            break
        cleared_in_basket: list[MarkerSet] = []
        markers_in_basket: list[MarkerSet] = []
        for sym in members:
            sym = sym.upper()
            if benchmark and sym == benchmark.upper():
                continue
            result.n_scanned += 1
            m = compute_markers(sym, as_of, market=market, benchmark=benchmark, params=params,
                                basket=basket, event_provider=event_provider)
            markers_in_basket.append(m)
            passed, _reason = clears_gate(m, params)
            if passed and sym not in exclude:
                cleared_in_basket.append(m)
        cleared_by_basket[basket] = cleared_in_basket
        result.by_basket[basket] = len(cleared_in_basket)
        result.n_cleared += len(cleared_in_basket)
        # eligible-but-not-cleared names feed the control pool
        cleared_syms = {m.symbol for m in cleared_in_basket}
        eligible_unsurfaced.extend(m for m in markers_in_basket
                                   if m.eligible and m.symbol not in cleared_syms)

    # rank the gate-clearers: within-basket freshness-z for ≥2-clearer baskets (§5); a CROSS-SECTION z
    # fallback for a <2-clearer basket (no within-basket peers → degenerate 0.0, blind to its own
    # freshness — the §5.1 lone-basket departure). Deferred past the scan loop so the fallback sees the
    # full cleared cross-section.
    scores = rank_scores(cleared_by_basket, params)
    for cleared_in_basket in cleared_by_basket.values():
        for m in cleared_in_basket:
            scored.append(Surfaced(m, direction_of(m, params), scores.get(m.symbol, 0.0),
                                   _gate_reason(m, params)))

    scored.sort(key=lambda s: s.inflection_score, reverse=True)
    result.surfaced = scored[:top_k]
    surfaced_syms = {s.markers.symbol for s in result.surfaced}

    # controls: random eligible names that were NOT surfaced AND are not already tracked — the
    # clean forward-null cohort. Mirror the surfacing exclusion (``not in exclude``, above): an
    # open position or an active sentinel that re-clears the gate is dropped from surfacing, but
    # without this filter it falls into ``eligible_unsurfaced`` and can be drawn as a control —
    # i.e. the null arm gets contaminated by the very lineage it is the counterfactual for (#71).
    pool = [m for m in eligible_unsurfaced
            if m.symbol not in surfaced_syms and m.symbol not in exclude]
    rng.shuffle(pool)
    result.controls = pool[:n_controls]
    return result


def _gate_reason(m: MarkerSet, params: MarkerParams) -> str:
    ok, reason = clears_gate(m, params)
    return reason or "none"


def synthetic_market(symbols, as_of: datetime, *, movers=()):
    """Deterministic offline ``MarketData`` for ``--demo --discover`` (mirrors SyntheticChainProvider).

    ``movers`` ramp up over the window (→ momentum clears the absolute gate, surfacing them); the
    rest stay flat (→ they don't clear, feeding the control pool). Real ``MarketData`` over a temp
    point-in-time cache, so the demo exercises the same code path as a live scan."""
    import tempfile

    from data.cache import PointInTimeCache
    from data.market import MarketData

    mv = {m.upper() for m in movers}
    n = 320
    start = as_of - timedelta(days=n)
    cache = PointInTimeCache(tempfile.mkdtemp(prefix="disc_demo_"))
    for sym in symbols:
        s = sym.upper()
        closes = [10.0 + 10.0 * i / (n - 1) for i in range(n)] if s in mv else [10.0] * n
        bars = [{"ts": (start + timedelta(days=i)).isoformat(), "open": c, "high": c, "low": c,
                 "close": c, "volume": 2_000_000} for i, c in enumerate(closes)]
        cache.write("bars", s, bars, coverage_from=start - timedelta(days=2),
                    coverage_through=as_of + timedelta(days=2))
    return MarketData(cache, client=None, fetch_start=start, fetch_end=as_of + timedelta(days=2))
