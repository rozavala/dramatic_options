"""Brain-off NULL shadow book (T3 PR3b) — the forward "does the LLM layer add value?" control.

Covers: brain-off booking (every gate-passer), origin tagging (hand_seed vs sentinel), the
deterministic-cap parity held with the real book (slot reservation + per-name dedup), kill gating,
mark/exit + per-position realized-multiple, the tail report — and, the MERGE-BLOCKER, that the shadow
path can never reach the broker.
"""

from __future__ import annotations

import inspect
import re
from datetime import UTC, datetime
from pathlib import Path

from dramatic_options import risk, shadow_book, state
from dramatic_options.clock import FixedClock
from dramatic_options.convexity_data import StaticQuoteProvider, SyntheticChainProvider
from dramatic_options.themes import Theme

CLOCK = FixedClock(datetime(2026, 1, 2, tzinfo=UTC))
CONFIG = {
    "convexity_book": {"account_equity": 100_000.0, "book_fraction": 0.10,
                       "per_name_fraction": 0.01, "max_open_positions": 15},
    "convexity_gate": {"iv_rv_max": 1.2, "otm_skew_max_volpts": 10.0, "rv_window_days": 252,
                       "tenor_min_days": 180, "tenor_max_days": 365, "target_moneyness": 0.25},
    "convexity_exits": {"profit_take_multiple": 10.0, "time_stop_dte": 21, "min_close_bid": 0.05},
    "eligibility": {"live": {"min_option_open_interest": 50, "max_bid_ask_pct": 0.25}},
    "kill_rule": {"book_drawdown_halt": 0.20, "dry_months_halt": 9},
    "discovery": {"sentinel_max_slots": 6},
    "themes_path": "themes.json",
}


def _no_kill(monkeypatch):
    monkeypatch.delenv("KILL", raising=False)
    monkeypatch.setattr(risk, "KILL_FILE", Path("/nonexistent/KILL"))


def _provider():
    return SyntheticChainProvider(as_of=CLOCK.now().date())


def _book(conn, candidates, monkeypatch, config=CONFIG):
    _no_kill(monkeypatch)
    return shadow_book.run_shadow_cycle(config=config, conn=conn, clock=CLOCK,
                                        provider=_provider(), run_id=None, candidates=candidates)


def _insert_shadow(conn, *, contract="FCX261218C00080000", entry_pc=200.0, contracts=3,
                   expiry="2026-12-18", strike=80.0, kind="C", origin="hand_seed", symbol="FCX"):
    return state.record_shadow_position(
        conn, run_id=None, origin=origin, opened_at="2026-01-02T00:00:00+00:00", theme="t",
        symbol=symbol, direction="bullish", structure_kind=kind, contract_symbol=contract,
        expiry=expiry, strike=strike, dte=300, moneyness=0.25, contracts=contracts,
        entry_premium_per_contract=entry_pc, total_premium=entry_pc * contracts, entry_spot=45.0)


# ── brain-off booking ──────────────────────────────────────────────────────────────────────────

def test_brain_off_books_every_gate_passer_and_vetoes_rich(convexity_db, monkeypatch):
    # FCX cheap (clears the IV gate), NVDA rich (vetoed) — the shadow books FCX with NO council.
    res = _book(convexity_db, [Theme("copper", "FCX", "bullish", "cheap"),
                               Theme("hype", "NVDA", "bullish", "rich")], monkeypatch)
    assert res.booked == 1
    assert res.vetoed == 1
    rows = state.open_shadow_positions(convexity_db)
    assert len(rows) == 1 and rows[0]["symbol"] == "FCX"
    assert rows[0]["total_premium"] > 0


def test_origin_tagging_hand_seed_vs_sentinel(convexity_db, monkeypatch):
    res = _book(convexity_db, [
        Theme("copper", "FCX", "bullish", "cheap"),                                     # hand-seed
        Theme("ai_compute", "CCJ", "bullish", "", source="sentinel", sentinel_id=7),    # discovered
    ], monkeypatch)
    assert res.booked == 2
    assert res.by_origin == {"hand_seed": 1, "sentinel": 1}
    origins = {r["symbol"]: r["origin"] for r in state.open_shadow_positions(convexity_db)}
    assert origins["FCX"] == "hand_seed"
    assert origins["CCJ"] == "sentinel"


def test_dedup_does_not_double_book(convexity_db, monkeypatch):
    cands = [Theme("copper", "FCX", "bullish", "cheap")]
    _book(convexity_db, cands, monkeypatch)
    res2 = _book(convexity_db, cands, monkeypatch)  # FCX already open → skipped
    assert res2.booked == 0 and res2.skipped == 1
    assert state.count_open_shadow_positions(convexity_db) == 1


def test_inactive_candidate_skipped(convexity_db, monkeypatch):
    res = _book(convexity_db, [Theme("copper", "FCX", "bullish", "cheap", active=False)], monkeypatch)
    assert res.booked == 0


