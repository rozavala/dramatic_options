"""Calibration metrics — PREREG_CONVEXITY_CALIBRATION §5 (calibration, NOT a gate).

Pure functions over a ``CellResult``'s option-return multiples (M = exit_value / entry
premium; M=0 ⇒ total loss, the venture floor). NO edge claim — these characterize the payoff
*shape* to inform structure + sizing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from calibration.engine import CellResult


@dataclass
class PayoffStats:
    n: int
    entry_premium: float
    mean_multiple: float
    median_multiple: float
    p_total_loss: float            # P(M ≈ 0) — "most expire worthless"
    quantiles: dict[str, float]    # p50/p75/p90/p95/p99 of M
    premium_bled_frac: float       # total premium lost / total premium deployed
    convexity_ratio: float         # mean right-tail multiple ÷ |bounded downside (1)|
    breakeven_hit_rate: float | None  # p* — see breakeven_hit_rate()
    transfer_curve: list[tuple[str, float]] = field(default_factory=list)
    exit_mix: dict[str, float] = field(default_factory=dict)

    def to_text(self) -> str:
        q = self.quantiles
        be = "n/a" if self.breakeven_hit_rate is None else f"{self.breakeven_hit_rate:.0%}"
        exit_mix = "  ".join(f"{k}={v:.0%}" for k, v in sorted(self.exit_mix.items()))
        lines = [
            f"  n={self.n}  entry_premium/sh=${self.entry_premium:.2f}",
            f"  mean M={self.mean_multiple:.2f}x  median M={self.median_multiple:.2f}x  "
            f"P(total loss)={self.p_total_loss:.0%}",
            f"  quantiles: p50={q.get('p50', 0):.2f}x p75={q.get('p75', 0):.2f}x "
            f"p90={q.get('p90', 0):.2f}x p95={q.get('p95', 0):.2f}x p99={q.get('p99', 0):.2f}x",
            f"  premium bled={self.premium_bled_frac:.0%}  convexity ratio={self.convexity_ratio:.1f}",
            f"  break-even hit-rate p*={be}",
            f"  exit mix: {exit_mix}",
        ]
        if self.transfer_curve:
            lines.append("  payoff transfer (underlying-return bucket -> median M):")
            for bucket, med in self.transfer_curve:
                lines.append(f"    {bucket:>12s}: {med:.2f}x")
        return "\n".join(lines)


_TOTAL_LOSS_EPS = 0.02  # M ≤ 2% of premium counts as "worthless"


def payoff_stats(cell: CellResult) -> PayoffStats:
    m = np.asarray(cell.multiples, dtype=float)
    if m.size == 0:
        return PayoffStats(0, cell.entry_premium, 0, 0, 0, {}, 0, 0, None)
    quant = {f"p{int(p)}": float(np.percentile(m, p)) for p in (50, 75, 90, 95, 99)}
    p_total_loss = float(np.mean(m <= _TOTAL_LOSS_EPS))
    # premium bled: each path deploys 1 unit of premium; loss per path = max(0, 1 − M).
    premium_bled = float(np.mean(np.clip(1.0 - m, 0.0, 1.0)))
    # convexity: mean of the winning tail (M>1) vs the bounded downside of 1 unit.
    winners = m[m > 1.0]
    convexity = float(winners.mean()) if winners.size else 0.0
    return PayoffStats(
        n=int(m.size),
        entry_premium=cell.entry_premium,
        mean_multiple=float(m.mean()),
        median_multiple=float(np.median(m)),
        p_total_loss=p_total_loss,
        quantiles=quant,
        premium_bled_frac=premium_bled,
        convexity_ratio=convexity,
        breakeven_hit_rate=breakeven_hit_rate(m),
        transfer_curve=transfer_curve(cell),
        exit_mix=_exit_mix(cell.exit_reasons),
    )


def breakeven_hit_rate(multiples: np.ndarray) -> float | None:
    """Hit-rate interpretation (PREREG §5): treat the right tail as 'thesis right'.

    Split paths into 'winners' (M>1, thesis paid) and 'losers' (M≤1). Break-even when
    E_win·p + E_loss·(1−p) = 1 ⇒ p* = (1 − E_loss)/(E_win − E_loss). Returns None when
    undefined (no winners, or E_win ≤ E_loss). p*∈(0,1] is "how often judgment must be right."
    """
    m = np.asarray(multiples, dtype=float)
    win = m[m > 1.0]
    los = m[m <= 1.0]
    if win.size == 0:
        return None
    e_win = float(win.mean())
    e_los = float(los.mean()) if los.size else 0.0
    denom = e_win - e_los
    if denom <= 0:
        return None
    p = (1.0 - e_los) / denom
    if p <= 0 or p > 1:
        return None
    return float(p)


def transfer_curve(cell: CellResult, buckets=(-0.5, -0.2, 0.0, 0.2, 0.5, 1.0)) -> list[tuple[str, float]]:
    """Underlying-terminal-return bucket → median option multiple (the pure mechanics)."""
    m = np.asarray(cell.multiples, dtype=float)
    u = np.asarray(cell.underlying_returns, dtype=float)
    if m.size == 0:
        return []
    edges = [-np.inf, *buckets, np.inf]
    out = []
    labels = []
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        mask = (u > lo) & (u <= hi)
        lo_s = "-inf" if lo == -np.inf else f"{lo:+.0%}"
        hi_s = "+inf" if hi == np.inf else f"{hi:+.0%}"
        labels.append(f"{lo_s}..{hi_s}")
        out.append(float(np.median(m[mask])) if mask.any() else 0.0)
    return list(zip(labels, out, strict=True))


def _exit_mix(reasons: list[str]) -> dict[str, float]:
    if not reasons:
        return {}
    n = len(reasons)
    out: dict[str, float] = {}
    for why in reasons:
        out[why] = out.get(why, 0.0) + 1.0 / n
    return out
