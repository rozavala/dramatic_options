"""``dashboard_data.why_no_entry_panel`` (issue #351) — the per-name "why no entry" table + its three tiles.

The acceptance criteria pinned: every judged name gets exactly one row; the rows total back to
``funnel_panel.by_decision`` and ``council_stage_funnel.stages``; the expressible count is the gate-of-record
read (``state.unexpressible_symbols``); and a session where nothing reached the gate still renders."""

from __future__ import annotations

from datetime import UTC, datetime

import dashboard_data as dd
import state

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)
CFG = {"council": {"conviction_floor": "MODERATE"}}
AS_OF = "2026-10-26T19:45:00+00:00"


def _strat(include, veto=False):
    return {"strategist": {"include": include, "criteria_veto": veto,
                           "under_narrated": True, "at_inflection": include}}


def _prop(conn, rid, sym, conv, rat, status="dropped", as_of=AS_OF):
    return state.record_council_proposal(conn, run_id=rid, as_of=as_of, theme="t", symbol=sym,
                                         direction="bullish", conviction=conv, rationale=rat, status=status)


def _eval(conn, rid, sym, decision, pid=None, iv_rv=None, skew=None):
    state.record_convexity_eval(conn, run_id=rid, as_of=AS_OF, theme="t", symbol=sym, direction="bullish",
                                decision=decision, proposal_id=pid, iv_rv=iv_rv, otm_skew=skew)


def _read(conn, sym, structured, iv_rv=None, note=None, as_of="2026-10-26T22:00:00+00:00", rid=None):
    state.record_gate_dualread(conn, run_id=rid, as_of=as_of, symbol=sym, feed="opra", source="sweep",
                               structured=structured, iv_rv=iv_rv, otm_skew=4.0 if structured else None,
                               cheap=bool(structured and iv_rv is not None and iv_rv <= 1.2), note=note)


def _mixed_session(conn):
    """8 judged names covering every council stage + two that reached the gate."""
    rid = state.record_run(conn, mode="PAPER", equity=None)
    _prop(conn, rid, "UNGR", "NEUTRAL", {"dropped": "ungrounded (no numeric evidence)"})
    _prop(conn, rid, "ABST", "NEUTRAL", {"dropped": "proposer abstained (NEUTRAL)"})
    _prop(conn, rid, "DLOW", "LOW", _strat(False))
    _prop(conn, rid, "VETO", "HIGH", _strat(False, veto=True))
    _prop(conn, rid, "BFLR", "LOW", _strat(True))
    p_open = _prop(conn, rid, "TRAD", "MODERATE", _strat(True), status="traded")
    p_veto = _prop(conn, rid, "PROP", "HIGH", _strat(True), status="proposed")
    _prop(conn, rid, "NOEV", "MODERATE", _strat(True), status="proposed")  # reached the gate, no eval row
    _eval(conn, rid, "TRAD", "open", p_open, iv_rv=0.9, skew=3.0)
    _eval(conn, rid, "PROP", "veto-iv-gate", p_veto, iv_rv=1.7, skew=6.0)
    return rid


