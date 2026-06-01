"""FSSD Stage-1 gate: CAR primitive, trailing-decile no-lookahead, monthly series, bands+controls."""

from datetime import UTC, datetime, timedelta

from fssd_stage1 import (
    assign_trailing_deciles,
    evaluate_stage1,
    forward_car,
    monthly_mean_series,
    per_decile_grid,
)

FSSD = {
    "alpha_base": 0.05,
    "bootstrap_iters": 500,
    "block_months": 1,
    "stage1_bands": {
        "require_negative": True, "cost_stub_bps": 50,
        "car_fail_below_abs": 0.010, "car_green_above_abs": 0.025,
    },
}
W = {"si_pct": 1.0, "days_to_cover": 1.0, "inv_float": 0.34, "inv_adv": 0.33, "inv_price": 0.33}


def test_forward_car_subtracts_beta_benchmark():
    assert forward_car(-0.10, -0.04, 1.5) == -0.10 - 1.5 * -0.04  # = -0.04
    assert forward_car(None, -0.04, 1.5) is None
    assert forward_car(-0.10, None, 1.5) is None
    assert forward_car(-0.10, -0.04, None) is None


def _ev(day, **inputs):
    return {"ts": datetime(2021, 1, 1, tzinfo=UTC) + timedelta(days=day), "inputs": inputs}


def test_trailing_deciles_warmup_is_none_then_assigns():
    # 60 events over time; first min_trailing have too-thin a trailing window -> None
    events = []
    for d in range(60):
        events.append(_ev(d * 3, si_pct=0.01 * d, days_to_cover=0.1 * d,
                          inv_float=1e-7, inv_adv=1e-6, inv_price=0.05))
    deciles = assign_trailing_deciles(events, weights=W, trailing_days=365,
                                      min_trailing=30, n_deciles=10)
    assert deciles[0] is None and deciles[10] is None  # warmup
    assert deciles[-1] is not None                     # later events assigned
    # the latest event has the highest si_pct/days_to_cover -> top decile
    assert deciles[-1] == 9


def test_trailing_deciles_are_no_lookahead():
    # No-lookahead property: an EARLIER event's decile must not change when a LATER event is
    # appended (its decile depends only on its trailing window). Build a genuinely-distributed
    # set so ranks aren't degenerate, then compare with/without an extra future event.
    base = [_ev(i, si_pct=0.01 * (i % 7), days_to_cover=0.5 * (i % 5),
                inv_float=1e-7 * (1 + i % 4), inv_adv=1e-6, inv_price=0.05)
            for i in range(50)]
    d_base = assign_trailing_deciles(base, weights=W, trailing_days=3650,
                                     min_trailing=30, n_deciles=10)
    extended = base + [_ev(60, si_pct=9.0, days_to_cover=99.0, inv_float=1e-5,
                           inv_adv=1e-4, inv_price=0.9)]  # extreme future outlier
    d_ext = assign_trailing_deciles(extended, weights=W, trailing_days=3650,
                                    min_trailing=30, n_deciles=10)
    # every original event keeps its decile — the future outlier changed nothing before it
    assert d_ext[:50] == d_base
    assert d_ext[50] == 9  # the appended outlier itself lands top-decile


def test_monthly_series_and_only_decile_filter():
    events = [
        {"ts": datetime(2021, 1, 5, tzinfo=UTC), "car": -0.05},
        {"ts": datetime(2021, 1, 20, tzinfo=UTC), "car": -0.03},
        {"ts": datetime(2021, 2, 10, tzinfo=UTC), "car": 0.01},
        {"ts": datetime(2021, 2, 15, tzinfo=UTC), "car": None},  # dropped
    ]
    s = monthly_mean_series(events)
    assert s == [("2021-01", -0.04), ("2021-02", 0.01)]
    deciles = [9, 5, 9, 9]
    s9 = monthly_mean_series(events, deciles=deciles, only_decile=9)
    assert s9 == [("2021-01", -0.05), ("2021-02", 0.01)]


def test_per_decile_grid():
    events = [{"ts": datetime(2021, 1, 1, tzinfo=UTC), "car": c} for c in
              [-0.05, -0.03, 0.0, 0.02]]
    deciles = [9, 9, 0, 0]
    grid = per_decile_grid(events, deciles, n_deciles=10)
    by_d = {g["decile"]: g for g in grid}
    assert by_d[9]["n"] == 2 and abs(by_d[9]["mean_car"] - -0.04) < 1e-9
    assert by_d[0]["n"] == 2 and abs(by_d[0]["mean_car"] - 0.01) < 1e-9


def _series(vals, start_month=1):
    return [(f"2021-{start_month + i:02d}", v) for i, v in enumerate(vals)]


def test_gate_green_on_strong_negative_car():
    top = _series([-0.05, -0.06, -0.04, -0.05, -0.07, -0.05, -0.06, -0.04, -0.05, -0.06])
    r = evaluate_stage1(top, k_iterations=1, config_fssd=FSSD)
    assert r.ci_excludes_zero_negative is True
    assert r.band == "GREEN"


def test_gate_fail_on_positive_sign():
    top = _series([0.04, 0.05, 0.03, 0.06, 0.05, 0.04, 0.05, 0.04, 0.05, 0.06])
    r = evaluate_stage1(top, k_iterations=1, config_fssd=FSSD)
    assert r.band == "FAIL"
    assert any("POSITIVE" in n or "wrong sign" in n for n in r.notes)


def test_gate_fail_when_ci_spans_zero():
    top = _series([-0.05, 0.05, -0.04, 0.06, -0.05, 0.05, -0.06, 0.04, -0.05, 0.06])
    r = evaluate_stage1(top, k_iterations=1, config_fssd=FSSD)
    assert r.ci_excludes_zero_negative is False
    assert r.band == "FAIL"


def test_gate_yellow_small_but_significant():
    # tight, consistently negative but small (~1.5% net after 0.5% cost) -> YELLOW
    top = _series([-0.020, -0.021, -0.019, -0.020, -0.022,
                   -0.020, -0.019, -0.021, -0.020, -0.020])
    r = evaluate_stage1(top, k_iterations=1, config_fssd=FSSD)
    assert r.ci_excludes_zero_negative is True
    assert r.band == "YELLOW"


def test_null_persistence_annotated():
    top = _series([-0.05, -0.06, -0.04, -0.05, -0.07, -0.05, -0.06, -0.04, -0.05, -0.06])
    null = _series([-0.05] * 10)
    r = evaluate_stage1(top, k_iterations=1, config_fssd=FSSD, null_series=null)
    assert r.null_vanishes is False
    assert any("NULL control did NOT vanish" in n for n in r.notes)


def test_bonferroni_widens_ci_with_k():
    top = _series([-0.03, -0.035, -0.025, -0.03, -0.032,
                   -0.03, -0.028, -0.031, -0.03, -0.03])
    r1 = evaluate_stage1(top, k_iterations=1, config_fssd=FSSD)
    r5 = evaluate_stage1(top, k_iterations=5, config_fssd=FSSD)
    assert r5.ci_low <= r1.ci_low
