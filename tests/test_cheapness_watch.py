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

# §2.1.8 sane IV profiles (all pass the degenerate bounds): a cheap=1 row carries a CHEAP-but-sane wing
# (so it classifies `cheap`); a cheap=0 row carries a RICH-but-sane profile (so it classifies `not_cheap`,
# NOT unmeasurable — the missing-input marker is iv_rv IS NULL, which the explicit cases set). A cheap=None
# row leaves the IVs NULL (no_structure — the gate did not run). These let the pre-§2.1.8 tests keep
# asserting their verdicts now that the classifier reads the IV columns.
_CHEAP_IV = {"atm_iv": 0.50, "wing_iv": 0.45, "iv_rv": 1.0, "otm_skew": -5.0}
_RICH_IV = {"atm_iv": 0.60, "wing_iv": 0.62, "iv_rv": 1.5, "otm_skew": 2.0}


def _obs(conn, symbol, as_of, *, cheap, rv_rising, mom_recent, marker_age, iv=None):
    """One session. ``iv`` overrides the sane default profile (a dict of atm_iv/wing_iv/iv_rv/otm_skew);
    omitted → derived from ``cheap`` (cheap→cheap-sane, 0→rich-sane, None→no_structure/NULL)."""
    if iv is None:
        iv = _CHEAP_IV if cheap == 1 else (_RICH_IV if cheap == 0 else {})
    with conn:
        conn.execute(
            "INSERT INTO cheapness_watch (run_id, as_of, symbol, cheap, rv_rising, mom_recent, "
            "marker_age_days, atm_iv, wing_iv, iv_rv, otm_skew, created_at) "
            "VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
            (as_of, symbol, cheap, rv_rising, mom_recent, marker_age,
             iv.get("atm_iv"), iv.get("wing_iv"), iv.get("iv_rv"), iv.get("otm_skew")),
        )


def _series(conn, symbol, days, *, marker_age):
    """days: list of (rv_rising, mom_recent, cheap) — or (rv_rising, mom_recent, cheap, iv_dict) to override
    a session's IV profile (for the §2.1.8 degenerate / unmeasurable cases) — per session, in order."""
    for i, day in enumerate(days):
        rvr, mom, cheap = day[0], day[1], day[2]
        iv = day[3] if len(day) > 3 else None
        _obs(conn, symbol, f"2026-03-{i + 1:02d}", cheap=cheap, rv_rising=rvr, mom_recent=mom,
             marker_age=marker_age, iv=iv)


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


# ════════════════════════════════════════════════════════════════════════════════════════════════
# §2.1.8 — the degenerate_iv / unmeasurable reclassification + right-censoring (PR A)
# Assert the VERDICT, not the label.
# ════════════════════════════════════════════════════════════════════════════════════════════════

# §2.1.8 degenerate IV profiles (all paired with cheap=1 unless noted, to expose the seam where the gate
# would say cheap):
#  - WING_LOW_RELATIVE: clean ATM, a wing whose skew (−45vp) sits BELOW the |skew| ceiling (100) and whose
#    wing IV (0.05) is ABOVE the absolute floor (0.03) — caught ONLY by the relative wing < k·atm disjunct
#    (0.05 < 0.15·0.50 = 0.075). The load-bearing clean-ATM / garbage-wing seam (R2 verdict-corruptor).
WING_LOW_RELATIVE = {"atm_iv": 0.50, "wing_iv": 0.05, "iv_rv": 1.0, "otm_skew": -45.0}
#  - CDE_HIGH: the real degenerate-HIGH (CDE −202vp / iv_rv 3.7) — both the skew-abs and iv_rv disjuncts
#    trip; skew is checked first → which_bound 'otm_skew_abs'.
CDE_HIGH = {"atm_iv": 2.00, "wing_iv": 0.10, "iv_rv": 3.7, "otm_skew": -202.0}
#  - a real CHEAP wing that must NOT be clipped (spectacularly cheap but sane): wing 0.10 sits just ABOVE
#    both the absolute floor (0.03) and the relative floor (0.075), skew −40 inside the ceiling.
REAL_CHEAP_WING = {"atm_iv": 0.50, "wing_iv": 0.10, "iv_rv": 1.0, "otm_skew": -40.0}
#  - a legitimately RICH name that must NOT be swept into degenerate_iv: iv_rv 1.3 just over the gate's 1.2
#    (so cheap=0) but well under the 5.0 sanity ceiling; sane skew + sane legs.
LEGIT_RICH = {"atm_iv": 0.50, "wing_iv": 0.55, "iv_rv": 1.3, "otm_skew": 5.0}


