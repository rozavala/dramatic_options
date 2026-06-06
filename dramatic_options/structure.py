"""Defined-risk structure selection (T1) — eligibility + the long-dated far-OTM pick.

PREREG_THEMATIC_CONVEXITY §1/§3. T1 expresses a theme as the simplest defined-risk
long-dated structure: a **single long option** (call for a bullish/tailwind theme, put for
a bearish/rollover theme) at 6–12mo tenor, ~``target_moneyness`` OTM. Max loss = premium
paid (inherently defined-risk). Extensible to verticals/condors later.

Eligibility reuses ``options_tradability.spread_pct`` (the bid/ask gate) plus a per-contract
price band and an open-interest floor (enforced only when the feed reports OI). Pure
functions — offline-testable.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from dramatic_options.convexity_gate import Contract
from dramatic_options.options_tradability import spread_pct

DIRECTION_KIND = {"bullish": "C", "bearish": "P"}


@dataclass(frozen=True)
class Structure:
    direction: str
    kind: str            # "C" / "P"
    contract: Contract
    dte: int
    moneyness: float     # signed (strike − spot)/spot
    entry_premium: float  # per share (mid); per-contract debit = ×100
    max_loss: float       # = entry_premium per share (defined risk)


def mid_price(c: Contract) -> float | None:
    """Two-sided mid, or None if not a usable quote."""
    if c.bid is None or c.ask is None or c.ask <= 0 or c.bid < 0 or c.ask < c.bid:
        return None
    return 0.5 * (c.bid + c.ask)


def contract_eligible(
    c: Contract,
    *,
    max_spread_pct: float,
    min_contract_price: float,
    max_contract_price: float,
    min_oi: int | None,
) -> tuple[bool, tuple[str, ...]]:
    """Per-contract eligibility. Fail-closed on a missing two-sided quote / price."""
    reasons: list[str] = []
    sp = spread_pct(c.bid, c.ask)
    if sp is None:
        reasons.append("no_two_sided_quote")
    elif sp > max_spread_pct:
        reasons.append(f"spread {sp:.0%}>{max_spread_pct:.0%}")
    m = mid_price(c)
    if m is None:
        reasons.append("no_mid")
    else:
        if m < min_contract_price:
            reasons.append(f"contract_px {m:.2f}<{min_contract_price}")
        if m > max_contract_price:
            reasons.append(f"contract_px {m:.2f}>{max_contract_price}")
    # OI enforced only when the feed provides it (Alpaca's chain snapshot may omit OI).
    if min_oi is not None and c.oi is not None and c.oi < min_oi:
        reasons.append(f"oi {c.oi}<{min_oi}")
    return (not reasons, tuple(reasons))


def select_structure(
    chain: list[Contract],
    *,
    direction: str,
    as_of: date,
    underlying_price: float | None,
    tenor_min_days: int,
    tenor_max_days: int,
    target_moneyness: float,
    eligibility: Callable[[Contract], tuple[bool, tuple[str, ...]]],
) -> tuple[Structure | None, tuple[str, ...]]:
    """Pick the defined-risk long option closest to the target OTM strike within the tenor
    window, among eligible contracts. Returns (Structure, ()) or (None, reasons)."""
    kind = DIRECTION_KIND.get(direction)
    if kind is None:
        return None, (f"bad_direction:{direction}",)
    if not underlying_price or underlying_price <= 0:
        return None, ("no_underlying_price",)

    if kind == "C":
        target_strike = underlying_price * (1.0 + target_moneyness)
    else:
        target_strike = underlying_price * (1.0 - target_moneyness)
    tenor_mid = (tenor_min_days + tenor_max_days) / 2.0

    cands: list[tuple[Contract, int]] = []
    for c in chain:
        if c.kind != kind:
            continue
        dte = (c.expiry - as_of).days
        if dte < tenor_min_days or dte > tenor_max_days:
            continue
        ok, _ = eligibility(c)
        if not ok:
            continue
        cands.append((c, dte))

    if not cands:
        return None, ("no_eligible_contract_in_tenor_window",)

    c, dte = min(cands, key=lambda t: (abs(t[0].strike - target_strike), abs(t[1] - tenor_mid)))
    m = mid_price(c)
    if m is None or m <= 0:
        return None, ("chosen_contract_no_mid",)
    moneyness = (c.strike - underlying_price) / underlying_price
    return Structure(direction, kind, c, dte, moneyness, m, m), ()
