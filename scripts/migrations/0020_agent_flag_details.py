"""Migration 0020 — ``council_agent_outputs.flagged_details`` (#402): WHICH claims the authenticity filter flagged.

``council/filters.py::authenticity_scan`` builds one detail string per flag (``unsupported figure: 2026``,
``unsupported quote: "…"``), but only the count reached ``flagged_unsupported``. A grader could see that a
conviction was dampened, never which claim did it (L1 #1867 AG adversary, L1 #1884 FRO adversary and SMR strategist).

Record-only: a JSON list stored beside the count; no conviction, gate, prompt or stamp changes. Rows recorded before
this migration keep NULL (unknown). Idempotent: guarded on ``PRAGMA table_info``. A missing table is NOT skipped: the
ALTER then raises, so ``schema_version`` can never record 20 without the column.
"""

from __future__ import annotations

import sqlite3


def apply(conn: sqlite3.Connection) -> None:
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(council_agent_outputs)").fetchall()}
    if "flagged_details" not in cols:
        conn.execute("ALTER TABLE council_agent_outputs ADD COLUMN flagged_details TEXT")
