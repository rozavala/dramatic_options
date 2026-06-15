"""§9 evidence-grounding integration (PREREG_EVIDENCE_GROUNDING) — the judgment-layer wiring.

Covers the two red-team-load-bearing items (the authenticity-filter interaction #0 and the framer
byte-identity #1), the origin-scoped OR-leg both ways, metric-aware never-raise rendering, the
origin-keyed fill telemetry on the early-exit path, the grader split, the live-wiring forward, and
the §5b contrast report.
"""

from datetime import UTC, datetime, timedelta

import state
from council.context import (
    ContextPack,
    build_context_pack,
    sentinel_context_pack,
    synthetic_context_pack,
)
from council.council import propose
from council.debate import run_candidate
from council.filters import apply_filter
from council.router import FakeRouter
from council.wiring import council_to_themes
from council_health_report import council_l1_health
from grounding_attribution import grounding_attribution_report
from themes import Theme

AS_OF = datetime(2026, 6, 1, tzinfo=UTC)

# Corpus lines shaped EXACTLY like data/fundamentals.py:corpus_lines emits (the three shapes):
REV = {"concept": "revenue", "metric": "ttm_yoy", "value": 0.123, "latest_musd": 1234.5,
       "base_musd": 1099.4, "period_end": "2025-09-30", "filed": "2025-11-01"}
GM = {"concept": "gross_margin", "metric": "delta_pts", "value": 2.3, "latest_musd": 45.2,
      "base_musd": 42.9, "period_end": "2025-09-30", "filed": "2025-11-01"}
ACCEL = {"concept": "revenue", "metric": "qtr_yoy_accel", "value": 0.05, "latest_musd": None,
         "base_musd": None, "period_end": "2025-09-30", "filed": "2025-11-01"}
CAPEX = {"concept": "capex", "metric": "qtr_yoy", "value": 0.30, "latest_musd": 50.0,
         "base_musd": 38.5, "period_end": "2025-09-30", "filed": "2025-11-01"}


class _FakeFund:
    """Mirrors FundamentalsData.corpus_asof: status empty if no lines, ok if ≥3 concepts, else partial."""

    def __init__(self, lines):
        self._lines = lines

    def corpus_asof(self, symbol, as_of, *, force_refresh=False):
        n_concepts = len({ln["concept"] for ln in self._lines})
        status = "empty" if not self._lines else ("ok" if n_concepts >= 3 else "partial")
        return {"lines": self._lines, "status": status, "n_lines": len(self._lines)}


class _Boom:
    def corpus_asof(self, *a, **k):
        raise RuntimeError("SEC down")


class _FakeNews:
    def __init__(self, recs):
        self._recs = recs

    def headlines_asof(self, symbol, as_of):
        return self._recs


def _rec(headline, ts="2026-05-28T12:00:00+00:00"):
    return {"ts": ts, "headline": headline, "source": "x", "id": 1}


def _handseed(thesis="copper supply story without digits"):
    return Theme("copper_supply", "FCX", "bullish", thesis)


def _sentinel(markers, symbol="UEC"):
    return Theme("nuclear_fuel", symbol, "bullish", "discovery hypothesis", source="sentinel", markers=markers)


# ── #0: the authenticity filter must support REAL fundamentals citations ──────────────────────────
def test_filter_supports_real_fundamentals_citation():
    pack = build_context_pack(_handseed(), news=_FakeNews([]), as_of=AS_OF, fundamentals=_FakeFund([REV]))
    assert pack.grounded  # OR-leg
    # An agent quoting the rendered numbers (12.3%, $1234.5M) + the coverage counts must NOT flag.
    conf, res = apply_filter(["revenue ttm grew 12.3% to 1234.5M against 1099.4M"], pack, confidence="MODERATE")
    assert res.flagged == 0 and conf == "MODERATE"


def test_filter_still_flags_an_invented_number():
    pack = build_context_pack(_handseed(), news=_FakeNews([]), as_of=AS_OF, fundamentals=_FakeFund([REV]))
    conf, res = apply_filter(["margins exploded 87.6% on secret orders"], pack, confidence="MODERATE")
    assert res.flagged >= 1 and conf == "LOW"  # 87.6 absent from the enlarged pool → flagged + dampened


# ── #1: the T3 framer's sentinel pack renders byte-identically (no §9 lines) ──────────────────────
def test_framer_sentinel_pack_byte_identical():
    cand = _sentinel({"momentum": 0.5, "rv_slope": 0.3})
    block = sentinel_context_pack(cand, as_of=AS_OF).as_prompt_block()  # the framer call — no corpus
    assert "article(s)" in block          # the pre-§9 NEWS_COVERAGE format
    assert "7d=" not in block             # the new format is absent
    assert "FUNDAMENTALS:" not in block   # no corpus section
    # exact golden (the framer prompt must not drift):
    assert block == (
        "CANDIDATE: UEC bullish nuclear_fuel\n"
        "OPERATOR_THESIS: discovery hypothesis\n"
        "NEWS_COVERAGE: 2 article(s) as of 2026-06-01\n"
        "RECENT_HEADLINES:\n  - momentum +0.500\n  - rv_slope +0.300"
    )


