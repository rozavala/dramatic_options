"""Migration 0016 — stamp ``markers_asof`` on council_proposals (finding #1, PREREG_FRESH_INFLECTION_FUNNEL §7.1).

The binding ``at_inflection`` leg is grounded on a sentinel's PERSISTED markers, which refresh only when
the name re-enters the L0 surfaced top-K — so the markers a council judgment ran on can be days-to-weeks
old (measured 1.3–22.7d on the 2026-06-25 L1), while news/fundamentals refresh daily. That staleness was
UN-AUDITABLE at grading time: marker-age was *derivable* (``proposal.as_of − sentinel.last_seen_at``) but
CORRUPTIBLE — ``last_seen_at`` advances when the name re-surfaces, mis-deriving a *past* proposal's age.

This stamps ``markers_asof`` (the sentinel's ``last_seen_at`` AT JUDGMENT) onto the proposal row,
point-in-time and frozen, so marker-age = ``as_of − markers_asof`` is correct forever. NULL for hand-seed
proposals (news-grounded, no markers). The precursor the cheapness-watch needs to compare the cheap-entry
window against the staleness lag (the §7.1 re-open trigger).

Idempotent: SQLite has no ``ADD COLUMN IF NOT EXISTS`` → guard on ``PRAGMA table_info``.
"""

from __future__ import annotations

import sqlite3


def apply(conn: sqlite3.Connection) -> None:
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(council_proposals)").fetchall()}
    if "markers_asof" not in cols:
        conn.execute("ALTER TABLE council_proposals ADD COLUMN markers_asof TEXT")
