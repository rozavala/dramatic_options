"""Friction composite: input assembly, cross-section z-score, corner membership, mean-impute."""

from friction import FRICTION_INPUTS, friction_inputs, score_cross_section


def test_friction_inputs_invert_correctly():
    fi = friction_inputs(si_pct=0.3, shares_out=10_000_000, adv_usd=2_000_000, price=5.0,
                         days_to_cover=4.0)
    assert fi["si_pct"] == 0.3
    assert fi["days_to_cover"] == 4.0
    assert fi["inv_float"] == 1 / 10_000_000
    assert fi["inv_adv"] == 1 / 2_000_000
    assert fi["inv_price"] == 0.2
    # zero/None guards → None, not a divide error (days_to_cover defaults to None)
    assert friction_inputs(si_pct=None, shares_out=0, adv_usd=None, price=0) == {
        "si_pct": None, "days_to_cover": None, "inv_float": None, "inv_adv": None,
        "inv_price": None,
    }


def test_corner_is_top_quantile_of_composite():
    # 5 names with monotonically increasing friction on every input → highest is the corner
    rows = []
    for i in range(5):
        rows.append(friction_inputs(
            si_pct=0.1 * (i + 1),
            days_to_cover=1.0 * (i + 1),
            shares_out=10_000_000 / (i + 1),   # smaller float = higher inv_float for big i
            adv_usd=5_000_000 / (i + 1),
            price=100.0 / (i + 1),
        ))
    res = score_cross_section(rows, corner_quantile=0.8)
    # the last (hardest-to-short) name is in the corner; the first is not
    assert res.in_corner[-1] is True
    assert res.in_corner[0] is False
    # composite is monotonically increasing in friction here
    assert res.composite[-1] > res.composite[0]
    assert all(p == 5 for p in res.inputs_present)  # all five inputs present


def test_freeze_b_weights_lean_on_borrow_dimension():
    """FREEZE-B #4: with corr(si_pct,inv_float)≈1, leaning weight onto si_pct+days_to_cover
    must change the ranking vs equal weight (the smallness names no longer dominate)."""
    # name A: huge borrow pressure, NOT tiny;  name B: tiny float, NO short interest
    rows = [
        friction_inputs(si_pct=0.40, days_to_cover=15.0, shares_out=80_000_000,
                        adv_usd=20_000_000, price=40.0),   # high borrow, mid-cap
        friction_inputs(si_pct=0.01, days_to_cover=0.3, shares_out=900_000,
                        adv_usd=200_000, price=1.5),        # tiny/illiquid, no borrow
        friction_inputs(si_pct=0.05, days_to_cover=1.0, shares_out=30_000_000,
                        adv_usd=8_000_000, price=20.0),
    ]
    borrow_w = {"si_pct": 1.0, "days_to_cover": 1.0, "inv_float": 0.34,
                "inv_adv": 0.33, "inv_price": 0.33}
    res_borrow = score_cross_section(rows, weights=borrow_w)
    res_equal = score_cross_section(rows)  # equal weight
    # under borrow weighting the high-SI mid-cap (row 0) ranks above the tiny illiquid (row 1);
    # under equal weight the smallness proxies pull row 1 up relative to row 0.
    assert res_borrow.composite[0] > res_borrow.composite[1]
    assert (res_borrow.composite[0] - res_borrow.composite[1]) > \
           (res_equal.composite[0] - res_equal.composite[1])


def test_mean_imputes_missing_inputs():
    rows = [
        friction_inputs(si_pct=0.5, shares_out=1_000_000, adv_usd=1_000_000, price=2.0,
                        days_to_cover=3.0),
        {"si_pct": None, "days_to_cover": None, "inv_float": None, "inv_adv": None,
         "inv_price": None},  # all missing
        friction_inputs(si_pct=0.1, shares_out=50_000_000, adv_usd=50_000_000, price=200.0,
                        days_to_cover=0.5),
    ]
    res = score_cross_section(rows)
    # the all-missing row gets composite ≈ 0 (every column mean-imputed) — not an error/NaN
    assert abs(res.composite[1]) < 1e-9
    assert res.inputs_present[1] == 0
    assert res.inputs_present[0] == 5


def test_input_corr_reported():
    rows = []
    for i in range(6):
        rows.append(friction_inputs(
            si_pct=0.1 * (i + 1), days_to_cover=1.0 * (i + 1),
            shares_out=10_000_000 / (i + 1),
            adv_usd=5_000_000 / (i + 1), price=100.0 / (i + 1)))
    res = score_cross_section(rows)
    # inv_float / inv_adv / inv_price are all ~collinear (all scale with i+1) → high corr
    assert any(v > 0.9 for v in res.input_corr.values())
    assert set(FRICTION_INPUTS) == {"si_pct", "days_to_cover", "inv_float", "inv_adv", "inv_price"}
