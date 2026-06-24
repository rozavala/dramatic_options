"""PR2 — structural-thesis backdrop for sentinels (symbol-keyed, evidence-not-permission).

A discovery sentinel's OPERATOR_THESIS is the framer's markers-narration (e.g. "transient
correction"); this surfaces the theme's operator-authored STRUCTURAL thesis as a read-only backdrop
so the council reasons against the secular frame. Keyed on SYMBOL (the framer renames the theme, so
`candidate.name` is an LLM slug, not the register key). Conditional render → the framer pack stays
byte-identical (§6 leash). Never touches `grounded`/the tri-criteria/the gate.
"""

import json
from datetime import UTC, datetime

from council.context import build_context_pack, sentinel_context_pack
from council.filters import apply_filter
from themes import Theme
from universe import load_theme_theses

AS_OF = datetime(2026, 6, 24, 12, 0, tzinfo=UTC)
_MARKERS = {"momentum": 0.30, "rv_slope": 0.20, "mom_recent": -0.10, "rv_rising": 0.15}
_THESIS = "A structural silver supply deficit — industrial + solar demand outrunning supply"


def _sentinel(symbol="AG", name="silver_price_mean_reversion"):
    # name = the framer's LLM theme slug (NOT the register basket key) — the lookup must not use it.
    return Theme(name=name, symbol=symbol, direction="bearish", thesis="transient correction",
                 source="sentinel", markers=_MARKERS)


# ── render + §6 framer byte-identity ──────────────────────────────────────────

def test_framer_pack_byte_identical_without_structural_context():
    pack = sentinel_context_pack(_sentinel(), as_of=AS_OF)  # framer path passes no backdrop
    assert pack.structural_context is None
    assert "STRUCTURAL_CONTEXT" not in pack.as_prompt_block()


def test_council_pack_renders_backdrop_right_after_operator_thesis():
    pack = sentinel_context_pack(_sentinel(), as_of=AS_OF, structural_context=_THESIS)
    block = pack.as_prompt_block()
    assert f"STRUCTURAL_CONTEXT: {_THESIS} (secular backdrop)" in block
    lines = block.splitlines()
    i = next(k for k, ln in enumerate(lines) if ln.startswith("OPERATOR_THESIS:"))
    assert lines[i + 1].startswith("STRUCTURAL_CONTEXT:")  # placement pinned


def test_structural_context_does_not_change_grounded():
    base = sentinel_context_pack(_sentinel(), as_of=AS_OF)
    withctx = sentinel_context_pack(_sentinel(), as_of=AS_OF, structural_context=_THESIS)
    assert base.grounded == withctx.grounded  # evidence, not permission


def test_filter_supports_a_backdrop_citation():
    pack = sentinel_context_pack(_sentinel(), as_of=AS_OF, structural_context=_THESIS)
    conf, res = apply_filter(['the thesis cites a "structural silver supply deficit"'],
                             pack, confidence="MODERATE")
    assert res.flagged == 0 and conf == "MODERATE"  # not flagged unsupported / dampened


# ── the load-bearing wiring: keyed on SYMBOL, not the framer's theme name ──────

def test_build_context_pack_keys_backdrop_on_symbol_not_name():
    # the production failure the red-team caught: keying on candidate.name (the framer slug) misses.
    cand = _sentinel(symbol="AG", name="silver_price_mean_reversion")
    pack = build_context_pack(cand, news=None, as_of=AS_OF, theme_theses={"AG": _THESIS})
    assert pack.structural_context == _THESIS
    assert "STRUCTURAL_CONTEXT:" in pack.as_prompt_block()


def test_build_context_pack_hand_seed_gets_no_backdrop():
    hs = Theme(name="copper", symbol="FCX", direction="bullish", thesis="copper deficit",
               source="hand-seed")
    pack = build_context_pack(hs, news=None, as_of=AS_OF, theme_theses={"FCX": _THESIS})
    assert pack.structural_context is None and "STRUCTURAL_CONTEXT" not in pack.as_prompt_block()


def test_build_context_pack_sentinel_without_map_is_byte_identical():
    cand = _sentinel()
    assert build_context_pack(cand, news=None, as_of=AS_OF, theme_theses=None).structural_context is None
    assert build_context_pack(cand, news=None, as_of=AS_OF, theme_theses={}).structural_context is None


# ── load_theme_theses (symbol→basket→register thesis) ─────────────────────────

def test_load_theme_theses_maps_symbol_to_basket_thesis(tmp_path):
    config = {"universe": {"themes": {"silver_deficit": ["AG", "PAAS"], "seaborne_freight": ["FRO"]}}}
    reg = {"themes": {"silver_deficit": {"thesis": "silver"}, "seaborne_freight": {"thesis": "freight"}}}
    p = tmp_path / "reg.json"
    p.write_text(json.dumps(reg))
    assert load_theme_theses(config, register_path=str(p)) == {
        "AG": "silver", "PAAS": "silver", "FRO": "freight"}


def test_load_theme_theses_fail_soft_missing_file(tmp_path):
    config = {"universe": {"themes": {"silver_deficit": ["AG"]}}}
    assert load_theme_theses(config, register_path=str(tmp_path / "nope.json")) == {}


def test_load_theme_theses_omits_baskets_without_thesis(tmp_path):
    config = {"universe": {"themes": {"x": ["AAA"], "y": ["BBB"]}}}
    reg = {"themes": {"x": {"thesis": "t"}, "y": {}}}  # y has no thesis → BBB omitted
    p = tmp_path / "r.json"
    p.write_text(json.dumps(reg))
    assert load_theme_theses(config, register_path=str(p)) == {"AAA": "t"}