# ── the OR-leg, origin-scoped, both directions ────────────────────────────────────────────────────
def test_or_leg_grounds_thin_news_handseed():
    pack = build_context_pack(_handseed(), news=_FakeNews([]), as_of=AS_OF, fundamentals=_FakeFund([REV]))
    assert pack.coverage_count == 0 and not pack.has_numeric  # thin news
    assert pack.origin == "hand-seed" and pack.grounded       # grounded via the OR-leg


def test_thin_news_handseed_without_fundamentals_not_grounded():
    pack = build_context_pack(_handseed(), news=_FakeNews([]), as_of=AS_OF, fundamentals=_FakeFund([]))
    assert not pack.grounded


def test_sentinel_with_fundamentals_but_no_markers_is_not_grounded():
    # The silent-re-grant guard: a sentinel NEVER OR-legs, even with a full corpus.
    pack = build_context_pack(_sentinel({}), news=None, as_of=AS_OF, fundamentals=_FakeFund([REV, GM]))
    assert pack.fundamentals_present and pack.origin == "sentinel"
    assert not pack.grounded


def test_build_context_pack_sentinel_branch_forwards_fundamentals():
    # R2-#5: the council's sentinels (and the 16-name re-score band) must SEE fundamentals.
    pack = build_context_pack(_sentinel({"momentum": 0.5}), news=None, as_of=AS_OF,
                              fundamentals=_FakeFund([REV]))
    assert pack.origin == "sentinel" and pack.fundamentals == [REV] and pack.grounded  # via markers
    assert "FUNDAMENTALS:" in pack.as_prompt_block()


def test_fundamentals_present_boundary():
    def p(lines):
        return ContextPack("S", "t", "bullish", "u", fundamentals=lines)
    assert p([REV]).fundamentals_present              # 1 revenue line
    assert p([GM, CAPEX]).fundamentals_present         # 2 non-revenue lines
    assert not p([GM]).fundamentals_present            # 1 non-revenue line
    assert not p([dict(GM, value=None)]).fundamentals_present  # value=None lines don't count


# ── metric-aware rendering (the three shapes) + the new NEWS_COVERAGE format + never-raise ────────
def test_render_three_shapes_and_counts():
    pack = ContextPack("FCX", "copper", "bullish", "thesis text", coverage_count=0, has_numeric=False,
                       fundamentals=[REV, GM, ACCEL], news_7d=3, news_90d=12, origin="hand-seed")
    block = pack.as_prompt_block()
    assert "NEWS_COVERAGE: 7d=3 90d=12 (free feed — sparse; low counts are weak evidence)" in block
    assert "- revenue ttm_yoy +12.3% ($1234.5M vs $1099.4M); period 2025-09-30, filed 2025-11-01" in block
    assert "- gross_margin delta_pts +2.3pts (45.2% vs 42.9% margin); period 2025-09-30, filed 2025-11-01" in block
    assert "- revenue qtr_yoy_accel +0.050; period 2025-09-30, filed 2025-11-01" in block


def test_render_never_raises_on_none_value():
    bad = {"concept": "revenue", "metric": "ttm_yoy", "value": None, "latest_musd": 1.0,
           "base_musd": 1.0, "period_end": "x", "filed": "y"}
    pack = ContextPack("S", "t", "bullish", "u", coverage_count=1, has_numeric=True,
                       fundamentals=[bad, REV], news_7d=0, news_90d=0)
    block = pack.as_prompt_block()  # must NOT raise
    assert "ttm_yoy +12.3%" in block and block.count("- revenue") == 1  # the None-value line skipped


# ── fail-soft: a corpus outage degrades to pre-§9 grounding, never raises ─────────────────────────
def test_corpus_outage_is_fail_soft():
    pack = build_context_pack(_handseed(), news=_FakeNews([]), as_of=AS_OF, fundamentals=_Boom())
    assert pack.fundamentals == [] and not pack.grounded  # reverts to the $0-drop baseline (no false grounding)


def test_demo_pack_unchanged_by_s9():
    block = synthetic_context_pack(_handseed(), as_of=AS_OF).as_prompt_block()
    assert "FUNDAMENTALS:" not in block and "article(s)" in block and "7d=" not in block


# ── telemetry rides EVERY path (incl. the empty-corpus early-exit miss), origin-keyed ─────────────
def test_telemetry_on_ungrounded_early_exit():
    pack = build_context_pack(_handseed(), news=_FakeNews([]), as_of=AS_OF, fundamentals=_FakeFund([]))
    assert not pack.grounded
    prop = run_candidate(_handseed(), pack, FakeRouter())  # early-exit, no LLM spend
    assert prop.rationale["fundamentals"] == {"n_lines": 0, "status": "empty", "origin": "hand-seed"}


