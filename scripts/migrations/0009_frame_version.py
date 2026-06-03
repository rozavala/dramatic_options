"""Migration 0009 — per-run frame stamp (pre-T4 cluster exposure cap).

The cluster cap (PREREG_THEMATIC_CONVEXITY §5 amendment 2026-06-03) lands mid-stream — after the
forward record has begun accruing. To audit "was any entry admitted in violation of the THEN-LIVE
frame" (the breach definition) and to segment the T4 payoff analysis by risk regime, each run stamps
the frame/taxonomy version live at that cycle. Positions (real ``convexity_positions`` + the shadow
``shadow_positions``) both carry ``run_id``, so every position joins to this stamp.

Idempotent: SQLite has no ``ADD COLUMN IF NOT EXISTS``, so guard on ``PRAGMA table_info``.
"""

from __future__ import annotations

import sqlite3


def apply(conn: sqlite3.Connection) -> None:
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(runs)").fetchall()}
    if "frame_version" not in cols:
        conn.execute("ALTER TABLE runs ADD COLUMN frame_version TEXT")
