"""#455 cheap-then-repriced report (PREREG_CHEAP_THEN_REPRICED §4.2–§7): unit rows derived at read time from the
sweep rows and the captured term records, hand-computed outcomes, the splits, the guard, aggregate-only output and no
lookahead."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import pytest

import cheap_repriced as cr
from data.cache import PointInTimeCache

D0 = date(2026, 11, 23)   # a Monday


def _sessions(n=70):
    out, d = [], D0
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _occ(sym, kind, strike):
    return f"{sym}270917{kind}{int(strike * 1000):08d}"


def _world(names, *, iv_rv_of, mult_of, n=70, spot=100.0, kind="C", strike_of=lambda s: 125.0, rv63=0.5,
           iv_rv_cheap=lambda s: True):
    """Sweeps + term records: every name structured every session on the same wing; the wing's mid at t is 1.00 and at
    every later session ``mult_of(sym)``; IV 0.40 at t and 0.45 later; spot 100 → 110; iv_rv constant per name."""
    sess = _sessions(n)
    sweeps, terms = {}, {s: {} for s in names}
    for i, d in enumerate(sess):
        sweeps[d] = {}
        for s in names:
            wing = _occ(s, kind, strike_of(s))
            sweeps[d][s] = {"structured": True, "iv_rv": iv_rv_of(s), "cheap": iv_rv_cheap(s), "wing": wing,
                            "frame_version": "f1"}
            m = 1.0 if i == 0 else mult_of(s)
            terms[s][d] = {"ts": f"{d}T20:45:00+00:00", "spot": spot if i == 0 else spot * 1.1, "rv": 0.5,
                           "rv63": rv63, "quotes": {wing: [m * 0.9, m * 1.1, 0.40 if i == 0 else 0.45]}}
    return sweeps, terms, sess


def test_no_capture_no_rows():
    sweeps, terms, _ = _world(["AAA"], iv_rv_of=lambda s: 1.0, mult_of=lambda s: 1.0)
    for recs in terms.values():
        for r in recs.values():
            r.pop("quotes")
    rows, _ = cr.build_rows(sweeps, terms, ["AAA"])
    assert rows == [] and cr.report_from(rows, {}, as_of=D0)["status"] == "no outcome rows yet"


def test_hand_computed_outcomes_for_one_row():
    sweeps, terms, sess = _world(["AAA", "BBB", "CCC"], iv_rv_of=lambda s: {"AAA": 0.8, "BBB": 0.9, "CCC": 1.1}[s],
                                 mult_of=lambda s: 2.5, kind="P", strike_of=lambda s: 75.0)
    rows, ex = cr.build_rows(sweeps, terms, ["AAA", "BBB", "CCC"])
    t0 = [r for r in rows if r["t"] == sess[0]]
    assert [r["tercile_cheapest"] for r in sorted(t0, key=lambda r: r["iv_rv"])] == [True, False, False]   # ⌈3/3⌉=1
    o = next(r for r in t0 if r["symbol"] == "AAA")["outcomes"][21]
    assert o["o1"] == pytest.approx(2.5)                                     # mid 2.5 / mid 1.0
    assert o["realizable"] == pytest.approx(2.25 / 1.1)                      # bid(t+h) / ask(t)
    assert o["o2"] == pytest.approx(5.0)                                     # 0.45 − 0.40 = 5 vol points
    assert o["o3"] == pytest.approx(-0.10)                                   # a put: spot +10% is −10% directional
    assert o["o4"] == pytest.approx(0.0)
    assert ex == {}
    # unit dates are the first sweep date of each ISO week only
    assert sorted({r["t"] for r in rows}) == cr.unit_dates(sess)


def test_a_wing_beyond_40pct_otm_is_excluded_and_counted():
    sweeps, terms, sess = _world(["AAA", "BBB"], iv_rv_of=lambda s: 1.0, mult_of=lambda s: 1.0,
                                 strike_of=lambda s: 145.0 if s == "AAA" else 140.0)
    rows, ex = cr.build_rows(sweeps, terms, ["AAA", "BBB"])
    # at the first unit date spot is 100: C145 is 45% OTM (out), C140 exactly 40% (in). Later spot is 110, where C145 is
    # 31.8% OTM — measured at each row's own t, so AAA is back in from the second unit date.
    assert {r["symbol"] for r in rows if r["t"] == sess[0]} == {"BBB"}
    assert {r["symbol"] for r in rows if r["t"] != sess[0]} == {"AAA", "BBB"}
    assert ex == {"wing > 40% OTM at t": 1}


def test_unquoted_rows_are_counted_and_set_to_zero_in_the_worst_case():
    names = [f"N{i:02d}" for i in range(60)]
    sweeps, terms, sess = _world(names, iv_rv_of=lambda s: int(s[1:]) / 100.0,
                                 mult_of=lambda s: 2.0 if int(s[1:]) < 20 else 1.0)
    h_date = sess[21]
    terms["N00"][h_date]["quotes"] = {list(terms["N00"][h_date]["quotes"])[0]: None}   # contract gone at t+21
    rows, _ = cr.build_rows(sweeps, terms, names)
    t0 = [r for r in rows if r["t"] == sess[0]]
    c = cr.contrast([r for r in t0 if r["tercile_cheapest"]], [r for r in t0 if not r["tercile_cheapest"]], 21)
    assert c["n"] == [20, 40] and c["names"] == [20, 40] and c["unquoted"] == [1, 0]
    assert c["o1_mid_multiple"]["median"] == [2.0, 1.0] and c["o1_mid_multiple"]["diff"] == 1.0
    assert c["o1_unquoted_as_0"]["median"] == [2.0, 1.0]                     # 19 of 20 still 2.0
    assert c["o1_mid_multiple"]["ci95_name_blocked"] == (1.0, 1.0)
    assert c["o1_mid_multiple"]["mann_whitney_u"] == 19 * 40 and c["o1_mid_multiple"]["u_note"].startswith("rows")
    assert c["paid"]["share"] == [round(19 / 20, 4), 0.0]                    # unquoted counts as not paid


def test_guard_needs_twenty_rows_and_eight_names():
    names = [f"N{i:02d}" for i in range(9)]
    sweeps, terms, _ = _world(names, iv_rv_of=lambda s: int(s[1:]) / 10.0, mult_of=lambda s: 1.5)
    rows, _ = cr.build_rows(sweeps, terms, names)
    rep = cr.report_from(rows, {}, as_of=D0 + timedelta(days=200))
    for h in cr.HORIZONS:
        assert rep["E1_cheapest_tercile_vs_rest"][h]["guard"] == "n<20"   # 3 cheapest names a week < 8 names


def test_e2_dependence_on_rv63_and_e3_counts():
    names = [f"N{i:02d}" for i in range(6)]
    sweeps, terms, _ = _world(names, iv_rv_of=lambda s: 1.0, mult_of=lambda s: 1.0, rv63=0.3,
                              iv_rv_cheap=lambda s: s != "N05")
    terms["N04"] = {d: {k: v for k, v in r.items() if k != "rv63"} for d, r in terms["N04"].items()}
    rows, _ = cr.build_rows(sweeps, terms, names)
    r = next(x for x in rows if x["symbol"] == "N00")
    assert r["atm_iv"] == pytest.approx(0.5) and r["dependent"] is True       # 0.5 / 0.3 = 1.67 > 1.2
    assert next(x for x in rows if x["symbol"] == "N04")["dependent"] is None
    rep = cr.report_from(rows, {}, as_of=D0 + timedelta(days=200))
    assert rep["E2_no_rv63"] == len({x["t"] for x in rows})                   # one cheap row a week without rv63
    assert rep["E3_cheap_vs_not_cheap_counts"][21]["not_cheap"] > 0
    assert rep["E3_never_filled_by"] == (D0 + timedelta(days=200)).isoformat()


def test_output_is_aggregate_only():
    names = [f"Z{i:02d}X" for i in range(30)]
    sweeps, terms, _ = _world(names, iv_rv_of=lambda s: int(s[1:3]) / 10.0, mult_of=lambda s: 1.2)
    rows, _ = cr.build_rows(sweeps, terms, names)
    blob = json.dumps(cr.report_from(rows, {}, as_of=D0 + timedelta(days=200)), default=str) + cr.render(
        cr.report_from(rows, {}, as_of=D0 + timedelta(days=200)))
    assert not any(n in blob for n in names) and "270917" not in blob


def test_no_lookahead_an_unmatured_horizon_and_a_future_record(tmp_path):
    sweeps, terms, sess = _world(["AAA"], iv_rv_of=lambda s: 1.0, mult_of=lambda s: 3.0, n=30)
    rows, _ = cr.build_rows(sweeps, terms, ["AAA"])
    r0 = next(r for r in rows if r["t"] == sess[0])
    assert r0["outcomes"][21] is not None and r0["outcomes"][42] is None    # only 29 later sessions exist
    # a record that is NOT the one at exactly t+h never feeds O1: change every later record except t+21
    for d in sess[1:]:
        if d != sess[21]:
            q = terms["AAA"][d]["quotes"]
            terms["AAA"][d]["quotes"] = {k: [99.0, 101.0, 0.9] for k in q}
    rows, _ = cr.build_rows(sweeps, terms, ["AAA"])
    assert next(r for r in rows if r["t"] == sess[0])["outcomes"][21]["o1"] == pytest.approx(3.0)
    # load_terms never loads a record dated after as_of
    cache = PointInTimeCache(tmp_path / "c")
    recs = [{"ts": f"{d}T20:45:00+00:00", "spot": 1.0} for d in sess[:25]]
    cache.write("iv_term_snapshot", "AAA", recs, coverage_from=datetime(2026, 11, 1, tzinfo=UTC),
                coverage_through=datetime(2027, 6, 1, tzinfo=UTC))
    got = cr.load_terms(cache, ["AAA"], upto=date.fromisoformat(sess[10]))["AAA"]
    assert max(got) == sess[10] and len(got) == 11


def test_report_reads_the_db_and_the_cache(convexity_db, tmp_path):
    import state

    conn = convexity_db
    rid = state.record_run(conn, mode="PAPER", equity=None, note="t")
    with conn:
        conn.execute("UPDATE runs SET frame_version = 'f1' WHERE id = ?", (rid,))
    state.record_gate_dualread(conn, run_id=rid, as_of="2026-11-23T20:45:00+00:00", symbol="FCX", feed="opra",
                               source="sweep", structured=True, iv_rv=0.9, otm_skew=1.0, cheap=True,
                               wing=_occ("FCX", "C", 125.0), note=None)
    rows = cr.sweep_rows(conn, upto=date(2026, 11, 23))
    assert rows == {"2026-11-23": {"FCX": {"structured": True, "iv_rv": 0.9, "cheap": 1,
                                           "wing": _occ("FCX", "C", 125.0), "frame_version": "f1"}}}
    assert cr.sweep_rows(conn, upto=date(2026, 11, 22)) == {}                # nothing after as_of
    rep = cr.report(conn, PointInTimeCache(tmp_path / "c", offline=True),
                    {"universe": {"themes": {"x": ["FCX"]}}}, as_of=date(2026, 11, 23))
    assert rep["status"] == "no outcome rows yet"


# ── #531 review: the cohort at t is the sweep's own population; the pinned first read per horizon ──────────────────

def test_the_cohort_at_t_is_the_sweeps_population_not_todays_config(convexity_db, tmp_path):
    """F1 (§4.2, §10): a later universe edit must not re-cut a past unit date. The report reads the names the sweep
    covered at t; config.universe is not consulted."""
    import state

    conn = convexity_db
    rid = state.record_run(conn, mode="PAPER", equity=None, note="t")
    sess = _sessions(30)
    cache = PointInTimeCache(tmp_path / "c")
    names = ["AAA", "BBB", "CCC"]
    for s, ivrv in zip(names, (0.8, 0.9, 1.1), strict=True):
        wing = _occ(s, "C", 125.0)
        recs = []
        for d in sess:
            state.record_gate_dualread(conn, run_id=rid, as_of=f"{d}T20:45:00+00:00", symbol=s, feed="opra",
                                       source="sweep", structured=True, iv_rv=ivrv, otm_skew=1.0, cheap=True,
                                       wing=wing, note=None)
            recs.append({"ts": f"{d}T20:45:00+00:00", "spot": 100.0, "rv": 0.5, "rv63": 0.5,
                         "quotes": {wing: [0.9, 1.1, 0.4]}})
        cache.write("iv_term_snapshot", s, recs, coverage_from=datetime(2026, 11, 1, tzinfo=UTC),
                    coverage_through=datetime(2027, 1, 30, tzinfo=UTC))
    ro = PointInTimeCache(tmp_path / "c", offline=True)
    as_of = date.fromisoformat(sess[-1])
    full = cr.report(conn, ro, {"universe": {"themes": {"x": names}}}, as_of=as_of)
    edited = cr.report(conn, ro, {"universe": {"themes": {"x": ["AAA", "BBB"]}}}, as_of=as_of)   # CCC removed later
    none = cr.report(conn, ro, {}, as_of=as_of)
    assert full == edited == none
    assert full["rows"] == 3 * len(cr.unit_dates(sess)) and full["names"] == 3


def test_no_contrast_before_the_pinned_first_read_even_with_a_passing_guard():
    """F2 (§7): one pinned first read per horizon. With a 2026-11-23 first row the dates are the prereg's own."""
    assert cr.first_reads(D0.isoformat()) == {21: "2027-01-17", 42: "2027-02-21", 63: "2027-03-21"}
    names = [f"N{i:02d}" for i in range(60)]
    sweeps, terms, _ = _world(names, iv_rv_of=lambda s: int(s[1:]) / 100.0,
                              mult_of=lambda s: 2.0 if int(s[1:]) < 20 else 1.0)
    rows, _ = cr.build_rows(sweeps, terms, names)
    before = cr.report_from(rows, {}, as_of=date(2027, 1, 16))["E1_cheapest_tercile_vs_rest"][21]
    assert before["guard"] == "pinned first read 2027-01-17" and "o1_mid_multiple" not in before
    assert before["n"][0] >= 20                                   # the guard alone would have passed
    on = cr.report_from(rows, {}, as_of=date(2027, 1, 17))
    assert "guard" not in on["E1_cheapest_tercile_vs_rest"][21]
    assert on["E1_cheapest_tercile_vs_rest"][21]["o1_mid_multiple"]["median"] is not None    # the contrast prints
    assert on["E1_cheapest_tercile_vs_rest"][42]["guard"] == "pinned first read 2027-02-21"   # each horizon its own
    assert on["E2_rv252_dependent_vs_rest_among_cheap"][42]["guard"] == "pinned first read 2027-02-21"
    assert "pinned first reads (h: date): {21: '2027-01-17'" in cr.render(on)


