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

from convexity_gate import Contract, occ_root
from options_tradability import spread_pct

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


SPREAD_LIMIT_EPS = 1e-9


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
    elif sp > max_spread_pct + SPREAD_LIMIT_EPS:
        # the epsilon admits a spread of EXACTLY the limit (issue #276: $0.70/$0.90 computes as
        # 0.25000000000000006 and was rejected by float rounding at a 25% cap)
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


# occ_root moved to convexity_gate (this module imports from it; the gate's ATM estimator needs
# the root filter too — the 2026-07-07 CDE1/CDE2 ATM-pollution fix). Re-exported via the import
# above for the existing structure.occ_root callers.


def is_wrong_side(kind: str | None, moneyness: float | None) -> bool:
    """A booked position OUTSIDE the far-OTM frame (issue #276): a call at or below spot, or a put at or above
    it (``moneyness`` = signed (strike − spot)/spot, as stamped at entry). The same strictly-OTM line the side
    guard draws in :func:`select_structure`; used to TAG legacy positions, never to delete or re-mark them."""
    if moneyness is None or kind not in ("C", "P"):
        return False
    return moneyness <= 0 if kind == "C" else moneyness >= 0


# SQL twin of :func:`is_wrong_side` over the book tables' (structure_kind, moneyness) columns.
OUTSIDE_FRAME_SQL = "((structure_kind = 'C' AND moneyness <= 0) OR (structure_kind = 'P' AND moneyness >= 0))"


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
    underlying_symbol: str | None = None,
    require_otm_side: bool = False,
) -> tuple[Structure | None, tuple[str, ...]]:
    """Pick the defined-risk long option closest to the target OTM strike within the tenor
    window, among eligible contracts. Returns (Structure, ()) or (None, reasons).

    ``require_otm_side`` (issue #276; callers pass ``convexity_gate.otm_side_guard``, default OFF =
    byte-identical): drop wrong-side candidates before choosing, and fail closed when only in-the-money
    contracts are eligible.

    ``underlying_symbol`` (pass it everywhere a symbol is known): contracts whose OCC root ≠
    the underlying ticker are EXCLUDED — adjusted classes carry non-standard deliverables (the
    gate/sizing math would price the wrong payoff object) and fail downstream quote lookups.
    Booked 3A/CDE2 on 2026-07-06 before this guard existed; real-book-relevant (an adjusted
    class must never reach a real order)."""
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
        if underlying_symbol and occ_root(c.symbol) != underlying_symbol.upper():
            continue  # adjusted class (root ≠ ticker) — wrong payoff object, never selectable
        dte = (c.expiry - as_of).days
        if dte < tenor_min_days or dte > tenor_max_days:
            continue
        ok, _ = eligibility(c)
        if not ok:
            continue
        cands.append((c, dte))

    if not cands:
        return None, ("no_eligible_contract_in_tenor_window",)
    if require_otm_side:
        # Issue #276 — the frozen frame (PREREG_THEMATIC_CONVEXITY) is FAR-OTM only; in-the-money is a
        # separate, unbuilt sleeve, and the skew test misfires on ITM by put-call parity. On thin chains the
        # OTM strikes can all fail eligibility while ITM ones pass, and "nearest eligible" then lands on the
        # wrong side. Keep only strictly-OTM candidates; none left → no structure (FAIL-CLOSED), never ITM.
        otm = [(c, d) for (c, d) in cands
               if (c.strike > underlying_price if kind == "C" else c.strike < underlying_price)]
        if not otm:
            return None, ("no_otm_eligible_contract_in_tenor_window",)
        cands = otm

    c, dte = min(cands, key=lambda t: (abs(t[0].strike - target_strike), abs(t[1] - tenor_mid)))
    m = mid_price(c)
    if m is None or m <= 0:
        return None, ("chosen_contract_no_mid",)
    moneyness = (c.strike - underlying_price) / underlying_price
    return Structure(direction, kind, c, dte, moneyness, m, m), ()
