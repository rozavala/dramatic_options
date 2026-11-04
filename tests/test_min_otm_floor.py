"""#416 — the selector's fail-closed moneyness floor (operator word 2026-11-04, PREREG_THEMATIC_CONVEXITY amendment).

The frame is far-OTM. On L1 #1918 the nearest-eligible fallback put TITN at 7% OTM (C25) when the ~28%-OTM C30 was
refused by eligibility; with the floor that is "no structure", never a near-money fallback."""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path

import pytest

from convexity_gate import Contract
from structure import contract_eligible, select_structure

ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 1, 2)


def _c(kind, strike, *, bid=2.0, ask=2.1, oi=500, dte=226):
    return Contract(symbol=f"X{kind}{strike}", expiry=AS_OF + timedelta(days=dte), kind=kind, strike=strike,
                    bid=bid, ask=ask, iv=0.4, oi=oi)


def _elig(c):
    return contract_eligible(c, max_spread_pct=0.25, min_contract_price=0.10, max_contract_price=100.0, min_oi=50)


def _select(chain, *, spot, direction="bullish", floor=0.15):
    return select_structure(chain, direction=direction, as_of=AS_OF, underlying_price=spot, tenor_min_days=180,
                            tenor_max_days=365, target_moneyness=0.25, eligibility=_elig, require_otm_side=True,
                            min_otm_moneyness=floor)


def test_the_titn_1918_shape_fails_closed_instead_of_buying_near_money():
    chain = [_c("C", 25.0), _c("C", 30.0, bid=1.0, ask=2.0), _c("C", 22.5)]          # spot 23.36: C25 = 7.0% OTM
    s, why = _select(chain, spot=23.36, floor=0.0)
    assert s.contract.symbol == "XC25.0"                                            # the defect, floor off
    s, why = _select(chain, spot=23.36)
    assert s is None and why == ("no_eligible_contract_beyond_min_moneyness",)


def test_when_the_far_wing_is_eligible_it_is_chosen_as_before():
    chain = [_c("C", 25.0), _c("C", 30.0), _c("C", 35.0)]
    assert _select(chain, spot=23.36)[0].contract.symbol == "XC30.0"                   # 28.4% OTM, as on 11-04


def test_puts_measure_the_floor_on_the_downside():
    chain = [_c("P", 95.0), _c("P", 85.0), _c("P", 70.0, bid=1.0, ask=2.0)]         # spot 100, target 75
    s, _ = _select(chain, spot=100.0, direction="bearish")
    assert s.contract.symbol == "XP85.0"                                            # 15% OTM passes, 5% does not
    assert _select([_c("P", 95.0)], spot=100.0, direction="bearish")[0] is None


def test_exactly_the_floor_is_admitted():
    assert _select([_c("C", 115.0)], spot=100.0)[0].contract.symbol == "XC115.0"       # 15.0% exactly


def test_a_zero_floor_is_byte_identical():
    chain = [_c("C", 105.0), _c("C", 125.0, bid=1.0, ask=2.0), _c("C", 140.0)]
    a = select_structure(chain, direction="bullish", as_of=AS_OF, underlying_price=100.0, tenor_min_days=180,
                         tenor_max_days=365, target_moneyness=0.25, eligibility=_elig, require_otm_side=True)
    assert a == _select(chain, spot=100.0, floor=0.0)


def test_refused_contracts_below_the_floor_are_not_listed_as_nearer():
    # C120 (20%) refused, C110 (10%) refused, C140 chosen: only C120 could have been chosen under the floor
    s, _ = _select([_c("C", 120.0, oi=10), _c("C", 110.0, oi=10), _c("C", 140.0)], spot=100.0)
    assert s.contract.symbol == "XC140.0" and [sym for sym, _ in s.refused_nearer] == ["XC120.0"]


@pytest.mark.parametrize("module", ["paper_loop.py", "shadow_book.py", "fixed_basket.py", "shares_basket.py",
                                    "gate_dualread.py", "cheapness_watch.py"])
def test_every_book_and_gate_path_passes_the_floor(module):
    src = (ROOT / module).read_text()
    calls = len(re.findall(r"=\s*select_structure\(", src))
    wired = src.count('min_otm_moneyness=float(gate.get("min_otm_moneyness", 0.0) or 0.0)')
    assert calls >= 1 and wired == calls, f"{module}: {calls} call(s), {wired} wired"


def test_the_floor_is_on_in_config_and_moves_the_frame():
    from config_loader import frame_version
    cfg = json.loads((ROOT / "config.json").read_text())
    assert cfg["convexity_gate"]["min_otm_moneyness"] == 0.15                        # operator word 2026-11-04
    off = {**cfg, "convexity_gate": {k: v for k, v in cfg["convexity_gate"].items() if k != "min_otm_moneyness"}}
    assert frame_version(cfg) != frame_version(off)