def test_degenerate_low_seam_reclassified_out_verdict_unchanged(convexity_db):
    """THE critical seam test: a clean-ATM / garbage-wing onset that WOULD be cheap=1 and enter qualifying
    (caught ONLY by the relative wing<k·atm disjunct, NOT the |skew| ceiling) is reclassified OUT — and
    n_qualifying/verdict are UNCHANGED vs a clean baseline. (Both arms run the same fixed code; the claim
    is that the degenerate name — which looks like a juicy qualifying window — contributes nothing.)"""
    # baseline: one clean qualifying cheap_window (stale markers, closes at V=2 → fire under floor=1)
    _series(convexity_db, "CLEAN", [(*BELOW, 1), (*FRESH, 1), (*FRESH, 0), (*FRESH, 0)], marker_age=25)
    base = cw.cheapness_report(convexity_db, staleness_lag_days=20.0, n_qualify_floor=1)
    assert base["n_qualifying"] == 1 and base["verdict"] == "fire" and base["n_degenerate_iv"] == 0

    # add DEGEN: onset is degenerate-LOW (cheap=1 by the gate), then clean cheap days, then a close.
    # Without §2.1.8 this is a qualifying cheap_window; with it the onset is reclassified → no break at all.
    _series(convexity_db, "DEGEN",
            [(*BELOW, 1), (*FRESH, 1, WING_LOW_RELATIVE), (*FRESH, 1), (*FRESH, 1), (*FRESH, 0), (*FRESH, 0)],
            marker_age=25)
    rep = cw.cheapness_report(convexity_db, staleness_lag_days=20.0, n_qualify_floor=1)
    assert rep["n_qualifying"] == base["n_qualifying"]            # the seam name did NOT swell qualifying
    assert rep["verdict"] == base["verdict"]                      # verdict unchanged vs the clean baseline
    assert rep["n_degenerate_iv"] == 1                            # it was caught + counted
    rc = [r for r in rep["reclassified_rows"] if r["symbol"] == "DEGEN"]
    assert len(rc) == 1 and rc[0]["which_bound"] == "wing_atm_ratio"   # caught by the RELATIVE disjunct
    assert rc[0]["offending_value"] == 0.05 and rc[0]["state"] == "degenerate_iv"   # the offending wing IV


def test_unmeasurable_is_not_never_cheap_nor_qualifying(convexity_db):
    """A missing-input fail-close onset (cheap=0 ∧ iv_rv IS NULL) is `unmeasurable`, NOT `never_cheap` and
    NOT qualifying — it launders out of the 'IV already popped' bucket into the honest 'we couldn't read it'."""
    _series(convexity_db, "U", [(*BELOW, 0, {}), (*FRESH, 0, {}), (*FRESH, 0, {})], marker_age=25)
    rep = cw.cheapness_report(convexity_db, n_qualify_floor=1)
    assert rep["n_breaks"] == 1 and rep["n_unmeasurable"] == 1
    assert rep["n_never_cheap"] == 0 and rep["n_qualifying"] == 0
    rc = rep["reclassified_rows"]
    assert len(rc) == 1 and rc[0]["state"] == "unmeasurable" and rc[0]["which_bound"] == "missing_iv_rv"


def test_mid_window_degenerate_low_does_not_inflate_the_window(convexity_db):
    """A clean cheap onset with an injected mid-window degenerate-LOW (cheap=1 at the gate) session: the
    unreadable blip is TRANSPARENT — cheap_window_days counts only the real cheap days, NOT inflated."""
    _series(convexity_db, "X",
            [(*BELOW, 1), (*FRESH, 1), (*FRESH, 1, WING_LOW_RELATIVE), (*FRESH, 1), (*FRESH, 0), (*FRESH, 0)],
            marker_age=25)
    rep = cw.cheapness_report(convexity_db, staleness_lag_days=20.0, n_qualify_floor=1)
    # 2 real cheap days (i1, i3); the mid-window degen blip is transparent. Without §2.1.8 it would count → 3.
    assert rep["n_breaks"] == 1 and rep["qualifying_windows"] == [2]
    assert rep["verdict"] == "fire"                                    # median 2 < lag 20


