"""Fundamentals freshness v2 (PR1) — tag-recency + IFRS taxonomy + annual fallback (offline).

The §9 corpus must show the council the FRESHEST available revenue: de-stale tag-migrated names
(SalesRevenueNet→Revenues→RevenueFromContract…), read the `ifrs-full` taxonomy for foreign filers,
and fall back to an annual line for annual-only (foreign IFRS) filers — all without splicing tags or
darkening a name. Hand-checked values per PREREG_CONVEXITY_CALIBRATION §6.
"""

import json
from datetime import UTC, datetime

import pytest

from council.context import (
    ContextPack,
    _fmt_fundamental_line,
    _fmt_value,
    fundamental_evidence_tokens,
)
from council.filters import apply_filter
from data.fundamentals import (
    IFRS_CONCEPT_TAGS,
    FundamentalsData,
    corpus_lines,
)

AS_OF = datetime(2026, 6, 24, 12, 0, tzinfo=UTC)

# ── fixture helpers (consecutive calendar quarters / annual FYs) ──────────────
_QB = {1: ("01-01", "03-31"), 2: ("04-01", "06-30"), 3: ("07-01", "09-30"), 4: ("10-01", "12-31")}


def _q(year: int, q: int, val: float) -> dict:
    s, e = _QB[q]
    return {"start": f"{year}-{s}", "end": f"{year}-{e}", "val": float(val), "filed": f"{year}-{e}"}


def _consec(end_year: int, end_q: int, n: int, *, base: float = 100e6, step: float = 5e6) -> list[dict]:
    """n consecutive quarterly facts ending at (end_year, end_q), chronological."""
    out, y, q = [], end_year, end_q
    for i in range(n):
        out.append(_q(y, q, base - i * step))
        q -= 1
        if q == 0:
            q, y = 4, y - 1
    return list(reversed(out))


def _fy(year: int, val: float) -> dict:
    return {"start": f"{year}-01-01", "end": f"{year}-12-31", "val": float(val), "filed": f"{year + 1}-02-15"}


def _tax(**tags: list[dict]) -> dict:
    return {tag: {"units": {"USD": facts}} for tag, facts in tags.items()}


def _rev(lines: list[dict]) -> list[dict]:
    return [ln for ln in lines if ln["concept"] == "revenue"]


# ── (a) tag selection: freshest COMPUTABLE wins (de-staling) ──────────────────

def test_freshest_computable_revenue_tag_de_stales():
    # legacy tag has the longer history but a stale latest; the current tag is fresher + computable.
    facts = _tax(SalesRevenueNet=_consec(2018, 4, 8), Revenues=_consec(2026, 1, 8))
    rev = _rev(corpus_lines(facts, AS_OF))
    assert rev and all(ln["period_end"].startswith("2026") for ln in rev)  # current, not 2018


def test_fresh_but_sparse_tag_falls_through_to_computable_no_dark_no_splice():
    # the freshest tag has only 2 quarters (no 4-consecutive TTM) → it is SKIPPED, falling through
    # to the freshest COMPUTABLE tag (stale-but-real). Never dark, never a splice across tags.
    facts = _tax(
        RevenueFromContractWithCustomerExcludingAssessedTax=_consec(2026, 1, 2),  # fresh, sparse
        SalesRevenueNet=_consec(2024, 4, 8),                                       # stale, computable
    )
    rev = _rev(corpus_lines(facts, AS_OF))
    assert rev, "must not go dark — falls through to the computable tag"
    assert all(ln["period_end"].startswith("2024") for ln in rev)  # the computable tag only (no splice)


# ── (c) annual fallback (annual-only foreign IFRS filers) ─────────────────────

def test_ifrs_annual_only_emits_rev_annual_yoy():
    facts = {"Revenue": {"units": {"USD": [_fy(2024, 1000e6), _fy(2025, 1240e6)]}}}
    rev = _rev(corpus_lines(facts, AS_OF, tags=IFRS_CONCEPT_TAGS))
    assert len(rev) == 1
    ln = rev[0]
    assert ln["metric"] == "rev_annual_yoy" and ln["value"] == 0.24  # 1240/1000 - 1, hand-checked
    assert ln["period_end"] == "2025-12-31"
    assert ln["latest_musd"] == 1240.0 and ln["base_musd"] == 1000.0


