"""Gate-cheap RESERVE (PREREG gate_cheap_reserve, FROZEN 2026-07-02) — composition + data
contract + seam guards.

The frozen claims under test: the reserve changes WHO is judged, never HOW (§2 — membership
only); eligibility is the prior-cycle gate-of-record cheap read, fail-closed on staleness (§3);
within-reserve rank is least-recently-judged → lowest iv_rv → symbol (§4); displacement is
observable (§5); provenance rides the rationale JSON + the model_mix stamp (§6); and
``cheap_reserve_slots=0`` (or an absent config) reproduces the old ``[:max_candidates]`` slice
byte-for-byte — the OFF path is the old code path.
"""

from __future__ import annotations

from datetime import UTC, datetime

import state
from council.council import compose_judged_set
from council.router import FakeRouter
from council.wiring import council_to_themes
from themes import Theme

AS_OF = datetime(2026, 7, 2, 19, 45, tzinfo=UTC)


class _Clock:
    def now(self):
        return AS_OF


def _hand(sym="NVDA"):
    return Theme(name=f"hand_{sym}", symbol=sym, direction="bullish", thesis="t")


def _sent(sym, sid, direction="bullish"):
    return Theme(name=f"s_{sym}", symbol=sym, direction=direction, thesis="t",
                 source="sentinel", sentinel_id=sid)


def _union(n_sent=15, hand=("NVDA",)):
    """Hand-seeds first, then sentinels in inflection order (S00 strongest)."""
    cands = [_hand(s) for s in hand]
    cands += [_sent(f"S{i:02d}", sid=i + 1) for i in range(n_sent)]
    return cands


# ── compose_judged_set (pure §2/§4) ─────────────────────────────────────────────────────────────


def test_reserve_off_is_the_old_slice_byte_for_byte():
    cands = _union()
    selected, selection, displaced = compose_judged_set(
        cands, max_candidates=12, reserve_k=0, cheap_eligible={}, last_judged={})
    assert selected == cands[:12]              # identical objects, identical order
    assert all(v == "rank" for v in selection.values())
    assert displaced == []


def test_no_eligible_names_backfills_to_the_old_slice():
    # Fail-closed (§3): an empty cheap read must NOT shrink the judged set — motion backfill.
    cands = _union()
    selected, selection, displaced = compose_judged_set(
        cands, max_candidates=12, reserve_k=3, cheap_eligible={}, last_judged={})
    assert selected == cands[:12]
    assert all(v == "rank" for v in selection.values())
    assert displaced == []


def test_reserve_pulls_truncated_cheap_names_and_displaces_bottom_motion():
    cands = _union()  # 1 hand-seed → 11 sentinel slots; motion top-8 = S00..S07
    cheap = {"S12": 1.05, "S14": 0.90}  # both below the truncation line
    selected, selection, displaced = compose_judged_set(
        cands, max_candidates=12, reserve_k=3, cheap_eligible=cheap, last_judged={})
    syms = [c.symbol for c in selected]
    assert len(selected) == 12
    assert syms[0] == "NVDA"                       # hand-seed protected, first
    assert syms[1:9] == [f"S{i:02d}" for i in range(8)]   # top-(11−3) motion unchanged
    assert "S12" in syms and "S14" in syms         # the starved cheap names are judged
    assert selection[("S12", "bullish")] == "reserve"
    assert selection[("S14", "bullish")] == "reserve"
    # 2 reserve + 1 backfill (S08, next by motion) fill the 3 slots; S09/S10 displaced.
    assert syms.count("S08") == 1
    assert displaced == ["S09", "S10"]


def test_within_reserve_rank_lru_then_ivrv_then_symbol():
    cands = _union()
    cheap = {"S09": 1.10, "S10": 0.80, "S11": 0.80, "S12": 0.95}
    last = {"S09": "2026-06-01T00:00:00", "S10": "2026-06-20T00:00:00"}  # S11/S12 never judged
    selected, selection, _ = compose_judged_set(
        cands, max_candidates=12, reserve_k=3, cheap_eligible=cheap, last_judged=last)
    reserve = [c.symbol for c in selected if selection[(c.symbol, "bullish")] == "reserve"]
    # never-judged first (tie on iv_rv 0.80 vs 0.95 → S11 lowest, then S12), then oldest-judged S09.
    assert reserve == ["S11", "S12", "S09"]


def test_hand_seeds_never_displaced_and_cap_respected():
    cands = _union(hand=("NVDA", "FCX"))  # 2 hand-seeds → 10 sentinel slots
    cheap = {f"S{i:02d}": 1.0 for i in range(15)}
    selected, selection, _ = compose_judged_set(
        cands, max_candidates=12, reserve_k=3, cheap_eligible=cheap, last_judged={})
    syms = [c.symbol for c in selected]
    assert len(selected) == 12
    assert syms[:2] == ["NVDA", "FCX"]
    assert selection[("NVDA", "bullish")] == "rank"


