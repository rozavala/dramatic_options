"""READ-ONLY §4 scoring of the §10.13 held-name reads (#508) — the thin CLI over ``held_reads_report``.

    PYTHONPATH=. venv/bin/python scripts/probe_held_reads_report.py           # table
    PYTHONPATH=. venv/bin/python scripts/probe_held_reads_report.py --json    # machine-readable

Opens the journal with ``dashboard_data.connect_ro`` (a write raises). No network, no LLM, no file writes; stdout
only. Keyless: never loads ``.env``. Paths come from config.json (run from the live checkout) or ``DRAMATIC_DB``.
Counts only; no rate prints before 20 scored closes. Measurement only: nothing here acts on a position (§5).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import held_reads_report  # noqa: E402
from config_loader import load_config  # noqa: E402
from dashboard_data import connect_ro, resolve_paths  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Read-only §4 scoring of the §10.13 held-name reads")
    ap.add_argument("--json", action="store_true", help="print the full report as JSON instead of the table")
    args = ap.parse_args(argv)

    os.environ.setdefault("DRAMATIC_SKIP_DOTENV", "1")
    paths = resolve_paths(load_config())
    if not paths["db_exists"]:
        print(f"no database at {paths['db_path']}", file=sys.stderr)
        return 2
    conn = connect_ro(paths["db_path"])
    try:
        rep = held_reads_report.report(conn)
    finally:
        conn.close()
    print(json.dumps(rep, indent=2, sort_keys=True, default=str) if args.json else held_reads_report.render(rep))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
