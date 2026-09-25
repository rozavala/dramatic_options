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


def _rev_dated(yoy, accel, q="2026-06-30", f="2026-08-05"):
    return [{"concept": "revenue", "metric": "qtr_yoy", "value": yoy, "period_end": q, "filed": f},
            {"concept": "revenue", "metric": "qtr_yoy_accel", "value": accel, "period_end": q, "filed": f}]


def test_summary_carries_the_filed_facts_for_every_examined_bear():
    """#263: every bearish sentinel the rule examined appears in exactly one list, with the filed
    growth/acceleration, quarter end and filing date it was judged on — auditable from the record."""
    f = _filter({"AMSC": _rev_dated(0.3001, 0.0863), "CEG": _rev_dated(0.1321, -0.126),
                 "KLAR": _rev(0.248, None)})
    f.apply([_t("AMSC"), _t("CEG"), _t("KLAR"), _t("ETN", direction="bullish")])
    assert f.summary() == (
        "direction-coherence: withheld=[AMSC(+0.3001/+0.0863 q=2026-06-30 f=2026-08-05)] "
        "kept=[CEG(+0.1321/-0.1260 q=2026-06-30 f=2026-08-05)] kept_no_accel=[KLAR] errors=0")


def test_verdicts_unchanged_by_the_audit_trail():
    """The F2 window is open: the audit trail must not move a single verdict."""
    table = {"AMSC": _rev_dated(0.30, 0.086), "CC": _rev_dated(-0.0149, 0.0072),
             "SMR": _rev_dated(-0.9907, -0.0435), "CEG": _rev_dated(0.1321, -0.126), "CCJ": None}
    f = _filter(table)
    out = f.apply([_t(s) for s in table])
    assert [t.symbol for t in out] == ["CC", "SMR", "CEG", "CCJ"]
    assert set(f.withheld) == {("AMSC", "bearish")}
    assert f.kept == ["CC", "SMR", "CEG"] and f.kept_no_accel == ["CCJ"]


def test_parse_summary_reads_both_shapes_on_record():
    old = ("paper cycle · direction-coherence: withheld=['AMSC', 'GEV'] kept_no_accel=['CCJ', 'KLAR'] "
           "errors=0 · fwd_catalysts: rendered=1")
    p = dc.parse_summary(old)
    assert [i["symbol"] for i in p["withheld"]] == ["AMSC", "GEV"] and "yoy" not in p["withheld"][0]
    assert [i["symbol"] for i in p["kept_no_accel"]] == ["CCJ", "KLAR"] and p["kept"] == []

    f = _filter({"AMSC": _rev_dated(0.3001, 0.0863), "CEG": _rev_dated(0.1321, -0.126),
                 "KLAR": _rev(0.248, None)})
    f.apply([_t("AMSC"), _t("CEG"), _t("KLAR")])
    q = dc.parse_summary("x · " + f.summary())
    assert q["withheld"] == [{"symbol": "AMSC", "yoy": 0.3001, "accel": 0.0863,
                              "period_end": "2026-06-30", "filed": "2026-08-05"}]
    assert q["kept"][0]["symbol"] == "CEG" and q["kept"][0]["accel"] == -0.126
    assert [i["symbol"] for i in q["kept_no_accel"]] == ["KLAR"] and q["errors"] == 0
    assert dc.parse_summary("direction-coherence: fundamentals unavailable — nothing withheld")["status"] \
        == "unavailable"
    assert dc.parse_summary("paper cycle") is None


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