def test_ero_style_alt_ifrs_revenue_tag_un_darks():
    # ERO reports under RevenueFromContractsWithCustomers, not `Revenue` — both must be recognized.
    facts = {"RevenueFromContractsWithCustomers": {"units": {"USD": [_fy(2024, 500e6), _fy(2025, 560e6)]}}}
    rev = _rev(corpus_lines(facts, AS_OF, tags=IFRS_CONCEPT_TAGS))
    assert len(rev) == 1 and rev[0]["metric"] == "rev_annual_yoy"


def test_ifrs_with_quarterly_does_not_fire_annual_fallback():
    # quarterly IFRS data present → the quarterly path produces lines; the annual fallback must NOT fire.
    facts = {"Revenue": {"units": {"USD": _consec(2026, 1, 8)}}}
    metrics = {ln["metric"] for ln in _rev(corpus_lines(facts, AS_OF, tags=IFRS_CONCEPT_TAGS))}
    assert "rev_annual_yoy" not in metrics
    assert metrics & {"ttm_yoy", "qtr_yoy"}


def test_annual_floor_is_two_periods_not_quarterly_four():
    # a single FY period cannot make a YoY → no line (the 2-period floor); two → a line.
    one = {"Revenue": {"units": {"USD": [_fy(2025, 1240e6)]}}}
    two = {"Revenue": {"units": {"USD": [_fy(2024, 1000e6), _fy(2025, 1240e6)]}}}
    assert _rev(corpus_lines(one, AS_OF, tags=IFRS_CONCEPT_TAGS)) == []
    assert len(_rev(corpus_lines(two, AS_OF, tags=IFRS_CONCEPT_TAGS))) == 1


# ── (b) taxonomy selection (corpus_asof) ──────────────────────────────────────

def _fd(tmp_path, raw: dict, sym_cik: tuple[str, str]):
    sym, cik = sym_cik
    rdir = tmp_path / "xbrl_raw"
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / f"CIK{cik.zfill(10)}.json").write_text(json.dumps(raw))
    return FundamentalsData(cache=None, edgar=None, fetch_end=AS_OF, cache_dir=tmp_path,
                            cik_overrides={sym: cik}, max_raw_age_days=None)


def test_corpus_asof_routes_to_fresher_ifrs_over_stale_usgaap(tmp_path):
    # FRO shape: a dead us-gaap stub (2014) + a live ifrs-full annual series (2025) → route to IFRS.
    raw = {"facts": {
        "us-gaap": {"Revenues": {"units": {"USD": _consec(2014, 2, 8)}}},
        "ifrs-full": {"Revenue": {"units": {"USD": [_fy(2024, 1000e6), _fy(2025, 1240e6)]}}},
    }}
    out = _fd(tmp_path, raw, ("FRO", "9999999")).corpus_asof("FRO", AS_OF)
    rev = _rev(out["lines"])
    assert rev and rev[0]["period_end"] == "2025-12-31" and rev[0]["metric"] == "rev_annual_yoy"


def test_corpus_asof_usgaap_wins_ties_us_filer_unchanged(tmp_path):
    # a US filer with only us-gaap (no ifrs) stays on us-gaap, quarterly path unchanged.
    raw = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": _consec(2026, 1, 8)}}}}}
    out = _fd(tmp_path, raw, ("USX", "8888888")).corpus_asof("USX", AS_OF)
    rev = _rev(out["lines"])
    assert rev and rev[0]["period_end"].startswith("2026") and rev[0]["metric"] in ("ttm_yoy", "qtr_yoy")


# ── render + authenticity-filter pool (the §9-#0 surface, this time from PR1) ──

