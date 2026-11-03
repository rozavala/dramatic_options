"""Migration 0021 — the short leg of a debit call vertical (PREREG_THEMATIC_CONVEXITY §5 amendment 2026-11-03b).

An over-cap bullish name may be expressed as a long ≈25%-OTM / short ≈+75%-OTM call vertical. The long leg keeps the
existing columns (``contract_symbol``, ``strike``, ``structure_kind = 'C'``) and ``entry_premium_per_contract`` holds
the NET debit; these two columns carry the short leg. NULL = a single-leg position (every row before this
migration). Added to the real book and to the shadow and no-gate books, which apply the same rule so the null
contrasts stay paired. Idempotent: guarded on ``PRAGMA table_info``; a missing table raises (never a silent skip).
"""

from __future__ import annotations

import sqlite3

_TABLES = ("convexity_positions", "shadow_positions", "fixed_basket_positions")
_COLUMNS = (("short_contract_symbol", "TEXT"), ("short_strike", "REAL"))


def apply(conn: sqlite3.Connection) -> None:
    for table in _TABLES:
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if not cols:
            raise sqlite3.OperationalError(f"no such table: {table}")
        for name, decl in _COLUMNS:
            if name not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