def test_one_row_per_judged_name_and_totals_reconcile(convexity_db):
    rid = _mixed_session(convexity_db)
    p = dd.why_no_entry_panel(convexity_db, CFG, now=NOW)
    stage = dd.council_stage_funnel(convexity_db, CFG)
    fun = dd.funnel_panel(convexity_db)["l1_decision"]
    assert p["run_id"] == rid == stage["run_id"] == fun["run_id"]
    assert sorted(r["symbol"] for r in p["rows"]) == sorted(
        ["UNGR", "ABST", "DLOW", "VETO", "BFLR", "TRAD", "PROP", "NOEV"])
    assert len(p["rows"]) == len({r["proposal_id"] for r in p["rows"]}) == stage["stages"]["proposed"] == 8
    by = {r["symbol"]: r for r in p["rows"]}
    assert by["UNGR"]["stage"] == "ungrounded" and by["ABST"]["stage"] == "proposer_abstained"
    assert by["VETO"]["stage"] == "criteria_vetoed" and by["DLOW"]["stage"] == "not_included"
    assert by["BFLR"]["stage"] == "below_floor" and by["BFLR"]["above_floor"] is False
    assert by["TRAD"]["veto_stage"] == "open" and by["TRAD"]["iv_rv"] == 0.9
    assert by["PROP"]["veto_stage"] == "veto-iv-gate" and by["PROP"]["iv_rv"] == 1.7
    assert by["NOEV"]["gate_decision"] is None and "no gate row" in by["NOEV"]["veto_stage"]
    # totals tie back to the two existing panels
    st = stage["stages"]
    assert p["totals"]["reached_gate"] == st["to_gate"] == 3
    assert p["totals"]["by_stage"].get("below_floor", 0) == st["below_floor"]
    assert p["totals"]["by_stage"].get("criteria_vetoed", 0) == st["criteria_vetoed"]
    assert p["totals"]["by_decision"] == fun["by_decision"] == {"open": 1, "veto-iv-gate": 1}
    assert p["reconciliation"] == {"by_decision_ok": True, "stages_ok": True}


def test_unattributed_gate_rows_still_reconcile(convexity_db):
    rid = _mixed_session(convexity_db)
    _eval(convexity_db, rid, "SEED", "veto-eligibility", pid=None)   # a gate row with no council proposal
    p = dd.why_no_entry_panel(convexity_db, CFG, now=NOW)
    assert p["totals"]["unattributed_gate_rows"] == 1
    assert p["totals"]["by_decision"] == dd.funnel_panel(convexity_db)["l1_decision"]["by_decision"]
    assert p["reconciliation"]["by_decision_ok"] is True


def test_session_where_nothing_reached_the_gate(convexity_db):
    rid = state.record_run(convexity_db, mode="PAPER", equity=None)
    for sym, conv, rat in (("AAA", "LOW", _strat(True)), ("BBB", "NEUTRAL", {"dropped": "proposer abstained (NEUTRAL)"}),
                           ("CCC", "LOW", _strat(False, veto=True))):
        _prop(convexity_db, rid, sym, conv, rat)
    p = dd.why_no_entry_panel(convexity_db, CFG, now=NOW)
    fun = dd.funnel_panel(convexity_db)["l1_decision"]
    assert p["run_id"] == rid and not p["empty"]
    assert [r["symbol"] for r in p["rows"]] == ["AAA", "BBB", "CCC"]       # one row each, none dropped for lack of a gate row
    assert all(r["gate_decision"] is None for r in p["rows"])
    assert p["totals"]["reached_gate"] == 0 and p["totals"]["by_decision"] == {} == fun["by_decision"]
    assert fun["evaluated"] == 0 and fun["proposed"] == 3
    assert p["reconciliation"] == {"by_decision_ok": True, "stages_ok": True}
    assert p["tiles"]["last_above_floor"] is None            # nothing above floor, ever
    assert p["tiles"]["last_order"] is None                  # nothing ever submitted


def test_floor_follows_config(convexity_db):
    _mixed_session(convexity_db)
    p = dd.why_no_entry_panel(convexity_db, {"council": {"conviction_floor": "HIGH"}}, now=NOW)
    by = {r["symbol"]: r for r in p["rows"]}
    assert p["floor"] == "HIGH" and by["TRAD"]["stage"] == "below_floor" and by["PROP"]["stage"] == "to_gate"
    assert p["reconciliation"]["stages_ok"] is True


