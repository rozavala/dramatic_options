"""Sentinel store (T3) — lineage identity/upsert, TTL dormancy, ranked union, resolve/link."""

from datetime import UTC, datetime, timedelta

import sentinels
import state
from discovery import DiscoveryResult, MarkerParams, MarkerSet, Surfaced
from themes import Theme


def _rec(conn, symbol, direction, score, *, kind="sentinel", as_of="2026-06-02T12:00:00+00:00",
         basket="ai_compute", markers=None):
    return state.record_sentinel_candidate(
        conn, run_id=None, as_of=as_of, symbol=symbol, direction=direction, basket=basket,
        inflection_score=score, markers=markers or {"momentum": 0.4}, kind=kind,
    )


def test_resurface_updates_lineage_in_place(convexity_db):
    conn = convexity_db
    id1 = _rec(conn, "FCX", "bullish", 0.5, as_of="2026-06-02T12:00:00+00:00")
    id2 = _rec(conn, "FCX", "bullish", 0.9, as_of="2026-06-09T12:00:00+00:00")
    assert id1 == id2  # same lineage → one continuous bet, not a new discovery
    row = state.sentinel_by_id(conn, id1)
    assert row["surface_count"] == 2
    assert row["inflection_score"] == 0.9            # refreshed
    assert row["last_seen_at"].startswith("2026-06-09")
    # exactly one row for this lineage
    n = conn.execute("SELECT COUNT(*) AS n FROM sentinel_candidates WHERE symbol='FCX'").fetchone()["n"]
    assert n == 1


def test_dormant_lineage_revives_on_resurface(convexity_db):
    conn = convexity_db
    sid = _rec(conn, "FCX", "bullish", 0.5)
    state.set_sentinel_status(conn, sid, status="dormant")
    sid2 = _rec(conn, "FCX", "bullish", 0.7)
    assert sid2 == sid
    assert state.sentinel_by_id(conn, sid)["status"] == "candidate"  # revived


def test_opposite_direction_is_a_new_lineage(convexity_db):
    conn = convexity_db
    a = _rec(conn, "FCX", "bullish", 0.5)
    b = _rec(conn, "FCX", "bearish", 0.5)
    assert a != b  # a tailwind and a rollover on the same name are different bets


def test_active_rows_ranked_and_controls_excluded(convexity_db):
    conn = convexity_db
    _rec(conn, "AAA", "bullish", 0.2)
    _rec(conn, "BBB", "bullish", 0.9)
    _rec(conn, "CCC", "bullish", 0.5)
    _rec(conn, "ZZZ", "bullish", 5.0, kind="control")  # null cohort, never unioned
    rows = state.active_sentinel_rows(conn)
    assert [r["symbol"] for r in rows] == ["BBB", "CCC", "AAA"]  # score desc
    assert "ZZZ" not in state.active_sentinel_symbols(conn)


def test_control_rows_do_not_collide(convexity_db):
    conn = convexity_db
    a = _rec(conn, "AAA", "bullish", 0.0, kind="control")
    b = _rec(conn, "AAA", "bullish", 0.0, kind="control")
    assert a != b  # controls always insert (per-scan), never upsert


def test_expire_stale_flips_to_dormant(convexity_db):
    conn = convexity_db
    sid = _rec(conn, "FCX", "bullish", 0.5, as_of="2026-01-01T00:00:00+00:00")
    fresh = _rec(conn, "NEW", "bullish", 0.5, as_of="2026-06-01T00:00:00+00:00")
    n = state.expire_stale_sentinels(conn, as_of=datetime(2026, 6, 2, tzinfo=UTC), ttl_days=35)
    assert n == 1
    assert state.sentinel_by_id(conn, sid)["status"] == "dormant"
    assert state.sentinel_by_id(conn, fresh)["status"] == "candidate"  # within TTL
    assert "FCX" not in state.active_sentinel_symbols(conn)            # dormant drops from union


def test_link_proposal_sets_both_sides(convexity_db):
    conn = convexity_db
    sid = _rec(conn, "FCX", "bullish", 0.5)
    pid = state.record_council_proposal(
        conn, run_id=None, as_of="2026-06-02T12:00:00+00:00", theme="ai_compute", symbol="FCX",
        direction="bullish", conviction="HIGH",
    )
    state.link_sentinel_proposal(conn, sid, pid)
    assert state.sentinel_by_id(conn, sid)["proposal_id"] == pid
    assert state.council_proposal_by_id(conn, pid)["sentinel_id"] == sid


