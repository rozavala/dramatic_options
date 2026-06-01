"""Snapshot accrual: compact serialization + append-only persistence into the PIT cache."""

from datetime import UTC, date, datetime

from convexity_data import SNAPSHOT_SOURCE, persist_chain_snapshot, snapshot_record
from convexity_gate import Contract
from data.cache import PointInTimeCache

EXP = date(2026, 9, 30)


def _chain():
    return [
        Contract("FCXc", EXP, "C", 56.0, bid=2.0, ask=2.1, iv=0.40, oi=500),
        Contract("FCXw", EXP, "C", 70.0, bid=0.5, ask=0.6, iv=0.43, oi=300),
        Contract("FCXn", EXP, "C", 60.0, bid=1.0, ask=1.1, iv=None, oi=100),  # no IV → dropped
    ]


def test_snapshot_record_keeps_only_iv_surface():
    rec = snapshot_record("FCX", _chain(), 45.0, datetime(2026, 5, 31, tzinfo=UTC))
    assert rec["symbol"] == "FCX"
    assert rec["underlying_price"] == 45.0
    assert rec["n_contracts"] == 3
    assert len(rec["surface"]) == 2  # the iv=None contract is dropped
    assert {s["strike"] for s in rec["surface"]} == {56.0, 70.0}
    assert "ts" in rec and rec["surface"][0]["iv"] == 0.40


def test_persist_appends_across_cycles(tmp_path):
    cache = PointInTimeCache(tmp_path)
    d1 = datetime(2026, 5, 31, tzinfo=UTC)
    d2 = datetime(2026, 6, 1, tzinfo=UTC)
    persist_chain_snapshot(cache, "FCX", _chain(), 45.0, d1)
    persist_chain_snapshot(cache, "FCX", _chain(), 46.0, d2)
    recs = cache.read_between(SNAPSHOT_SOURCE, "FCX", None, d2)
    assert len(recs) == 2  # appended, not overwritten
    assert [r["underlying_price"] for r in recs] == [45.0, 46.0]
    # coverage widened to span both days
    assert cache.covers(SNAPSHOT_SOURCE, "FCX", d1, d2)


def test_persist_first_write_has_coverage(tmp_path):
    cache = PointInTimeCache(tmp_path)
    d1 = datetime(2026, 5, 31, tzinfo=UTC)
    persist_chain_snapshot(cache, "FCX", _chain(), 45.0, d1)
    recs = cache.read_between(SNAPSHOT_SOURCE, "FCX", None, d1)
    assert len(recs) == 1


def test_persist_same_day_replaces_not_stacks(tmp_path):
    cache = PointInTimeCache(tmp_path)
    morning = datetime(2026, 5, 31, 14, 0, tzinfo=UTC)
    afternoon = datetime(2026, 5, 31, 20, 0, tzinfo=UTC)
    persist_chain_snapshot(cache, "FCX", _chain(), 45.0, morning)
    persist_chain_snapshot(cache, "FCX", _chain(), 46.5, afternoon)
    recs = cache.read_between(SNAPSHOT_SOURCE, "FCX", None, afternoon)
    assert len(recs) == 1  # same day → replaced
    assert recs[0]["underlying_price"] == 46.5  # the later snapshot won
