#!/usr/bin/env python3
"""Idempotent SQLite migration runner.

Discovers ``scripts/migrations/NNNN_*.py`` modules (each exposing ``apply(conn)``),
applies any not yet recorded in the ``schema_version`` table, in numeric order, each
inside its own transaction. Safe to run repeatedly — ``deploy.sh`` calls this on every
deploy (mirrors real_options' scripts/run_migrations.py).

    python scripts/run_migrations.py            # apply pending migrations
    python scripts/run_migrations.py --dry-run  # show what would run
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

# Make repo-root modules (state, config_loader) importable when run directly.
sys.path.insert(0, str(REPO_ROOT))

from config_loader import load_config  # noqa: E402
from state import get_db  # noqa: E402

_NUM_RE = re.compile(r"^(\d+)_")


def _discover() -> list[tuple[int, Path]]:
    found = []
    for p in sorted(MIGRATIONS_DIR.glob("*.py")):
        if p.name == "__init__.py":
            continue
        m = _NUM_RE.match(p.name)
        if m:
            found.append((int(m.group(1)), p))
    return sorted(found)


def _load_apply(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "apply"):
        raise RuntimeError(f"Migration {path.name} has no apply(conn) function")
    return mod.apply


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SQLite migrations")
    parser.add_argument("--dry-run", action="store_true", help="Preview without applying")
    args = parser.parse_args()

    conn = get_db(load_config())
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        " version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    conn.commit()
    applied = {
        int(r["version"]) for r in conn.execute("SELECT version FROM schema_version").fetchall()
    }

    pending = [(v, p) for v, p in _discover() if v not in applied]
    if not pending:
        print(f"Migrations up to date (version {max(applied) if applied else 0}).")
        return 0

    if args.dry_run:
        for version, path in pending:
            print(f"[dry-run] would apply {path.name} (version {version})")
        return 0

    for version, path in pending:
        print(f"Applying {path.name} ...")
        apply = _load_apply(path)
        try:
            with conn:  # atomic per migration
                apply(conn)
                conn.execute(
                    "INSERT INTO schema_version (version, applied_at) "
                    "VALUES (?, datetime('now'))",
                    (version,),
                )
        except Exception as e:  # noqa: BLE001 — surface and stop
            print(f"  FAILED {path.name}: {e}", file=sys.stderr)
            return 1
        print(f"  applied version {version}")

    print(f"Done. Now at version {max(v for v, _ in pending)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