def test_censored_short_window_excluded_from_median_and_floor(convexity_db):
    """A censored_short window (truncated by a SUSTAINED unreadable run at V < lag) does NOT enter the
    median or the N-floor — verdict unchanged vs a baseline without it; counted as censored_short."""
    # baseline: 3 clean qualifying closed windows (median 2 < lag 20 → fire under floor 3)
    for sym in ("A", "B", "C"):
        _series(convexity_db, sym, [(*BELOW, 1), (*FRESH, 1), (*FRESH, 0), (*FRESH, 0)], marker_age=25)
    base = cw.cheapness_report(convexity_db, staleness_lag_days=20.0, n_qualify_floor=3)
    assert base["n_qualifying"] == 3 and base["verdict"] == "fire"

    # add a window truncated at V=2 (< lag) by 2 consecutive degenerate sessions
    _series(convexity_db, "TRUNC",
            [(*BELOW, 1), (*FRESH, 1), (*FRESH, 1, WING_LOW_RELATIVE), (*FRESH, 1, WING_LOW_RELATIVE)],
            marker_age=25)
    rep = cw.cheapness_report(convexity_db, staleness_lag_days=20.0, n_qualify_floor=3)
    assert rep["n_censored_short"] == 1
    assert rep["n_qualifying"] == 4                       # it IS a qualifying break (the harm occurred)
    assert sorted(rep["qualifying_windows"]) == [1, 1, 1]  # the truncated V=1 is NOT in the decision median set
    assert rep["verdict"] == base["verdict"]             # verdict unchanged vs the baseline without it


def test_censored_window_past_lag_votes_hold(convexity_db):
    """A censored window (open_at_end, never closed) with V ≥ lag is a definitive HOLD vote — its true
    length is ≥ V ≥ lag, so it is kept and votes hold."""
    # 5 cheap days, no close (open_at_end); lag=3 so V=5 ≥ lag → kept as a hold vote
    _series(convexity_db, "H", [(*BELOW, 1), (*FRESH, 1), (*FRESH, 1), (*FRESH, 1), (*FRESH, 1), (*FRESH, 1)],
            marker_age=25)
    rep = cw.cheapness_report(convexity_db, staleness_lag_days=3.0, n_qualify_floor=1)
    assert rep["n_qualifying"] == 1 and rep["n_censored_short"] == 0
    assert rep["qualifying_windows"] == [5] and rep["verdict"] == "hold"   # median 5 ≥ lag 3 → HOLD


def test_open_at_end_short_window_is_censored_not_a_face_value_short(convexity_db):
    """An open_at_end window shorter than the lag is treated as RIGHT-CENSORED (excluded), NOT a face-value
    short that would fire — the would-be-fire is suppressed because the true length is unknown."""
    # 2 cheap days, no close (open_at_end), V=2 < lag=20 → censored_short, NOT a fire
    _series(convexity_db, "S", [(*BELOW, 1), (*FRESH, 1), (*FRESH, 1)], marker_age=25)
    rep = cw.cheapness_report(convexity_db, staleness_lag_days=20.0, n_qualify_floor=1)
    assert rep["n_qualifying"] == 1 and rep["n_censored_short"] == 1
    assert rep["qualifying_windows"] == []                # not in the decision set
    assert rep["verdict"] == "insufficient_N"             # NOT 'fire' — a face-value short would have fired


def test_cde_high_onset_is_degenerate_not_never_cheap(convexity_db):
    """A degenerate-HIGH onset (CDE: iv_rv 3.7, skew −202) is `degenerate_iv`, NOT `never_cheap` — the
    'IV already popped' bucket is corrected to 'we couldn't read it'. Skew is checked first."""
    _series(convexity_db, "CDE", [(*BELOW, 0, CDE_HIGH), (*FRESH, 0, CDE_HIGH), (*FRESH, 0, CDE_HIGH)],
            marker_age=25)
    rep = cw.cheapness_report(convexity_db, n_qualify_floor=1)
    assert rep["n_breaks"] == 1 and rep["n_degenerate_iv"] == 1 and rep["n_never_cheap"] == 0
    rc = rep["reclassified_rows"]
    assert rc[0]["which_bound"] == "otm_skew_abs" and rc[0]["offending_value"] == -202.0


