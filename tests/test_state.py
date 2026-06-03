"""SQLite state: migration idempotency + atomic run journaling."""

import importlib.util
from pathlib import Path

import state

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATION_0001 = REPO_ROOT / "scripts" / "migrations" / "0001_initial.py"
MIGRATION_0009 = REPO_ROOT / "scripts" / "migrations" / "0009_frame_version.py"


def _load_migration(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _migrate(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version "
        "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    _load_migration(MIGRATION_0001).apply(conn)
    # record_run writes runs.frame_version (migration 0009); apply it so the journal insert works.
    _load_migration(MIGRATION_0009).apply(conn)
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (1, datetime('now'))"
    )
    conn.commit()


def test_schema_version_zero_before_init(tmp_path):
    conn = state.connect(tmp_path / "x.db")
    assert state.schema_version(conn) == 0
    conn.close()


def test_migration_creates_runs_and_is_idempotent(tmp_path):
    db = tmp_path / "t.db"
    conn = state.connect(db)
    _migrate(conn)
    _migrate(conn)  # second run must not error or double-bump
    assert state.schema_version(conn) == 1
    rid = state.record_run(conn, mode="PAPER", equity=12345.67, note="t")
    assert rid >= 1
    row = conn.execute("SELECT mode, equity, note FROM runs WHERE id=?", (rid,)).fetchone()
    assert row["mode"] == "PAPER"
    assert row["equity"] == 12345.67
    conn.close()


def test_wal_mode_enabled(tmp_path):
    conn = state.connect(tmp_path / "w.db")
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
    conn.close()


def test_connect_creates_parent_dir(tmp_path):
    nested = tmp_path / "deep" / "nested" / "db.sqlite"
    conn = state.connect(nested)
    assert nested.parent.exists()
    conn.close()
