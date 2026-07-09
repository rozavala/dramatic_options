"""Agents (prompts/parsers) + authenticity filter + debate orchestration (T2). Offline."""

import json
import random

import pytest

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


# ── extract_json bracket tail-repair (the gemini JSON-mode tail-mangling family, live
#    runs #458/#491 2026-07-07/09: finish=STOP with the final '}' dropped, or a stray ']') ──

def test_tail_repair_missing_final_brace():
    # Run #491 (RKLB, AMSC): the complete object minus its closing '}' — natural STOP.
    damaged = ('{\n  "confidence": "LOW",\n  "evidence_cited": [\n'
               '    "momentum_12m +1.944",\n    "17 analyst(s) covering"\n  ]')
    assert agents.extract_json(damaged) == {
        "confidence": "LOW",
        "evidence_cited": ["momentum_12m +1.944", "17 analyst(s) covering"],
    }


def test_tail_repair_stray_duplicate_closer():
    # Run #458 (RKLB): a doubled ']' before the final '}' — braces balance, json.loads chokes.
    damaged = '{\n  "confidence": "LOW",\n  "evidence_cited": [\n    "capex qtr_yoy -5.6%"\n  ]\n]\n}\n'
    assert agents.extract_json(damaged) == {
        "confidence": "LOW",
        "evidence_cited": ["capex qtr_yoy -5.6%"],
    }


def test_tail_repair_never_touches_strings_and_valid_json_unchanged():
    # Brackets/braces INSIDE strings are content, not structure — no repair path may alter them.
    ok = '{"a": "closer } and ] inside", "b": [1, 2]}'
    assert agents.extract_json(ok) == {"a": "closer } and ] inside", "b": [1, 2]}
    # A damaged tail whose strings contain brackets still repairs on structure alone.
    damaged = '{"a": "text with ] and } chars", "b": [1, 2]'
    assert agents.extract_json(damaged) == {"a": "text with ] and } chars", "b": [1, 2]}


def test_tail_repair_stays_bounded_and_fails_closed():
    # Garbage is still garbage — the repair must not become a lenient parser.
    with pytest.raises(ValueError):
        agents.extract_json("no json here at all")
    # An unterminated STRING is content damage, not bracket damage → original error re-raised.
    with pytest.raises(ValueError, match="unbalanced"):
        agents.extract_json('{"a": "never closed')
    # More than 3 stray closers → beyond the bounded repair → the ORIGINAL error surfaces.
    with pytest.raises(ValueError):
        agents.extract_json('{"a": [1]]]]]')
    # More than 4 missing closers → beyond the bounded repair.
    with pytest.raises(ValueError, match="unbalanced"):
        agents.extract_json('{"a": {"b": {"c": {"d": {"e": 1')


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
    s = agents.parse_strategist(fr.call(role="strategist", system="s", user=user).text)
    assert not s.get("parse_error")
    # §10.7 lock-step extension: the fake strategist's include must also PASS the tri-criteria
    # (booleans present AND True), else every demo include silently dies at select_for_trade.
    assert s["include"] is True
    assert s.get("under_narrated") is True and s.get("at_inflection") is True


def test_parse_strategist_tri_key_classification():
    # CGS §10.9: ABSENT tri key on include∧non-NEUTRAL → parse_error (truncation/non-compliance,
    # the #37 discipline — must grade DEGRADED, never read as a deliberated veto).
    base = {"include": True, "conviction": "HIGH", "structural_vs_fad": "structural",
            "summary": "s", "at_inflection": True}
    absent = agents.parse_strategist(json.dumps(base))  # under_narrated ABSENT
    assert absent["parse_error"] is True and absent["include"] is False
    assert "under_narrated" in absent["validation_error"]
    # Key PRESENT with null → parses CLEAN (an explicit non-assertion is deliberated; the
    # criteria-veto downstream handles it — truncation never emits selective nulls).
    null_val = agents.parse_strategist(json.dumps({**base, "under_narrated": None}))
    assert not null_val.get("parse_error") and null_val["include"] is True
    # Key present with false → also clean at parse (veto downstream).
    false_val = agents.parse_strategist(json.dumps({**base, "under_narrated": False}))
    assert not false_val.get("parse_error")
    # A genuine minimal NEUTRAL abstention needs NO new keys (never convert abstentions to failures).
    neutral = agents.parse_strategist(json.dumps({"include": False, "conviction": "NEUTRAL"}))
    assert not neutral.get("parse_error")
    # An include row missing summary is still parse_error (shape-first, deterministic).
    no_summary = agents.parse_strategist(json.dumps({"include": True, "conviction": "HIGH",
                                                     "under_narrated": False, "at_inflection": False}))
    assert no_summary["parse_error"] is True


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
        # Never invoked here (the proposer abstains first) — kept FULL-shape anyway so any future
        # reuse passes the strategist parse (summary + the §10.7 booleans; no sweep exemption).
        return json.dumps({"include": True, "conviction": "HIGH", "summary": "s",
                           "structural_vs_fad": "structural",
                           "under_narrated": True, "at_inflection": True})

    fr = FakeRouter(responder=responder)
    prop = run_candidate(BULL, synthetic_context_pack(BULL), fr, rng=random.Random(0))
    assert prop.include is False and prop.conviction == "NEUTRAL"
    assert fr.ledger.calls == 1  # only the proposer was called


