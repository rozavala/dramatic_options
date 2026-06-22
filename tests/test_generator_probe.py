"""Stage-2 narration probe — the DETERMINISTIC scorer core + the reject RULE (no LLM, offline).

Covers PREREG_NARRATION_PROBE §4 (the entity/quantity overlap scorers + the 5-family unit-aware
quantity parse), §5 (the all-three-high ∧ ≥2-concur RULE + the load-bearing empty/absent-field rule),
§6 (the non-perishable scorer smoke exemplars), §7 (the rejection-rate read).
"""

from generator import probe as P

# ── §6: non-perishable scorer smoke (verifies the DETERMINISTIC legs, not a live model) ──────────

_NVDA_NARRATED_DESC = ("NVIDIA dominates AI data-center GPUs; its data-center segment revenue is "
                       "around $30 billion per quarter, with surging accelerator demand and pricing power.")
_OBSCURE_DESC = ("Some niche compound-semiconductor process tweaks occasionally help small, unnamed "
                 "component suppliers; nothing specific or widely reported.")


def test_smoke_narrated_nvda_scores_high_on_deterministic_legs():
    # (A) the blatantly-narrated exemplar: a recall-style description surfaces the entity + the
    # circulated quantity → both deterministic legs read HIGH (≥0.80). Direction is the classifier's
    # leg (LLM); the full all-three pass is asserted via probe_claim below.
    e = P.entity_overlap(_NVDA_NARRATED_DESC, P.SMOKE_NARRATED_NVDA["named_entities"])
    q = P.quantity_overlap(_NVDA_NARRATED_DESC, P.SMOKE_NARRATED_NVDA["headline_quantities"])
    assert e >= P.HIGH_OVERLAP_CUTOFF and q >= P.HIGH_OVERLAP_CUTOFF


def test_smoke_obscure_invented_scores_low_on_deterministic_legs():
    # (B) the fictional exemplar: no describer can surface a fabricated issuer/figure → both legs LOW.
    e = P.entity_overlap(_OBSCURE_DESC, P.SMOKE_OBSCURE_INVENTED["named_entities"])
    q = P.quantity_overlap(_OBSCURE_DESC, P.SMOKE_OBSCURE_INVENTED["headline_quantities"])
    assert e < P.HIGH_OVERLAP_CUTOFF and q < P.HIGH_OVERLAP_CUTOFF


def test_smoke_full_rule_narrated_rejects_obscure_passes():
    # End-to-end through the RULE with the deterministic legs + a (simulated) classifier direction.
    narr = [P.score_claim_against_description(P.SMOKE_NARRATED_NVDA, m, _NVDA_NARRATED_DESC,
                                              direction_match=True) for m in ("g", "x")]
    assert P.probe_claim(P.SMOKE_NARRATED_NVDA, narr).rejected is True   # narrated → rejected
    obsc = [P.score_claim_against_description(P.SMOKE_OBSCURE_INVENTED, m, _OBSCURE_DESC,
                                              direction_match=False) for m in ("g", "x")]
    assert P.probe_claim(P.SMOKE_OBSCURE_INVENTED, obsc).passed is True  # quiet → passes


# ── §5: the LOAD-BEARING empty/absent-field rule (REQUIRED) ──────────────────────────────────────

def test_empty_quantity_field_always_passes_even_when_entity_and_direction_high():
    # A quantity-less structural mechanism (NRC docket / FERC queue): headline_quantities=[] → quantity
    # overlap 0.0 → can never clear all-three → NEVER rejected, even with full entity+direction concord
    # on every model (the protector of under-narrated specifics, §5).
    claim = {"claim_id": "struct", "named_entities": [{"canonical": "Cameco", "ticker": "CCJ"}],
             "mechanism_direction": {"vocab": "capacity_constraint", "sign": "+"},
             "headline_quantities": []}
    scores = [P.score_claim_against_description(claim, m, "Cameco CCJ faces a capacity constraint",
                                               direction_match=True) for m in ("g", "x", "a")]
    assert all(s.entity_overlap == 1.0 and s.quantity_overlap == 0.0 for s in scores)
    assert all(not s.clears_all_three() for s in scores)
    assert P.probe_claim(claim, scores).rejected is False


# ── §4 leg 1: entity overlap ─────────────────────────────────────────────────────────────────────

def test_entity_overlap_full_partial_zero():
    ents = [{"canonical": "NVIDIA", "ticker": "NVDA"}, {"canonical": "Eaton", "ticker": "ETN"}]
    assert P.entity_overlap("nvidia and eaton both rally", ents) == 1.0
    assert P.entity_overlap("only nvidia is mentioned here", ents) == 0.5
    assert P.entity_overlap("neither is here", ents) == 0.0
    assert P.entity_overlap("anything", []) == 0.0   # empty field → 0.0 (§5)


