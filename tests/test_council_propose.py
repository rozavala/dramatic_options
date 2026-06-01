"""Top-level council.propose (T2): demo run, kill guard, budget + provider fail-closed."""

from datetime import UTC, datetime
from pathlib import Path

import risk
from clock import FixedClock
from council.council import propose
from council.router import FakeRouter, RouterError
from themes import Theme

CLOCK = FixedClock(datetime(2026, 6, 1, tzinfo=UTC))
CONFIG = {"council": {"max_candidates": 12, "news_lookback_days": 90}}
CANDS = [
    Theme("copper_electrification", "FCX", "bullish", "unloved industrial tailwind"),
    Theme("legacy_rollover", "XYZ", "bearish", "secular demand rollover"),
]


def _no_kill(monkeypatch):
    monkeypatch.delenv("KILL", raising=False)
    monkeypatch.setattr(risk, "KILL_FILE", Path("/nonexistent/KILL"))


def test_demo_run_proposes_each_candidate(monkeypatch):
    _no_kill(monkeypatch)
    props = propose(CANDS, router=FakeRouter(), config=CONFIG, clock=CLOCK, demo=True)
    assert len(props) == 2
    assert all(p.include and p.conviction == "HIGH" for p in props)
    assert {p.symbol for p in props} == {"FCX", "XYZ"}


def test_kill_switch_blocks_council_without_spend(monkeypatch):
    monkeypatch.setenv("KILL", "1")
    fr = FakeRouter()
    props = propose(CANDS, router=fr, config=CONFIG, clock=CLOCK, demo=True)
    assert props == [] and fr.ledger.calls == 0  # never invoked → no LLM spend


def test_over_budget_fails_closed_to_zero(monkeypatch):
    _no_kill(monkeypatch)
    fr = FakeRouter(cap_usd=0.0)  # at cap before any call → first call raises BudgetExceeded
    props = propose(CANDS, router=fr, config=CONFIG, clock=CLOCK, demo=True)
    assert props == []  # over-budget → no entries


def test_max_candidates_caps_the_set(monkeypatch):
    _no_kill(monkeypatch)
    cfg = {"council": {"max_candidates": 1, "news_lookback_days": 90}}
    props = propose(CANDS, router=FakeRouter(), config=cfg, clock=CLOCK, demo=True)
    assert len(props) == 1


class _FlakyRouter(FakeRouter):
    """FakeRouter that raises a RouterError on one symbol's proposer call."""

    def __init__(self, bad_symbol):
        super().__init__()
        self._bad = bad_symbol

    def call(self, *, role, system, user, max_tokens=None):
        if self._bad in user and role == "proposer":
            raise RouterError("provider down")
        return super().call(role=role, system=system, user=user, max_tokens=max_tokens)


def test_provider_error_drops_only_that_candidate(monkeypatch):
    _no_kill(monkeypatch)
    props = propose(CANDS, router=_FlakyRouter("XYZ"), config=CONFIG, clock=CLOCK, demo=True)
    assert len(props) == 2  # both recorded
    by_sym = {p.symbol: p for p in props}
    assert by_sym["FCX"].include is True            # healthy candidate still proposed
    assert by_sym["XYZ"].include is False           # failed candidate dropped (never trades)
    assert "provider_error" in by_sym["XYZ"].weakest_point
