"""Calibration engine + metrics: deterministic-path payoffs, exits, transfer/EV math."""

import numpy as np

from dramatic_options.calibration.engine import (
    Structure,
    run_cell_historical,
    run_cell_mc,
    simulate_option_on_path,
)
from dramatic_options.calibration.metrics import breakeven_hit_rate, payoff_stats


def _struct(rule="hold", mny=0.25, tenor=270, smult=1.0, **kw):
    return Structure(moneyness=mny, tenor_days=tenor, kind="C", exit_rule=rule,
                     sigma_entry_mult=smult, **kw)


def test_expiry_worthless_is_total_loss():
    # Flat path → 25% OTM call expires worthless → multiple 0 (M = exit/entry).
    path = np.full(271, 100.0)
    m, ur, why = simulate_option_on_path(path, structure=_struct(), r=0.04, sigma_entry=0.5,
                                         roundtrip_cost_pct=0.05)
    assert why == "expiry"
    assert m == 0.0
    assert abs(ur) < 1e-9


def test_expiry_in_the_money_pays_multiple():
    # Path ramps to +50%: 25% OTM call (strike 125) → intrinsic 25 on a small premium.
    path = np.linspace(100.0, 150.0, 271)
    m, ur, why = simulate_option_on_path(path, structure=_struct(), r=0.04, sigma_entry=0.5,
                                         roundtrip_cost_pct=0.0)
    assert why == "expiry"
    assert m > 1.0  # returned more than the premium
    assert abs(ur - 0.5) < 1e-6


def test_profit_take_fires_before_expiry():
    # Big early jump then fade → profit-take should capture the spike.
    path = np.concatenate([[100.0], np.full(30, 180.0), np.full(240, 100.0)])
    s = _struct(rule="profit_take", profit_take_mult=2.0)
    m, ur, why = simulate_option_on_path(path, structure=s, r=0.04, sigma_entry=0.5,
                                         roundtrip_cost_pct=0.0)
    assert why == "profit_take"
    assert m >= 2.0


def test_time_stop_fires_near_expiry():
    # Flat-ish until near expiry → time-stop at ≤21 DTE closes it.
    path = np.full(271, 105.0)
    s = _struct(rule="time_stop", time_stop_dte=21)
    m, ur, why = simulate_option_on_path(path, structure=s, r=0.04, sigma_entry=0.5,
                                         roundtrip_cost_pct=0.0)
    assert why == "time_stop"


def test_live_rule_is_profit_take_or_time_stop():
    spike = np.concatenate([[100.0], np.full(30, 200.0), np.full(240, 100.0)])
    s = _struct(rule="live", profit_take_mult=3.0, time_stop_dte=21)
    _, _, why = simulate_option_on_path(spike, structure=s, r=0.04, sigma_entry=0.5,
                                        roundtrip_cost_pct=0.0)
    assert why == "profit_take"
    flat = np.full(271, 100.0)
    _, _, why2 = simulate_option_on_path(flat, structure=s, r=0.04, sigma_entry=0.5,
                                         roundtrip_cost_pct=0.0)
    assert why2 == "time_stop"  # never profitable → exits at the time stop


def test_delta_exit_fires_when_move_plays_out():
    # 25% OTM call (strike 125); a rise toward/through it pushes |delta| past 0.5 → "delta" exit.
    path = np.concatenate([[100.0], np.linspace(105, 135, 60), np.full(210, 135.0)])
    s = _struct(rule="delta", delta_exit_threshold=0.5)
    m, ur, why = simulate_option_on_path(path, structure=s, r=0.04, sigma_entry=0.5,
                                         roundtrip_cost_pct=0.0)
    assert why == "delta" and m > 1.0  # banked the convex move after it happened


def test_delta_exit_holds_to_expiry_when_flat():
    # No move → delta stays low → never triggers → holds the tail to (worthless) expiry.
    flat = np.full(271, 100.0)
    s = _struct(rule="delta", delta_exit_threshold=0.5)
    _, _, why = simulate_option_on_path(flat, structure=s, r=0.04, sigma_entry=0.5,
                                        roundtrip_cost_pct=0.0)
    assert why == "expiry"


def test_reprice_rule_delta_primary_with_backstops():
    s = _struct(rule="reprice", delta_exit_threshold=0.5, profit_take_mult=10.0, time_stop_dte=21)
    # the move plays out → delta is the primary "take it"
    rise = np.concatenate([[100.0], np.linspace(105, 135, 60), np.full(210, 135.0)])
    assert simulate_option_on_path(rise, structure=s, r=0.04, sigma_entry=0.5, roundtrip_cost_pct=0.0)[2] == "delta"
    # never moves → falls through to the 21-DTE time-stop backstop, not held to expiry
    flat = np.full(271, 100.0)
    assert simulate_option_on_path(flat, structure=s, r=0.04, sigma_entry=0.5, roundtrip_cost_pct=0.0)[2] == "time_stop"


def test_cost_reduces_multiple():
    path = np.linspace(100.0, 150.0, 271)
    m0 = simulate_option_on_path(path, structure=_struct(), r=0.04, sigma_entry=0.5,
                                 roundtrip_cost_pct=0.0)[0]
    mc = simulate_option_on_path(path, structure=_struct(), r=0.04, sigma_entry=0.5,
                                 roundtrip_cost_pct=0.20)[0]
    assert mc < m0


def test_mc_cell_reproducible_and_venture_shaped():
    s = _struct(rule="hold")
    c1 = run_cell_mc(s, mu=0.10, sigma_real=0.5, n_paths=2000, r=0.04, roundtrip_cost_pct=0.05, seed=7)
    c2 = run_cell_mc(s, mu=0.10, sigma_real=0.5, n_paths=2000, r=0.04, roundtrip_cost_pct=0.05, seed=7)
    assert np.allclose(c1.multiples, c2.multiples)  # seeded
    st = payoff_stats(c1)
    # Venture shape: most lose, mean dragged by a right tail.
    assert st.p_total_loss > 0.3
    assert st.quantiles["p99"] > st.median_multiple


def test_breakeven_hit_rate_math():
    # winners avg 5×, losers all 0 → p* = (1−0)/(5−0) = 0.2
    m = np.array([0.0] * 8 + [5.0, 5.0])
    p = breakeven_hit_rate(m)
    assert abs(p - 0.2) < 1e-9
    # no winners → undefined
    assert breakeven_hit_rate(np.zeros(10)) is None


def test_payoff_stats_empty():
    s = _struct()
    cell = run_cell_mc(s, mu=0.0, sigma_real=0.01, n_paths=0, r=0.04, roundtrip_cost_pct=0.05)
    st = payoff_stats(cell)
    assert st.n == 0


def test_historical_cell_runs_on_paths():
    paths = [np.linspace(100, 150, 271), np.full(271, 100.0)]
    cell = run_cell_historical(_struct(), paths=paths, sigma_real_of=lambda p: 0.5,
                               r=0.04, roundtrip_cost_pct=0.05)
    assert cell.n == 2
    st = payoff_stats(cell)
    assert 0.0 in [round(x, 6) for x in cell.multiples] or st.p_total_loss > 0
