"""D6 step 1: analyst-coverage history (daily record, same-day merge) and the ~90-day trend label."""

from datetime import UTC, datetime, timedelta

import attention as at
from data.cache import PointInTimeCache

T0 = datetime(2026, 8, 1, 20, 45, tzinfo=UTC)


def test_record_daily_merges_same_day_and_skips_unknowns(tmp_path):
    cache = PointInTimeCache(tmp_path / "c")

    def count_of(s):
        if s == "BAD":
            raise RuntimeError("down")
        return {"AAA": 3, "BBB": 12}.get(s)
    rec = at.record_daily(cache, ["aaa", "BAD", "ZZZ"], count_of, T0)
    assert rec["counts"] == {"AAA": 3}
    at.record_daily(cache, ["BBB"], count_of, T0 + timedelta(hours=1))      # same day: merged, not stacked
    recs = cache.read_between(at.SOURCE, at.KEY, None, T0 + timedelta(hours=2))
    assert len(recs) == 1 and recs[0]["counts"] == {"AAA": 3, "BBB": 12}
    assert at.record_daily(cache, ["ZZZ"], count_of, T0 + timedelta(hours=3)) is None


def test_trend_and_labels(tmp_path):
    cache = PointInTimeCache(tmp_path / "c")
    at.record_daily(cache, ["AAA", "BBB", "CCC"], {"AAA": 2, "BBB": 20, "CCC": 8}.get, T0)
    at.record_daily(cache, ["AAA"], {"AAA": 3}.get, T0 + timedelta(days=40))         # too recent to compare
    later = T0 + timedelta(days=88)
    at.record_daily(cache, ["AAA", "BBB", "CCC"], {"AAA": 5, "BBB": 17, "CCC": 9}.get, later)
    p = at.panel(PointInTimeCache(tmp_path / "c", offline=True), now=later + timedelta(hours=1))
    rows = {r["symbol"]: r for r in p["rows"]}
    assert rows["AAA"]["change"] == 3 and rows["AAA"]["count_then"] == 2 and rows["AAA"]["label"] == "quiet, coverage rising"
    assert rows["BBB"]["label"] == "crowded, coverage falling"
    assert rows["CCC"]["label"] == "covered"
    assert p["status"].startswith("trend live")


def test_empty_panel(tmp_path):
    p = at.panel(PointInTimeCache(tmp_path / "c", offline=True), now=T0)
    assert p["rows"] == [] and p["status"].startswith("trend accruing")
