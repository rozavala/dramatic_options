"""Stage-0 corpus assembly — the point-in-time UNION the Stage-1 synthesis reads.

**PINNED storage decision (PREREG_THEME_GENERATION_STUB, 2026-06-17, measure-first):** the assembled
corpus is the in-memory union of the per-source point-in-time caches — NOT a DB table. Measured volume
is ~1.8k records / ~0.5 MB parsed per scan-date across the four sources (capital_raises ~1,075/quarter
the largest), fetched in ~7s — trivially small, so file-backed PIT reads suffice and a SQLite table +
migration would only re-encode the cache's own as-of semantics in SQL (and couple corpus research data
to the trading journal). **Graduate to a DB ONLY when** one of: indexed cross-source SQL is genuinely
needed (dashboard / curation analytics, e.g. "recipients in DoD awards that also filed a 424B5"); the
union grows to tens of thousands of records; or scored Stage-1 artifacts need relational links to the
raw inputs. Until then, files.

This reader is deliberately CONTENT-AGNOSTIC and deterministic: the caller passes the ``(source, key)``
coords to read (which series / agencies / forms to track is a CONTENT decision — config, pinned later).
NO LLM, NO ranking/summarization (that is Stage-1) — just the as-of union, fail-soft per coord.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from data.cache import PointInTimeCache


def assemble_corpus(
    cache: PointInTimeCache,
    as_of: datetime,
    coords: list[tuple[str, str]],
) -> dict[str, list[dict[str, Any]]]:
    """Union of every ``(source, key)`` coord's records with ``ts <= as_of``, grouped by source.

    Uses the forward-window read (``read_between`` with ``end=as_of``) so a coord with no payload or
    short coverage yields ``[]`` rather than raising — a missing corpus source must never break the
    scheduled assembly. Each source's records are concatenated across its keys and sorted by ``ts``
    (then ``key``) for a deterministic bundle. Every requested source appears as a key in the result
    (possibly empty), so the caller can tell "source had nothing as-of T" from "source not requested".
    """
    out: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for source, key in coords:
        recs = cache.read_between(source, key, None, as_of)
        out.setdefault(source, []).extend((key, r) for r in recs)
    return {
        source: [r for _, r in sorted(tagged, key=lambda kr: (kr[1].get("ts", ""), kr[0]))]
        for source, tagged in out.items()
    }