def test_negative_control_legit_rich_stays_never_cheap(convexity_db):
    """A legitimately RICH name (iv_rv 1.3 just over the gate's 1.2, sane skew/legs) stays `never_cheap` —
    NOT swept into degenerate_iv. The iv_rv sanity ceiling (5.0) is ≫ 1.2 so it does not launder rich names."""
    _series(convexity_db, "RICH", [(*BELOW, 0, LEGIT_RICH), (*FRESH, 0, LEGIT_RICH), (*FRESH, 0, LEGIT_RICH)],
            marker_age=25)
    rep = cw.cheapness_report(convexity_db, n_qualify_floor=1)
    assert rep["n_never_cheap"] == 1 and rep["n_degenerate_iv"] == 0 and rep["n_unmeasurable"] == 0


def test_negative_control_real_cheap_wing_not_clipped(convexity_db):
    """A spectacularly-cheap-but-REAL wing (low wing IV just above the absolute+relative floors, skew inside
    the ceiling) stays a `cheap_window` and qualifies — NOT clipped to degenerate_iv (the clip budget fires
    only on near-zero/stale quotes, never on a real low-IV wing — the exact signal the watch must keep)."""
    _series(convexity_db, "CHEAPW",
            [(*BELOW, 1), (*FRESH, 1, REAL_CHEAP_WING), (*FRESH, 1, REAL_CHEAP_WING), (*FRESH, 0), (*FRESH, 0)],
            marker_age=25)
    rep = cw.cheapness_report(convexity_db, staleness_lag_days=20.0, n_qualify_floor=1)
    assert rep["n_degenerate_iv"] == 0 and rep["n_qualifying"] == 1
    assert rep["qualifying_windows"] == [2] and rep["verdict"] == "fire"


def test_window_len_transition_table_all_cells(convexity_db):
    """Every cell of the §2.1.8 3-input transition table (IN_WINDOW / CLOSING × cheap / not_cheap /
    unreadable), plus alternating cheap/unreadable and the sustained-truncate, asserted on (window, reason).
    Built as raw row dicts so the machine is exercised directly (no onset detection in the way)."""
    bounds = cw.DEFAULT_DEGEN_BOUNDS

    def row(label):
        if label == "cheap":
            return dict(cheap=1, **_CHEAP_IV)
        if label == "not_cheap":
            return dict(cheap=0, **_RICH_IV)
        return dict(cheap=1, **WING_LOW_RELATIVE)   # 'unreadable' (degenerate-LOW; cheap=1 at the gate)

    def wl(labels):
        return cw._window_len([row(x) for x in labels], 0, bounds)

    # IN_WINDOW + cheap → window++ (and stays open → open_at_end)
    assert wl(["cheap", "cheap", "cheap"]) == (3, "open_at_end")
    # IN_WINDOW + not_cheap → CLOSING; CLOSING + cheap → back to IN_WINDOW (the 1-blip absorbed)
    assert wl(["cheap", "not_cheap", "cheap", "cheap"]) == (3, "open_at_end")
    # CLOSING + not_cheap → CLOSED (the sustained close; the 2nd not_cheap is not counted)
    assert wl(["cheap", "not_cheap", "not_cheap"]) == (1, "closed")
    # IN_WINDOW + unreadable (isolated) → transparent blip; window unchanged, run untouched
    assert wl(["cheap", "unreadable", "cheap"]) == (2, "open_at_end")
    # CLOSING + unreadable (isolated) → transparent; the close-run survives, next not_cheap finalizes
    assert wl(["cheap", "not_cheap", "unreadable", "not_cheap"]) == (1, "closed")
    # IN_WINDOW + 2 consecutive unreadable → TRUNCATE at the last clean cheap
    assert wl(["cheap", "cheap", "unreadable", "unreadable"]) == (2, "truncated")
    # CLOSING + 2 consecutive unreadable → TRUNCATE (the degen run hits the threshold while closing)
    assert wl(["cheap", "not_cheap", "unreadable", "unreadable"]) == (1, "truncated")
    # alternating cheap/unreadable never truncates (the run resets on each cheap) → open_at_end, counts cheaps
    assert wl(["cheap", "unreadable", "cheap", "unreadable", "cheap"]) == (3, "open_at_end")


