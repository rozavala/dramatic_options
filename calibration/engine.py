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
  - live       : profit_take OR time_stop, else expiry  (the OLD venture combined rule)
  - delta      : close when |delta| ≥ delta_exit_threshold (the "move played out"), else expiry
  - reprice    : delta OR profit_take(backstop) OR time_stop, else expiry  (the NEW OTM rule,
                 2026-06-01 amendment — delta is primary, 10× profit-take is a backstop)

Calibration v2 (PREREG §4 amendment 2026-11-03) adds three orthogonal overlays on any exit rule:
  - salvage           : sell at the mark on the falsifier day when the falsifier fires
  - roll_trigger_mult : at mark ≥ R× entry, bank 1× entry as cash and roll the rest into a new
                        25%-OTM call from the current spot, same expiry (naked calls only, one roll)
  - short_moneyness   : a vertical — the short leg at that OTM fraction, priced at σ_entry + skew
and two path sources for Monte-Carlo: Merton jumps (``JumpModel``) and thesis-state drift with a
falsifier read (``ThesisModel``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from calibration.pricing import (
    bs_delta,
    bs_price,
    intrinsic_value,
    simulate_gbm_path,
    simulate_merton_path,
)


@dataclass(frozen=True)
class Structure:
    moneyness: float        # OTM fraction (0.25 = 25% OTM)
    tenor_days: int
    kind: str               # "C" | "P"
    exit_rule: str          # hold | time_stop | profit_take | live | delta | reprice
    sigma_entry_mult: float  # σ_entry = mult × σ_real
    profit_take_mult: float = 4.0
    time_stop_dte: int = 21
    delta_exit_threshold: float | None = None  # close when |delta| ≥ this (the "move played out")
    # v2 overlays (2026-11-03); the defaults leave every v1 cell unchanged.
    salvage: bool = False                       # sell on the falsifier day if the falsifier fires
    roll_trigger_mult: float | None = None      # house-money roll at mark ≥ R× entry
    roll_moneyness: float = 0.25                # the rolled leg's OTM fraction from the roll-day spot
    short_moneyness: float | None = None        # vertical: short leg OTM fraction (None = naked)
    short_skew_volpts: float = 0.0              # short leg priced at σ_entry + this/100


@dataclass(frozen=True)
class JumpModel:
    """Merton jumps: Poisson ``lam`` per year, log-jump N(0, ``sigma_j``); total variance held at σ_real²."""
    lam: float = 2.0
    sigma_j: float = 0.20


@dataclass(frozen=True)
class ThesisModel:
    """Thesis state per path: right w.p. ``p_right`` (drift ``mu_right``) else wrong (``mu_wrong``).

    A falsifier is read on calendar day ``falsifier_day`` and fires w.p. ``accuracy`` when wrong and
    ``1 − accuracy`` when right (a false alarm).
    """
    p_right: float
    mu_right: float
    mu_wrong: float = -0.10
    falsifier_day: int = 90
    accuracy: float = 0.7


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
    thesis_right: np.ndarray | None = field(default=None, repr=False)  # per path, ThesisModel cells only


def _strike(spot: float, moneyness: float, kind: str) -> float:
    return spot * (1 + moneyness) if kind == "C" else spot * (1 - moneyness)


def simulate_option_on_path(
    path: np.ndarray, *, structure: Structure, r: float, sigma_entry: float,
    roundtrip_cost_pct: float, steps_per_year: int = 252, falsifier_step: int | None = None,
) -> tuple[float, float, str]:
    """Return (multiple, underlying_terminal_return, exit_reason) for one price path.

    ``path[0]`` is entry spot; the option is priced at entry with ``sigma_entry``; the path is
    walked day-by-day applying the structure's exit rule. ``multiple`` = net exit value /
    entry premium. ``falsifier_step`` is the path index on which a FIRED falsifier is read
    (None = it never fires); it matters only when ``structure.salvage``.
    """
    spot0 = float(path[0])
    kind = structure.kind
    strike = _strike(spot0, structure.moneyness, kind)
    short_strike = (None if structure.short_moneyness is None
                    else _strike(spot0, structure.short_moneyness, kind))
    sigma_short = sigma_entry + structure.short_skew_volpts / 100.0
    if short_strike is not None and structure.roll_trigger_mult is not None:
        raise ValueError("a roll is defined for a naked leg only")

    def leg_value(spot: float, t_rem: float, k: float) -> float:
        v = bs_price(spot=spot, strike=k, t_years=t_rem, r=r, sigma=sigma_entry, kind=kind)
        if short_strike is not None and k == strike:
            v -= bs_price(spot=spot, strike=short_strike, t_years=t_rem, r=r, sigma=sigma_short, kind=kind)
        return v

    t0 = structure.tenor_days / 365.0
    entry = leg_value(spot0, t0, strike)
    if entry <= 0:
        # Degenerate (deep-OTM at ~0 vol) — unpriceable; skip by returning a sentinel.
        return (float("nan"), float(path[-1] / spot0 - 1.0), "unpriceable")

    n_steps = len(path) - 1
    profit_target = structure.profit_take_mult * entry
    rule = structure.exit_rule
    # Position state: cash banked by a roll + `qty` units of the leg struck at `leg_k`, whose own
    # close cost is `leg_cost`. Before any roll: qty 1, the entry leg, cost = pct × entry (v1 exactly).
    banked, qty, leg_k = 0.0, 1.0, strike
    leg_cost = roundtrip_cost_pct * entry
    rolled = False

    def close(total_mark: float, spot: float, why: str) -> tuple[float, float, str]:
        return ((total_mark - leg_cost) / entry, spot / spot0 - 1.0, why)

    for i in range(1, n_steps + 1):
        spot = float(path[i])
        days_elapsed = i * 365.0 / steps_per_year
        dte = structure.tenor_days - days_elapsed
        t_rem = max(0.0, dte / 365.0)
        # mark mid-life via BS at the held entry vol (PREREG §3 simplification)
        leg_mark = leg_value(spot, t_rem, leg_k)
        mark = banked + qty * leg_mark

        if structure.salvage and falsifier_step is not None and i == falsifier_step:
            return close(mark, spot, "salvage")

        # House-money roll (v2): bank the original stake, re-strike the rest from today's spot.
        if (structure.roll_trigger_mult is not None and not rolled and t_rem > 0
                and mark >= structure.roll_trigger_mult * entry):
            proceeds = mark - leg_cost
            reinvest = proceeds - entry
            new_k = _strike(spot, structure.roll_moneyness, kind)
            new_px = bs_price(spot=spot, strike=new_k, t_years=t_rem, r=r, sigma=sigma_entry, kind=kind)
            if reinvest > 0 and new_px > 0:
                banked, qty, leg_k = entry, reinvest / new_px, new_k
                leg_cost = roundtrip_cost_pct * reinvest
                rolled = True
                continue

        # Delta trigger (primary "take it" for the reprice rule): the far-OTM convexity has
        # converted into delta = the anticipated spot move played out. Banks it AFTER the move.
        if rule in ("delta", "reprice") and structure.delta_exit_threshold is not None:
            delta = bs_delta(spot=spot, strike=leg_k, t_years=t_rem, r=r, sigma=sigma_entry, kind=kind)
            if abs(delta) >= structure.delta_exit_threshold:
                return close(mark, spot, "delta")
        if rule in ("profit_take", "live", "reprice") and mark >= profit_target:
            return close(mark, spot, "profit_take")
        if rule in ("time_stop", "live", "reprice") and dte <= structure.time_stop_dte:
            return close(mark, spot, "time_stop")

    # held to expiry → intrinsic
    spot_T = float(path[-1])
    intr = intrinsic_value(spot=spot_T, strike=leg_k, kind=kind)
    if short_strike is not None:
        intr -= intrinsic_value(spot=spot_T, strike=short_strike, kind=kind)
    leg_payoff = qty * intr
    net = banked + leg_payoff - (leg_cost if leg_payoff > 0 else 0.0)  # no exit cost on a worthless expiry
    return (max(0.0, net) / entry, spot_T / spot0 - 1.0, "expiry")


def run_cell_mc(
    structure: Structure, *, mu: float, sigma_real: float, n_paths: int, r: float,
    roundtrip_cost_pct: float, spot: float = 100.0, seed: int = 7, steps_per_year: int = 252,
    jumps: JumpModel | None = None, thesis: ThesisModel | None = None,
) -> CellResult:
    """Monte-Carlo a structure cell over ``n_paths`` paths (Mode A).

    GBM by default; Merton jumps with ``jumps``. With ``thesis`` each path first draws its state
    (drift μ_right or μ_wrong — ``mu`` is then unused) and its falsifier outcome. Random draws never
    depend on the structure, so two structures on the same seed see identical paths (paired cells).
    """
    rng = np.random.default_rng(seed)
    sigma_entry = structure.sigma_entry_mult * sigma_real
    mults, urets, reasons, rights = [], [], [], []
    entries = []
    for _ in range(n_paths):
        path_mu, fstep, right = mu, None, None
        if thesis is not None:
            right = bool(rng.random() < thesis.p_right)
            path_mu = thesis.mu_right if right else thesis.mu_wrong
            fires = bool(rng.random() < (1.0 - thesis.accuracy if right else thesis.accuracy))
            if fires:
                fstep = max(1, int(round(thesis.falsifier_day * steps_per_year / 365.0)))
        if jumps is None:
            path = simulate_gbm_path(spot=spot, mu=path_mu, sigma=sigma_real, days=structure.tenor_days,
                                     rng=rng, steps_per_year=steps_per_year)
        else:
            path = simulate_merton_path(spot=spot, mu=path_mu, sigma=sigma_real, days=structure.tenor_days,
                                        rng=rng, jump_lambda=jumps.lam, jump_sigma=jumps.sigma_j,
                                        steps_per_year=steps_per_year)
        m, ur, why = simulate_option_on_path(
            path, structure=structure, r=r, sigma_entry=sigma_entry,
            roundtrip_cost_pct=roundtrip_cost_pct, steps_per_year=steps_per_year, falsifier_step=fstep)
        if why == "unpriceable":
            continue
        mults.append(m)
        urets.append(ur)
        reasons.append(why)
        rights.append(right)
        entries.append(entry_premium(structure, spot=spot, r=r, sigma_entry=sigma_entry))
    return CellResult(
        structure=structure, mu=mu, sigma_real=sigma_real, n=len(mults),
        entry_premium=float(np.mean(entries)) if entries else 0.0,
        multiples=np.array(mults), underlying_returns=np.array(urets), exit_reasons=reasons,
        thesis_right=(np.array(rights, dtype=bool) if thesis is not None else None),
    )


def entry_premium(structure: Structure, *, spot: float, r: float, sigma_entry: float) -> float:
    """Per-share entry premium of the structure (naked leg, or long − short for a vertical)."""
    t0 = structure.tenor_days / 365.0
    long_px = bs_price(spot=spot, strike=_strike(spot, structure.moneyness, structure.kind),
                       t_years=t0, r=r, sigma=sigma_entry, kind=structure.kind)
    if structure.short_moneyness is None:
        return long_px
    short_px = bs_price(spot=spot, strike=_strike(spot, structure.short_moneyness, structure.kind),
                        t_years=t0, r=r, sigma=sigma_entry + structure.short_skew_volpts / 100.0,
                        kind=structure.kind)
    return long_px - short_px


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
