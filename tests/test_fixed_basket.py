"""No-gate / fixed-basket NULL book 3A (PREREG_FIXED_BASKET_NULL.md, PR2a) — gate-off over the union.

Covers: gate-off books a gate-REJECTED name the gated shadow book vetoes (the point — `shadow − 3A` is
the gate test); the BOOKED superset over the union where the cap doesn't bind (R3 — it only holds
there); the cap-ON cluster cap + slot reservation are respected (3A holds the full frame); mark/exits +
the realized-multiple tail; kill gating; and the MERGE-BLOCKER never-broker invariant + orchestrator
fail-soft.
"""

from __future__ import annotations

import inspect
import re
from datetime import UTC, datetime
from pathlib import Path

import discovery
import fixed_basket
import risk
import shadow_book
import state
from clock import FixedClock
from convexity_data import StaticQuoteProvider, SyntheticChainProvider
from discovery import MarkerParams
from themes import Theme

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
    "fixed_basket": {"enabled": True},
    "themes_path": "themes.json",
}
BOOK = fixed_basket.BOOK_UNION_NOGATE


def _no_kill(monkeypatch):
    monkeypatch.delenv("KILL", raising=False)
    monkeypatch.setattr(risk, "KILL_FILE", Path("/nonexistent/KILL"))


def _provider():
    return SyntheticChainProvider(as_of=CLOCK.now().date())


def _run_3a(conn, candidates, monkeypatch, config=CONFIG):
    _no_kill(monkeypatch)
    return fixed_basket.run_fixed_basket_3a_cycle(config=config, conn=conn, clock=CLOCK,
                                                  provider=_provider(), run_id=None, candidates=candidates)


def _cfg_cluster(fraction, members, name="power"):
    return {**CONFIG, "convexity_book": {**CONFIG["convexity_book"], "cluster_fraction": fraction,
                                         "clusters": {name: list(members)}}}


def _insert_fb(conn, *, symbol, total_premium, origin="hand_seed", contract=None, expiry="2026-12-18",
               strike=80.0, kind="C", contracts=1, book=BOOK):
    return state.record_fixed_basket_position(
        conn, run_id=None, book=book, origin=origin, opened_at="2026-01-02T00:00:00+00:00", theme="t",
        symbol=symbol, direction="bullish", structure_kind=kind, contract_symbol=contract or f"{symbol}X",
        expiry=expiry, strike=strike, dte=300, moneyness=0.25, contracts=contracts,
        entry_premium_per_contract=total_premium / contracts, total_premium=total_premium, entry_spot=45.0)


# ── the point: gate-off books a name the gate REJECTS ───────────────────────────────────────────

def test_3a_books_a_gate_rejected_name_the_shadow_vetoes(convexity_db, monkeypatch):
    # NVDA is rich (iv/rv 1.73>1.2, skew 17vp>10) → the gated shadow book vetoes it; 3A (gate OFF) books it.
    cands = [Theme("copper", "FCX", "bullish", "cheap"), Theme("hype", "NVDA", "bullish", "rich")]
    res = _run_3a(convexity_db, cands, monkeypatch)
    booked = {r["symbol"] for r in state.open_fixed_basket_positions(convexity_db, BOOK)}
    assert booked == {"FCX", "NVDA"} and res.booked == 2          # gate-off books BOTH


def test_3a_booked_is_a_superset_of_the_shadow_when_cap_unconstrained(convexity_db, monkeypatch):
    # R3: the BOOKED superset holds only where the cluster cap doesn't bind. Same union, gate-on vs -off.
    _no_kill(monkeypatch)
    cands = [Theme("copper", "FCX", "bullish", "cheap"), Theme("hype", "NVDA", "bullish", "rich")]
    shadow_book.run_shadow_cycle(config=CONFIG, conn=convexity_db, clock=CLOCK, provider=_provider(),
                                 candidates=cands)
    shadow_syms = state.shadow_open_symbols(convexity_db)
    _run_3a(convexity_db, cands, monkeypatch)
    nogate_syms = state.fixed_basket_open_symbols(convexity_db, BOOK)
    assert shadow_syms <= nogate_syms                            # gate-off ⊇ gate-on (booked)
    assert nogate_syms - shadow_syms == {"NVDA"}                 # the strict addition = the gate-rejected name


