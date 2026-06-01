"""Backtest gate: positive + NULL controls, lookahead guard, bands/Bonferroni/density.

The NULL control is the highest-value test: a leakage/methodology bug that conjures signal
out of noise would otherwise silently inflate the real result too.
"""

from datetime import UTC, datetime, timedelta

import numpy as np

from backtest import metrics
from backtest.engine import Backtest
from data.cache import PointInTimeCache
from data.filings import FilingsData
from data.market import MarketData
from data.news import NewsData
from universe import Universe

CFG = {
    "backtest": {
        "alpha_base": 0.05, "bootstrap_iters": 1000, "block_days": 21, "rebalance_days": 21,
        "quantiles": 5, "fold_count": 4, "ic_fail_below": 0.03, "ic_green_above": 0.06,
        "sign_consistency_min": 0.60, "residual_ic_retention_min": 0.50,
        "substance_density_floor": 0.20, "horizon_days": 21,
        "n_min_cross_section": 8, "horizon_sweep_days": [],
    }
}
T0 = datetime(2022, 1, 1, tzinfo=UTC)


def _panels(rng, *, predictive: bool, density: bool, n_dates=30, n_names=15):
    panels = []
    for d in range(n_dates):
        s = rng.normal(size=n_names)
        fwd = (0.6 * s if predictive else np.zeros(n_names)) + rng.normal(size=n_names)
        obs = [{
            "s": float(s[i]), "fwd_ret": float(fwd[i]),
            "momentum": float(rng.normal()), "growth_beta": float(rng.normal()),
            "broad_beta": float(rng.normal()), "has_substance_event": density,
        } for i in range(n_names)]
        panels.append({"as_of": T0 + timedelta(days=21 * d), "obs": obs, "theme_obs": []})
    return panels


def test_positive_control_recovers_ic():
    res = metrics.evaluate(_panels(np.random.default_rng(0), predictive=True, density=True),
                           config=CFG, k_iterations=1, horizon_days=21)
    assert res.pooled_ic > 0.2
    assert res.ci_excludes_zero
    assert res.substance_density == 1.0
    assert res.band in {"YELLOW", "GREEN"}
    assert "INCONCLUSIVE" not in res.verdict


def test_null_control_ic_spans_zero():
    res = metrics.evaluate(_panels(np.random.default_rng(1), predictive=False, density=True),
                           config=CFG, k_iterations=1, horizon_days=21)
    assert abs(res.pooled_ic) < 0.1
    assert not res.ci_excludes_zero
    assert res.verdict == "INCONCLUSIVE-ITERATE"


def test_substance_density_floor_blocks_thesis_even_if_predictive():
    # strong signal but NO substance events → divergence ≈ narrative → not the thesis
    res = metrics.evaluate(_panels(np.random.default_rng(0), predictive=True, density=False),
                           config=CFG, k_iterations=1, horizon_days=21)
    assert res.substance_density == 0.0
    assert res.verdict == "INCONCLUSIVE-FOR-THESIS"


def test_bonferroni_alpha_widens_ci():
    ics = list(np.random.default_rng(3).normal(0.05, 0.08, size=20))
    wide = metrics.block_bootstrap_ci(ics, alpha=0.05 / 20, n_iter=2000, block=1)
    narrow = metrics.block_bootstrap_ci(ics, alpha=0.05, n_iter=2000, block=1)
    assert wide[0] < narrow[0] and wide[1] > narrow[1]  # smaller alpha → wider interval


def test_verdict_bands():
    base = dict(ci_excludes_zero=True, sign_consistency=0.8, sign_min=0.6, spread=0.02,
                monotonic=True, retention=0.9, retain_min=0.5, density=0.5,
                density_floor=0.2, ic_fail=0.03, ic_green=0.06, n_periods=20)
    assert metrics._verdict(pooled_ic=0.10, **base)[0] == "GREEN"
    assert metrics._verdict(pooled_ic=0.04, **base)[0] == "YELLOW"
    assert metrics._verdict(pooled_ic=0.01, **base)[0] == "FAIL"
    # density floor overrides
    band, verdict, _ = metrics._verdict(pooled_ic=0.10, **{**base, "density": 0.1})
    assert verdict == "INCONCLUSIVE-FOR-THESIS"
    # CI spanning 0 → iterate
    _, verdict2, _ = metrics._verdict(pooled_ic=0.10, **{**base, "ci_excludes_zero": False})
    assert verdict2 == "INCONCLUSIVE-ITERATE"


