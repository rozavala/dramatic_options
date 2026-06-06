"""Basket-quality report (the survivorship → basket-curation loop, report-not-gate) — offline.

Covers the converged design: kind='sentinel'-only funnel with controls in the separate baseline;
never_surfaced subtracts the barred set; per-symbol multi-lineage aggregation; the forward SPLIT
(reference horizon-indexed vs traded pooled — a realized_multiple is never horizon-bucketed); the two
maturity clocks; data-dead + degenerate-basket flags; convexity_eval coverage ≠ rich; the NO-FETCH and
NO-DB-WRITE invariants; horizon consistency; and per-name fail-soft.
"""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime, timedelta

import dramatic_options.basket_quality as bq
from dramatic_options import state
from dramatic_options.data.cache import PointInTimeCache
from dramatic_options.data.market import MarketData

AS_OF = datetime(2026, 6, 4, tzinfo=UTC)
OLD = (AS_OF - timedelta(days=400)).isoformat()      # mature: a full 365d window has elapsed
YOUNG = (AS_OF - timedelta(days=1)).isoformat()      # references can't have resolved


def _market(returns_by_symbol: dict, *, start=100.0) -> MarketData:
    """Cache-backed (client=None) MarketData whose trailing bars realize the given daily returns."""
    cache = PointInTimeCache(tempfile.mkdtemp(prefix="bq_"))
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


def _flat(n=420):
    return [0.0] * n


def _ramp(n=420, step=0.004):     # steady climb → momentum clears the prescreen floor
    return [step] * n


def _config(*, themes_path="/nonexistent/themes.json", horizons=(180, 270, 365)) -> dict:
    return {
        "universe": {"themes": {"alpha": ["AAA", "BBB"], "beta": ["CCC", "DDD"]},
                     "benchmarks": {"broad": "SPY"}},
        "discovery": {"markers": {"mom_lookback": 252, "mom_skip": 21, "rv_recent": 21, "rv_base": 252,
                                  "adv_window": 20, "mom_floor": 0.15, "rv_slope_floor": 0.25,
                                  "min_price": 3.0, "min_adv_usd": 3_000_000.0}},
        "eligibility": {"live": {}},
        "basket_quality": {"enabled": True, "horizons": list(horizons),
                           "min_resolved_references_for_flag": 2, "min_traded_outcomes_for_flag": 1,
                           "min_live_names_per_basket": 2, "top_n_per_name": 40},
        "themes_path": themes_path,
    }


_COLS = ("lineage_key", "kind", "symbol", "basket", "direction", "status", "surface_count",
         "discovered_at", "proposal_id", "outcome", "realized_multiple", "framer_conviction",
         "confound_label", "structural_vs_fad", "markers")


def _seed(conn, *, symbol, basket, kind="sentinel", direction="bullish", status="candidate",
          discovered_at=YOUNG, surface_count=1, proposal_id=None, outcome=None,
          realized_multiple=None, framer_conviction=None, confound_label=None,
          structural_vs_fad=None, markers=None):
    conn.commit()                             # close any open txn so the PRAGMA takes effect
    conn.execute("PRAGMA foreign_keys=OFF")   # synthetic rows reference no real proposal/run FK targets
    vals = (f"{symbol.upper()}|{direction}", kind, symbol.upper(), basket, direction, status,
            surface_count, discovered_at, proposal_id, outcome, realized_multiple, framer_conviction,
            confound_label, structural_vs_fad, json.dumps(markers or {}))
    conn.execute(f"INSERT INTO sentinel_candidates ({','.join(_COLS)}) "
                 f"VALUES ({','.join('?' * len(_COLS))})", vals)
    conn.commit()


# ── funnel / population (R1 #1) ─────────────────────────────────────────────────────────────────

def test_funnel_counts_and_controls_excluded(convexity_db):
    conn = convexity_db
    _seed(conn, symbol="AAA", basket="alpha")                                   # framer-passed only
    _seed(conn, symbol="BBB", basket="alpha", proposal_id=7)                    # traded
    _seed(conn, symbol="CCC", basket="beta", proposal_id=9, realized_multiple=4.0, outcome=1)  # resolved
    _seed(conn, symbol="DDD", basket="beta", kind="control", direction="bullish")              # control
    rep = bq.basket_quality_report(conn, _config(), AS_OF, _market({s: _flat() for s in "AAA BBB CCC DDD SPY".split()}))

    alpha = rep["baskets"]["alpha"]["funnel"]
    assert alpha["framer_passed_lineages"] == 2 and alpha["traded"] == 1 and alpha["resolved"] == 0
    beta = rep["baskets"]["beta"]
    assert beta["funnel"]["framer_passed_lineages"] == 1 and beta["funnel"]["traded"] == 1 and beta["funnel"]["resolved"] == 1
    # the control is NOT in beta's sentinel funnel; it counts as a control instead
    assert beta["controls"]["n"] == 1
    assert "DDD" in beta["funnel"]["never_surfaced_curated"]   # DDD never surfaced AS A SENTINEL


