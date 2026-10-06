"""News adapter: normalization, as-of filtering, coverage audit, fetch-and-cache path."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from data.cache import CacheMiss, PointInTimeCache
from data.news import NewsData, _news_records


class _FakeNewsSet:
    def __init__(self, items):
        self.data = {"news": items}
        self.next_page_token = None


def _article(ts, headline, source="Benzinga"):
    return SimpleNamespace(
        created_at=datetime.fromisoformat(ts).replace(tzinfo=UTC),
        headline=headline, source=source, symbols=["JOBY"], id=hash(ts) & 0xFFFF,
    )


def test_news_records_normalizes_objects():
    ns = _FakeNewsSet([_article("2023-01-01T12:00:00", "JOBY wins contract")])
    recs = _news_records(ns, "JOBY")
    assert recs[0]["headline"] == "JOBY wins contract"
    assert recs[0]["ts"].startswith("2023-01-01")


class _FakeClient:
    def __init__(self, items):
        self.items = items
        self.calls = 0

    def get_news(self, symbols, start, end=None, limit=50000):
        self.calls += 1
        return _FakeNewsSet(self.items)


def _prewarmed(tmp_path):
    cache = PointInTimeCache(tmp_path)
    end = datetime.fromisoformat("2023-12-31").replace(tzinfo=UTC)
    recs = _news_records(_FakeNewsSet([
        _article("2022-03-01T10:00:00", "a"),
        _article("2022-09-01T10:00:00", "b"),
        _article("2023-05-01T10:00:00", "c"),
    ]), "JOBY")
    cache.write("news", "JOBY", recs, coverage_from=datetime(2022, 1, 1, tzinfo=UTC),
                coverage_through=end)
    return NewsData(cache, client=None, fetch_start=datetime(2022, 1, 1, tzinfo=UTC), fetch_end=end)


def test_headlines_asof_drops_future(tmp_path):
    nd = _prewarmed(tmp_path)
    got = nd.headlines_asof("JOBY", datetime.fromisoformat("2022-12-31").replace(tzinfo=UTC))
    assert [r["headline"] for r in got] == ["a", "b"]


def test_coverage_by_year(tmp_path):
    nd = _prewarmed(tmp_path)
    assert nd.coverage_by_year("JOBY") == {2022: 2, 2023: 1}


def test_fetch_and_cache_when_online(tmp_path):
    cache = PointInTimeCache(tmp_path)
    end = datetime(2023, 1, 1, tzinfo=UTC)
    client = _FakeClient([_article("2022-06-01T10:00:00", "x")])
    nd = NewsData(cache, client=client, fetch_start=datetime(2022, 1, 1, tzinfo=UTC), fetch_end=end)
    nd.headlines_asof("JOBY", datetime(2022, 7, 1, tzinfo=UTC))
    assert client.calls == 1
    # second read is served from cache (no second fetch)
    nd.headlines_asof("JOBY", end - timedelta(days=1))
    assert client.calls == 1


def test_headlines_asof_clamps_live_forward_drift(tmp_path):
    # THE LIVE CASE (regression): the council's as_of is a strictly later clock.now() than this
    # provider's fetch_end. A bare read would CacheMiss (as_of > coverage_through) and the caller
    # would silently drop ALL headlines; the online clamp returns everything through fetch_end.
    nd = _prewarmed(tmp_path)  # online cache; fetch_end = coverage_through = 2023-12-31
    got = nd.headlines_asof("JOBY", datetime(2023, 12, 31, tzinfo=UTC) + timedelta(seconds=5))
    assert [r["headline"] for r in got] == ["a", "b", "c"]  # all headlines, not empty


def test_headlines_asof_offline_keeps_coverage_tripwire(tmp_path):
    # Offline/backtest must NOT clamp — an as_of beyond coverage still raises (widen-your-fetch;
    # the cache.py contract against silently truncating a point-in-time replay).
    _prewarmed(tmp_path)  # writes news/JOBY via an online cache (coverage_through 2023-12-31)
    offline = PointInTimeCache(tmp_path, offline=True)
    nd = NewsData(offline, client=None, fetch_start=datetime(2022, 1, 1, tzinfo=UTC),
                  fetch_end=datetime(2023, 12, 31, tzinfo=UTC))
    with pytest.raises(CacheMiss):
        nd.headlines_asof("JOBY", datetime(2024, 6, 1, tzinfo=UTC))