def test_entity_ticker_matches_on_word_boundary_not_inside_a_word():
    # a short ticker must not fire inside a longer word ('BA' inside 'backlog')
    ent = [{"canonical": "Boeing", "ticker": "BA"}]
    assert P.entity_overlap("rising backlog at suppliers", ent) == 0.0   # 'BA' not a standalone token
    assert P.entity_overlap("BA wins a new order", ent) == 1.0


def test_entity_edgar_name_expansion_resolves_a_renamed_issuer():
    # the EDGAR company-name map expands a ticker to its filed name so a description using the full
    # name (not the ticker/alias) still surfaces the entity (§4 leg 1).
    ent = [{"canonical": "GEV", "ticker": "GEV"}]                       # claim only carries the ticker
    edgar = {"GEV": "GE Vernova Inc"}
    assert P.entity_overlap("ge vernova inc guides capex higher", ent) == 0.0
    assert P.entity_overlap("ge vernova inc guides capex higher", ent, edgar_names=edgar) == 1.0


# ── §4 leg 3: quantity overlap across the 5 families + ±1 tolerance ──────────────────────────────

def test_quantity_overlap_each_family_recovers_and_misses():
    def q(bucket):
        return [{"metric": "x", "value": "v", "bucket": bucket}]
    # pct_
    assert P.quantity_overlap("defect rates fell 40%", q("pct_25_50")) == 1.0
    assert P.quantity_overlap("a tiny 5% move", q("pct_25_50")) == 0.0     # 2 buckets away (not ±1)
    # usd_
    assert P.quantity_overlap("about $30 billion per quarter", q("usd_tens_of_billions")) == 1.0
    assert P.quantity_overlap("roughly $5 million", q("usd_tens_of_billions")) == 0.0
    # cnt_ (bare magnitude)
    assert P.quantity_overlap("operates 95 reactors", q("cnt_lt100")) == 1.0
    # dur_ (unit-aware → canonical weeks; ±1 across the weeks/months boundary)
    assert P.quantity_overlap("lead times stretched to 120 weeks", q("dur_months_12_36")) == 1.0
    assert P.quantity_overlap("an 8-week lead time", q("dur_months_12_36")) == 0.0
    # x_ (multiplier)
    assert P.quantity_overlap("a 2x increase in orders", q("x_2plus")) == 1.0
    assert P.quantity_overlap("anything", []) == 0.0                       # empty field → 0.0 (§5)


# ── §5: the reject RULE (all-three-high ∧ ≥CONCUR_MIN concur) ────────────────────────────────────

def _clearing_score(model):
    return P.ModelScore(model=model, entity_overlap=1.0, quantity_overlap=1.0, direction_match=True)


def _failing_score(model):
    return P.ModelScore(model=model, entity_overlap=1.0, quantity_overlap=0.5, direction_match=True)


def test_rule_rejects_only_when_at_least_two_models_clear_all_three():
    claim = {"claim_id": "c"}
    assert P.probe_claim(claim, [_clearing_score("g"), _clearing_score("x")]).rejected is True
    # one clears, one fails → 1 < CONCUR_MIN → passes
    v1 = P.probe_claim(claim, [_clearing_score("g"), _failing_score("x")])
    assert v1.passed is True and v1.n_concur == 1
    # zero clear → passes
    assert P.probe_claim(claim, [_failing_score("g"), _failing_score("x")]).passed is True


def test_direction_miss_blocks_a_clear_even_with_both_overlap_legs_high():
    s = P.ModelScore(model="g", entity_overlap=1.0, quantity_overlap=1.0, direction_match=False)
    assert s.clears_all_three() is False


def test_rejection_rate_over_a_batch():
    claim = {"claim_id": "c"}
    rej = P.probe_claim(claim, [_clearing_score("g"), _clearing_score("x")])
    keep = P.probe_claim(claim, [_failing_score("g"), _failing_score("x")])
    assert P.rejection_rate([rej, keep, keep, keep]) == 0.25
    assert P.rejection_rate([]) == 0.0


def test_frozen_constants_match_the_prereg():
    assert P.FIELD_WEIGHTS == {"named_entities": 0.40, "mechanism_direction": 0.30, "headline_quantities": 0.30}
    assert P.HIGH_OVERLAP_CUTOFF == 0.80 and P.CONCUR_MIN == 2
    assert P.REJECT_BAND == (0.15, 0.35) and P.INERT_N_FLOOR == 20
