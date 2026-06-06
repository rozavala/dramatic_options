"""Risk guards (Phase 0 skeleton).

Fail-closed primitives consulted before any work. The full risk/portfolio model
(fractional Kelly, caps, VaR, drawdown breaker) arrives in Phase 4 — this module
only provides the always-on guards: kill switch, daily-loss halt placeholder, and a
market-hours guard driven by the injectable clock.
"""

from __future__ import annotations

import os
from pathlib import Path

from dramatic_options.clock import Clock

# A KILL file at repo root OR the KILL env var halts everything. This module lives in the
# dramatic_options/ package, so the repo root is one level up.
KILL_FILE = Path(__file__).resolve().parent.parent / "KILL"


def kill_switch_active() -> bool:
    """True if the operator has engaged the kill switch (file or env)."""
    if KILL_FILE.exists():
        return True
    return os.getenv("KILL", "").strip().lower() in ("1", "true", "yes", "on")


def market_hours_guard(clock: Clock) -> bool:
    """True if trading is permitted by market state. Fail-closed via the clock."""
    return clock.is_market_open()


def daily_loss_halt(realized_pnl: float, equity: float, halt_pct: float) -> bool:
    """Placeholder daily-loss halt (full model in Phase 4).

    Returns True (halt) if the day's realized loss exceeds halt_pct of equity.
    Fail-closed: non-positive equity halts.
    """
    if equity <= 0:
        return True
    return realized_pnl <= -abs(halt_pct) * equity
