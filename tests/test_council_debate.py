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
    # A well-formed non-NEUTRAL proposal keeps its (normalized) confidence.
    full = json.dumps({"confidence": "high", "structural_vs_fad": "structural",
                       "inflection_thesis": "real backlog inflection"})
    assert agents.parse_proposer(full)["confidence"] == "HIGH"
    # A bare {confidence} with NO thesis/structure is JSON-mode's "valid but empty shape" → fail-closed
    # NEUTRAL + parse_error (P1-#1: the bug in a new costume, caught).
    bare = agents.parse_proposer('{"confidence": "high"}')
    assert bare["confidence"] == "NEUTRAL" and bare["parse_error"] is True
    # A genuine NEUTRAL abstention is allowed to be minimal — NOT a parse error.
    neutral = agents.parse_proposer('{"confidence": "NEUTRAL"}')
    assert neutral["confidence"] == "NEUTRAL" and not neutral.get("parse_error")
    # Non-JSON → fail-closed, evidence preserved.
    s = agents.parse_strategist("not json")
    assert s["include"] is False and s["conviction"] == "NEUTRAL" and s["parse_error"] is True


def test_parse_error_captures_forensics():
    # Forensic fields ride into the fallback so council_agent_outputs.raw is self-diagnosing — critical
    # for the thinking-starvation case where the body is empty/truncated (raw_text='' → finish_reason
    # is the only signal).
    d = agents.parse_proposer("", finish_reason="MAX_TOKENS", thoughts_tokens=981)
    assert d["parse_error"] is True and d["finish_reason"] == "MAX_TOKENS" and d["thoughts_tokens"] == 981
    assert "raw_text" in d and "validation_error" in d
    d2 = agents.parse_adversary("here is my answer, no json at all", finish_reason="STOP")
    assert d2["parse_error"] is True and d2["raw_text"].startswith("here is my answer")


def test_fakerouter_outputs_satisfy_validation():
    # Ground-truth P1-#1: the validation required-key sets must stay in lock-step with what the agents
    # emit. If a prompt/responder edit desyncs them, every REAL call fails-closed and the apparatus goes
    # inert with a NEW root cause — so assert FakeRouter's output validates clean (no parse_error).
    fr = FakeRouter()
    user = "CANDIDATE: FCX bullish copper\n\nmarkers..."
    assert not agents.parse_proposer(fr.call(role="proposer", system="s", user=user).text).get("parse_error")
    assert not agents.parse_adversary(fr.call(role="adversary", system="s", user=user).text).get("parse_error")
    assert not agents.parse_strategist(fr.call(role="strategist", system="s", user=user).text).get("parse_error")


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