def test_sentinel_slot_reservation_caps_discovered_origin(convexity_db, monkeypatch):
    # The SAME deterministic cap the real book applies (only the council include/exclude is removed):
    # at most sentinel_max_slots discovered positions.
    cfg = {**CONFIG, "discovery": {"sentinel_max_slots": 1}}
    res = _book(convexity_db, [
        Theme("t", "CCJ", "bullish", "", source="sentinel", sentinel_id=1),
        Theme("t", "VRT", "bullish", "", source="sentinel", sentinel_id=2),
    ], monkeypatch, config=cfg)
    assert state.count_open_shadow_sentinel_positions(convexity_db) == 1
    assert res.booked == 1


def test_kill_switch_halts_shadow_booking(convexity_db, monkeypatch):
    monkeypatch.setenv("KILL", "1")
    res = shadow_book.run_shadow_cycle(config=CONFIG, conn=convexity_db, clock=CLOCK,
                                       provider=_provider(),
                                       candidates=[Theme("c", "FCX", "bullish", "x")])
    assert res.halted is True and res.booked == 0
    assert state.count_open_shadow_positions(convexity_db) == 0


# ── mark + deterministic exits (per-position realized multiple) ──────────────────────────────────

def test_profit_take_closes_at_multiple_with_realized_multiple(convexity_db):
    pid = _insert_shadow(convexity_db, entry_pc=200.0, contracts=3)  # $200/ct entry → $600 total
    qp = StaticQuoteProvider({"FCX261218C00080000": 25.0})           # $2500/ct ≥ 10×$200 → take
    res = shadow_book.mark_shadow_positions(conn=convexity_db, clock=CLOCK, quote_provider=qp, config=CONFIG)
    assert res.profit_taken == 1 and res.closed == 1
    row = convexity_db.execute(
        "SELECT status, realized_multiple FROM shadow_positions WHERE id = ?", (pid,)).fetchone()
    assert row["status"] == "closed"
    assert abs(row["realized_multiple"] - 12.5) < 1e-6  # (25*100*3)/600


def test_below_threshold_marks_only(convexity_db):
    pid = _insert_shadow(convexity_db, entry_pc=200.0)
    qp = StaticQuoteProvider({"FCX261218C00080000": 5.0})  # $500/ct < 10×$200 → mark only
    res = shadow_book.mark_shadow_positions(conn=convexity_db, clock=CLOCK, quote_provider=qp, config=CONFIG)
    assert res.marked == 1 and res.closed == 0
    row = convexity_db.execute("SELECT status, mark FROM shadow_positions WHERE id = ?", (pid,)).fetchone()
    assert row["status"] == "open" and abs(row["mark"] - 5.0) < 1e-9


def test_time_stop_closes_near_expiry(convexity_db):
    pid = _insert_shadow(convexity_db, expiry="2026-01-15")  # ~13 DTE from 2026-01-02 ≤ 21
    qp = StaticQuoteProvider({"FCX261218C00080000": 1.0})
    res = shadow_book.mark_shadow_positions(conn=convexity_db, clock=CLOCK, quote_provider=qp, config=CONFIG)
    assert res.time_stopped == 1 and res.closed == 1
    assert convexity_db.execute("SELECT status FROM shadow_positions WHERE id = ?", (pid,)).fetchone()[
        "status"] == "closed"


def test_expiry_closes_at_intrinsic_worthless_otm(convexity_db):
    pid = _insert_shadow(convexity_db, expiry="2025-12-31", entry_pc=200.0, contracts=2)
    res = shadow_book.mark_shadow_positions(conn=convexity_db, clock=CLOCK,
                                            quote_provider=StaticQuoteProvider({}), config=CONFIG,
                                            underlying_price_of=lambda s: 45.0)  # 45 < 80 strike → 0
    assert res.expired == 1 and res.closed == 1
    row = convexity_db.execute(
        "SELECT status, realized_multiple FROM shadow_positions WHERE id = ?", (pid,)).fetchone()
    assert row["status"] == "closed" and row["realized_multiple"] == 0.0


def test_unmarked_when_no_quote(convexity_db):
    _insert_shadow(convexity_db)
    res = shadow_book.mark_shadow_positions(conn=convexity_db, clock=CLOCK,
                                            quote_provider=StaticQuoteProvider({}), config=CONFIG)
    assert res.unmarked == 1 and res.closed == 0


# ── tail scoring (refinement #2 — per-position tail, decomposed by origin) ───────────────────────

def test_tail_report_decomposes_by_origin(convexity_db):
    for mult, origin, sym in [(0.0, "sentinel", "AAA"), (12.0, "sentinel", "BBB"), (2.0, "hand_seed", "CCC")]:
        pid = _insert_shadow(convexity_db, origin=origin, symbol=sym, contract=f"{sym}X")
        state.close_shadow_position(convexity_db, pid, exit_price=0.0, realized_pnl=0.0,
                                    realized_multiple=mult, reason="expiry", as_of="2026-06-01T00:00:00+00:00")
    rep = shadow_book.tail_report(convexity_db)
    assert rep["shadow_sentinel"]["n"] == 2 and rep["shadow_sentinel"]["max"] == 12.0
    assert rep["shadow_hand_seed"]["n"] == 1
    assert rep["shadow_all"]["n"] == 3


