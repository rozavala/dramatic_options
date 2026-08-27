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
                                "strategist_abstained": 0, "strategist_criteria_vetoed": 0,
                                "any_role_parse_error": False}
    assert rep["cost_usd"] > 0 and rep["cost_by_role"]["strategist"] > 0 and rep["council_health"] == "ok"


def test_l1_health_floor_is_config_driven(convexity_db, monkeypatch):
    # The grade's conviction floor must track config.council.conviction_floor (NOT a hardcoded MODERATE), so a
    # future mandate retighten can't silently desync the L1 grade from the gate/dashboard funnel (#37 class).
    import config_loader
    rid = state.record_run(convexity_db, mode="PAPER", equity=10000)
    state.update_run_council_health(convexity_db, rid, council_health="ok")
    _roundtrip(convexity_db, rid, "SMCI", "bearish", adv_stance="bullish", strat_conv="MODERATE")

    monkeypatch.setattr(config_loader, "load_config", lambda: {"council": {"conviction_floor": "MODERATE"}})
    assert council_l1_health(convexity_db, run_id=rid)["proposer"]["above_floor_proposals"] == 1
    # retighten the floor to HIGH → the same MODERATE proposal falls below it, with NO caller change
    monkeypatch.setattr(config_loader, "load_config", lambda: {"council": {"conviction_floor": "HIGH"}})
    assert council_l1_health(convexity_db, run_id=rid)["proposer"]["above_floor_proposals"] == 0
    # an explicit floor arg still wins over config
    assert council_l1_health(convexity_db, run_id=rid, floor="LOW")["proposer"]["above_floor_proposals"] == 1


def test_l1_health_page_rate_is_config_driven(convexity_db, monkeypatch):
    # The PARSE_FAIL threshold must track config.council.parse_fail_page_rate (NOT a hardcoded 0.5) so the
    # grader's verdict can never silently diverge from the orchestrator's live parse-fail page (the SAME key).
    import config_loader
    rid = state.record_run(convexity_db, mode="PAPER", equity=10000)
    state.update_run_council_health(convexity_db, rid, council_health="ok")  # NOT stamped parse_fail
    _proposer_output(convexity_db, rid, "A", {"parse_error": True, "finish_reason": "MAX_TOKENS"})  # fails
    _proposer_output(convexity_db, rid, "B", {"confidence": "NEUTRAL"})                              # parses
    # rate = 1/2 = 0.5. page_rate 0.4 → 0.5 >= 0.4 → PARSE_FAIL
    monkeypatch.setattr(config_loader, "load_config", lambda: {"council": {"parse_fail_page_rate": 0.4}})
    assert council_l1_health(convexity_db, run_id=rid)["verdict"] == "PARSE_FAIL"
    # loosen the threshold to 0.6 → 0.5 < 0.6 → NOT parse_fail (proposer-clean, no round-trip), NO caller change
    monkeypatch.setattr(config_loader, "load_config", lambda: {"council": {"parse_fail_page_rate": 0.6}})
    assert council_l1_health(convexity_db, run_id=rid)["verdict"] == "PROPOSER_CLEAN_NO_ROUNDTRIP"
    # an explicit page_rate arg still wins over config
    assert council_l1_health(convexity_db, run_id=rid, page_rate=0.9)["verdict"] == "PROPOSER_CLEAN_NO_ROUNDTRIP"


def test_l1_health_confirmed_with_criteria_veto_surfaced(convexity_db):
    # A §10.7 criteria-veto is a DELIBERATED outcome (valid conviction, no parse_error): the
    # round-trip stays CONFIRMED and the veto is SURFACED (anomalous-but-non-degrading — the
    # §10.8 expected shape is ~0; repeated include∧tri-false = prompt-compliance drift to watch).
    rid = state.record_run(convexity_db, mode="PAPER", equity=10000)
    state.update_run_council_health(convexity_db, rid, council_health="ok")
    pid = state.record_council_proposal(convexity_db, run_id=rid, as_of="t", theme="x", symbol="VRT",
                                        direction="bullish", conviction="MODERATE", status="dropped")
    state.record_agent_output(convexity_db, proposal_id=pid, role="proposer", provider="gemini", model="m",
                              confidence="MODERATE", stance="bullish",
                              raw={"confidence": "MODERATE", "inflection_thesis": "real"}, cost_usd=0.003)
    state.record_agent_output(convexity_db, proposal_id=pid, role="adversary", provider="xai", model="m",
                              confidence="MODERATE", stance="bearish",
                              raw={"confidence": "MODERATE", "counter_case": "c"}, cost_usd=0.003)
    state.record_agent_output(convexity_db, proposal_id=pid, role="strategist", provider="anthropic", model="m",
                              confidence="MODERATE", stance="bullish",
                              raw={"conviction": "MODERATE", "summary": "s", "include": False,
                                   "under_narrated": False, "at_inflection": True,
                                   "criteria_veto": True}, cost_usd=0.003)
    rep = council_l1_health(convexity_db, run_id=rid)
    assert rep["verdict"] == "ROUNDTRIP_CONFIRMED"
    assert rep["roundtrip"]["strategist_valid_conviction"] == 1
    assert rep["roundtrip"]["strategist_criteria_vetoed"] == 1
    assert rep["roundtrip"]["any_role_parse_error"] is False


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


