"""Calibration CLI — PREREG_CONVEXITY_CALIBRATION §6.

    # Parametric Monte-Carlo (PRIMARY; offline, no creds):
    python -m calibration.run --mode mc
    python -m calibration.run --mode mc --paths 20000 --kind C

    # Historical reality-check overlay (caveated; reads the warm bars cache):
    python -m calibration.run --mode historical --names FCX,RKLB,OKLO

Writes a JSON grid + a human report under data/calibration/<timestamp>/. This is a
calibration tool — it makes NO edge claim (see the PREREG §1 three walls). NOT run in CI.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from calibration.engine import Structure, run_cell_mc  # noqa: E402
from calibration.metrics import payoff_stats  # noqa: E402

# Frozen grid axes (PREREG §4; delta/reprice + θ sweep added 2026-06-01).
MONEYNESS = [0.15, 0.25, 0.40]
TENORS = [180, 270, 365]
EXIT_RULES = ["hold", "time_stop", "profit_take", "live"]
SIGMA_MULTS = [0.8, 1.0, 1.2, 1.5]
MC_MUS = [0.0, 0.10, 0.25]
MC_SIGMAS = [0.30, 0.50, 0.80]
DELTA_THRESHOLDS = [0.4, 0.5, 0.6]   # θ_delta for the "move played out" exit
BACKSTOP_MULT = 10.0                  # live profit-take backstop (PREREG §6a, 2026-06-01)


def _banner() -> None:
    print("=" * 72)
    print("  CONVEXITY PAYOFF-MECHANICS CALIBRATION  (NOT a strategy backtest — PREREG §1)")
    print("  No edge claim. Characterizes option payoff shape to inform structure + sizing.")
    print("=" * 72)


def run_mc(args) -> dict:
    r = args.rate
    cost = args.cost_pct
    results = []
    # To keep the default run readable, sweep the structure grid at a representative
    # (μ, σ_real) and the σ_entry sweep; then a focused (μ, σ_real) surface at the live cell.
    rep_mu, rep_sigma = 0.10, 0.50
    print(f"\n## Structure grid @ μ={rep_mu:.0%}, σ_real={rep_sigma:.0%}, kind={args.kind} "
          f"(σ_entry swept) ##")
    for mny in MONEYNESS:
        for tenor in TENORS:
            for rule in EXIT_RULES:
                for smult in SIGMA_MULTS:
                    s = Structure(moneyness=mny, tenor_days=tenor, kind=args.kind,
                                  exit_rule=rule, sigma_entry_mult=smult)
                    cell = run_cell_mc(s, mu=rep_mu, sigma_real=rep_sigma, n_paths=args.paths,
                                       r=r, roundtrip_cost_pct=cost, seed=args.seed)
                    st = payoff_stats(cell)
                    results.append(_record(s, rep_mu, rep_sigma, st))
                    if rule == "live" and smult == 1.0:
                        print(f"\n[{int(mny*100)}% OTM · {tenor}d · {rule} · σ_entry={smult}×]")
                        print(st.to_text())

    print(f"\n## (μ, σ_real) surface @ live cell "
          f"(25% OTM, 270d, live exit, σ_entry=1.2×), kind={args.kind} ##")
    for mu in MC_MUS:
        for sig in MC_SIGMAS:
            s = Structure(moneyness=0.25, tenor_days=270, kind=args.kind, exit_rule="live",
                          sigma_entry_mult=1.2)
            cell = run_cell_mc(s, mu=mu, sigma_real=sig, n_paths=args.paths, r=r,
                               roundtrip_cost_pct=cost, seed=args.seed)
            st = payoff_stats(cell)
            results.append(_record(s, mu, sig, st))
            print(f"\n[μ={mu:.0%} · σ_real={sig:.0%}]")
            print(st.to_text())

    # Exit-rule head-to-head @ the live cell — the θ_delta decision surface (2026-06-01).
    # hold-the-tail vs the new reprice rule (delta primary, 10× backstop) across θ. Read with
    # the GBM-no-jumps caveat: GBM understates the OTM right tail, which flatters EARLY exits in
    # a head-to-head — so the delta cells here are an UPPER bound on how good early-exit looks.
    print(f"\n## Exit head-to-head @ 25% OTM, 270d, σ_entry=1.0×, kind={args.kind} (θ_delta sweep) ##")
    cmp_cells: list[tuple[str, str, float | None, float]] = [
        ("hold (tail)", "hold", None, 4.0),
        ("live 10× backstop", "live", None, BACKSTOP_MULT),
    ]
    for th in DELTA_THRESHOLDS:
        cmp_cells.append((f"delta@{th:g}", "delta", th, 4.0))
        cmp_cells.append((f"reprice@{th:g} (delta+10×+21DTE)", "reprice", th, BACKSTOP_MULT))
    for label, rule, th, pt in cmp_cells:
        s = Structure(moneyness=0.25, tenor_days=270, kind=args.kind, exit_rule=rule,
                      sigma_entry_mult=1.0, profit_take_mult=pt, delta_exit_threshold=th)
        cell = run_cell_mc(s, mu=rep_mu, sigma_real=rep_sigma, n_paths=args.paths, r=r,
                           roundtrip_cost_pct=cost, seed=args.seed)
        st = payoff_stats(cell)
        results.append(_record(s, rep_mu, rep_sigma, st))
        print(f"\n[{label}]")
        print(st.to_text())

    return {"mode": "mc", "kind": args.kind, "paths": args.paths, "rate": r,
            "cost_pct": cost, "cells": results}


def _record(s: Structure, mu, sigma_real, st) -> dict:
    return {
        "moneyness": s.moneyness, "tenor_days": s.tenor_days, "kind": s.kind,
        "exit_rule": s.exit_rule, "sigma_entry_mult": s.sigma_entry_mult,
        "profit_take_mult": s.profit_take_mult, "delta_exit_threshold": s.delta_exit_threshold,
        "mu": mu, "sigma_real": sigma_real,
        "n": st.n, "entry_premium": st.entry_premium, "mean_multiple": st.mean_multiple,
        "median_multiple": st.median_multiple, "p_total_loss": st.p_total_loss,
        "quantiles": st.quantiles, "premium_bled_frac": st.premium_bled_frac,
        "convexity_ratio": st.convexity_ratio, "breakeven_hit_rate": st.breakeven_hit_rate,
        "exit_mix": st.exit_mix,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Convexity payoff-mechanics calibration (no edge claim)")
    p.add_argument("--mode", choices=["mc", "historical"], default="mc")
    p.add_argument("--kind", choices=["C", "P"], default="C")
    p.add_argument("--paths", type=int, default=5000, help="MC paths per cell")
    p.add_argument("--rate", type=float, default=0.04, help="risk-free rate")
    p.add_argument("--cost-pct", type=float, default=0.05, help="round-trip cost as %% of entry premium")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--names", default="", help="historical mode: comma-separated symbols")
    args = p.parse_args(argv)

    _banner()
    if args.mode == "historical":
        print("\nHistorical mode is a caveated overlay (≤3.5y IEX window, overlapping, one "
              "regime — PREREG §2). Build it with --names; not implemented in this entry yet.")
        print("Run the PRIMARY parametric tool: python -m calibration.run --mode mc")
        return 2

    out = run_mc(args)
    out_dir = Path("data/calibration") / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "calibration.json").write_text(json.dumps(out, indent=2, default=str))
    print(f"\nArtifacts → {out_dir}")
    print("\nReminder: payoff SHAPE only. A good shape is NOT evidence the strategy makes "
          "money — only that IF judgment has edge, this structure expresses it (PREREG §5).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
