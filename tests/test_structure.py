"""Structure selection: tenor + moneyness pick, eligibility, defined-risk premium."""

from datetime import date, timedelta

from dramatic_options.convexity_gate import Contract
from dramatic_options.structure import contract_eligible, mid_price, select_structure

AS_OF = date(2026, 1, 2)


def _c(kind, strike, dte, *, bid=2.0, ask=2.1, oi=500):
    return Contract(symbol=f"X{kind}{strike}", expiry=AS_OF + timedelta(days=dte), kind=kind,
                    strike=strike, bid=bid, ask=ask, iv=0.4, oi=oi)


def _elig(c):
    return contract_eligible(c, max_spread_pct=0.25, min_contract_price=0.10,
                             max_contract_price=100.0, min_oi=50)


def test_mid_price():
    assert mid_price(_c("C", 125, 270)) == 2.05
    assert mid_price(Contract("Z", AS_OF, "C", 1, bid=None, ask=2.0)) is None


def test_contract_eligible_spread_and_oi():
    ok, _ = _elig(_c("C", 125, 270))
    assert ok is True
    bad_spread = _c("C", 125, 270, bid=1.0, ask=2.0)  # 67% spread
    assert _elig(bad_spread)[0] is False
    low_oi = _c("C", 125, 270, oi=10)
    assert _elig(low_oi)[0] is False
    no_quote = Contract("Z", AS_OF + timedelta(days=270), "C", 125, bid=None, ask=None, oi=500)
    ok2, reasons = _elig(no_quote)
    assert ok2 is False and "no_two_sided_quote" in reasons


def test_select_bullish_picks_otm_call_in_tenor():
    chain = [
        _c("C", 100, 270),   # ATM
        _c("C", 125, 270),   # ~25% OTM, in tenor → target
        _c("C", 125, 30),    # right strike, WRONG tenor (too short)
        _c("C", 200, 270),   # too far OTM
        _c("P", 75, 270),    # wrong side
    ]
    s, reasons = select_structure(
        chain, direction="bullish", as_of=AS_OF, underlying_price=100.0,
        tenor_min_days=180, tenor_max_days=365, target_moneyness=0.25, eligibility=_elig,
    )
    assert s is not None, reasons
    assert s.kind == "C" and s.contract.strike == 125
    assert 180 <= s.dte <= 365
    assert abs(s.moneyness - 0.25) < 1e-9
    assert s.max_loss == s.entry_premium == mid_price(_c("C", 125, 270))


def test_select_bearish_picks_put():
    chain = [_c("P", 75, 270), _c("C", 125, 270)]
    s, _ = select_structure(
        chain, direction="bearish", as_of=AS_OF, underlying_price=100.0,
        tenor_min_days=180, tenor_max_days=365, target_moneyness=0.25, eligibility=_elig,
    )
    assert s is not None and s.kind == "P" and s.contract.strike == 75


def test_select_no_underlying_or_no_candidate():
    chain = [_c("C", 125, 270)]
    assert select_structure(chain, direction="bullish", as_of=AS_OF, underlying_price=None,
                            tenor_min_days=180, tenor_max_days=365, target_moneyness=0.25,
                            eligibility=_elig)[0] is None
    short_only = [_c("C", 125, 30)]
    s, reasons = select_structure(short_only, direction="bullish", as_of=AS_OF,
                                  underlying_price=100.0, tenor_min_days=180, tenor_max_days=365,
                                  target_moneyness=0.25, eligibility=_elig)
    assert s is None and "no_eligible_contract_in_tenor_window" in reasons


def test_bad_direction():
    s, reasons = select_structure([], direction="sideways", as_of=AS_OF, underlying_price=100.0,
                                  tenor_min_days=180, tenor_max_days=365, target_moneyness=0.25,
                                  eligibility=_elig)
    assert s is None and reasons[0].startswith("bad_direction")
