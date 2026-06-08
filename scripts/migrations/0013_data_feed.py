"""Migration 0013 — per-run data-feed provenance stamp (the data-feed upgrade, PR1).

PR1 wires ``config.data_feed`` → the providers (the previously-dead knob) and flips the equity
bars IEX→SIP for the gate's RV input **and** the discovery prescreen markers — a gate-INPUT /
candidate-funnel data-provenance change (verdicts near ``iv/rv=1.2`` and the surfaced sentinel set
can shift; that's the expected SIP effect, not a regression). Each run stamps the resolved feed
roles ``{equity_bars, option_gate, option_monitor}`` so the forward record segments by data regime
(companion to ``frame_version`` / 0009 + ``model_mix`` / 0011), and the eventual PR3 OPRA-gate flip
is auditable.

Idempotent: SQLite has no ``ADD COLUMN IF NOT EXISTS`` → guard on ``PRAGMA table_info``.
"""

from __future__ import annotations

import sqlite3


def apply(conn: sqlite3.Connection) -> None:
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(runs)").fetchall()}
    if "data_feed" not in cols:
        conn.execute("ALTER TABLE runs ADD COLUMN data_feed TEXT")
