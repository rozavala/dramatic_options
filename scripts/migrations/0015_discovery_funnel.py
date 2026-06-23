"""Migration 0015 — per-run discovery-funnel version stamp (PREREG_FRESH_INFLECTION_FUNNEL §8/§9).

The fresh-inflection funnel re-target (re-rank the discovery prescreen by rv_rising + recent
momentum instead of trailing-magnitude, + an additive freshness surface disjunct + horizon-labeled
grounding markers) is a measurement-regime change to the discovery prescreen. Each run stamps the
live funnel version so the THREE forward-scored layers that join on ``run_id`` — the discovery null
(``sentinel_scoring`` surfaced-vs-control TAIL), the framer score, and the council Brier — segment
OLD (legacy/NULL = the pre-re-target funnel) from NEW (``"fresh_v1"``), never pooling two funnels
(companion to ``frame_version``/0009 + ``data_feed``/0013 + ``model_mix``/0011).

``frame_version`` can NOT carry this — it hashes only ``{convexity_book, convexity_gate,
convexity_exits, kill_rule}`` (config_loader.frame_version), not ``discovery.markers``, so a
funnel-knob change does not move it. Hence a dedicated column (the 0009/0011/0013 precedent).

Idempotent: SQLite has no ``ADD COLUMN IF NOT EXISTS`` → guard on ``PRAGMA table_info``.
"""

from __future__ import annotations

import sqlite3


def apply(conn: sqlite3.Connection) -> None:
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(runs)").fetchall()}
    if "discovery_funnel" not in cols:
        conn.execute("ALTER TABLE runs ADD COLUMN discovery_funnel TEXT")
