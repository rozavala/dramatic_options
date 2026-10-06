"""SHARES descriptive null (PREREG_FIXED_BASKET_NULL §2/§5, PR2c) — offline.

Covers: booking the option-eligible basket equal-weight with the MOTION-derived direction; the
universe-agreement invariant (shares ⊇ 3B-booked + direction agrees); skip-and-count on a missing price;
the time-dedup; the report-time multi-horizon signed return + the §6 terminal-event guard + with/without
top-k; the two pinned caveats; and the MERGE-BLOCKER never-broker invariant.
"""

from __future__ import annotations

import inspect
import re
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import discovery
import fixed_basket
import risk
import shares_basket
import state
from clock import FixedClock
from convexity_data import SyntheticChainProvider
from data.cache import PointInTimeCache
from data.market import MarketData
from discovery import MarkerParams

CLOCK = FixedClock(datetime(2026, 1, 2, tzinfo=UTC))
_MARKERS = {"mom_lookback": 252, "mom_skip": 21, "rv_recent": 21, "rv_base": 252, "adv_window": 20,
            "mom_floor": 0.15, "rv_slope_floor": 0.25, "min_price": 3.0, "min_adv_usd": 3000000.0}
CONFIG = {
    "convexity_book": {"account_equity": 100_000.0, "book_fraction": 0.10, "per_name_fraction": 0.01,
                       "max_open_positions": 15},
    "convexity_gate": {"tenor_min_days": 180, "tenor_max_days": 365, "target_moneyness": 0.25},
    "eligibility": {"live": {"min_option_open_interest": 50, "max_bid_ask_pct": 0.25}},
    "kill_rule": {"book_drawdown_halt": 0.20, "dry_months_halt": 9},
    "discovery": {"sentinel_max_slots": 6, "markers": dict(_MARKERS)},
    "shares_basket": {"enabled": True, "horizons": [180, 270, 365]},
    "themes_path": "themes.json",
}


def _no_kill(monkeypatch):
    monkeypatch.delenv("KILL", raising=False)
    monkeypatch.setattr(risk, "KILL_FILE", Path("/nonexistent/KILL"))


def _provider():
    return SyntheticChainProvider(as_of=CLOCK.now().date())


def _market(symbols, movers=()):
    return discovery.synthetic_market(symbols, CLOCK.now(), movers=movers)


def _cfg(themes):
    return {**CONFIG, "universe": {"themes": themes}}


def _params():
    return MarkerParams(**dict(_MARKERS))


def _run_shares(conn, config, market, monkeypatch, *, provider=None, benchmark="SPY"):
    _no_kill(monkeypatch)
    return shares_basket.run_shares_basket_cycle(
        config=config, conn=conn, clock=CLOCK, provider=provider or _provider(), market=market,
        benchmark=benchmark, params=_params(), run_id=None)


def _fwd_market(closes_by_symbol: dict, start: datetime) -> MarketData:
    """A MarketData whose cache carries a forward daily bar series per symbol from ``start``."""
    cache = PointInTimeCache(tempfile.mkdtemp(prefix="shares_fwd_"))
    last = start
    for sym, closes in closes_by_symbol.items():
        bars = [{"ts": (start + timedelta(days=i)).isoformat(), "open": c, "high": c, "low": c,
                 "close": c, "volume": 2_000_000} for i, c in enumerate(closes)]
        last = start + timedelta(days=len(closes) - 1)
        cache.write("bars", sym.upper(), bars, coverage_from=start - timedelta(days=2),
                    coverage_through=last + timedelta(days=2))
    return MarketData(cache, client=None, fetch_start=start - timedelta(days=2), fetch_end=last)


# ── booking ──────────────────────────────────────────────────────────────────

def test_shares_books_eligible_basket_equal_weight(convexity_db, monkeypatch):
    res = _run_shares(convexity_db, _cfg({"t": ["AAA", "BBB", "CCC"]}),
                      _market(["AAA", "BBB", "CCC", "SPY"], movers=["AAA", "BBB", "CCC"]), monkeypatch)
    assert res.booked == 3 and res.errors == 0
    rows = state.all_shares_positions(convexity_db)
    assert {r["symbol"] for r in rows} == {"AAA", "BBB", "CCC"}
    assert all(r["direction"] == "bullish" and r["entry_spot"] > 0 for r in rows)   # up-movers → bullish


