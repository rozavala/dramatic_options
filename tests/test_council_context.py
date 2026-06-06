"""ContextPack grounding + the early-exit rule (T2)."""

from datetime import UTC, datetime

from dramatic_options.council.context import build_context_pack, synthetic_context_pack
from dramatic_options.themes import Theme

AS_OF = datetime(2026, 6, 1, tzinfo=UTC)
CAND = Theme("copper_electrification", "FCX", "bullish", "unloved industrial tailwind")


class _FakeNews:
    def __init__(self, recs):
        self._recs = recs

    def headlines_asof(self, symbol, as_of):
        return self._recs


def _rec(headline, ts="2026-05-20T12:00:00+00:00"):
    return {"ts": ts, "headline": headline, "source": "x", "symbols": ["FCX"], "id": 1}


def test_numeric_headlines_are_grounded():
    news = _FakeNews([_rec("Copper demand up 12% YoY against tight supply")])
    pack = build_context_pack(CAND, news=news, as_of=AS_OF)
    assert pack.coverage_count == 1 and pack.has_numeric and pack.grounded


def test_non_numeric_headlines_not_grounded():
    news = _FakeNews([_rec("Copper looks interesting say analysts")])
    pack = build_context_pack(CAND, news=news, as_of=AS_OF)
    assert pack.coverage_count == 1 and not pack.has_numeric and not pack.grounded
    assert "INSUFFICIENT" in pack.as_prompt_block() and "NEUTRAL" in pack.as_prompt_block()


def test_empty_coverage_not_grounded():
    pack = build_context_pack(CAND, news=_FakeNews([]), as_of=AS_OF)
    assert pack.coverage_count == 0 and not pack.grounded


def test_old_headlines_filtered_by_lookback():
    news = _FakeNews([_rec("Old 9% move", ts="2025-01-01T00:00:00+00:00")])
    pack = build_context_pack(CAND, news=news, as_of=AS_OF, lookback_days=90)
    assert pack.coverage_count == 0  # outside the 90d window


def test_news_error_is_fail_soft_to_ungrounded():
    class _Boom:
        def headlines_asof(self, symbol, as_of):
            raise RuntimeError("network down")

    pack = build_context_pack(CAND, news=_Boom(), as_of=AS_OF)
    assert not pack.grounded and any("news error" in n for n in pack.notes)


def test_synthetic_pack_is_grounded_and_has_candidate_header():
    pack = synthetic_context_pack(CAND, as_of=AS_OF)
    assert pack.grounded
    block = pack.as_prompt_block()
    assert block.startswith("CANDIDATE: FCX bullish copper_electrification")
