"""D3 step 1: the wide call vertical selector (selection only; no order path)."""

from datetime import date

from convexity_gate import Contract
from structure import Structure
from verticals import select_vertical

EXP = date(2027, 6, 17)


def _c(k, bid, ask, sym="NVDA", kind="C", exp=EXP):
    return Contract(symbol=f"{sym}{exp:%y%m%d}{kind}{int(k * 1000):08d}", expiry=exp, kind=kind, strike=k,
                    bid=bid, ask=ask, iv=0.5, oi=500)


def _long(c, mid):
    return Structure("bullish", "C", c, 226, 0.25, mid, mid)


OK = lambda c: (True, ())  # noqa: E731
SPOT = 100.0


def test_picks_the_wing_nearest_plus_75():
    lg = _c(125, 10.4, 10.8)
    chain = [lg, _c(150, 6.0, 6.4), _c(160, 4.6, 5.0), _c(180, 3.0, 3.4), _c(200, 2.0, 2.4)]
    v, why = select_vertical(chain, _long(lg, 10.6), underlying_price=SPOT, eligibility=OK, underlying_symbol="NVDA")
    assert why == () and v.short.strike == 180 and v.short_moneyness == 0.80   # nearest +75% (175)
    assert v.net_debit == 10.6 - 3.2 and v.width == 55 and round(v.debit_per_contract) == 740
    assert v.max_multiple == 55 / (10.6 - 3.2)


def test_fail_closed_cases():
    lg = _c(125, 10.4, 10.8)
    L = _long(lg, 10.6)
    sel = lambda chain, **kw: select_vertical(chain, L, underlying_price=SPOT, eligibility=OK,  # noqa: E731
                                              underlying_symbol="NVDA", **kw)[1]
    assert sel([lg]) == ("no_eligible_short_leg",)
    assert sel([lg, _c(140, 7.0, 7.4)])[0].startswith("short_leg_too_near")          # only a narrow spread
    assert sel([lg, _c(180, 3.0, 3.4, exp=date(2027, 9, 17))]) == ("no_eligible_short_leg",)  # other expiry
    assert sel([lg, _c(180, 3.0, 3.4, sym="NVDA1")]) == ("no_eligible_short_leg",)    # adjusted class
    assert sel([lg, _c(180, None, 3.4)]) == ("short_leg_no_mid",)
    put = Structure("bearish", "P", _c(75, 5, 5.2, kind="P"), 226, -0.25, 5.1, 5.1)
    assert select_vertical([lg], put, underlying_price=SPOT, eligibility=OK)[1] == ("vertical_calls_only",)
    inel = lambda c: (c.strike != 180, ("spread",))  # noqa: E731
    assert select_vertical([lg, _c(180, 3.0, 3.4)], L, underlying_price=SPOT, eligibility=inel,
                           underlying_symbol="NVDA")[1] == ("no_eligible_short_leg",)
