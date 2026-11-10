"""#467 step 3: the net-of-slippage twin of each booked real-book entry (display only, an estimate)."""

import dashboard_data as dd
import state
from execution_ledger import haircut

Q = {"bid": 1.40, "ask": 1.60, "mid": 1.50, "spread_pct": 13.3}


def _pos(conn, sym, *, px, status="open", contracts=5, rationale=None, short=None, exit_reason=None):
    pid = state.record_convexity_position(
        conn, run_id=None, opened_at="2026-11-04T15:00:00+00:00", theme=f"t-{sym}", symbol=sym, direction="bullish",
        structure_kind="long_call", contract_symbol=f"{sym}270617C00020000", expiry="2027-06-17", strike=20.0,
        dte=226, moneyness=0.25, contracts=contracts, entry_premium_per_contract=px * 100,
        total_premium=px * 100 * contracts, rationale=rationale if rationale is not None else {}, status=status,
        short_contract_symbol=short, short_strike=(35.0 if short else None))
    if exit_reason is not None:
        state.drop_convexity_position(conn, pid, reason=exit_reason)
    return pid


def _rows(conn):
    return {r["symbol"]: r for r in haircut(conn)["rows"]}


def test_ask_at_entry_reprices_premium_and_the_marked_pnl(convexity_db):
    c = convexity_db
    pid = _pos(c, "FLNC", px=1.50, rationale={"quote": Q})
    state.mark_convexity_position(c, pid, mark=1.80, as_of="2026-11-09T15:00:00+00:00")
    r = _rows(c)["FLNC"]
    assert r["fill_px"] == 1.50 and r["conservative_px"] == 1.60 and r["basis"] == "ask_at_entry"
    assert r["premium_filled_usd"] == 750.0 and r["premium_conservative_usd"] == 800.0 and r["haircut_usd"] == 50.0
    assert r["pnl_kind"] == "marked" and r["pnl_filled_usd"] == 150.0 and r["pnl_conservative_usd"] == 100.0


def test_closed_entry_has_a_realized_twin(convexity_db):
    c = convexity_db
    pid = _pos(c, "TITN", px=2.60, contracts=3, rationale={"quote": {"bid": 2.40, "ask": 2.90, "mid": 2.65}})
    state.close_convexity_position(c, pid, exit_price=2.0, realized_pnl=-180.0, reason="time_stop",
                                   as_of="2026-11-09T15:00:00+00:00")
    r = _rows(c)["TITN"]
    assert r["pnl_kind"] == "realized" and r["haircut_usd"] == 90.0
    assert r["pnl_filled_usd"] == -180.0 and r["pnl_conservative_usd"] == -270.0


def test_unknown_when_no_quote_was_stored_never_the_fill(convexity_db):
    c = convexity_db
    pid = _pos(c, "OLD", px=1.00, rationale={"thesis": "pre-2026-10-27 entry: no quote recorded"})
    state.mark_convexity_position(c, pid, mark=1.20, as_of="2026-11-09T15:00:00+00:00")
    r = _rows(c)["OLD"]
    assert r["conservative_px"] is None and r["basis"] is None
    assert r["premium_conservative_usd"] is None and r["haircut_usd"] is None
    assert r["pnl_filled_usd"] == 100.0 and r["pnl_conservative_usd"] is None
    t = haircut(c)["totals"]
    assert t["entries"] == 1 and t["unknown"] == 1 and t["known"] == 0 and t["haircut_pct"] is None


def test_carry_worst_rung_when_no_quote_but_only_above_the_fill(convexity_db):
    c = convexity_db
    l1 = _pos(c, "NTSK", px=1.50, status="pending", exit_reason="carry_filled")
    _pos(c, "NTSK", px=1.50, status="pending", exit_reason="carry_lapsed", rationale={"carry": {"of": l1, "step": 0, "limit": 1.50}})
    # filled at 1.55 against a 1.58 limit: the walk's worst rung is above the fill
    _pos(c, "NTSK", px=1.55, rationale={"carry": {"of": l1, "step": 1, "limit": 1.58}})
    l1b = _pos(c, "SMR", px=1.00, status="pending", exit_reason="carry_filled")
    _pos(c, "SMR", px=1.00, rationale={"carry": {"of": l1b, "step": 0, "limit": 1.00}})   # top rung == fill
    rows = _rows(c)
    assert rows["NTSK"]["conservative_px"] == 1.58 and rows["NTSK"]["basis"] == "carry_worst_rung"
    assert rows["SMR"]["conservative_px"] is None, "a rung equal to the fill is no estimate: unknown"
    assert len(haircut(c)["rows"]) == 2   # cancelled carry intents and lapsed attempts are not entries


def test_vertical_uses_the_natural_debit(convexity_db):
    c = convexity_db
    rat = {"quote": {"bid": 2.60, "ask": 3.00, "mid": 2.80},
           "vertical": {"short": "VRT270617C00035000", "short_quote": {"bid": 1.10, "ask": 1.30, "mid": 1.20}}}
    _pos(c, "VRT", px=1.60, contracts=1, rationale=rat, short="VRT270617C00035000")
    r = _rows(c)["VRT"]
    assert r["conservative_px"] == 1.90 and r["haircut_usd"] == 30.0   # long ask 3.00 − short bid 1.10
    assert r["short_contract"] == "VRT270617C00035000"


