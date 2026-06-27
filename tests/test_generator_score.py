"""Seeded-diagnostic SCORER (PREREG_SEEDED_GENERATOR_DIAGNOSTIC §4-§5) — hand-checked value tests.

Pure functions; every net-new number asserted to a hand-computed value (the anti-HARK convention)."""

from __future__ import annotations

import pytest

from corpus.etf_constituents import SOURCE as ETF_SOURCE
from corpus.federal_awards import SOURCE as AWARDS_SOURCE
from generator import score
from generator.entity import _norm


def _art(theses, *, model="m1", prompt_sha="p1", de=0, df=0):
    return {"as_of": "2026-06-27", "model": model, "prompt_sha": prompt_sha,
            "dropped_entity_unresolved": de, "dropped_fact_untraced": df, "theses": theses}


def _claim(ticker, sources):
    return {"named_entities": [{"ticker": ticker, "canonical": ticker}],
            "citations": [{"source": s, "key": "k", "ts": "t"} for s in sources]}


def test_assert_matched_version():
    assert score.assert_matched_version([_art([]), _art([])]) == ("m1", "p1")
    with pytest.raises(ValueError):                          # a pre-stamp run (no model/sha) → refused
        score.assert_matched_version([{"as_of": "x", "theses": []}])
    with pytest.raises(ValueError):                          # mixed versions across the k-set → refused
        score.assert_matched_version([_art([]), _art([], model="m2")])


def test_second_order_sources_filters_entity_free_and_feasibility():
    from pathlib import Path

    from corpus.content import load_content
    content = load_content(Path(__file__).resolve().parent.parent / "corpus_content.json")  # CWD-robust
    cfg = {"universe": {"themes": {}}}
    # nuclear_fuel: its non-ETF sources (nrc/eia) are ENTITY-FREE → no resolvable second-order source →
    # leg (c) unsatisfiable → the slice is INFEASIBLE (the nuclear_fuel trap).
    assert score.second_order_sources("nuclear_fuel", content=content, config=cfg) == set()
    assert score.slice_feasible("nuclear_fuel", content=content, config=cfg) is False
    # space_smallcap: federal_awards is FREE_TEXT_RECIPIENT (entity-resolvable) → feasible.
    assert score.second_order_sources("space_smallcap", content=content, config=cfg) == {AWARDS_SOURCE}
    assert score.slice_feasible("space_smallcap", content=content, config=cfg) is True


def test_score_arm_hand_checked():
    # NEWCO: second-order ∧ not-in-register ∧ not-in-ETF, in 4/5 runs → STABLE qualifying.
    # OLDCO: in register → leg (a) fails. ETFCO: in the ETF → leg (c2) fails. NOSRC: ETF-only cite → (c) fails.
    # ONCE: qualifies but 1/5 → not stable.
    runs = [
        [_claim("NEWCO", [AWARDS_SOURCE]), _claim("OLDCO", [AWARDS_SOURCE])],
        [_claim("NEWCO", [AWARDS_SOURCE]), _claim("ETFCO", [AWARDS_SOURCE])],
        [_claim("NEWCO", [AWARDS_SOURCE]), _claim("NOSRC", [ETF_SOURCE])],
        [_claim("NEWCO", [AWARDS_SOURCE])],
        [_claim("ONCE", [AWARDS_SOURCE])],
    ]
    arm = score.score_arm([_art(r, de=1) for r in runs], register_keys={"OLDCO"},
                          second_order_srcs={AWARDS_SOURCE}, etf_holdings={"ETFCO"}, stability_min=3)
    assert arm["stable_qualifying"] == {_norm("NEWCO")}      # 4/5 ≥ 3; everything else excluded
    assert arm["drop_split"]["dropped_entity_unresolved"] == 5   # 1 per run × 5 runs


def test_stage1_escalation_subset_and_final_verdict():
    s1 = score.stage1({"stable_qualifying": {"NEWCO", "QUIETCO"}}, {"stable_qualifying": {"NEWCO"}})
    assert s1["escalate"] is True and s1["subset_plumbing_negative"] is False
    assert s1["stage2_candidates"] == ["NEWCO", "QUIETCO"]   # BOTH arms labeled by the council
    # subset ⇒ the slice isn't biting → plumbing-negative, no escalation
    sub = score.stage1({"stable_qualifying": {"NEWCO"}}, {"stable_qualifying": {"NEWCO", "X"}})
    assert sub["subset_plumbing_negative"] is True and sub["escalate"] is False
    # confirmation: council labels → YIELD(seeded) > YIELD(autonomous)
    fv = score.final_verdict(["NEWCO", "QUIETCO"], ["NEWCO"], {"QUIETCO": True, "NEWCO": False})
    assert fv == {"yield_seeded": 1, "yield_autonomous": 0, "confirmed": True}
