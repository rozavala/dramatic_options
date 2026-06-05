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


# ── council_health_report: the codified L1 verification checklist ──────────────────────────────

from council_health_report import council_l1_health  # noqa: E402


def _roundtrip(conn, run_id, symbol, direction, *, adv_stance, strat_conv="MODERATE", cost=0.003):
    pid = state.record_council_proposal(conn, run_id=run_id, as_of="t", theme="x", symbol=symbol,
                                        direction=direction, conviction=strat_conv, status="proposed")
    state.record_agent_output(conn, proposal_id=pid, role="proposer", provider="gemini", model="m",
                              confidence="MODERATE", stance=direction,
                              raw={"confidence": "MODERATE", "inflection_thesis": "real"}, cost_usd=cost)
    state.record_agent_output(conn, proposal_id=pid, role="adversary", provider="xai", model="m",
                              confidence="MODERATE", stance=adv_stance,
                              raw={"confidence": "MODERATE", "counter_case": "c"}, cost_usd=cost)
    state.record_agent_output(conn, proposal_id=pid, role="strategist", provider="anthropic", model="m",
                              confidence=strat_conv, stance=direction,
                              raw={"conviction": strat_conv, "summary": "s"}, cost_usd=cost)
    return pid


def test_l1_health_roundtrip_confirmed(convexity_db):
    rid = state.record_run(convexity_db, mode="PAPER", equity=10000)
    state.update_run_council_health(convexity_db, rid, council_health="ok")
    _roundtrip(convexity_db, rid, "SMCI", "bearish", adv_stance="bullish")   # adversary = bull case on a bear
    rep = council_l1_health(convexity_db, run_id=rid)
    assert rep["verdict"] == "ROUNDTRIP_CONFIRMED"
    assert rep["roundtrip"] == {"n": 1, "adversary_direction_relative": 1, "strategist_valid_conviction": 1,
                                "strategist_abstained": 0, "any_role_parse_error": False}
    assert rep["cost_usd"] > 0 and rep["cost_by_role"]["strategist"] > 0 and rep["council_health"] == "ok"


def test_l1_health_parse_fail(convexity_db):
    rid = state.record_run(convexity_db, mode="PAPER", equity=10000)
    state.update_run_council_health(convexity_db, rid, council_health="parse_fail")
    _proposer_output(convexity_db, rid, "A", {"parse_error": True})
    _proposer_output(convexity_db, rid, "B", {"parse_error": True})
    assert council_l1_health(convexity_db, run_id=rid)["verdict"] == "PARSE_FAIL"


def test_l1_health_proposer_clean_but_no_roundtrip(convexity_db):
    # The trap: a clean all-NEUTRAL cycle confirms the proposer parses but NOT the adversary/strategist.
    rid = state.record_run(convexity_db, mode="PAPER", equity=10000)
    state.update_run_council_health(convexity_db, rid, council_health="ok")
    _proposer_output(convexity_db, rid, "A", {"confidence": "NEUTRAL"})       # clean NEUTRAL, no adv/strat rows
    assert council_l1_health(convexity_db, run_id=rid)["verdict"] == "PROPOSER_CLEAN_NO_ROUNDTRIP"


def test_l1_health_degraded_when_adversary_not_direction_relative(convexity_db):
    rid = state.record_run(convexity_db, mode="PAPER", equity=10000)
    state.update_run_council_health(convexity_db, rid, council_health="ok")
    _roundtrip(convexity_db, rid, "SMCI", "bearish", adv_stance="bearish")    # SAME as proposal → not dir-relative
    assert council_l1_health(convexity_db, run_id=rid)["verdict"] == "ROUNDTRIP_DEGRADED"


def test_l1_health_confirmed_with_strategist_abstention(convexity_db):
    # A GENUINE strategist NEUTRAL abstention (reasoned exclude, no parse_error) is VALID — the round-trip
    # is still CONFIRMED, with the abstention surfaced. This is the live Friday-L1 #72 case (strategist
    # abstained on SMCI: "the move is mean-reverting; elevated RV → convexity already expensive").
    rid = state.record_run(convexity_db, mode="PAPER", equity=10000)
    state.update_run_council_health(convexity_db, rid, council_health="ok")
    _roundtrip(convexity_db, rid, "SMCI", "bearish", adv_stance="bullish", strat_conv="NEUTRAL")
    rep = council_l1_health(convexity_db, run_id=rid)
    assert rep["verdict"] == "ROUNDTRIP_CONFIRMED"
    assert rep["roundtrip"]["strategist_valid_conviction"] == 1
    assert rep["roundtrip"]["strategist_abstained"] == 1


def test_l1_health_degraded_when_strategist_parse_error(convexity_db):
    # A FAIL-CLOSED strategist NEUTRAL carries parse_error → NOT a valid abstention → still degraded
    # (the bug in a new costume must not pass as healthy selectivity).
    rid = state.record_run(convexity_db, mode="PAPER", equity=10000)
    state.update_run_council_health(convexity_db, rid, council_health="ok")
    pid = state.record_council_proposal(convexity_db, run_id=rid, as_of="t", theme="x", symbol="SMCI",
                                        direction="bearish", conviction="NEUTRAL", status="proposed")
    state.record_agent_output(convexity_db, proposal_id=pid, role="proposer", provider="g", model="m",
                              confidence="MODERATE", stance="bearish",
                              raw={"confidence": "MODERATE", "inflection_thesis": "x"}, cost_usd=0.003)
    state.record_agent_output(convexity_db, proposal_id=pid, role="adversary", provider="x", model="m",
                              confidence="MODERATE", stance="bullish",
                              raw={"confidence": "MODERATE", "counter_case": "c"}, cost_usd=0.003)
    state.record_agent_output(convexity_db, proposal_id=pid, role="strategist", provider="a", model="m",
                              confidence="NEUTRAL", stance="bearish",
                              raw={"parse_error": True, "finish_reason": "MAX_TOKENS"}, cost_usd=0.003)
    rep = council_l1_health(convexity_db, run_id=rid)
    assert rep["verdict"] == "ROUNDTRIP_DEGRADED"
    assert rep["roundtrip"]["any_role_parse_error"] is True
    assert rep["roundtrip"]["strategist_abstained"] == 0   # a parse_error abstention is NOT credited


def test_l1_health_no_council(convexity_db):
    assert council_l1_health(convexity_db)["verdict"] == "NO_COUNCIL"
