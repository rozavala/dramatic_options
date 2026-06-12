"""§9 evidence-grounding corpus — extraction shapes, PIT pick rule, freshness (offline).

Every numeric assertion is HAND-CHECKED against tests/fixtures/companyfacts_mini.json
(the PREREG_CONVEXITY_CALIBRATION §6 rule): revenue 2025 TTM = 120+140+160+180 = 600M vs
year-ago TTM = 100(derived Q4-23)+110+120+130 = 460M → ttm_yoy 0.3043; Q3-25 qtr_yoy
180/130−1 = 0.3846; accel vs Q1-25 (140/110−1 = 0.2727) = 0.1119; gross margin Q3-25
(180−99)/180 = 45.0% vs Q3-24 (130−76)/130 = 41.54% → Δ +3.46pts; capex Q3-25 = 66−40 = 26M
vs Q3-24 = 36−22 = 14M → 0.8571; RPO 290/200−1 = 0.45.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from data.fundamentals import (
    CONCEPT_TAGS,
    FundamentalsData,
    _pick_tag,
    _pit_dedup,
    _ttm_at,
    corpus_lines,
    quarterly_income_series,
    ytd_cashflow_series,
)

FIXTURE = Path(__file__).parent / "fixtures" / "companyfacts_mini.json"
USG = json.loads(FIXTURE.read_text())["facts"]["us-gaap"]
AS_OF = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)


def _by(lines, concept, metric):
    return next(ln for ln in lines if ln["concept"] == concept and ln["metric"] == metric)


# ── corpus end-to-end (hand-checked values) ───────────────────────────────────

def test_corpus_lines_hand_checked():
    lines = corpus_lines(USG, AS_OF)
    assert _by(lines, "revenue", "ttm_yoy")["value"] == 0.3043
    assert _by(lines, "revenue", "ttm_yoy")["latest_musd"] == 600.0
    assert _by(lines, "revenue", "ttm_yoy")["base_musd"] == 460.0
    assert _by(lines, "revenue", "qtr_yoy")["value"] == 0.3846
    assert _by(lines, "revenue", "qtr_yoy_accel")["value"] == 0.1119
    gm = _by(lines, "gross_margin", "delta_pts")
    assert gm["value"] == 3.46 and gm["latest_musd"] == 45.0 and gm["base_musd"] == 41.5
    assert _by(lines, "capex", "qtr_yoy")["value"] == 0.8571
    assert _by(lines, "rpo", "yoy")["value"] == 0.45
    # every line carries BOTH dates (staleness must be self-describing)
    assert all(ln["period_end"] and ln["filed"] for ln in lines)


# ── shape (i): Q4 derivation ─────────────────────────────────────────────────

def test_q4_derived_from_fy_with_pit_correct_filed():
    _tag, series = _pick_tag(USG, CONCEPT_TAGS["revenue"], AS_OF)
    q = quarterly_income_series(series)
    q4_24 = next(p for p in q if p["end"] == "2024-12-31")
    # 480 − (110 + 120[amended] + 130) = 120; filed = max(FY 2025-02-20, inputs)
    assert q4_24["val"] == 120e6 and q4_24["filed"] == "2025-02-20"
    q4_23 = next(p for p in q if p["end"] == "2023-12-31")
    assert q4_23["val"] == 100e6


# ── shape (ii): YTD differencing ─────────────────────────────────────────────

def test_ytd_cashflow_differencing():
    _tag, series = _pick_tag(USG, CONCEPT_TAGS["capex"], AS_OF)
    q = ytd_cashflow_series(series)
    assert [p["val"] for p in q] == [10e6, 12e6, 14e6, 16e6, 18e6, 22e6, 26e6]


# ── PIT: amendment pick rule + same-day boundary ─────────────────────────────

def test_amendment_read_time_pick():
    raw = [{"start": "2024-04-01", "end": "2024-06-30", "val": 115e6, "filed": "2024-08-09"},
           {"start": "2024-04-01", "end": "2024-06-30", "val": 120e6, "filed": "2025-01-15"}]
    before = _pit_dedup(raw, datetime(2024, 12, 31, tzinfo=UTC))
    after = _pit_dedup(raw, datetime(2025, 1, 16, tzinfo=UTC))
    assert before[0]["val"] == 115e6   # the original is NOT erased from an earlier read
    assert after[0]["val"] == 120e6    # max-filed ≤ as_of wins


def test_same_day_boundary_t2000z():
    raw = [{"start": "2025-07-01", "end": "2025-09-30", "val": 1e9, "filed": "2025-11-07"}]
    at_1945 = _pit_dedup(raw, datetime(2025, 11, 7, 19, 45, tzinfo=UTC))
    at_2030 = _pit_dedup(raw, datetime(2025, 11, 7, 20, 30, tzinfo=UTC))
    assert at_1945 == [] and len(at_2030) == 1  # invisible to the 19:45 UTC L1, by convention


# ── stable tag per name ──────────────────────────────────────────────────────

def test_stable_tag_most_coverage_wins():
    tag, series = _pick_tag(USG, CONCEPT_TAGS["revenue"], AS_OF)
    assert tag == "RevenueFromContractWithCustomerExcludingAssessedTax"  # decoy (2 periods) loses
    assert len(series) > 2


# ── guards ───────────────────────────────────────────────────────────────────

def test_ttm_refuses_non_consecutive_window():
    pts = [{"start": "2024-01-01", "end": "2024-03-31", "val": 1.0, "filed": "x"},
           {"start": "2024-04-01", "end": "2024-06-30", "val": 1.0, "filed": "x"},
           {"start": "2024-07-01", "end": "2024-09-30", "val": 1.0, "filed": "x"},
           {"start": "2025-01-01", "end": "2025-03-31", "val": 1.0, "filed": "x"}]  # gap (no Q4)
    assert _ttm_at(pts, "2025-03-31") is None


def test_denominator_floor_omits_line():
    usg = {"RevenueRemainingPerformanceObligation": {"units": {"USD": [
        {"end": "2024-09-30", "val": 5e6, "filed": "2024-11-08"},    # base below the 10M floor
        {"end": "2025-09-30", "val": 50e6, "filed": "2025-11-07"},
    ]}}}
    assert corpus_lines(usg, AS_OF) == []


# ── freshness policy (§4) ────────────────────────────────────────────────────

class _Resp:
    def __init__(self, status_code, text):
        self.status_code, self.text = status_code, text

    def json(self):
        return json.loads(self.text)


class _Sess:
    def __init__(self, resp):
        self.resp, self.calls = resp, 0

    def get(self, *a, **k):
        self.calls += 1
        return self.resp


def _fd(tmp_path, *, session=None, ua="", max_age=None):
    return FundamentalsData(cache=None, edgar=None, fetch_end=AS_OF, ua=ua,
                            cache_dir=tmp_path, session=session,
                            cik_overrides={"MINI": "9999999"}, max_raw_age_days=max_age)


def test_raw_fresh_default_never_refetches(tmp_path):
    raw_dir = tmp_path / "xbrl_raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "CIK0009999999.json").write_text(FIXTURE.read_text())
    sess = _Sess(_Resp(200, '{"facts": {}}'))
    fd = _fd(tmp_path, session=sess, ua="t@t")  # max_age None = old behavior
    raw = fd._raw_fresh("0009999999")
    assert raw["entityName"] == "MINIATURE TEST CO" and sess.calls == 0


def test_raw_fresh_validates_before_rename(tmp_path):
    raw_dir = tmp_path / "xbrl_raw"
    raw_dir.mkdir(parents=True)
    good = FIXTURE.read_text()
    (raw_dir / "CIK0009999999.json").write_text(good)
    # 200-OK SEC error page (no 'facts') must NOT clobber the good raw → stale fallback.
    fd = _fd(tmp_path, session=_Sess(_Resp(200, '{"error": "throttled"}')), ua="t@t", max_age=0)
    raw = fd._raw_fresh("0009999999", force_refresh=True)
    assert raw["entityName"] == "MINIATURE TEST CO"
    assert (raw_dir / "CIK0009999999.json").read_text() == good  # file untouched


def test_raw_fresh_refetch_replaces_and_force_refresh(tmp_path):
    raw_dir = tmp_path / "xbrl_raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "CIK0009999999.json").write_text('{"facts": {"us-gaap": {}}, "entityName": "OLD"}')
    fresh = '{"facts": {"us-gaap": {}}, "entityName": "NEW"}'
    sess = _Sess(_Resp(200, fresh))
    fd = _fd(tmp_path, session=sess, ua="t@t", max_age=7)
    assert fd._raw_fresh("0009999999")["entityName"] == "OLD"      # young file, no refetch
    assert fd._raw_fresh("0009999999", force_refresh=True)["entityName"] == "NEW"  # event forces
    assert json.loads((raw_dir / "CIK0009999999.json").read_text())["entityName"] == "NEW"


def test_corpus_asof_fail_soft_and_status(tmp_path):
    raw_dir = tmp_path / "xbrl_raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "CIK0009999999.json").write_text(FIXTURE.read_text())
    fd = _fd(tmp_path)
    out = fd.corpus_asof("MINI", AS_OF)
    assert out["status"] == "ok" and out["n_lines"] == 6
    none = _fd(tmp_path).corpus_asof("UNKNOWN", AS_OF)  # no CIK → empty, never raises
    assert none == {"lines": [], "status": "empty", "n_lines": 0}