def test_tail_summary_pure():
    assert shadow_book.tail_summary([])["n"] == 0
    s = shadow_book.tail_summary([1.0, 2.0, 3.0, 100.0])
    assert s["n"] == 4 and s["max"] == 100.0 and s["mean"] == 26.5


# ── MERGE-BLOCKER: the shadow path can never reach the broker ─────────────────────────────────────

def test_shadow_path_never_touches_the_broker(convexity_db, monkeypatch):
    """A shadow→live-broker bug is the one genuinely dangerous failure in this subsystem. Assert it
    structurally three ways + behaviorally."""
    src = Path(shadow_book.__file__).read_text()
    # (1) no broker import — this module owns none (transitive imports by reused helpers are fine).
    assert not re.search(r"^\s*(from\s+broker\s+import|import\s+broker)\b", src, re.M)
    # (2) no submit / broker construction / order minting anywhere in the source.
    for forbidden in ("submit_paper", "AlpacaPaperBroker", "PaperBroker",
                      "make_client_order_id", "SELL_TO_CLOSE", ".submit("):
        assert forbidden not in src, f"shadow_book must not reference {forbidden!r}"
    # (3) no 'broker' parameter on any entry point — it structurally cannot be handed one.
    for fn in (shadow_book.run_shadow_cycle, shadow_book.mark_shadow_positions, shadow_book._eval_and_book):
        assert "broker" not in inspect.signature(fn).parameters, fn.__name__
    # (4) behavioral: a full book + mark cycle runs to completion with NO broker in scope.
    _no_kill(monkeypatch)
    booked = shadow_book.run_shadow_cycle(config=CONFIG, conn=convexity_db, clock=CLOCK,
                                          provider=_provider(),
                                          candidates=[Theme("copper", "FCX", "bullish", "cheap")])
    assert booked.booked == 1
    shadow_book.mark_shadow_positions(conn=convexity_db, clock=CLOCK, quote_provider=_provider(),
                                      config=CONFIG, underlying_price_of=_provider().underlying_price)


# ── fail-soft: a shadow bug must never halt the real trade cycle ─────────────────────────────────

def test_orchestrator_shadow_failure_is_non_fatal(monkeypatch):
    from dramatic_options import orchestrator

    monkeypatch.delenv("KILL", raising=False)

    def _boom(**kwargs):
        raise RuntimeError("shadow boom")

    monkeypatch.setattr(shadow_book, "run_shadow_cycle", _boom)
    monkeypatch.setattr(shadow_book, "mark_shadow_positions", _boom)
    assert orchestrator.run_once(demo=True) == 0  # the real demo cycle still completes (exit 0)


# ── cluster exposure cap parity with the real book (PREREG §5 amendment) ─────────────────────────

def _cluster_cfg(cluster_fraction, members, name="power"):
    return {**CONFIG, "convexity_book": {**CONFIG["convexity_book"],
                                         "cluster_fraction": cluster_fraction,
                                         "clusters": {name: list(members)}}}


def test_cluster_cap_binds_identically_in_the_shadow_book(convexity_db, monkeypatch):
    # The SAME deterministic cap the real book applies — only the council selection differs. A full
    # cluster blocks a mate. (Shadow books 'open' immediately, so the open-only basis counts mates.)
    cfg = _cluster_cfg(0.01, ["FCX", "AAA"])  # cap = $1000
    _insert_shadow(convexity_db, symbol="AAA", contract="AAAx", entry_pc=1000.0, contracts=1)
    res = _book(convexity_db, [Theme("c", "FCX", "bullish", "cheap")], monkeypatch, config=cfg)
    assert res.booked == 0                                          # FCX cluster-capped
    assert state.count_open_shadow_positions(convexity_db) == 1     # only the pre-seeded AAA


def test_shadow_cluster_cap_admits_only_a_subset(convexity_db, monkeypatch):
    # Brain-off books EVERY gate-passer, but still under the cluster cap (held identical to the real book).
    cfg = _cluster_cfg(0.02, ["AAA", "BBB", "CCC", "DDD"])  # cap = $2000 ≈ 2 names
    cands = [Theme(f"t_{s}", s, "bullish", "cheap") for s in ["AAA", "BBB", "CCC", "DDD"]]
    res = _book(convexity_db, cands, monkeypatch, config=cfg)
    assert 0 < res.booked < 4
    assert state.shadow_cluster_open_premium(
        convexity_db, {"AAA", "BBB", "CCC", "DDD"}) <= 100_000.0 * 0.02 + 1e-6
