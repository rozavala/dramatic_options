"""Forward-only sentinel scoring (T3) — reference-return survivorship guard, multiple, NULL-safety."""

from datetime import UTC, datetime, timedelta

from dramatic_options import state
from dramatic_options.data.cache import PointInTimeCache
from dramatic_options.data.market import MarketData
from dramatic_options.sentinel_scoring import (
    reference_return_from_bars,
    resolve_due_references,
    resolve_reference,
    resolve_traded_sentinel,
)


def _daily(start, closes):
    d0 = datetime.fromisoformat(start).replace(tzinfo=UTC)
    return [{"ts": (d0 + timedelta(days=i)).isoformat(), "open": c, "high": c, "low": c,
             "close": c, "volume": 1_000_000} for i, c in enumerate(closes)]


def _md(tmp_path, series):  # series: sym -> (start_iso, closes)
    cache = PointInTimeCache(tmp_path)
    cov_from, cov_to = datetime(2025, 1, 1, tzinfo=UTC), datetime(2027, 1, 1, tzinfo=UTC)
    for sym, (start, closes) in series.items():
        cache.write("bars", sym, _daily(start, closes), coverage_from=cov_from, coverage_through=cov_to)
    return MarketData(cache, client=None, fetch_start=cov_from, fetch_end=cov_to)


# ── pure survivorship guard ─────────────────────────────────────────────────────────────────


def test_reference_return_horizon_vs_terminated_vs_unresolved():
    r, t = reference_return_from_bars(10.0, [11, 12, 13, 14, 15], 3, terminated=False)
    assert t == "horizon" and abs(r - (13 / 10 - 1)) < 1e-9
    # acquisition/delisting: series ends early → return to LAST bar, NOT None (don't clip the tail)
    r2, t2 = reference_return_from_bars(10.0, [12, 30], 5, terminated=True)
    assert t2 == "terminated" and abs(r2 - (30 / 10 - 1)) < 1e-9
    # too early + not terminated → genuinely unresolved (never fabricated)
    assert reference_return_from_bars(10.0, [11, 12], 5, terminated=False) == (None, None)
    assert reference_return_from_bars(None, [1, 2, 3], 1, terminated=True) == (None, None)


# ── traded resolution: direction + magnitude ──────────────────────────────────────────────────


def test_resolve_traded_outcome_brier_and_multiple():
    o, b, m = resolve_traded_sentinel(reason="profit_take_10x", direction="bullish",
                                      conviction="HIGH", entry_premium=100.0, realized_pnl=900.0)
    assert o == 1 and b is not None and abs(m - 10.0) < 1e-9   # 10× winner captured as magnitude
    o2, b2, m2 = resolve_traded_sentinel(reason="expiry", direction="bullish", conviction="HIGH",
                                         intrinsic=0.0, entry_premium=100.0, realized_pnl=-100.0)
    assert o2 == 0 and abs(m2 - 0.0) < 1e-9                    # total loss → multiple 0
    o3, b3, _ = resolve_traded_sentinel(reason="time_stop", direction="bullish", conviction="HIGH")
    assert o3 is None and b3 is None                          # no spot → unresolved, never fabricated


# ── reference resolution against real bars ─────────────────────────────────────────────────────


def test_resolve_reference_horizon_and_terminated(tmp_path):
    run = [10.0 + i * 0.5 for i in range(40)]                 # rises well past the horizon
    gone = [10, 10, 10, 10, 10, 10, 50, 50, 50]               # acquired pop, then series ends
    md = _md(tmp_path, {"RUN": ("2026-01-01", run), "GONE": ("2026-01-01", gone)})
    as_of = datetime(2026, 1, 6, tzinfo=UTC)
    now = datetime(2026, 4, 1, tzinfo=UTC)
    r, t = resolve_reference(md, "RUN", as_of, 10, now=now)
    assert t == "horizon" and r is not None and r > 0
    r2, t2 = resolve_reference(md, "GONE", as_of, 10, now=now)
    assert t2 == "terminated" and r2 is not None and abs(r2 - 4.0) < 1e-9  # jackpot, not NULL


def test_resolve_due_references_sweep(convexity_db, tmp_path):
    conn = convexity_db
    rising = [10.0 + i * 0.4 for i in range(120)]
    md = _md(tmp_path, {"RUN": ("2026-01-01", rising), "CTRL": ("2026-01-01", rising),
                        "RUN2": ("2026-01-01", rising)})

    def rec(symbol, as_of, **kw):
        return state.record_sentinel_candidate(conn, run_id=None, as_of=as_of, symbol=symbol,
                                                direction="bullish", basket="b",
                                                inflection_score=0.5, markers={}, **kw)

    old = rec("RUN", "2026-01-06T00:00:00+00:00")                        # due
    recent = rec("RUN2", "2026-03-25T00:00:00+00:00")                    # horizon not elapsed
    ctrl = rec("CTRL", "2026-01-06T00:00:00+00:00", kind="control", status="control")  # due
    traded = rec("TRADED", "2026-01-06T00:00:00+00:00")
    pid = state.record_council_proposal(conn, run_id=None, as_of="2026-01-06T00:00:00+00:00",
                                        theme="b", symbol="TRADED", direction="bullish",
                                        conviction="HIGH")
    state.link_sentinel_proposal(conn, traded, pid)   # traded → resolves at close, not via sweep

    n = resolve_due_references(conn, md, now=datetime(2026, 4, 1, tzinfo=UTC), horizon_days=10)
    assert n == 2                                                        # old + control only
    assert state.sentinel_by_id(conn, old)["reference_return"] is not None
    assert state.sentinel_by_id(conn, ctrl)["reference_return"] is not None
    assert state.sentinel_by_id(conn, recent)["reference_return"] is None   # not due
    assert state.sentinel_by_id(conn, traded)["reference_return"] is None   # traded → resolves at close
