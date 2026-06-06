"""Trailing-return correlation diagnostic (cluster-cap curation backstop) — offline.

Covers the sensitivity-tuned methodology: perfect/anti correlation; residual strips a common SPY factor;
the union flag + driver label; top-N sorted (a near-miss still appears); the short-history lower-confidence
tier; the degenerate-beta guard; the no-fetch invariant; and the cohesion / cross-cluster baseline.
"""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime, timedelta

import numpy as np

import dramatic_options.cluster_diagnostic as cd
from dramatic_options import state
from dramatic_options.data.cache import PointInTimeCache
from dramatic_options.data.market import MarketData

AS_OF = datetime(2026, 1, 2, tzinfo=UTC)


def _market(returns_by_symbol: dict, *, start=100.0) -> MarketData:
    """A cache-backed (client=None) MarketData whose trailing bars realize the given daily returns."""
    cache = PointInTimeCache(tempfile.mkdtemp(prefix="corr_"))
    first = AS_OF
    for sym, rets in returns_by_symbol.items():
        closes = [start]
        for r in rets:
            closes.append(closes[-1] * (1.0 + r))
        first = AS_OF - timedelta(days=len(closes))
        bars = [{"ts": (first + timedelta(days=i)).isoformat(), "open": c, "high": c, "low": c,
                 "close": c, "volume": 2_000_000} for i, c in enumerate(closes)]
        cache.write("bars", sym.upper(), bars, coverage_from=first - timedelta(days=2),
                    coverage_through=AS_OF + timedelta(days=2))
    return MarketData(cache, client=None, fetch_start=first, fetch_end=AS_OF)


def _pair(pairs, a, b):
    return next(p for p in pairs if {p.a, p.b} == {a, b})


# ── correlation core ──────────────────────────────────────────────────────────

def test_perfect_and_anti_correlation():
    rng = np.random.default_rng(1)
    r = rng.normal(0, 0.01, 260)
    mkt = _market({"AAA": r, "BBB": r, "CCC": -r, "SPY": rng.normal(0, 0.01, 260)})
    pairs = cd.trailing_return_correlation(["AAA", "BBB", "CCC"], AS_OF, mkt, window=250)
    assert _pair(pairs, "AAA", "BBB").raw > 0.99
    assert _pair(pairs, "AAA", "CCC").raw < -0.99


def test_residual_strips_common_market_factor():
    rng = np.random.default_rng(2)
    spy = rng.normal(0, 0.012, 260)
    mkt = _market({"AAA": spy + rng.normal(0, 0.001, 260), "BBB": spy + rng.normal(0, 0.001, 260), "SPY": spy})
    p = _pair(cd.trailing_return_correlation(["AAA", "BBB"], AS_OF, mkt, window=250), "AAA", "BBB")
    assert p.raw > 0.9 and abs(p.residual) < 0.4 and p.driver == "mostly market beta"   # co-move is market beta


def test_shared_driver_survives_residual():
    rng = np.random.default_rng(3)
    spy = rng.normal(0, 0.01, 260)
    shared = rng.normal(0, 0.01, 260)                       # a non-SPY common factor (the theme)
    mkt = _market({"AAA": spy + shared + rng.normal(0, 0.001, 260),
                   "BBB": spy + shared + rng.normal(0, 0.001, 260), "SPY": spy})
    p = _pair(cd.trailing_return_correlation(["AAA", "BBB"], AS_OF, mkt, window=250), "AAA", "BBB")
    assert p.raw > 0.9 and p.residual > 0.5 and p.driver == "shared driver"


def test_degenerate_series_insufficient():
    rng = np.random.default_rng(4)
    mkt = _market({"FLAT": [0.0] * 260, "AAA": rng.normal(0, 0.01, 260), "SPY": [0.0] * 260})
    p = _pair(cd.trailing_return_correlation(["FLAT", "AAA"], AS_OF, mkt, window=250), "FLAT", "AAA")
    assert p.raw is None and p.residual is None             # constant series + zero-variance SPY → no NaN/inf


def test_no_fetch_on_cache_miss():
    rng = np.random.default_rng(5)
    mkt = _market({"AAA": rng.normal(0, 0.01, 260), "SPY": rng.normal(0, 0.01, 260)})
    # MISSING is not in the cache + client is None → insufficient, no fetch, no raise.
    assert mkt.client is None
    pairs = cd.trailing_return_correlation(["AAA", "MISSING"], AS_OF, mkt, window=250)
    assert pairs == []                                      # MISSING dropped (no cached returns)


# ── the curation report ───────────────────────────────────────────────────────

