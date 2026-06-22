"""Deterministic prescreen (T3) — the disjunctive gate, within-basket ranking, discrimination.

The key §B tests: a planted inflection in a LOW-VARIANCE basket surfaces and ranks above noise
(discrimination, not just determinism), and a DEAD basket surfaces nothing (the absolute floors,
not relative z — the auto-trade failure mode the planted-signal test alone can't catch).
"""

from datetime import UTC, datetime, timedelta

from data.cache import PointInTimeCache
from discovery import (
    MarkerParams,
    MarkerSet,
    clears_gate,
    direction_of,
    rank_basket,
    scan_baskets,
)

START = datetime(2022, 1, 1, tzinfo=UTC)
N = 320
AS_OF = START + timedelta(days=N - 1)


def _bars(closes, start=START, vol=2_000_000):
    out = []
    for i, c in enumerate(closes):
        out.append({"ts": (start + timedelta(days=i)).isoformat(),
                    "open": c, "high": c, "low": c, "close": c, "volume": vol})
    return out


def _flat(px=10.0, n=N):
    return [px] * n


def _ramp(p0, p1, n=N):
    return [p0 + (p1 - p0) * i / (n - 1) for i in range(n)]


def _vol_burst(px=10.0, n=N, burst=25):
    """Flat for n-burst, then a high-amplitude oscillation → rv_slope spikes, momentum ~0."""
    head = [px] * (n - burst)
    tail = [px * (1.0 + (0.18 if i % 2 else -0.18)) for i in range(burst)]
    return head + tail


def _md(tmp_path, series: dict[str, list[float]]):
    cache = PointInTimeCache(tmp_path)
    end = AS_OF + timedelta(days=5)
    for sym, closes in series.items():
        cache.write("bars", sym, _bars(closes),
                    coverage_from=START - timedelta(days=5), coverage_through=end)
    from data.market import MarketData
    return MarketData(cache, client=None, fetch_start=START - timedelta(days=5), fetch_end=end)


class _Events:
    def __init__(self, mapping):
        self._m = mapping

    def has_structural_event(self, symbol, as_of):
        return self._m.get(symbol, (False, None))


# ── pure-function gate / direction / ranking ────────────────────────────────────────────────


def _m(symbol, basket="b", *, mom=None, rv_slope=None, mom_recent=None, rv_rising=None,
       has_event=False, price=10.0, adv=1e7):
    return MarkerSet(symbol, basket, mom, None, 0.4, rv_slope, has_event,
                     "424B5" if has_event else None, 0, price, adv,
                     mom_recent=mom_recent, rv_rising=rv_rising)


def test_gate_is_disjunctive_on_absolute_floors():
    p = MarkerParams(mom_floor=0.15, rv_slope_floor=0.25)
    assert clears_gate(_m("MOVE", mom=0.4), p)[0] is True            # motion clears
    assert clears_gate(_m("VOL", rv_slope=0.5), p)[0] is True        # rv slope clears
    assert clears_gate(_m("EVT", has_event=True), p)[0] is True      # event clears (no motion)
    assert clears_gate(_m("FLAT", mom=0.02), p)[0] is False          # below floor → no surface
    assert clears_gate(_m("NOELIG", mom=0.9, price=None), p)[0] is False  # ineligible


def test_direction_follows_motion_sign():
    assert direction_of(_m("U", mom=0.3)) == "bullish"
    assert direction_of(_m("D", mom=-0.3)) == "bearish"


def test_rank_is_within_basket_and_event_bonus():
    # the rank is now the FRESHNESS composite z(rv_rising)+z(|mom_recent|) — §5 (trailing magnitude
    # removed); a fresher name (rising vol + recent move) ranks higher, the event bonus dominates.
    p = MarkerParams(event_bonus=10.0)
    cleared = [_m("HI", rv_rising=0.5, mom_recent=0.4), _m("LO", rv_rising=0.1, mom_recent=0.1),
               _m("EVT", rv_rising=0.1, mom_recent=0.1, has_event=True)]
    scores = rank_basket(cleared, p)
    assert scores["HI"] > scores["LO"]          # fresher (rising vol + recent move) ranks higher
    assert scores["EVT"] > scores["HI"]          # the event bonus dominates


# ── fresh-inflection re-target (PREREG_FRESH_INFLECTION_FUNNEL) ──────────────────────────────


def test_fresh_leg_surfaces_quiet_just_moving_name_not_post_spike_monster():
    """§4: the fresh conjunct (|mom_recent|≥0.20 AND rv_rising≥0.10) surfaces a trailing-quiet name
    the trailing legs miss; a post-spike monster (big trailing, vol rolling over) does NOT clear it."""
    p = MarkerParams()
    fresh = _m("FRESH", mom=0.05, rv_slope=0.10, mom_recent=0.30, rv_rising=0.25)  # trailing-quiet, just moving
    ok, reason = clears_gate(fresh, p)
    assert ok and reason == "fresh"                       # surfaces ONLY via the fresh leg
    monster = _m("MON", mom=2.0, rv_slope=0.05, mom_recent=0.05, rv_rising=-0.10)  # ran, vol fading
    okm, reasonm = clears_gate(monster, p)
    assert okm and reasonm == "momentum"                  # surfaces, but via trailing momentum — NOT fresh


