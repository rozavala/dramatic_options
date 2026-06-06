"""Black-Scholes + GBM sanity — put-call parity, monotonicity, known values, seed."""

import math

import numpy as np

from dramatic_options.calibration.pricing import (
    bs_delta,
    bs_price,
    intrinsic_value,
    simulate_gbm_path,
)


def test_put_call_parity():
    spot, strike, t, r, sig = 100.0, 110.0, 0.75, 0.04, 0.5
    call = bs_price(spot=spot, strike=strike, t_years=t, r=r, sigma=sig, kind="C")
    put = bs_price(spot=spot, strike=strike, t_years=t, r=r, sigma=sig, kind="P")
    # C − P = S − K·e^{−rT}
    assert abs((call - put) - (spot - strike * math.exp(-r * t))) < 1e-6


def test_atm_call_known_value():
    # ATM call, classic check: ~ 0.4·S·σ·√T for small rates.
    spot, t, sig = 100.0, 1.0, 0.2
    call = bs_price(spot=spot, strike=spot, t_years=t, r=0.0, sigma=sig, kind="C")
    approx = 0.4 * spot * sig * math.sqrt(t)
    assert abs(call - approx) < 0.6  # within the approximation's tolerance


def test_degenerate_inputs_collapse_to_intrinsic():
    assert bs_price(spot=100, strike=80, t_years=0, r=0.04, sigma=0.5, kind="C") == 20.0
    assert bs_price(spot=100, strike=120, t_years=0, r=0.04, sigma=0.5, kind="C") == 0.0
    assert bs_price(spot=100, strike=120, t_years=1, r=0.04, sigma=0.0, kind="C") == 0.0
    assert bs_price(spot=100, strike=120, t_years=1, r=0.04, sigma=0.5, kind="P") > 0


def test_call_price_monotonic_in_spot_and_vol():
    base = dict(strike=110.0, t_years=0.75, r=0.04, kind="C")
    lo = bs_price(spot=90, sigma=0.5, **base)
    hi = bs_price(spot=110, sigma=0.5, **base)
    assert hi > lo
    cheap = bs_price(spot=100, sigma=0.3, **base)
    rich = bs_price(spot=100, sigma=0.8, **base)
    assert rich > cheap  # vega positive


def test_far_otm_is_cheap_and_convex():
    # 40% OTM long-dated call: small premium, big upside if the move is large (convexity).
    prem = bs_price(spot=100, strike=140, t_years=0.75, r=0.04, sigma=0.5, kind="C")
    assert 0 < prem < 8  # cheap relative to spot
    # a big move (+80% → spot 180) returns many multiples of the premium
    val = intrinsic_value(spot=180, strike=140, kind="C")
    assert val / prem > 4.0
    # while a small adverse move loses 100% of premium (bounded downside)
    assert intrinsic_value(spot=95, strike=140, kind="C") == 0.0


def test_bs_delta_bounds_and_landmarks():
    # call ∈ [0,1], put ∈ [-1,0]; ATM ≈ ±0.5-ish; deep ITM → ±1; deep OTM → 0
    atm = bs_delta(spot=100, strike=100, t_years=0.5, r=0.04, sigma=0.5, kind="C")
    assert 0.45 < atm < 0.65
    assert bs_delta(spot=300, strike=100, t_years=0.5, r=0.04, sigma=0.5, kind="C") > 0.97
    assert bs_delta(spot=40, strike=100, t_years=0.5, r=0.04, sigma=0.5, kind="C") < 0.1
    put = bs_delta(spot=100, strike=100, t_years=0.5, r=0.04, sigma=0.5, kind="P")
    assert -1.0 <= put <= 0.0
    # delta parity: Δcall − Δput = 1
    assert abs(atm - put - 1.0) < 1e-9
    # degenerate (t=0): step delta ±1 if ITM else 0
    assert bs_delta(spot=120, strike=100, t_years=0, r=0.04, sigma=0.5, kind="C") == 1.0
    assert bs_delta(spot=80, strike=100, t_years=0, r=0.04, sigma=0.5, kind="C") == 0.0
    assert bs_delta(spot=80, strike=100, t_years=0, r=0.04, sigma=0.5, kind="P") == -1.0


def test_intrinsic_value():
    assert intrinsic_value(spot=150, strike=140, kind="C") == 10.0
    assert intrinsic_value(spot=130, strike=140, kind="C") == 0.0
    assert intrinsic_value(spot=130, strike=140, kind="P") == 10.0


def test_gbm_reproducible_and_shaped():
    rng1 = np.random.default_rng(7)
    rng2 = np.random.default_rng(7)
    p1 = simulate_gbm_path(spot=100, mu=0.1, sigma=0.5, days=270, rng=rng1)
    p2 = simulate_gbm_path(spot=100, mu=0.1, sigma=0.5, days=270, rng=rng2)
    assert np.allclose(p1, p2)          # seed reproducible
    assert p1[0] == 100.0               # starts at spot
    assert len(p1) == int(round(270 * 252 / 365)) + 1


def test_gbm_realized_vol_in_ballpark():
    rng = np.random.default_rng(1)
    # average realized vol across many 1y paths ≈ sigma
    sig = 0.5
    rvs = []
    for _ in range(50):
        p = simulate_gbm_path(spot=100, mu=0.0, sigma=sig, days=365, rng=rng)
        rets = np.diff(np.log(p))
        rvs.append(rets.std(ddof=1) * math.sqrt(252))
    assert abs(np.mean(rvs) - sig) < 0.05
