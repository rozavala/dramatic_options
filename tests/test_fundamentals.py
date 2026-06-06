"""Fundamentals (k=4): quarterly extraction, TTM YoY, point-in-time filed filtering, floor."""

from datetime import UTC, datetime

from dramatic_options.data.fundamentals import extract_quarterly_revenue, revenue_yoy


def _q(start, end, val, filed):
    return {"start": start, "end": end, "val": val, "filed": filed}


def _facts(points, concept="RevenueFromContractWithCustomerExcludingAssessedTax"):
    return {"facts": {"us-gaap": {concept: {"units": {"USD": points}}}}}


# 8 consecutive quarters, revenue stepping up; year-2 TTM > year-1 TTM.
Q = [
    _q("2022-01-01", "2022-03-31", 100, "2022-05-01"),
    _q("2022-04-01", "2022-06-30", 110, "2022-08-01"),
    _q("2022-07-01", "2022-09-30", 120, "2022-11-01"),
    _q("2022-10-01", "2022-12-31", 130, "2023-02-01"),
    _q("2023-01-01", "2023-03-31", 150, "2023-05-01"),
    _q("2023-04-01", "2023-06-30", 165, "2023-08-01"),
    _q("2023-07-01", "2023-09-30", 180, "2023-11-01"),
    _q("2023-10-01", "2023-12-31", 200, "2024-02-01"),
]


def test_extract_drops_annual_durations_and_dedups_amendments():
    pts = list(Q) + [
        _q("2022-01-01", "2022-12-31", 460, "2023-02-01"),       # annual (FY) → dropped
        _q("2022-01-01", "2022-03-31", 105, "2022-05-15"),       # amendment of Q1 → wins
    ]
    out = extract_quarterly_revenue(_facts(pts))
    assert len(out) == 8                       # 8 quarters, annual excluded
    q1 = next(p for p in out if p["end"] == "2022-03-31")
    assert q1["val"] == 105.0                   # later-filed amendment wins


def test_revenue_yoy_growth():
    pts = extract_quarterly_revenue(_facts(Q))
    g = revenue_yoy(pts, datetime(2024, 3, 1, tzinfo=UTC), min_base=10)
    # TTM 2023 = 150+165+180+200 = 695; TTM 2022 = 100+110+120+130 = 460; 695/460-1 ≈ 0.511
    assert abs(g - (695 / 460 - 1)) < 1e-6


def test_point_in_time_filed_filter():
    pts = extract_quarterly_revenue(_facts(Q))
    # As of 2023-06-01 only quarters filed by then are visible → <8 → None (no full YoY yet).
    assert revenue_yoy(pts, datetime(2023, 6, 1, tzinfo=UTC), min_base=10) is None
    # As of 2024-03-01 all 8 are visible → growth computable.
    assert revenue_yoy(pts, datetime(2024, 3, 1, tzinfo=UTC), min_base=10) is not None


def test_materiality_floor_excludes_tiny_base():
    pts = extract_quarterly_revenue(_facts(Q))
    # year-ago TTM = 460; require min_base above it → None (pre-revenue-style exclusion)
    assert revenue_yoy(pts, datetime(2024, 3, 1, tzinfo=UTC), min_base=10_000) is None


def test_too_few_quarters_returns_none():
    pts = extract_quarterly_revenue(_facts(Q[:5]))
    assert revenue_yoy(pts, datetime(2024, 3, 1, tzinfo=UTC), min_base=10) is None