def test_a_print_after_the_pinned_first_read_is_labelled_a_reprint():
    """#532 (§7): later prints are "re-prints of the same pinned look, never new looks". Before the pinned date the
    contrast is counts-only and carries no look; on it, the first read; after it, a re-print, per horizon."""
    names = [f"N{i:02d}" for i in range(60)]
    sweeps, terms, _ = _world(names, iv_rv_of=lambda s: int(s[1:]) / 100.0,
                              mult_of=lambda s: 2.0 if int(s[1:]) < 20 else 1.0)
    rows, _ = cr.build_rows(sweeps, terms, names)
    key = "E1_cheapest_tercile_vs_rest"
    pre = cr.report_from(rows, {}, as_of=date(2027, 1, 16))
    before = pre[key]
    assert "look" not in before[21] and before[21]["guard"] == "pinned first read 2027-01-17"
    on = cr.report_from(rows, {}, as_of=date(2027, 1, 17))
    assert on[key][21]["look"] == "first read"
    assert "look" not in on[key][42] and on[key][42]["guard"] == "pinned first read 2027-02-21"   # each horizon its own
    after = cr.report_from(rows, {}, as_of=date(2027, 1, 24))
    assert after[key][21]["look"] == "re-print" and after["E2_rv252_dependent_vs_rest_among_cheap"][21]["look"] == "re-print"
    assert "look" not in after[key][42]
    out = cr.render(after)
    assert "h=21 [re-print of the 2027-01-17 look]" in out
    assert "re-print" not in cr.render(pre) and "first read of the" not in cr.render(pre)
    assert "h=21 [first read of the 2027-01-17 look]" in cr.render(on)