# ── never_surfaced subtracts the barred set (R1 #1) ─────────────────────────────────────────────

def test_never_surfaced_excludes_barred_hand_seeds(convexity_db, tmp_path):
    conn = convexity_db
    themes = tmp_path / "themes.json"
    themes.write_text(json.dumps({"themes": [{"name": "t", "symbol": "AAA", "direction": "bullish"}]}))
    # AAA is a hand-seed (barred from surfacing); BBB is just an un-surfaced curated name.
    rep = bq.basket_quality_report(conn, _config(themes_path=str(themes)), AS_OF,
                                   _market({s: _flat() for s in "AAA BBB CCC DDD SPY".split()}))
    alpha = rep["baskets"]["alpha"]["funnel"]
    assert "AAA" in alpha["barred"] and "AAA" not in alpha["never_surfaced_curated"]
    assert "BBB" in alpha["never_surfaced_curated"]


# ── per-symbol multi-lineage aggregation (R1 #1) ────────────────────────────────────────────────

def test_per_name_aggregates_two_lineages(convexity_db):
    conn = convexity_db
    _seed(conn, symbol="AAA", basket="alpha", direction="bullish", surface_count=3)
    _seed(conn, symbol="AAA", basket="alpha", direction="bearish", surface_count=2)
    rep = bq.basket_quality_report(conn, _config(), AS_OF, _market({s: _flat() for s in "AAA BBB SPY".split()}))
    row = next(r for r in rep["per_name"] if r["symbol"] == "AAA")
    assert {ln["direction"] for ln in row["lineages"]} == {"bullish", "bearish"}
    assert row["surface_count"] == 5 and row["ever_surfaced_as_sentinel"]


# ── forward split: reference horizon-indexed vs traded pooled (R2 #1) ────────────────────────────

def test_forward_split_realized_multiple_never_horizon_bucketed(convexity_db):
    conn = convexity_db
    # a resolved traded sentinel (realized_multiple) and a surfaced-never-traded with an OLD anchor so
    # its forward bars reach the horizons.
    _seed(conn, symbol="AAA", basket="alpha", proposal_id=1, realized_multiple=6.5, outcome=1, discovered_at=OLD)
    _seed(conn, symbol="BBB", basket="alpha", discovered_at=OLD)
    rep = bq.basket_quality_report(conn, _config(), AS_OF, _market({s: _ramp() for s in "AAA BBB SPY".split()}))
    alpha = rep["baskets"]["alpha"]
    assert alpha["traded_outcomes"]["n_traded"] == 1 and alpha["traded_outcomes"]["realized_multiple_p95"] is not None
    # the reference read is keyed strictly by horizon; the realized multiple lives nowhere under it
    assert set(alpha["reference_forward"]) == {"h180", "h270", "h365"}
    assert alpha["reference_forward"]["h180"]["resolved"] >= 1   # BBB's stock return resolved at 180d
    assert all("realized_multiple" not in v for v in alpha["reference_forward"].values())


# ── two maturity clocks (R2 #2) ─────────────────────────────────────────────────────────────────

def test_never_productive_flag_gated_by_maturity(convexity_db):
    conn = convexity_db
    mkt = _market({s: _flat() for s in "AAA BBB CCC DDD SPY".split()})
    # YOUNG record → not mature → no never-productive flag even though BBB never surfaced.
    _seed(conn, symbol="AAA", basket="alpha", discovered_at=YOUNG)
    young = bq.basket_quality_report(conn, _config(), AS_OF, mkt)
    assert young["mature"] is False
    assert not any("never-productive" in f for f in young["baskets"]["alpha"]["flags"])
    # add an OLD lineage → window matures → BBB (eligible, never surfaced) flags never-productive.
    _seed(conn, symbol="CCC", basket="beta", discovered_at=OLD)
    mature = bq.basket_quality_report(conn, _config(), AS_OF, mkt)
    assert mature["mature"] is True
    assert any("never-productive" in f and "BBB" in f for f in mature["baskets"]["alpha"]["flags"])


# ── data-dead + degenerate-basket (evidence-independent) ────────────────────────────────────────

def test_data_dead_and_degenerate(convexity_db):
    conn = convexity_db
    # alpha: AAA has bars, BBB has NONE (data-dead) → 1 usable < min_live(2) → degenerate too.
    mkt = _market({"AAA": _flat(), "CCC": _flat(), "DDD": _flat(), "SPY": _flat()})
    rep = bq.basket_quality_report(conn, _config(), AS_OF, mkt)
    alpha = rep["baskets"]["alpha"]
    assert alpha["current_snapshot"]["data_dead"] == 1
    assert any("data-dead" in f and "BBB" in f for f in alpha["flags"])
    assert any("degenerate" in f for f in alpha["flags"])
    assert any("BBB" in d["indicator"] for d in rep["curation_drift_indicators"])