def test_expressible_matches_the_gate_of_record_read(convexity_db):
    _mixed_session(convexity_db)
    for sym in ("TRAD", "PROP", "UNGR", "NOEV"):
        _read(convexity_db, sym, 1, iv_rv=1.0)
    _read(convexity_db, "ABST", 0, note="no_eligible_contract_in_tenor_window")
    _read(convexity_db, "OLD", 0, note="stale", as_of="2026-10-01T22:00:00+00:00")   # stale: neither side of n/N
    # a later row supersedes an earlier one for the same name (latest read wins)
    _read(convexity_db, "VETO", 1, iv_rv=1.0, as_of="2026-10-25T22:00:00+00:00")
    _read(convexity_db, "VETO", 0, note="wrong_side", as_of="2026-10-26T22:00:00+00:00")
    p = dd.why_no_entry_panel(convexity_db, CFG, now=NOW)
    ex = p["tiles"]["expressible"]
    unexpr = state.unexpressible_symbols(convexity_db, now=NOW)
    assert ex["of"] == 6 and ex["n"] == 4
    assert set(ex["no_structure"]) == unexpr - {"OLD"} == {"ABST", "VETO"}
    by = {r["symbol"]: r for r in p["rows"]}
    assert by["ABST"]["expressible"] is False and by["ABST"]["structure_note"] == "no_eligible_contract_in_tenor_window"
    assert by["ABST"]["iv_rv"] is None
    assert by["TRAD"]["expressible"] is True
    assert by["DLOW"]["expressible"] is None                  # never read → unknown, not "no structure"
    assert by["UNGR"]["iv_rv"] == 1.0 and by["UNGR"]["iv_rv_source"] == "opra read"
    assert by["PROP"]["iv_rv_source"] == "gate"               # the gate's own number wins where it ran


def test_last_above_floor_conviction(convexity_db):
    r1 = state.record_run(convexity_db, mode="PAPER", equity=None)
    _prop(convexity_db, r1, "OLD", "HIGH", _strat(True), as_of="2026-07-10T19:45:00+00:00")
    r2 = state.record_run(convexity_db, mode="PAPER", equity=None)
    _prop(convexity_db, r2, "NEW", "LOW", _strat(True), as_of="2026-10-26T19:45:00+00:00")
    p = dd.why_no_entry_panel(convexity_db, CFG, now=NOW)
    la = p["tiles"]["last_above_floor"]
    assert (la["symbol"], la["run_id"], la["day"], la["days_ago"]) == ("OLD", r1, "2026-07-10", 109)
    r3 = state.record_run(convexity_db, mode="PAPER", equity=None)
    _prop(convexity_db, r3, "HL", "MODERATE", _strat(True), as_of="2026-10-26T19:45:00+00:00")
    la = dd.why_no_entry_panel(convexity_db, CFG, now=NOW)["tiles"]["last_above_floor"]
    assert (la["symbol"], la["days_ago"]) == ("HL", 1)


def _position(conn, status, exit_reason=None, opened="2026-10-26T19:50:00+00:00"):
    pid = state.record_convexity_position(
        conn, run_id=None, opened_at=opened, theme="t", symbol="HL", direction="bullish", structure_kind="long_call",
        contract_symbol="HL270115C00012000", expiry="2027-01-15", strike=12.0, dte=80, moneyness=0.2,
        contracts=2, entry_premium_per_contract=345.0, total_premium=690.0, status=status, order_id="o-1")
    if exit_reason:
        state.drop_convexity_position(conn, pid, reason=exit_reason)
    return pid


def test_last_order_attempt_unfilled_resting_filled_and_veto_fill(convexity_db):
    pid = _position(convexity_db, "pending", exit_reason="cancelled_unfilled")
    lo = dd.why_no_entry_panel(convexity_db, CFG, now=NOW)["tiles"]["last_order"]
    assert lo["kind"] == "not_filled" and lo["result"] == "not filled — cancelled unfilled"
    assert (lo["symbol"], lo["contracts"], lo["premium"], lo["day"], lo["days_ago"], lo["position_id"]) == (
        "HL", 2, 690.0, "2026-10-26", 1, pid)

    convexity_db.execute("UPDATE convexity_positions SET status='pending', exit_reason=NULL WHERE id=?", (pid,))
    assert dd.why_no_entry_panel(convexity_db, CFG, now=NOW)["tiles"]["last_order"]["kind"] == "resting"
    convexity_db.execute("UPDATE convexity_positions SET status='open' WHERE id=?", (pid,))
    lo = dd.why_no_entry_panel(convexity_db, CFG, now=NOW)["tiles"]["last_order"]
    assert lo["kind"] == "filled" and lo["result"] == "filled"

    # a LATER broker refusal (veto-fill, no position row) is the newest attempt
    state.record_convexity_eval(convexity_db, run_id=None, as_of="2026-10-27T10:00:00+00:00", theme="t",
                                symbol="AMD", direction="bullish", decision="veto-fill", reasons=["rejected: halted"])
    lo = dd.why_no_entry_panel(convexity_db, CFG, now=NOW)["tiles"]["last_order"]
    assert (lo["symbol"], lo["kind"], lo["result"], lo["days_ago"]) == ("AMD", "not_filled", "not filled — rejected: halted", 0)


