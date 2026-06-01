"""FSSD Stage-1 gross-CAR gate (PREREG §6 / FREEZE-B) — the first real edge measurement.

This module **computes CAR** (cumulative abnormal return), so the first run is **k=1** under the
pre-registered Bonferroni discipline (PREREG §14). It is the *gross-stock* gate: forward
CAR = raw − β·SPY over the primary horizon (h=10td), for the **top friction decile**, as a
**calendar-month series**, with a block-bootstrap CI at α = 0.05/k that must **exclude 0 AND be
negative** (the bearish pre-commitment). Magnitude bands apply to |net mean CAR| net of a
stock-level cost stub only — the *option* borrow cost is Stage-2, not here.

No-lookahead choices baked in:
  - **Trailing deciles (PREREG §5):** an event's friction decile is its rank within a *trailing*
    window of prior events (z-scored on trailing stats only) — never the full-sample
    cross-section, which would leak later events into an earlier event's decile.
  - The CAR forward window is a *label* (it sees t→t+h by design; it is never a feature).

Pure functions only (no I/O / no market client) so the statistics are unit-tested offline; the
networked funnel + CAR/beta reads live in ``scripts/fssd_audit.py``. Reuses the period
block-bootstrap from :mod:`backtest.metrics` (the same machinery the divergence gate used).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import numpy as np

from backtest.metrics import block_bootstrap_ci
from friction import FRICTION_INPUTS


# ── CAR primitive ────────────────────────────────────────────────────────────
def forward_car(stock_fwd: float | None, spy_fwd: float | None, beta: float | None) -> float | None:
    """Abnormal return = stock forward return − β·benchmark forward return. None if any input
    is missing (the event is then dropped — never imputed into a return)."""
    if stock_fwd is None or spy_fwd is None or beta is None:
        return None
    return stock_fwd - beta * spy_fwd


# ── trailing-decile friction assignment (no full-sample lookahead) ───────────
def _ref_stats(events: list[dict[str, Any]]) -> dict[str, tuple[float, float] | tuple[None, None]]:
    """Per-input (mean, std) over a reference (trailing) event set; (None, None) if < 2 values."""
    stats: dict[str, tuple] = {}
    for k in FRICTION_INPUTS:
        vals = [e["inputs"].get(k) for e in events if e["inputs"].get(k) is not None]
        stats[k] = (float(np.mean(vals)), float(np.std(vals))) if len(vals) >= 2 else (None, None)
    return stats


def _composite(inputs: dict[str, float | None], stats: dict, weights: dict[str, float]) -> float:
    """Weighted sum of z-scored inputs vs ``stats``; missing/degenerate inputs contribute 0
    (mean-imputed) — the same convention as :func:`friction.score_cross_section`."""
    total = 0.0
    for k in FRICTION_INPUTS:
        v = inputs.get(k)
        mean, std = stats.get(k, (None, None))
        if v is None or mean is None or std is None or std < 1e-12:
            z = 0.0
        else:
            z = (v - mean) / std
        total += weights.get(k, 1.0) * z
    return total


def assign_trailing_deciles(
    events: list[dict[str, Any]],
    *,
    weights: dict[str, float],
    trailing_days: int = 365,
    min_trailing: int = 30,
    n_deciles: int = 10,
) -> list[int | None]:
    """Assign each event a friction decile (0..n_deciles-1, highest = hardest to short) by its
    composite's rank within a **trailing window** of prior events. Returns None for events whose
    trailing window is too thin (warmup) — those are excluded from the gate. ``events`` must each
    carry ``ts`` (datetime) and ``inputs`` (a friction-input dict); order need not be sorted."""
    order = sorted(range(len(events)), key=lambda i: events[i]["ts"])
    out: list[int | None] = [None] * len(events)
    for pos, i in enumerate(order):
        e = events[i]
        lo = e["ts"] - timedelta(days=trailing_days)
        trailing = [events[order[p]] for p in range(pos) if events[order[p]]["ts"] >= lo]
        if len(trailing) < min_trailing:
            continue
        stats = _ref_stats(trailing)
        comp_e = _composite(e["inputs"], stats, weights)
        comp_tr = [_composite(t["inputs"], stats, weights) for t in trailing]
        pct = sum(1 for c in comp_tr if c <= comp_e) / len(comp_tr)
        out[i] = min(n_deciles - 1, int(pct * n_deciles))
    return out


# ── monthly CAR series + per-decile grid ─────────────────────────────────────
def monthly_mean_series(
    events: list[dict[str, Any]], *, car_key: str = "car",
    deciles: list[int | None] | None = None, only_decile: int | None = None,
) -> list[tuple[str, float]]:
    """(YYYY-MM, mean CAR) per calendar month, optionally restricted to ``only_decile``.
    Months with no usable CAR are omitted. This is the resampling unit (PREREG §6)."""
    by_month: dict[str, list[float]] = defaultdict(list)
    for idx, e in enumerate(events):
        if only_decile is not None:
            if deciles is None or deciles[idx] != only_decile:
                continue
        c = e.get(car_key)
        if c is None:
            continue
        by_month[e["ts"].strftime("%Y-%m")].append(float(c))
    return [(m, float(np.mean(v))) for m, v in sorted(by_month.items())]


def per_decile_grid(
    events: list[dict[str, Any]], deciles: list[int | None], *, car_key: str = "car",
    n_deciles: int = 10,
) -> list[dict[str, Any]]:
    """Per-decile signed-CAR + dispersion (FREEZE-B #2 grid; monotonicity is supporting, not
    gating). One row per decile with ≥1 event: {decile, n, mean_car, std_car}."""
    buckets: dict[int, list[float]] = defaultdict(list)
    for idx, e in enumerate(events):
        d = deciles[idx]
        c = e.get(car_key)
        if d is None or c is None:
            continue
        buckets[d].append(float(c))
    grid = []
    for d in range(n_deciles):
        v = buckets.get(d, [])
        if not v:
            continue
        grid.append({"decile": d, "n": len(v), "mean_car": float(np.mean(v)),
                     "std_car": float(np.std(v))})
    return grid


# ── the gate ─────────────────────────────────────────────────────────────────
@dataclass
class Stage1Result:
    n_top_events: int
    n_months: int
    mean_car: float
    ci_low: float
    ci_high: float
    ci_excludes_zero_negative: bool
    net_abs_car: float
    band: str
    verdict: str
    per_decile: list[dict[str, Any]] = field(default_factory=list)
    null_mean_car: float = float("nan")
    null_ci: tuple[float, float] = (float("nan"), float("nan"))
    null_vanishes: bool = False
    poscontrol_mean_car: float = float("nan")
    poscontrol_ci: tuple[float, float] = (float("nan"), float("nan"))
    poscontrol_alive: bool = False
    notes: list[str] = field(default_factory=list)


def _ci(series: list[float], *, alpha: float, n_iter: int, block: int) -> tuple[float, float]:
    return block_bootstrap_ci(series, alpha=alpha, n_iter=n_iter, block=block)


def evaluate_stage1(
    top_series: list[tuple[str, float]],
    *,
    k_iterations: int,
    config_fssd: dict[str, Any],
    per_decile: list[dict[str, Any]] | None = None,
    null_series: list[tuple[str, float]] | None = None,
    poscontrol_series: list[tuple[str, float]] | None = None,
) -> Stage1Result:
    """Score the top-friction-decile monthly CAR series against the FREEZE-B bands.

    Gate (PREREG §6 / FREEZE-B): the Bonferroni CI (α=0.05/k) must **exclude 0 and be negative**;
    then bands on |net mean CAR| (net of the stock-level ``cost_stub_bps``). Controls are reported
    and annotated but do not silently flip the band — a dead null / live positive control are
    *validity preconditions* surfaced as notes."""
    bands = config_fssd.get("stage1_bands", {})
    alpha = float(config_fssd.get("alpha_base", 0.05)) / max(1, int(k_iterations))
    n_iter = int(config_fssd.get("bootstrap_iters", 2000))
    block = int(config_fssd.get("block_months", 1))
    cost = float(bands.get("cost_stub_bps", 50)) / 10000.0
    fail_below = float(bands.get("car_fail_below_abs", 0.010))
    green_above = float(bands.get("car_green_above_abs", 0.025))
    require_negative = bool(bands.get("require_negative", True))

    series = [v for _, v in top_series]
    mean = float(np.mean(series)) if series else float("nan")
    lo, hi = _ci(series, alpha=alpha, n_iter=n_iter, block=block)
    excl_neg = (not np.isnan(lo) and not np.isnan(hi)) and hi < 0
    net_abs = abs(mean) - cost if not np.isnan(mean) else float("nan")

    notes: list[str] = []
    if not (require_negative and excl_neg):
        band = "FAIL"
        if not np.isnan(mean) and mean > 0:
            notes.append("top-decile mean CAR is POSITIVE — wrong sign for the bearish thesis "
                         "(squeeze corner, FREEZE-B #2); not re-fished as long.")
        else:
            notes.append("Bonferroni CI does not exclude 0 on the negative side → no edge at k.")
    elif net_abs >= green_above:
        band = "GREEN"
    elif net_abs < fail_below:
        band = "FAIL"
        notes.append(f"CI negative but |net CAR| {net_abs:.1%} < fail band {fail_below:.1%} "
                     "— statistically present, economically too small.")
    else:
        band = "YELLOW"

    # Controls (validity preconditions; reported, annotated)
    null_mean = null_lo = null_hi = float("nan")
    null_vanishes = False
    if null_series is not None:
        ns = [v for _, v in null_series]
        null_mean = float(np.mean(ns)) if ns else float("nan")
        null_lo, null_hi = _ci(ns, alpha=alpha, n_iter=n_iter, block=block)
        null_vanishes = np.isnan(null_lo) or np.isnan(null_hi) or (null_lo <= 0 <= null_hi)
        if band in ("GREEN", "YELLOW") and not null_vanishes:
            notes.append("⚠ NULL control did NOT vanish (random-date CAR also significant) → the "
                         "signal may be a friction CHARACTERISTIC, not the EVENT. Treat as suspect.")

    pos_mean = pos_lo = pos_hi = float("nan")
    pos_alive = False
    if poscontrol_series is not None:
        ps = [v for _, v in poscontrol_series]
        pos_mean = float(np.mean(ps)) if ps else float("nan")
        pos_lo, pos_hi = _ci(ps, alpha=alpha, n_iter=n_iter, block=block)
        pos_alive = (not np.isnan(pos_hi)) and pos_hi < 0  # unconditional post-offering drift ≤ 0
        if not pos_alive:
            notes.append("⚠ POSITIVE control weak (unconditional post-424B5 drift not clearly "
                         "negative) → CAR plumbing/ universe may be off; interpret with caution.")

    verdict = {"FAIL": "FAIL", "YELLOW": "YELLOW (real-but-marginal — minimal risk only)",
               "GREEN": "GREEN"}[band]
    n_months = len([v for v in series if not np.isnan(v)])
    return Stage1Result(
        n_top_events=sum(d["n"] for d in (per_decile or []) if d["decile"] == max(
            (g["decile"] for g in per_decile), default=-1)) if per_decile else 0,
        n_months=n_months, mean_car=mean, ci_low=lo, ci_high=hi,
        ci_excludes_zero_negative=excl_neg, net_abs_car=net_abs, band=band, verdict=verdict,
        per_decile=per_decile or [], null_mean_car=null_mean, null_ci=(null_lo, null_hi),
        null_vanishes=null_vanishes, poscontrol_mean_car=pos_mean, poscontrol_ci=(pos_lo, pos_hi),
        poscontrol_alive=pos_alive, notes=notes,
    )


def result_text(r: Stage1Result, *, horizon: int, k: int, alpha: float) -> str:
    lines = [
        f"  horizon={horizon}td   k={k}   α(Bonferroni)={alpha:.4f}   "
        f"top-decile months(N)={r.n_months}",
        f"  top-decile mean CAR = {r.mean_car:+.4f}   "
        f"CI[{r.ci_low:+.4f}, {r.ci_high:+.4f}]  "
        f"{'excludes 0 & negative ✓' if r.ci_excludes_zero_negative else 'spans 0 / not negative ✗'}",
        f"  |net CAR| (− cost stub) = {r.net_abs_car:+.4f}   "
        f"(FAIL<{0.010:.1%}  GREEN≥{0.025:.1%})",
        "  per-friction-decile signed CAR (FREEZE-B #2 grid; supporting, not gating):",
    ]
    for d in r.per_decile:
        lines.append(f"    decile {d['decile']}: n={d['n']:>4}  mean CAR {d['mean_car']:+.4f}  "
                     f"σ {d['std_car']:.4f}")
    lines += [
        f"  NULL control (random in-name dates): mean {r.null_mean_car:+.4f}  "
        f"CI[{r.null_ci[0]:+.4f},{r.null_ci[1]:+.4f}]  "
        f"{'vanishes ✓' if r.null_vanishes else 'PERSISTS ✗'}",
        f"  POSITIVE control (uncond. post-424B5 drift): mean {r.poscontrol_mean_car:+.4f}  "
        f"CI[{r.poscontrol_ci[0]:+.4f},{r.poscontrol_ci[1]:+.4f}]  "
        f"{'alive ✓' if r.poscontrol_alive else 'weak ✗'}",
        f"  ── BAND: {r.band}   VERDICT: {r.verdict}",
    ]
    for n in r.notes:
        lines.append(f"     · {n}")
    return "\n".join(lines)


def horizon_from_event_ts(ts: str) -> datetime:
    """ISO event ts → datetime (helper for runners assembling event panels)."""
    return datetime.fromisoformat(ts)
