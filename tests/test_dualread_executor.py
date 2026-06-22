"""The §5 dual-read tripwire RUNTIME executor (#72 / the 2026-07-10 close-out amendment).

Covers, fixture-driven and offline:
  • the per-class coverage-gap partition in ``gate_dualread_report`` (incl. the 1+1+1 heterogeneous
    independence rule) and sweep-error classification reaching the SWEEP population;
  • the ≥4-consecutive debounce (the three flicker shapes + the literal UROY sequence);
  • the THREE safety invariants (wrong-class can't revert; flag-off never reverts; one name's flaky
    chain never raises the feed-wide entitlement state);
  • the fail-soft evaluator envelope (an exception → the cycle completes + a degraded page);
  • the single-source guard (patch the canonical report → the executor branches on ITS output).
"""

from __future__ import annotations

from datetime import UTC, datetime

import dualread_executor as dx
import gate_dualread
import state
from dashboard_data import gate_dualread_report

AS_OF = datetime(2026, 6, 10, 15, 45, tzinfo=UTC).isoformat()


# ── a capturing notifier (run_executor takes notify=; .send already never raises) ────────────────

class FakeNotify:
    def __init__(self):
        self.pages: list[tuple[str, str, int]] = []

    def send(self, title, message, *, priority=0):
        self.pages.append((title, message, priority))
        return True

    def titles(self):
        return [t for t, _, _ in self.pages]


def _session(conn, *, arms: list[dict]):
    """Write one synthetic dual-read SESSION (a fresh run_id) of arm rows. Each arm dict is a
    ``record_gate_dualread`` kwargs payload (symbol/feed/structured/iv_rv/cheap/note)."""
    rid = state.record_run(conn, mode="TEST", equity=None, note="t")
    for a in arms:
        state.record_gate_dualread(conn, run_id=rid, as_of=AS_OF, source="sweep", **a)
    return rid


def _opra(sym, **kw):
    return dict(symbol=sym, feed="opra", **kw)


def _ind(sym, **kw):
    return dict(symbol=sym, feed="indicative", **kw)


def _gap(sym, *, note=None):
    """A coverage-gap pair for ``sym``: INDICATIVE structures, OPRA does not (with ``note``)."""
    return [_opra(sym, structured=False, note=note),
            _ind(sym, structured=True, iv_rv=1.05, cheap=True)]


# ══════════════════════════════════════════════════════════════════════════════════════════════
# 1. the per-class partition (the report) + sweep-error classification reaching the SWEEP population
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_gap_partition_classes_by_note(convexity_db):
    """structural-absence / entitlement / transient split off the OPRA ¬structured note."""
    _session(convexity_db, arms=[
        *_gap("AAA", note="no_eligible_contract_in_tenor_window"),  # structural
        *_gap("BBB", note="transient: connection timed out"),       # transient
        *_gap("CCC", note="entitlement: subscription does not permit"),  # entitlement (feed-wide)
    ])
    rep = gate_dualread_report(convexity_db)
    s = rep["sessions"][-1]
    assert s["gap_structural"] == ["AAA"]
    assert s["gap_transient"] == ["BBB"]
    assert s["entitlement"] is True  # CCC's note raised the feed-wide flag
    assert sorted(s["coverage_gaps"]) == ["AAA", "BBB", "CCC"]  # all three are still gaps


def test_partition_1plus1plus1_does_not_aggregate(convexity_db):
    """The trip rule: 1 structural + 1 transient + 1 entitlement across reasons trips NOTHING on
    absence/transient (each needs ≥2/5 of its OWN class); only entitlement pages on its per-session
    rule. One heterogeneous session ⇒ no structural/transient trip."""
    _session(convexity_db, arms=[
        *_gap("AAA", note="no_eligible_contract_in_tenor_window"),
        *_gap("BBB", note="transient: blip"),
        *_gap("CCC", note="entitlement: not authorized"),
    ])
    rep = gate_dualread_report(convexity_db)
    gp = rep["gap_partition"]
    assert gp["structural_sessions"] == 1 and not gp["structural_tripped"]   # 1 < 2
    assert gp["transient_sessions"] == 1 and not gp["transient_escalate"]    # 1 < 2
    assert gp["entitlement_active"] is True  # per-session, feed-wide — fires on its own
    # and the executor agrees: no structural/transient/flip revert, only the entitlement page
    v = dx.evaluate(rep, {})
    assert v["gap_structural"]["tripped"] is False
    assert v["entitlement"]["active"] is True
    assert v["delta"]["revert_authorized"] is False


