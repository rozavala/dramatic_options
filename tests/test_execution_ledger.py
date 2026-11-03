"""D0 execution ledger: approvals followed to the broker (telemetry only)."""

import state
from execution_ledger import build_ledger, panel, summarize


def _approval(conn, sym, as_of, status="proposed"):
    return state.record_council_proposal(conn, run_id=None, as_of=as_of, theme=f"t-{sym}", symbol=sym,
                                         direction="bullish", conviction="MODERATE", status=status)


def _order(conn, pid, sym, as_of, *, status, px=1.50, rationale=None, exit_reason=None, decision="submit-pending"):
    rat = rationale or {"quote": {"bid": 1.40, "ask": 1.60, "mid": 1.50, "spread_pct": 13.3}}
    pos = state.record_convexity_position(
        conn, run_id=None, opened_at=as_of, theme=f"t-{sym}", symbol=sym, direction="bullish",
        structure_kind="long_call", contract_symbol=f"{sym}270617C00020000", expiry="2027-06-17", strike=20.0,
        dte=226, moneyness=0.25, contracts=5, entry_premium_per_contract=px * 100, total_premium=px * 500,
        rationale=rat, status=status, proposal_id=pid)
    if exit_reason is not None:
        state.drop_convexity_position(conn, pos, reason=exit_reason)
    state.record_convexity_eval(conn, run_id=None, as_of=as_of, theme=f"t-{sym}", symbol=sym,
                                direction="bullish", decision=decision, position_id=pos, proposal_id=pid)
    return pos


def test_outcomes_are_classified(convexity_db):
    c = convexity_db
    # AG-style: submitted late, cancelled unfilled, before carry-over existed.
    p1 = _approval(c, "AG", "2026-10-29T19:48:00+00:00")
    _order(c, p1, "AG", "2026-10-29T19:48:00+00:00", status="pending", exit_reason="cancelled_unfilled")
    # Gate veto: never reached an order.
    p2 = _approval(c, "HL", "2026-10-30T19:48:00+00:00", status="dropped")   # dropped ⇒ not an approval
    p3 = _approval(c, "CF", "2026-10-30T19:48:00+00:00")
    state.record_convexity_eval(c, run_id=None, as_of="x", theme="t", symbol="CF", direction="bullish",
                                decision="veto-iv-gate", proposal_id=p3)
    # Carried, filled on the second walk step.
    p4 = _approval(c, "NTSK", "2026-11-02T20:48:00+00:00")
    l1 = _order(c, p4, "NTSK", "2026-11-02T20:48:00+00:00", status="pending", exit_reason="carry_filled")
    _order(c, p4, "NTSK", "2026-11-03T15:00:00+00:00", status="pending", px=1.55, exit_reason="carry_lapsed",
           rationale={"carry": {"of": l1, "step": 0, "limit": 1.50}}, decision="carry-submit-pending")
    _order(c, p4, "NTSK", "2026-11-03T16:00:00+00:00", status="open", px=1.58,
           rationale={"carry": {"of": l1, "step": 1, "limit": 1.58}}, decision="carry-submit-pending")
    # Filled at L1 directly.
    p5 = _approval(c, "BWXT", "2026-11-03T20:48:00+00:00", status="traded")
    _order(c, p5, "BWXT", "2026-11-03T20:48:00+00:00", status="open", decision="open")

    led = {r["symbol"]: r for r in build_ledger(c)}
    assert "HL" not in led and p2
    assert led["AG"]["outcome"] == "unfilled_no_carry" and led["AG"]["under_carry"] is False
    assert led["CF"]["outcome"] == "gate:veto-iv-gate" and led["CF"]["position_id"] is None
    assert led["NTSK"]["outcome"] == "filled_carry"
    assert [a["step"] for a in led["NTSK"]["attempts"]] == [0, 1]
    assert led["NTSK"]["fill_px"] == 1.58 and led["NTSK"]["limit"] == 1.50 and led["NTSK"]["ask"] == 1.60
    assert led["BWXT"]["outcome"] == "filled_l1"

    s = summarize(build_ledger(c))
    assert s["all"]["approvals"] == 4 and s["all"]["reached_order"] == 3 and s["all"]["filled"] == 2
    assert s["under_carry"]["decided"] == 2 and s["under_carry"]["fill_rate"] == 1.0
    assert s["read"].startswith("accruing")


def test_a_working_order_is_not_a_miss(convexity_db):
    c = convexity_db
    p = _approval(c, "SMR", "2026-11-04T20:48:00+00:00")
    _order(c, p, "SMR", "2026-11-04T20:48:00+00:00", status="pending")
    s = summarize(build_ledger(c))
    assert s["under_carry"]["reached_order"] == 1 and s["under_carry"]["decided"] == 0
    assert s["under_carry"]["fill_rate"] is None


def test_read_fires_after_five_decided(convexity_db):
    c = convexity_db
    for i, sym in enumerate(["A1", "A2", "A3", "A4", "A5"]):
        p = _approval(c, sym, f"2026-11-0{i + 4}T20:48:00+00:00")
        _order(c, p, sym, f"2026-11-0{i + 4}T20:48:00+00:00", status="pending",
               exit_reason="carry_lapsed" if i < 2 else "carry_filled")
    s = summarize(build_ledger(c))
    assert s["under_carry"]["decided"] == 5 and s["under_carry"]["filled"] == 3
    assert "consider submitting" in s["read"]
    assert panel(c)["rows"][0]["symbol"] == "A5"   # newest first
