"""scripts/catalyst_pin_suggestions.py — the pure suggestion core (no network)."""
from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("cps", REPO / "scripts" / "catalyst_pin_suggestions.py")
cps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cps)

TODAY = date(2026, 10, 6)
BASKETS = {"ai_compute": ["CEG", "NEE", "GEV"], "nuclear_fuel": ["SMR", "UEC"], "space_smallcap": ["RKLB"]}


def _row(doc, eff, title, abstract="", slug="environmental-protection-agency", typ="Rule"):
    return {"document_number": doc, "effective_on": eff, "title": title, "abstract": abstract, "type": typ,
            "agencies": [{"slug": slug}], "publication_date": "2026-09-17", "html_url": f"https://fr/{doc}"}


def test_keeps_a_keyword_hit_final_rule_with_a_future_effective_date():
    rows = [_row("2026-19071", "2026-11-16", "Partial Repeal of the Carbon Pollution Standards for Fossil "
                 "Fuel-Fired Electric Generating Units")]
    out = cps.suggest(rows, BASKETS, TODAY, pinned_docs={"2026-19071"})
    assert [s["document_number"] for s in out] == ["2026-19071"]
    assert out[0]["baskets"] == ["ai_compute"] and out[0]["names"] == ["CEG", "GEV", "NEE"] and out[0]["pinned"]


def test_drops_routine_classes_and_no_keyword_rules_and_counts_them():
    skipped: dict[str, int] = {}
    rows = [_row("a", "2026-10-20", "Airworthiness Directives; The Boeing Company Airplanes", "launch"),
            _row("b", "2026-10-20", "Air Plan Approval; New York; power plant SO2"),
            _row("c", "2026-10-20", "Estate Tax Closing Letter User Fee Update", slug="internal-revenue-service")]
    assert cps.suggest(rows, BASKETS, TODAY, skipped=skipped) == []
    assert skipped == {"routine": 2, "no_keyword": 1}


def test_effective_window_type_and_dedup():
    rows = [_row("past", "2026-10-06", "reactor rule"),              # effective today → not "ahead"
            _row("far", "2028-01-01", "reactor rule"),                # beyond the horizon
            _row("prop", "2026-12-01", "reactor rule", typ="Proposed Rule"),
            _row("ok", "2026-12-21", "Exemptions From Materials Licensing", "small modular reactor",
                 slug="nuclear-regulatory-commission"),
            _row("ok", "2026-12-21", "duplicate of ok", "reactor")]
    out = cps.suggest(rows, BASKETS, TODAY)
    assert [s["document_number"] for s in out] == ["ok"] and out[0]["baskets"] == ["nuclear_fuel"]


def test_a_keyword_basket_outside_the_universe_is_not_tagged():
    rows = [_row("x", "2026-12-01", "Hydrofluorocarbon allowance allocation under the AIM Act")]
    assert cps.suggest(rows, BASKETS, TODAY) == []        # refrigerant_transition is not in BASKETS


def test_render_says_suggestions_only_and_reports_skips():
    text = cps.render([], today=TODAY, since=date(2026, 9, 22), errors=["fcc: timeout"],
                      skipped={"routine": 3, "no_keyword": 4})
    assert "Suggestions only — nothing is pinned" in text and "Skipped: 3 routine" in text
    assert "4 with no basket keyword" in text and "fcc: timeout" in text


def test_the_script_never_writes_the_pin_file():
    src = (REPO / "scripts" / "catalyst_pin_suggestions.py").read_text()
    assert "forward_catalysts.json\").write" not in src and ".write_text" in src     # only --out writes
    assert src.count("write_text(") == 1