def test_membership_only_objects_unchanged():
    # §10 seam guard: the composition returns the SAME frozen Theme objects — no mutation,
    # no re-derivation, nothing a prompt/gate/sizing input could observe per-candidate.
    cands = _union()
    selected, _, _ = compose_judged_set(
        cands, max_candidates=12, reserve_k=3, cheap_eligible={"S13": 1.0}, last_judged={})
    ids = {id(c) for c in cands}
    assert all(id(c) in ids for c in selected)


# ── gate_cheap_reads (state §3 data contract) ───────────────────────────────────────────────────


def _watch_row(conn, sym, *, iv_rv, cheap, as_of, run_id=1):
    conn.execute(
        "INSERT INTO cheapness_watch (run_id, as_of, symbol, contract_symbol, iv_rv, cheap, created_at) "
        "VALUES (?,?,?,?,?,?,?)", (run_id, as_of, sym, f"{sym}X", iv_rv, cheap, as_of))


def _dualread_row(conn, sym, *, iv_rv, cheap, evaluated_at, feed="opra"):
    conn.execute("INSERT OR IGNORE INTO runs (id, started_at, mode) VALUES (1, ?, 'PAPER')",
                 (evaluated_at,))
    conn.execute(
        "INSERT INTO gate_dualread (run_id, evaluated_at, symbol, feed, source, structured, iv_rv, cheap) "
        "VALUES (1,?,?,?,'sweep',1,?,?)", (evaluated_at, sym, feed, iv_rv, cheap))


def test_gate_cheap_reads_fresh_primary(convexity_db):
    _watch_row(convexity_db, "PAAS", iv_rv=0.95, cheap=1, as_of="2026-07-01T19:48:00+00:00")
    out = state.gate_cheap_reads(convexity_db, now=AS_OF, max_age_td=5)
    assert out == {"PAAS": 0.95}


def test_gate_cheap_reads_staleness_fail_closed(convexity_db):
    # 6 weekdays old (Wed 06-24 → Thu 07-02) > S=5 → NOT eligible (§3 fail-closed).
    _watch_row(convexity_db, "PAAS", iv_rv=0.95, cheap=1, as_of="2026-06-24T19:48:00+00:00")
    assert state.gate_cheap_reads(convexity_db, now=AS_OF, max_age_td=5) == {}
    # exactly 5 weekdays (Thu 06-25) → eligible at the boundary.
    _watch_row(convexity_db, "HL", iv_rv=1.1, cheap=1, as_of="2026-06-25T19:48:00+00:00")
    assert state.gate_cheap_reads(convexity_db, now=AS_OF, max_age_td=5) == {"HL": 1.1}


def test_gate_cheap_reads_latest_row_is_the_verdict(convexity_db):
    # The LATEST primary row governs: an older cheap=1 must not outrank a newer cheap=0.
    _watch_row(convexity_db, "VRT", iv_rv=0.9, cheap=1, as_of="2026-06-30T19:48:00+00:00")
    _watch_row(convexity_db, "VRT", iv_rv=1.4, cheap=0, as_of="2026-07-01T19:48:00+00:00")
    assert state.gate_cheap_reads(convexity_db, now=AS_OF, max_age_td=5) == {}


def test_gate_cheap_reads_fallback_only_fills_coverage_gaps(convexity_db):
    # No fresh primary for UEC → the opra dual-read fallback qualifies it.
    _dualread_row(convexity_db, "UEC", iv_rv=1.02, cheap=1, evaluated_at="2026-07-01T19:47:00+00:00")
    # Fresh primary NOT-cheap for NOC → the fallback must NOT overrule it.
    _watch_row(convexity_db, "NOC", iv_rv=1.5, cheap=0, as_of="2026-07-01T19:48:00+00:00")
    _dualread_row(convexity_db, "NOC", iv_rv=1.0, cheap=1, evaluated_at="2026-07-01T19:47:00+00:00")
    # An indicative-feed row never qualifies (gate-of-record is opra).
    _dualread_row(convexity_db, "AG", iv_rv=1.0, cheap=1, evaluated_at="2026-07-01T19:47:00+00:00",
                  feed="indicative")
    assert state.gate_cheap_reads(convexity_db, now=AS_OF, max_age_td=5) == {"UEC": 1.02}