# ── cap-ON: 3A holds the FULL frozen frame ──────────────────────────────────────────────────────

def test_3a_respects_the_cluster_cap(convexity_db, monkeypatch):
    cfg = _cfg_cluster(0.01, ["FCX", "AAA"])                     # cap = $1000
    _insert_fb(convexity_db, symbol="AAA", total_premium=1000.0)   # cluster already full in the 3A book
    res = _run_3a(convexity_db, [Theme("c", "FCX", "bullish", "cheap")], monkeypatch, config=cfg)
    assert res.booked == 0                                       # FCX cluster-capped (cap-ON like real/shadow)
    assert res.veto_reasons == {"cluster_cap": 1}                # and the veto is attributable
    assert state.fixed_basket_open_symbols(convexity_db, BOOK) == {"AAA"}


def test_3a_null_slot_reservation_applies_when_set(convexity_db, monkeypatch):
    # FBN §4 amendment (2026-07-02): the null-book knob, symmetric with the shadow book.
    cfg = {**CONFIG, "discovery": {"null_sentinel_max_slots": 1}}
    res = _run_3a(convexity_db, [
        Theme("t", "CCJ", "bullish", "", source="sentinel", sentinel_id=1),
        Theme("t", "VRT", "bullish", "", source="sentinel", sentinel_id=2),
    ], monkeypatch, config=cfg)
    assert state.count_open_fixed_basket_sentinel_positions(convexity_db, BOOK) == 1 and res.booked == 1
    assert res.veto_reasons == {"sentinel_slots": 1}


def test_3a_real_book_slot_key_does_not_cap(convexity_db, monkeypatch):
    # FBN §4 amendment (2026-07-02): symmetric relief — sentinel_max_slots no longer censors 3A.
    cfg = {**CONFIG, "discovery": {"sentinel_max_slots": 1}}
    res = _run_3a(convexity_db, [
        Theme("t", "CCJ", "bullish", "", source="sentinel", sentinel_id=1),
        Theme("t", "VRT", "bullish", "", source="sentinel", sentinel_id=2),
    ], monkeypatch, config=cfg)
    assert res.booked == 2 and res.veto_reasons == {}
    assert state.count_open_fixed_basket_sentinel_positions(convexity_db, BOOK) == 2


def test_3a_null_book_fraction_knob_relieves_the_null_book_cap(convexity_db, monkeypatch):
    # Symmetric with the shadow book (the shadow−3A contrast stays clean).
    _insert_fb(convexity_db, symbol="AAA", total_premium=9900.0)  # $9,900 of the $10k cap
    cand = [Theme("t", "CCJ", "bullish", "", source="sentinel", sentinel_id=1)]
    res = _run_3a(convexity_db, cand, monkeypatch)
    assert res.booked == 0 and res.veto_reasons == {"sizing": 1}
    cfg = {**CONFIG, "discovery": {"null_book_fraction": 1.0}}
    res2 = _run_3a(convexity_db, cand, monkeypatch, config=cfg)
    assert res2.booked == 1


def test_3a_null_cluster_fraction_zero_disables_the_null_cluster_cap(convexity_db, monkeypatch):
    cfg = _cfg_cluster(0.01, ["FCX", "AAA"])
    _insert_fb(convexity_db, symbol="AAA", total_premium=1000.0)  # cluster full in the 3A book
    res = _run_3a(convexity_db, [Theme("c", "FCX", "bullish", "cheap")], monkeypatch, config=cfg)
    assert res.booked == 0 and res.veto_reasons == {"cluster_cap": 1}
    cfg2 = {**cfg, "discovery": {"null_cluster_fraction": 0}}
    res2 = _run_3a(convexity_db, [Theme("c", "FCX", "bullish", "cheap")], monkeypatch, config=cfg2)
    assert res2.booked == 1


