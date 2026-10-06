"""Migration 0014 — the OPRA/INDICATIVE gate dual-read log (PREREG_DATA_FEED_OPRA_SEQUENCING §6).

The gate-of-record flips INDICATIVE→OPRA with the dual-read CONCURRENT: every gate evaluation
logs BOTH arms' reads (the OPRA row from the actual verdict; the INDICATIVE shadow row from an
additive, fail-soft fetch), and a post-entries sweep covers the rest of the option-eligible
universe (the §5 tripwire population). The shadow arm NEVER authorizes — it can only tighten
(the date-gated ``veto-dualread-disagree``). A shadow failure writes a structured=0 row with the
error note (the both-arms coverage guard: a silently-empty arm must not masquerade as agreement).

Idempotent CREATE TABLE IF NOT EXISTS.
"""

from __future__ import annotations

import sqlite3


def apply(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS gate_dualread ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  run_id INTEGER,"
        "  evaluated_at TEXT NOT NULL,"
        "  symbol TEXT NOT NULL,"
        "  feed TEXT NOT NULL,"            # 'opra' (of-record) | 'indicative' (shadow)
        "  source TEXT,"                   # 'inline' (an evaluated candidate) | 'sweep'
        "  structured INTEGER,"            # 1 = a structure was selected on this arm
        "  iv_rv REAL,"
        "  otm_skew REAL,"
        "  cheap INTEGER,"
        "  wing TEXT,"
        "  note TEXT,"                     # error note on a failed arm (coverage guard)
        "  created_at TEXT,"
        "  FOREIGN KEY (run_id) REFERENCES runs(id)"
        ")"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_gate_dualread_run ON gate_dualread(run_id, symbol, feed)"
    )