def test_vertical_without_a_short_quote_is_unknown(convexity_db):
    c = convexity_db
    _pos(c, "GEV", px=1.60, contracts=1, rationale={"quote": Q}, short="GEV270617C00035000")
    assert _rows(c)["GEV"]["conservative_px"] is None   # the long ask alone is not the net debit's ask


def test_ask_below_fill_is_unknown_not_a_zero_haircut(convexity_db):
    # #467 review: the ask moved between the quote and the fill, so the ask at fill time is unknown.
    c = convexity_db
    _pos(c, "CCJ", px=1.70, rationale={"quote": Q})
    r = _rows(c)["CCJ"]
    assert r["conservative_px"] is None and r["basis"] == "ask_below_fill" and r["haircut_usd"] is None
    assert haircut(c)["totals"]["unknown"] == 1 and haircut(c)["totals"]["known"] == 0


def test_ask_below_fill_falls_through_to_the_carry_rung(convexity_db):
    c = convexity_db
    l1 = _pos(c, "BWXT", px=1.50, status="pending", exit_reason="carry_filled")
    _pos(c, "BWXT", px=1.70, rationale={"quote": Q, "carry": {"of": l1, "step": 3, "limit": 1.75}})
    r = _rows(c)["BWXT"]
    assert r["conservative_px"] == 1.75 and r["basis"] == "carry_worst_rung"


def test_partial_close_counts_the_original_quantity(convexity_db):
    # #467 review: 10 bought at 1.50 (ask 1.60), 6 sold at 2.00 → the entry haircut is on all 10, not the 4 left.
    c = convexity_db
    pid = _pos(c, "PL", px=1.50, contracts=10, rationale={"quote": Q})
    state.record_partial_close(c, pid, sold_qty=6, exit_price=2.00, reason="time_stop",
                               as_of="2026-11-09T15:00:00+00:00")
    state.mark_convexity_position(c, pid, mark=1.80, as_of="2026-11-09T16:00:00+00:00")
    r = _rows(c)["PL"]
    assert r["partial"] is True and r["sold_qty"] == 6 and r["contracts_remaining"] == 4 and r["contracts"] == 10
    assert r["premium_filled_usd"] == 1500.0 and r["premium_conservative_usd"] == 1600.0 and r["haircut_usd"] == 100.0
    # realized on the sold 6 ((200 − 150) × 6 = 300) + marked on the remaining 4 ((180 − 150) × 4 = 120)
    assert r["pnl_kind"] == "realized+marked" and r["pnl_filled_usd"] == 420.0 and r["pnl_conservative_usd"] == 320.0


def test_a_final_close_after_a_partial_is_not_double_counted(convexity_db):
    c = convexity_db
    pid = _pos(c, "PL", px=1.50, contracts=10, rationale={"quote": Q})
    state.record_partial_close(c, pid, sold_qty=6, exit_price=2.00, reason="time_stop",
                               as_of="2026-11-09T15:00:00+00:00")
    # what monitor._close_and_resolve does: the whole bet restored on the row, every part's P&L added
    state.close_convexity_position(c, pid, exit_price=1.92, realized_pnl=420.0, reason="time_stop",
                                   as_of="2026-11-10T15:00:00+00:00", contracts=10, total_premium=1500.0)
    r = _rows(c)["PL"]
    assert r["contracts"] == 10 and r["partial"] is True and r["premium_filled_usd"] == 1500.0
    assert r["haircut_usd"] == 100.0 and r["pnl_filled_usd"] == 420.0 and r["pnl_conservative_usd"] == 320.0


def test_totals_cover_priced_rows_only(convexity_db):
    c = convexity_db
    a = _pos(c, "A1", px=1.50, rationale={"quote": Q})
    state.mark_convexity_position(c, a, mark=1.50, as_of="2026-11-09T15:00:00+00:00")
    _pos(c, "A2", px=1.00)
    t = haircut(c)["totals"]
    assert t["entries"] == 2 and t["known"] == 1 and t["unknown"] == 1
    assert t["premium_filled_usd"] == 1250.0 and t["premium_filled_known_usd"] == 750.0
    assert t["premium_conservative_usd"] == 800.0 and t["haircut_usd"] == 50.0 and t["haircut_pct"] == 0.0667
    assert t["pnl_n"] == 1 and t["pnl_filled_usd"] == 0.0 and t["pnl_conservative_usd"] == -50.0


def test_panel_is_labelled_an_estimate_and_writes_nothing(convexity_db):
    c = convexity_db
    _pos(c, "FLNC", px=1.50, rationale={"quote": Q})
    before = c.execute("SELECT entry_premium_per_contract, total_premium FROM convexity_positions").fetchall()
    p = dd.slippage_panel(c)
    assert "#467" in p["note"] and "Estimate" in p["note"] and "nothing is re-booked" in p["note"]
    after = c.execute("SELECT entry_premium_per_contract, total_premium FROM convexity_positions").fetchall()
    assert [tuple(r) for r in before] == [tuple(r) for r in after]
    assert dd.slippage_panel(c)["rows"][0]["conservative_px"] == 1.60
