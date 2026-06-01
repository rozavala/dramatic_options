"""Backtest metrics (plan §A3) — the pre-registered, multiple-testing-aware gate math.

The primary metric is the **rank Information Coefficient (IC)** of the trade signal
``s = −divergence`` against forward returns. The non-negotiable statistical choices:

- **Resampling unit = the time period, not the name-date.** One cross-sectional ``IC_t`` per
  rebalance date (Spearman across that date's names); the pooled IC is the mean of the
  ``IC_t`` series and its CI comes from a **block bootstrap over that series** — so ~40
  co-moving, autocorrelated names in a month count as ~one draw, not 40 (plan §A1 crit. 1).
- **Multiple testing as math:** the CI is taken at a **Bonferroni level α = 0.05/k** for
  ``k`` signal-iteration rounds — the bar rises with every peek (plan §A1 crit. 6).
- **Neutralize the real factor:** residualize ``s`` cross-sectionally on
  {momentum, growth-beta, broad-beta} and require the residual IC to retain ≥ 50%.
- **Bands, not a line:** FAIL / YELLOW / GREEN by IC magnitude, because a ~0.03 spot-IC is a
  statistical floor but economically marginal once options costs are paid (plan §A1, §A5).

Pure functions over the engine's per-date observation panels — no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


# ── rank / correlation primitives ───────────────────────────────────────────
def _avg_rank(a: np.ndarray) -> np.ndarray:
    """Average ranks (ties shared) — the basis of Spearman correlation."""
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(len(a), dtype=float)
    ranks[order] = np.arange(1, len(a) + 1)
    # average tied ranks
    _, inv, counts = np.unique(a, return_inverse=True, return_counts=True)
    sums = np.zeros(len(counts))
    np.add.at(sums, inv, ranks)
    avg = sums / counts
    return avg[inv]


def _pearson(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 2:
        return float("nan")
    sx, sy = x.std(), y.std()
    if sx < 1e-12 or sy < 1e-12:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 3:
        return float("nan")
    return _pearson(_avg_rank(x), _avg_rank(y))


# ── block bootstrap over the IC_t series ─────────────────────────────────────
def block_bootstrap_ci(
    ic_series: list[float], *, alpha: float, n_iter: int, block: int, seed: int = 7
) -> tuple[float, float]:
    """Circular block-bootstrap CI for the mean of the IC_t series at level ``alpha``."""
    xs = np.array([v for v in ic_series if not np.isnan(v)], dtype=float)
    n = len(xs)
    if n < 2:
        return (float("nan"), float("nan"))
    block = max(1, min(block, n))
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block))
    means = np.empty(n_iter)
    for i in range(n_iter):
        starts = rng.integers(0, n, size=n_blocks)
        idx = np.concatenate([(np.arange(s, s + block) % n) for s in starts])[:n]
        means[i] = xs[idx].mean()
    lo = float(np.percentile(means, 100 * alpha / 2))
    hi = float(np.percentile(means, 100 * (1 - alpha / 2)))
    return (lo, hi)


# ── residualization (neutralize momentum + growth/broad beta) ────────────────
def _residualize(s: np.ndarray, factors: np.ndarray) -> np.ndarray:
    """Residual of ``s`` after OLS on ``factors`` (with intercept). NaN rows dropped upstream."""
    X = np.column_stack([np.ones(len(s)), factors])
    beta, *_ = np.linalg.lstsq(X, s, rcond=None)
    return s - X @ beta


@dataclass
class GateResult:
    horizon_days: int
    k_iterations: int
    alpha: float
    n_periods: int
    pooled_ic: float
    ci_low: float
    ci_high: float
    ci_excludes_zero: bool
    sign_consistency: float
    quintile_spread: float
    quintile_monotonic: bool
    residual_ic: float
    residual_retention: float
    corr_div_momentum: float
    theme_ic: float
    substance_density: float
    median_abs_fwd_move: float
    ls_sharpe: float
    ls_max_drawdown: float
    band: str
    verdict: str
    notes: list[str] = field(default_factory=list)

    def to_text(self) -> str:
        lines = [
            f"  horizon={self.horizon_days}td   periods(N)={self.n_periods}   "
            f"k_iter={self.k_iterations}  α(Bonferroni)={self.alpha:.4f}",
            f"  pooled rank-IC = {self.pooled_ic:+.4f}   "
            f"CI[{self.ci_low:+.4f}, {self.ci_high:+.4f}]  "
            f"{'excludes 0 ✓' if self.ci_excludes_zero else 'spans 0 ✗'}",
            f"  sign-consistency across folds = {self.sign_consistency:.0%}",
            f"  quintile top−bottom spread = {self.quintile_spread:+.4f}  "
            f"{'monotonic ✓' if self.quintile_monotonic else 'non-monotonic ✗'}",
            f"  residual IC (mom+growth+broad-neutral) = {self.residual_ic:+.4f}  "
            f"retention = {self.residual_retention:.0%}",
            f"  corr(divergence, momentum) = {self.corr_div_momentum:+.3f}",
            f"  theme-level IC (non-gating) = {self.theme_ic:+.4f}",
            f"  substance non-zero density = {self.substance_density:.0%}",
            f"  median |t→t+h| underlying move = {self.median_abs_fwd_move:.1%}  "
            "(spot-edge ≠ options-edge; must clear bid/ask+theta)",
            f"  L/S Sharpe = {self.ls_sharpe:+.2f}  maxDD = {self.ls_max_drawdown:.1%}  "
            "(low-power context only, NOT a gate)",
            f"  ── BAND: {self.band}   VERDICT: {self.verdict}",
        ]
        for n in self.notes:
            lines.append(f"     · {n}")
        return "\n".join(lines)


def evaluate(
    date_panels: list[dict[str, Any]],
    *,
    config: dict[str, Any],
    k_iterations: int,
    horizon_days: int,
) -> GateResult:
    """Score the signal against the pre-registered gate criteria for one horizon."""
    bt = config.get("backtest", {})
    alpha = float(bt.get("alpha_base", 0.05)) / max(1, int(k_iterations))
    n_iter = int(bt.get("bootstrap_iters", 2000))
    block_days = int(bt.get("block_days", 21))
    rebalance_days = int(bt.get("rebalance_days", 21))
    quantiles = int(bt.get("quantiles", 5))
    fold_count = int(bt.get("fold_count", 4))
    ic_fail = float(bt.get("ic_fail_below", 0.03))
    ic_green = float(bt.get("ic_green_above", 0.06))
    sign_min = float(bt.get("sign_consistency_min", 0.60))
    retain_min = float(bt.get("residual_ic_retention_min", 0.50))
    density_floor = float(bt.get("substance_density_floor", 0.20))

    ic_series: list[float] = []
    resid_ic_series: list[float] = []
    theme_ic_series: list[float] = []
    quantile_rets: list[np.ndarray] = []
    div_mom_pairs: tuple[list[float], list[float]] = ([], [])
    ls_returns: list[float] = []
    all_fwd_moves: list[float] = []
    density_hits = density_total = 0

    for panel in date_panels:
        obs = panel["obs"]
        # Substance density is measured at NAME-DATE granularity (plan §A1 crit. 5).
        density_total += len(obs)
        density_hits += sum(1 for o in obs if o.get("has_substance_event"))
        if len(obs) < 3:
            continue
        s = np.array([o["s"] for o in obs], dtype=float)
        fwd = np.array([o["fwd_ret"] for o in obs], dtype=float)
        good = ~(np.isnan(s) | np.isnan(fwd))
        s, fwd = s[good], fwd[good]
        objs = [o for o, g in zip(obs, good, strict=True) if g]
        if len(s) < 3:
            continue
        all_fwd_moves.extend(np.abs(fwd).tolist())
        ic_series.append(spearman(s, fwd))

        # residualized IC (drop rows with any missing factor)
        fac = np.array([[o.get("momentum"), o.get("growth_beta"), o.get("broad_beta")]
                        for o in objs], dtype=float)
        fmask = ~np.isnan(fac).any(axis=1)
        if fmask.sum() >= 4:
            resid = _residualize(s[fmask], fac[fmask])
            resid_ic_series.append(spearman(resid, fwd[fmask]))
            mom = fac[fmask][:, 0]
            div_mom_pairs[0].extend((-s[fmask]).tolist())  # divergence = -s
            div_mom_pairs[1].extend(mom.tolist())

        # quintile forward returns by s
        q = _quantile_means(s, fwd, quantiles)
        if q is not None:
            quantile_rets.append(q)
            ls_returns.append(q[-1] - q[0])  # long top-s, short bottom-s

        # theme-level IC
        tobs = panel.get("theme_obs", [])
        if len(tobs) >= 3:
            ts = np.array([t["s"] for t in tobs], dtype=float)
            tf = np.array([t["fwd_ret"] for t in tobs], dtype=float)
            tg = ~(np.isnan(ts) | np.isnan(tf))
            if tg.sum() >= 3:
                theme_ic_series.append(spearman(ts[tg], tf[tg]))

    n_periods = len([v for v in ic_series if not np.isnan(v)])
    pooled_ic = float(np.nanmean(ic_series)) if ic_series else float("nan")
    ci_low, ci_high = block_bootstrap_ci(
        ic_series, alpha=alpha, n_iter=n_iter,
        block=max(1, round(block_days / max(1, rebalance_days))),
    )
    ci_excludes_zero = not (np.isnan(ci_low) or np.isnan(ci_high)) and (ci_low > 0 or ci_high < 0)

    sign_consistency = _fold_sign_consistency(ic_series, fold_count)
    spread, monotonic = _quintile_summary(quantile_rets)
    resid_ic = float(np.nanmean(resid_ic_series)) if resid_ic_series else float("nan")
    retention = (resid_ic / pooled_ic) if pooled_ic not in (0.0,) and not np.isnan(pooled_ic) else float("nan")
    corr_dm = _pearson(np.array(div_mom_pairs[0]), np.array(div_mom_pairs[1])) if div_mom_pairs[0] else float("nan")
    theme_ic = float(np.nanmean(theme_ic_series)) if theme_ic_series else float("nan")
    density = density_hits / density_total if density_total else 0.0
    median_move = float(np.median(all_fwd_moves)) if all_fwd_moves else float("nan")
    sharpe, maxdd = _ls_stats(ls_returns)

    band, verdict, notes = _verdict(
        pooled_ic=pooled_ic, ci_excludes_zero=ci_excludes_zero, sign_consistency=sign_consistency,
        sign_min=sign_min, spread=spread, monotonic=monotonic, retention=retention,
        retain_min=retain_min, density=density, density_floor=density_floor,
        ic_fail=ic_fail, ic_green=ic_green, n_periods=n_periods,
    )
    return GateResult(
        horizon_days=horizon_days, k_iterations=k_iterations, alpha=alpha, n_periods=n_periods,
        pooled_ic=pooled_ic, ci_low=ci_low, ci_high=ci_high, ci_excludes_zero=ci_excludes_zero,
        sign_consistency=sign_consistency, quintile_spread=spread, quintile_monotonic=monotonic,
        residual_ic=resid_ic, residual_retention=retention, corr_div_momentum=corr_dm,
        theme_ic=theme_ic, substance_density=density, median_abs_fwd_move=median_move,
        ls_sharpe=sharpe, ls_max_drawdown=maxdd, band=band, verdict=verdict, notes=notes,
    )


def _quantile_means(s: np.ndarray, fwd: np.ndarray, q: int) -> np.ndarray | None:
    if len(s) < q:
        return None
    ranks = _avg_rank(s)
    edges = np.quantile(ranks, np.linspace(0, 1, q + 1))
    out = np.full(q, np.nan)
    for i in range(q):
        lo, hi = edges[i], edges[i + 1]
        mask = (ranks >= lo) & (ranks <= hi) if i == q - 1 else (ranks >= lo) & (ranks < hi)
        if mask.any():
            out[i] = fwd[mask].mean()
    return out if not np.isnan(out).any() else None


def _quintile_summary(quantile_rets: list[np.ndarray]) -> tuple[float, bool]:
    if not quantile_rets:
        return (float("nan"), False)
    mean_by_q = np.nanmean(np.vstack(quantile_rets), axis=0)
    spread = float(mean_by_q[-1] - mean_by_q[0])
    diffs = np.diff(mean_by_q)
    monotonic = bool((diffs >= 0).mean() >= 0.75)  # broadly monotonic
    return spread, monotonic


def _fold_sign_consistency(ic_series: list[float], folds: int) -> float:
    xs = [v for v in ic_series if not np.isnan(v)]
    if len(xs) < folds or folds < 1:
        return float("nan")
    chunks = np.array_split(np.array(xs), folds)
    fold_means = [c.mean() for c in chunks if len(c)]
    return float(np.mean([1.0 if m > 0 else 0.0 for m in fold_means]))


def _ls_stats(ls_returns: list[float]) -> tuple[float, float]:
    if len(ls_returns) < 2:
        return (float("nan"), float("nan"))
    r = np.array(ls_returns)
    sharpe = float(r.mean() / r.std() * np.sqrt(252 / 21)) if r.std() > 1e-12 else float("nan")
    equity = np.cumprod(1 + r)
    peak = np.maximum.accumulate(equity)
    maxdd = float((equity / peak - 1).min())
    return sharpe, maxdd


def _verdict(**kw: Any) -> tuple[str, str, list[str]]:
    notes: list[str] = []
    pooled_ic = kw["pooled_ic"]

    # Band by IC magnitude (signed; thesis expects positive).
    if np.isnan(pooled_ic) or pooled_ic < kw["ic_fail"]:
        band = "FAIL"
    elif pooled_ic < kw["ic_green"]:
        band = "YELLOW"
    else:
        band = "GREEN"

    # Substance-density floor (overrides — plan §A1 crit. 5).
    if kw["density"] < kw["density_floor"]:
        notes.append(
            f"substance density {kw['density']:.0%} < floor {kw['density_floor']:.0%}: "
            "divergence ≈ narrative → INCONCLUSIVE for the divergence THESIS "
            "(this is narrative-momentum, not narrative-vs-delivery)."
        )
        return band, "INCONCLUSIVE-FOR-THESIS", notes

    if not kw["ci_excludes_zero"]:
        notes.append(
            "Bonferroni CI spans 0 → inconclusive, ITERATE (within budget); not 'thesis dead'. "
            "Bonferroni is conservative for correlated sequential refinements."
        )
        return band, "INCONCLUSIVE-ITERATE", notes

    failed = []
    if not (kw["sign_consistency"] >= kw["sign_min"]):
        failed.append(f"sign-consistency {kw['sign_consistency']:.0%} < {kw['sign_min']:.0%}")
    if not (kw["spread"] > 0 and kw["monotonic"]):
        failed.append("quintile spread not positive-and-monotonic")
    if not (kw["retention"] >= kw["retain_min"]):
        failed.append(f"residual IC retention {kw['retention']:.0%} < {kw['retain_min']:.0%} "
                      "(edge may be momentum/growth in disguise)")
    if kw["n_periods"] < 8:
        notes.append(f"only {kw['n_periods']} independent periods — low power; treat as weak.")

    if failed:
        notes.extend(failed)
        return band, "INCONCLUSIVE-ITERATE", notes

    verdict = {"FAIL": "FAIL", "YELLOW": "YELLOW (real-but-marginal — minimal risk only)",
               "GREEN": "GREEN"}[band]
    return band, verdict, notes
