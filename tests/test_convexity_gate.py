"""IV/cheap-convexity gate: realized vol, IV/RV + skew thresholds, fail-closed."""

import math
from datetime import date

from dramatic_options.convexity_gate import Contract, atm_iv, is_cheap_convexity, realized_vol

EXP = date(2026, 9, 30)


def _c(kind, strike, iv):
    mid = max(0.2, iv * 4)
    return Contract(symbol=f"X{strike}{kind}", expiry=EXP, kind=kind, strike=strike,
                    bid=mid * 0.97, ask=mid * 1.03, iv=iv, oi=500)


def _chain():
    # ATM call iv 0.40 (strike 100), wing call iv 0.42 (strike 125), plus some puts.
    return [_c("C", 100, 0.40), _c("C", 105, 0.41), _c("C", 125, 0.42), _c("P", 75, 0.45)]


def test_realized_vol_constant_is_zero():
    assert realized_vol([10.0] * 30, window=20) == 0.0


def test_realized_vol_insufficient_returns_none():
    assert realized_vol([10.0, 11.0], window=20) is None
    assert realized_vol(None, window=20) is None
    assert realized_vol([], window=20) is None


def test_realized_vol_recovers_known_sigma():
    # Alternating ±d log-returns → annualized vol ≈ d·√252.
    d = 0.02
    px = [100.0]
    for i in range(60):
        px.append(px[-1] * math.exp(d if i % 2 == 0 else -d))
    rv = realized_vol(px, window=50)
    assert rv is not None
    assert abs(rv - d * math.sqrt(252)) < 0.02


def test_atm_iv_picks_nearest_strike():
    assert atm_iv(_chain(), 101.0, "C", EXP) == 0.40


def test_cheap_passes_both_thresholds():
    wing = _c("C", 125, 0.42)
    v = is_cheap_convexity(_chain(), underlying_price=100.0, wing=wing, rv=0.38,
                           iv_rv_max=1.2, otm_skew_max_volpts=10.0)
    assert v.cheap is True
    assert v.iv_rv_ratio is not None and v.iv_rv_ratio < 1.2
    assert v.otm_skew_volpts is not None and v.otm_skew_volpts <= 10.0


def test_rich_by_iv_rv_vetoes():
    wing = _c("C", 125, 0.42)
    v = is_cheap_convexity(_chain(), underlying_price=100.0, wing=wing, rv=0.20,
                           iv_rv_max=1.2, otm_skew_max_volpts=10.0)
    assert v.cheap is False
    assert any("iv/rv" in r for r in v.reasons)


def test_rich_by_skew_vetoes():
    rich_wing = _c("C", 125, 0.60)  # wing 0.60 vs atm 0.40 → 20vp skew
    chain = _chain() + [rich_wing]
    v = is_cheap_convexity(chain, underlying_price=100.0, wing=rich_wing, rv=0.40,
                           iv_rv_max=1.2, otm_skew_max_volpts=10.0)
    assert v.cheap is False
    assert any("skew" in r for r in v.reasons)


def test_fail_closed_on_missing_inputs():
    wing = _c("C", 125, 0.42)
    # missing rv
    assert is_cheap_convexity(_chain(), underlying_price=100.0, wing=wing, rv=None,
                              iv_rv_max=1.2, otm_skew_max_volpts=10.0).cheap is False
    # missing wing iv
    wing_no_iv = Contract("Z", EXP, "C", 125, bid=1.0, ask=1.1, iv=None, oi=500)
    v = is_cheap_convexity(_chain(), underlying_price=100.0, wing=wing_no_iv, rv=0.38,
                           iv_rv_max=1.2, otm_skew_max_volpts=10.0)
    assert v.cheap is False and "no_wing_iv" in v.reasons
    # no ATM contract available (empty chain) → no_atm_iv
    v2 = is_cheap_convexity([], underlying_price=100.0, wing=wing, rv=0.38,
                            iv_rv_max=1.2, otm_skew_max_volpts=10.0)
    assert v2.cheap is False and "no_atm_iv" in v2.reasons
