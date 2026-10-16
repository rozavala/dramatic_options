"""L1 marker refresh for the council pack — BUILT BEHIND A SWITCH, default OFF.

The council judges ``at_inflection`` partly on a sentinel's price markers (12-month momentum, relative strength,
3-month momentum, realized-vol slope/acceleration). Those are the markers persisted when the weekly L0 last
surfaced the name — a median ~31 days old at judgment — while news and fundamentals refresh every L1
(PREREG_FRESH_INFLECTION_FUNNEL §7.1). ``records/2026-10-16_marker_freshness_PROPOSAL.md`` proposes
recomputing them at each L1, for the operator to decide at the F4 review (≈ 2026-11-04).

``council.marker_refresh`` (config):
  * ``"off"`` (default) — candidates pass through untouched; the pack and ``runs.model_mix`` are byte-identical.
  * ``"fresh"`` — each sentinel's markers are recomputed from current bars (``discovery.compute_markers``, the
    L0's own function) and rendered with the date they were computed.
  * ``"both"`` — as ``fresh``, plus the markers as of surfacing, dated, so the move since surfacing is visible.

Discipline:
  * Council path only. The L0 funnel, the framer, the shadow/3A null unions and the persisted
    ``sentinel_candidates.markers`` are never changed.
  * The structural-event leg (``has_event``/``event_kind``) is the L0's call and is carried over unchanged.
  * Fail-soft per name: no bars → the persisted markers render as today (a refresh never blocks a cycle).
  * Turning it on is a pack-shape change: ``runs.model_mix.markers = l1_refresh_<mode>_v1``, record-segmenting.
"""
from __future__ import annotations

import dataclasses
import logging
from datetime import datetime

import state
from discovery import MarkerParams, compute_markers
from sentinels import markers_dict

log = logging.getLogger("marker_refresh")

MODES = ("off", "fresh", "both")
# The L0 owns the structural-event leg; a price refresh never re-decides it.
_EVENT_KEYS = ("has_event", "event_kind", "news_count")


def mode(config: dict) -> str:
    """The configured mode; anything unknown is ``off`` (never on by accident)."""
    m = str((config.get("council", {}) or {}).get("marker_refresh", "off") or "off").strip().lower()
    return m if m in MODES else "off"


def stamp(config: dict) -> str | None:
    """The ``runs.model_mix.markers`` value, or None when off (the model_mix stays byte-identical)."""
    m = mode(config)
    return None if m == "off" else f"l1_refresh_{m}_v1"


def refresh_candidates(candidates: list, *, config: dict, conn, as_of: datetime, market,
                       benchmark: str | None) -> tuple[list, dict]:
    """Return (candidates, counts). Off, or no market → the same list object, untouched.

    ``market`` is duck-typed like the L0's ``data/market.py:MarketData`` (``closes_asof``/``momentum``/
    ``adv_usd``). Only ``source == 'sentinel'`` candidates with persisted markers are refreshed."""
    m = mode(config)
    counts = {"mode": m, "refreshed": 0, "kept": 0}
    if m == "off" or market is None:
        return candidates, counts
    params = MarkerParams(**dict((config.get("discovery", {}) or {}).get("markers", {})))
    out = []
    for c in candidates:
        persisted = getattr(c, "markers", None)
        if getattr(c, "source", None) != "sentinel" or not persisted:
            out.append(c)
            continue
        try:
            ms = compute_markers(c.symbol, as_of, market=market, benchmark=benchmark, params=params,
                                 basket=getattr(c, "basket", None) or "")
            fresh = markers_dict(ms)
        except Exception as e:  # noqa: BLE001 — fail-soft: the persisted markers render as before
            log.warning("marker_refresh: %s kept persisted markers: %s", c.symbol, e)
            fresh = None
        if not fresh or fresh.get("momentum") is None:
            counts["kept"] += 1
            out.append(c)
            continue
        fresh.update({k: persisted.get(k) for k in _EVENT_KEYS if k in persisted})
        fresh["refreshed_asof"] = as_of.date().isoformat()
        if m == "both":
            row = state.sentinel_by_id(conn, c.sentinel_id) if c.sentinel_id is not None else None
            fresh["at_surfacing"] = {k: v for k, v in persisted.items() if k not in _EVENT_KEYS}
            fresh["at_surfacing_asof"] = (str(row["last_seen_at"])[:10] if row and row["last_seen_at"] else None)
        counts["refreshed"] += 1
        out.append(dataclasses.replace(c, markers=fresh))
    return out, counts