def test_fold_sign_consistency():
    assert metrics._fold_sign_consistency([0.1] * 8, 4) == 1.0
    assert metrics._fold_sign_consistency([0.1, 0.1, -0.1, -0.1, 0.1, 0.1, -0.1, -0.1], 4) == 0.5


# ── engine: lookahead guard + non-overlap + ragged audit ─────────────────────
class _FakeCache:
    def __init__(self, running_max):
        self.running_max_ts = running_max

    def reset_running_max(self):
        self.running_max_ts = None


def _engine_with_cache(running_max):
    bt = Backtest.__new__(Backtest)
    bt.cache = _FakeCache(running_max)
    return bt


def test_lookahead_assertion_raises_on_future_record():
    t = datetime(2023, 6, 1, tzinfo=UTC)
    eng = _engine_with_cache(t + timedelta(days=1))
    try:
        eng._assert_no_lookahead(t)
        raised = False
    except AssertionError:
        raised = True
    assert raised


def test_lookahead_assertion_passes_when_at_or_before_t():
    t = datetime(2023, 6, 1, tzinfo=UTC)
    _engine_with_cache(t)._assert_no_lookahead(t)  # no raise


class _StubMarket:
    def __init__(self, dates):
        self._dates = dates

    def closes_asof(self, sym, as_of):
        return [(d, 10.0) for d in self._dates if d <= as_of]


def test_rebalance_dates_are_non_overlapping():
    dates = [datetime(2022, 1, 1, tzinfo=UTC) + timedelta(days=i) for i in range(100)]
    uni = Universe(themes={}, broad_benchmark="SPY", growth_benchmark="ARKK")
    bt = Backtest(CFG, uni, cache=None, market=_StubMarket(dates), news=None, filings=None)
    rb = bt._rebalance_dates(dates[0], dates[-1])
    gaps = [(rb[i + 1] - rb[i]).days for i in range(len(rb) - 1)]
    assert all(g == 21 for g in gaps)  # rebalance step = horizon → non-overlapping


def _bars(start, n, vol=1_000_000):
    d0 = datetime.fromisoformat(start).replace(tzinfo=UTC)
    return [{"ts": (d0 + timedelta(days=i)).isoformat(), "open": 10.0, "high": 10.0,
             "low": 10.0, "close": 10.0, "volume": vol} for i in range(n)]


def test_audit_eligible_curve_grows_with_ragged_starts(tmp_path):
    cache = PointInTimeCache(tmp_path)
    end = datetime.fromisoformat("2022-06-30").replace(tzinfo=UTC)
    # SPY full range (drives the rebalance calendar); A early, B late (ragged).
    cov_from = datetime(2020, 1, 1, tzinfo=UTC)
    for sym, start, n in [("SPY", "2022-01-01", 180), ("ARKK", "2022-01-01", 180),
                          ("A", "2022-01-01", 180), ("B", "2022-05-01", 60)]:
        cache.write("bars", sym, _bars(start, n), coverage_from=cov_from, coverage_through=end)
    for sym in ["A", "B"]:
        cache.write("news", sym, [], coverage_from=cov_from, coverage_through=end)
        cache.write("filings", sym, [], coverage_from=cov_from, coverage_through=end)
    uni = Universe(themes={"t": ("A", "B")}, broad_benchmark="SPY", growth_benchmark="ARKK")
    cfg = {**CFG, "eligibility": {"backtest": {"min_price": 3.0, "min_adv_usd": 3e6,
                                               "adv_window_days": 20}}}
    md = MarketData(cache, client=None, fetch_start=datetime(2021, 1, 1, tzinfo=UTC), fetch_end=end)
    nd = NewsData(cache, client=None, fetch_start=datetime(2021, 1, 1, tzinfo=UTC), fetch_end=end)
    fd = FilingsData(cache, edgar=None, fetch_end=end)
    bt = Backtest(cfg, uni, cache=cache, market=md, news=nd, filings=fd)
    report = bt.audit(datetime.fromisoformat("2022-02-01").replace(tzinfo=UTC), end)
    curve = dict(report.eligible_curve)
    # B only becomes eligible after ~20 sessions past 2022-05-01 → later months ≥ earlier
    assert max(curve.values()) >= 2
    assert curve[min(curve)] <= curve[max(curve)]