def test_empty_database_is_explicit(convexity_db):
    p = dd.why_no_entry_panel(convexity_db, CFG, now=NOW)
    assert p["empty"] is True and p["rows"] == [] and p["run_id"] is None
    assert p["tiles"]["expressible"] == {"n": 0, "of": 0, "no_structure": [], "basis": p["tiles"]["expressible"]["basis"]}
    assert p["tiles"]["last_above_floor"] is None and p["tiles"]["last_order"] is None


def _hl_session(conn, *, link_proposal: bool):
    """HL reached the gate; the gate stamped ``submit-pending`` and the order was then cancelled unfilled."""
    rid = state.record_run(conn, mode="PAPER", equity=None)
    pid = _prop(conn, rid, "HL", "MODERATE", _strat(True), status="traded")
    _eval(conn, rid, "HL", "submit-pending", pid, iv_rv=0.9, skew=3.0)
    pos = state.record_convexity_position(
        conn, run_id=rid, opened_at="2026-10-26T19:50:00+00:00", theme="t", symbol="HL", direction="bullish",
        structure_kind="long_call", contract_symbol="HL270617C00017000", expiry="2027-06-17", strike=17.0, dte=234,
        moneyness=0.2, contracts=5, entry_premium_per_contract=176.0, total_premium=880.0, status="pending",
        order_id="o-2", proposal_id=pid if link_proposal else None)
    state.drop_convexity_position(conn, pos, reason="cancelled_unfilled")
    return rid, pid, pos


def test_row_shows_the_orders_real_outcome_not_the_stale_gate_stamp(convexity_db):
    _, pid, pos = _hl_session(convexity_db, link_proposal=True)
    row = dd.why_no_entry_panel(convexity_db, CFG, now=NOW)["rows"][0]
    assert row["gate_decision"] == "submit-pending"               # the point-in-time stamp is still reported ...
    o = row["order"]                                              # ... but the row carries what the order did
    assert (o["kind"], o["result"], o["position_id"], o["contract"], o["contracts"], o["premium"]) == (
        "not_filled", "not filled — cancelled unfilled", pos, "HL270617C00017000", 5, 880.0)


def test_order_join_is_exact_so_an_unlinked_position_shows_unmatched(convexity_db):
    _hl_session(convexity_db, link_proposal=False)                # position carries no proposal_id
    row = dd.why_no_entry_panel(convexity_db, CFG, now=NOW)["rows"][0]
    assert row["order"] is None and row["veto_stage"] == "submit-pending — order unmatched"
    # a position not from THIS run (here: run-less) is not this session's order, and not even "unmatched"
    convexity_db.execute("UPDATE convexity_positions SET run_id = NULL")
    row = dd.why_no_entry_panel(convexity_db, CFG, now=NOW)["rows"][0]
    assert row["order"] is None and row["veto_stage"] == "submit-pending"


