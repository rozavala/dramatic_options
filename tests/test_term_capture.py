"""#455/#462 capture (PREREG_CHEAP_THEN_REPRICED §4.1): the nightly term record gains rv63/rv21 and the tracked
contracts' quotes from the SAME chain the OPRA arm fetched — no extra fetch, no migration, no stamp — and every step
of it sits inside the sink's try/except, so it can never change, delay or skip a gate read or a gate_dualread row."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

import gate_dualread
import iv_history
import state
from convexity_data import SyntheticChainProvider
from convexity_gate import realized_vol
from data.cache import PointInTimeCache

AS_OF = datetime(2026, 12, 8, 20, 45, tzinfo=UTC)
GATE = {"iv_rv_max": 1.2, "otm_skew_max_volpts": 10.0, "rv_window_days": 252, "tenor_min_days": 180,
        "tenor_max_days": 365, "target_moneyness": 0.25}
MISSING = "FCX990115C00001000"


class _Counting(SyntheticChainProvider):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.chain_calls: list[str] = []
        self.closes_calls: list[str] = []

    def chain(self, symbol):
        self.chain_calls.append(symbol)
        return super().chain(symbol)

    def closes(self, symbol, *, window):
        self.closes_calls.append(symbol)
        return super().closes(symbol, window=window)


def _sweep(conn, cache, provider, *, run_id, symbols=("FCX", "NVDA")):
    return gate_dualread.sweep_universe(
        conn, run_id=run_id, as_of_iso=AS_OF.isoformat(), symbols=list(symbols), provider_record=provider,
        provider_shadow=provider, market_closes=lambda s: provider.closes(s, window=300), gate=GATE,
        eligibility=lambda c: (True, None), skip=set(), term_cache=cache)


def _rows(conn, run_id):
    return [tuple(r) for r in conn.execute(
        "SELECT symbol, feed, source, structured, iv_rv, otm_skew, cheap, wing, note FROM gate_dualread "
        "WHERE run_id = ? ORDER BY id", (run_id,))]


def _seed_positions(conn, chain_contract: str):
    common = dict(run_id=None, opened_at="2026-11-01T19:50:00+00:00", theme="t", symbol="FCX", direction="bullish",
                  structure_kind="C", expiry="2027-09-04", strike=42.8, dte=300, moneyness=0.25, contracts=1,
                  entry_premium_per_contract=160.0, total_premium=160.0)
    state.record_convexity_position(conn, contract_symbol=chain_contract, short_contract_symbol=MISSING, **common)
    state.record_shadow_position(conn, origin="sentinel", contract_symbol="FCX270904C00099000", **common)
    state.record_fixed_basket_position(conn, book="union_nogate", origin="sentinel",
                                       contract_symbol="FCX270904C00098000", **common)
    closed = state.record_convexity_position(conn, contract_symbol="FCX270904C00097000", **common)
    with conn:
        conn.execute("UPDATE convexity_positions SET status = 'closed' WHERE id = ?", (closed,))


def test_the_record_carries_rv63_rv21_quotes_and_no_extra_fetch(convexity_db, tmp_path):
    provider = _Counting(as_of=AS_OF.date())
    chain = provider.chain("FCX")
    provider.chain_calls.clear()
    pos_contract = chain[1].symbol
    _seed_positions(convexity_db, pos_contract)
    cache = PointInTimeCache(tmp_path / "cache")
    rid = state.record_run(convexity_db, mode="TEST", equity=None, note="t")
    counts = _sweep(convexity_db, cache, provider, run_id=rid)
    assert counts["term_ok"] == 2 and counts["record_ok"] == 2
    # no fetch beyond the sweep's own: one chain per arm per name, one closes per name
    assert sorted(provider.chain_calls) == ["FCX", "FCX", "NVDA", "NVDA"]
    assert sorted(provider.closes_calls) == ["FCX", "NVDA"]
    rec = cache.read_between(iv_history.TERM_SOURCE, "FCX", None, AS_OF)[-1]
    closes = provider.closes("FCX", window=300)
    assert rec["rv63"] == pytest.approx(realized_vol(closes, window=63))
    assert rec["rv21"] == pytest.approx(realized_vol(closes, window=21))
    assert rec["term_version"] == iv_history.TERM_VERSION == 1
    wing = convexity_db.execute("SELECT wing FROM gate_dualread WHERE symbol='FCX' AND feed='opra'").fetchone()[0]
    q = rec["quotes"]
    assert set(q) == {wing, pos_contract, MISSING, "FCX270904C00099000", "FCX270904C00098000"}  # closed one absent
    by = {c.symbol: c for c in chain}
    assert q[wing] == [by[wing].bid, by[wing].ask, by[wing].iv]
    assert q[MISSING] is None and q["FCX270904C00099000"] is None          # not in the chain: null, never dropped
    assert rec["expiries"] and rec["spot"] and rec["rv"]                  # the old fields are unchanged


def _identical_gate_rows(convexity_db, tmp_path, monkeypatch, breaker):
    provider = SyntheticChainProvider(as_of=AS_OF.date())
    base = state.record_run(convexity_db, mode="TEST", equity=None, note="no term")
    gate_dualread.sweep_universe(
        convexity_db, run_id=base, as_of_iso=AS_OF.isoformat(), symbols=["FCX", "NVDA"], provider_record=provider,
        provider_shadow=provider, market_closes=lambda s: provider.closes(s, window=300), gate=GATE,
        eligibility=lambda c: (True, None), skip=set(), term_cache=None)
    breaker(monkeypatch)
    rid = state.record_run(convexity_db, mode="TEST", equity=None, note="broken capture")
    counts = _sweep(convexity_db, PointInTimeCache(tmp_path / "c"), provider, run_id=rid)
    assert _rows(convexity_db, rid) == _rows(convexity_db, base)            # the gate rows are identical
    assert counts["record_ok"] == 2 and counts["shadow_ok"] == 2 and counts["errors"] == 0
    return counts, tmp_path / "c"


def test_a_raising_tracked_set_read_never_touches_the_gate_rows(convexity_db, tmp_path, monkeypatch):
    def breaker(mp):
        mp.setattr(gate_dualread, "tracked_contracts", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db gone")))

    counts, path = _identical_gate_rows(convexity_db, tmp_path, monkeypatch, breaker)
    rec = PointInTimeCache(path).read_between(iv_history.TERM_SOURCE, "FCX", None, AS_OF)[-1]
    assert "quotes" not in rec and rec["rv63"] is not None and counts["term_ok"] == 2   # only the failing field is gone


def test_a_raising_record_write_never_touches_the_gate_rows(convexity_db, tmp_path, monkeypatch):
    def breaker(mp):
        mp.setattr(iv_history, "persist_term_record", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))

    counts, _ = _identical_gate_rows(convexity_db, tmp_path, monkeypatch, breaker)
    assert counts["term_ok"] == 0


def test_a_raising_quote_lookup_leaves_the_old_record(convexity_db, tmp_path, monkeypatch):
    def breaker(mp):
        mp.setattr(iv_history, "tracked_quotes", lambda *a, **k: (_ for _ in ()).throw(ValueError("bad row")))

    counts, path = _identical_gate_rows(convexity_db, tmp_path, monkeypatch, breaker)
    rec = PointInTimeCache(path).read_between(iv_history.TERM_SOURCE, "FCX", None, AS_OF)[-1]
    assert "quotes" not in rec and rec["expiries"] and counts["term_ok"] == 2


def _gd(conn, rid, day, sym, wing, structured=True):
    state.record_gate_dualread(conn, run_id=rid, as_of=f"{day}T20:45:00+00:00", symbol=sym, feed="opra",
                               source="sweep", structured=structured, iv_rv=1.0, otm_skew=1.0, cheap=True,
                               wing=wing, note=None)


def test_tracked_set_unit_date_wings_and_the_70_session_window(convexity_db):
    from datetime import date, timedelta

    conn = convexity_db
    rid = state.record_run(conn, mode="TEST", equity=None, note="t")
    d0 = date(2026, 8, 3)   # a Monday
    days = [d0 + timedelta(days=i) for i in range(0, 200) if (d0 + timedelta(days=i)).weekday() < 5][:80]
    for i, d in enumerate(days):
        _gd(conn, rid, d.isoformat(), "FCX", f"W{i:03d}")
    tue = next(d for d in days[-20:] if d.weekday() == 1)
    _gd(conn, rid, tue.isoformat(), "NVDA", "NV1")               # a Tuesday row: not on its week's unit date (Monday)
    tonight = days[-1] + timedelta(days=1)
    got = gate_dualread.tracked_contracts(conn, as_of=tonight)
    window = days[-69:]                                          # the 69 sweep dates before tonight
    want = set()
    seen_weeks = set()
    for i, d in enumerate(days):                                 # unit date = the FIRST sweep date of its ISO week
        wk = d.isocalendar()[:2]
        if wk not in seen_weeks:
            seen_weeks.add(wk)
            if d in window:
                want.add(f"W{i:03d}")
    assert got["FCX"] == want and all(w in {f"W{i:03d}" for i in range(80)} for w in got["FCX"])
    # hand check: 80 weekdays from a Monday; the 69 before tonight are indices 11..79. Index 11 is a Tuesday, so its
    # week's unit date (index 10) is outside the window; the Mondays at 15, 20, ..., 75 are in.
    assert want == {f"W{i:03d}" for i in range(15, 80, 5)} and len(want) == 13
    assert "NVDA" not in got                                     # the unit date is the week's, not the name's


def test_tracked_set_takes_the_last_sweep_row_of_a_unit_date(convexity_db):
    conn = convexity_db
    rid = state.record_run(conn, mode="TEST", equity=None, note="t")
    _gd(conn, rid, "2026-12-07", "FCX", "FIRST")
    _gd(conn, rid, "2026-12-07", "FCX", "RERUN")                 # a same-day re-run: the last row wins
    _gd(conn, rid, "2026-12-07", "NVDA", None, structured=False)  # unstructured: no wing
    from datetime import date

    assert gate_dualread.tracked_contracts(conn, as_of=date(2026, 12, 8)) == {"FCX": {"RERUN"}}


def test_the_sweep_does_not_stamp_model_mix(convexity_db, tmp_path):
    provider = SyntheticChainProvider(as_of=AS_OF.date())
    rid = state.record_run(convexity_db, mode="TEST", equity=None, note="t")
    _sweep(convexity_db, PointInTimeCache(tmp_path / "c"), provider, run_id=rid)
    assert convexity_db.execute("SELECT model_mix FROM runs WHERE id = ?", (rid,)).fetchone()[0] is None
