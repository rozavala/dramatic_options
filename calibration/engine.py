"""Calibration sweep engine — PREREG_CONVEXITY_CALIBRATION §4.

Given a structure cell (moneyness, tenor, exit rule, entry-IV multiple) and a source of
underlying price PATHS (parametric GBM in Mode A, or historical bar windows in Mode B), it
simulates each entry → exit and returns the option-return **multiple** per path:

    multiple = (exit_value_per_share − roundtrip_cost) / entry_premium − 1   ... no:
    multiple = net_exit_value / entry_premium                                (gross-of-entry)

We report the *multiple of premium returned* M = exit_value / entry_premium (so M=0 ⇒ total
loss, M=1 ⇒ break-even before cost, M=5 ⇒ 5×). Costs are a round-trip stub subtracted from
the exit value. Pure given its path source (no I/O here).

The exits mirror the live §6a rules so one grid cell == the live structure:
  - hold       : value at expiry = intrinsic
  - time_stop  : close (re-price) when ≤ time_stop_dte days remain
  - profit_take: close when mark ≥ profit_take_mult × entry premium
  - live       : profit_take OR time_stop, else expiry  (the live combined rule)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from calibration.pricing import bs_price, intrinsic_value, simulate_gbm_path


@dataclass(frozen=True)
class Structure:
    moneyness: float        # OTM fraction (0.25 = 25% OTM)
    tenor_days: int
    kind: str               # "C" | "P"
    exit_rule: str          # hold | time_stop | profit_take | live
    sigma_entry_mult: float  # σ_entry = mult × σ_real
    profit_take_mult: float = 4.0
    time_stop_dte: int = 21


@dataclass
class CellResult:
    structure: Structure
    mu: float | None
    sigma_real: float | None
    n: int
    entry_premium: float            # per-share, representative (mean over paths)
    multiples: np.ndarray = field(repr=False)  # exit_value / entry_premium per path
    underlying_returns: np.ndarray = field(repr=False)  # terminal underlying return per path
    exit_reasons: list[str] = field(default_factory=list, repr=False)


def _strike(spot: float, moneyness: float, kind: str) -> float:
    return spot * (1 + moneyness) if kind == "C" else spot * (1 - moneyness)


def simulate_option_on_path(
    path: np.ndarray, *, structure: Structure, r: float, sigma_entry: float,
    roundtrip_cost_pct: float, steps_per_year: int = 252,
) -> tuple[float, float, str]:
    """Return (multiple, underlying_terminal_return, exit_reason) for one price path.

    ``path[0]`` is entry spot; the option is priced at entry with ``sigma_entry``; the path is
    walked day-by-day applying the structure's exit rule. ``multiple`` = net exit value /
    entry premium.
    """
    spot0 = float(path[0])
    strike = _strike(spot0, structure.moneyness, structure.kind)
    t0 = structure.tenor_days / 365.0
    entry = bs_price(spot=spot0, strike=strike, t_years=t0, r=r, sigma=sigma_entry, kind=structure.kind)
    if entry <= 0:
        # Degenerate (deep-OTM at ~0 vol) — unpriceable; skip by returning a sentinel.
        return (float("nan"), float(path[-1] / spot0 - 1.0), "unpriceable")

    n_steps = len(path) - 1
    cost = roundtrip_cost_pct * entry
    profit_target = structure.profit_take_mult * entry
    rule = structure.exit_rule

    for i in range(1, n_steps + 1):
        spot = float(path[i])
        days_elapsed = i * 365.0 / steps_per_year
        dte = structure.tenor_days - days_elapsed
        t_rem = max(0.0, dte / 365.0)
        # mark mid-life via BS at the held entry vol (PREREG §3 simplification)
        mark = bs_price(spot=spot, strike=strike, t_years=t_rem, r=r, sigma=sigma_entry, kind=structure.kind)

        if rule in ("profit_take", "live") and mark >= profit_target:
            return ((mark - cost) / entry, spot / spot0 - 1.0, "profit_take")
        if rule in ("time_stop", "live") and dte <= structure.time_stop_dte:
            return ((mark - cost) / entry, spot / spot0 - 1.0, "time_stop")

    # held to expiry → intrinsic
    spot_T = float(path[-1])
    intr = intrinsic_value(spot=spot_T, strike=strike, kind=structure.kind)
    net = intr - (cost if intr > 0 else 0.0)  # no exit cost on a worthless expiry
    return (max(0.0, net) / entry, spot_T / spot0 - 1.0, "expiry")


def run_cell_mc(
    structure: Structure, *, mu: float, sigma_real: float, n_paths: int, r: float,
    roundtrip_cost_pct: float, spot: float = 100.0, seed: int = 7, steps_per_year: int = 252,
) -> CellResult:
    """Monte-Carlo a structure cell over ``n_paths`` GBM paths (Mode A)."""
    rng = np.random.default_rng(seed)
    sigma_entry = structure.sigma_entry_mult * sigma_real
    mults, urets, reasons = [], [], []
    entries = []
    for _ in range(n_paths):
        path = simulate_gbm_path(spot=spot, mu=mu, sigma=sigma_real, days=structure.tenor_days,
                                 rng=rng, steps_per_year=steps_per_year)
        m, ur, why = simulate_option_on_path(
            path, structure=structure, r=r, sigma_entry=sigma_entry,
            roundtrip_cost_pct=roundtrip_cost_pct, steps_per_year=steps_per_year)
        if why == "unpriceable":
            continue
        mults.append(m)
        urets.append(ur)
        reasons.append(why)
        entries.append(bs_price(spot=spot, strike=_strike(spot, structure.moneyness, structure.kind),
                                t_years=structure.tenor_days / 365.0, r=r, sigma=sigma_entry,
                                kind=structure.kind))
    return CellResult(
        structure=structure, mu=mu, sigma_real=sigma_real, n=len(mults),
        entry_premium=float(np.mean(entries)) if entries else 0.0,
        multiples=np.array(mults), underlying_returns=np.array(urets), exit_reasons=reasons,
    )


def run_cell_historical(
    structure: Structure, *, paths: list[np.ndarray], sigma_real_of, r: float,
    roundtrip_cost_pct: float,
) -> CellResult:
    """Replay a structure cell over historical bar windows (Mode B — caveated overlay).

    ``paths``: list of price arrays (each ``path[0]`` = entry). ``sigma_real_of(path)`` →
    the trailing realized vol used both as σ_real and (× mult) as σ_entry for that entry.
    Entries are mechanical (caller builds them on a schedule); NO outcome selection here.
    """
    mults, urets, reasons, entries = [], [], [], []
    for path in paths:
        sigma_real = sigma_real_of(path)
        if sigma_real is None or sigma_real <= 0:
            continue
        sigma_entry = structure.sigma_entry_mult * sigma_real
        m, ur, why = simulate_option_on_path(
            path, structure=structure, r=r, sigma_entry=sigma_entry,
            roundtrip_cost_pct=roundtrip_cost_pct)
        if why == "unpriceable":
            continue
        spot0 = float(path[0])
        mults.append(m)
        urets.append(ur)
        reasons.append(why)
        entries.append(bs_price(spot=spot0, strike=_strike(spot0, structure.moneyness, structure.kind),
                                t_years=structure.tenor_days / 365.0, r=r, sigma=sigma_entry,
                                kind=structure.kind))
    return CellResult(
        structure=structure, mu=None, sigma_real=None, n=len(mults),
        entry_premium=float(np.mean(entries)) if entries else 0.0,
        multiples=np.array(mults), underlying_returns=np.array(urets), exit_reasons=reasons,
    )