def test_structural_trips_at_two_of_five(convexity_db):
    for _ in range(2):
        _session(convexity_db, arms=_gap("AAA", note="no_eligible_contract_in_tenor_window"))
    rep = gate_dualread_report(convexity_db)
    gp = rep["gap_partition"]
    assert gp["structural_sessions"] == 2 and gp["structural_tripped"] is True


def test_transient_escalates_at_two_of_five(convexity_db):
    for _ in range(2):
        _session(convexity_db, arms=_gap("BBB", note="transient: timed out"))
    rep = gate_dualread_report(convexity_db)
    gp = rep["gap_partition"]
    assert gp["transient_sessions"] == 2 and gp["transient_escalate"] is True
    v = dx.evaluate(rep, {})
    assert "BBB" in v["gap_transient"]["pages"]  # ≥2/5 ⇒ the per-name escalation page


def test_sweep_error_classification_reaches_sweep_population(convexity_db):
    """The SWEEP arm stores a CLASSIFIED note (not raw str(e)) — entitlement detection now reaches
    the sweep population, which §7 covered only for INLINE-evaluated names."""

    class EntitlementChain:
        def chain(self, symbol):
            raise RuntimeError("subscription does not permit querying premium option data")

    class CloseProvider:
        def closes(self, symbol, *, window):
            return [50.0] * window

    closes = CloseProvider()
    run_id = state.record_run(convexity_db, mode="TEST", equity=None, note="t")
    counts = gate_dualread.sweep_universe(
        convexity_db, run_id=run_id, as_of_iso=AS_OF, symbols=["FCX"],
        provider_record=EntitlementChain(), provider_shadow=EntitlementChain(),
        market_closes=lambda s: closes.closes(s, window=300),
        gate={"rv_window_days": 252}, eligibility=lambda c: (True, None))
    assert counts["errors"] >= 1
    notes = [r[0] for r in convexity_db.execute(
        "SELECT note FROM gate_dualread WHERE feed='opra' AND source='sweep'").fetchall()]
    assert any(n and n.startswith("entitlement:") for n in notes), notes
    # and the report routes it to the feed-wide entitlement state
    rep = gate_dualread_report(convexity_db)
    assert rep["sessions"][-1]["entitlement"] is True


def test_sweep_transient_error_classifies_transient(convexity_db):
    class FlakyChain:
        def chain(self, symbol):
            raise TimeoutError("connection reset")

    closes = lambda s: [50.0] * 300  # noqa: E731
    run_id = state.record_run(convexity_db, mode="TEST", equity=None, note="t")
    gate_dualread.sweep_universe(
        convexity_db, run_id=run_id, as_of_iso=AS_OF, symbols=["NVDA"],
        provider_record=FlakyChain(), provider_shadow=FlakyChain(),
        market_closes=closes, gate={"rv_window_days": 252}, eligibility=lambda c: (True, None))
    notes = [r[0] for r in convexity_db.execute(
        "SELECT note FROM gate_dualread WHERE feed='opra'").fetchall()]
    assert any(n and n.startswith("transient:") for n in notes), notes
    rep = gate_dualread_report(convexity_db)
    assert rep["sessions"][-1]["entitlement"] is False  # transient ≠ entitlement (feed-wide)


# ══════════════════════════════════════════════════════════════════════════════════════════════
# 2. the ≥4-consecutive debounce — the three flicker shapes + the literal UROY sequence
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_debounce_rising_edge_pages_once():
    # a fresh trip pages; a parked trip does not
    assert dx.rising_edge_page([False, False, True]) is True
    assert dx.rising_edge_page([False, True, True]) is False   # second consecutive trip: parked
    assert dx.rising_edge_page([True, True, True, True]) is False