def test_kill_switch_halts_3a(convexity_db, monkeypatch):
    monkeypatch.setenv("KILL", "1")
    res = fixed_basket.run_fixed_basket_3a_cycle(config=CONFIG, conn=convexity_db, clock=CLOCK,
                                                 provider=_provider(),
                                                 candidates=[Theme("c", "FCX", "bullish", "x")])
    assert res.halted is True and res.booked == 0


# ── mark + deterministic exits + the tail ───────────────────────────────────────────────────────

def test_3a_profit_take_records_realized_multiple(convexity_db):
    pid = _insert_fb(convexity_db, symbol="FCX", contract="FCX261218C00080000", total_premium=600.0, contracts=3)
    qp = StaticQuoteProvider({"FCX261218C00080000": 25.0})       # $2500/ct ≥ 10×$200 → profit-take
    res = fixed_basket.mark_fixed_basket_positions(conn=convexity_db, clock=CLOCK, quote_provider=qp, config=CONFIG)
    assert res.profit_taken == 1 and res.closed == 1
    row = convexity_db.execute("SELECT status, realized_multiple FROM fixed_basket_positions WHERE id=?",
                               (pid,)).fetchone()
    assert row["status"] == "closed" and abs(row["realized_multiple"] - 12.5) < 1e-6   # (25*100*3)/600


def test_3a_tail_report_surfaces_the_book(convexity_db):
    pid = _insert_fb(convexity_db, symbol="AAA", contract="AAAX", total_premium=200.0)
    state.close_fixed_basket_position(convexity_db, pid, exit_price=0.0, realized_pnl=0.0,
                                      realized_multiple=8.0, reason="expiry", as_of="2026-06-01T00:00:00+00:00")
    rep = fixed_basket.tail_report(convexity_db)
    assert rep[f"nogate_{BOOK}"]["n"] == 1 and rep[f"nogate_{BOOK}"]["max"] == 8.0


# ── MERGE-BLOCKER: never the broker + orchestrator fail-soft ─────────────────────────────────────

def test_fixed_basket_never_touches_the_broker(convexity_db, monkeypatch):
    src = Path(fixed_basket.__file__).read_text()
    assert not re.search(r"^\s*(from\s+broker\s+import|import\s+broker)\b", src, re.M)
    for forbidden in ("submit_paper", "AlpacaPaperBroker", "AlpacaLiveBroker", "PaperBroker",
                      "make_client_order_id", "SELL_TO_CLOSE", ".submit("):
        assert forbidden not in src, f"fixed_basket must not reference {forbidden!r}"
    for fn in (fixed_basket.run_fixed_basket_3a_cycle, fixed_basket.mark_fixed_basket_positions,
               fixed_basket._eval_and_book_nogate):
        assert "broker" not in inspect.signature(fn).parameters, fn.__name__
    _no_kill(monkeypatch)
    fixed_basket.run_fixed_basket_3a_cycle(config=CONFIG, conn=convexity_db, clock=CLOCK,
                                           provider=_provider(),
                                           candidates=[Theme("copper", "FCX", "bullish", "cheap")])


def test_orchestrator_fixed_basket_failure_is_non_fatal(monkeypatch):
    import orchestrator
    monkeypatch.delenv("KILL", raising=False)

    def _boom(**kwargs):
        raise RuntimeError("3A boom")

    monkeypatch.setattr(fixed_basket, "run_fixed_basket_3a_cycle", _boom)
    monkeypatch.setattr(fixed_basket, "mark_fixed_basket_positions", _boom)
    assert orchestrator.run_once(demo=True) == 0                 # the real demo cycle still completes (exit 0)


# ── book 3B: whole basket, gate-OFF, EQUAL-WEIGHT, MOTION-derived direction ──────────────────────

BOOK3B = fixed_basket.BOOK_BASKET_NOGATE
_MARKERS = {"mom_lookback": 252, "mom_skip": 21, "rv_recent": 21, "rv_base": 252, "adv_window": 20,
            "mom_floor": 0.15, "rv_slope_floor": 0.25, "min_price": 3.0, "min_adv_usd": 3000000.0}


def _market(symbols, movers=()):
    return discovery.synthetic_market(symbols, CLOCK.now(), movers=movers)


