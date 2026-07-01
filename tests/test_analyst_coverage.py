"""§19 analyst-coverage meter — the adapter (``data/analyst_coverage.py``).

Covers the pure bucket-sum, the fetch→PIT-cache→read round-trip, the natural lookahead-safety
(a current snapshot can't leak into an earlier as_of), and every fail-soft path (non-200,
missing analystChart, network error, no session, offline cache) → None."""
from datetime import UTC, datetime, timedelta

from data.analyst_coverage import AnalystCoverageData, sum_analyst_chart
from data.cache import PointInTimeCache

FETCH_END = datetime(2026, 7, 1, tzinfo=UTC)


# ── sum_analyst_chart (pure) ──────────────────────────────────────────────────────────────────────
def test_sum_analyst_chart_sums_buckets():
    # the live AAPL shape, verified against §19's spot-check (47)
    assert sum_analyst_chart({"strongBuy": 22, "buy": 6, "hold": 16, "sell": 2, "strongSell": 1}) == 47


def test_sum_analyst_chart_empty_dict_is_zero():
    assert sum_analyst_chart({}) == 0


def test_sum_analyst_chart_non_dict_is_none():
    # None (thin ADR) / the sibling `analysts` label string / a bare number → unknown, NOT 0 (§19: don't
    # over-read a data gap as a quietness signal).
    assert sum_analyst_chart(None) is None
    assert sum_analyst_chart("Buy") is None
    assert sum_analyst_chart(5) is None


def test_sum_analyst_chart_ignores_nonnumeric_values():
    assert sum_analyst_chart({"strongBuy": 2, "note": "x"}) == 2


# ── a fake stockanalysis session ──────────────────────────────────────────────────────────────────
class _Resp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _Session:
    """Returns a fixed response (or raises a fixed exception) and counts calls."""

    def __init__(self, resp):
        self._resp = resp
        self.calls = 0

    def get(self, url, **kw):
        self.calls += 1
        if isinstance(self._resp, Exception):
            raise self._resp
        return self._resp


def _cache(tmp_path, *, offline=False):
    return PointInTimeCache(tmp_path / "cache", offline=offline)


def _acd(cache, session):
    return AnalystCoverageData(cache, fetch_end=FETCH_END, session=session, rate_limit_per_sec=0)


def _ok(buckets):
    return _Resp(200, {"status": 200, "data": {"analystChart": buckets}})


# ── fetch → cache → read ────────────────────────────────────────────────────────────────────────
def test_count_asof_fetches_sums_and_caches(tmp_path):
    sess = _Session(_ok({"strongBuy": 4}))
    acd = _acd(_cache(tmp_path), sess)
    assert acd.count_asof("GATX", FETCH_END) == 4
    assert acd.count_asof("GATX", FETCH_END) == 4  # served from cache
    assert sess.calls == 1                          # not re-fetched


def test_count_asof_lookahead_safe_before_snapshot(tmp_path):
    # A CURRENT snapshot must never leak back into an earlier as_of (the record ts = fetch_end).
    acd = _acd(_cache(tmp_path), _Session(_ok({"strongBuy": 4})))
    assert acd.count_asof("GATX", FETCH_END - timedelta(days=30)) is None


def test_count_asof_reads_snapshot_when_as_of_drifts_past_fetch_end(tmp_path):
    # THE LIVE CASE (regression): the council's clock.now() (as_of) is a strictly later call than
    # the provider's fetch_end (LiveClock.now() advances). The read must clamp to the snapshot and
    # return the count, NOT CacheMiss → None. Without the min(as_of, fetch_end) clamp the meter
    # would silently never fire in the live loop.
    acd = _acd(_cache(tmp_path), _Session(_ok({"strongBuy": 4})))
    assert acd.count_asof("GATX", FETCH_END + timedelta(seconds=5)) == 4
    assert acd.count_asof("GATX", FETCH_END + timedelta(hours=3)) == 4


# ── fail-soft paths → None ────────────────────────────────────────────────────────────────────────
def test_non_200_is_none_and_left_uncached(tmp_path):
    sess = _Session(_Resp(404, {}))
    acd = _acd(_cache(tmp_path), sess)
    assert acd.count_asof("ZZZZ", FETCH_END) is None
    assert acd.count_asof("ZZZZ", FETCH_END) is None
    assert sess.calls == 2  # a transient/bad response is not cached → retried next run


def test_missing_analystchart_is_none(tmp_path):
    sess = _Session(_Resp(200, {"status": 200, "data": {"analystChart": None}}))  # a thin ADR
    acd = _acd(_cache(tmp_path), sess)
    assert acd.count_asof("SIFY", FETCH_END) is None


def test_bad_envelope_is_none(tmp_path):
    sess = _Session(_Resp(200, {"status": 500}))  # status!=200 in body / no data
    acd = _acd(_cache(tmp_path), sess)
    assert acd.count_asof("AAPL", FETCH_END) is None


def test_network_error_is_fail_soft(tmp_path):
    acd = _acd(_cache(tmp_path), _Session(RuntimeError("connection reset")))
    assert acd.count_asof("AAPL", FETCH_END) is None


def test_no_session_is_no_fetch(tmp_path):
    acd = _acd(_cache(tmp_path), None)  # cache-only mode (demo / offline tests)
    assert acd.count_asof("AAPL", FETCH_END) is None


def test_offline_cache_never_hits_network(tmp_path):
    sess = _Session(_ok({"strongBuy": 4}))
    acd = _acd(_cache(tmp_path, offline=True), sess)
    assert acd.count_asof("GATX", FETCH_END) is None
    assert sess.calls == 0


def test_zero_coverage_caches_and_reads_zero(tmp_path):
    # A genuinely-uncovered name (empty chart → 0) is a real, cacheable count, not None.
    sess = _Session(_ok({}))
    acd = _acd(_cache(tmp_path), sess)
    assert acd.count_asof("TINY", FETCH_END) == 0
    assert acd.count_asof("TINY", FETCH_END) == 0
    assert sess.calls == 1