def test_council_last_judged(convexity_db):
    convexity_db.execute(
        "INSERT OR IGNORE INTO runs (id, started_at, mode) VALUES (1, '2026-06-20', 'PAPER')")
    for as_of in ("2026-06-20T19:47:00+00:00", "2026-07-01T19:47:00+00:00"):
        state.record_council_proposal(
            convexity_db, run_id=1, as_of=as_of, theme="t", symbol="PL", direction="bullish",
            conviction="NEUTRAL", structural_vs_fad=None, weakest_point=None, rationale={},
            strategist_summary=None, cost_usd=0.0, model_mix={}, status="dropped")
    out = state.council_last_judged(convexity_db)
    assert out["PL"] == "2026-07-01T19:47:00+00:00"


# ── wiring integration (§6 provenance + the OFF-path byte-identity) ─────────────────────────────


def test_wiring_off_path_passes_candidates_through_untouched(monkeypatch, convexity_db):
    captured = {}

    def _spy(candidates, **kw):
        captured["candidates"] = candidates
        return []

    monkeypatch.setattr("council.wiring.propose", _spy)
    cands = _union()
    council_to_themes(convexity_db, candidates=cands, router=FakeRouter(),
                      config={"council": {}}, clock=_Clock(), run_id=None)
    assert captured["candidates"] is cands  # reserve off → the exact object, untouched


def test_wiring_reserve_selection_rides_rationale(monkeypatch, convexity_db):
    _watch_row(convexity_db, "S12", iv_rv=0.95, cheap=1, as_of="2026-07-01T19:48:00+00:00")

    def _fake_propose(candidates, **kw):
        from council.proposal import CouncilProposal
        return [CouncilProposal(theme=c.name, symbol=c.symbol, direction=c.direction,
                                conviction="NEUTRAL", structural_vs_fad=None, weakest_point=None,
                                strategist_summary=None, rationale={"order": "x"}, agent_outputs=[],
                                cost_usd=0.0, model_mix={}, include=False,
                                sentinel_id=c.sentinel_id)
                for c in candidates]

    monkeypatch.setattr("council.wiring.propose", _fake_propose)
    convexity_db.execute(
        "INSERT OR IGNORE INTO runs (id, started_at, mode) VALUES (1, '2026-07-01', 'PAPER')")
    cfg = {"council": {"cheap_reserve_slots": 3, "max_candidates": 12}}
    council_to_themes(convexity_db, candidates=_union(), router=FakeRouter(),
                      config=cfg, clock=_Clock(), run_id=1)
    rows = {r["symbol"]: state._json_or_none(r["rationale"]) for r in convexity_db.execute(
        "SELECT symbol, rationale FROM council_proposals")}
    assert rows["S12"]["selection"] == "reserve"
    assert rows["S00"]["selection"] == "rank"
    assert rows["NVDA"]["selection"] == "rank"
    assert rows["S12"]["order"] == "x"  # the existing rationale keys survive the merge


def test_wiring_reserve_needs_conn_and_positive_k(monkeypatch, convexity_db):
    # sentinel_id-less conn path guard: k>0 but conn=None (a caller without a DB) must not crash
    # and must not compose — fail-soft to the old slice.
    captured = {}

    def _spy(candidates, **kw):
        captured["candidates"] = candidates
        return []

    monkeypatch.setattr("council.wiring.propose", _spy)
    cands = _union()
    council_to_themes(None, candidates=cands, router=FakeRouter(),
                      config={"council": {"cheap_reserve_slots": 3}}, clock=_Clock(), run_id=None)
    assert captured["candidates"] is cands


# ── seam guards (§2/§10): prompts + gate/sizing inputs are reserve-blind ────────────────────────


def test_seam_prompts_unchanged_by_reserve_config():
    # The sha-pinned prompt test (test_council_prompts.py) enforces byte-exactness; here we assert
    # the reserve path cannot even REACH the prompt layer: compose_judged_set has no imports from
    # council.agents and returns the caller's own objects (membership only).
    import council.council as cc
    names = cc.compose_judged_set.__code__.co_names
    assert "agents" not in names and "build_context_pack" not in names
    # And the composition consumes nothing but its four declared inputs — no router, no pack.
    assert cc.compose_judged_set.__code__.co_varnames[:5] == (
        "candidates", "max_candidates", "reserve_k", "cheap_eligible", "last_judged")


def test_seam_gate_and_sizing_reserve_blind():
    # convexity_gate / convexity_sizing never read the selection provenance — the reserve changes
    # the judged set, never a gate value or sizing input (§2).
    import inspect

    import convexity_gate
    import convexity_sizing
    for mod in (convexity_gate, convexity_sizing):
        src = inspect.getsource(mod)
        assert "cheap_reserve" not in src and "selection" not in src.lower().replace(
            "select_structure", "")
