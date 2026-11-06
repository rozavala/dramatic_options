"""D3b forward falsifier-accuracy ledger: one sealed read per spec × name, outcomes counted later."""

import json
from datetime import UTC, datetime
from pathlib import Path

import falsifier_ledger as fl

SPEC = {"id": "cyber_sase.q_ending_1031", "theme": "cyber_sase", "direction": "bullish",
        "metric": "quarterly_revenue_yoy", "threshold": 0.20, "first_filed_after": "2026-10-31"}


def _pts():
    return [
        {"start": "2025-08-01", "end": "2025-10-31", "val": 100.0, "filed": "2025-12-05"},
        {"start": "2026-05-01", "end": "2026-07-31", "val": 110.0, "filed": "2026-09-05"},
        {"start": "2026-08-01", "end": "2026-10-31", "val": 115.0, "filed": "2026-12-04"},
    ]


def test_evaluate_waits_for_the_named_quarter():
    assert fl.evaluate(SPEC, _pts(), datetime(2026, 11, 20, tzinfo=UTC)) is None   # not filed yet
    r = fl.evaluate(SPEC, _pts(), datetime(2026, 12, 8, tzinfo=UTC))
    assert r == {"period_end": "2026-10-31", "filed": "2026-12-04", "value": 0.15, "threshold": 0.2, "fired": 1}


def test_no_year_ago_base_means_no_read():
    pts = [p for p in _pts() if p["end"] != "2025-10-31"]
    assert fl.evaluate(SPEC, pts, datetime(2026, 12, 8, tzinfo=UTC)) is None


def test_record_due_appends_once(tmp_path):
    ledger = tmp_path / "falsifier_ledger.csv"
    kw = dict(symbols_of=lambda k: ["NTSK"] if k == "cyber_sase" else [], points_of=lambda s: _pts(),
              close_of=lambda s: 21.5, specs=[SPEC], ledger_path=ledger)
    assert fl.record_due(as_of=datetime(2026, 11, 20, tzinfo=UTC), **kw) == []
    first = fl.record_due(as_of=datetime(2026, 12, 8, tzinfo=UTC), **kw)
    assert len(first) == 1 and first[0]["fired"] == 1 and first[0]["entry_close"] == 21.5
    assert fl.record_due(as_of=datetime(2026, 12, 9, tzinfo=UTC), **kw) == []   # sealed: never re-read
    assert len(fl._read_ledger(ledger)) == 1
    p = fl.panel(ledger_path=ledger, specs=[SPEC], symbols_of=kw["symbols_of"])
    assert p["summary"]["fired"] == 1 and p["waiting"] == []


def test_a_failing_name_is_skipped(tmp_path):
    def boom(_s):
        raise RuntimeError("edgar down")
    out = fl.record_due(symbols_of=lambda k: ["NTSK"], points_of=boom, close_of=lambda s: 1.0,
                        as_of=datetime(2026, 12, 8, tzinfo=UTC), specs=[SPEC], ledger_path=tmp_path / "l.csv")
    assert out == []


def test_report_counts_accuracy_and_false_alarms():
    rows = [{"fired": "1", "direction": "bullish", "r": -0.3}, {"fired": "1", "direction": "bullish", "r": 0.9},
            {"fired": "0", "direction": "bullish", "r": 0.1}, {"fired": "0", "direction": "bearish", "r": -0.6},
            {"fired": "1", "direction": "bullish", "r": None}]
    rep = fl.report(rows, outcome_of=lambda r: r["r"])
    assert rep["matured"] == 4
    assert rep["cells"] == {"fired_big": 1, "fired_not_big": 1, "quiet_big": 1, "quiet_not_big": 1}
    assert rep["accuracy"] == 0.5 and rep["false_alarm"] == 0.5


def test_shipped_specs_parse_and_name_real_baskets():
    specs = fl.load_specs()
    assert {s["id"] for s in specs} >= {SPEC["id"]}
    cfg = json.loads((Path(fl.__file__).parent / "config.json").read_text())
    themes = cfg["universe"]["themes"]
    for s in specs:
        assert s["theme"] in themes and s["metric"] == "quarterly_revenue_yoy" and 0 < s["threshold"] < 1


# FIG's real shape (SEC companyfacts CIK0001579878, extract_quarterly_revenue, fetched 2026-11-05): the 11-04
# 10-Q carries Q3-26 and its year-ago comparative, and the extractor keeps the latest filing per period, so
# both quarters read filed 2026-11-04.
FIG_SPEC = {"id": "design_software_ai.q3_2026_rev", "theme": "design_software_ai", "direction": "bullish",
            "metric": "quarterly_revenue_yoy", "threshold": 0.30, "first_filed_after": "2026-10-01"}
FIG_PTS = [
    {"start": "2024-07-01", "end": "2024-09-30", "val": 198639000.0, "filed": "2025-11-05"},
    {"start": "2025-04-01", "end": "2025-06-30", "val": 249640000.0, "filed": "2026-08-05"},
    {"start": "2025-07-01", "end": "2025-09-30", "val": 274173000.0, "filed": "2026-11-04"},
    {"start": "2026-04-01", "end": "2026-06-30", "val": 370083000.0, "filed": "2026-08-05"},
    {"start": "2026-07-01", "end": "2026-09-30", "val": 391415000.0, "filed": "2026-11-04"},
]


def test_the_reported_quarter_wins_over_its_year_ago_comparative():
    # #429: the first sealed read took Q3-25 (+38.03%, the comparative) instead of Q3-26 (+42.76%)
    r = fl.evaluate(FIG_SPEC, FIG_PTS, datetime(2026, 11, 5, 21, tzinfo=UTC))
    assert (r["period_end"], r["filed"], r["value"], r["fired"]) == ("2026-09-30", "2026-11-04", 0.4276, 0)


def test_the_earliest_filing_after_the_cutoff_still_decides():
    # a later filing's newer quarter does not jump the queue: the first filing after the cutoff is the read
    pts = FIG_PTS + [{"start": "2026-10-01", "end": "2026-12-31", "val": 400000000.0, "filed": "2027-02-20"}]
    assert fl.first_quarter_after(pts, "2026-10-01")["end"] == "2026-09-30"


def test_a_name_with_no_quarterly_points_warns_that_it_can_never_read(tmp_path, caplog):
    # #429: KLAR has no us-gaap quarterly revenue, so the bnpl spec was silently unreadable
    spec = {"id": "bnpl_payments.first_q_after_0913", "theme": "bnpl_payments", "metric": "quarterly_revenue_yoy",
            "threshold": 0.10, "first_filed_after": "2026-09-13"}
    with caplog.at_level("WARNING", logger="falsifier_ledger"):
        out = fl.record_due(symbols_of=lambda k: ["klar"], points_of=lambda s: [], close_of=lambda s: 1.0,
                            as_of=datetime(2026, 11, 5, tzinfo=UTC), specs=[spec], ledger_path=tmp_path / "l.csv")
    assert out == []
    assert [r.getMessage() for r in caplog.records] == [
        "falsifier ledger: no quarterly revenue points, so these can never read: "
        "['bnpl_payments.first_q_after_0913/KLAR']"]


def test_the_ledger_is_gitignored():
    # #429: the live L1 writes it in the live checkout; a deploy's `git clean -fd` must keep it
    import subprocess
    root = Path(fl.__file__).resolve().parent
    r = subprocess.run(["git", "check-ignore", "-q", "--no-index", "records/falsifier_ledger.csv"], cwd=root)
    assert r.returncode == 0
