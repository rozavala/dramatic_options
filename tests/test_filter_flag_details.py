"""#402 — the authenticity filter's flagged claims are persisted beside the count, not just the count.

Record-only: the same scan, the same dampening, the same prompts; ``council_agent_outputs.flagged_details`` now says
WHICH claims were flagged, so a grader can tell a fabricated figure from a filter artefact (L1 #1884)."""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime

import state
from council.context import synthetic_context_pack
from council.debate import run_candidate
from council.filters import authenticity_scan
from council.proposal import AgentOutput, CouncilProposal
from council.router import FakeRouter
from council.wiring import council_to_themes
from themes import Theme

BULL = Theme("copper_electrification", "FCX", "bullish", "unloved industrial tailwind")


def _responder(role, system, user):
    if role == "proposer":
        return json.dumps({"theme": "t", "symbol": "FCX", "direction": "bullish", "structural_vs_fad": "structural",
                           "inflection_thesis": "real", "confidence": "HIGH", "cited": []})
    if role == "adversary":   # one invented figure + one invented quote
        return json.dumps({"counter_case": 'margins fell to 77.7% and the CEO said "we are finished here"',
                           "weakest_point": "w", "is_fad": False, "already_consensus": False,
                           "inflection_passed": False, "confidence": "MODERATE", "cited": []})
    return json.dumps({"include": False, "conviction": "LOW", "summary": "s", "weakest_point": "w",
                       "structural_vs_fad": "structural", "under_narrated": True, "at_inflection": True})


def test_the_debate_carries_each_roles_flagged_claims_one_per_count():
    prop = run_candidate(BULL, synthetic_context_pack(BULL), FakeRouter(responder=_responder), rng=random.Random(0))
    by_role = {a.role: a for a in prop.agent_outputs}
    adv = by_role["adversary"]
    assert adv.flagged_unsupported == 2 and adv.confidence == "LOW"          # dampened exactly as before
    assert adv.flagged_details == ('unsupported quote: "we are finished here"', "unsupported figure: 77.7")
    assert len(adv.flagged_details) == adv.flagged_unsupported
    for role in ("proposer", "strategist"):
        assert len(by_role[role].flagged_details) == by_role[role].flagged_unsupported


class _Clock:
    def now(self):
        return datetime(2026, 7, 1, 19, 47, tzinfo=UTC)


def test_the_flagged_claims_round_trip_to_the_stored_row(monkeypatch, convexity_db):
    res = authenticity_scan(["capex rose 41.5% in 2026"], "capex rose in the period")
    assert res.flagged == 2
    ao = [AgentOutput("adversary", "fake", "m", "LOW", "bearish", "w", {"k": 1},
                      flagged_unsupported=res.flagged, flagged_details=tuple(res.details)),
          AgentOutput("proposer", "fake", "m", "HIGH", "bullish", None, {"k": 2})]

    def _fake_propose(candidates, **kw):
        return [CouncilProposal(theme=c.name, symbol=c.symbol, direction=c.direction, conviction="NEUTRAL",
                                structural_vs_fad=None, weakest_point=None, strategist_summary=None, rationale={},
                                agent_outputs=ao, cost_usd=0.0, model_mix={}, include=False)
                for c in candidates]

    monkeypatch.setattr("council.wiring.propose", _fake_propose)
    council_to_themes(convexity_db, candidates=[BULL], router=FakeRouter(), config={"council": {}}, clock=_Clock())
    rows = {r["role"]: r for r in convexity_db.execute(
        "SELECT role, flagged_unsupported, flagged_details, raw FROM council_agent_outputs")}
    assert json.loads(rows["adversary"]["flagged_details"]) == ["unsupported figure: 41.5", "unsupported figure: 2026"]
    assert rows["adversary"]["flagged_unsupported"] == 2
    assert json.loads(rows["proposer"]["flagged_details"]) == []              # explicit "none", not NULL
    assert json.loads(rows["adversary"]["raw"]) == {"k": 1}                   # the agent's raw is untouched


def test_migration_0020_is_idempotent_and_leaves_old_rows_null(convexity_db):
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "scripts" / "migrations" / "0020_agent_flag_details.py"
    spec = importlib.util.spec_from_file_location("m0020", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.apply(convexity_db)                                                    # already applied by the fixture
    cols = [r["name"] for r in convexity_db.execute("PRAGMA table_info(council_agent_outputs)")]
    assert cols.count("flagged_details") == 1
    pid = state.record_council_proposal(
        convexity_db, run_id=None, as_of="2026-07-01", theme="t", symbol="FCX", direction="bullish",
        conviction="LOW", structural_vs_fad=None, weakest_point=None, rationale={}, strategist_summary=None,
        cost_usd=0.0, model_mix={}, status="dropped")
    convexity_db.execute("INSERT INTO council_agent_outputs (proposal_id, role, raw, flagged_unsupported, created_at) "
                         "VALUES (?, 'proposer', '{}', 1, datetime('now'))", (pid,))   # a pre-0020-shaped write
    assert convexity_db.execute("SELECT flagged_details FROM council_agent_outputs").fetchone()[0] is None


def test_migration_0020_fails_loudly_without_the_table():
    import importlib.util
    import sqlite3
    from pathlib import Path

    import pytest

    path = Path(__file__).resolve().parents[1] / "scripts" / "migrations" / "0020_agent_flag_details.py"
    spec = importlib.util.spec_from_file_location("m0020b", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    with pytest.raises(sqlite3.OperationalError):        # never a silent no-op recorded as applied
        mod.apply(conn)