def test_classify_is_none_safe_and_total(convexity_db):
    """`_classify` never raises on any (cheap, IV) combination and maps the partition exactly."""
    b = cw.DEFAULT_DEGEN_BOUNDS
    assert cw._classify(dict(cheap=None, atm_iv=None, wing_iv=None, iv_rv=None, otm_skew=None), b) == "no_structure"
    assert cw._classify(dict(cheap=0, atm_iv=None, wing_iv=None, iv_rv=None, otm_skew=None), b) == "unmeasurable"
    assert cw._classify(dict(cheap=1, **_CHEAP_IV), b) == "cheap"
    assert cw._classify(dict(cheap=0, **_RICH_IV), b) == "not_cheap"
    assert cw._classify(dict(cheap=1, **WING_LOW_RELATIVE), b) == "degenerate_iv"
    assert cw._classify(dict(cheap=1, **CDE_HIGH), b) == "degenerate_iv"
    # a stray None on a present-IV row must not raise and must not spuriously trip
    assert cw._classify(dict(cheap=1, atm_iv=0.5, wing_iv=0.45, iv_rv=1.0, otm_skew=None), b) == "cheap"


# ════════════════════════════════════════════════════════════════════════════════════════════════
# §2.1.7 — the FAIL-CLOSED clock-start gate (council-confirmed-quiet). The RATE (qualifying_per_quarter)
# counts observed_days only from the day the cohort first held a name the STRATEGIST read
# under_narrated=True at FIRST judgment (parse_error=false) — never from first observation.
# ════════════════════════════════════════════════════════════════════════════════════════════════


def _council_read(conn, symbol, *, as_of, under_narrated, parse_error=False, strat_conv="MODERATE",
                  proposer_un=None, run_id=None):
    """Record one council judgment for ``symbol`` carrying the strategist's ``under_narrated`` read.

    Mirrors the production persist path: the aggregate rides ``rationale.strategist.under_narrated``
    (the read path the §2.1.7 gate uses), and each role's read rides ``council_agent_outputs.raw`` (the
    per-role audit). ``parse_error`` marks the strategist agent_output as the fail-closed fallback."""
    rationale = {"strategist": {"under_narrated": under_narrated, "at_inflection": True,
                                "include": bool(under_narrated), "conviction": strat_conv}}
    pid = state.record_council_proposal(
        conn, run_id=run_id, as_of=as_of, theme="t", symbol=symbol, direction="bullish",
        conviction=strat_conv, rationale=rationale, status="proposed",
    )
    # proposer/adversary structurally don't emit under_narrated (a strategist-only key) — record them as
    # such so the per_role composition is truthful (None for the non-emitting roles unless overridden).
    state.record_agent_output(conn, proposal_id=pid, role="proposer", provider="g", model="m",
                              confidence="MODERATE", stance="bullish",
                              raw=({"under_narrated": proposer_un} if proposer_un is not None
                                   else {"confidence": "MODERATE", "inflection_thesis": "x"}))
    state.record_agent_output(conn, proposal_id=pid, role="adversary", provider="x", model="m",
                              confidence="MODERATE", stance="bearish", raw={"counter_case": "c"})
    srow = ({"confidence": "NEUTRAL", "parse_error": True} if parse_error
            else {"conviction": strat_conv, "under_narrated": under_narrated, "at_inflection": True,
                  "include": bool(under_narrated)})
    state.record_agent_output(conn, proposal_id=pid, role="strategist", provider="a", model="m",
                              confidence=strat_conv, stance="bullish", raw=srow)
    return pid


# a qualifying cheap_window break (stale markers age 25 ≥ lag 20, closes at V=2 < lag → would fire)
_QUALIFYING = [(*BELOW, 1), (*FRESH, 1), (*FRESH, 0), (*FRESH, 0)]