def test_shares_universe_is_superset_of_3b_and_direction_agrees(convexity_db, monkeypatch):
    cfg = _cfg({"t": ["AAA", "BBB", "CCC"]})
    market = _market(["AAA", "BBB", "CCC", "SPY"], movers=["AAA", "BBB"])
    _no_kill(monkeypatch)
    fixed_basket.run_fixed_basket_3b_cycle(config=cfg, conn=convexity_db, clock=CLOCK, provider=_provider(),
                                           market=market, benchmark="SPY", params=_params(), run_id=None)
    shares_basket.run_shares_basket_cycle(config=cfg, conn=convexity_db, clock=CLOCK, provider=_provider(),
                                          market=market, benchmark="SPY", params=_params(), run_id=None)
    b3b = {r["symbol"]: r["direction"]
           for r in state.open_fixed_basket_positions(convexity_db, fixed_basket.BOOK_BASKET_NOGATE)}
    sh = {r["symbol"]: r["direction"] for r in state.all_shares_positions(convexity_db)}
    assert set(sh) >= set(b3b) and b3b                         # shares ⊇ 3B (3B also needs sizing ≥ 1)
    assert all(sh[s] == b3b[s] for s in b3b)                   # same MOTION-derived direction


def test_shares_skips_missing_price_no_degenerate_row(convexity_db, monkeypatch):
    class _NoPrice(SyntheticChainProvider):
        def underlying_price(self, sym):
            return None if sym == "AAA" else super().underlying_price(sym)

    res = _run_shares(convexity_db, _cfg({"t": ["AAA"]}), _market(["AAA", "SPY"]), monkeypatch,
                      provider=_NoPrice(as_of=CLOCK.now().date()))
    assert res.booked == 0 and res.skipped == 1 and state.all_shares_positions(convexity_db) == []


def test_shares_time_dedups_within_horizon(convexity_db, monkeypatch):
    cfg = _cfg({"t": ["AAA"]})
    mkt = _market(["AAA", "SPY"], movers=["AAA"])
    assert _run_shares(convexity_db, cfg, mkt, monkeypatch).booked == 1
    res2 = _run_shares(convexity_db, cfg, mkt, monkeypatch)                 # same week → dedup
    assert res2.booked == 0 and res2.skipped == 1
    assert len(state.all_shares_positions(convexity_db)) == 1


def test_kill_switch_halts_shares(convexity_db, monkeypatch):
    monkeypatch.setattr(risk, "KILL_FILE", Path(__file__))                  # exists → kill active
    res = shares_basket.run_shares_basket_cycle(
        config=_cfg({"t": ["AAA"]}), conn=convexity_db, clock=CLOCK, provider=_provider(),
        market=_market(["AAA", "SPY"]), benchmark="SPY", params=_params(), run_id=None)
    assert res.halted and res.booked == 0 and state.all_shares_positions(convexity_db) == []


# ── report-time, multi-horizon signed return + the §6 terminal guard ─────────────────────────────

def test_report_signs_by_direction(convexity_db):
    start = CLOCK.now()
    # AAA rises 100→150 over 400 bars; bar[179] ≈ 100 + 50*179/399 ≈ 122.4 → +0.224 at h180.
    closes = [100.0 + 50.0 * i / 399 for i in range(400)]
    state.record_shares_position(convexity_db, run_id=None, basket="t", symbol="AAA", direction="bullish",
                                 entry_spot=100.0, entry_at=start.isoformat())
    state.record_shares_position(convexity_db, run_id=None, basket="t", symbol="BBB", direction="bearish",
                                 entry_spot=100.0, entry_at=start.isoformat())
    mkt = _fwd_market({"AAA": closes, "BBB": closes}, start)
    rep = shares_basket.shares_return_report(convexity_db, mkt, now=start + timedelta(days=700),
                                             horizons=[180])
    h = rep["horizons"]["h180"]["full"]
    assert h["n"] == 2
    assert h["max"] > 0.2 and h["min"] < -0.2                  # bullish-on-up → +, bearish-on-up → −
    assert rep["caveats"] and len(rep["caveats"]) == 2         # both pinned caveats present


