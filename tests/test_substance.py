"""Substance scorer: signed weights, EWMA decay, density diagnostic, item mapping."""

from datetime import UTC, datetime, timedelta

from substance import has_events, score_substance

PARAMS = {
    "ewma_span_days": 30,
    "lookback_days": 120,
    "event_weights": {
        "8-K:1.01": 1.0, "8-K:2.02": 0.5, "8-K:3.02": -1.0, "8-K:5.02": -0.5,
        "FORM4": 0.4, "SC 13D": 1.0, "S-1": -0.7, "424B": -0.7,
    },
}
AS_OF = datetime(2024, 1, 1, tzinfo=UTC)


def _f(days_ago, form, items=None):
    return {"ts": (AS_OF - timedelta(days=days_ago)).isoformat(), "form": form,
            "items": items or []}


def test_positive_and_negative_events_signed():
    pos = score_substance("J", [_f(5, "8-K", ["1.01"])], AS_OF, PARAMS)
    neg = score_substance("J", [_f(5, "8-K", ["3.02"])], AS_OF, PARAMS)
    assert pos.score > 0 > neg.score


def test_ewma_decay_older_events_count_less():
    recent = score_substance("J", [_f(2, "8-K", ["1.01"])], AS_OF, PARAMS)
    old = score_substance("J", [_f(90, "8-K", ["1.01"])], AS_OF, PARAMS)
    assert recent.score > old.score > 0


def test_event_outside_lookback_ignored():
    s = score_substance("J", [_f(200, "8-K", ["1.01"])], AS_OF, PARAMS)
    assert s.n_events == 0 and s.score == 0.0


def test_form_type_mapping():
    s = score_substance("J", [_f(3, "SC 13D/A"), _f(3, "424B4"), _f(3, "4")], AS_OF, PARAMS)
    assert s.n_events == 3  # 13D, 424B, FORM4 all matched


def test_has_events_density_helper():
    assert has_events([_f(5, "8-K", ["1.01"])], AS_OF, PARAMS) is True
    assert has_events([_f(5, "8-K", ["9.01"])], AS_OF, PARAMS) is False  # 9.01 not weighted
    assert has_events([], AS_OF, PARAMS) is False
