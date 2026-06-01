"""FSSD friction composite (plan §8b / PREREG §5) — the short-sale-cost conditioner.

The thesis (PREREG §1): forced-supply drift survives where short-sale friction makes the
corrective arb-short uneconomic. The friction composite ranks events by how hard/costly the
offsetting short is, from five point-in-time inputs (higher = harder to short):

  - ``si_pct``         short interest ÷ shares-outstanding (direct borrow/limits-to-arb signal)
  - ``days_to_cover``  short interest ÷ ADV (borrow PRESSURE: days of volume to cover)
  - ``inv_float``      1 / shares-outstanding             (tighter float = harder borrow)
  - ``inv_adv``        1 / ADV₂₀ dollar volume            (thinner = costlier to short)
  - ``inv_price``      1 / price                          (low price ≈ harder/no borrow)

Each input is **z-scored across the cross-section** (the caller supplies a *trailing* window to
avoid lookahead — PREREG §5), then weighted. **FREEZE-B #4:** the §8b audit found
``corr(si_pct, inv_float) = +1.00`` (both ∝ 1/shares-out, nano-cap-tail-dominated), so equal
weighting made the composite mostly a *smallness* score. FREEZE-B leans the weight onto the
**borrow dimension** (``si_pct`` + ``days_to_cover``) and downweights the three collinear
illiquidity proxies. The corner is the top ``corner_quantile`` of the composite.

Pure functions — no I/O. Missing inputs are mean-imputed (z=0) so a name isn't excluded for one
gap, and the count of present inputs is returned for a coverage diagnostic.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

FRICTION_INPUTS = ("si_pct", "days_to_cover", "inv_float", "inv_adv", "inv_price")


def friction_inputs(
    *, si_pct: float | None, shares_out: float | None, adv_usd: float | None,
    price: float | None, days_to_cover: float | None = None,
) -> dict[str, float | None]:
    """Assemble the raw friction inputs from point-in-time observables (higher = harder to
    short). ``days_to_cover`` comes straight from the FINRA SI record (SI ÷ ADV shares). Any
    unavailable input is None (mean-imputed downstream)."""
    return {
        "si_pct": si_pct,
        "days_to_cover": days_to_cover,
        "inv_float": (1.0 / shares_out) if shares_out and shares_out > 0 else None,
        "inv_adv": (1.0 / adv_usd) if adv_usd and adv_usd > 0 else None,
        "inv_price": (1.0 / price) if price and price > 0 else None,
    }


def _zscore_column(vals: list[float | None]) -> tuple[np.ndarray, np.ndarray]:
    """Z-score a column across the cross-section; missing → 0 (the mean). Returns (z, present)."""
    arr = np.array([np.nan if v is None else float(v) for v in vals], dtype=float)
    present = ~np.isnan(arr)
    if present.sum() < 2:
        return np.zeros(len(arr)), present
    mu = np.nanmean(arr)
    sd = np.nanstd(arr)
    if sd < 1e-12:
        return np.zeros(len(arr)), present
    z = (arr - mu) / sd
    z[~present] = 0.0  # mean-impute missing
    return z, present


@dataclass
class FrictionResult:
    composite: list[float]
    in_corner: list[bool]
    inputs_present: list[int]  # how many of the 4 inputs each row had (coverage diagnostic)
    input_corr: dict[str, float]  # pairwise correlations among inputs (FREEZE-B #4 evidence)


def score_cross_section(
    rows: list[dict[str, float | None]],
    *,
    weights: dict[str, float] | None = None,
    corner_quantile: float = 0.8,
) -> FrictionResult:
    """Composite friction score + corner membership for a cross-section of friction-input dicts.

    ``rows`` are dicts with the :data:`FRICTION_INPUTS` keys (from :func:`friction_inputs`).
    Z-scores each input across ``rows`` (so the caller is responsible for passing a *trailing*
    cross-section), weights, sums, and flags the top ``corner_quantile`` as the friction corner.
    """
    n = len(rows)
    if n == 0:
        return FrictionResult([], [], [], {})
    w = {k: 1.0 for k in FRICTION_INPUTS}
    if weights:
        w.update({k: float(v) for k, v in weights.items() if k in w})

    cols = {k: _zscore_column([r.get(k) for r in rows]) for k in FRICTION_INPUTS}
    composite = np.zeros(n)
    for k in FRICTION_INPUTS:
        composite += w[k] * cols[k][0]
    present_counts = [int(sum(cols[k][1][i] for k in FRICTION_INPUTS)) for i in range(n)]

    # corner = top quantile of the composite (ties: strictly above the threshold rank)
    if n >= 2:
        thr = float(np.quantile(composite, corner_quantile))
        in_corner = [bool(c >= thr) for c in composite]
    else:
        in_corner = [True] * n

    # pairwise input correlations (collinearity evidence for FREEZE-B #4)
    corr: dict[str, float] = {}
    keys = list(FRICTION_INPUTS)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a = np.array([np.nan if r.get(keys[i]) is None else float(r[keys[i]]) for r in rows])
            b = np.array([np.nan if r.get(keys[j]) is None else float(r[keys[j]]) for r in rows])
            m = ~(np.isnan(a) | np.isnan(b))
            if m.sum() >= 3 and np.std(a[m]) > 1e-12 and np.std(b[m]) > 1e-12:
                corr[f"{keys[i]}~{keys[j]}"] = float(np.corrcoef(a[m], b[m])[0, 1])
    return FrictionResult(
        composite=composite.tolist(),
        in_corner=in_corner,
        inputs_present=present_counts,
        input_corr=corr,
    )