def test_two_proposals_same_symbol_one_run_never_borrow_each_others_order(convexity_db):
    rid = state.record_run(convexity_db, mode="PAPER", equity=None)
    p1 = _prop(convexity_db, rid, "HL", "MODERATE", _strat(True), status="traded")
    p2 = _prop(convexity_db, rid, "HL", "HIGH", _strat(True), status="proposed")
    _eval(convexity_db, rid, "HL", "submit-pending", p1, iv_rv=0.9, skew=3.0)
    _eval(convexity_db, rid, "HL", "veto-iv-gate", p2, iv_rv=1.7, skew=6.0)
    pos = state.record_convexity_position(
        convexity_db, run_id=rid, opened_at="2026-10-26T19:50:00+00:00", theme="t", symbol="HL",
        direction="bullish", structure_kind="long_call", contract_symbol="HL270617C00017000",
        expiry="2027-06-17", strike=17.0, dte=234, moneyness=0.2, contracts=5, entry_premium_per_contract=176.0,
        total_premium=880.0, status="pending", order_id="o-3", proposal_id=p1)
    by = {r["proposal_id"]: r for r in dd.why_no_entry_panel(convexity_db, CFG, now=NOW)["rows"]}
    assert by[p1]["order"]["position_id"] == pos and by[p1]["order"]["kind"] == "resting"
    assert by[p2]["order"] is None and by[p2]["veto_stage"] == "veto-iv-gate — order unmatched"
    # the same holds if the order carries no link at all: neither proposal claims it
    convexity_db.execute("UPDATE convexity_positions SET proposal_id = NULL")
    by = {r["proposal_id"]: r for r in dd.why_no_entry_panel(convexity_db, CFG, now=NOW)["rows"]}
    assert by[p1]["order"] is None and by[p2]["order"] is None
    assert by[p1]["veto_stage"].endswith("order unmatched") and by[p2]["veto_stage"].endswith("order unmatched")


def test_order_join_follows_a_later_fill_and_ignores_names_that_never_reached_the_gate(convexity_db):
    rid, pid, pos = _hl_session(convexity_db, link_proposal=True)
    convexity_db.execute("UPDATE convexity_positions SET status='open', exit_reason=NULL WHERE id=?", (pos,))
    assert dd.why_no_entry_panel(convexity_db, CFG, now=NOW)["rows"][0]["order"]["kind"] == "filled"
    _prop(convexity_db, rid, "HL2", "LOW", _strat(False))
    by = {r["symbol"]: r for r in dd.why_no_entry_panel(convexity_db, CFG, now=NOW)["rows"]}
    assert by["HL2"]["order"] is None


def test_panel_ages_gate_reads_on_the_et_date():
    """Both ``now`` and the row are put on the ET calendar *inside the panel*. (``state.unexpressible_symbols``
    still uses the UTC date — the divergence is documented, not changed, here.)"""
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE gate_dualread (id INTEGER PRIMARY KEY, symbol TEXT, feed TEXT, structured INTEGER, "
                 "iv_rv REAL, otm_skew REAL, cheap INTEGER, note TEXT, run_id INTEGER, evaluated_at TEXT)")
    # Mon 10-19 22:00 ET stored as 10-20 02:00Z → ET date 10-19
    conn.execute("INSERT INTO gate_dualread (symbol, feed, structured, evaluated_at) VALUES "
                 "('AAA','opra',1,'2026-10-20T02:00:00+00:00')")
    # 20:00-24:00 ET window: UTC is already Tue 10-27, ET is still Mon 10-26 → ET age 5 (fresh)
    late = datetime(2026, 10, 27, 1, 0, tzinfo=UTC)
    conn.execute("UPDATE gate_dualread SET evaluated_at='2026-10-19T22:00:00+00:00'")
    assert set(dd._gate_of_record_reads(conn, late)) == {"AAA"}
    # the next ET day the same read is 6 weekdays old → stale; and a UTC-dated row is NOT read as its UTC day
    midday = datetime(2026, 10, 27, 16, 0, tzinfo=UTC)
    assert dd._gate_of_record_reads(conn, midday) == {}
    conn.execute("UPDATE gate_dualread SET evaluated_at='2026-10-20T02:00:00+00:00'")   # UTC 10-20 = ET 10-19
    assert dd._gate_of_record_reads(conn, midday) == {}
