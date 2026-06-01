"""Agents (prompts/parsers) + authenticity filter + debate orchestration (T2). Offline."""

import json
import random

from council import agents
from council.context import synthetic_context_pack
from council.debate import run_candidate
from council.filters import apply_filter, authenticity_scan, dampen
from council.router import FakeRouter
from themes import Theme

BULL = Theme("copper_electrification", "FCX", "bullish", "unloved industrial tailwind")
BEAR = Theme("legacy_rollover", "XYZ", "bearish", "secular demand rollover not yet consensus")


# ── agents ───────────────────────────────────────────────────────────────────

def test_extract_json_handles_fences_and_prose():
    assert agents.extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert agents.extract_json('Sure! {"a": {"b": 2}} done') == {"a": {"b": 2}}


def test_parsers_coerce_and_fail_closed():
    assert agents.parse_proposer('{"confidence": "high"}')["confidence"] == "HIGH"
    assert agents.parse_strategist("not json")["include"] is False
    assert agents.parse_strategist("not json")["conviction"] == "NEUTRAL"


def test_adversary_prompt_is_direction_relative():
    pack = synthetic_context_pack(BEAR)
    _, user = agents.adversary_prompt(pack, {"inflection_thesis": "rollover"})
    # Candidate is bearish → the adversary must argue the BULLISH case against it.
    assert "bullish" in user.lower()


# ── filters ──────────────────────────────────────────────────────────────────

def test_authenticity_scan_flags_unsupported():
    evidence = "Copper demand up 12% YoY against tight supply"
    supported = authenticity_scan(["demand up 12% as reported"], evidence)
    assert supported.flagged == 0
    unsupported = authenticity_scan(['margins hit 45% and CEO said "we will dominate"'], evidence)
    assert unsupported.flagged == 2  # 45% + the quote


def test_dampen_and_apply_filter():
    assert dampen("HIGH") == "MODERATE"
    assert dampen("NEUTRAL") == "NEUTRAL"
    pack = synthetic_context_pack(BULL)
    conf, res = apply_filter(["unsupported 99% claim"], pack, confidence="HIGH")
    assert conf == "MODERATE" and res.flagged == 1


def test_apply_filter_ungrounded_forces_neutral():
    pack = synthetic_context_pack(BULL).__class__(  # rebuild ungrounded
        symbol="FCX", theme="t", direction="bullish", operator_thesis="x",
        headlines=[], coverage_count=0, has_numeric=False)
    conf, _ = apply_filter(["anything"], pack, confidence="EXTREME")
    assert conf == "NEUTRAL"


# ── debate ───────────────────────────────────────────────────────────────────

def test_debate_grounded_produces_full_proposal():
    pack = synthetic_context_pack(BULL)
    prop = run_candidate(BULL, pack, FakeRouter(), rng=random.Random(0))
    assert prop.include is True and prop.conviction == "HIGH" and prop.direction == "bullish"
    assert [a.role for a in prop.agent_outputs] == ["proposer", "adversary", "strategist"]
    assert prop.model_mix["strategist"].startswith("fake/")


def test_debate_adversary_argues_opposite_on_bearish_candidate():
    pack = synthetic_context_pack(BEAR)
    prop = run_candidate(BEAR, pack, FakeRouter(), rng=random.Random(1))
    adversary = next(a for a in prop.agent_outputs if a.role == "adversary")
    assert adversary.stance == "bullish"  # direction-relative: bull case against a bearish trade


def test_debate_ungrounded_early_exits_without_llm_calls():
    pack = synthetic_context_pack(BULL).__class__(
        symbol="FCX", theme="copper", direction="bullish", operator_thesis="x",
        headlines=[], coverage_count=0, has_numeric=False)
    fr = FakeRouter()
    prop = run_candidate(BULL, pack, fr, rng=random.Random(0))
    assert prop.conviction == "NEUTRAL" and prop.include is False
    assert prop.agent_outputs == [] and fr.ledger.calls == 0  # no spend


def test_debate_proposer_abstention_drops_before_adversary():
    def responder(role, system, user):
        if role == "proposer":
            return json.dumps({"confidence": "NEUTRAL", "inflection_thesis": "insufficient"})
        return json.dumps({"include": True, "conviction": "HIGH"})

    fr = FakeRouter(responder=responder)
    prop = run_candidate(BULL, synthetic_context_pack(BULL), fr, rng=random.Random(0))
    assert prop.include is False and prop.conviction == "NEUTRAL"
    assert fr.ledger.calls == 1  # only the proposer was called
