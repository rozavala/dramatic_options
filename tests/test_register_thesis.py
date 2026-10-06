"""PREREG_EVIDENCE_GROUNDING amendment A2 + the Rule 0 dated amendment (2026-10-06): a sentinel's council pack
shows the operator's council-facing register thesis for its basket. The raw register `thesis` (operator-facing:
process notes, price and convexity language) is never read."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import register_theses
import sentinels
from council.context import SENTINEL_NO_OPERATOR_THESIS, build_context_pack, sentinel_context_pack
from council.filters import evidence_text
from themes import Theme

REPO = Path(__file__).resolve().parents[1]
AS_OF = datetime(2026, 10, 6, 19, 45)
SKEPTIC = "a corrective bounce rather than a fundamental secular breakout"
FIG = Theme("short-term mean reversion", "FIG", "bullish", SKEPTIC, source="sentinel",
            markers={"momentum": 1.2, "price": 23.0, "adv_usd": 5e7}, basket="design_software_ai")
# Everything a council-facing thesis must never contain: council-verdict words, cheapness/IV/convexity, price
# moves, process notes.
FORBIDDEN = re.compile(r"under.narrated|at.inflection|council|convexity|cheap|\bIV\b|momentum|price return|"
                       r"trailing return|−\d|IPO froth|round-trip|de-rated|busted|priced|PINNED|delegation|"
                       r"premise-currency|admission", re.I)


def test_every_register_theme_has_a_clean_council_thesis():
    themes = json.loads((REPO / "universe_register.json").read_text())["themes"]
    for key, t in themes.items():
        ct = t.get("council_thesis")
        assert ct, f"{key} has no council_thesis"
        assert not FORBIDDEN.search(ct), f"{key}: {FORBIDDEN.search(ct).group(0)!r}"


def test_the_loader_reads_council_thesis_never_the_raw_thesis(tmp_path):
    reg = {"themes": {"a": {"thesis": "RAW — under_narrated will FAIL at the council", "council_thesis": "clean",
                            "falsifier": "x drops (Draft-dated under the operator's admission delegation)"},
                      "b": {"thesis": "raw only, no council_thesis"}}}
    p = tmp_path / "r.json"
    p.write_text(json.dumps(reg))
    out = register_theses.load(p)
    assert out == {"a": {"thesis": "clean", "falsifier": "x drops", "added": None}}


def test_the_live_register_loads_and_falsifiers_lose_their_process_notes():
    out = register_theses.load()
    assert len(out) == 14
    for k, v in out.items():
        assert v["falsifier"] and "Draft-dated" not in v["falsifier"] and "AI-drafted" not in v["falsifier"], k
        assert "premise-currency" not in v["falsifier"] and not v["falsifier"].startswith("The card's"), k


def test_unreadable_register_is_empty_not_an_error(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json")
    assert register_theses.load(p) == {}


def test_a_sentinel_pack_shows_the_basket_thesis_and_the_framer_summary():
    reg = register_theses.load()
    pack = build_context_pack(FIG, news=None, as_of=AS_OF, sentinel_provenance=True, register_theses=reg)
    block = pack.as_prompt_block()
    assert "OPERATOR_THESIS (the operator's admission hypothesis for basket 'design_software_ai'" in block
    assert reg["design_software_ai"]["thesis"] in block and "OPERATOR_FALSIFIER:" in block
    assert SKEPTIC in block and "DISCOVERY_SUMMARY" in block
    shown = reg["design_software_ai"]["thesis"] + " " + reg["design_software_ai"]["falsifier"]
    assert not FORBIDDEN.search(shown)                                       # what the council reads as content
    assert reg["design_software_ai"]["thesis"] in evidence_text(pack)       # quotable, not flagged
    plain = build_context_pack(FIG, news=None, as_of=AS_OF, sentinel_provenance=True)
    assert pack.grounded == plain.grounded                                   # evidence, never permission


def test_a_basket_without_a_thesis_keeps_none_on_file():
    t = Theme("x", "ETN", "bullish", SKEPTIC, source="sentinel", markers={"momentum": 1.0}, basket="ai_compute")
    pack = build_context_pack(t, news=None, as_of=AS_OF, sentinel_provenance=True,
                              register_theses=register_theses.load())
    assert f"OPERATOR_THESIS: {SENTINEL_NO_OPERATOR_THESIS}" in pack.as_prompt_block()


def test_hand_seeds_and_the_framer_are_untouched():
    reg = register_theses.load()
    hand = Theme("copper", "FCX", "bullish", "operator hand-seed thesis", basket="copper_supply")
    assert (build_context_pack(hand, news=None, as_of=AS_OF, sentinel_provenance=True, register_theses=reg)
            .as_prompt_block() == build_context_pack(hand, news=None, as_of=AS_OF).as_prompt_block())
    assert "register" not in (REPO / "council" / "sentinel.py").read_text()
    assert sentinel_context_pack(FIG, as_of=AS_OF).as_prompt_block() == \
        sentinel_context_pack(FIG, as_of=AS_OF, provenance=False, register_entry=reg["design_software_ai"]) \
        .as_prompt_block()


def test_discovered_sentinels_carry_their_basket():
    row = {"theme": "silver_price_momentum", "basket": "silver_deficit", "symbol": "HL", "direction": "bullish",
           "seed_thesis": "s", "framer_conviction": "MODERATE", "id": 7, "markers": None}
    assert sentinels.discovered_to_theme(row).basket == "silver_deficit"


def test_the_council_loads_theses_only_with_both_switches(monkeypatch):
    import council.council as cc
    seen = {}

    def fake_build(candidate, **kw):
        seen.update(kw)
        raise StopIteration

    monkeypatch.setattr(cc, "build_context_pack", fake_build)
    monkeypatch.setattr(cc, "kill_switch_active", lambda: False)
    clock = type("C", (), {"now": lambda self: AS_OF})()
    for cfg, expect in (({"pack_provenance": True, "register_thesis": True}, True),
                        ({"pack_provenance": False, "register_thesis": True}, False),
                        ({"pack_provenance": True}, False)):
        seen.clear()
        try:
            cc.propose([FIG], router=None, config={"council": cfg}, clock=clock)
        except StopIteration:
            pass
        assert bool(seen["register_theses"]) is expect, cfg


def test_live_config_turns_it_on():
    cfg = json.loads((REPO / "config.json").read_text())
    assert cfg["council"]["register_thesis"] is True and cfg["council"]["pack_provenance"] is True
