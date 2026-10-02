"""Draft amendments of 2026-10-02 (both switches default OFF → byte-identical until the operator flips them).

1. **Pack provenance** (``council.pack_provenance``; PREREG_EVIDENCE_GROUNDING amendment A1; Finding B of 2026-09-29):
   a sentinel's thesis text is the discovery framer's skeptical summary. With the switch on, the council pack
   says plainly that the operator has stated no thesis, and renders the framer text on its own labelled line.
2. **Forward-catalyst sentinel scope** (``forward_catalysts.sentinel_scope``; channel prereg §11): the
   operator-pinned dated block reaches the council's sentinel packs too.

Neither may touch ``grounded`` (evidence, never permission), and the discovery framer's own pack — built by
``sentinel_context_pack`` with no switches — must stay byte-identical (the §6 leash).
"""
from __future__ import annotations

from datetime import datetime

from council.context import SENTINEL_NO_OPERATOR_THESIS, build_context_pack, sentinel_context_pack
from council.filters import evidence_text
from themes import Theme

AS_OF = datetime(2026, 10, 2, 19, 45)
SKEPTIC = "a corrective bounce rather than a fundamental secular breakout"
SENT = Theme("design_software_ai", "FIG", "bearish", SKEPTIC, source="sentinel",
             markers={"momentum": 1.2, "price": 23.0, "adv_usd": 5e7})
HAND = Theme("bead_buildout", "ADTN", "bullish", "BEAD construction-start expression")
ITEM = {"class": "a", "claim": "EPA final rule takes effect", "event_date": "2026-11-16",
        "as_of": "2026-09-27", "expires": "2026-11-23", "source": "FR 2026-19071"}


class _Cat:
    def __init__(self):
        self.calls: list[str] = []

    def items_asof(self, sym, as_of):
        self.calls.append(sym)
        return [dict(ITEM, symbol=sym)]


def test_default_off_is_byte_identical_to_the_framer_pack():
    council = build_context_pack(SENT, news=None, as_of=AS_OF).as_prompt_block()
    framer = sentinel_context_pack(SENT, as_of=AS_OF).as_prompt_block()
    assert f"OPERATOR_THESIS: {SKEPTIC}" in council and "DISCOVERY_SUMMARY" not in council
    assert framer == sentinel_context_pack(SENT, as_of=AS_OF, provenance=False).as_prompt_block()


def test_provenance_on_labels_the_framer_text_honestly():
    pack = build_context_pack(SENT, news=None, as_of=AS_OF, sentinel_provenance=True)
    block = pack.as_prompt_block()
    assert f"OPERATOR_THESIS: {SENTINEL_NO_OPERATOR_THESIS}" in block
    assert SKEPTIC in block and "NOT the operator's view" in block
    assert block.index("OPERATOR_THESIS") < block.index("DISCOVERY_SUMMARY")
    # evidence, never permission: grounding is unchanged by the relabel
    off = build_context_pack(SENT, news=None, as_of=AS_OF)
    assert pack.grounded == off.grounded
    # an agent quoting the framer text must not be flagged unsupported (the evidence pool carries it)
    assert SKEPTIC in evidence_text(pack)


def test_provenance_never_touches_a_hand_seed():
    on = build_context_pack(HAND, news=None, as_of=AS_OF, sentinel_provenance=True).as_prompt_block()
    off = build_context_pack(HAND, news=None, as_of=AS_OF).as_prompt_block()
    assert on == off and "DISCOVERY_SUMMARY" not in on


def test_sentinel_scope_off_never_calls_the_provider_for_a_sentinel():
    cat = _Cat()
    pack = build_context_pack(SENT, news=None, as_of=AS_OF, catalysts=cat)
    assert cat.calls == [] and pack.forward_catalysts == []
    assert "FORWARD_CATALYSTS" not in pack.as_prompt_block()


def test_sentinel_scope_on_renders_the_block_without_changing_grounding():
    cat = _Cat()
    pack = build_context_pack(SENT, news=None, as_of=AS_OF, catalysts=cat, sentinel_catalysts=True)
    assert cat.calls == ["FIG"]
    assert "FORWARD_CATALYSTS" in pack.as_prompt_block() and "2026-11-16" in pack.as_prompt_block()
    assert pack.grounded == build_context_pack(SENT, news=None, as_of=AS_OF).grounded


def test_sentinel_scope_is_fail_soft():
    class _Boom:
        def items_asof(self, sym, as_of):
            raise RuntimeError("provider down")
    pack = build_context_pack(SENT, news=None, as_of=AS_OF, catalysts=_Boom(), sentinel_catalysts=True)
    assert pack.forward_catalysts == []


def test_the_framer_path_never_receives_either_switch():
    src = open("council/sentinel.py").read()
    assert "sentinel_context_pack(cand, as_of=as_of)" in src   # no provenance, no catalysts


def test_council_reads_both_switches_from_config(monkeypatch):
    import council.council as cc
    seen = {}

    def fake_build(candidate, **kw):
        seen.update(kw)
        raise StopIteration  # stop before any LLM call

    monkeypatch.setattr(cc, "build_context_pack", fake_build)
    monkeypatch.setattr(cc, "kill_switch_active", lambda: False)
    cfg = {"council": {"pack_provenance": True}, "forward_catalysts": {"sentinel_scope": True}}
    try:
        cc.propose([SENT], router=None, config=cfg, clock=type("C", (), {"now": lambda self: AS_OF})())
    except StopIteration:
        pass
    assert seen["sentinel_provenance"] is True and seen["sentinel_catalysts"] is True


def test_live_config_leaves_both_switches_off_until_the_operator_word():
    import json
    cfg = json.load(open("config.json"))
    assert not cfg["council"].get("pack_provenance", False)
    assert not (cfg.get("forward_catalysts") or {}).get("sentinel_scope", False)
