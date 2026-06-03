"""Root conftest — makes the flat-layout top-level modules importable in tests.

pytest prepends the directory containing the first conftest.py onto sys.path, so
``import config_loader``, ``import state``, ``import data.alpaca_client`` etc. all
resolve from the repo root without an installed package.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

import state

_ROOT = Path(__file__).resolve().parent


def _apply_migration(conn, name: str) -> None:
    path = _ROOT / "scripts" / "migrations" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.apply(conn)


@pytest.fixture
def convexity_db(tmp_path):
    """A migrated SQLite connection with runs + convexity + council + sentinel + shadow tables."""
    conn = state.connect(tmp_path / "t.db")
    _apply_migration(conn, "0001_initial.py")
    _apply_migration(conn, "0003_convexity.py")
    _apply_migration(conn, "0004_convexity_mtm.py")
    _apply_migration(conn, "0005_council.py")
    _apply_migration(conn, "0006_close_side.py")
    _apply_migration(conn, "0007_sentinels.py")
    _apply_migration(conn, "0008_shadow_book.py")
    _apply_migration(conn, "0009_frame_version.py")
    _apply_migration(conn, "0010_fixed_basket.py")
    _apply_migration(conn, "0011_council_health.py")
    try:
        yield conn
    finally:
        conn.close()