def test_resolve_records_forward_fields_without_fabrication(convexity_db):
    conn = convexity_db
    sid = _rec(conn, "FCX", "bullish", 0.5)
    # never-traded → resolved via reference return + a terminal-event tag (acquisition jackpot)
    state.resolve_sentinel(conn, sid, resolved_at="2026-12-02T00:00:00+00:00",
                           reference_return=3.1, terminal_event="acquired")
    row = state.sentinel_by_id(conn, sid)
    assert row["reference_return"] == 3.1 and row["terminal_event"] == "acquired"
    assert row["outcome"] is None  # genuinely unresolved direction → NULL, never fabricated


# ── sentinels.py glue: project / union / persist / re-validate ─────────────────────────────────


def _mk(symbol, basket="ai_compute", *, mom=0.4, has_event=False):
    return MarkerSet(symbol, basket, mom, 0.1, 0.4, 0.3, has_event,
                     "13D" if has_event else None, 0, 12.0, 1e7)


def test_persist_discovery_records_surfaced_and_controls(convexity_db):
    conn = convexity_db
    res = DiscoveryResult(
        surfaced=[Surfaced(_mk("FCX"), "bullish", 1.5, "momentum"),
                  Surfaced(_mk("CCJ"), "bullish", 0.8, "rv_slope")],
        controls=[_mk("RANDX")],
    )
    counts = sentinels.persist_discovery(conn, res, run_id=None, as_of_iso="2026-06-02T12:00:00+00:00")
    assert counts == {"sentinels": 2, "controls": 1}
    cands = sentinels.active_sentinel_candidates(conn)
    assert [t.symbol for t in cands] == ["FCX", "CCJ"]           # ranked by score
    assert all(t.source == "sentinel" and t.sentinel_id for t in cands)
    assert cands[0].thesis.startswith("momentum")                # seed_thesis = marker summary
    assert "RANDX" not in state.active_sentinel_symbols(conn)     # control never unioned


def test_persist_discovery_carries_framer_fields(convexity_db):
    """The framer's confound-label (real/artifact/mean-reversion) is PERSISTED on the row, not just
    acted on — otherwise the one output that makes the framer a skeptic, not a narrator, is unscored
    (it gets bucketed by at resolution)."""
    conn = convexity_db
    res = DiscoveryResult(surfaced=[Surfaced(_mk("SMCI"), "bullish", 1.2, "momentum")])
    framings = {"SMCI": {"direction": "bullish", "theme": "ai_compute",
                         "seed_thesis": "momentum +0.40 inflection", "conviction": "HIGH",
                         "structural_vs_fad": "structural", "confound_label": "real_inflection",
                         "cost_usd": 0.01, "provider": "gemini", "model": "gemini-3.1-flash-lite"}}
    sentinels.persist_discovery(conn, res, run_id=None, as_of_iso="2026-06-02T12:00:00+00:00",
                                framings=framings)
    row = conn.execute("SELECT * FROM sentinel_candidates WHERE symbol='SMCI'").fetchone()
    assert row["confound_label"] == "real_inflection"   # the skeptic's verdict is recorded
    assert row["framer_conviction"] == "HIGH"
    assert row["seed_thesis"] == "momentum +0.40 inflection"
    assert row["theme"] == "ai_compute" and row["provider"] == "gemini"


def test_union_truncation_drops_weakest_sentinel_not_handseed():
    hand = [Theme("copper", "FCX", "bullish", "operator conviction"),
            Theme("space", "RKLB", "bullish", "operator conviction")]
    sents = [Theme("s_hi", "AAA", "bullish", "", source="sentinel", sentinel_id=1),
             Theme("s_lo", "BBB", "bullish", "", source="sentinel", sentinel_id=2)]  # already ranked
    union = sentinels.union_candidates(hand, sents)
    capped = union[:3]  # mirrors council.propose's [:max_candidates]
    syms = [t.symbol for t in capped]
    assert syms == ["FCX", "RKLB", "AAA"]   # both hand-seed kept; weakest sentinel (BBB) dropped