def test_fresh_reason_labels_a_name_clearing_both_fresh_and_momentum():
    """§4/§8.1: the fresh conjunct is checked BEFORE momentum, so a name clearing both reads `fresh`
    (observable for the 'fresh cohort enters' telemetry)."""
    both = _m("BOTH", mom=0.4, mom_recent=0.30, rv_rising=0.25)
    ok, reason = clears_gate(both, MarkerParams())
    assert ok and reason == "fresh"


def test_freshness_rank_invariant_fresh_outranks_post_spike_monster():
    """§10 unit invariant (universe-independent): in one basket a fresh-ramp out-ranks a post-spike
    monster — magnitude no longer drives the rank, freshness does."""
    cleared = [_m("MON", mom=3.0, rv_slope=0.05, mom_recent=0.04, rv_rising=-0.05),
               _m("FRESH", mom=0.10, rv_slope=0.30, mom_recent=0.35, rv_rising=0.30)]
    scores = rank_basket(cleared, MarkerParams())
    assert scores["FRESH"] > scores["MON"]


def test_direction_keys_on_recent_move_only_with_params():
    """§6: with params, a fresh ROLLOVER (recent down, trailing up) surfaces bearish/puts; without
    params (the null books' callers) direction stays trailing-based; a sub-epsilon recent move falls back."""
    p = MarkerParams()
    roll = _m("ROLL", mom=0.5, mom_recent=-0.25)          # trailing up, recent DOWN
    assert direction_of(roll, p) == "bearish"             # funnel path → the recent move
    assert direction_of(roll) == "bullish"                # null-book path → trailing (unchanged)
    tiny = _m("TINY", mom=0.5, mom_recent=0.01)           # |recent| < dir_recent_epsilon
    assert direction_of(tiny, p) == "bullish"             # falls back to trailing


def test_compute_markers_populates_freshness(tmp_path):
    """compute_markers fills mom_recent + rv_rising from bars (the §3 markers)."""
    from discovery import compute_markers
    md = _md(tmp_path, {"X": _ramp(10, 25), "SPY": _ramp(100, 110)})
    m = compute_markers("X", AS_OF, market=md, benchmark="SPY", params=MarkerParams(), basket="b")
    assert m.mom_recent is not None and m.rv_rising is not None


def test_record_run_stamps_discovery_funnel(convexity_db):
    """§8/§9: the funnel version is segmentable on the run row (migration 0015)."""
    import state
    rid = state.record_run(convexity_db, mode="DISCOVERY", equity=None, note="t",
                           discovery_funnel="fresh_v1")
    row = convexity_db.execute("SELECT discovery_funnel FROM runs WHERE id=?", (rid,)).fetchone()
    assert row["discovery_funnel"] == "fresh_v1"


