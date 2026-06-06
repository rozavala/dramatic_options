"""XBRL shares-out: fallback chain (PLTR public-float case), as-of, supply delta + subtype."""

from datetime import UTC, datetime

from dramatic_options.data.shares_out import (
    extract_shares_points,
    shares_out_asof,
    shares_out_delta,
)


def _facts(*, dei_shares=None, gaap_shares=None, public_float=None):
    facts: dict = {"facts": {"dei": {}, "us-gaap": {}}}
    if dei_shares is not None:
        facts["facts"]["dei"]["EntityCommonStockSharesOutstanding"] = {"units": {"shares": dei_shares}}
    if gaap_shares is not None:
        facts["facts"]["us-gaap"]["CommonStockSharesOutstanding"] = {"units": {"shares": gaap_shares}}
    if public_float is not None:
        facts["facts"]["dei"]["EntityPublicFloat"] = {"units": {"USD": public_float}}
    return facts


def test_prefers_real_share_count_over_float_proxy():
    facts = _facts(
        dei_shares=[{"end": "2022-03-31", "val": 5_000_000, "filed": "2022-04-15"}],
        public_float=[{"end": "2022-03-31", "val": 90_000_000, "filed": "2022-04-15"}],
    )
    pts = extract_shares_points(facts)
    val, src = shares_out_asof(pts, datetime(2022, 6, 1, tzinfo=UTC))
    assert val == 5_000_000
    assert "EntityCommonStockSharesOutstanding" in src


def test_falls_back_to_public_float_over_price_when_shares_absent():
    # the PLTR case: only EntityPublicFloat present (0 share-count points)
    facts = _facts(public_float=[{"end": "2022-03-31", "val": 100_000_000, "filed": "2022-04-15"}])
    pts = extract_shares_points(facts)
    val, src = shares_out_asof(pts, datetime(2022, 6, 1, tzinfo=UTC), price=10.0)
    assert val == 10_000_000  # 100M USD / $10
    assert "EntityPublicFloat÷price" in src
    # without a price the proxy can't be converted → None
    val2, _ = shares_out_asof(pts, datetime(2022, 6, 1, tzinfo=UTC), price=None)
    assert val2 is None


def test_asof_is_point_in_time_on_filed_date():
    facts = _facts(dei_shares=[
        {"end": "2022-03-31", "val": 5_000_000, "filed": "2022-04-15"},
        {"end": "2022-06-30", "val": 6_000_000, "filed": "2022-07-15"},
    ])
    pts = extract_shares_points(facts)
    # before the Q2 filing is public → still the Q1 count
    v1, _ = shares_out_asof(pts, datetime(2022, 7, 1, tzinfo=UTC))
    assert v1 == 5_000_000
    v2, _ = shares_out_asof(pts, datetime(2022, 8, 1, tzinfo=UTC))
    assert v2 == 6_000_000


def test_shares_out_delta_primary_vs_secondary():
    # +20% shares-out across the event → primary (dilutive)
    facts = _facts(dei_shares=[
        {"end": "2022-03-31", "val": 5_000_000, "filed": "2022-04-15"},
        {"end": "2022-09-30", "val": 6_000_000, "filed": "2022-10-15"},
    ])
    pts = extract_shares_points(facts)
    d = shares_out_delta(pts, datetime(2022, 6, 1, tzinfo=UTC))
    assert d["subtype"] == "primary"
    assert abs(d["pct_change"] - 0.2) < 1e-9

    # flat shares-out → secondary (selling holders, no dilution)
    facts2 = _facts(dei_shares=[
        {"end": "2022-03-31", "val": 5_000_000, "filed": "2022-04-15"},
        {"end": "2022-09-30", "val": 5_000_000, "filed": "2022-10-15"},
    ])
    d2 = shares_out_delta(extract_shares_points(facts2), datetime(2022, 6, 1, tzinfo=UTC))
    assert d2["subtype"] == "secondary"