def _down_market(symbols, down):
    import tempfile
    from datetime import timedelta

    from data.cache import PointInTimeCache
    from data.market import MarketData
    n, as_of = 320, CLOCK.now()
    start = as_of - timedelta(days=n)
    cache = PointInTimeCache(tempfile.mkdtemp(prefix="fb_down_"))
    dn = {s.upper() for s in down}
    for sym in symbols:
        s = sym.upper()
        closes = [20.0 - 10.0 * i / (n - 1) for i in range(n)] if s in dn else [10.0] * n
        bars = [{"ts": (start + timedelta(days=i)).isoformat(), "open": c, "high": c, "low": c,
                 "close": c, "volume": 2_000_000} for i, c in enumerate(closes)]
        cache.write("bars", s, bars, coverage_from=start - timedelta(days=2),
                    coverage_through=as_of + timedelta(days=2))
    return MarketData(cache, client=None, fetch_start=start, fetch_end=as_of + timedelta(days=2))


def _basket_cfg(themes, **book):
    cfg = {**CONFIG, "universe": {"themes": themes},
           "discovery": {**CONFIG["discovery"], "markers": dict(_MARKERS)}}
    if book:
        cfg["convexity_book"] = {**CONFIG["convexity_book"], **book}
    return cfg


def _run_3b(conn, config, market, monkeypatch, benchmark="SPY"):
    _no_kill(monkeypatch)
    return fixed_basket.run_fixed_basket_3b_cycle(
        config=config, conn=conn, clock=CLOCK, provider=_provider(), market=market,
        benchmark=benchmark, params=MarkerParams(**dict(config["discovery"]["markers"])), run_id=None)


def test_3b_books_the_whole_basket_equal_weight(convexity_db, monkeypatch):
    cfg = _basket_cfg({"t": ["AAA", "BBB", "CCC"]})
    res = _run_3b(convexity_db, cfg, _market(["AAA", "BBB", "CCC", "SPY"], movers=["AAA", "BBB", "CCC"]), monkeypatch)
    assert res.booked == 3 and res.errors == 0
    rows = state.open_fixed_basket_positions(convexity_db, BOOK3B)
    assert {r["symbol"] for r in rows} == {"AAA", "BBB", "CCC"}
    assert all(r["direction"] == "bullish" and r["structure_kind"] == "C" for r in rows)   # up-movers → calls


def test_3b_universe_is_the_basket_not_the_union(convexity_db, monkeypatch):
    # 3B reads config.universe.themes (NOT themes.json / the council union) — books a name no theme/sentinel has.
    res = _run_3b(convexity_db, _basket_cfg({"t": ["ZZZ"]}), _market(["ZZZ", "SPY"]), monkeypatch)
    assert res.booked == 1 and state.fixed_basket_open_symbols(convexity_db, BOOK3B) == {"ZZZ"}


def test_3b_motion_derived_bearish_on_a_down_mover(convexity_db, monkeypatch):
    res = _run_3b(convexity_db, _basket_cfg({"t": ["DOWN"]}), _down_market(["DOWN", "SPY"], down=["DOWN"]), monkeypatch)
    assert res.booked == 1
    row = state.open_fixed_basket_positions(convexity_db, BOOK3B)[0]
    assert row["direction"] == "bearish" and row["structure_kind"] == "P"   # down-mover → puts


def test_3b_equal_weight_ignores_the_cluster_cap(convexity_db, monkeypatch):
    # 3B = the WHOLE basket, equal-weight, NO cluster truncation: a 3-name cluster ALL book (a cap-ON
    # book would cap it at 2 at cluster_fraction=0.02). This is *why* real−3B is the bundled read.
    cfg = _basket_cfg({"t": ["AAA", "BBB", "CCC"]}, cluster_fraction=0.02, clusters={"power": ["AAA", "BBB", "CCC"]})
    res = _run_3b(convexity_db, cfg, _market(["AAA", "BBB", "CCC", "SPY"]), monkeypatch)
    assert res.booked == 3   # all three despite the 0.02 (2-name) cluster cap — 3B doesn't truncate