def test_migration_0015_is_idempotent(convexity_db):
    """The guarded ADD COLUMN re-applies cleanly (conftest already applied it once)."""
    import importlib.util
    from pathlib import Path
    p = Path(__file__).resolve().parent.parent / "scripts" / "migrations" / "0015_discovery_funnel.py"
    spec = importlib.util.spec_from_file_location(p.stem, p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.apply(convexity_db)   # second application must not raise
    cols = {r["name"] for r in convexity_db.execute("PRAGMA table_info(runs)")}
    assert "discovery_funnel" in cols


# ── integration scans ───────────────────────────────────────────────────────────────────────


def test_planted_signal_surfaces_in_low_variance_basket(tmp_path):
    # low-variance basket: two flat names + one planted mover; high-variance basket: big movers.
    md = _md(tmp_path, {
        "FLATA": _flat(), "FLATB": _flat(), "PLANT": _ramp(10, 20),
        "BIG1": _ramp(5, 40), "BIG2": _ramp(8, 30), "SPY": _ramp(100, 110),
    })
    baskets = {"low_var": ["FLATA", "FLATB", "PLANT"], "high_var": ["BIG1", "BIG2"]}
    res = scan_baskets(baskets, AS_OF, market=md, benchmark="SPY", params=MarkerParams(),
                       top_k=8, n_controls=2)
    surfaced = {s.markers.symbol for s in res.surfaced}
    assert "PLANT" in surfaced                       # the planted mover surfaces despite a quiet basket
    assert {"FLATA", "FLATB"}.isdisjoint(surfaced)   # flat noise does NOT surface
    assert res.surfaced[0].direction == "bullish" or "PLANT" in surfaced


def test_dead_basket_surfaces_nothing(tmp_path):
    md = _md(tmp_path, {"FLATA": _flat(), "FLATB": _flat(), "FLATC": _flat(), "SPY": _flat(100.0)})
    res = scan_baskets({"dead": ["FLATA", "FLATB", "FLATC"]}, AS_OF, market=md, benchmark="SPY",
                       params=MarkerParams(), top_k=8)
    assert res.surfaced == []        # absolute floors → a dead week surfaces nothing
    assert res.n_cleared == 0


def test_rv_slope_disjunct_surfaces_a_quiet_then_volatile_name(tmp_path):
    md = _md(tmp_path, {"CALM": _flat(), "BURST": _vol_burst(), "SPY": _flat(100.0)})
    res = scan_baskets({"b": ["CALM", "BURST"]}, AS_OF, market=md, benchmark="SPY",
                       params=MarkerParams(), top_k=8)
    surfaced = {s.markers.symbol for s in res.surfaced}
    assert "BURST" in surfaced and "CALM" not in surfaced


def test_event_only_name_surfaces_without_motion(tmp_path):
    md = _md(tmp_path, {"QUIET": _flat(), "SPY": _flat(100.0)})
    ev = _Events({"QUIET": (True, "13D")})
    res = scan_baskets({"b": ["QUIET"]}, AS_OF, market=md, benchmark="SPY",
                       params=MarkerParams(), event_provider=ev, top_k=8)
    assert {s.markers.symbol for s in res.surfaced} == {"QUIET"}
    assert res.surfaced[0].gate_reason.startswith("event")


def test_novelty_excludes_known_symbols(tmp_path):
    md = _md(tmp_path, {"PLANT": _ramp(10, 20), "SPY": _ramp(100, 110)})
    res = scan_baskets({"b": ["PLANT"]}, AS_OF, market=md, benchmark="SPY",
                       params=MarkerParams(), exclude_symbols={"PLANT"}, top_k=8)
    assert res.surfaced == []        # already-known name is not re-surfaced


def test_controls_drawn_from_eligible_unsurfaced(tmp_path):
    import random
    md = _md(tmp_path, {"FLATA": _flat(), "FLATB": _flat(), "PLANT": _ramp(10, 20),
                        "SPY": _ramp(100, 110)})
    res = scan_baskets({"b": ["FLATA", "FLATB", "PLANT"]}, AS_OF, market=md, benchmark="SPY",
                       params=MarkerParams(), top_k=8, n_controls=2, rng=random.Random(0))
    surfaced = {s.markers.symbol for s in res.surfaced}
    control_syms = {c.symbol for c in res.controls}
    assert control_syms and control_syms.isdisjoint(surfaced)   # null cohort ≠ surfaced
    assert control_syms <= {"FLATA", "FLATB"}                   # eligible but not surfaced


def test_controls_exclude_already_tracked_names(tmp_path):
    """A name in ``exclude_symbols`` (an open position or active sentinel) must NEVER be drawn as a
    control, even when eligible-but-unsurfaced — else the forward-null cohort is contaminated by the
    very lineage it is the counterfactual for (#71). Covers both shapes: an active sentinel that
    still CLEARS the gate (dropped from surfacing → leaks via eligible_unsurfaced), and a held name
    gone QUIET (eligible, doesn't clear → already in the pool)."""
    import random
    md = _md(tmp_path, {
        "FLATA": _flat(), "FLATB": _flat(),
        "HELD": _flat(),          # an open position gone quiet: eligible, doesn't clear → pool
        "SENT": _ramp(10, 20),    # an active sentinel still moving: clears the gate but is excluded
        "MOVER": _ramp(10, 20),   # a fresh, un-tracked mover → surfaces
        "SPY": _ramp(100, 110),
    })
    res = scan_baskets({"b": ["FLATA", "FLATB", "HELD", "SENT", "MOVER"]}, AS_OF, market=md,
                       benchmark="SPY", params=MarkerParams(), exclude_symbols={"SENT", "HELD"},
                       top_k=8, n_controls=10, rng=random.Random(0))
    surfaced = {s.markers.symbol for s in res.surfaced}
    control_syms = {c.symbol for c in res.controls}
    assert "MOVER" in surfaced and "SENT" not in surfaced       # excluded names never surface
    # n_controls=10 takes the whole purified pool, pinning the cohort exactly:
    assert control_syms == {"FLATA", "FLATB"}                   # only un-tracked eligible-unsurfaced
    assert {"SENT", "HELD"}.isdisjoint(control_syms)            # the #71 contamination is gone


def test_max_scan_names_bounds_the_pass(tmp_path):
    md = _md(tmp_path, {f"S{i}": _ramp(10, 20) for i in range(6)} | {"SPY": _ramp(100, 110)})
    baskets = {"a": ["S0", "S1", "S2"], "b": ["S3", "S4", "S5"]}
    res = scan_baskets(baskets, AS_OF, market=md, benchmark="SPY", params=MarkerParams(),
                       max_scan_names=3, top_k=8)
    assert res.n_scanned == 3        # stops after the first whole basket (cold-cache budget)