def test_clock_does_not_start_on_feasibility_fresh_not_council_confirmed(convexity_db):
    """A feasibility-fresh cohort with NO council-confirmed-quiet name: the clock does NOT start, so
    observed_days / qualifying_per_quarter are None — EVEN with a qualifying break present. (Fail-CLOSED:
    a not-yet-break-capable cohort cannot dilute the rate toward a false negative.)"""
    _series(convexity_db, "X", _QUALIFYING, marker_age=25)
    rep = cw.cheapness_report(convexity_db, staleness_lag_days=20.0, n_qualify_floor=1)
    assert rep["n_qualifying"] == 1                       # the break is detected & qualifies
    assert rep["observed_days"] is None                   # but the RATE clock has not started
    assert rep["qualifying_per_quarter"] is None
    assert rep["clock"]["clock_started"] is False and rep["clock"]["n_confirmed_quiet"] == 0


def test_clock_starts_at_first_council_confirmed_quiet_name(convexity_db):
    """With a council-confirmed-quiet name (strategist under_narrated=True at first judgment,
    parse_error=false) in the cohort, the clock STARTS — observed_days spans from the clock-start obs and
    the rate is a real number."""
    # judgment lands on/before the watch history; the watch runs 2026-03-01..03-04 (4 obs)
    _council_read(convexity_db, "X", as_of="2026-02-15T00:00:00+00:00", under_narrated=True)
    _series(convexity_db, "X", _QUALIFYING, marker_age=25)
    rep = cw.cheapness_report(convexity_db, staleness_lag_days=20.0, n_qualify_floor=1)
    assert rep["clock"]["clock_started"] is True and rep["clock"]["clock_start_symbol"] == "X"
    assert rep["clock"]["n_confirmed_quiet_watched"] == 1
    # clock-start = first watch obs (2026-03-01); last obs 2026-03-04 → ~3 days
    assert rep["observed_days"] is not None and 2.9 < rep["observed_days"] < 3.1
    assert rep["qualifying_per_quarter"] is not None and rep["qualifying_per_quarter"] > 0


def test_clock_does_not_start_on_under_narrated_false_or_parse_error(convexity_db):
    """A deliberated under_narrated=False, and a strategist parse_error, are NOT confirmations — neither
    starts the clock (the binding tri-criteria role must AFFIRM quietness on a clean parse)."""
    _council_read(convexity_db, "FALSEY", as_of="2026-02-15T00:00:00+00:00", under_narrated=False)
    _council_read(convexity_db, "PARSEFAIL", as_of="2026-02-15T00:00:00+00:00", under_narrated=True,
                  parse_error=True)
    _series(convexity_db, "FALSEY", _QUALIFYING, marker_age=25)
    _series(convexity_db, "PARSEFAIL", _QUALIFYING, marker_age=25)
    rep = cw.cheapness_report(convexity_db, staleness_lag_days=20.0, n_qualify_floor=1)
    assert rep["clock"]["clock_started"] is False
    assert rep["observed_days"] is None and rep["qualifying_per_quarter"] is None


def test_name_narrating_mid_window_stays_counted_anti_survivorship(convexity_db):
    """Anti-survivorship (§2.1.7): a name confirmed-quiet at FIRST judgment that later NARRATES
    (under_narrated=False in a subsequent proposal) STAYS in the cohort and keeps its clock-start — the
    during-window narration is the signal being measured, never a disqualifier. The clock-start, the
    confirmed-quiet count, and the qualifying break are all unchanged vs. confirmation alone."""
    _council_read(convexity_db, "X", as_of="2026-02-15T00:00:00+00:00", under_narrated=True)   # FIRST: quiet
    _council_read(convexity_db, "X", as_of="2026-03-20T00:00:00+00:00", under_narrated=False)  # LATER: narrates
    _series(convexity_db, "X", _QUALIFYING, marker_age=25)
    rep = cw.cheapness_report(convexity_db, staleness_lag_days=20.0, n_qualify_floor=1)
    # the FIRST judgment (under_narrated=True) is the binding read; the later narration does not drop it
    assert rep["clock"]["clock_started"] is True and rep["clock"]["n_confirmed_quiet"] == 1
    assert rep["clock"]["composition"]["X"]["first_judgment_as_of"] == "2026-02-15T00:00:00+00:00"
    assert rep["n_qualifying"] == 1 and rep["observed_days"] is not None   # the narrator is still counted