def _cfg(themes, clusters_map=None, *, window=60, min_overlap=20):
    return {"universe": {"themes": themes},
            "convexity_book": {"per_name_fraction": 0.01, "cluster_fraction": 0.02,
                               "clusters": clusters_map or {}},
            "cluster_diagnostic": {"window_days": window, "high_corr_threshold": 0.7,
                                   "min_overlap": min_overlap, "top_n": 25, "residual_benchmark": "SPY"},
            "themes_path": "themes.json", "discovery": {}}


def test_report_flags_noncoclustered_gap_grouped_by_action(convexity_db):
    rng = np.random.default_rng(6)
    shared = rng.normal(0, 0.015, 80)
    mkt = _market({"AAA": shared + rng.normal(0, 0.001, 80), "BBB": shared + rng.normal(0, 0.001, 80),
                   "SPY": rng.normal(0, 0.01, 80)})
    # AAA & BBB co-move but neither is clustered → a 'create_or_extend' GAP at full N.
    rep = cd.cluster_curation_report(convexity_db, _cfg({"t": ["AAA", "BBB"]}), AS_OF, mkt)
    gap = next(g for g in rep["gaps_full_n"] if g["pair"] in ("AAA-BBB", "BBB-AAA"))
    assert gap["over_threshold"] and gap["action"] == "create_or_extend" and gap["cluster_status"] == "none"


def test_report_near_miss_appears_not_filtered(convexity_db):
    # A ~0.6 pair (below 0.7) must STILL appear in the sorted list — threshold highlights, never drops.
    rng = np.random.default_rng(7)
    base = rng.normal(0, 0.015, 80)
    mkt = _market({"AAA": base + rng.normal(0, 0.018, 80), "BBB": base + rng.normal(0, 0.018, 80),
                   "SPY": rng.normal(0, 0.01, 80)})
    rep = cd.cluster_curation_report(convexity_db, _cfg({"t": ["AAA", "BBB"]}), AS_OF, mkt)
    rows = rep["gaps_full_n"] + rep["gaps_lower_confidence"]
    assert any(r["pair"] in ("AAA-BBB", "BBB-AAA") and not r["over_threshold"] for r in rows)


def test_report_short_history_in_lower_confidence_tier(convexity_db):
    rng = np.random.default_rng(8)
    shared = rng.normal(0, 0.015, 80)
    # NEW has only 30 returns (< 0.85*60=51) → the LOWER-CONFIDENCE tier, not full-N GAPS.
    mkt = _market({"AAA": shared + rng.normal(0, 0.001, 80), "NEW": (shared + rng.normal(0, 0.001, 80))[-30:],
                   "SPY": rng.normal(0, 0.01, 80)})
    rep = cd.cluster_curation_report(convexity_db, _cfg({"t": ["AAA", "NEW"]}), AS_OF, mkt)
    assert any(g["pair"] in ("AAA-NEW", "NEW-AAA") for g in rep["gaps_lower_confidence"])
    assert not any(g["pair"] in ("AAA-NEW", "NEW-AAA") for g in rep["gaps_full_n"])


def test_report_cohesion_baseline_and_cross_cluster(convexity_db):
    rng = np.random.default_rng(9)
    drv = rng.normal(0, 0.015, 80)
    mkt = _market({"AAA": drv + rng.normal(0, 0.001, 80), "BBB": drv + rng.normal(0, 0.001, 80),
                   "ZZZ": rng.normal(0, 0.02, 80), "SPY": rng.normal(0, 0.01, 80)})
    cfg = _cfg({"t": ["AAA", "BBB", "ZZZ"]}, {"powr": ["AAA", "BBB"], "other": ["ZZZ"]})
    rep = cd.cluster_curation_report(convexity_db, cfg, AS_OF, mkt)
    assert rep["cohesion"]["powr"]["mean"] > 0.8 and rep["cohesion"]["powr"]["min_pair"] in ("AAA-BBB", "BBB-AAA")
    assert rep["universe_median_corr"] is not None and "powr|other" in rep["cross_cluster"]
    assert len(rep["caveats"]) >= 4 and "report-not-gate" in rep["caveats"][0].lower()


def test_universe_includes_open_book_symbols(convexity_db):
    # A held real-book name dropped from the candidate sets is still cap-constrained → in the universe.
    state.record_convexity_position(
        convexity_db, run_id=None, opened_at="2026-01-02T00:00:00+00:00", theme="t", symbol="HELD",
        direction="bullish", structure_kind="C", contract_symbol="HELDX", expiry="2026-12-18", strike=80.0,
        dte=300, moneyness=0.25, contracts=1, entry_premium_per_contract=100.0, total_premium=100.0)
    uni = cd.build_universe(convexity_db, _cfg({"t": ["AAA"]}))
    assert "HELD" in uni and "AAA" in uni
