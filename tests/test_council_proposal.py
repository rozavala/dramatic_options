"""Council proposal types + the proposal→Theme hard-seam adapter (T2)."""

from council.proposal import (
    AgentOutput,
    CouncilProposal,
    normalize_conviction,
    passes_floor,
    select_for_trade,
)


def _prop(symbol="FCX", direction="bullish", conviction="HIGH", include=True):
    return CouncilProposal(
        theme="copper", symbol=symbol, direction=direction, conviction=conviction,
        structural_vs_fad="structural", weakest_point="priced?", strategist_summary="buy cheap calls",
        rationale={"k": "v"}, include=include,
    )


def test_normalize_conviction():
    assert normalize_conviction("high") == "HIGH"
    assert normalize_conviction("bogus") == "NEUTRAL"
    assert normalize_conviction(None) == "NEUTRAL"


def test_passes_floor():
    assert passes_floor("HIGH", "MODERATE")
    assert passes_floor("MODERATE", "MODERATE")
    assert not passes_floor("LOW", "MODERATE")
    assert not passes_floor("NEUTRAL", "MODERATE")
    assert not passes_floor(None, "MODERATE")


def test_to_theme_carries_proposal_id_and_conviction():
    t = _prop().to_theme(proposal_id=42)
    assert t.symbol == "FCX" and t.direction == "bullish"
    assert t.proposal_id == 42 and t.conviction == "HIGH"
    assert t.thesis == "buy cheap calls" and t.active is True


def test_to_theme_defaults_bad_direction_to_bullish():
    t = _prop(direction="sideways").to_theme(proposal_id=1)
    assert t.direction == "bullish"


def test_select_for_trade_only_reduces():
    props = [
        _prop(symbol="FCX", conviction="HIGH"),       # keep
        _prop(symbol="XYZ", conviction="LOW"),         # below floor → drop
        _prop(symbol="ABC", conviction="EXTREME", include=False),  # strategist drop
    ]
    kept = select_for_trade(props, floor="MODERATE")
    assert [p.symbol for p in kept] == ["FCX"]


def test_agent_output_dataclass_fields():
    a = AgentOutput("proposer", "gemini", "g", "HIGH", "bullish", "wp", {"x": 1}, flagged_unsupported=2, cost_usd=0.01)
    assert a.role == "proposer" and a.flagged_unsupported == 2 and a.cost_usd == 0.01
