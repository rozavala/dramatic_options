"""#463 known gap: the dashboard's real-book positions show both legs of a vertical (display only)."""

import dashboard_data as dd
import state


def _pos(conn, sym, *, strike, epc, short=None, short_strike=None):
    return state.record_convexity_position(
        conn, run_id=None, opened_at="2026-11-04T15:00:00+00:00", theme=f"t-{sym}", symbol=sym, direction="bullish",
        structure_kind="long_call", contract_symbol=f"{sym}270617C{int(strike * 1000):08d}", expiry="2027-06-17",
        strike=strike, dte=226, moneyness=0.25, contracts=1, entry_premium_per_contract=epc, total_premium=epc,
        rationale={}, status="open", short_contract_symbol=short, short_strike=short_strike)


def test_a_vertical_row_carries_both_legs_and_the_net_debit(convexity_db):
    _pos(convexity_db, "GEV", strike=750.0, epc=1840.0, short="GEV270617C01050000", short_strike=1050.0)
    row = dd.positions_panel(convexity_db)["real_open"][0]
    assert row["vertical"] is True
    assert row["contract_symbol"] == "GEV270617C00750000" and row["strike"] == 750.0
    assert row["short_contract_symbol"] == "GEV270617C01050000" and row["short_strike"] == 1050.0
    assert row["net_debit"] == 18.40
    assert "entry_per_contract" not in row


def test_a_single_leg_row_is_unchanged(convexity_db):
    _pos(convexity_db, "FLNC", strike=5.0, epc=100.0)
    row = dd.positions_panel(convexity_db)["real_open"][0]
    assert row["vertical"] is False
    assert row["short_contract_symbol"] is None and row["short_strike"] is None and row["net_debit"] is None
    assert row["contract_symbol"] == "FLNC270617C00005000" and row["total_premium"] == 100.0
