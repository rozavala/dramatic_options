"""D5 step 1: per-cluster capex-cycle telemetry from XBRL (fiscal-YTD cash-flow facts differenced into quarters)."""

from datetime import UTC, date, datetime, timedelta

import capex_cycle as cc
from data.cache import PointInTimeCache

AS_OF = datetime(2026, 11, 3, 21, 0, tzinfo=UTC)


def _facts(quarterly_by_year: dict[int, list[float]], filed_lag_days: int = 40) -> dict:
    """Calendar-year filer: per year, YTD facts (Q1, H1, 9M, FY) whose differences are the quarterly values."""
    units = []
    for y, qs in quarterly_by_year.items():
        start = date(y, 1, 1)
        ends = [date(y, 3, 31), date(y, 6, 30), date(y, 9, 30), date(y, 12, 31)]
        running = 0.0
        for q, end in zip(qs, ends, strict=False):
            running += q
            units.append({"start": start.isoformat(), "end": end.isoformat(), "val": running,
                          "filed": (end + timedelta(days=filed_lag_days)).isoformat()})
    return {"facts": {"us-gaap": {"PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": units}}}}}


M = 1e6


def test_quarterly_capex_differences_ytd_facts():
    pts = cc.quarterly_capex(_facts({2025: [10 * M, 20 * M, 30 * M, 40 * M]}), AS_OF)
    assert [p["val"] for p in pts] == [10 * M, 20 * M, 30 * M, 40 * M]


def test_name_cycle_yoy_and_two_quarter_lag():
    # 2024 flat 10/q; 2025 steps up to 15/q; 2026 Q1–Q3 at 20/q (Q3 filed 2026-11-09 > AS_OF → not visible)
    f = _facts({2024: [10 * M] * 4, 2025: [15 * M] * 4, 2026: [20 * M] * 3})
    c = cc.name_cycle(cc.quarterly_capex(f, AS_OF))
    assert c["period_end"] == "2026-06-30"
    assert c["ttm_now"] == 70 * M and c["ttm_ago"] == 50 * M          # (15+15+20+20) vs (10+10+15+15)
    assert round(c["yoy"], 4) == 0.4
    assert c["prev_now"] == 60 * M and c["prev_ago"] == 40 * M        # Q4-2025 TTM vs Q4-2024 TTM
    assert round(c["yoy_prev"], 4) == 0.5


def test_cluster_sums_members_and_needs_the_same_basket_for_accel():
    a = {"period_end": "2026-06-30", "ttm_now": 70 * M, "ttm_ago": 50 * M, "yoy": 0.4, "yoy_prev": 0.5,
         "prev_now": 60 * M, "prev_ago": 40 * M}
    b = {"period_end": "2026-06-30", "ttm_now": 30 * M, "ttm_ago": 50 * M, "yoy": -0.4, "yoy_prev": -0.2,
         "prev_now": 40 * M, "prev_ago": 50 * M}
    r = cc.cluster_cycle({"A": a, "B": b, "C": None})
    assert r["n_with_data"] == 2 and r["missing"] == ["C"]
    assert r["yoy"] == 0.0 and r["yoy_prev"] == round(100 / 90 - 1, 4) and r["accel"] == round(-(100 / 90 - 1), 4)
    b_no_prev = {**b, "prev_now": None, "prev_ago": None, "yoy_prev": None}
    assert cc.cluster_cycle({"A": a, "B": b_no_prev})["accel"] is None


def test_record_daily_is_once_per_day_and_fail_soft(tmp_path):
    cache = PointInTimeCache(tmp_path / "cache")
    facts = {"AAA": _facts({2024: [10 * M] * 4, 2025: [15 * M] * 4, 2026: [20 * M] * 3})}

    def facts_of(s):
        if s == "BAD":
            raise RuntimeError("edgar down")
        return facts.get(s)
    cmap = {"power": frozenset({"AAA", "BAD"}), "empty": frozenset({"ZZZ"})}
    rec = cc.record_daily(cache, cmap, facts_of, AS_OF)
    assert rec["clusters"]["power"]["n_with_data"] == 1 and rec["clusters"]["power"]["missing"] == ["BAD"]
    assert rec["clusters"]["power"]["phase"] == "capex boom, slowing"           # +40% YoY, down from +50%
    assert rec["clusters"]["empty"]["phase"] == "no data"
    assert cc.record_daily(cache, cmap, facts_of, AS_OF + timedelta(hours=1)) is None   # same day: skipped
    p = cc.panel(PointInTimeCache(tmp_path / "cache", offline=True), now=AS_OF + timedelta(hours=2))
    assert p["records"] == 1 and [r["cluster"] for r in p["rows"]] == ["empty", "power"]