def test_report_terminal_guard_and_unresolved(convexity_db):
    start = CLOCK.now()
    # Series TERMINATES at day 220 (a buyout/delist): visible at h180 (horizon), terminated at h270/h365.
    closes = [100.0 + 60.0 * i / 219 for i in range(220)]      # 100→160 then ends
    state.record_shares_position(convexity_db, run_id=None, basket="t", symbol="AAA", direction="bullish",
                                 entry_spot=100.0, entry_at=start.isoformat())
    mkt = _fwd_market({"AAA": closes}, start)
    rep = shares_basket.shares_return_report(convexity_db, mkt, now=start + timedelta(days=800),
                                             horizons=[180, 270, 365])
    assert rep["horizons"]["h180"]["full"]["n"] == 1 and rep["horizons"]["h180"]["n_terminal"] == 0
    assert rep["horizons"]["h270"]["n_terminal"] == 1          # series ended early → terminal guard fired
    assert rep["horizons"]["h365"]["n_terminal"] == 1


def test_report_excludes_unresolved_no_fabrication(convexity_db):
    start = CLOCK.now()
    state.record_shares_position(convexity_db, run_id=None, basket="t", symbol="AAA", direction="bullish",
                                 entry_spot=100.0, entry_at=start.isoformat())
    mkt = _fwd_market({"AAA": [100.0 + i for i in range(50)]}, start)   # only 50 bars, not terminated
    rep = shares_basket.shares_return_report(convexity_db, mkt, now=start + timedelta(days=60),
                                             horizons=[180])
    assert rep["horizons"]["h180"]["full"]["n"] == 0           # horizon not elapsed → unresolved, never faked


def test_report_with_and_without_top_k(convexity_db):
    start = CLOCK.now()
    syms = {f"S{i}": [100.0, 101.0] for i in range(5)}         # 5 flat-ish names
    syms["BUYOUT"] = [100.0] + [300.0]                          # one 3x event-name (dominates the tail)
    for s in syms:
        state.record_shares_position(convexity_db, run_id=None, basket="t", symbol=s, direction="bullish",
                                     entry_spot=100.0, entry_at=start.isoformat())
    mkt = _fwd_market(syms, start)
    rep = shares_basket.shares_return_report(convexity_db, mkt, now=start + timedelta(days=800), horizons=[1])
    full, ex = rep["horizons"]["h1"]["full"], rep["horizons"]["h1"]["ex_top1"]
    assert full["n"] == 6 and ex["n"] == 5                     # top-1 (the buyout) dropped
    assert full["max"] > 1.5 and ex["max"] < 0.5              # the robust read isn't carried by one event


# ── never-broker (MERGE BLOCKER) ─────────────────────────────────────────────

def test_shares_basket_never_touches_the_broker(convexity_db, monkeypatch):
    src = Path(shares_basket.__file__).read_text()
    assert not re.search(r"^\s*(from\s+broker\s+import|import\s+broker)\b", src, re.M)
    for forbidden in ("submit_paper", "AlpacaPaperBroker", "PaperBroker", "make_client_order_id",
                      "SELL_TO_CLOSE", ".submit("):
        assert forbidden not in src, f"shares_basket must not reference {forbidden!r}"
    for fn in (shares_basket.run_shares_basket_cycle, shares_basket._eval_and_book_shares,
               shares_basket.shares_return_report):
        assert "broker" not in inspect.signature(fn).parameters, fn.__name__
    # A booking creates ONLY a shares_positions row (no broker, no other table touched).
    _run_shares(convexity_db, _cfg({"t": ["AAA"]}), _market(["AAA", "SPY"], movers=["AAA"]), monkeypatch)
    assert len(state.all_shares_positions(convexity_db)) == 1
