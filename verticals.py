"""Wide debit call verticals for over-cap names (calibration v2 Rule V; PREREG_THEMATIC_CONVEXITY §5 amendment
2026-11-03b).

Selection (``select_vertical``), the over-cap switch every book shares (``maybe_vertical``), and the position
arithmetic the monitors share (``is_vertical`` / ``position_intrinsic`` / ``position_mid``). **Inert unless
``convexity_gate.vertical_for_over_cap.enabled`` is true.** Orders go through ``broker.submit_spread``.

Rule V (records/2026-11-03_calibration_v2_finding.md): long the gate-of-record ≈25%-OTM call, short the call nearest
+75% OTM at the same expiry — premium ≈0.71× naked, mean multiple ≈0.98× naked under jumps, p99 cut from ~10.7× to
~7×. For a name whose single naked contract exceeds the per-name cap, that is a shot the book can't otherwise take.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from convexity_gate import Contract, occ_root
from structure import DIRECTION_KIND, Structure, mid_price

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


# ── the over-cap switch (shared by the real, shadow and no-gate books) ────────────────────────────
def settings(config: dict) -> dict | None:
    """``{"short_moneyness", "min_short_moneyness"}`` when ``convexity_gate.vertical_for_over_cap.enabled`` is
    true, else None (an absent block is off, so ``frame_version`` only moves at the dated enabling edit)."""
    v = (config.get("convexity_gate") or {}).get("vertical_for_over_cap")
    if not isinstance(v, dict) or v.get("enabled") is not True:
        return None
    return {"short_moneyness": float(v.get("short_moneyness", SHORT_MONEYNESS)),
            "min_short_moneyness": float(v.get("min_short_moneyness", MIN_SHORT_MONEYNESS))}


def maybe_vertical(
    chain: list[Contract], structure: Structure, *, config: dict, direction: str, underlying_price: float | None,
    eligibility: Callable[[Contract], tuple[bool, tuple[str, ...]]], symbol: str, per_name_cap: float,
) -> tuple[Vertical | None, str | None]:
    """The vertical to use instead of ``structure``, or (None, why-not). None with a None reason means "not
    applicable" (off, bearish, or the naked contract fits): the caller proceeds with the naked structure."""
    cfg = settings(config)
    if cfg is None or DIRECTION_KIND.get(direction) != "C":
        return None, None
    if structure.entry_premium * 100.0 <= per_name_cap:
        return None, None
    v, why = select_vertical(chain, structure, underlying_price=underlying_price, eligibility=eligibility,
                             underlying_symbol=symbol, short_moneyness=cfg["short_moneyness"],
                             min_short_moneyness=cfg["min_short_moneyness"])
    return v, (None if v is not None else (why[0] if why else "no_vertical"))


# ── position arithmetic (a row with a short leg is a vertical) ────────────────────────────────────
def _get(row, key):
    try:
        return row[key]
    except (KeyError, IndexError):
        return None


def is_vertical(row) -> bool:
    return bool(_get(row, "short_contract_symbol"))


def position_intrinsic(row, underlying_price: float | None) -> float:
    """Per-share value at expiry: long call intrinsic minus short call intrinsic (0 without a price)."""
    if not underlying_price:
        return 0.0
    long_v = max(0.0, underlying_price - float(row["strike"]))
    short_v = max(0.0, underlying_price - float(row["short_strike"]))
    return max(0.0, long_v - short_v)


def position_mid(row, quote_provider) -> float | None:
    """Per-share spread mark: long mid − short mid (floored at 0), or None when either leg is unquoted."""
    lm = quote_provider.option_mid(row["contract_symbol"])
    sm = quote_provider.option_mid(row["short_contract_symbol"])
    if lm is None or sm is None:
        return None
    return max(0.0, float(lm) - float(sm))


def walk_limit(v: Vertical, fraction: float) -> float:
    """A carry attempt's net debit: mid + fraction × (natural − mid), natural = long ask − short bid."""
    mid = v.net_debit
    la, sb = v.long.contract.ask, v.short.bid
    if la is None or sb is None:
        return round(mid, 2)
    natural = la - sb
    if natural <= mid:
        return round(mid, 2)
    return round(min(mid + min(max(fraction, 0.0), 1.0) * (natural - mid), natural), 2)