def _provider_drop(conn, run_id, symbol):
    """The 2026-08-26 incident row shape: a dropped proposal whose rationale carries
    ``error: provider_error:...`` and NO agent outputs for the failed role."""
    return state.record_council_proposal(
        conn, run_id=run_id, as_of="t", theme="x", symbol=symbol, direction="bullish",
        conviction="NEUTRAL", status="dropped",
        rationale={"error": "provider_error: strategist (anthropic/x) failed after 3 attempts: 400"},
    )


def test_l1_health_provider_degraded_on_majority_drops(convexity_db):
    # The #37 class in its third costume: an exhausted provider quota drops candidates with no
    # parse_error flag — must grade PROVIDER_DEGRADED (censor-class), never a benign quiet night.
    rid = state.record_run(convexity_db, mode="PAPER", equity=10000)
    state.update_run_council_health(convexity_db, rid, council_health="ok")
    _proposer_output(convexity_db, rid, "A", {"confidence": "NEUTRAL"})
    _provider_drop(convexity_db, rid, "B")
    _provider_drop(convexity_db, rid, "C")
    out = council_l1_health(convexity_db, run_id=rid)
    assert out["verdict"] == "PROVIDER_DEGRADED"
    assert out["provider"] == {"drops": 2, "proposals": 3, "rate": round(2 / 3, 4)}


def test_l1_health_single_provider_drop_is_note_only(convexity_db):
    # A 1-off per-candidate blip (fail-soft by design) must NOT fail the night — count surfaced only.
    rid = state.record_run(convexity_db, mode="PAPER", equity=10000)
    state.update_run_council_health(convexity_db, rid, council_health="ok")
    _proposer_output(convexity_db, rid, "A", {"confidence": "NEUTRAL"})
    _proposer_output(convexity_db, rid, "B", {"confidence": "NEUTRAL"})
    _proposer_output(convexity_db, rid, "C", {"confidence": "NEUTRAL"})
    _provider_drop(convexity_db, rid, "D")
    out = council_l1_health(convexity_db, run_id=rid)
    assert out["verdict"] == "PROPOSER_CLEAN_NO_ROUNDTRIP"
    assert out["provider"]["drops"] == 1


def test_l1_health_honors_provider_fail_stamp(convexity_db):
    rid = state.record_run(convexity_db, mode="PAPER", equity=10000)
    state.update_run_council_health(convexity_db, rid, council_health="provider_fail")
    _proposer_output(convexity_db, rid, "A", {"confidence": "NEUTRAL"})
    assert council_l1_health(convexity_db, run_id=rid)["verdict"] == "PROVIDER_DEGRADED"


