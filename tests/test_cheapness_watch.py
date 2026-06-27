"""Cheapness-watch (PREREG_CHEAPNESS_WATCH) — the §2.1 state machine + §7.1 JOINT trigger + N-floor.

The state machine (debounced break-onset / sustained-close-ignores-blip / never_cheap-distinct / the
marker_age SELECTION join / the N-floor) is the deciding measurement for finding #1 — tested over
hand-built daily histories. Window = CHEAP-days (§2's "days the gate stays cheap" / the enterable
measure); for a cheap onset that's ≥1, so the spec's "=0" is unreachable — `never_cheap` (onset not
cheap) is the 0-enterable state, kept distinct (the reason the operator pinned it).
"""

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import cheapness_watch as cw
import state

CONFIG = {
    "convexity_gate": {"iv_rv_max": 1.2, "otm_skew_max_volpts": 10.0, "rv_window_days": 252,
                       "tenor_min_days": 180, "tenor_max_days": 365, "target_moneyness": 0.25},
    "eligibility": {"live": {"min_option_open_interest": 50, "max_bid_ask_pct": 0.25}},
}

BELOW = (0.0, 0.0)    # below the fresh leg
FRESH = (0.3, 0.3)    # clears the fresh leg (rv_rising≥0.10 ∧ |mom_recent|≥0.20)


def _obs(conn, symbol, as_of, *, cheap, rv_rising, mom_recent, marker_age):
    with conn:
        conn.execute(
            "INSERT INTO cheapness_watch (run_id, as_of, symbol, cheap, rv_rising, mom_recent, "
            "marker_age_days, created_at) VALUES (NULL, ?, ?, ?, ?, ?, ?, datetime('now'))",
            (as_of, symbol, cheap, rv_rising, mom_recent, marker_age),
        )


def _series(conn, symbol, days, *, marker_age):
    """days: list of (rv_rising, mom_recent, cheap) per session, in order."""
    for i, (rvr, mom, cheap) in enumerate(days):
        _obs(conn, symbol, f"2026-03-{i + 1:02d}", cheap=cheap, rv_rising=rvr, mom_recent=mom,
             marker_age=marker_age)


def test_break_onset_is_debounced(convexity_db):
    # below, FRESH(onset), FRESH(continuation — NOT a new onset), below, FRESH(new onset) → 2 breaks
    _series(convexity_db, "X", [(*BELOW, 1), (*FRESH, 1), (*FRESH, 1), (*BELOW, 0), (*FRESH, 1)], marker_age=25)
    rep = cw.cheapness_report(convexity_db, n_qualify_floor=1)
    assert rep["n_breaks"] == 2   # the continuation session did NOT re-trigger; the re-cross did


def test_cheap_window_sustained_close_ignores_a_one_session_blip(convexity_db):
    # onset cheap, cheap, blip(not-cheap), cheap, not, not(SUSTAINED close) → cheap-days = 3 (blip excluded)
    _series(convexity_db, "X",
            [(*BELOW, 1), (*FRESH, 1), (*FRESH, 1), (*FRESH, 0), (*FRESH, 1), (*FRESH, 0), (*FRESH, 0)],
            marker_age=25)
    rep = cw.cheapness_report(convexity_db, n_qualify_floor=1)
    assert rep["n_breaks"] == 1 and rep["qualifying_windows"] == [3]  # the 1-session blip did not close it


def test_never_cheap_is_distinct_from_a_cheap_window(convexity_db):
    # onset NOT cheap → never_cheap (IV already popped); reported separately, NOT a 0-window, NOT qualifying
    _series(convexity_db, "X", [(*BELOW, 0), (*FRESH, 0), (*FRESH, 0)], marker_age=25)
    rep = cw.cheapness_report(convexity_db, n_qualify_floor=1)
    assert rep["n_breaks"] == 1 and rep["n_never_cheap"] == 1
    assert rep["n_qualifying"] == 0 and rep["qualifying_windows"] == []   # never_cheap never folded into the window


def test_joint_excludes_fresh_marker_breaks(convexity_db):
    # two identical catchable breaks: one on STALE markers (age 25 ≥ lag) → qualifies; one FRESH (age 3) → benign
    _series(convexity_db, "STALE", [(*BELOW, 1), (*FRESH, 1), (*FRESH, 0), (*FRESH, 0)], marker_age=25)
    _series(convexity_db, "FRESHM", [(*BELOW, 1), (*FRESH, 1), (*FRESH, 0), (*FRESH, 0)], marker_age=3)
    rep = cw.cheapness_report(convexity_db, staleness_lag_days=20.0, n_qualify_floor=1)
    assert rep["n_breaks"] == 2 and rep["n_qualifying"] == 1 and rep["n_fresh_marker"] == 1  # the §7.1 selection join


