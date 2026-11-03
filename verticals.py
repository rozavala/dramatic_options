"""Wide debit call verticals for over-cap names — D3 step 1 (calibration v2 Rule V: CANDIDATE).

**Selection and arithmetic only. Nothing here places an order or is called from the trade path.** The live path
(multi-leg broker orders, a second-leg column, spread marking/expiry/close/reconcile in the monitor, carry walking,
and the same structure in the shadow/3A books so the null contrasts stay paired) is D3 step 2, its own phase.

Rule V (records/2026-11-03_calibration_v2_finding.md): long the gate-of-record ≈25%-OTM call, short the call nearest
+75% OTM at the same expiry — premium ≈0.71× naked, mean multiple ≈0.98× naked under jumps, p99 cut from ~10.7× to
~7×. For a name whose single naked contract exceeds the per-name cap, that is a shot the book can't otherwise take.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from convexity_gate import Contract, occ_root
from structure import Structure, mid_price

SHORT_MONEYNESS = 0.75       # the Rule V wing
MIN_SHORT_MONEYNESS = 0.50   # a short wing nearer than this is a narrow spread: a different payoff object


@dataclass(frozen=True)
class Vertical:
    long: Structure
    short: Contract
    short_moneyness: float   # (short strike − spot) / spot
    net_debit: float         # per share: long mid − short mid (the max loss)
    width: float             # short strike − long strike (the max value per share)

    @property
    def debit_per_contract(self) -> float:
        return self.net_debit * 100.0

    @property
    def max_multiple(self) -> float:
        return self.width / self.net_debit


def select_vertical(
    chain: list[Contract], long: Structure, *, underlying_price: float | None,
    eligibility: Callable[[Contract], tuple[bool, tuple[str, ...]]], underlying_symbol: str | None = None,
    short_moneyness: float = SHORT_MONEYNESS, min_short_moneyness: float = MIN_SHORT_MONEYNESS,
) -> tuple[Vertical | None, tuple[str, ...]]:
    """The short call for ``long`` (same expiry, same OCC class, eligible, nearest ``short_moneyness``), or
    (None, reasons). Fail-closed: calls only, a two-sided short quote, a positive debit below the width."""
    if long.kind != "C":
        return None, ("vertical_calls_only",)
    if not underlying_price or underlying_price <= 0:
        return None, ("no_underlying_price",)
    root = (underlying_symbol or occ_root(long.contract.symbol)).upper()
    cands = []
    for c in chain:
        if c.kind != "C" or c.expiry != long.contract.expiry or c.strike <= long.contract.strike:
            continue
        if occ_root(c.symbol) != root:
            continue
        ok, _ = eligibility(c)
        if ok:
            cands.append(c)
    if not cands:
        return None, ("no_eligible_short_leg",)
    target = underlying_price * (1.0 + short_moneyness)
    short = min(cands, key=lambda c: abs(c.strike - target))
    sm = (short.strike - underlying_price) / underlying_price
    if sm < min_short_moneyness:
        return None, (f"short_leg_too_near:{sm:.0%}",)
    smid = mid_price(short)
    if smid is None:
        return None, ("short_leg_no_mid",)
    debit = long.entry_premium - smid
    width = short.strike - long.contract.strike
    if debit <= 0 or debit >= width:
        return None, (f"bad_debit:{debit:.2f}",)
    return Vertical(long, short, sm, debit, width), ()
