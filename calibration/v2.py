"""Calibration v2 suite — PREREG_CONVEXITY_CALIBRATION §4 amendment 2026-11-03 (written blind).

    python -m calibration.v2                 # the frozen suite (5,000 paths per cell, seed 7)
    python -m calibration.v2 --paths 500     # a quick smoke run (NOT the record)

Runs exactly the amendment's cells and applies its five pre-stated rules (J, S, R, V, T). A rule that
passes earns only the right to DRAFT a live amendment; nothing here touches the live path. Payoff
mechanics only: no edge claim (PREREG §1).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from calibration.engine import (  # noqa: E402
    CellResult,
    JumpModel,
    Structure,
    ThesisModel,
    entry_premium,
    run_cell_mc,
)
from calibration.metrics import breakeven_hit_rate  # noqa: E402

# ── frozen settings (the amendment's "common settings") ──────────────────────────────────────
SIGMA_REAL = 0.50
MU = 0.10
COST = 0.05
RATE = 0.04
LIVE = Structure(moneyness=0.25, tenor_days=270, kind="C", exit_rule="live", sigma_entry_mult=1.0,
                 profit_take_mult=10.0, time_stop_dte=21)
PATH_MODELS: dict[str, JumpModel | None] = {"gbm": None, "jumps": JumpModel(lam=2.0, sigma_j=0.20)}
MU_RIGHT = [0.40, 0.80]
MU_WRONG = -0.10
FALSIFIER_DAYS = [90, 150]
ACCURACIES = [0.7, 0.9]
ROLL_TRIGGERS = [3.0, 5.0]
SHORT_WINGS = [0.75, 1.00]
SHORT_SKEWS = [0.0, 5.0]
TENOR_MUS = [0.0, 0.10, 0.25]


def _stats(cell: CellResult) -> dict:
    m = np.asarray(cell.multiples, dtype=float)
    return {
        "n": int(m.size),
        "entry_premium": round(cell.entry_premium, 4),
        "mean_M": round(float(m.mean()), 4),
        "median_M": round(float(np.median(m)), 4),
        "p99": round(float(np.percentile(m, 99)), 3),
        "p_M_ge_1": round(float(np.mean(m >= 1.0)), 4),
        "p_total_loss": round(float(np.mean(m <= 0.02)), 4),
        "p_star": (None if (p := breakeven_hit_rate(m)) is None else round(p, 4)),
    }


class Suite:
    def __init__(self, paths: int, seed: int) -> None:
        self.paths, self.seed = paths, seed

    def cell(self, s: Structure, *, mu: float = MU, jumps: JumpModel | None = None,
             thesis: ThesisModel | None = None) -> CellResult:
        return run_cell_mc(s, mu=mu, sigma_real=SIGMA_REAL, n_paths=self.paths, r=RATE,
                           roundtrip_cost_pct=COST, seed=self.seed, jumps=jumps, thesis=thesis)

    # Rule J — does the June exit ranking survive jumps?
    def rule_j(self) -> dict:
        cells = {
            "hold": replace(LIVE, exit_rule="hold"),
            "live_10x": LIVE,
            "delta_0.5": replace(LIVE, exit_rule="delta", profit_take_mult=4.0, delta_exit_threshold=0.5),
        }
        out = {pm: {k: _stats(self.cell(s, jumps=j)) for k, s in cells.items()} for pm, j in PATH_MODELS.items()}
        reopened = out["jumps"]["delta_0.5"]["mean_M"] > out["jumps"]["hold"]["mean_M"]
        return {"cells": out, "verdict": "REOPENED" if reopened else "CONFIRMED"}

    # Rule S — falsifier salvage under thesis-state paths.
    def rule_s(self) -> dict:
        rows = []
        for pm, j in PATH_MODELS.items():
            for mu_r in MU_RIGHT:
                for d_f in FALSIFIER_DAYS:
                    for acc in ACCURACIES:
                        row = {"path_model": pm, "mu_right": mu_r, "falsifier_day": d_f, "accuracy": acc}
                        for label, s in (("hold", LIVE), ("salvage", replace(LIVE, salvage=True))):
                            st = {}
                            for state, p in (("right", 1.0), ("wrong", 0.0)):
                                th = ThesisModel(p_right=p, mu_right=mu_r, mu_wrong=MU_WRONG,
                                                 falsifier_day=d_f, accuracy=acc)
                                st[state] = _stats(self.cell(s, jumps=j, thesis=th))
                            e_r, e_w = st["right"]["mean_M"], st["wrong"]["mean_M"]
                            p_star = (1.0 - e_w) / (e_r - e_w) if e_r > e_w else None
                            row[label] = {"E_right": e_r, "E_wrong": e_w, "p99_right": st["right"]["p99"],
                                          "p_star": None if p_star is None else round(p_star, 4)}
                        rows.append(row)

        def ok(r: dict) -> bool:
            h, s = r["hold"], r["salvage"]
            return (s["p_star"] is not None and h["p_star"] is not None and s["p_star"] < h["p_star"]
                    and s["E_right"] >= 0.85 * h["E_right"])

        corner = [r for r in rows if r["accuracy"] == 0.7 and r["falsifier_day"] == 90]
        return {"rows": rows, "corner_pass": [ok(r) for r in corner],
                "verdict": "CANDIDATE" if corner and all(ok(r) for r in corner) else "NOT A CANDIDATE"}

    # Rule R — house-money roll.
    def rule_r(self) -> dict:
        out: dict = {}
        verdicts = {}
        for trig in ROLL_TRIGGERS:
            passes = []
            for pm, j in PATH_MODELS.items():
                base = _stats(self.cell(LIVE, jumps=j))
                roll = _stats(self.cell(replace(LIVE, roll_trigger_mult=trig), jumps=j))
                ok = (roll["mean_M"] >= 0.95 * base["mean_M"]
                      and roll["p_M_ge_1"] >= base["p_M_ge_1"] + 0.03)
                passes.append(ok)
                out[f"R{trig:g}_{pm}"] = {"live": base, "roll": roll, "pass": ok}
            verdicts[f"R{trig:g}"] = "CANDIDATE" if all(passes) else "NOT A CANDIDATE"
        return {"cells": out, "verdict": verdicts}

    # Rule V — wide call vertical for over-cap names.
    def rule_v(self) -> dict:
        out: dict = {}
        candidate = False
        for pm, j in PATH_MODELS.items():
            naked = _stats(self.cell(LIVE, jumps=j))
            out[f"naked_{pm}"] = naked
            for k2 in SHORT_WINGS:
                for skew in SHORT_SKEWS:
                    s = replace(LIVE, short_moneyness=k2, short_skew_volpts=skew)
                    st = _stats(self.cell(s, jumps=j))
                    st["premium_ratio"] = round(st["entry_premium"] / naked["entry_premium"], 4)
                    st["mean_ratio"] = round(st["mean_M"] / naked["mean_M"], 4)
                    out[f"K{k2:g}_s{skew:g}_{pm}"] = st
                    if pm == "jumps" and skew == 0.0 and st["premium_ratio"] <= 0.75 and st["mean_ratio"] >= 0.85:
                        candidate = True
        return {"cells": out, "verdict": "CANDIDATE" if candidate else "NOT A CANDIDATE"}

    # Rule T — 540-day tenor vs 365.
    def rule_t(self) -> dict:
        out: dict = {}
        passes = []
        for pm, j in PATH_MODELS.items():
            for mu in TENOR_MUS:
                a = _stats(self.cell(replace(LIVE, tenor_days=365), mu=mu, jumps=j))
                b = _stats(self.cell(replace(LIVE, tenor_days=540), mu=mu, jumps=j))
                prem_365 = entry_premium(replace(LIVE, tenor_days=365), spot=100.0, r=RATE, sigma_entry=SIGMA_REAL)
                prem_540 = entry_premium(replace(LIVE, tenor_days=540), spot=100.0, r=RATE, sigma_entry=SIGMA_REAL)
                ok = (b["mean_M"] >= a["mean_M"] and a["p_star"] is not None and b["p_star"] is not None
                      and b["p_star"] <= a["p_star"])
                passes.append(ok)
                out[f"mu{mu:g}_{pm}"] = {
                    "t365": a, "t540": b, "pass": ok,
                    "premium_ratio": round(prem_540 / prem_365, 4),
                    "premium_per_day": {"t365": round(prem_365 / 365, 5), "t540": round(prem_540 / 540, 5)},
                }
        return {"cells": out, "verdict": "CANDIDATE" if all(passes) else "NOT A CANDIDATE"}


def _report(res: dict) -> str:
    L = [f"# Calibration v2 — {res['ran_at']} ({res['paths']} paths/cell, seed {res['seed']})", "",
         "Payoff mechanics only (PREREG §1): no edge claim. A CANDIDATE earns a DRAFT, never a change.", ""]
    j = res["J"]
    L += [f"## Rule J (exit ranking under jumps): **{j['verdict']}**", "",
          "| path | rule | mean M | median | p99 | P(M≥1) | P(loss) | p* |", "|---|---|---|---|---|---|---|---|"]
    for pm, cells in j["cells"].items():
        for k, st in cells.items():
            L.append(f"| {pm} | {k} | {st['mean_M']:.2f} | {st['median_M']:.2f} | {st['p99']:.1f} | "
                     f"{st['p_M_ge_1']:.0%} | {st['p_total_loss']:.0%} | {st['p_star']} |")
    s = res["S"]
    L += ["", f"## Rule S (falsifier salvage): **{s['verdict']}** (corner a=0.7, d_f=90: {s['corner_pass']})", "",
          "| path | μ_right | d_f | a | hold E_r | hold E_w | hold p* | salv E_r | salv E_w | salv p* | p99_r hold→salv |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in s["rows"]:
        h, v = r["hold"], r["salvage"]
        L.append(f"| {r['path_model']} | {r['mu_right']:.0%} | {r['falsifier_day']} | {r['accuracy']} | "
                 f"{h['E_right']:.2f} | {h['E_wrong']:.3f} | {h['p_star']} | {v['E_right']:.2f} | "
                 f"{v['E_wrong']:.3f} | {v['p_star']} | {h['p99_right']:.1f}→{v['p99_right']:.1f} |")
    rr = res["R"]
    L += ["", f"## Rule R (house-money roll): **{rr['verdict']}**", "",
          "| cell | live mean M | roll mean M | live P(M≥1) | roll P(M≥1) | live p99 | roll p99 | pass |",
          "|---|---|---|---|---|---|---|---|"]
    for k, c in rr["cells"].items():
        a, b = c["live"], c["roll"]
        L.append(f"| {k} | {a['mean_M']:.2f} | {b['mean_M']:.2f} | {a['p_M_ge_1']:.1%} | {b['p_M_ge_1']:.1%} | "
                 f"{a['p99']:.1f} | {b['p99']:.1f} | {c['pass']} |")
    v = res["V"]
    L += ["", f"## Rule V (wide vertical): **{v['verdict']}**", "",
          "| cell | premium ratio | mean M | mean ratio | p99 | P(M≥1) |", "|---|---|---|---|---|---|"]
    for k, st in v["cells"].items():
        L.append(f"| {k} | {st.get('premium_ratio', 1.0)} | {st['mean_M']:.2f} | {st.get('mean_ratio', 1.0)} | "
                 f"{st['p99']:.1f} | {st['p_M_ge_1']:.1%} |")
    t = res["T"]
    L += ["", f"## Rule T (540 d vs 365 d): **{t['verdict']}**", "",
          "| cell | 365 mean M | 540 mean M | 365 p* | 540 p* | premium ratio | pass |", "|---|---|---|---|---|---|---|"]
    for k, c in t["cells"].items():
        L.append(f"| {k} | {c['t365']['mean_M']:.2f} | {c['t540']['mean_M']:.2f} | {c['t365']['p_star']} | "
                 f"{c['t540']['p_star']} | {c['premium_ratio']} | {c['pass']} |")
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Calibration v2 suite (no edge claim)")
    p.add_argument("--paths", type=int, default=5000)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--out", default="data/calibration")
    args = p.parse_args(argv)
    suite = Suite(args.paths, args.seed)
    res = {"ran_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ"), "paths": args.paths, "seed": args.seed}
    for name in ("J", "S", "R", "V", "T"):
        res[name] = getattr(suite, f"rule_{name.lower()}")()
        print(f"rule {name}: {res[name]['verdict']}", flush=True)
    out_dir = Path(args.out) / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "calibration_v2.json").write_text(json.dumps(res, indent=2, default=str))
    (out_dir / "calibration_v2.md").write_text(_report(res))
    print(f"Artifacts → {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
