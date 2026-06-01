"""Watchlist persistence: name + theme signals land in the signals table, ranked."""

import importlib.util
from datetime import datetime
from pathlib import Path

import state
import watchlist
from data.news import to_utc
from divergence import NameSignal, Panel, ThemeSignal

REPO = Path(__file__).resolve().parent.parent
MIGRATIONS = REPO / "scripts" / "migrations"


def _apply(path, conn):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.apply(conn)


def _migrated_config(tmp_path):
    db = tmp_path / "wl.db"
    conn = state.connect(db)
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version "
                 "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
    _apply(MIGRATIONS / "0001_initial.py", conn)
    _apply(MIGRATIONS / "0002_signals.py", conn)
    conn.commit()
    conn.close()
    return {"database": {"path": str(db)}}


def _panel():
    as_of = to_utc(datetime(2024, 1, 2, 21, 0, 0))
    names = [
        NameSignal("JOBY", "evtol", 1.0, 0.0, 1.2, -0.3, 1.5, "FADE", True, {"k": 1}),
        NameSignal("RKLB", "space", 0.0, 1.0, -0.8, 0.6, -1.4, "LONG", True, {"k": 2}),
    ]
    themes = [ThemeSignal("evtol", 1.5, "FADE", 1, ["JOBY"]),
              ThemeSignal("space", -1.4, "LONG", 1, ["RKLB"])]
    return Panel(as_of=as_of, names=names, themes=themes, n_valid=2,
                 n_substance_nonzero=2, skipped=False)


def test_persist_writes_name_and_theme_rows(tmp_path):
    config = _migrated_config(tmp_path)
    run_id = watchlist._persist(config, {"panel": _panel()})
    conn = state.connect(config["database"]["path"])
    try:
        names = conn.execute("SELECT * FROM signals WHERE scope='name' ORDER BY rank").fetchall()
        themes = conn.execute("SELECT * FROM signals WHERE scope='theme'").fetchall()
        assert len(names) == 2 and len(themes) == 2
        assert names[0]["symbol"] == "JOBY" and names[0]["direction"] == "FADE"
        assert names[0]["rank"] == 1 and names[0]["run_id"] == run_id
        # rationale persisted as JSON text
        assert "k" in names[0]["rationale"]
        # theme rows carry no symbol
        assert themes[0]["symbol"] is None
    finally:
        conn.close()
