"""Sentinel framer + origin-aware grounding (T3 PR2).

The keystone: a DISCOVERED (pre-news) candidate grounds the framer AND the council on its
deterministic MARKERS, not news — so it is NOT NEUTRAL-dropped for lack of coverage. Plus the
framer as a skeptic (drops artifacts / NEUTRAL) and fail-closed-to-zero on budget.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import risk
from clock import FixedClock
from council.context import build_context_pack, sentinel_context_pack
from council.council import propose
from council.router import FakeRouter
from council.sentinel import frame_candidates, parse_framer, sentinel_fake_responder
from discovery import MarkerSet, Surfaced
from themes import Theme

AS_OF = datetime(2026, 6, 2, tzinfo=UTC)
CLOCK = FixedClock(AS_OF)
MARKERS = {"momentum": 0.42, "rel_strength": 0.10, "rv_slope": 0.31, "has_event": False,
           "event_kind": None, "news_count": 0, "price": 30.0, "adv_usd": 1.0e8}


def _no_kill(monkeypatch):
    monkeypatch.delenv("KILL", raising=False)
    monkeypatch.setattr(risk, "KILL_FILE", Path("/nonexistent/KILL"))


def _surf(sym, *, mom=0.42, has_event=False):
    m = MarkerSet(sym, "ai_compute", mom, 0.1, 0.4, 0.31, has_event,
                  "13D" if has_event else None, 0, 30.0, 1.0e8)
    return Surfaced(m, "bullish", 1.0, "momentum")


# ── origin-aware grounding (the keystone fix) ─────────────────────────────────────────────────


def test_sentinel_grounds_on_markers_not_news():
    cand = Theme("ai_compute", "SMCI", "bullish", "discovery hypothesis",
                 source="sentinel", sentinel_id=1, markers=MARKERS)
    pack = build_context_pack(cand, news=None, as_of=AS_OF)  # news ignored for sentinels
    assert pack.grounded is True                              # pre-news, but grounded on markers
    assert any("momentum" in h for h in pack.headlines)
    assert "not news" in " ".join(pack.notes)


def test_sentinel_without_markers_is_ungrounded():
    cand = Theme("x", "Y", "bullish", "", source="sentinel", sentinel_id=2, markers={})
    pack = sentinel_context_pack(cand, as_of=AS_OF)
    assert pack.grounded is False     # no markers → nothing to adjudicate → correct early-exit


def test_hand_seed_unchanged_grounds_on_news():
    class _News:
        def headlines_asof(self, symbol, as_of):
            return [{"headline": "FCX up 5% on grid demand", "ts": "2026-06-01T00:00:00+00:00"}]
    cand = Theme("copper", "FCX", "bullish", "operator thesis")  # source defaults hand-seed
    pack = build_context_pack(cand, news=_News(), as_of=AS_OF)
    assert pack.grounded is True and "FCX up 5%" in " ".join(pack.headlines)


# ── the framer (a skeptic) ────────────────────────────────────────────────────────────────────


def test_framer_frames_grounded_topk():
    fr = frame_candidates([_surf("SMCI"), _surf("VRT")],
                          FakeRouter(responder=sentinel_fake_responder), as_of=AS_OF)
    assert set(fr) == {"SMCI", "VRT"}
    assert fr["SMCI"]["confound_label"] == "real_inflection"
    assert fr["SMCI"]["conviction"] == "HIGH" and fr["SMCI"]["direction"] == "bullish"


def test_framer_over_budget_frames_nothing():
    r = FakeRouter(responder=sentinel_fake_responder, cap_usd=0.0)  # at cap → fail-closed
    assert frame_candidates([_surf("SMCI")], r, as_of=AS_OF) == {}


def test_framer_drops_ungrounded_without_spend():
    empty = Surfaced(MarkerSet("EMPTY", "b", None, None, None, None, False, None, 0, None, None),
                     "bullish", 0.0, "none")
    r = FakeRouter(responder=sentinel_fake_responder)
    assert frame_candidates([empty], r, as_of=AS_OF) == {}
    assert r.ledger.calls == 0        # no markers → no LLM spend


def test_framer_drops_artifact_and_neutral():
    def responder(role, system, user):
        if "ART" in user:
            return json.dumps({"confound": "artifact", "direction": "bullish", "theme": "b",
                               "confidence": "HIGH", "seed_thesis": "stale far-OTM quote"})
        return json.dumps({"confound": "real_inflection", "direction": "bullish", "theme": "b",
                           "confidence": "NEUTRAL", "seed_thesis": "unclear"})
    fr = frame_candidates([_surf("ART"), _surf("NEU")], FakeRouter(responder=responder), as_of=AS_OF)
    assert fr == {}                   # the skeptic drops a data artifact AND a NEUTRAL verdict


def test_parse_framer_coerces_and_fails_closed():
    assert parse_framer("not json").get("confidence") == "NEUTRAL"
    # A non-NEUTRAL framing with an INVALID confound is incoherent (the framer's whole job IS naming
    # the confound) → fail-closed NEUTRAL + parse_error (P1-#1 stricter validation).
    d = parse_framer(json.dumps({"confound": "weird", "confidence": "high"}))
    assert d["confound"] is None and d["confidence"] == "NEUTRAL" and d["parse_error"] is True
    # A valid non-NEUTRAL framing is preserved.
    ok = parse_framer(json.dumps({"confound": "real_inflection", "direction": "bullish", "confidence": "high"}))
    assert ok["confound"] == "real_inflection" and ok["confidence"] == "HIGH"


# ── the council judges a discovered candidate (no NEUTRAL-drop for lack of news) ──────────────


def test_council_judges_sentinel_candidate_via_marker_grounding(monkeypatch):
    _no_kill(monkeypatch)
    cand = Theme("ai_compute", "SMCI", "bullish", "discovery hypothesis: momentum +0.42",
                 source="sentinel", sentinel_id=5, markers=MARKERS)
    # demo=False → real grounding path (build_context_pack → sentinel_context_pack on markers).
    props = propose([cand], router=FakeRouter(),
                    config={"council": {"max_candidates": 12, "news_lookback_days": 90}},
                    clock=CLOCK, news=None, demo=False)
    assert len(props) == 1
    assert props[0].conviction != "NEUTRAL"     # judged on markers, NOT dropped for lack of news
    assert props[0].sentinel_id == 5            # provenance threaded into the proposal
