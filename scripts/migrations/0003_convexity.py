"""Migration 0003 — thematic cheap-convexity tables (T1).

``convexity_positions`` holds opened paper positions; ``convexity_eval`` is the append-only
**survivorship log** — every evaluated bet (open or veto), the only honest basis for judging
edge vs. luck (PREREG_THEMATIC_CONVEXITY §5). Idempotent.
"""

from __future__ import annotations

import sqlite3


def apply(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS convexity_positions ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  run_id INTEGER,"
        "  opened_at TEXT NOT NULL,"
        "  theme TEXT NOT NULL,"
        "  symbol TEXT NOT NULL,"
        "  direction TEXT NOT NULL,"
        "  structure_kind TEXT NOT NULL,"
        "  contract_symbol TEXT NOT NULL,"
        "  expiry TEXT,"
        "  strike REAL,"
        "  dte INTEGER,"
        "  moneyness REAL,"
        "  contracts INTEGER NOT NULL,"
        "  entry_premium_per_contract REAL NOT NULL,"
        "  total_premium REAL NOT NULL,"
        "  status TEXT NOT NULL DEFAULT 'open',"
        "  mark REAL,"
        "  rationale TEXT,"
        "  FOREIGN KEY (run_id) REFERENCES runs(id)"
        ")"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS convexity_eval ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  run_id INTEGER,"
        "  evaluated_at TEXT NOT NULL,"
        "  theme TEXT NOT NULL,"
        "  symbol TEXT NOT NULL,"
        "  direction TEXT,"
        "  eligible INTEGER,"
        "  gate_cheap INTEGER,"
        "  iv_rv REAL,"
        "  otm_skew REAL,"
        "  decision TEXT NOT NULL,"
        "  position_id INTEGER,"
        "  reasons TEXT,"
        "  created_at TEXT,"
        "  FOREIGN KEY (run_id) REFERENCES runs(id),"
        "  FOREIGN KEY (position_id) REFERENCES convexity_positions(id)"
        ")"
    )
