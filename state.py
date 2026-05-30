"""SQLite state/journal store.

Phase 0 creates only the ``runs`` table (+ the ``schema_version`` tracking table,
owned by the migration runner). Later phases add ``signals``/``theses``/``orders``/
``positions`` via their own migrations once those columns are actually designed.

WAL mode is enabled so the future intraday monitor can read while the orchestrator
writes. Writes use the connection as a context manager for atomic transactions.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open (creating parent dirs) a WAL-mode SQLite connection."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def get_db(config: dict[str, Any]) -> sqlite3.Connection:
    """Open the database at the configured path (default data/dramatic_options.db)."""
    db_path = config.get("database", {}).get("path", "data/dramatic_options.db")
    return connect(db_path)


def record_run(
    conn: sqlite3.Connection,
    *,
    mode: str,
    equity: float | None,
    note: str = "",
) -> int:
    """Insert a row into ``runs`` and return its id. Atomic."""
    with conn:  # commits on success, rolls back on exception
        cur = conn.execute(
            "INSERT INTO runs (started_at, mode, equity, note) "
            "VALUES (datetime('now'), ?, ?, ?)",
            (mode, equity, note),
        )
    return int(cur.lastrowid)


def record_signals(
    conn: sqlite3.Connection,
    run_id: int | None,
    rows: list[dict[str, Any]],
) -> int:
    """Insert watchlist signal rows (name- and theme-scope). Returns the count inserted.

    Each row: ``as_of, scope, theme, symbol, narrative, substance, divergence, direction,
    rank, rationale`` (rationale is JSON-encoded by the caller or a dict). Atomic.
    """
    import json

    with conn:  # commits on success, rolls back on exception
        for r in rows:
            rationale = r.get("rationale")
            if not isinstance(rationale, str):
                rationale = json.dumps(rationale, default=str)
            conn.execute(
                "INSERT INTO signals (run_id, as_of, scope, theme, symbol, narrative, "
                "substance, divergence, direction, rank, rationale, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
                (
                    run_id, r["as_of"], r["scope"], r.get("theme"), r.get("symbol"),
                    r.get("narrative"), r.get("substance"), r["divergence"],
                    r.get("direction"), r.get("rank"), rationale,
                ),
            )
    return len(rows)


def schema_version(conn: sqlite3.Connection) -> int:
    """Highest applied migration version, or 0 if none/uninitialized."""
    try:
        row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    except sqlite3.OperationalError:
        return 0
    return int(row["v"]) if row and row["v"] is not None else 0
