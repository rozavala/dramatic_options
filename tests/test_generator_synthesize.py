"""P1 tests — pinned synthesis prompt + strict §3 parser + emit-cleanliness (FakeRouter, no LLM).

``PREREG_THEME_GENERATOR §4/§6``. Fixture-inert: a ``FakeRouter`` with a scripted responder — NO
network, NO keys, NO real model. Covers: the byte-exact prompt pin (the ``test_council_prompts``
sha-pin pattern); a valid synthesis → all §3 fields present + correctly typed; fail-closed on
truncated / empty / wrong-shape; and the vocab/bucket emit-cleanliness round-trip incl. the
schema-REOPEN flag on an out-of-enum direction / non-frozen bucket.
"""

from __future__ import annotations

import hashlib
import json

from council.router import FakeRouter
from generator import prompts, synthesize

# A canonical, well-formed §3 claim carrying the additive `citations` field (the generator's
# contract — the §6 schema exemplars predate `citations`, so we build a citation-bearing one here).
_GOOD_CLAIM = {
    "claim_id": "uranium_supply_squeeze",
    "statement": "Sustained reactor restarts -> primary uranium deficit -> uranium miners.",
    "named_entities": [{"canonical": "Cameco Corp", "ticker": "CCJ", "aliases": ["Cameco"]}],
    "mechanism_direction": {"vocab": "shortage", "sign": "+"},
    "headline_quantities": [{"metric": "transformer lead time", "value": "~50->~120 weeks",
                             "bucket": "weeks_x2plus"}],
    "provenance": "generated",
    "citations": [{"source": "corpus_etf_constituents", "key": "URNM",
                   "ts": "2026-03-02T20:00:00+00:00"}],
}


def _responder_for(payload):
    """A FakeRouter responder that returns a fixed JSON string regardless of role/prompt."""
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return lambda role, system, user: text


# ── the pinned synthesis prompt (byte-exact) ───────────────────────────────────────────────────

def test_synthesis_prompt_sha_pin():
    # Mirrors tests/test_council_prompts.py: a drifted byte is unshippable (the prompt is part of
    # the generator forward record — a change needs a re-pin, never a quiet edit).
    pin = "09c17c8a6d85e60b"
    got = hashlib.sha256(prompts.SYNTHESIS_SYSTEM.encode()).hexdigest()[:16]
    assert got == pin, f"SYNTHESIS_SYSTEM drifted (pin {pin}, got {got}) — re-pin via a freeze, not an edit"


def test_synthesis_prompt_names_the_frozen_schema_and_enums():
    # The schema fields + the frozen vocab/bucket sets must appear verbatim in the prompt (prompt and
    # verifier may only change together — the council lock-step discipline).
    s = prompts.SYNTHESIS_SYSTEM
    for fld in ("claim_id", "statement", "named_entities", "mechanism_direction",
                "headline_quantities", "provenance", "citations"):
        assert fld in s
    for v in prompts.MECHANISM_VOCAB:
        assert v in s
    for b in prompts.HEADLINE_BUCKETS:
        assert b in s


# ── parser: valid claim → all §3 fields present + correctly typed ──────────────────────────────

def test_valid_claim_parses_with_all_fields():
    res = synthesize.synthesize({}, router=FakeRouter(responder=_responder_for({"claims": [_GOOD_CLAIM]})))
    assert len(res.claims) == 1
    c = res.claims[0]
    for f in synthesize._REQUIRED_FIELDS:
        assert f in c
    assert isinstance(c["named_entities"], list) and c["named_entities"]
    assert c["mechanism_direction"]["sign"] == "+"
    assert c["provenance"] == "generated"
    assert isinstance(c["citations"], list) and c["citations"]
    assert res.cleanliness.clean and not res.cleanliness.reopen_required


def test_parser_tolerates_a_lone_claim_object_without_wrapper():
    res = synthesize.synthesize({}, router=FakeRouter(responder=_responder_for(_GOOD_CLAIM)))
    assert len(res.claims) == 1 and res.claims[0]["claim_id"] == "uranium_supply_squeeze"


def test_parser_drops_malformed_claims_but_keeps_good_ones():
    bad_missing = {k: v for k, v in _GOOD_CLAIM.items() if k != "citations"}      # missing citations
    bad_provenance = {**_GOOD_CLAIM, "claim_id": "x", "provenance": "operator"}   # wrong provenance
    bad_sign = {**_GOOD_CLAIM, "claim_id": "y", "mechanism_direction": {"vocab": "shortage", "sign": "up"}}
    bad_entities = {**_GOOD_CLAIM, "claim_id": "z", "named_entities": []}          # empty entities
    payload = {"claims": [_GOOD_CLAIM, bad_missing, bad_provenance, bad_sign, bad_entities]}
    res = synthesize.synthesize({}, router=FakeRouter(responder=_responder_for(payload)))
    assert [c["claim_id"] for c in res.claims] == ["uranium_supply_squeeze"]