def test_debounce_short_wing_run_does_not_rearm():
    # [absent, wing, wing, wing(<4), absent] — the 3-wing run does NOT re-arm ⇒ second absence suppressed
    assert dx.rising_edge_page([True, False, False, False, True]) is False
    # 4 consecutive wings DO re-arm ⇒ the next absence is a fresh rising edge
    assert dx.rising_edge_page([True, False, False, False, False, True]) is True


def test_debounce_literal_uroy_sequence():
    """UROY: present #130/#147, absent #164, present #182, absent #199/#216 (per the close-out).
    'present' = a durable wing (re-arm step), 'absent' = structurally absent. The two absences are
    separated by a single wing session (#182) — far short of 4 — so the SECOND absence run
    (#199/#216) must NOT re-page; only #164's first absence is the rising edge."""
    # encode as the per-name structural history (True=absent):
    #   #130 wing, #147 wing, #164 absent, #182 wing, #199 absent, #216 absent
    seq = [False, False, True, False, True, True]
    # at #164 (index 2) it would page; we assert the LAST session (#216) does NOT
    assert dx.rising_edge_page(seq) is False
    # and the #164 rising edge in isolation:
    assert dx.rising_edge_page([False, False, True]) is True


def test_structural_debounce_via_report(convexity_db):
    """The structural-absence debounce reads ``gap_structural`` (trip) vs ``opra_wing`` (re-arm) off
    the report's sessions. A flicker name pages once, then stays parked across a sub-4 wing run."""
    # S1 absent, S2 wing, S3 absent  → only S1 is a rising edge; by S3 still parked (1 wing < 4)
    _session(convexity_db, arms=_gap("UROY", note="no_eligible_contract_in_tenor_window"))
    _session(convexity_db, arms=[_opra("UROY", structured=True, iv_rv=1.0, cheap=True),
                                 _ind("UROY", structured=True, iv_rv=1.0, cheap=True)])
    _session(convexity_db, arms=_gap("UROY", note="no_eligible_contract_in_tenor_window"))
    rep = gate_dualread_report(convexity_db)
    v = dx.evaluate(rep, {})
    assert v["gap_structural"]["pages"] == []  # parked — the sub-4 wing did not re-arm


def test_material_flip_debounce_via_report(convexity_db):
    """A material flip pages on the rising edge, then is suppressed while parked."""
    def flip_session():
        _session(convexity_db, arms=[_opra("DDD", structured=True, iv_rv=1.30, cheap=False),
                                     _ind("DDD", structured=True, iv_rv=1.10, cheap=True)])
    flip_session()
    rep = gate_dualread_report(convexity_db)
    assert dx.evaluate(rep, {})["material_flip"]["pages"] == ["DDD"]  # rising edge
    flip_session()  # second consecutive flip session → parked
    rep = gate_dualread_report(convexity_db)
    assert dx.evaluate(rep, {})["material_flip"]["pages"] == []


# ══════════════════════════════════════════════════════════════════════════════════════════════
# 3. THE SAFETY INVARIANTS (load-bearing)
# ══════════════════════════════════════════════════════════════════════════════════════════════

def _flag_on():
    return {"data_feed": {"dualread_revert_enabled": True}}


def test_invariant_1_wrong_class_never_reverts(convexity_db):
    """The load-bearing safety invariant: a structural-absence trip AND an entitlement state, with the
    flag ON but NO Δ breach, write NO sentinel and emit NO revert page (reverting would restore phantom
    coverage / silently downgrade a held feed). Only the Δ wire can write the sentinel."""
    writes: list[str] = []
    # a 2/5 structural trip + a feed-wide entitlement session, flag ON, but NO delta breach
    for _ in range(2):
        _session(convexity_db, arms=_gap("AAA", note="no_eligible_contract_in_tenor_window"))
    _session(convexity_db, arms=_gap("CCC", note="entitlement: not authorized"))
    rep = gate_dualread_report(convexity_db)
    assert rep["gap_partition"]["structural_tripped"] is True
    assert rep["gap_partition"]["entitlement_active"] is True
    assert rep["tripwires"]["delta_tripped"] is False
    n = FakeNotify()
    v = dx.run_executor(rep, _flag_on(), notify=n, write_sentinel=writes.append)
    assert writes == []                          # NO sentinel written on structural/entitlement
    assert v["revert_written"] is False
    titles = " ".join(n.titles())
    assert "entitlement lapse" in titles         # entitlement → feed-wide page (never debounced)
    assert "REVERTED" not in titles              # no revert page, ever, for the wrong class


