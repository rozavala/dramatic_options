"""Council parse-health read + run-health stamp + migration 0011 computed backfill (offline)."""

import importlib.util
from pathlib import Path

import state

_M0011 = Path(__file__).resolve().parent.parent / "scripts" / "migrations" / "0011_council_health.py"


def _apply_0011(conn):
    spec = importlib.util.spec_from_file_location(_M0011.stem, _M0011)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.apply(conn)


def _proposer_output(conn, run_id, symbol, raw, *, conviction="NEUTRAL"):
    pid = state.record_council_proposal(
        conn, run_id=run_id, as_of="t", theme="x", symbol=symbol, direction="bullish",
        conviction=conviction, status="dropped" if conviction == "NEUTRAL" else "proposed",
    )
    state.record_agent_output(
        conn, proposal_id=pid, role="proposer", provider="gemini", model="gemini-3.5-flash",
        confidence=conviction, stance="bullish", weakest_point=None, raw=raw, cost_usd=0.001,
    )
    return pid


def test_council_parse_health_counts_called_and_excludes_ungrounded(convexity_db):
    conn = convexity_db
    run_id = state.record_run(conn, mode="PAPER", equity=10000)
    _proposer_output(conn, run_id, "A", {"confidence": "NEUTRAL", "parse_error": True, "finish_reason": "MAX_TOKENS"})
    _proposer_output(conn, run_id, "B", {"confidence": "HIGH", "inflection_thesis": "real"}, conviction="HIGH")
    # Ungrounded early-exit: a proposal with NO proposer agent_output → must NOT count as "called".
    state.record_council_proposal(conn, run_id=run_id, as_of="t", theme="x", symbol="C",
                                  direction="bullish", conviction="NEUTRAL", status="dropped")

    h = state.council_parse_health(conn, run_id)
    assert h["called"] == 2 and h["parse_failed"] == 1 and h["rate"] == 0.5


def test_update_run_council_health_stamps_health_and_model_mix(convexity_db):
    conn = convexity_db
    run_id = state.record_run(conn, mode="PAPER", equity=10000)
    state.update_run_council_health(conn, run_id, council_health="parse_fail",
                                    model_mix='{"proposer": "gemini/gemini-3.5-flash"}')
    row = conn.execute("SELECT council_health, model_mix FROM runs WHERE id=?", (run_id,)).fetchone()
    assert row["council_health"] == "parse_fail" and "gemini" in row["model_mix"]


def test_migration_0011_backfills_only_majority_parse_error_runs(convexity_db):
    conn = convexity_db
    bad = state.record_run(conn, mode="PAPER", equity=10000)   # 2/3 proposer parse_error
    _proposer_output(conn, bad, "A", {"parse_error": True})
    _proposer_output(conn, bad, "B", {"parse_error": True})
    _proposer_output(conn, bad, "C", {"confidence": "HIGH", "inflection_thesis": "real"}, conviction="HIGH")
    good = state.record_run(conn, mode="PAPER", equity=10000)  # 0 parse_error
    _proposer_output(conn, good, "D", {"confidence": "HIGH", "inflection_thesis": "real"}, conviction="HIGH")

    _apply_0011(conn)  # idempotent column-adds + the computed backfill UPDATE
    health = {r["id"]: r["council_health"] for r in conn.execute("SELECT id, council_health FROM runs")}
    assert health[bad] == "parse_fail" and health[good] is None