def test_per_role_under_narrated_reads_recorded_in_composition(convexity_db):
    """Per-role recording (§2.1.7 point 4): each council role's under_narrated read is captured in the
    clock composition so the cohort's quietness composition is auditable. under_narrated is a
    strategist-only key (proposer/adversary don't emit it → None); the strategist carries the True read."""
    _council_read(convexity_db, "X", as_of="2026-02-15T00:00:00+00:00", under_narrated=True,
                  proposer_un=False)   # force a proposer read to prove per-role capture is real
    _series(convexity_db, "X", _QUALIFYING, marker_age=25)
    rep = cw.cheapness_report(convexity_db, staleness_lag_days=20.0, n_qualify_floor=1)
    comp = rep["clock"]["composition"]["X"]
    assert comp["per_role"]["strategist"] is True       # the binding role affirmed quiet
    assert comp["per_role"]["proposer"] is False        # captured verbatim (proven non-None here)
    assert comp["per_role"]["adversary"] is None        # adversary structurally doesn't emit it
    assert comp["under_narrated"] is True and comp["parse_error"] is False


def test_clock_start_requires_the_confirmed_name_to_be_watched(convexity_db):
    """A council-confirmed-quiet name that is NOT in the watch cohort cannot start the clock (no
    break-capable OBSERVATION of it); a DIFFERENT, unconfirmed watched name does not start it either."""
    _council_read(convexity_db, "CONFIRMED_BUT_UNWATCHED", as_of="2026-02-15T00:00:00+00:00",
                  under_narrated=True)
    _series(convexity_db, "WATCHED_BUT_UNCONFIRMED", _QUALIFYING, marker_age=25)
    rep = cw.cheapness_report(convexity_db, staleness_lag_days=20.0, n_qualify_floor=1)
    assert rep["clock"]["n_confirmed_quiet"] == 1            # the confirmation exists
    assert rep["clock"]["n_confirmed_quiet_watched"] == 0    # but it is not watched → clock unstarted
    assert rep["clock"]["clock_started"] is False and rep["observed_days"] is None


def test_council_first_judgment_under_narrated_uses_first_deliberated(convexity_db):
    """state.council_first_judgment_under_narrated picks the EARLIEST DELIBERATED proposal per symbol; a
    pre-strategist drop (no rationale.strategist) never claims the slot."""
    # an earlier ungrounded drop (no strategist) must NOT be the first judgment
    state.record_council_proposal(convexity_db, run_id=None, as_of="2026-01-01T00:00:00+00:00", theme="t",
                                  symbol="X", direction="bullish", conviction="NEUTRAL",
                                  rationale={"dropped": "ungrounded (no numeric evidence)"}, status="dropped")
    _council_read(convexity_db, "X", as_of="2026-02-15T00:00:00+00:00", under_narrated=True)
    reads = state.council_first_judgment_under_narrated(convexity_db)
    assert reads["X"]["as_of"] == "2026-02-15T00:00:00+00:00"   # the deliberated row, not the earlier drop
    assert reads["X"]["confirmed_quiet"] is True


def test_stamp_run_clock_basis_merges_into_model_mix(convexity_db):
    """state.stamp_run_clock_basis record-segments the run by the §2.1.7 basis WITHOUT clobbering the
    council model_mix keys (the prompt/corpus stamp idiom)."""
    import json
    rid = state.record_run(convexity_db, mode="PAPER", equity=10000)
    state.update_run_council_health(convexity_db, rid, council_health="ok",
                                    model_mix=json.dumps({"proposer": "gemini/x", "corpus": "fundamentals_v2"}))
    state.stamp_run_clock_basis(convexity_db, rid, cw.CLOCK_BASIS)
    mix = json.loads(convexity_db.execute("SELECT model_mix FROM runs WHERE id=?", (rid,)).fetchone()["model_mix"])
    assert mix["clock_basis"] == cw.CLOCK_BASIS               # the new segmentation key
    assert mix["proposer"] == "gemini/x" and mix["corpus"] == "fundamentals_v2"   # preserved, not clobbered
