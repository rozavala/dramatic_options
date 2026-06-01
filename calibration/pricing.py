"""Black-Scholes pricing + GBM path simulation (pure) — PREREG_CONVEXITY_CALIBRATION §3.

European, no dividends. Used only by the calibration harness (NOT the live trade path).
The normal CDF is from ``math.erf`` (stdlib) so the harness adds no new dependency beyond
numpy (already pinned); numpy drives the path simulator. All functions are pure +
deterministic (the simulator takes an explicit ``rng``).
"""

from __future__ import annotations

import math

import numpy as np


def _norm_cdf(x: float) -> float:
    """Standard-normal CDF via the error function (stdlib, no scipy)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_price(
    *, spot: float, strike: float, t_years: float, r: float, sigma: float, kind: str
) -> float:
    """Black-Scholes price of a European call ('C') or put ('P'). No dividends.

    Degenerate inputs collapse to intrinsic (t≤0 or sigma≤0) so the caller never divides by
    zero — far-OTM intrinsic is typically 0, the expected floor.
    """
    intrinsic = max(0.0, spot - strike) if kind == "C" else max(0.0, strike - spot)
    if t_years <= 0 or sigma <= 0 or spot <= 0 or strike <= 0:
        return intrinsic
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma * sigma) * t_years) / (sigma * math.sqrt(t_years))
    d2 = d1 - sigma * math.sqrt(t_years)
    if kind == "C":
        return spot * _norm_cdf(d1) - strike * math.exp(-r * t_years) * _norm_cdf(d2)
    return strike * math.exp(-r * t_years) * _norm_cdf(-d2) - spot * _norm_cdf(-d1)


def intrinsic_value(*, spot: float, strike: float, kind: str) -> float:
    """Per-share intrinsic value at expiry."""
    return max(0.0, spot - strike) if kind == "C" else max(0.0, strike - spot)


def simulate_gbm_path(
    *, spot: float, mu: float, sigma: float, days: int, rng: np.random.Generator,
    steps_per_year: int = 252,
) -> np.ndarray:
    """One daily GBM price path of length ``days+1`` (includes the entry spot at index 0).

    ``mu``/``sigma`` are annualized; daily log-returns ~ N((mu−σ²/2)/N, σ/√N). Deterministic
    given ``rng`` (seed reproducibility, PREREG §6).
    """
    n = max(1, int(round(days * steps_per_year / 365.0)))
    dt = 1.0 / steps_per_year
    drift = (mu - 0.5 * sigma * sigma) * dt
    shock = sigma * math.sqrt(dt)
    incr = drift + shock * rng.standard_normal(n)
    logpath = np.concatenate([[0.0], np.cumsum(incr)])
    return spot * np.exp(logpath)
