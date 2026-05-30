"""Migration 0001 — initial schema.

Creates only the ``runs`` table. Other tables (signals, theses, orders, positions)
are deliberately deferred to the phases that design their columns (P2–P4), each in
its own migration.
"""

from __future__ import annotations

import sqlite3


def apply(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at  TEXT NOT NULL,
            mode        TEXT NOT NULL,
            equity      REAL,
            note        TEXT
        )
        """
    )
