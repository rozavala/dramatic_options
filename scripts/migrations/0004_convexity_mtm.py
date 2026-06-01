"""Migration 0004 — mark-to-market + exit + reconciliation columns (T1.5).

Adds the columns the L2 monitor needs to mark open positions, close them (expiry /
profit-take / time-stop) with realized P&L, and reconcile a real Alpaca paper order
(`order_id`, `status='pending'`). The `mark` and `status` columns already exist from 0003.
Idempotent: each ADD COLUMN is guarded against re-run.
"""

from __future__ import annotations

import sqlite3

_NEW_COLUMNS = [
    ("marked_at", "TEXT"),
    ("realized_pnl", "REAL"),
    ("closed_at", "TEXT"),
    ("exit_reason", "TEXT"),
    ("order_id", "TEXT"),
]


def apply(conn: sqlite3.Connection) -> None:
    for name, decl in _NEW_COLUMNS:
        try:
            conn.execute(f"ALTER TABLE convexity_positions ADD COLUMN {name} {decl}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise
