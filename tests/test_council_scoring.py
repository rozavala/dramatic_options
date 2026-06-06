"""Forward-only scoring (T2): Brier + resolution branches + per-agent contribution."""

import pytest

from dramatic_options.council.proposal import AgentOutput
from dramatic_options.council.scoring import (
    agent_contribution,
    brier,
    conviction_prob,
    outcome_from_close,
    resolve,
)


def test_conviction_prob_and_brier():
    assert conviction_prob("HIGH") == 0.75
    assert conviction_prob("NEUTRAL") == 0.5
    assert conviction_prob("bogus") == 0.5
    assert brier(0.75, 1) == pytest.approx(0.0625)


def test_outcome_profit_take_is_favorable():
    assert outcome_from_close("profit_take_10x", direction="bullish") == 1


def test_outcome_expiry_uses_intrinsic():
    assert outcome_from_close("expiry", direction="bullish", intrinsic=5.0) == 1
    assert outcome_from_close("expiry", direction="bullish", intrinsic=0.0) == 0


def test_outcome_time_stop_needs_spot_directional():
    assert outcome_from_close("time_stop_21dte", direction="bullish", exit_spot=110, entry_spot=100) == 1
    assert outcome_from_close("time_stop_21dte", direction="bullish", exit_spot=90, entry_spot=100) == 0
    # bearish: a DOWN move is favorable
    assert outcome_from_close("time_stop_21dte", direction="bearish", exit_spot=90, entry_spot=100) == 1
    # spot unavailable → unresolved (never fabricated)
    assert outcome_from_close("time_stop_21dte", direction="bullish") is None


def test_resolve_returns_outcome_and_brier_or_none():
    outcome, b = resolve("profit_take_10x", direction="bullish", conviction="HIGH")
    assert outcome == 1 and b == pytest.approx(0.0625)
    # unresolved time-stop → (None, None), never fabricated
    assert resolve("time_stop_21dte", direction="bullish", conviction="HIGH") == (None, None)


def test_agent_contribution_rewards_correct_stance():
    proposer = AgentOutput("proposer", "p", "m", "HIGH", "bullish", None, {})
    adversary = AgentOutput("adversary", "a", "m", "HIGH", "bearish", None, {})
    # outcome=1 (proposed bullish direction worked): proposer should beat adversary.
    contrib = agent_contribution([proposer, adversary], outcome=1, proposed_direction="bullish")
    assert contrib["proposer"] < contrib["adversary"]
    # outcome=0 (proposed direction failed): the adversary's against-case was the better forecast.
    contrib0 = agent_contribution([proposer, adversary], outcome=0, proposed_direction="bullish")
    assert contrib0["adversary"] < contrib0["proposer"]
