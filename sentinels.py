"""Sentinel store glue (T3) — project discovered candidates into the council, persist, re-validate.

The discovery scan (``discovery.py``) produces ranked candidates; this module persists them, and
projects the **live** ones into ``themes.Theme`` objects the *unchanged* council judges. The union
order matters: hand-seed FIRST (protected), then sentinels **ranked by inflection_score**, so the
council's ``[:max_candidates]`` truncation drops the *weakest sentinel*, never a hand-seed
conviction or the newest arrival (the v1 silent-truncation bug).

``themes.json`` is never mutated — sentinels live only in the DB with their own lineage/TTL.
"""

from __future__ import annotations

import json
import logging

import state
from discovery import (
    DiscoveryResult,
    MarkerParams,
    MarkerSet,
    clears_gate,
    compute_markers,
    direction_of,
)
from themes import Theme

log = logging.getLogger("sentinels")


def markers_dict(m: MarkerSet) -> dict:
    """The marker values, JSON-ready — also the framer/council grounding corpus (PR2)."""
    return {
        "momentum": m.momentum, "rel_strength": m.rel_strength, "rv": m.rv,
        "rv_slope": m.rv_slope, "mom_recent": m.mom_recent, "rv_rising": m.rv_rising,
        "has_event": m.has_event, "event_kind": m.event_kind,
        "news_count": m.news_count, "price": m.price, "adv_usd": m.adv_usd,
    }


def marker_summary(markers: dict) -> str:
    """A compact numeric summary of the markers (the grounding evidence — has numbers so a
    sentinel pack is `grounded` without news; PR2 feeds this to the framer/council)."""
    bits: list[str] = []
    if markers.get("momentum") is not None:
        bits.append(f"momentum {markers['momentum']:+.2f}")
    if markers.get("rv_slope") is not None:
        bits.append(f"rv_slope {markers['rv_slope']:+.2f}")
    if markers.get("rel_strength") is not None:
        bits.append(f"rel_strength {markers['rel_strength']:+.2f}")
    if markers.get("has_event"):
        bits.append(f"event {markers.get('event_kind') or 'structural'}")
    return "; ".join(bits) or "no numeric markers"


def discovered_to_theme(row) -> Theme:
    """Project a live sentinel row → a council candidate Theme (source='sentinel').

    Carries the deterministic ``markers`` so the council grounds on them (origin-aware), not news."""
    try:
        markers = json.loads(row["markers"]) if row["markers"] else None
    except (ValueError, TypeError):
        markers = None
    return Theme(
        name=row["theme"] or row["basket"] or "discovered",
        symbol=row["symbol"],
        direction=row["direction"],
        thesis=row["seed_thesis"] or "",
        active=True,
        conviction=row["framer_conviction"],
        source="sentinel",
        sentinel_id=int(row["id"]),
        markers=markers,
    )


def active_sentinel_candidates(conn) -> list[Theme]:
    """Live sentinels as council candidates, **ranked by inflection_score desc** (the union order)."""
    return [discovered_to_theme(r) for r in state.active_sentinel_rows(conn)]


def union_candidates(hand_seed: list[Theme], sentinel_themes: list[Theme]) -> list[Theme]:
    """hand-seed FIRST (protected), then ranked sentinels, **DEDUPED on the lineage identity
    ``(symbol, direction)``** (migration 0007 keys a sentinel lineage on `<SYMBOL>|<direction>`) —
    first occurrence wins, so a hand-seed beats a sentinel of the SAME bet (FCX-bullish ⊕ FCX-bullish
    → one, the hand-seed), while OPPOSITE-direction bets (FCX-bullish ⊕ FCX-bearish) are DISTINCT and
    BOTH kept. Removes only a true duplicate (same symbol AND direction = same forward prediction); the
    sentinel lineage stays in ``sentinel_candidates`` (still surfaced + reference-swept). Truncation
    downstream (``council.propose``'s ``[:max_candidates]``) then drops the weakest sentinel, not the newest.

    Single point of dedup for ALL THREE consumers (council, the brain-off shadow null, the no-gate 3A
    null) — they stay aligned on the same deduped union. The per-name TRADE cap stays symbol-only by
    design; whether the system should hold a bull AND a bear on one name is a separate, pre-registered
    concentration question, deliberately not decided here."""
    out: list[Theme] = []
    seen: set[tuple[str, str]] = set()
    for t in list(hand_seed) + list(sentinel_themes):
        key = (t.symbol.upper(), str(t.direction).lower())
        if key not in seen:
            seen.add(key)
            out.append(t)
    return out


def persist_discovery(
    conn, result: DiscoveryResult, *, run_id: int | None, as_of_iso: str, framings: dict | None = None
) -> dict:
    """Persist a scan: surfaced candidates (upsert lineage) + the control cohort. Returns counts.

    ``framings`` (PR2): ``{symbol: {direction, theme, seed_thesis, conviction, structural_vs_fad,
    confound_label, cost_usd, provider, model}}`` from the LLM framer. Absent (PR1) → deterministic
    defaults (direction from motion, theme = basket, seed_thesis = the marker summary)."""
    framings = framings or {}
    n_sent = 0
    for s in result.surfaced:
        sym = s.markers.symbol
        f = framings.get(sym, {})
        md = markers_dict(s.markers)
        state.record_sentinel_candidate(
            conn, run_id=run_id, as_of=as_of_iso, symbol=sym,
            direction=f.get("direction", s.direction), basket=s.markers.basket,
            inflection_score=s.inflection_score, markers=md,
            theme=f.get("theme", s.markers.basket),
            seed_thesis=f.get("seed_thesis", marker_summary(md)),
            framer_conviction=f.get("conviction"), structural_vs_fad=f.get("structural_vs_fad"),
            confound_label=f.get("confound_label"), cost_usd=f.get("cost_usd"),
            provider=f.get("provider"), model=f.get("model"),
        )
        n_sent += 1
    n_ctrl = 0
    for c in result.controls:
        state.record_sentinel_candidate(
            conn, run_id=run_id, as_of=as_of_iso, symbol=c.symbol, direction=direction_of(c),
            basket=c.basket, inflection_score=None, markers=markers_dict(c),
            kind="control", status="control",
        )
        n_ctrl += 1
    return {"sentinels": n_sent, "controls": n_ctrl}


def revalidate_active(conn, as_of, *, market, benchmark, params: MarkerParams) -> int:
    """Cheap daily freshness re-check (closes the intra-week staleness window). An active,
    **motion-origin** sentinel whose motion no longer clears the absolute floor goes dormant
    (drops from the union). Bars-only, no LLM, no cost. Event-origin sentinels are left to TTL
    (a slow structural thesis shouldn't be dropped just because price hasn't moved yet)."""
    n = 0
    for row in state.active_sentinel_rows(conn):
        markers_were_event = False
        try:
            markers_were_event = bool(json.loads(row["markers"] or "{}").get("has_event"))
        except (ValueError, TypeError):
            pass
        if markers_were_event:
            continue
        m = compute_markers(row["symbol"], as_of, market=market, benchmark=benchmark,
                            params=params, basket=row["basket"] or "")
        passed, _ = clears_gate(m, params)
        if not passed:
            state.set_sentinel_status(conn, int(row["id"]), status="dormant")
            n += 1
    return n
