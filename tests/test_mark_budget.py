"""The L2 mark budget (the 2026-09-11 Alpaca-outage lesson): after N CONSECUTIVE chain-pull failures the
quote provider trips and the remaining marks return None (counted ``unmarked``) instead of each paying a
provider timeout — a warning, never a unit kill/page. Never mis-marks; a success resets the streak."""
from __future__ import annotations

import pytest

from convexity_data import DEFAULT_MARK_FAILURE_BUDGET, AlpacaQuoteProvider


class _Client:
    def __init__(self, plan):
        self.plan = list(plan)   # per call: "ok" | "fail"
        self.calls = 0

    def option_quote_tuples(self, underlying, **kw):
        self.calls += 1
        step = self.plan.pop(0) if self.plan else "ok"
        if step == "fail":
            raise TimeoutError("backend request timeout")
        return [{"symbol": f"{underlying}270115C00100000", "bid": 1.0, "ask": 1.2}]


def _sym(u):
    return f"{u}270115C00100000"


def test_trips_after_budget_and_skips_the_rest():
    c = _Client(["fail", "fail", "fail"])
    qp = AlpacaQuoteProvider(c, failure_budget=3)
    for u in ("AAA", "BBB", "CCC"):
        with pytest.raises(TimeoutError):   # the failing pulls still raise → the monitor counts unmarked
            qp.option_mid(_sym(u))
    assert qp.tripped and c.calls == 3
    # tripped: no further provider calls, marks are None (unmarked), never a stale/mis-mark
    assert qp.option_mid(_sym("DDD")) is None and qp.option_bid(_sym("EEE")) is None
    assert c.calls == 3 and qp.skipped == 2


def test_success_resets_the_streak():
    c = _Client(["fail", "fail", "ok", "fail", "fail", "ok"])
    qp = AlpacaQuoteProvider(c, failure_budget=3)
    for u in ("AAA", "BBB"):
        with pytest.raises(TimeoutError):
            qp.option_mid(_sym(u))
    assert qp.option_mid(_sym("CCC")) == pytest.approx(1.1)
    for u in ("DDD", "EEE"):
        with pytest.raises(TimeoutError):
            qp.option_mid(_sym(u))
    assert not qp.tripped
    assert qp.option_mid(_sym("FFF")) == pytest.approx(1.1)


def test_cached_underlying_still_marks_after_trip():
    c = _Client(["ok", "fail", "fail", "fail"])
    qp = AlpacaQuoteProvider(c, failure_budget=3)
    assert qp.option_mid(_sym("AAA")) == pytest.approx(1.1)
    for u in ("BBB", "CCC", "DDD"):
        with pytest.raises(TimeoutError):
            qp.option_mid(_sym(u))
    assert qp.tripped
    assert qp.option_mid(_sym("AAA")) == pytest.approx(1.1)  # already-pulled chain: no provider call


def test_none_budget_disables_the_breaker():
    c = _Client(["fail"] * 6)
    qp = AlpacaQuoteProvider(c, failure_budget=None)
    for u in ("A", "B", "C", "D", "E", "F"):
        with pytest.raises(TimeoutError):
            qp.option_mid(_sym(u))
    assert not qp.tripped and c.calls == 6


def test_default_budget_is_small():
    assert DEFAULT_MARK_FAILURE_BUDGET == 3
