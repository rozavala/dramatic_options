"""Narrative scorer: determinism, monotonicity, robust components dominate lexicon."""

from datetime import UTC, datetime, timedelta

from narrative import score_narrative

PARAMS = {"count_window_days": 21, "baseline_window_days": 126, "ewma_span_days": 10,
          "lexicon_weight": 0.15}
AS_OF = datetime(2023, 6, 1, tzinfo=UTC)


def _news(days_ago_list, headline="news"):
    return [{"ts": (AS_OF - timedelta(days=d)).isoformat(), "headline": headline,
             "source": "x", "symbols": ["JOBY"]} for d in days_ago_list]


def test_more_recent_coverage_raises_score():
    quiet = score_narrative("JOBY", _news([2, 40, 80]), AS_OF, PARAMS)
    loud = score_narrative("JOBY", _news([1, 2, 3, 4, 5, 6, 7]), AS_OF, PARAMS)
    assert loud.count_recent > quiet.count_recent
    assert loud.score > quiet.score


def test_deterministic():
    recs = _news([1, 5, 10, 30])
    a = score_narrative("JOBY", recs, AS_OF, PARAMS)
    b = score_narrative("JOBY", recs, AS_OF, PARAMS)
    assert a.score == b.score


def test_empty_news_is_low_not_crash():
    s = score_narrative("JOBY", [], AS_OF, PARAMS)
    assert s.count_recent == 0
    assert s.score is not None


def test_breadth_counts_distinct_days():
    s = score_narrative("JOBY", _news([1, 1, 1]), AS_OF, PARAMS)  # 3 articles, same day
    assert s.breadth is not None and s.breadth <= 1.0 / PARAMS["count_window_days"] + 1e-9