def test_insufficient_N_below_floor_then_verdict(convexity_db):
    # one qualifying break with a short window — below an N-floor of 3 → insufficient_N (no verdict off noise)
    _series(convexity_db, "X", [(*BELOW, 1), (*FRESH, 1), (*FRESH, 0), (*FRESH, 0)], marker_age=25)
    assert cw.cheapness_report(convexity_db, n_qualify_floor=3)["verdict"] == "insufficient_N"
    # add two more qualifying short-window breaks → floor met → fire (median window 2 < lag 20)
    _series(convexity_db, "Y", [(*BELOW, 1), (*FRESH, 1), (*FRESH, 0), (*FRESH, 0)], marker_age=25)
    _series(convexity_db, "Z", [(*BELOW, 1), (*FRESH, 1), (*FRESH, 0), (*FRESH, 0)], marker_age=25)
    rep = cw.cheapness_report(convexity_db, staleness_lag_days=20.0, n_qualify_floor=3)
    assert rep["n_qualifying"] == 3 and rep["verdict"] == "fire"


def test_record_cheapness_smoke_no_fetch(convexity_db):
    # NO-FETCH end-to-end: an active FCX sentinel + the synthetic provider → one recorded obs via the
    # real-extractor (select_structure + is_cheap_convexity), with marker_age from the 0016 stamp.
    from convexity_data import SyntheticChainProvider
    conn = convexity_db
    state.record_sentinel_candidate(conn, run_id=None, as_of="2026-03-01T00:00:00+00:00", symbol="FCX",
                                    direction="bullish", basket="copper", inflection_score=1.0,
                                    markers={"rv_rising": 0.3, "mom_recent": 0.3})
    as_of = datetime(2026, 3, 15, tzinfo=UTC)
    n = cw.record_cheapness(conn, provider=SyntheticChainProvider(as_of=as_of.date()), config=CONFIG,
                            as_of=as_of, run_id=None)
    assert n == 1
    row = conn.execute("SELECT symbol, cheap, marker_age_days, rv_rising FROM cheapness_watch").fetchone()
    assert row["symbol"] == "FCX" and row["cheap"] is not None     # the gate actually ran (FCX has a structure)
    assert 13.0 < row["marker_age_days"] < 15.0                    # 2026-03-01 → 2026-03-15 ≈ 14d
    assert row["rv_rising"] != 0.3 and isinstance(row["rv_rising"], float)  # FRESH from bars, NOT the persisted 0.3


class _BarsOnlyProvider:
    """Provider exercising only the markers path (empty chain → cheap=None); for the no-op regression."""

    def __init__(self, closes):
        self._closes = closes

    def underlying_price(self, symbol):
        return 10.0

    def chain(self, symbol):
        return []

    def closes(self, symbol, *, window):
        return self._closes


def _breaking_closes(n=253):
    """A path quiet for most of the year then a recent high-amplitude leg → fresh rv_rising > 0."""
    px = [10.0]
    for i in range(n - 1):
        amp = 0.06 if i >= n - 1 - 25 else 0.004   # last ~25 sessions high-vol, the rest quiet
        px.append(px[-1] * (1.0 + (amp if i % 2 == 0 else -amp)))
    return px


def test_record_uses_FRESH_markers_not_the_persisted_snapshot(convexity_db):
    """Regression guard for the silent no-op: record_cheapness must recompute rv_rising/mom_recent from
    CURRENT bars, NOT record the persisted row['markers'] snapshot (constant between L0s → break-onset
    could never fire). The persisted snapshot is set to a sentinel value (0.99) the fresh computation
    won't produce; the recorded values must be the FRESH ones."""
    conn = convexity_db
    state.record_sentinel_candidate(conn, run_id=None, as_of="2026-03-01T00:00:00+00:00", symbol="ZZ",
                                    direction="bullish", basket="b", inflection_score=1.0,
                                    markers={"rv_rising": 0.99, "mom_recent": 0.99})
    closes = _breaking_closes()
    cw.record_cheapness(conn, provider=_BarsOnlyProvider(closes), config=CONFIG,
                        as_of=datetime(2026, 3, 15, tzinfo=UTC), run_id=None)
    rec = conn.execute("SELECT rv_rising, mom_recent FROM cheapness_watch WHERE symbol='ZZ'").fetchone()
    expect_mom, expect_rvr = cw._fresh_freshness(closes)
    assert rec["rv_rising"] == expect_rvr and rec["rv_rising"] != 0.99   # FRESH from bars, not persisted 0.99
    assert rec["mom_recent"] == expect_mom and rec["mom_recent"] != 0.99
    assert rec["rv_rising"] > 0.10   # the recent high-vol leg crosses the fresh floor → a real break is detectable


def test_migration_0017_is_idempotent(convexity_db):
    p = Path(__file__).resolve().parent.parent / "scripts" / "migrations" / "0017_cheapness_watch.py"
    spec = importlib.util.spec_from_file_location(p.stem, p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.apply(convexity_db)   # second apply → no error (guarded)
    cols = {r[1] for r in convexity_db.execute("PRAGMA table_info(cheapness_watch)").fetchall()}
    assert "marker_age_days" in cols and "cheap" in cols
