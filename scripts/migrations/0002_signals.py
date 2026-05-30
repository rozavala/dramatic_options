"""Migration 0002 — signals table.

Phase 1 is the phase that *produces* signals, so designing this schema here is correct
(unlike orders/theses, which are deferred to the phases that design their columns). Stores
one row per name- or theme-scope divergence signal emitted by the watchlist, linked to the
``runs`` row that produced it.
"""

from __future__ import annotations

import sqlite3


def apply(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS signals (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id       INTEGER REFERENCES runs(id),
            as_of        TEXT NOT NULL,
            scope        TEXT NOT NULL,            -- 'name' | 'theme'
            theme        TEXT,
            symbol       TEXT,                     -- NULL for theme-scope rows
            narrative    REAL,
            substance    REAL,
            divergence   REAL NOT NULL,
            direction    TEXT,                     -- LONG | FADE | NEUTRAL
            rank         INTEGER,
            rationale    TEXT,                     -- JSON
            created_at   TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_as_of ON signals(as_of)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol)")
