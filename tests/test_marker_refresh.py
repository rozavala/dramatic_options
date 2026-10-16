"""council.marker_refresh — built behind a switch, default OFF (records/2026-10-16_marker_freshness_PROPOSAL.md).

Off must be byte-identical (same candidate objects, same pack lines, no model_mix key); on, sentinel markers are
recomputed from current bars and dated, the event leg is carried over, hand-seeds and the persisted markers are
untouched, and a name without bars falls back to its persisted markers.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

import discovery
import marker_refresh
from council.context import _marker_evidence, sentinel_context_pack
from themes import Theme

AS_OF = datetime(2026, 10, 15, 19, 45, tzinfo=UTC)
PERSISTED = {"momentum": 1.218, "rel_strength": 1.021, "rv": 0.633, "rv_slope": 0.193, "mom_recent": 0.281,
             "rv_rising": 0.118, "has_event": True, "event_kind": "424B5", "news_count": 0, "price": 35.47,
             "adv_usd": 59691915.9}


def _sentinel(sym="ERO", markers=PERSISTED, sid=7):
    return Theme("copper supply", sym, "bullish", "discovery summary", source="sentinel", sentinel_id=sid,
                 markers=dict(markers), basket="copper_supply")


def _cfg(mode):
    return {"council": {"marker_refresh": mode}, "discovery": {"markers": {}}}


@pytest.fixture
def market():
    return discovery.synthetic_market(["ERO", "SPY"], AS_OF, movers=["ERO"])


@pytest.mark.parametrize("raw,want", [(None, "off"), ("off", "off"), ("FRESH", "fresh"), ("both", "both"),
                                      ("yes", "off"), (True, "off")])
def test_mode_is_off_unless_named(raw, want):
    cfg = {"council": {} if raw is None else {"marker_refresh": raw}}
    assert marker_refresh.mode(cfg) == want
    assert (marker_refresh.stamp(cfg) is None) == (want == "off")


def test_off_returns_the_same_list_untouched(market):
    cands = [_sentinel()]
    out, counts = marker_refresh.refresh_candidates(cands, config=_cfg("off"), conn=None, as_of=AS_OF,
                                                    market=market, benchmark="SPY")
    assert out is cands and out[0].markers == PERSISTED and counts["refreshed"] == 0


def test_fresh_recomputes_dates_and_keeps_the_event_leg(market):
    hand = Theme("ai", "NVDA", "bullish", "operator thesis")
    sent = _sentinel()
    out, counts = marker_refresh.refresh_candidates([hand, sent], config=_cfg("fresh"), conn=None, as_of=AS_OF,
                                                    market=market, benchmark="SPY")
    assert out[0] is hand                                            # hand-seeds never touched
    m = out[1].markers
    assert m["refreshed_asof"] == "2026-10-15" and m["momentum"] != PERSISTED["momentum"]
    assert m["has_event"] is True and m["event_kind"] == "424B5"     # the L0's structural call carried over
    assert "at_surfacing" not in m
    assert sent.markers == PERSISTED                                 # the persisted markers never mutated
    assert counts == {"mode": "fresh", "refreshed": 1, "kept": 0}


def test_both_adds_the_dated_surfacing_values(market, monkeypatch):
    monkeypatch.setattr(marker_refresh.state, "sentinel_by_id",
                        lambda _conn, sid: {"last_seen_at": "2026-09-13T12:00:07+00:00"} if sid == 7 else None)
    out, _ = marker_refresh.refresh_candidates([_sentinel()], config=_cfg("both"), conn=object(), as_of=AS_OF,
                                               market=market, benchmark="SPY")
    m = out[0].markers
    assert m["at_surfacing_asof"] == "2026-09-13"
    assert m["at_surfacing"]["mom_recent"] == PERSISTED["mom_recent"] and "has_event" not in m["at_surfacing"]


def test_a_name_without_bars_keeps_its_persisted_markers(market):
    out, counts = marker_refresh.refresh_candidates([_sentinel(sym="NOBARS")], config=_cfg("fresh"), conn=None,
                                                    as_of=AS_OF, market=market, benchmark="SPY")
    assert out[0].markers == PERSISTED and counts["kept"] == 1 and counts["refreshed"] == 0


def test_no_market_is_a_no_op():
    cands = [_sentinel()]
    out, _ = marker_refresh.refresh_candidates(cands, config=_cfg("fresh"), conn=None, as_of=AS_OF, market=None,
                                               benchmark="SPY")
    assert out is cands


def test_off_shape_markers_render_exactly_as_before():
    # The pre-switch render, pinned: no markers_computed / at_surfacing line when the keys are absent.
    assert _marker_evidence(PERSISTED) == [
        "momentum_12m +1.218", "momentum_recent_3m +0.281", "rel_strength_12m +1.021", "rv_reexpansion_1y +0.193",
        "rv_accel_3m +0.118", "rv_annualized +0.633", "structural_event 424B5", "price 35.47", "adv_usd 59691916",
    ]


def test_refreshed_markers_render_dated_and_both_shows_surfacing():
    fresh = {**PERSISTED, "mom_recent": -0.13, "refreshed_asof": "2026-10-15"}
    lines = _marker_evidence(fresh)
    assert lines[0] == "markers_computed 2026-10-15" and "momentum_recent_3m -0.130" in lines
    both = {**fresh, "at_surfacing": {k: v for k, v in PERSISTED.items() if k != "has_event"},
            "at_surfacing_asof": "2026-09-13"}
    lines = _marker_evidence(both)
    assert "momentum_recent_3m -0.130" in lines and "momentum_recent_3m +0.281 at_surfacing 2026-09-13" in lines


def test_the_pack_is_unchanged_when_off():
    pack = sentinel_context_pack(_sentinel(), as_of=AS_OF)
    assert pack.headlines == _marker_evidence(PERSISTED) and not any("at_surfacing" in h for h in pack.headlines)


def test_orchestrator_hook_is_a_no_op_when_off_or_offline():
    import orchestrator

    cands = [_sentinel()]
    assert orchestrator._refresh_council_markers(None, cands, config=_cfg("off"), client=object(), cache=object(),
                                                 as_of=AS_OF, run_id=None) is cands
    assert orchestrator._refresh_council_markers(None, cands, config=_cfg("fresh"), client=None, cache=None,
                                                 as_of=AS_OF, run_id=None) is cands   # demo: no client