def test_union_dedup_same_bet_handseed_wins():
    # SAME (symbol, direction) in both lists = a true duplicate → one entry, the HAND-SEED kept.
    hand = [Theme("copper", "FCX", "bullish", "operator conviction")]
    sents = [Theme("s_fcx", "FCX", "bullish", "", source="sentinel", sentinel_id=9)]
    union = sentinels.union_candidates(hand, sents)
    assert [t.symbol for t in union] == ["FCX"]
    assert union[0].source == "hand-seed" and union[0].thesis == "operator conviction"


def test_union_dedup_opposite_direction_both_kept():
    # OPPOSITE directions of one name are DISTINCT bets (lineage identity = (symbol, direction)) → BOTH
    # kept; hand-seed first. (symbol-only dedup would have wrongly dropped the bear.)
    hand = [Theme("copper", "FCX", "bullish", "operator conviction")]
    sents = [Theme("s_fcx", "FCX", "bearish", "", source="sentinel", sentinel_id=9)]
    union = sentinels.union_candidates(hand, sents)
    assert [(t.symbol, t.direction) for t in union] == [("FCX", "bullish"), ("FCX", "bearish")]


def test_union_dedup_intra_list_two_directions_both_kept():
    # No hand-seed; a symbol surfaced as a sentinel in two live directions → both kept (a symbol-only
    # key would silently drop one directional bet with no hand-seed involved).
    sents = [Theme("s_hi", "AAA", "bullish", "", source="sentinel", sentinel_id=1),
             Theme("s_lo", "AAA", "bearish", "", source="sentinel", sentinel_id=2)]
    union = sentinels.union_candidates([], sents)
    assert [(t.symbol, t.direction) for t in union] == [("AAA", "bullish"), ("AAA", "bearish")]


def test_union_dedup_case_insensitive():
    hand = [Theme("copper", "fcx", "Bullish", "operator")]
    sents = [Theme("s", "FCX", "bullish", "", source="sentinel", sentinel_id=3)]
    assert len(sentinels.union_candidates(hand, sents)) == 1   # 'fcx'/'Bullish' == 'FCX'/'bullish'


def test_union_no_overlap_is_byte_identical_concat():
    # The common case (no collision) → identical to the old bare concatenation, order preserved.
    hand = [Theme("copper", "FCX", "bullish", "op"), Theme("space", "RKLB", "bullish", "op")]
    sents = [Theme("s", "AAA", "bullish", "", source="sentinel", sentinel_id=1),
             Theme("s", "BBB", "bearish", "", source="sentinel", sentinel_id=2)]
    union = sentinels.union_candidates(hand, sents)
    assert union == hand + sents   # same objects, same order — no behavior change absent a collision


def test_revalidate_dormants_dead_motion_keeps_event_origin(convexity_db, tmp_path):
    conn = convexity_db
    # a motion-origin sentinel that has since gone flat, and an event-origin one
    state.record_sentinel_candidate(conn, run_id=None, as_of="2026-05-01T00:00:00+00:00",
                                    symbol="DEAD", direction="bullish", basket="b",
                                    inflection_score=0.5, markers={"has_event": False, "momentum": 0.4})
    state.record_sentinel_candidate(conn, run_id=None, as_of="2026-05-01T00:00:00+00:00",
                                    symbol="EVT", direction="bullish", basket="b",
                                    inflection_score=0.5, markers={"has_event": True, "event_kind": "13D"})
    # a MarketData where DEAD is now flat (no motion)
    from data.cache import PointInTimeCache
    from data.market import MarketData
    start = datetime(2025, 6, 1, tzinfo=UTC)
    as_of = start + timedelta(days=319)
    cache = PointInTimeCache(tmp_path)
    flat = [{"ts": (start + timedelta(days=i)).isoformat(), "open": 10, "high": 10, "low": 10,
             "close": 10.0, "volume": 1e6} for i in range(320)]
    cache.write("bars", "DEAD", flat, coverage_from=start, coverage_through=as_of + timedelta(days=2))
    md = MarketData(cache, client=None, fetch_start=start, fetch_end=as_of + timedelta(days=2))

    n = sentinels.revalidate_active(conn, as_of, market=md, benchmark=None, params=MarkerParams())
    assert n == 1
    assert state.active_sentinel_symbols(conn) == {"EVT"}   # DEAD dormant-ed; event-origin kept
