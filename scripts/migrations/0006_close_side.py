"""Migration 0006 — close-side execution (T2.5).

Under `DRY_RUN=false` the monitor transmits a real `SELL_TO_CLOSE` to flatten a position, so a
position spends a window in a ``status='closing'`` state with a resting sell whose broker id is
``close_order_id`` — reconciled to ``'closed'`` at the actual exit fill (an honest exit price,
not the mid). ``status`` reuses the existing free-text column; this migration only adds the id.
Idempotent.
"""

from __future__ import annotations

import sqlite3


def apply(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("ALTER TABLE convexity_positions ADD COLUMN close_order_id TEXT")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e).lower():
            raise
