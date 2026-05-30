"""Walk-forward replay engine (plan §B8) — the point-in-time spine of the gate.

At each non-overlapping rebalance date ``t`` (stepped along the benchmark's trading
calendar) the engine:
  1. determines the eligible cross-section (price + ADV only — no historical option
     liquidity, plan §B1),
  2. builds the divergence panel with **as-of** adapters,
  3. **asserts the cache surfaced no record dated > t** (the lookahead tripwire), and
  4. pairs each name's signal ``s = −divergence`` with its strictly-forward return label.

The forward-return label uses future bars by design (it is never a feature). The
:meth:`Backtest.audit` method emits the §A0 data-availability pre-flight (eligible-N curve,
coverage, substance density) and **never computes any IC** — coverage must stay orthogonal
to performance so the explore/lockbox boundary can be set without contaminating the gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from divergence import build_panel
from universe import Universe, check_eligibility


@dataclass
class BacktestData:
    horizons: list[int]
    date_panels: list[dict[str, Any]]  # each: as_of, obs[], theme_obs[]
    n_dates: int
    n_skipped: int
    eligible_curve: list[tuple[str, int]]  # (yyyy-mm, eligible count) — audit

    def panels_for_horizon(self, h: int) -> list[dict[str, Any]]:
        """Project per-name/theme ``fwd_rets[h]`` into the ``fwd_ret`` field metrics expects."""
        out = []
        for p in self.date_panels:
            obs = [{**o, "fwd_ret": o["fwd_rets"].get(h)} for o in p["obs"]]
            tobs = [{**t, "fwd_ret": t["fwd_rets"].get(h)} for t in p["theme_obs"]]
            out.append({"as_of": p["as_of"], "obs": obs, "theme_obs": tobs})
        return out


@dataclass
class AuditReport:
    """§A0 pre-flight: coverage/availability ONLY — no performance numbers."""

    rebalance_dates: int
    eligible_curve: list[tuple[str, int]]
    coverage_by_year: dict[str, dict[int, int]]
    substance_density: float
    skipped_dates: int
    notes: list[str] = field(default_factory=list)

    def to_text(self) -> str:
        lines = [
            "DATA-AVAILABILITY PRE-FLIGHT (coverage only — NO IC/performance computed)",
            f"  rebalance dates: {self.rebalance_dates}   skipped (n<n_min): {self.skipped_dates}",
            "  eligible-N over time (price+ADV floor):",
        ]
        for ym, n in self.eligible_curve:
            lines.append(f"    {ym}: {'#' * n} {n}")
        lines.append(f"  substance non-zero density (name-dates): {self.substance_density:.0%}")
        lines.append("  NOTE: review this BEFORE judging the signal; set the explore/lockbox")
        lines.append("        boundary from coverage, then freeze it. (plan §A0)")
        for n in self.notes:
            lines.append(f"  · {n}")
        return "\n".join(lines)


class Backtest:
    def __init__(
        self,
        config: dict[str, Any],
        universe: Universe,
        *,
        cache: Any,
        market: Any,
        news: Any,
        filings: Any,
        horizons: list[int] | None = None,
    ) -> None:
        self.config = config
        self.universe = universe
        self.cache = cache
        self.market = market
        self.news = news
        self.filings = filings
        bt = config.get("backtest", {})
        primary = int(bt.get("horizon_days", 21))
        self.horizons = horizons or sorted(
            {primary, *[int(h) for h in bt.get("horizon_sweep_days", [])]}
        )
        self.primary_horizon = primary
        self.rebalance_days = int(bt.get("rebalance_days", 21))

    # ── rebalance calendar (benchmark trading days) ─────────────────────────
    def _rebalance_dates(self, start: datetime, end: datetime) -> list[datetime]:
        bench = self.universe.broad_benchmark
        closes = self.market.closes_asof(bench, end)
        dates = [d for d, _ in closes if start <= d <= end]
        return dates[:: self.rebalance_days]

    def _eligible(self, as_of: datetime) -> list[str]:
        out = []
        adv_window = self.config.get("eligibility", {}).get("backtest", {}).get("adv_window_days", 20)
        for sym in self.universe.symbols:
            price = self.market.latest_price(sym, as_of)
            adv = self.market.adv_usd(sym, as_of, window=adv_window)
            res = check_eligibility(
                sym, as_of, price=price, adv_usd=adv, config=self.config, mode="backtest"
            )
            if res.eligible:
                out.append(sym)
        return out

    # ── §A0 audit (coverage only) ───────────────────────────────────────────
    def audit(self, start: datetime, end: datetime) -> AuditReport:
        dates = self._rebalance_dates(start, end)
        by_month: dict[str, int] = {}
        density_hits = density_total = skipped = 0
        n_min = int(self.config.get("backtest", {}).get("n_min_cross_section", 8))
        for t in dates:
            elig = self._eligible(t)
            ym = t.strftime("%Y-%m")
            by_month[ym] = max(by_month.get(ym, 0), len(elig))
            if len(elig) < n_min:
                skipped += 1
            self.cache.reset_running_max()
            panel = build_panel(
                t, elig, self.universe.theme_of, news=self.news,
                filings=self.filings, config=self.config,
            )
            self._assert_no_lookahead(t)
            density_total += panel.n_valid
            density_hits += panel.n_substance_nonzero
        coverage = {s: self.news.coverage_by_year(s) for s in self.universe.symbols}
        return AuditReport(
            rebalance_dates=len(dates),
            eligible_curve=sorted(by_month.items()),
            coverage_by_year=coverage,
            substance_density=(density_hits / density_total) if density_total else 0.0,
            skipped_dates=skipped,
        )

    # ── full run ─────────────────────────────────────────────────────────────
    def run(self, start: datetime, end: datetime) -> BacktestData:
        dates = self._rebalance_dates(start, end)
        date_panels: list[dict[str, Any]] = []
        by_month: dict[str, int] = {}
        skipped = 0
        for t in dates:
            elig = self._eligible(t)
            by_month[t.strftime("%Y-%m")] = max(by_month.get(t.strftime("%Y-%m"), 0), len(elig))
            self.cache.reset_running_max()
            panel = build_panel(
                t, elig, self.universe.theme_of, news=self.news,
                filings=self.filings, config=self.config,
            )
            self._assert_no_lookahead(t)
            if panel.skipped:
                skipped += 1
                continue
            obs = []
            for ns in panel.names:
                fwd_rets = {h: self.market.forward_return(ns.symbol, t, h) for h in self.horizons}
                obs.append({
                    "symbol": ns.symbol,
                    "theme": ns.theme,
                    "s": -ns.divergence,  # directional trade signal
                    "momentum": self.market.momentum(ns.symbol, t),
                    "growth_beta": self.market.beta(ns.symbol, self.universe.growth_benchmark, t),
                    "broad_beta": self.market.beta(ns.symbol, self.universe.broad_benchmark, t),
                    "has_substance_event": ns.has_substance_event,
                    "fwd_rets": fwd_rets,
                })
            theme_obs = self._theme_obs(panel, obs)
            date_panels.append({"as_of": t, "obs": obs, "theme_obs": theme_obs})
            self._assert_no_lookahead(t)  # forward_return used read_between (no tripwire) — verify
        return BacktestData(
            horizons=self.horizons, date_panels=date_panels, n_dates=len(dates),
            n_skipped=skipped, eligible_curve=sorted(by_month.items()),
        )

    def _theme_obs(self, panel: Any, obs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_theme: dict[str, list[dict[str, Any]]] = {}
        for o in obs:
            if o["theme"]:
                by_theme.setdefault(o["theme"], []).append(o)
        out = []
        for ts in panel.themes:
            members = by_theme.get(ts.theme, [])
            if not members:
                continue
            fwd_rets = {}
            for h in self.horizons:
                vals = [m["fwd_rets"].get(h) for m in members if m["fwd_rets"].get(h) is not None]
                fwd_rets[h] = sum(vals) / len(vals) if vals else None
            out.append({"theme": ts.theme, "s": -ts.divergence, "fwd_rets": fwd_rets})
        return out

    def _assert_no_lookahead(self, t: datetime) -> None:
        rm = self.cache.running_max_ts
        if rm is not None and rm > t:
            raise AssertionError(
                f"LOOKAHEAD: cache surfaced a record dated {rm.isoformat()} for as_of {t.isoformat()}"
            )