def test_annual_line_renders_cadence_marker_and_percent():
    ln = {"concept": "revenue", "metric": "rev_annual_yoy", "value": 0.24,
          "latest_musd": 1240.0, "base_musd": 1000.0, "period_end": "2025-12-31", "filed": "2026-02-15"}
    assert _fmt_value(ln) == "+24.0%"
    rendered = _fmt_fundamental_line(ln)
    assert "(annual)" in rendered and "+24.0%" in rendered and "period 2025-12-31 (annual)" in rendered


def test_filter_supports_an_annual_revenue_citation():
    # adding rev_annual_yoy to _fmt_value's % set must also flow into fundamental_evidence_tokens,
    # else an agent citing the annual figure is flagged unsupported and dampened (§9 red-team #0).
    ln = {"concept": "revenue", "metric": "rev_annual_yoy", "value": 0.24,
          "latest_musd": 1240.0, "base_musd": 1000.0, "period_end": "2025-12-31", "filed": "2026-02-15"}
    pack = ContextPack(symbol="AG", theme="silver_deficit", direction="bullish",
                       operator_thesis="silver deficit", headlines=["momentum_12m +0.300"],
                       coverage_count=1, has_numeric=True, fundamentals=[ln], origin="sentinel")
    toks = fundamental_evidence_tokens(pack)
    assert "+24.0%" in toks and "1240.0" in toks
    conf, res = apply_filter(['revenue grew "+24.0%" YoY (annual)'], pack, confidence="MODERATE")
    assert res.flagged == 0 and conf == "MODERATE"


# ── standing universe-wide no-regression net (live; run on-host after fundamentals.py changes) ──

# v1 baseline captured 2026-06-24 from the committed (pre-PR1) fundamentals over the live universe.
_V1_STATUS = {
    "AG": "empty", "AMSC": "ok", "ATKR": "ok", "CCJ": "empty", "CDE": "ok", "CEG": "ok",
    "ERO": "empty", "ETN": "ok", "FCX": "ok", "FLNC": "ok", "FLY": "ok", "FRO": "partial",
    "GEV": "ok", "HBM": "empty", "HL": "ok", "IRDM": "ok", "KTOS": "ok", "LHX": "ok",
    "LMT": "ok", "LUNR": "ok", "NEE": "partial", "NNE": "empty", "NOC": "ok", "NVDA": "ok",
    "NXE": "empty", "PAAS": "empty", "PL": "ok", "PWR": "ok", "RDW": "ok", "RKLB": "ok",
    "RTX": "ok", "SMCI": "ok", "SMR": "partial", "TGB": "empty", "UEC": "ok", "UROY": "empty",
    "UUUU": "partial", "VRT": "ok",
}
_RANK = {"empty": 0, "partial": 1, "ok": 2}


@pytest.mark.live
def test_universe_no_status_regression_vs_v1_baseline():
    """The standing net: no live-universe name may move TOWARD `empty` under v2 vs the pinned v1
    baseline. Catches a future tag migration / newly-admitted name silently going dark (the exact
    failure that was invisible until the full-universe extraction). Fetches live SEC companyfacts."""
    from datetime import datetime as _dt

    from config_loader import load_config
    from data.filings import EdgarClient
    from universe import load_universe

    cfg = load_config()
    ua = (cfg.get("edgar", {}) or {}).get("user_agent")
    if not ua:
        pytest.skip("no EDGAR user_agent configured (run on-host)")
    now = _dt.now(UTC)
    fd = FundamentalsData(cache=None, edgar=EdgarClient(ua, cache_dir=cfg.get("cache", {}).get("dir", "data/cache")),
                          fetch_end=now, ua=ua, max_raw_age_days=7)
    regressions = []
    for sym in load_universe(cfg).symbols:
        v2 = fd.corpus_asof(sym, now)["status"]
        v1 = _V1_STATUS.get(sym, "empty")  # an unbaselined (newly-admitted) name cannot regress below empty
        if _RANK[v2] < _RANK[v1]:
            regressions.append(f"{sym}: {v1} -> {v2}")
    assert not regressions, f"status regressions vs v1 baseline: {regressions}"
