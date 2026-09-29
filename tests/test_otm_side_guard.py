"""Issue #276 — the fail-closed side guard in ``select_structure`` + the spread-limit float tolerance.

The fixtures reproduce the two thin chains verified on 2026-09-28 (``records/2026-09-29_itm_fallback_finding.md``):
STUB's five April puts and KLAR's August puts. With the guard OFF (the default, byte-identical) the selector still
takes the nearest eligible strike — which on these chains is in the money. With it ON, wrong-side candidates are
dropped and a chain with only in-the-money eligible contracts yields NO structure (fail-closed), never ITM.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

import pytest

from convexity_gate import Contract
from structure import contract_eligible, select_structure

AS_OF = date(2026, 9, 28)


def _c(kind, strike, dte, bid, ask):
    return Contract(symbol=f"T{kind}{strike}", expiry=AS_OF + timedelta(days=dte), kind=kind, strike=strike,
                    bid=bid, ask=ask, iv=0.6, oi=None)


def _elig(c):
    return contract_eligible(c, max_spread_pct=0.25, min_contract_price=0.10, max_contract_price=100.0, min_oi=50)


def _pick(chain, direction, spot, guard):
    return select_structure(chain, direction=direction, as_of=AS_OF, underlying_price=spot, tenor_min_days=180,
                            tenor_max_days=365, target_moneyness=0.25, eligibility=_elig, require_otm_side=guard)


# STUB, 2026-09-28 close: spot $5.30, target put strike $3.97; five April puts, $2.50 apart.
STUB = [_c("P", 2.5, 200, 0.0, 0.1), _c("P", 5.0, 200, 0.7, 0.9), _c("P", 7.5, 200, 2.4, 2.6),
        _c("P", 10.0, 200, 4.5, 4.9), _c("P", 12.5, 200, 6.8, 7.7)]
# KLAR, 2026-09-28 close (the August expiry): spot $12.41, target $9.31; every OTM put fails the spread limit.
KLAR = [_c("P", 10.0, 326, 0.5, 4.1), _c("P", 12.5, 326, 0.5, 4.7), _c("P", 15.0, 326, 2.05, 5.6),
        _c("P", 17.5, 326, 5.7, 6.7), _c("P", 25.0, 326, 12.1, 13.5)]


def test_klar_shape_reproduces_the_defect_off_and_fails_closed_on():
    off, _ = _pick(KLAR, "bearish", 12.41, guard=False)
    assert off.contract.strike == 17.5 and off.moneyness > 0.40          # the booked 41%-ITM put
    on, why = _pick(KLAR, "bearish", 12.41, guard=True)
    assert on is None and why == ("no_otm_eligible_contract_in_tenor_window",)


def test_stub_shape_itm_only_fails_closed_on():
    itm_only = [c for c in STUB if c.strike != 5.0]                       # drop the one OTM-side strike
    off, _ = _pick(itm_only, "bearish", 5.30, guard=False)
    assert off.contract.strike == 7.5 and off.moneyness > 0.40           # the booked 42%-ITM put
    on, why = _pick(itm_only, "bearish", 5.30, guard=True)
    assert on is None and why == ("no_otm_eligible_contract_in_tenor_window",)


def test_stub_shape_with_the_float_fix_selects_the_near_money_otm_put():
    """The $5.00 put quoted $0.70/$0.90 — a spread of EXACTLY 25%, previously rejected by float rounding.
    With the tolerance it is eligible, so STUB selects it (6% OTM) with or without the guard. Right side of
    the money, but NOT far-OTM: option 1 alone permits near-money picks; only option 2's band would not."""
    for guard in (False, True):
        s, _ = _pick(STUB, "bearish", 5.30, guard=guard)
        assert s.contract.strike == 5.0 and -0.07 < s.moneyness < 0


def test_guard_prefers_a_farther_otm_over_a_nearer_itm():
    chain = [_c("P", 101.0, 270, 5.0, 5.2), _c("P", 40.0, 270, 0.30, 0.34)]  # target 75: ITM 101 is nearer
    off, _ = _pick(chain, "bearish", 100.0, guard=False)
    on, _ = _pick(chain, "bearish", 100.0, guard=True)
    assert off.contract.strike == 101.0 and on.contract.strike == 40.0


def test_calls_itm_only_fail_closed_and_atm_is_not_otm():
    chain = [_c("C", 80.0, 270, 21.0, 22.0), _c("C", 100.0, 270, 8.0, 8.4), _c("C", 125.0, 270, 0.0, 0.4)]
    off, _ = _pick(chain, "bullish", 100.0, guard=False)
    assert off.contract.strike == 100.0                                   # nearest eligible to 125 = ATM
    on, why = _pick(chain, "bullish", 100.0, guard=True)
    assert on is None and why == ("no_otm_eligible_contract_in_tenor_window",)   # ATM is not OTM


def test_normal_chain_is_unchanged_by_the_guard():
    chain = [_c("C", 100.0, 270, 8.0, 8.4), _c("C", 125.0, 270, 2.0, 2.1), _c("C", 150.0, 270, 0.6, 0.7)]
    off, _ = _pick(chain, "bullish", 100.0, guard=False)
    on, _ = _pick(chain, "bullish", 100.0, guard=True)
    assert off.contract.symbol == on.contract.symbol and on.contract.strike == 125.0


def test_the_empty_chain_reason_is_unchanged():
    assert _pick([], "bearish", 10.0, guard=True)[1] == ("no_eligible_contract_in_tenor_window",)


def test_spread_limit_admits_exactly_the_limit_only():
    at_limit = _c("P", 5.0, 200, 0.7, 0.9)            # (0.9-0.7)/0.8 = 0.25000000000000006 in floating point
    assert (0.9 - 0.7) / 0.8 > 0.25                   # the rounding that used to reject it
    assert _elig(at_limit)[0] is True
    over = _c("P", 5.0, 200, 0.7, 0.91)               # ~26%
    ok, why = _elig(over)
    assert ok is False and any(r.startswith("spread") for r in why)


@pytest.mark.parametrize("module", ["paper_loop.py", "shadow_book.py", "fixed_basket.py", "shares_basket.py",
                                    "gate_dualread.py", "cheapness_watch.py"])
def test_every_book_and_gate_path_passes_the_one_switch(module):
    """The real book, the null books and the gate record must all read the same switch, so turning it on
    changes them together. (survivor_cards + scripts/ are intentionally out: the admission band already rejects
    ITM, and the miss base-rate ledger's frozen definition needs its own dated note before it changes.)"""
    src = (Path(__file__).resolve().parents[1] / module).read_text()
    calls = len(re.findall(r"=\s*select_structure\(", src))   # every call site is an assignment
    wired = src.count('require_otm_side=bool(gate.get("otm_side_guard", False))')
    assert calls >= 1 and wired == calls, f"{module}: {calls} call(s), {wired} wired"


def test_the_switch_is_off_in_config_and_turning_it_on_segments_the_frame():
    import json

    from config_loader import frame_version
    cfg = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text())
    assert "otm_side_guard" not in cfg["convexity_gate"]   # draft: OFF, and the frame hash untouched
    on = {**cfg, "convexity_gate": {**cfg["convexity_gate"], "otm_side_guard": True}}
    assert frame_version(on) != frame_version(cfg)          # enabling it IS a recorded frame change
