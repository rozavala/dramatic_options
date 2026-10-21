"""council.demote_unexpressible — the expressible-first slate, built behind a switch (default off).

After the 2026-10-19 tenor cliff ~2 of 12 council slots a night went to names with no eligible contract (ATKR took
a fairness slot on 10-20). With the switch on, a sentinel whose latest fresh gate-of-record read found no structure
is held out of the composition and only backfills empty slots. Off is byte-identical.
"""
from __future__ import annotations

from datetime import UTC, datetime

import state
from council.router import FakeRouter
from council.wiring import council_to_themes
from themes import Theme

AS_OF = datetime(2026, 10, 21, 19, 45, tzinfo=UTC)


class _Clock:
    def now(self):
        return AS_OF


def _hand(sym="NVDA"):
    return Theme(name=f"hand_{sym}", symbol=sym, direction="bullish", thesis="t")


def _sent(sym, sid):
    return Theme(name=f"s_{sym}", symbol=sym, direction="bullish", thesis="t", source="sentinel", sentinel_id=sid)


def _read(conn, sym, *, structured, evaluated_at="2026-10-20T19:49:00+00:00"):
    conn.execute("INSERT OR IGNORE INTO runs (id, started_at, mode) VALUES (1, ?, 'PAPER')", (evaluated_at,))
    conn.execute("INSERT INTO gate_dualread (run_id, evaluated_at, symbol, feed, source, structured, iv_rv, cheap) "
                 "VALUES (1,?,?,'opra','sweep',?,?,?)",
                 (evaluated_at, sym, structured, 0.9 if structured else None, 1 if structured else None))


def _spy(monkeypatch):
    captured = {}

    def _fake(candidates, **kw):
        captured["candidates"] = list(candidates)
        return []
    monkeypatch.setattr("council.wiring.propose", _fake)
    return captured


def test_unexpressible_needs_fresh_positive_evidence(convexity_db):
    _read(convexity_db, "ATKR", structured=0)
    _read(convexity_db, "ERO", structured=1)
    _read(convexity_db, "OLD", structured=0, evaluated_at="2026-10-01T19:49:00+00:00")   # stale → not held
    _read(convexity_db, "FLIP", structured=0, evaluated_at="2026-10-19T19:49:00+00:00")
    _read(convexity_db, "FLIP", structured=1, evaluated_at="2026-10-20T19:49:00+00:00")  # latest row decides
    assert state.unexpressible_symbols(convexity_db, now=AS_OF) == frozenset({"ATKR"})


def test_off_is_byte_identical(monkeypatch, convexity_db):
    _read(convexity_db, "S00", structured=0)
    captured = _spy(monkeypatch)
    cands = [_hand()] + [_sent(f"S{i:02d}", i + 1) for i in range(15)]
    council_to_themes(convexity_db, candidates=cands, router=FakeRouter(), config={"council": {}},
                      clock=_Clock(), run_id=None)
    assert [c.symbol for c in captured["candidates"]] == [c.symbol for c in cands]


def test_on_held_names_lose_motion_and_fairness_slots(monkeypatch, convexity_db):
    # S13 is the only never-judged name past the motion cut, so the fairness reserve picks it FIRST when off — the
    # ATKR-on-10-20 shape. S00 tops the motion rank. Both have no structure.
    for i in range(15):
        if i != 13:
            state.record_council_proposal(convexity_db, run_id=None, as_of="2026-10-01T19:45:00+00:00",
                                          theme="t", symbol=f"S{i:02d}", direction="bullish", conviction="LOW")
    for sym in ("S00", "S13"):
        _read(convexity_db, sym, structured=0)
    cands = [_hand()] + [_sent(f"S{i:02d}", i + 1) for i in range(15)]
    base = {"fairness_slots": 2, "max_candidates": 12}

    captured = _spy(monkeypatch)
    council_to_themes(convexity_db, candidates=cands, router=FakeRouter(), config={"council": base},
                      clock=_Clock(), run_id=None)
    off = [c.symbol for c in captured["candidates"]]
    assert "S00" in off and "S13" in off                 # off: both take slots (motion + fairness)

    council_to_themes(convexity_db, candidates=cands, router=FakeRouter(),
                      config={"council": {**base, "demote_unexpressible": True}}, clock=_Clock(), run_id=None)
    on = [c.symbol for c in captured["candidates"]]
    assert len(on) == 12 and on[0] == "NVDA"             # the hand-seed is never held
    assert "S00" not in on and "S13" not in on           # expressible names filled every slot


def test_on_held_names_backfill_empty_slots(monkeypatch, convexity_db):
    _read(convexity_db, "S01", structured=0)
    captured = _spy(monkeypatch)
    cands = [_hand()] + [_sent(f"S{i:02d}", i + 1) for i in range(4)]   # fewer candidates than slots
    cfg = {"council": {"demote_unexpressible": True, "max_candidates": 12}}
    council_to_themes(convexity_db, candidates=cands, router=FakeRouter(), config=cfg, clock=_Clock(), run_id=None)
    assert [c.symbol for c in captured["candidates"]] == ["NVDA", "S00", "S02", "S03", "S01"]   # S01 last


def test_on_without_a_db_is_a_no_op(monkeypatch):
    captured = _spy(monkeypatch)
    cands = [_hand(), _sent("S00", 1)]
    council_to_themes(None, candidates=cands, router=FakeRouter(),
                      config={"council": {"demote_unexpressible": True}}, clock=_Clock(), run_id=None)
    assert [c.symbol for c in captured["candidates"]] == ["NVDA", "S00"]