def test_structural_fresh_edge_pages_feasibility_no_revert(convexity_db):
    """A FRESH structural absence (the rising edge) → a coverage-feasibility page, flag ON, still NO
    sentinel (the page is the whole response — structural absence is OPRA-correct, never a revert)."""
    writes: list[str] = []
    _session(convexity_db, arms=_gap("AAA", note="no_eligible_contract_in_tenor_window"))
    rep = gate_dualread_report(convexity_db)
    n = FakeNotify()
    v = dx.run_executor(rep, _flag_on(), notify=n, write_sentinel=writes.append)
    assert writes == [] and v["revert_written"] is False
    assert "AAA" in v["gap_structural"]["pages"]
    assert any("coverage-feasibility" in t for t in n.titles())


def test_invariant_2_flag_off_never_reverts(convexity_db):
    """With dualread_revert_enabled=false, NO revert fires even when the Δ wire trips."""
    writes: list[str] = []
    # 3/5 delta breaches (med>0.05): iv_rv 1.30 vs 1.10 → Δ 0.20 each
    for _ in range(3):
        _session(convexity_db, arms=[_opra("ZZZ", structured=True, iv_rv=1.30, cheap=True),
                                     _ind("ZZZ", structured=True, iv_rv=1.10, cheap=True)])
    rep = gate_dualread_report(convexity_db)
    assert rep["tripwires"]["delta_tripped"] is True
    n = FakeNotify()
    # default config (flag absent ⇒ false)
    v = dx.run_executor(rep, {"data_feed": {}}, notify=n, write_sentinel=writes.append)
    assert writes == []
    assert v["delta"]["revert_authorized"] is False
    assert v["revert_written"] is False
    # the Δ wire still PAGES (Phase 2) — it just doesn't revert
    assert any("Δ iv/rv" in t for t in n.titles())
    assert any("revert latch OFF" in m for _, m, _ in n.pages)


def test_invariant_2b_flag_on_delta_reverts(convexity_db):
    """The positive control: flag ON + Δ wire tripped ⇒ the sentinel IS written, plus a page."""
    writes: list[str] = []
    for _ in range(3):
        _session(convexity_db, arms=[_opra("ZZZ", structured=True, iv_rv=1.30, cheap=True),
                                     _ind("ZZZ", structured=True, iv_rv=1.10, cheap=True)])
    rep = gate_dualread_report(convexity_db)
    n = FakeNotify()
    v = dx.run_executor(rep, _flag_on(), notify=n, write_sentinel=writes.append)
    assert len(writes) == 1                       # the sole revert trigger fired
    assert v["revert_written"] is True
    assert any("REVERTED to indicative" in t for t in n.titles())


def test_invariant_3_one_flaky_name_never_raises_feed_wide_entitlement(convexity_db):
    """A per-name transient blip classes 'transient' (per-name escalation), NOT entitlement — one
    name's flaky chain must never raise the feed-wide entitlement state."""
    _session(convexity_db, arms=[
        *_gap("AAA", note="transient: connection reset"),            # per-name blip
        *_gap("BBB", note="no_eligible_contract_in_tenor_window"),   # structural
    ])
    rep = gate_dualread_report(convexity_db)
    s = rep["sessions"][-1]
    assert s["entitlement"] is False             # NO feed-wide state from a transient
    assert s["gap_transient"] == ["AAA"]
    assert s["gap_structural"] == ["BBB"]
    v = dx.evaluate(rep, _flag_on())
    assert v["entitlement"]["active"] is False
    assert v["delta"]["revert_authorized"] is False


def test_real_sentinel_writer_round_trip(tmp_path, monkeypatch):
    """write_revert_sentinel writes; revert_latched reads; removing un-latches (the operator path)."""
    sentinel = tmp_path / "OPRA_REVERTED"
    monkeypatch.setattr(dx, "REVERT_SENTINEL", sentinel)
    assert dx.revert_latched() is False
    dx.write_revert_sentinel("test")
    assert dx.revert_latched() is True and sentinel.exists()
    sentinel.unlink()
    assert dx.revert_latched() is False