def _three_role_responder(strategist_json: dict):
    """Proposer+adversary full-shape; strategist = the given dict (per-test §10.7 scenarios)."""
    def responder(role, system, user):
        if role == "proposer":
            return json.dumps({"theme": "t", "symbol": "FCX", "direction": "bullish",
                               "structural_vs_fad": "structural", "inflection_thesis": "real",
                               "confidence": "HIGH", "cited": []})
        if role == "adversary":
            return json.dumps({"counter_case": "c", "weakest_point": "w", "is_fad": False,
                               "already_consensus": False, "inflection_passed": False,
                               "confidence": "MODERATE", "cited": []})
        return json.dumps(strategist_json)
    return responder


def test_debate_criteria_veto_coerces_include_and_preserves_conviction():
    # §10.7 enforcement at the coercion point: include=true violating its own asserted criteria →
    # include coerced false + criteria_veto recorded (DISTINCT from parse_error), conviction kept
    # (Brier substrate). Explicit false/null booleans are the deliberated-non-assertion path.
    fr = FakeRouter(responder=_three_role_responder(
        {"include": True, "conviction": "MODERATE", "structural_vs_fad": "structural",
         "under_narrated": False, "at_inflection": True, "summary": "s"}))
    prop = run_candidate(BULL, synthetic_context_pack(BULL), fr, rng=random.Random(0))
    assert prop.include is False and prop.criteria_veto is True
    assert prop.conviction == "MODERATE"  # preserved, never zeroed
    strat_raw = next(a for a in prop.agent_outputs if a.role == "strategist").raw
    assert strat_raw.get("criteria_veto") is True and not strat_raw.get("parse_error")
    assert prop.rationale["strategist"]["criteria_veto"] is True


def test_debate_sf_fallback_include_survives():
    # The §10.8 preview's survivor edge, pinned: strategist include with booleans True but NO
    # structural_vs_fad of its own + proposer 'structural' → the sanctioned fallback applies,
    # tri passes, include SURVIVES (production must not be stricter than the validated preview here).
    fr = FakeRouter(responder=_three_role_responder(
        {"include": True, "conviction": "HIGH",
         "under_narrated": True, "at_inflection": True, "summary": "s"}))
    prop = run_candidate(BULL, synthetic_context_pack(BULL), fr, rng=random.Random(0))
    assert prop.include is True and prop.criteria_veto is False
    assert prop.structural_vs_fad == "structural"  # the proposer fallback
    from council.proposal import select_for_trade
    assert select_for_trade([prop], floor="MODERATE") == [prop]


def test_debate_string_true_fails_tri_closed():
    # Comparison semantics verbatim from the preview: `is True` identity — a JSON-mode model
    # emitting the STRING "true" fails the tri by design (fail-closed, preview-identical).
    fr = FakeRouter(responder=_three_role_responder(
        {"include": True, "conviction": "HIGH", "structural_vs_fad": "structural",
         "under_narrated": "true", "at_inflection": True, "summary": "s"}))
    prop = run_candidate(BULL, synthetic_context_pack(BULL), fr, rng=random.Random(0))
    assert prop.include is False and prop.criteria_veto is True