def test_migration_0019_backfills_only_majority_provider_drop_runs(convexity_db):
    import importlib.util
    from pathlib import Path
    conn = convexity_db
    # run A: 2/3 provider drops + 'ok' -> flips to provider_fail
    ra = state.record_run(conn, mode="PAPER", equity=1)
    state.update_run_council_health(conn, ra, council_health="ok")
    _proposer_output(conn, ra, "A", {"confidence": "NEUTRAL"})
    _provider_drop(conn, ra, "B")
    _provider_drop(conn, ra, "C")
    # run B: 1/3 drops -> stays ok
    rb = state.record_run(conn, mode="PAPER", equity=1)
    state.update_run_council_health(conn, rb, council_health="ok")
    _proposer_output(conn, rb, "A", {"confidence": "NEUTRAL"})
    _proposer_output(conn, rb, "B", {"confidence": "NEUTRAL"})
    _provider_drop(conn, rb, "C")
    # run C: majority drops but already parse_fail -> untouched (never overwrite a FAIL stamp)
    rc = state.record_run(conn, mode="PAPER", equity=1)
    state.update_run_council_health(conn, rc, council_health="parse_fail")
    _provider_drop(conn, rc, "A")
    _provider_drop(conn, rc, "B")
    p = Path(__file__).resolve().parents[1] / "scripts" / "migrations" / "0019_provider_fail_backfill.py"
    spec = importlib.util.spec_from_file_location(p.stem, p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.apply(conn)
    got = {r["id"]: r["council_health"] for r in conn.execute(
        "SELECT id, council_health FROM runs WHERE id IN (?,?,?)", (ra, rb, rc))}
    assert got == {ra: "provider_fail", rb: "ok", rc: "parse_fail"}


def test_provider_month_spend_and_run_spend(convexity_db):
    from datetime import UTC, datetime
    conn = convexity_db
    rid = state.record_run(conn, mode="PAPER", equity=1)
    pid = _proposer_output(conn, rid, "A", {"confidence": "NEUTRAL"})
    state.record_agent_output(conn, proposal_id=pid, role="strategist", provider="anthropic",
                              model="m", confidence="NEUTRAL", stance="bullish",
                              raw={"conviction": "NEUTRAL"}, cost_usd=2.5)
    # an out-of-month row must not count
    pid2 = _proposer_output(conn, rid, "B", {"confidence": "NEUTRAL"})
    state.record_agent_output(conn, proposal_id=pid2, role="strategist", provider="anthropic",
                              model="m", confidence="NEUTRAL", stance="bullish",
                              raw={"conviction": "NEUTRAL"}, cost_usd=9.9)
    conn.execute("UPDATE council_agent_outputs SET created_at='2026-05-05 12:00:00' "
                 "WHERE cost_usd=9.9")
    now = datetime(2026, 8, 27, tzinfo=UTC)
    assert state.provider_month_spend(conn, "anthropic", now=now) == 2.5
    assert state.provider_run_spend(conn, rid, "anthropic") == 12.4  # run-scope ignores month


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


# ── marker-age telemetry (finding #1 / §7.1, migration 0016) ───────────────────────────────────

_M0016 = Path(__file__).resolve().parent.parent / "scripts" / "migrations" / "0016_marker_asof.py"


def test_migration_0016_is_idempotent(convexity_db):
    """The guarded ADD COLUMN re-applies cleanly (conftest already applied it once)."""
    spec = importlib.util.spec_from_file_location(_M0016.stem, _M0016)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.apply(convexity_db)   # second apply → no error
    cols = {r["name"] for r in convexity_db.execute("PRAGMA table_info(council_proposals)").fetchall()}
    assert "markers_asof" in cols


def test_marker_asof_stamped_and_grader_surfaces_staleness(convexity_db):
    """A sentinel proposal stamps markers_asof; the grader surfaces marker-age (= as_of − markers_asof);
    a hand-seed (markers_asof NULL) is excluded — the §7.1 staleness condition is now auditable."""
    conn = convexity_db
    run_id = state.record_run(conn, mode="PAPER", equity=10000)
    # judged 2026-06-25 on markers last refreshed 2026-06-03 → ~22.7d stale (the live VRT case)
    state.record_council_proposal(conn, run_id=run_id, as_of="2026-06-25T19:47:00+00:00", theme="x",
                                  symbol="VRT", direction="bullish", conviction="NEUTRAL",
                                  status="dropped", sentinel_id=1, markers_asof="2026-06-03T02:03:00+00:00")
    # hand-seed: no markers → must NOT enter the staleness summary
    state.record_council_proposal(conn, run_id=run_id, as_of="2026-06-25T19:47:00+00:00", theme="x",
                                  symbol="NVDA", direction="bullish", conviction="NEUTRAL", status="dropped")
    ms = council_l1_health(conn, run_id=run_id)["marker_staleness"]
    assert ms["n_with_markers"] == 1                       # hand-seed excluded
    assert ms["max_age_symbol"] == "VRT"
    assert 22 < ms["max_age_days"] < 23                    # 2026-06-03 → 2026-06-25 ≈ 22.7d