# ── parser: fail-closed on truncated / empty / wrong-shape ─────────────────────────────────────

def test_failclosed_on_truncated_json():
    truncated = '{"claims": [{"claim_id": "u", "statement": "a -> b -> c", "named_enti'
    res = synthesize.synthesize({}, router=FakeRouter(responder=_responder_for(truncated)))
    assert res.claims == [] and res.cleanliness.clean   # vacuously clean over zero claims


def test_failclosed_on_empty_text():
    res = synthesize.synthesize({}, router=FakeRouter(responder=_responder_for("")))
    assert res.claims == [] and res.raw_text == ""


def test_failclosed_on_wrong_shape():
    # valid JSON, wrong shape (no claims array, not a lone claim) → zero claims (the #37 guard)
    res = synthesize.synthesize({}, router=FakeRouter(responder=_responder_for({"foo": "bar"})))
    assert res.claims == []
    res2 = synthesize.synthesize({}, router=FakeRouter(responder=_responder_for({"claims": "not-a-list"})))
    assert res2.claims == []


# ── emit-cleanliness: the §4 vocab/bucket round-trip + the schema-REOPEN flag ───────────────────

def test_emit_cleanliness_all_frozen_resolves():
    # Every frozen vocab + every frozen bucket resolves; the §6 exemplar values resolve too.
    for v in prompts.MECHANISM_VOCAB:
        claim = {**_GOOD_CLAIM, "claim_id": v, "mechanism_direction": {"vocab": v, "sign": "+"}}
        assert synthesize.check_emit_cleanliness([claim]).clean
    for b in prompts.HEADLINE_BUCKETS:
        claim = {**_GOOD_CLAIM, "claim_id": b,
                 "headline_quantities": [{"metric": "m", "value": "v", "bucket": b}]}
        assert synthesize.check_emit_cleanliness([claim]).clean
    # §6 smoke exemplar vocab/buckets (demand_surge/usd_tens_of_billions, backlog_growth/pct_25_50)
    assert synthesize._resolves_vocab("demand_surge", {})
    assert synthesize._resolves_vocab("backlog_growth", {})
    assert synthesize._resolves_bucket("usd_tens_of_billions")
    assert synthesize._resolves_bucket("pct_25_50")


def test_emit_cleanliness_empty_quantities_is_clean():
    # headline_quantities=[] is the load-bearing quantity-less-structural case — it resolves (clean).
    claim = {**_GOOD_CLAIM, "headline_quantities": []}
    res = synthesize.check_emit_cleanliness([claim])
    assert res.clean and not res.unresolved_buckets


def test_emit_cleanliness_flags_out_of_enum_vocab_for_reopen():
    # A legitimate-but-novel direction (margin_compression) is NOT in the frozen enum and the
    # coercion map defaults EMPTY → FLAGGED for schema-reopen, never auto-added (§4).
    claim = {**_GOOD_CLAIM, "claim_id": "mc",
             "mechanism_direction": {"vocab": "margin_compression", "sign": "-"}}
    res = synthesize.check_emit_cleanliness([claim])
    assert not res.clean and res.reopen_required
    assert res.unresolved_vocab == [("mc", "margin_compression")]


def test_emit_cleanliness_coercion_map_resolves_without_touching_enum():
    # The operator's pinned coercion map resolves a synonym WITHOUT a probe-schema change (§4).
    claim = {**_GOOD_CLAIM, "claim_id": "mc",
             "mechanism_direction": {"vocab": "margin_compression", "sign": "-"}}
    res = synthesize.check_emit_cleanliness([claim], coercion_map={"margin_compression": "surplus"})
    assert res.clean and not res.reopen_required


def test_emit_cleanliness_flags_non_frozen_bucket():
    claim = {**_GOOD_CLAIM, "claim_id": "nb",
             "headline_quantities": [{"metric": "m", "value": "v", "bucket": "gigawatts_x10"}]}
    res = synthesize.check_emit_cleanliness([claim])
    assert not res.clean and res.unresolved_buckets == [("nb", "gigawatts_x10")]


# ── render: corpus block carries source/key/ts for verbatim citation ───────────────────────────

def test_render_corpus_block_includes_records_for_citation():
    corpus = {"corpus_etf_constituents": [
        {"ts": "2026-03-02T20:00:00+00:00", "etf": "URNM", "symbol": "CCJ", "name": "Cameco Corp"}]}
    block = synthesize.render_corpus_block(corpus)
    assert "corpus_etf_constituents" in block and "Cameco Corp" in block and "URNM" in block