# ── gate profile: coverage ≠ signal (R1 #5) ─────────────────────────────────────────────────────

def test_gate_profile_never_evaluated_vs_rich(convexity_db):
    conn = convexity_db
    state.record_convexity_eval(conn, run_id=None, as_of=AS_OF.isoformat(), theme="x", symbol="AAA",
                                direction="bullish", decision="veto", eligible=True, gate_cheap=False,
                                iv_rv=1.4, otm_skew=12.0)
    rep = bq.basket_quality_report(conn, _config(), AS_OF, _market({s: _flat() for s in "AAA BBB CCC DDD SPY".split()}))
    assert rep["baskets"]["alpha"]["real_gate_profile"]["n_evaluated"] == 1
    assert rep["baskets"]["alpha"]["real_gate_profile"]["gate_cheap_pct"] == 0.0
    assert rep["baskets"]["beta"]["real_gate_profile"] == "no gate data (never evaluated)"


# ── pooled surfaced-vs-control contrast (computed-when-mature) ───────────────────────────────────

def test_contrast_insufficient_then_computed(convexity_db):
    conn = convexity_db
    rep0 = bq.basket_quality_report(conn, _config(), AS_OF, _market({"SPY": _flat()}))
    assert rep0["surfaced_vs_control_contrast"]["h180"]["status"] == "insufficient_evidence"
    # ≥2 resolved surfaced + ≥2 resolved controls (OLD anchors, ramped bars) → contrast computes.
    for s in ("AAA", "BBB"):
        _seed(conn, symbol=s, basket="alpha", discovered_at=OLD)
    for s in ("CCC", "DDD"):
        _seed(conn, symbol=s, basket="beta", kind="control", discovered_at=OLD)
    rep = bq.basket_quality_report(conn, _config(), AS_OF, _market({s: _ramp() for s in "AAA BBB CCC DDD SPY".split()}))
    h = rep["surfaced_vs_control_contrast"]["h180"]
    assert "p95_gap" in h and "ci90" in h and h["n_surfaced"] >= 2 and h["n_control"] >= 2


# ── NO-FETCH + NO-DB-WRITE invariants ───────────────────────────────────────────────────────────

def test_no_fetch_on_cache_miss(convexity_db):
    conn = convexity_db
    # client=None market with NO bars for any basket name → every name data-dead, never an exception.
    rep = bq.basket_quality_report(conn, _config(), AS_OF, _market({"SPY": _flat()}))
    assert rep["baskets"]["alpha"]["current_snapshot"]["data_dead"] == 2


def test_no_db_write(convexity_db):
    conn = convexity_db
    _seed(conn, symbol="AAA", basket="alpha", proposal_id=3, realized_multiple=2.0, discovered_at=OLD)
    state.record_convexity_eval(conn, run_id=None, as_of=AS_OF.isoformat(), theme="x", symbol="AAA",
                                direction="bullish", decision="open", eligible=True, gate_cheap=True)
    before = {t: conn.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
              for t in ("sentinel_candidates", "convexity_eval", "runs", "convexity_positions")}
    bq.basket_quality_report(conn, _config(), AS_OF, _market({s: _ramp() for s in "AAA BBB SPY".split()}))
    after = {t: conn.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"] for t in before}
    assert before == after   # report-not-gate: SELECTs only, never a write


# ── horizon consistency + fail-soft ─────────────────────────────────────────────────────────────

def test_horizon_consistency(convexity_db):
    conn = convexity_db
    _seed(conn, symbol="AAA", basket="alpha", discovered_at=OLD)
    rep = bq.basket_quality_report(conn, _config(horizons=(180,)), AS_OF,
                                   _market({s: _ramp() for s in "AAA BBB SPY".split()}), horizons=(180,))
    assert rep["horizons"] == [180]
    assert set(rep["baskets"]["alpha"]["reference_forward"]) == {"h180"}
    assert set(rep["control_baseline"]) == {"h180"}


def test_fail_soft_malformed_discovered_at(convexity_db):
    conn = convexity_db
    _seed(conn, symbol="AAA", basket="alpha", discovered_at="not-a-date")   # malformed anchor
    _seed(conn, symbol="BBB", basket="alpha", discovered_at=YOUNG)
    rep = bq.basket_quality_report(conn, _config(), AS_OF, _market({s: _flat() for s in "AAA BBB SPY".split()}))
    # the bad row degrades (excluded from the window/forward read), it does not raise
    assert rep["baskets"]["alpha"]["funnel"]["framer_passed_lineages"] == 2


def test_caveats_present_and_report_not_gate(convexity_db):
    conn = convexity_db
    rep = bq.basket_quality_report(conn, _config(), AS_OF, _market({"SPY": _flat()}))
    joined = " ".join(rep["caveats"])
    assert "REPORT-NOT-GATE" in joined and "3B" in joined and "basket != cluster" in joined
    assert rep["schema_note"].startswith("report-not-gate")
