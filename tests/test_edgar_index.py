"""FSSD §8a 424B5 enumerator: full-index parse, accession dedup, window filter, caching."""

from datetime import UTC, datetime

from dramatic_options.data.cache import PointInTimeCache
from dramatic_options.data.edgar_index import (
    SOURCE,
    EdgarIndex,
    month_key,
    parse_form_index,
)

# Two quarters of synthetic full-index text in the real fixed-width-ish layout. Includes
# non-424B5 forms (must be ignored), a company name containing digits/commas (must not
# break the CIK/date anchors), and the same accession twice across quarters (dedup).
_HEADER = (
    "Description:           Master Index of EDGAR Dissemination Feed by Form Type\n"
    "Form Type   Company Name                                                  CIK"
    "         Date Filed  File Name\n"
    "----------------------------------------------------------------------------\n"
)
_Q1 = _HEADER + (
    "424B5            ACADIA REALTY TRUST                                           "
    "899629      2022-03-02  edgar/data/899629/0001104659-22-028897.txt\n"
    "424B5            ADIAL 360 PHARMA, INC.                                        "
    "1513525     2022-02-14  edgar/data/1513525/0001213900-22-007602.txt\n"
    "8-K              SOME OTHER CO                                                 "
    "111111      2022-02-01  edgar/data/111111/0000000000-22-000001.txt\n"
    "424B3            NOT A TAKEDOWN INC                                            "
    "222222      2022-02-03  edgar/data/222222/0000000000-22-000002.txt\n"
)
_Q2 = _HEADER + (
    "424B5            NEWCO ENERGY INC                                              "
    "333333      2022-05-10  edgar/data/333333/0001000000-22-000010.txt\n"
    # duplicate accession of ACADIA (cross-quarter dedup guard)
    "424B5            ACADIA REALTY TRUST                                           "
    "899629      2022-03-02  edgar/data/899629/0001104659-22-028897.txt\n"
)


def test_parse_only_424b5_and_fields():
    recs = parse_form_index(_Q1, form="424B5")
    assert [r["accession"] for r in recs] == [
        "0001104659-22-028897",
        "0001213900-22-007602",
    ]
    r = recs[0]
    assert r["cik"] == "0000899629"  # zero-padded to 10
    assert r["company"] == "ACADIA REALTY TRUST"
    assert r["date_filed"] == "2022-03-02"
    assert r["ts"] == "2022-03-02T20:00:00+00:00"  # conservative post-close
    # the digit/comma company name must not corrupt the CIK anchor
    assert recs[1]["cik"] == "0001513525"
    assert recs[1]["company"] == "ADIAL 360 PHARMA, INC."


class _FakeEdgar:
    def __init__(self, by_quarter):
        self._by_quarter = by_quarter

    def fetch_form_index(self, year, quarter):
        return self._by_quarter[(year, quarter)]


def test_enumerate_dedups_and_windows(tmp_path):
    cache = PointInTimeCache(tmp_path)
    idx = EdgarIndex(
        cache,
        edgar=_FakeEdgar({(2022, 1): _Q1, (2022, 2): _Q2}),
        cache_dir=tmp_path,
    )
    events = idx.enumerate_events(
        datetime(2022, 1, 1, tzinfo=UTC), datetime(2022, 6, 30, tzinfo=UTC)
    )
    accs = [e["accession"] for e in events]
    # 2 unique from Q1 + 1 new from Q2; the duplicate ACADIA in Q2 is dropped
    assert accs == [
        "0001213900-22-007602",  # 2022-02-14
        "0001104659-22-028897",  # 2022-03-02
        "0001000000-22-000010",  # 2022-05-10
    ]
    # distinct calendar months (the FSSD resampling unit)
    assert sorted({month_key(e["ts"]) for e in events}) == ["2022-02", "2022-03", "2022-05"]


def test_enumerate_filters_to_window(tmp_path):
    cache = PointInTimeCache(tmp_path)
    idx = EdgarIndex(cache, edgar=_FakeEdgar({(2022, 1): _Q1, (2022, 2): _Q2}), cache_dir=tmp_path)
    # window excludes May → NEWCO drops out
    events = idx.enumerate_events(
        datetime(2022, 2, 1, tzinfo=UTC), datetime(2022, 3, 31, tzinfo=UTC)
    )
    assert {e["accession"] for e in events} == {
        "0001104659-22-028897",
        "0001213900-22-007602",
    }


def test_enumerate_caches_to_point_in_time(tmp_path):
    cache = PointInTimeCache(tmp_path)
    idx = EdgarIndex(cache, edgar=_FakeEdgar({(2022, 1): _Q1, (2022, 2): _Q2}), cache_dir=tmp_path)
    idx.enumerate_events(datetime(2022, 1, 1, tzinfo=UTC), datetime(2022, 6, 30, tzinfo=UTC))
    # the deduped event list is in the point-in-time cache under SOURCE/424B5 (read within
    # the written coverage high-water mark, not past it)
    stored = cache.read(SOURCE, "424B5", datetime(2022, 6, 30, tzinfo=UTC))
    assert len(stored) == 3

    # determinism: a second enumerate over the same window hits the cache-reuse path and must
    # return the identical event set (the boundary-windowing bug regression guard)
    again = idx.enumerate_events(datetime(2022, 1, 1, tzinfo=UTC), datetime(2022, 6, 30, tzinfo=UTC))
    assert [r["accession"] for r in again] == [
        "0001213900-22-007602",
        "0001104659-22-028897",
        "0001000000-22-000010",
    ]
