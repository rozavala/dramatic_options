"""FINRA SI: publication-lag no-lookahead guard, parse, si% math, as-of read."""

from datetime import UTC, datetime

from dramatic_options.data.cache import PointInTimeCache
from dramatic_options.data.finra_si import (
    SOURCE,
    FinraShortInterest,
    parse_si_records,
    publication_date,
    si_pct_of_shares,
)

_ROWS = [
    {"symbolCode": "ZZZ", "settlementDate": "2022-03-15",
     "currentShortPositionQuantity": 1000000, "averageDailyVolumeQuantity": 200000,
     "daysToCoverQuantity": 5.0},
    {"symbolCode": "ZZZ", "settlementDate": "2022-03-31",
     "currentShortPositionQuantity": 1200000, "averageDailyVolumeQuantity": 210000,
     "daysToCoverQuantity": 5.7},
    {"symbolCode": "ZZZ", "settlementDate": "",  # dropped (no settlement date)
     "currentShortPositionQuantity": 999},
]


def test_publication_date_is_settlement_plus_lag():
    assert publication_date("2022-03-15", pub_lag_days=14).startswith("2022-03-29")


def test_parse_drops_bad_rows_and_timestamps_by_publication():
    recs = parse_si_records(_ROWS, pub_lag_days=14)
    assert len(recs) == 2
    assert recs[0]["settlement_date"] == "2022-03-15"
    assert recs[0]["ts"].startswith("2022-03-29")  # +14d publication
    assert recs[0]["si_shares"] == 1000000.0
    assert recs[0]["days_to_cover"] == 5.0


def test_si_pct_of_shares():
    assert si_pct_of_shares(1_000_000, 10_000_000) == 0.1
    assert si_pct_of_shares(1_000_000, 0) is None
    assert si_pct_of_shares(None, 10) is None


def test_si_asof_respects_publication_lag(tmp_path):
    """An SI print settled 2022-03-31 must be INVISIBLE until its +14d publication date."""
    cache = PointInTimeCache(tmp_path)
    fsi = FinraShortInterest(
        cache, fetch_start=datetime(2022, 1, 1, tzinfo=UTC),
        fetch_end=datetime(2022, 12, 31, tzinfo=UTC), pub_lag_days=14, cache_dir=tmp_path,
    )
    # seed the cache directly (offline) with parsed records
    recs = parse_si_records(_ROWS, pub_lag_days=14)
    cache.write(SOURCE, "ZZZ", recs,
                coverage_from=datetime(2022, 1, 1, tzinfo=UTC),
                coverage_through=datetime(2022, 12, 31, tzinfo=UTC))
    fsi.cache.offline = True  # prevent any refetch; rely on seeded cache

    # just after the 03-31 settlement but BEFORE its 04-14 publication → see only the 03-15 print
    early = fsi.si_asof("ZZZ", datetime(2022, 4, 5, tzinfo=UTC))
    assert early is not None and early["settlement_date"] == "2022-03-15"
    # after publication of the 03-31 print → see it
    late = fsi.si_asof("ZZZ", datetime(2022, 4, 20, tzinfo=UTC))
    assert late is not None and late["settlement_date"] == "2022-03-31"