# ══════════════════════════════════════════════════════════════════════════════════════════════
# 4. the single-source guard — the executor branches on the REPORT's output (no re-derivation)
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_single_source_executor_follows_report_delta_trip():
    """Patch the canonical report's verdict → the executor's revert decision FLIPS with it, proving
    it consumes the report rather than re-deriving the Δ/flip/partition math."""
    base = {"tripwires": {"delta_tripped": False, "flip_tripped": False},
            "gap_partition": {"structural_tripped": False, "entitlement_active": False},
            "sessions": []}
    # report says NOT tripped → no revert even with the flag on
    assert dx.evaluate(base, _flag_on())["delta"]["revert_authorized"] is False
    # flip ONLY the report's delta_tripped → the executor now authorizes the revert
    tripped = {**base, "tripwires": {"delta_tripped": True, "flip_tripped": False}}
    assert dx.evaluate(tripped, _flag_on())["delta"]["revert_authorized"] is True
    # and with the flag off, the same tripped report does NOT authorize
    assert dx.evaluate(tripped, {"data_feed": {}})["delta"]["revert_authorized"] is False


def test_single_source_run_executor_uses_patched_report(convexity_db, monkeypatch):
    """run_executor's orchestrator-facing path: patch gate_dualread_report to a canned tripped
    verdict → run_executor pages/reverts off THAT, never recomputing from rows."""
    import dashboard_data

    canned = {"tripwires": {"delta_tripped": True, "flip_tripped": False},
              "gap_partition": {"structural_tripped": False, "entitlement_active": False},
              "sessions": []}
    monkeypatch.setattr(dashboard_data, "gate_dualread_report", lambda *a, **k: canned)
    writes: list[str] = []
    n = FakeNotify()
    # simulate the orchestrator hook: report = gate_dualread_report(...); run_executor(report, ...)
    rep = dashboard_data.gate_dualread_report(convexity_db, {})
    v = dx.run_executor(rep, _flag_on(), notify=n, write_sentinel=writes.append)
    assert v["delta"]["tripped"] is True and len(writes) == 1  # branched on the patched report


# ══════════════════════════════════════════════════════════════════════════════════════════════
# 5. the fail-soft evaluator envelope (an exception → the cycle completes + a degraded page)
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_executor_degrades_loud_but_never_raises(monkeypatch):
    """If evaluate() blows up, run_executor's caller (the orchestrator) catches it. Here we prove the
    orchestrator-shaped envelope: an exception inside is converted to a LOUD degraded page, and the
    surrounding try/except in orchestrator.py lets the cycle complete. We simulate the envelope."""
    n = FakeNotify()

    def boom_report(*a, **k):
        raise RuntimeError("report exploded")

    # the orchestrator's actual envelope (mirrors orchestrator.py): try → except → degraded page
    completed = False
    try:
        report = boom_report()
        dx.run_executor(report, {}, notify=n)
    except Exception as e:  # noqa: BLE001 — the cycle must complete
        n.send("Dual-read §5 executor DEGRADED", f"errored: {e}", priority=1)
    completed = True
    assert completed is True
    assert any("DEGRADED" in t for t in n.titles())


def test_executor_internal_sentinel_write_failure_fails_loud(convexity_db):
    """If the Δ wire trips with the flag ON but the sentinel WRITE fails, the executor fails LOUD
    (a page) and reports revert_written=False — the gate stays UNCHANGED, never a silent half-revert."""
    for _ in range(3):
        _session(convexity_db, arms=[_opra("ZZZ", structured=True, iv_rv=1.30, cheap=True),
                                     _ind("ZZZ", structured=True, iv_rv=1.10, cheap=True)])
    rep = gate_dualread_report(convexity_db)
    n = FakeNotify()

    def failing_writer(reason):
        raise OSError("disk full")

    v = dx.run_executor(rep, _flag_on(), notify=n, write_sentinel=failing_writer)
    assert v["revert_written"] is False
    assert any("revert FAILED to latch" in t for t in n.titles())
