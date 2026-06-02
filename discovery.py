"""Sentinel inflection discovery — the deterministic prescreen (T3, PR1).

PREREG_THEMATIC_CONVEXITY §2 hard seam: discovery **proposes** candidate names; the council
**judges**; the deterministic Layer-1 gates **dispose**. This module is the funnel that surfaces
candidates — it makes **no alpha / cheapness claim** (cheapness is the IV gate's job, fresh and
authoritative; ranking the prescreen on it would pre-select for gate-pass and defeat the gate's
independence). The prescreen claims only "**something is happening here**".

Two design rules learned in plan-review and enforced here:

1. **Surface = a disjunctive GATE on ABSOLUTE floors, not a weighted blend.** A name surfaces iff
   ``|raw momentum| ≥ mom_floor`` OR ``rv_slope ≥ rv_slope_floor`` OR a structural event is present.
   Heterogeneous markers (a continuous z vs a 0/1 filing flag) are **never summed** into the
   surface decision — that has no principled exchange rate and collapses into whatever you weighted
   (the FSSD friction-composite-→-smallness failure). Absolute floors are also the only thing that
   delivers "a dead week surfaces nothing" — a relative z always has a top-of-distribution name.

2. **Within-basket z only RANKS the names that already cleared the gate** (ordering / top-K).
   Pooling heterogeneous baskets into one z would bury a low-vol basket's real inflection under a
   high-vol basket's raw magnitudes — so z is computed **per basket**.

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


# ── marker computation ───────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MarkerParams:
    """Prescreen tunables (config.discovery.markers). Funnel knobs, NOT a frozen gate."""

    mom_lookback: int = 252
    mom_skip: int = 21
    rv_recent: int = 21
    rv_base: int = 252
    adv_window: int = 20
    # absolute floors — the disjunctive surface gate
    mom_floor: float = 0.15          # |12-1 return| ≥ 15% = a real move
    rv_slope_floor: float = 0.25     # realized vol rose ≥ 25% recent-vs-baseline
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
    adv = market.adv_usd(symbol, as_of, window=params.adv_window)
    has_event, ev_kind = (False, None)
    if event_provider is not None:
        try:
            has_event, ev_kind = event_provider.has_structural_event(symbol, as_of)
        except Exception as e:  # noqa: BLE001 — enrichment is best-effort
            has_event, ev_kind = False, None
            log.debug("event provider failed for %s: %s", symbol, e)
    return MarkerSet(symbol, basket, mom, rel, rv_base, rv_slope, bool(has_event), ev_kind,
                     0, price, adv)


# ── the disjunctive surface gate + direction ───────────────────────────────────────────────────


def clears_gate(m: MarkerSet, params: MarkerParams) -> tuple[bool, str | None]:
    """Surface iff a structural event is present OR raw motion clears an ABSOLUTE floor.

    Disjunction, never a blend — this is what makes a dead basket surface nothing."""
    if not m.eligible:
        return False, None
    if m.has_event:
        return True, f"event:{m.event_kind or 'structural'}"
    if m.momentum is not None and abs(m.momentum) >= params.mom_floor:
        return True, "momentum"
    if m.rv_slope is not None and m.rv_slope >= params.rv_slope_floor:
        return True, "rv_slope"
    return False, None


def direction_of(m: MarkerSet) -> str:
    """Motion sign → direction. Tailwind (up) → bullish/calls; rollover (down) → bearish/puts.

    Relative strength breaks a flat-momentum tie; defaults bullish only if truly undetermined."""
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
    """inflection_score per cleared name = sum of WITHIN-BASKET z of the continuous markers
    (|momentum|, rv_slope, |rel_strength|) + a fixed event bonus. Ordering only — not a signal."""
    z_mom = _zmap({m.symbol: abs(m.momentum) for m in cleared if m.momentum is not None})
    z_rv = _zmap({m.symbol: m.rv_slope for m in cleared if m.rv_slope is not None})
    z_rs = _zmap({m.symbol: abs(m.rel_strength) for m in cleared if m.rel_strength is not None})
    out: dict[str, float] = {}
    for m in cleared:
        score = z_mom.get(m.symbol, 0.0) + z_rv.get(m.symbol, 0.0) + z_rs.get(m.symbol, 0.0)
        if m.has_event:
            score += params.event_bonus
        out[m.symbol] = score
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
    novelty. ``max_scan_names`` bounds the deterministic pass at the basket level (the cold-cache
    cost guard, C1) — whole baskets are processed until the budget is reached. Within-basket z
    ranks only the names that already cleared the absolute gate.
    """
    rng = rng or random.Random()
    exclude = {s.upper() for s in (exclude_symbols or set())}
    result = DiscoveryResult()

    scored: list[Surfaced] = []
    eligible_unsurfaced: list[MarkerSet] = []
    surfaced_syms: set[str] = set()

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
        # rank only the gate-clearers, WITHIN this basket
        scores = rank_basket(cleared_in_basket, params)
        for m in cleared_in_basket:
            scored.append(Surfaced(m, direction_of(m), scores.get(m.symbol, 0.0),
                                   _gate_reason(m, params)))
        result.by_basket[basket] = len(cleared_in_basket)
        result.n_cleared += len(cleared_in_basket)
        # eligible-but-not-cleared names feed the control pool
        cleared_syms = {m.symbol for m in cleared_in_basket}
        eligible_unsurfaced.extend(m for m in markers_in_basket
                                   if m.eligible and m.symbol not in cleared_syms)

    scored.sort(key=lambda s: s.inflection_score, reverse=True)
    result.surfaced = scored[:top_k]
    surfaced_syms = {s.markers.symbol for s in result.surfaced}

    # controls: random eligible names that were NOT surfaced (the forward null cohort)
    pool = [m for m in eligible_unsurfaced if m.symbol not in surfaced_syms]
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
