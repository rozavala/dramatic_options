"""Issue #269 — the stale-fundamentals flag: telemetry only, fail-soft, checks only what the loop READ."""
from __future__ import annotations

from datetime import UTC, datetime

import fundamentals_staleness as fs

NOW = datetime(2026, 9, 25, 19, 45, tzinfo=UTC)


def _lines(*filed):
    return [{"concept": "revenue", "metric": "qtr_yoy", "value": 0.1, "filed": f} for f in filed]


def _filings(*rows):
    return [{"form": f, "ts": f"{d}T20:00:00+00:00"} for f, d in rows]


def test_newest_corpus_filed_and_newest_periodic():
    assert fs.newest_corpus_filed(_lines("2026-04-23", "2026-02-13")) == "2026-04-23"
    assert fs.newest_corpus_filed([{"concept": "x"}]) is None and fs.newest_corpus_filed(None) is None
    recs = _filings(("8-K", "2026-09-14"), ("10-Q", "2026-07-24"), ("10-Q/A", "2026-08-30"), ("425", "2026-09-24"))
    assert fs.newest_periodic(recs) == ("10-Q", "2026-07-24")      # 8-K / 425 / amendments never count
    assert fs.newest_periodic(_filings(("40-F", "2026-03-20"))) == ("40-F", "2026-03-20")
    assert fs.newest_periodic([]) is None


def test_is_lagging_needs_a_newer_report_outside_the_grace_window():
    assert fs.is_lagging("2026-04-23", ("10-Q", "2026-07-24"), NOW)             # the NEE case
    assert not fs.is_lagging("2026-08-05", ("10-Q", "2026-08-05"), NOW)         # corpus current
    assert not fs.is_lagging("2026-08-05", ("10-Q", "2026-09-24"), NOW)         # filed 1 day ago: grace
    assert fs.is_lagging("2026-08-05", ("10-Q", "2026-09-21"), NOW)             # 4 days ago: lagging
    assert not fs.is_lagging(None, ("10-Q", "2026-07-24"), NOW)
    assert not fs.is_lagging("2026-04-23", None, NOW)


def test_check_flags_only_real_lag_and_never_raises():
    corpus = {"NEE": _lines("2026-04-23"), "CC": _lines("2026-08-05"), "NEWCO": []}
    filings = {"NEE": _filings(("10-Q", "2026-07-24")), "CC": _filings(("10-Q", "2026-08-05"))}

    def filings_of(sym):
        if sym == "BOOM":
            raise TimeoutError("edgar down")
        return filings.get(sym)

    chk = fs.StalenessCheck(lines_of=lambda s: corpus.get(s, _lines("2026-08-01")), filings_of=filings_of)
    chk.run(["nee", "CC", "NEWCO", "BOOM"], NOW)
    assert chk.lagging == {"NEE": {"corpus_filed": "2026-04-23", "form": "10-Q", "filed": "2026-07-24"}}
    assert chk.no_corpus == ["NEWCO"] and chk.errors == 1 and chk.checked == 2
    assert chk.summary() == ("fundamentals-staleness: lagging=[NEE(corpus 2026-04-23 < 10-Q 2026-07-24)] "
                             "checked=2 no_corpus=1 errors=1")


def test_symbols_read_this_cycle_are_proposals_plus_the_rules_examined(convexity_db):
    import direction_coherence as dc
    import state
    from themes import Theme

    rid = state.record_run(convexity_db, mode="PAPER", equity=None, note="t")
    state.record_council_proposal(convexity_db, run_id=rid, as_of="t", theme="x", symbol="MRK",
                                  direction="bullish", conviction="LOW", status="dropped")
    coh = dc.CoherenceFilter(lines_of=lambda s: [
        {"concept": "revenue", "metric": "qtr_yoy", "value": 0.3},
        {"concept": "revenue", "metric": "qtr_yoy_accel", "value": 0.1}] if s == "AMSC" else None)
    coh.apply([Theme(name="t", symbol=s, direction="bearish", thesis="t", source="sentinel", sentinel_id=1)
               for s in ("AMSC", "KLAR")])
    assert fs.symbols_read_this_cycle(convexity_db, rid, coh) == {"MRK", "AMSC", "KLAR"}


def test_check_cycle_is_injectable_and_degrades_honestly():
    class _Fund:
        def corpus_asof(self, sym, as_of):
            return {"lines": _lines("2026-04-23")}

    line = fs.check_cycle(None, None, {}, _Fund(), NOW, cache=None,
                          coherence=type("C", (), {"withheld": {("NEE", "bearish"): "x"}, "kept": [],
                                                   "kept_no_accel": []})(),
                          filings_of=lambda s: _filings(("10-Q", "2026-07-24")))
    assert line.startswith("fundamentals-staleness: lagging=[NEE(corpus 2026-04-23 < 10-Q 2026-07-24)]")
    assert fs.check_cycle(None, None, {}, None, NOW, cache=None) == \
        "fundamentals-staleness: fundamentals unavailable — nothing checked"
    assert "no EDGAR user agent" in fs.check_cycle(None, None, {}, _Fund(), NOW, cache=None)


def test_parse_summary_round_trips():
    chk = fs.StalenessCheck(lines_of=lambda s: _lines("2026-04-23"),
                            filings_of=lambda s: _filings(("10-Q", "2026-07-24")))
    chk.run(["NEE"], NOW)
    p = fs.parse_summary("paper cycle · " + chk.summary() + " · fwd_catalysts: rendered=1")
    assert p == {"status": "ok", "checked": 1, "no_corpus": 0, "errors": 0,
                 "lagging": [{"symbol": "NEE", "corpus_filed": "2026-04-23", "form": "10-Q", "filed": "2026-07-24"}]}
    assert fs.parse_summary("fundamentals-staleness: fundamentals unavailable — nothing checked")["status"] \
        == "unavailable"
    assert fs.parse_summary("paper cycle") is None
