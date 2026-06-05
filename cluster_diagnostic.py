"""Trailing-return correlation diagnostic — the cluster-cap curation backstop (report-not-gate).

The per-cluster exposure cap (PREREG §5) budgets correlation over an **operator-curated** `symbol→cluster`
map. Its one weakness: a co-moving name the curator missed reads as diversified (the first L0 scan was a
live near-miss — 7/8 sentinels were one AI-capex bet). This surfaces trailing-return correlations over the
names the system trades/considers and flags **co-moving pairs that aren't co-clustered**, so the operator
can curate the map. It **never edits the map** (operator-curated, hard seam) and **never gates a trade**.

**Tuned for SENSITIVITY, not specificity** — a backstop's defeating failure is a FALSE NEGATIVE (an
un-flagged correlated pair → the cap under-protects). So: flag on the UNION
`max(raw_pearson, resid_pearson, spearman) ≥ threshold`; report **top-N sorted**, the threshold a
highlight, never a hard filter; treat Pearson as a **lower bound** on the tail co-dependence a convex book
concentrates (below-threshold ≠ safe). Residual (SPY-stripped) is the **attribution column** ("shared
driver" vs "mostly market beta"), not the gatekeeper (residual β is noisy on the free feed). Short-history
pairs go in a separate lower-confidence tier (a ~130d corr on a fresh sentinel is unreliable).

**NO-FETCH:** read **cache-only** — build the ``market`` with ``client=None`` so ``MarketData._ensure``
cannot fetch; a cache-miss surfaces as insufficient data, never a network call.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

import clusters
import fixed_basket
import sentinels
import state
from themes import active_themes, load_themes

log = logging.getLogger("cluster_diagnostic")


# ── correlation core (cache-only; numpy) ──────────────────────────────────────────────────────


def _returns_by_date(market, symbol: str, as_of, window: int) -> dict[str, float]:
    """``{date_iso: daily_return}`` over the trailing ``window`` sessions ≤ as_of. Cache-only (a
    cache-miss → ``{}`` = insufficient, never a fetch). Empty if <2 closes."""
    try:
        closes = market.closes_asof(symbol, as_of)
    except Exception:  # noqa: BLE001 — CacheMiss / missing symbol → insufficient
        return {}
    closes = closes[-(window + 1):]
    out: dict[str, float] = {}
    for i in range(1, len(closes)):
        (_, c0), (d1, c1) = closes[i - 1], closes[i]
        if c0 > 0:
            out[d1.isoformat()] = c1 / c0 - 1.0
    return out


def _pearson(x, y) -> float | None:
    if len(x) < 2:
        return None
    x, y = np.asarray(x, float), np.asarray(y, float)
    if x.std() == 0 or y.std() == 0:   # degenerate (constant) series → undefined
        return None
    c = float(np.corrcoef(x, y)[0, 1])
    return None if np.isnan(c) else c


def _rank(a) -> np.ndarray:
    a = np.asarray(a, float)
    order = a.argsort()
    ranks = np.empty(len(a), float)
    ranks[order] = np.arange(len(a), dtype=float)
    return ranks


def _spearman(x, y) -> float | None:
    if len(x) < 2:
        return None
    return _pearson(_rank(x), _rank(y))


def _beta_residuals(ret: dict, spy: dict) -> dict[str, float]:
    """``{date: market-residual return}`` over ret∩spy (OLS-strip SPY beta). ``{}`` if degenerate —
    the residual N is the TRIPLE intersection (name ∩ SPY), smaller since SPY is sparse on IEX."""
    common = sorted(set(ret) & set(spy))
    if len(common) < 2:
        return {}
    s = np.array([ret[d] for d in common])
    m = np.array([spy[d] for d in common])
    var = float(m.var())
    if var == 0:                       # zero-variance SPY slice → β undefined → no residual
        return {}
    beta = float(np.cov(s, m, bias=True)[0, 1] / var)
    return {d: ret[d] - beta * spy[d] for d in common}


@dataclass
class PairCorr:
    a: str
    b: str
    raw: float | None
    residual: float | None
    spearman: float | None
    n_raw: int
    n_resid: int

    @property
    def flag(self) -> float | None:
        vals = [v for v in (self.raw, self.residual, self.spearman) if v is not None]
        return max(vals) if vals else None

    @property
    def driver(self) -> str:
        """Attribution: a high RAW but low RESIDUAL ⇒ mostly market beta; both high ⇒ a shared driver."""
        if self.raw is None:
            return "n/a"
        if self.residual is not None and self.residual >= 0.5 * self.raw and self.residual >= 0.4:
            return "shared driver"
        return "mostly market beta"


def trailing_return_correlation(symbols, as_of, market, *, window: int, benchmark: str = "SPY") -> list[PairCorr]:
    """Pairwise-complete raw + SPY-residual + Spearman correlation of daily returns over the trailing
    window. Cache-only. Names with no cached returns are dropped from the pairing (reported insufficient)."""
    rets = {s: _returns_by_date(market, s, as_of, window) for s in symbols}
    spy = _returns_by_date(market, benchmark, as_of, window)
    resids = {s: _beta_residuals(rets[s], spy) for s in symbols if rets.get(s)}
    have = [s for s in symbols if rets.get(s)]
    out: list[PairCorr] = []
    for i in range(len(have)):
        for j in range(i + 1, len(have)):
            a, b = have[i], have[j]
            craw = sorted(set(rets[a]) & set(rets[b]))
            raw = _pearson([rets[a][d] for d in craw], [rets[b][d] for d in craw])
            spear = _spearman([rets[a][d] for d in craw], [rets[b][d] for d in craw])
            cres = sorted(set(resids.get(a, {})) & set(resids.get(b, {})))
            resid = _pearson([resids[a][d] for d in cres], [resids[b][d] for d in cres]) if cres else None
            out.append(PairCorr(a, b, raw, resid, spear, len(craw), len(cres)))
    return out


# ── the curation report (GAPS / cohesion / cross-cluster) ─────────────────────────────────────


def build_universe(conn, config: dict, *, benchmark: str = "SPY") -> list[str]:
    """The names the system trades/considers: cluster members ∪ active sentinels ∪ basket ∪ hand-seeds
    ∪ OPEN real-book symbols (a held name dropped from the candidate sets is still cap-constrained)."""
    syms: set[str] = set()
    for members in clusters.load_cluster_map(config).values():
        syms |= set(members)
    syms |= {t.symbol.upper() for t in sentinels.active_sentinel_candidates(conn)}
    syms |= {s.upper() for s in fixed_basket.basket_symbols(config)}
    syms |= {t.symbol.upper() for t in active_themes(load_themes(config.get("themes_path", "themes.json")))}
    syms |= {s.upper() for s in state.open_position_symbols(conn)}
    syms.discard(benchmark.upper())
    return sorted(syms)


_ACTION = {"none": "create_or_extend", "one": "add_to_existing", "different": "consider_merge"}


def _cluster_series(members, as_of, market, window: int) -> dict[str, float]:
    """Equal-weight mean daily return of a cluster's members, by date (the portfolio read for the
    cross-cluster comparison: 'do the two baskets move together')."""
    rets = [r for r in (_returns_by_date(market, m, as_of, window) for m in members) if r]
    if not rets:
        return {}
    out: dict[str, float] = {}
    for d in set().union(*(set(r) for r in rets)):
        vals = [r[d] for r in rets if d in r]
        out[d] = sum(vals) / len(vals)
    return out


def cluster_curation_report(conn, config: dict, as_of, market, *, window=None, threshold=None,
                            min_overlap=None, top_n=None, benchmark=None) -> dict:
    cd = config.get("cluster_diagnostic", {})
    window = int(window or cd.get("window_days", 252))
    threshold = float(threshold if threshold is not None else cd.get("high_corr_threshold", 0.7))
    min_overlap = int(min_overlap or cd.get("min_overlap", 63))
    top_n = int(top_n or cd.get("top_n", 25))
    benchmark = str(benchmark or cd.get("residual_benchmark", "SPY"))
    full_n = int(0.85 * window)

    cmap = clusters.load_cluster_map(config)
    universe = build_universe(conn, config, benchmark=benchmark)
    pairs = trailing_return_correlation(universe, as_of, market, window=window, benchmark=benchmark)

    def status(a: str, b: str):
        ca, cb = clusters.cluster_of(a, cmap), clusters.cluster_of(b, cmap)
        if ca and ca == cb:
            return "same"
        if ca and cb:
            return "different"
        return "one" if (ca or cb) else "none"

    gaps = sorted((p for p in pairs if p.flag is not None and p.n_raw >= min_overlap
                   and status(p.a, p.b) != "same"), key=lambda p: p.flag, reverse=True)[:top_n]
    full = [_pair_row(p, status, threshold) for p in gaps if p.n_raw >= full_n]
    lowconf = [_pair_row(p, status, threshold) for p in gaps if p.n_raw < full_n]

    raw_vals = [p.raw for p in pairs if p.raw is not None]
    universe_median = round(float(np.median(raw_vals)), 3) if raw_vals else None
    cohesion = {}
    for cname, members in cmap.items():
        mem = [p for p in pairs if {p.a, p.b} <= set(members) and p.raw is not None]
        minp = min(mem, key=lambda p: p.raw) if mem else None
        cohesion[cname] = {
            "n_members": len(members),
            "mean": round(float(np.mean([p.raw for p in mem])), 3) if mem else None,
            "min": round(minp.raw, 3) if minp else None,
            "min_pair": f"{minp.a}-{minp.b}" if minp else None,
        }

    return {
        "as_of": as_of.isoformat(), "window_days": window, "secondary_window_days": cd.get("secondary_window_days"),
        "threshold": threshold, "min_overlap": min_overlap, "full_n_bar": full_n, "universe_n": len(universe),
        "gaps_full_n": full,
        "gaps_lower_confidence": lowconf,   # short-history → the SECOND mandatory tier (provisional-cluster-or-monitor)
        "cohesion": cohesion, "universe_median_corr": universe_median,
        "cross_cluster": _cross_cluster(cmap, as_of, market, window, benchmark),
        "caveats": [
            "REPORT-NOT-GATE: informs the operator-curated map (hard seam); it never edits the map or gates a trade.",
            "Tuned for SENSITIVITY: below-threshold != safe (Pearson is a LOWER BOUND on the tail co-dependence a "
            "convex book concentrates); the threshold highlights, it does not filter.",
            "GAPS = 'these co-move' (sector + theme bundle) -- NOT 'these share my theme'; the diagnostic can't "
            "attribute the WHY. Residual strips market beta; free-feed noise -> coarse directional flags.",
            "A MIXED-DIRECTION flagged pair carries the netting caveat: underlying co-movement != P&L co-movement.",
            "Lower-confidence (short-history) pairs are NOT silence -- conservative default for a new name is to "
            "OVER-cluster (tighter cap = the safe error), re-evaluate at full N.",
        ],
    }


def _pair_row(p: PairCorr, status, threshold: float) -> dict:
    st = status(p.a, p.b)
    return {"pair": f"{p.a}-{p.b}", "flag": round(p.flag, 3), "raw": round(p.raw, 3) if p.raw is not None else None,
            "residual": round(p.residual, 3) if p.residual is not None else None,
            "spearman": round(p.spearman, 3) if p.spearman is not None else None,
            "n_raw": p.n_raw, "n_resid": p.n_resid, "driver": p.driver, "cluster_status": st,
            "action": _ACTION.get(st, "?"), "over_threshold": p.flag >= threshold}


def _cross_cluster(cmap, as_of, market, window: int, benchmark: str) -> dict:
    names = list(cmap)
    series = {c: _cluster_series(m, as_of, market, window) for c, m in cmap.items()}
    out: dict[str, dict] = {}
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            common = sorted(set(series[a]) & set(series[b]))
            corr = _pearson([series[a][d] for d in common], [series[b][d] for d in common])
            out[f"{a}|{b}"] = {"corr": round(corr, 3) if corr is not None else None, "n": len(common)}
    return out


def main() -> int:
    import json
    from datetime import UTC, datetime

    from config_loader import load_config
    from data.cache import PointInTimeCache
    from data.market import MarketData, default_fetch_window

    config = load_config()
    conn = state.get_db(config)
    as_of = datetime.now(UTC)
    cache = PointInTimeCache(config.get("cache", {}).get("dir", "data/cache"))
    fetch_start, _ = default_fetch_window(as_of)
    # client=None → the NO-FETCH invariant (read-only over the warm cache).
    market = MarketData(cache, client=None, fetch_start=fetch_start, fetch_end=as_of)
    print(json.dumps(cluster_curation_report(conn, config, as_of, market), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
