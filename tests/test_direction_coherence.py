"""PREREG_DIRECTION_COHERENCE — the composition-only union filter.

Pinned: only a SENTINEL framed BEARISH is ever checked; it is withheld only when filed revenue is growing
AND accelerating (natural zeros); missing data, no provider, or a read error NEVER withholds; one withheld
set is removed identically from every consumer's union; the record-segmenting stamp appears only when on.
"""
from __future__ import annotations

import json

import direction_coherence as dc
from themes import Theme


def _t(sym, direction="bearish", source="sentinel"):
    return Theme(name=f"{sym}-theme", symbol=sym, direction=direction, thesis="t", source=source,
                 sentinel_id=1 if source == "sentinel" else None, markers={"mom_recent": -0.1})


def _rev(yoy=None, accel=None):
    out = []
    if yoy is not None:
        out.append({"concept": "revenue", "metric": "qtr_yoy", "value": yoy})
    if accel is not None:
        out.append({"concept": "revenue", "metric": "qtr_yoy_accel", "value": accel})
    return out


def _filter(table):
    return dc.CoherenceFilter(lines_of=lambda s: table.get(s))


def test_growing_and_accelerating_verdict_uses_natural_zeros():
    assert dc.revenue_growing_and_accelerating(_rev(0.30, 0.086)) is True
    assert dc.revenue_growing_and_accelerating(_rev(0.30, 0.0)) is False     # flat accel is not accelerating
    assert dc.revenue_growing_and_accelerating(_rev(0.0, 0.2)) is False      # zero growth is not growing
    assert dc.revenue_growing_and_accelerating(_rev(-0.015, 0.007)) is False  # the CC case: shrinking
    assert dc.revenue_growing_and_accelerating(_rev(0.30, None)) is None      # one filed quarter: no accel
    assert dc.revenue_growing_and_accelerating(None) is None
    assert dc.revenue_growing_and_accelerating([{"concept": "capex", "metric": "qtr_yoy", "value": 9}]) is None


def test_only_a_bearish_sentinel_is_ever_withheld():
    f = _filter({"AMSC": _rev(0.30, 0.086), "LUNR": _rev(3.04, 3.25), "ETN": _rev(0.2, 0.1),
                 "CC": _rev(0.2, 0.1)})
    union = [_t("AMSC"), _t("ETN", direction="bullish"), _t("CC", source="hand-seed"), _t("LUNR")]
    out = f.apply(union)
    assert [t.symbol for t in out] == ["ETN", "CC"]            # order of the kept names preserved
    assert set(f.withheld) == {("AMSC", "bearish"), ("LUNR", "bearish")}


def test_missing_or_failing_data_never_withholds():
    def boom(sym):
        raise RuntimeError("edgar down")

    f = _filter({"KLAR": _rev(0.248, None), "NEWCO": None})
    out = f.apply([_t("KLAR"), _t("NEWCO")])
    assert [t.symbol for t in out] == ["KLAR", "NEWCO"] and not f.withheld
    assert sorted(f.kept_no_accel) == ["KLAR", "NEWCO"]

    g = dc.CoherenceFilter(lines_of=boom)
    assert [t.symbol for t in g.apply([_t("AMSC")])] == ["AMSC"] and g.errors == 1 and not g.withheld

    none = dc.CoherenceFilter.from_fundamentals(None, as_of=None)
    assert [t.symbol for t in none.apply([_t("AMSC")])] == ["AMSC"]
    assert "fundamentals unavailable" in none.summary()


def test_one_withheld_set_is_removed_identically_from_every_union():
    f = _filter({"AMSC": _rev(0.30, 0.086)})
    f.apply([_t("AMSC"), _t("KTOS")])
    shadow_union = [_t("KTOS"), _t("AMSC"), _t("AMSC", direction="bullish"), _t("RDW")]
    out = f.exclude(shadow_union)
    # the bearish AMSC lineage goes; the OPPOSITE-direction AMSC lineage is a different bet and stays
    assert [(t.symbol, t.direction) for t in out] == [("KTOS", "bearish"), ("AMSC", "bullish"),
                                                      ("RDW", "bearish")]
    empty = _filter({})
    empty.apply([_t("KTOS")])
    assert empty.exclude(shadow_union) == shadow_union        # nothing withheld → unchanged


def test_corpus_is_read_once_per_symbol_per_cycle():
    calls = []
    f = dc.CoherenceFilter(lines_of=lambda s: calls.append(s) or _rev(0.3, 0.1))
    f.apply([_t("AMSC"), _t("AMSC")])
    assert calls == ["AMSC"]


def test_summary_is_the_durable_record():
    f = _filter({"AMSC": _rev(0.30, 0.086), "KLAR": _rev(0.248, None)})
    f.apply([_t("AMSC"), _t("KLAR")])
    assert f.summary() == "direction-coherence: withheld=['AMSC'] kept_no_accel=['KLAR'] errors=0"


def test_stamp_is_record_segmenting_only_when_enabled(convexity_db):
    import orchestrator
    import state
    from council.router import FakeRouter

    on = {"council": {"cheap_reserve_slots": 3, "fairness_slots": 2, "direction_coherence": {"enabled": True}}}
    off = {"council": {"cheap_reserve_slots": 3, "fairness_slots": 2}}
    for cfg, want in ((on, "cheap_reserve_v1+fairness_v1.1+dircoherence_v1"),
                      (off, "cheap_reserve_v1+fairness_v1.1")):
        run_id = state.record_run(convexity_db, mode="TEST", equity=None, note="t")
        orchestrator._stamp_council_health(convexity_db, run_id, cfg, FakeRouter(), catalysts=None)
        mix = json.loads(convexity_db.execute("SELECT model_mix FROM runs WHERE id=?",
                                              (run_id,)).fetchone()["model_mix"])
        assert mix["union_rank"] == want
