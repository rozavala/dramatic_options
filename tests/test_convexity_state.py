"""Convexity state: tables, position + survivorship-log + MTM/close helpers."""

from dramatic_options import state


def test_mark_close_and_drawdown(convexity_db):
    conn = convexity_db
    pid = state.record_convexity_position(
        conn, run_id=None, opened_at="2026-05-31T00:00:00+00:00", theme="copper", symbol="FCX",
        direction="bullish", structure_kind="C", contract_symbol="FCX261218C00080000",
        expiry="2026-12-18", strike=80.0, dte=270, moneyness=0.25, contracts=10,
        entry_premium_per_contract=300.0, total_premium=3000.0,
    )
    # mark down to $1/ct → marked $1000 vs $3000 entry = $2000 loss; budget $10k → 20% dd.
    state.mark_convexity_position(conn, pid, mark=1.0, as_of="2026-06-01T00:00:00+00:00")
    dd, have = state.convexity_book_drawdown(conn, 10_000.0)
    assert have is True
    assert abs(dd - 0.20) < 1e-9
    # close it
    state.close_convexity_position(conn, pid, exit_price=1.0, realized_pnl=-2000.0,
                                   reason="time_stop_21dte", as_of="2026-06-01T00:00:00+00:00")
    row = conn.execute("SELECT status, realized_pnl, exit_reason, closed_at FROM convexity_positions WHERE id=?", (pid,)).fetchone()
    assert row["status"] == "closed" and row["realized_pnl"] == -2000.0
    assert row["exit_reason"] == "time_stop_21dte" and row["closed_at"]
    # closed positions no longer count toward open book/drawdown
    assert state.count_open_convexity_positions(conn) == 0
    dd2, have2 = state.convexity_book_drawdown(conn, 10_000.0)
    assert have2 is False and dd2 == 0.0


def test_pending_confirm_and_drop(convexity_db):
    conn = convexity_db
    pid = state.record_convexity_position(
        conn, run_id=None, opened_at="2026-06-01T00:00:00+00:00", theme="t", symbol="FCX",
        direction="bullish", structure_kind="C", contract_symbol="FCX261218C00080000",
        expiry="2026-12-18", strike=80.0, dte=270, moneyness=0.25, contracts=2,
        entry_premium_per_contract=300.0, total_premium=600.0, status="pending", order_id="o1",
    )
    assert state.count_open_convexity_positions(conn) == 0  # pending ≠ open
    assert len(state.pending_convexity_positions(conn)) == 1
    state.confirm_convexity_fill(conn, pid, entry_premium_per_contract=310.0,
                                 total_premium=620.0, opened_at="2026-06-01T01:00:00+00:00")
    assert state.count_open_convexity_positions(conn) == 1
    row = conn.execute("SELECT total_premium FROM convexity_positions WHERE id=?", (pid,)).fetchone()
    assert row["total_premium"] == 620.0
    # a different pending one that gets dropped
    pid2 = state.record_convexity_position(
        conn, run_id=None, opened_at="2026-06-01T00:00:00+00:00", theme="t", symbol="ABC",
        direction="bullish", structure_kind="C", contract_symbol="ABC261218C00010000",
        expiry="2026-12-18", strike=10.0, dte=270, moneyness=0.25, contracts=1,
        entry_premium_per_contract=100.0, total_premium=100.0, status="pending", order_id="o2",
    )
    state.drop_convexity_position(conn, pid2, reason="cancelled_unfilled")
    row2 = conn.execute("SELECT status, exit_reason FROM convexity_positions WHERE id=?", (pid2,)).fetchone()
    assert row2["status"] == "cancelled" and row2["exit_reason"] == "cancelled_unfilled"


def test_record_and_aggregate_positions(convexity_db):
    conn = convexity_db
    assert state.count_open_convexity_positions(conn) == 0
    assert state.convexity_book_open_premium(conn) == 0.0

    pid1 = state.record_convexity_position(
        conn, run_id=None, opened_at="2026-05-31T00:00:00+00:00", theme="copper", symbol="FCX",
        direction="bullish", structure_kind="C", contract_symbol="FCX260930C00056000",
        expiry="2026-09-30", strike=56.0, dte=270, moneyness=0.25, contracts=3,
        entry_premium_per_contract=200.0, total_premium=600.0, rationale={"thesis": "copper"},
    )
    pid2 = state.record_convexity_position(
        conn, run_id=None, opened_at="2026-05-31T00:00:00+00:00", theme="x", symbol="ABC",
        direction="bearish", structure_kind="P", contract_symbol="ABC260930P00010000",
        expiry="2026-09-30", strike=10.0, dte=270, moneyness=-0.25, contracts=5,
        entry_premium_per_contract=200.0, total_premium=1000.0, rationale=None,
    )
    assert pid1 >= 1 and pid2 == pid1 + 1
    assert state.count_open_convexity_positions(conn) == 2
    assert state.convexity_book_open_premium(conn) == 1600.0

    rows = state.open_convexity_positions(conn)
    assert [r["symbol"] for r in rows] == ["FCX", "ABC"]
    assert rows[0]["status"] == "open" and rows[0]["mark"] is None


def test_survivorship_log_records_every_eval(convexity_db):
    conn = convexity_db
    pid = state.record_convexity_position(
        conn, run_id=None, opened_at="2026-05-31T00:00:00+00:00", theme="copper", symbol="FCX",
        direction="bullish", structure_kind="C", contract_symbol="FCX260930C00056000",
        expiry="2026-09-30", strike=56.0, dte=270, moneyness=0.25, contracts=3,
        entry_premium_per_contract=200.0, total_premium=600.0, rationale=None,
    )
    state.record_convexity_eval(
        conn, run_id=None, as_of="2026-05-31T00:00:00+00:00", theme="copper", symbol="FCX",
        direction="bullish", eligible=True, gate_cheap=True, iv_rv=1.05, otm_skew=3.0,
        decision="open", position_id=pid, reasons=["cheap"],
    )
    state.record_convexity_eval(
        conn, run_id=None, as_of="2026-05-31T00:00:00+00:00", theme="hype", symbol="NVDA",
        direction="bullish", eligible=True, gate_cheap=False, iv_rv=1.7, otm_skew=17.0,
        decision="veto-iv-gate", reasons=["iv/rv 1.70 > 1.20"],
    )
    rows = conn.execute("SELECT decision, gate_cheap, reasons FROM convexity_eval ORDER BY id").fetchall()
    assert [r["decision"] for r in rows] == ["open", "veto-iv-gate"]
    assert rows[0]["gate_cheap"] == 1 and rows[1]["gate_cheap"] == 0
    assert "iv/rv" in rows[1]["reasons"]  # JSON-encoded list contains the reason text
