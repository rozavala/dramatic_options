"""Point-in-time cache: record-timestamp read semantics, coverage, lookahead tripwire."""

from datetime import UTC, datetime

import pytest

from dramatic_options.data.cache import CacheMiss, PointInTimeCache


def _dt(s):
    return datetime.fromisoformat(s).replace(tzinfo=UTC)


def _recs():
    return [
        {"ts": "2022-01-01T00:00:00+00:00", "v": 1},
        {"ts": "2022-06-01T00:00:00+00:00", "v": 2},
        {"ts": "2023-01-01T00:00:00+00:00", "v": 3},
    ]


def test_read_filters_on_record_timestamp_not_fetch_time(tmp_path):
    c = PointInTimeCache(tmp_path)
    c.write("news", "JOBY", _recs(), coverage_from=_dt("2021-01-01"), coverage_through=_dt("2023-12-31"))
    # One wide fetch serves many as_ofs by filtering on the records' own timestamps.
    assert [r["v"] for r in c.read("news", "JOBY", _dt("2022-03-01"))] == [1]
    assert [r["v"] for r in c.read("news", "JOBY", _dt("2022-12-31"))] == [1, 2]
    assert [r["v"] for r in c.read("news", "JOBY", _dt("2023-06-01"))] == [1, 2, 3]


def test_read_beyond_coverage_is_a_miss(tmp_path):
    c = PointInTimeCache(tmp_path)
    c.write("news", "JOBY", _recs(), coverage_from=_dt("2021-01-01"), coverage_through=_dt("2023-01-15"))
    with pytest.raises(CacheMiss):
        c.read("news", "JOBY", _dt("2024-01-01"))  # past the high-water mark


def test_missing_payload_is_a_miss(tmp_path):
    c = PointInTimeCache(tmp_path)
    with pytest.raises(CacheMiss):
        c.read("news", "NOPE", _dt("2022-01-01"))


def test_offline_cannot_write(tmp_path):
    c = PointInTimeCache(tmp_path, offline=True)
    with pytest.raises(CacheMiss):
        c.write("news", "JOBY", _recs(), coverage_from=_dt("2021-01-01"), coverage_through=_dt("2023-12-31"))


def test_running_max_tracks_and_resets(tmp_path):
    c = PointInTimeCache(tmp_path)
    c.write("news", "JOBY", _recs(), coverage_from=_dt("2021-01-01"), coverage_through=_dt("2023-12-31"))
    c.reset_running_max()
    c.read("news", "JOBY", _dt("2022-03-01"))   # surfaces ts=2022-01-01
    c.read("news", "JOBY", _dt("2022-12-31"))   # surfaces up to 2022-06-01
    assert c.running_max_ts == _dt("2022-06-01")
    c.reset_running_max()
    assert c.running_max_ts is None


def test_read_between_is_label_only_and_ignores_tripwire(tmp_path):
    c = PointInTimeCache(tmp_path)
    c.write("bars", "JOBY", _recs(), coverage_from=_dt("2021-01-01"), coverage_through=_dt("2023-12-31"))
    c.reset_running_max()
    fwd = c.read_between("bars", "JOBY", _dt("2022-03-01"), _dt("2023-12-31"))
    assert [r["v"] for r in fwd] == [2, 3]          # start exclusive, future records returned
    assert c.running_max_ts is None                  # label reads must NOT trip the guard


def test_covers_rejects_stale_narrow_window(tmp_path):
    # Regression: a recent/narrow fetch (coverage_from late) must NOT be treated as covering
    # an earlier backtest window just because coverage_through is recent — that returned a
    # silently-empty series and produced 0 rebalance dates in the audit.
    c = PointInTimeCache(tmp_path)
    recent = [{"ts": "2025-05-01T00:00:00+00:00", "v": 9}]
    c.write("bars", "SPY", recent, coverage_from=_dt("2025-04-01"),
            coverage_through=_dt("2026-05-30"))
    assert c.has_coverage("bars", "SPY", _dt("2024-06-30"))          # upper bound says "yes"…
    assert not c.covers("bars", "SPY", _dt("2022-01-01"), _dt("2024-06-30"))  # …lower bound says NO
    assert c.covers("bars", "SPY", _dt("2025-04-15"), _dt("2026-01-01"))      # within range → covered


def test_offline_replay_is_deterministic(tmp_path):
    c = PointInTimeCache(tmp_path)
    c.write("news", "JOBY", _recs(), coverage_from=_dt("2021-01-01"), coverage_through=_dt("2023-12-31"))
    off = PointInTimeCache(tmp_path, offline=True)
    assert [r["v"] for r in off.read("news", "JOBY", _dt("2023-06-01"))] == [1, 2, 3]