# ── live wiring: council_to_themes forwards fundamentals to propose (R1-#2) ────────────────────────
class _Clock:
    def now(self):
        return AS_OF


def test_council_to_themes_forwards_fundamentals(monkeypatch, convexity_db):
    captured = {}

    def _spy(candidates, **kw):
        captured["fundamentals"] = kw.get("fundamentals")
        return []

    monkeypatch.setattr("council.wiring.propose", _spy)
    sentinel = object()
    council_to_themes(convexity_db, candidates=[], router=FakeRouter(), config={"council": {}},
                      clock=_Clock(), fundamentals=sentinel, run_id=None)
    assert captured["fundamentals"] is sentinel


def test_propose_threads_fundamentals_to_handseed_or_leg():
    # End-to-end (no live LLM): a thin-news hand-seed deliberates via the OR-leg only when the corpus
    # is threaded through propose; without it, the $0-drop baseline.
    grounded = propose([_handseed()], router=FakeRouter(), config={"council": {"max_candidates": 5}},
                       clock=_Clock(), news=_FakeNews([]), fundamentals=_FakeFund([REV, GM]))
    dropped = propose([_handseed()], router=FakeRouter(), config={"council": {"max_candidates": 5}},
                      clock=_Clock(), news=_FakeNews([]), fundamentals=_FakeFund([]))
    assert grounded[0].rationale.get("dropped") != "ungrounded (no numeric evidence)"
    assert dropped[0].rationale.get("dropped") == "ungrounded (no numeric evidence)"


# ── grader: per-run fill telemetry SPLIT BY ORIGIN ────────────────────────────────────────────────
def test_grader_fundamentals_split_by_origin(convexity_db):
    conn = convexity_db
    rid = state.record_run(conn, mode="PAPER", equity=10000)
    state.update_run_council_health(conn, rid, council_health="ok")
    # two hand-seeds (one empty = a SEC-outage OR-leg miss, one ok) + one thin sentinel
    for sym, origin, n, status in [("FCX", "hand-seed", 0, "empty"), ("NVDA", "hand-seed", 4, "ok"),
                                   ("UEC", "sentinel", 1, "partial")]:
        state.record_council_proposal(
            conn, run_id=rid, as_of="t", theme="x", symbol=sym, direction="bullish",
            conviction="NEUTRAL", status="dropped",
            rationale={"dropped": "x", "fundamentals": {"n_lines": n, "status": status, "origin": origin}})
    fund = council_l1_health(conn, run_id=rid)["fundamentals"]
    assert fund["hand-seed"] == {"n": 2, "median_lines": 2.0, "ok": 1, "partial": 0, "empty": 1}
    assert fund["sentinel"] == {"n": 1, "median_lines": 1, "ok": 0, "partial": 1, "empty": 0}


# ── §5b contrast report: citable gate + a mature include cohort ───────────────────────────────────
class _FakeCache:
    def __init__(self, bars):
        self._bars = bars

    def read_between(self, source, symbol, start, end):
        if source != "bars":
            return []
        return [b for b in self._bars.get(symbol, [])
                if start <= datetime.fromisoformat(b["ts"]) <= end]


class _FakeMarket:
    def __init__(self, cache):
        self.cache = cache


def _daily_bars(symbol, start: datetime, n: int, p0: float, step: float):
    return [{"ts": (start + timedelta(days=i)).isoformat(), "close": p0 + i * step} for i in range(n)]


def test_grounding_attribution_citable_gate_and_mature_cohort(convexity_db):
    conn = convexity_db
    rid = state.record_run(conn, mode="PAPER", equity=10000)
    entry = datetime(2025, 6, 1, tzinfo=UTC)
    now = entry + timedelta(days=200)
    # one INCLUDE (status='proposed'), bullish, with 200 fwd daily bars (≥ h180): +1/day from 100.
    state.record_council_proposal(conn, run_id=rid, as_of=entry.isoformat(), theme="t", symbol="AAA",
                                  direction="bullish", conviction="MODERATE", status="proposed",
                                  rationale={"strategist": {"include": True}})
    bars = {"AAA": [{"ts": entry.isoformat(), "close": 100.0}] + _daily_bars("AAA", entry + timedelta(days=1), 200, 101.0, 1.0)}
    market = _FakeMarket(_FakeCache(bars))
    rep = grounding_attribution_report(conn, market, now=now)
    assert rep["citable"] is False and rep["n_includes"] == 1  # < 10 includes
    inc = rep["cohorts"]["include"]
    assert inc["n_names"] == 1
    # h180: close at the 180th fwd bar (entry+1+179 → 101+179=280) / 100 - 1 = +1.8
    assert inc["horizons"]["h180"]["n"] == 1
    assert abs(inc["horizons"]["h180"]["p95"] - 1.8) < 1e-9
    assert rep["cohorts"]["deliberated_reject"]["n_names"] == 0
