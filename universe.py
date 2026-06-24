"""Seed universe + eligibility (Phase 1, task 1.1).

The hand-seeded thematic universe (SPEC §14.3) lives in ``config.json`` under ``universe``
(config over code). This module loads it, exposes the ticker→theme mapping, and applies the
**split eligibility floor**:

  - ``mode="backtest"`` gates on price + ADV ONLY — both available point-in-time from bars.
  - ``mode="live"`` additionally applies the option-liquidity floor (OI + bid/ask%).

This split is a point-in-time correctness requirement, not a convenience: historical option
OI/spread do not exist on this stack back to 2022, so applying *today's* option liquidity
retroactively in a backtest would inject survivorship/lookahead bias (plan §B1).

No bare ``datetime.now()``: eligibility is evaluated as-of a caller-supplied timestamp.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

EligibilityMode = Literal["backtest", "live"]


@dataclass(frozen=True)
class Universe:
    """The loaded seed universe: themes → member symbols, plus benchmarks."""

    themes: dict[str, tuple[str, ...]]
    broad_benchmark: str
    growth_benchmark: str

    @property
    def symbols(self) -> tuple[str, ...]:
        """All distinct member symbols, sorted, benchmarks excluded."""
        seen: dict[str, None] = {}
        for members in self.themes.values():
            for sym in members:
                seen.setdefault(sym, None)
        return tuple(sorted(seen))

    @property
    def benchmarks(self) -> tuple[str, ...]:
        return (self.broad_benchmark, self.growth_benchmark)

    @property
    def theme_of(self) -> dict[str, str]:
        """symbol → theme. If a symbol appears in multiple themes, first wins."""
        out: dict[str, str] = {}
        for theme, members in self.themes.items():
            for sym in members:
                out.setdefault(sym, theme)
        return out

    def members(self, theme: str) -> tuple[str, ...]:
        return self.themes.get(theme, ())


def load_universe(config: dict[str, Any]) -> Universe:
    """Build a Universe from the ``universe`` block of config."""
    uni = config.get("universe", {})
    themes_raw = uni.get("themes", {})
    themes = {
        str(theme): tuple(str(s).upper() for s in members)
        for theme, members in themes_raw.items()
        if not str(theme).startswith("_")
    }
    bms = uni.get("benchmarks", {})
    return Universe(
        themes=themes,
        broad_benchmark=str(bms.get("broad", "SPY")).upper(),
        growth_benchmark=str(bms.get("growth", "ARKK")).upper(),
    )


def load_theme_theses(config: dict[str, Any], *, register_path: str = "universe_register.json") -> dict[str, str]:
    """symbol → the operator-authored STRUCTURAL thesis for its basket (PR2 council backdrop).

    Joins the loop-facing universe (``config.universe.themes`` via ``Universe.theme_of``: symbol→basket)
    with the theme REGISTER's per-basket ``thesis`` (``universe_register.json``). The register is "never
    loaded by the trading loop" for ADMISSION — this reads ONLY its thesis text as council CONTEXT
    (gates still dispose). Fail-soft: a missing file / malformed JSON / absent thesis → the affected
    symbols are simply omitted (no backdrop line)."""
    import json
    from pathlib import Path

    theme_of = load_universe(config).theme_of  # symbol -> basket
    try:
        reg = json.loads(Path(register_path).read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    theses = {b: e.get("thesis") for b, e in (reg.get("themes", {}) or {}).items()}
    return {sym: theses[basket] for sym, basket in theme_of.items() if theses.get(basket)}


@dataclass(frozen=True)
class EligibilityResult:
    """Per-symbol eligibility outcome (advisory in Phase 1 — flags, does not drop history)."""

    symbol: str
    eligible: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)
    price: float | None = None
    adv_usd: float | None = None


def check_eligibility(
    symbol: str,
    as_of: datetime,
    *,
    price: float | None,
    adv_usd: float | None,
    config: dict[str, Any],
    mode: EligibilityMode = "backtest",
    option_open_interest: int | None = None,
    bid_ask_pct: float | None = None,
) -> EligibilityResult:
    """Apply the configured floor for ``mode``. Missing inputs → ineligible (fail-closed).

    ``option_open_interest`` / ``bid_ask_pct`` are consulted only in ``mode="live"``; in
    ``mode="backtest"`` they are ignored entirely (the historical option floor does not exist).
    """
    floor = config.get("eligibility", {}).get(mode, {})
    reasons: list[str] = []

    if price is None:
        reasons.append("no_price")
    elif price < floor.get("min_price", 0.0):
        reasons.append(f"price<{floor.get('min_price')}")

    if adv_usd is None:
        reasons.append("no_adv")
    elif adv_usd < floor.get("min_adv_usd", 0.0):
        reasons.append(f"adv<{floor.get('min_adv_usd')}")

    if mode == "live":
        min_oi = floor.get("min_option_open_interest")
        if min_oi is not None:
            if option_open_interest is None:
                reasons.append("no_option_oi")
            elif option_open_interest < min_oi:
                reasons.append(f"oi<{min_oi}")
        max_spread = floor.get("max_bid_ask_pct")
        if max_spread is not None:
            if bid_ask_pct is None:
                reasons.append("no_spread")
            elif bid_ask_pct > max_spread:
                reasons.append(f"spread>{max_spread}")

    return EligibilityResult(
        symbol=symbol,
        eligible=not reasons,
        reasons=tuple(reasons),
        price=price,
        adv_usd=adv_usd,
    )
