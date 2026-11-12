"""Calibration engine + metrics: deterministic-path payoffs, exits, transfer/EV math."""

import numpy as np

from calibration.engine import (
    Structure,
    run_cell_historical,
    run_cell_mc,
    simulate_option_on_path,
)
from calibration.metrics import breakeven_hit_rate, payoff_stats


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


# ── calibration v2 (PREREG_CONVEXITY_CALIBRATION §4 amendment 2026-11-03) ───────────────────
import pytest  # noqa: E402

from calibration.engine import JumpModel, ThesisModel, entry_premium  # noqa: E402
from calibration.pricing import simulate_merton_path  # noqa: E402


def test_merton_path_is_seeded_and_drift_compensated():
    a = simulate_merton_path(spot=100.0, mu=0.10, sigma=0.5, days=365, rng=np.random.default_rng(3),
                             jump_lambda=2.0, jump_sigma=0.2)
    b = simulate_merton_path(spot=100.0, mu=0.10, sigma=0.5, days=365, rng=np.random.default_rng(3),
                             jump_lambda=2.0, jump_sigma=0.2)
    assert np.array_equal(a, b)
    rng = np.random.default_rng(11)
    terminal = [simulate_merton_path(spot=1.0, mu=0.10, sigma=0.5, days=365, rng=rng,
                                     jump_lambda=2.0, jump_sigma=0.2)[-1] for _ in range(6000)]
    assert abs(np.mean(terminal) - np.exp(0.10)) < 0.03     # E[S_T] = S0·e^{μT}
    assert abs(np.std(np.log(terminal)) - 0.5) < 0.03        # total vol held at σ


def test_salvage_sells_at_the_mark_on_the_falsifier_day():
    path = np.full(190, 100.0)                     # flat: a hold expires worthless
    s = _struct(rule="live", profit_take_mult=10.0, salvage=True)
    m, _, why = simulate_option_on_path(path, structure=s, r=0.04, sigma_entry=0.5,
                                        roundtrip_cost_pct=0.05, falsifier_step=62)
    assert why == "salvage"
    assert 0.0 < m < 1.0                           # recovers part of the premium
    m2, _, why2 = simulate_option_on_path(path, structure=s, r=0.04, sigma_entry=0.5,
                                          roundtrip_cost_pct=0.05, falsifier_step=None)
    assert why2 == "time_stop" and m2 < m          # no fire ⇒ the live exit, decayed further


def test_salvage_flag_off_ignores_the_falsifier():
    path = np.full(190, 100.0)
    s = _struct(rule="hold")
    _, _, why = simulate_option_on_path(path, structure=s, r=0.04, sigma_entry=0.5,
                                        roundtrip_cost_pct=0.0, falsifier_step=62)
    assert why == "expiry"


def test_house_money_roll_keeps_the_stake_through_a_crash():
    # Spike to +60% in 20 days, then collapse: the naked live leg rides it to zero;
    # the 3× roll banked the original premium first.
    path = np.concatenate([np.linspace(100.0, 160.0, 21), np.full(169, 50.0)])
    live = _struct(rule="live", profit_take_mult=10.0)
    rolled = _struct(rule="live", profit_take_mult=10.0, roll_trigger_mult=3.0)
    m_live, _, _ = simulate_option_on_path(path, structure=live, r=0.04, sigma_entry=0.5,
                                           roundtrip_cost_pct=0.0)
    m_roll, _, why = simulate_option_on_path(path, structure=rolled, r=0.04, sigma_entry=0.5,
                                             roundtrip_cost_pct=0.0)
    assert m_live < 0.05
    assert why == "time_stop"
    assert m_roll == pytest.approx(1.0, abs=0.02)  # the banked stake (the rolled leg ≈ worthless)


def test_vertical_is_cheaper_and_capped():
    naked = _struct(rule="hold", tenor=270)
    vert = _struct(rule="hold", tenor=270, short_moneyness=1.0)
    e_naked = entry_premium(naked, spot=100.0, r=0.04, sigma_entry=0.5)
    e_vert = entry_premium(vert, spot=100.0, r=0.04, sigma_entry=0.5)
    assert 0 < e_vert < e_naked
    path = np.linspace(100.0, 400.0, 190)          # a 4× move: past both strikes
    m, _, why = simulate_option_on_path(path, structure=vert, r=0.04, sigma_entry=0.5,
                                        roundtrip_cost_pct=0.0)
    assert why == "expiry"
    assert m == pytest.approx((200.0 - 125.0) / e_vert, rel=1e-9)   # width / premium


def test_roll_on_a_vertical_is_rejected():
    s = _struct(rule="live", roll_trigger_mult=3.0, short_moneyness=1.0)
    with pytest.raises(ValueError):
        simulate_option_on_path(np.full(190, 100.0), structure=s, r=0.04, sigma_entry=0.5,
                                roundtrip_cost_pct=0.0)


def test_paired_cells_share_paths_and_thesis_draws():
    th = ThesisModel(p_right=0.3, mu_right=0.8, falsifier_day=90, accuracy=0.7)
    a = run_cell_mc(_struct(rule="live", profit_take_mult=10.0), mu=0.1, sigma_real=0.5, n_paths=200,
                    r=0.04, roundtrip_cost_pct=0.05, thesis=th, jumps=JumpModel())
    b = run_cell_mc(_struct(rule="live", profit_take_mult=10.0, salvage=True), mu=0.1, sigma_real=0.5,
                    n_paths=200, r=0.04, roundtrip_cost_pct=0.05, thesis=th, jumps=JumpModel())
    assert np.array_equal(a.thesis_right, b.thesis_right)
    assert "salvage" in b.exit_reasons and "salvage" not in a.exit_reasons
    # Two hold-to-expiry cells record the TERMINAL return, so equal arrays ⇒ the same paths.
    h1 = run_cell_mc(_struct(rule="hold", mny=0.25), mu=0.1, sigma_real=0.5, n_paths=100, r=0.04,
                     roundtrip_cost_pct=0.05, thesis=th, jumps=JumpModel())
    h2 = run_cell_mc(_struct(rule="hold", mny=0.40), mu=0.1, sigma_real=0.5, n_paths=100, r=0.04,
                     roundtrip_cost_pct=0.05, thesis=th, jumps=JumpModel())
    assert np.array_equal(h1.underlying_returns, h2.underlying_returns)


def test_thesis_extremes():
    always_wrong = ThesisModel(p_right=0.0, mu_right=0.8, falsifier_day=90, accuracy=1.0)
    c = run_cell_mc(_struct(rule="hold", tenor=270, salvage=True), mu=0.0, sigma_real=0.5, n_paths=50,
                    r=0.04, roundtrip_cost_pct=0.0, thesis=always_wrong)
    assert not c.thesis_right.any()
    assert set(c.exit_reasons) == {"salvage"}      # a perfect falsifier fires on every wrong path
