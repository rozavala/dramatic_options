"""READ-ONLY #455 cheap-then-repriced report (PREREG_CHEAP_THEN_REPRICED) — the thin CLI over ``cheap_repriced``.

    PYTHONPATH=. venv/bin/python scripts/probe_cheap_repriced.py                 # table, as of today (ET)
    PYTHONPATH=. venv/bin/python scripts/probe_cheap_repriced.py --json          # machine-readable
    PYTHONPATH=. venv/bin/python scripts/probe_cheap_repriced.py --as-of 2026-11-17

Opens the journal with ``dashboard_data.connect_ro`` (a write raises) and the term records through an OFFLINE
point-in-time cache (a write raises; nothing is fetched). No network, no LLM, no file writes; stdout only. Keyless:
never loads ``.env``. Paths from config.json (run from the live checkout) or ``DRAMATIC_DB`` / ``DRAMATIC_CACHE_DIR``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cheap_repriced  # noqa: E402
from config_loader import load_config  # noqa: E402
from dashboard_data import connect_ro, resolve_paths  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Read-only #455 cheap-then-repriced report (PREREG_CHEAP_THEN_REPRICED)")
    ap.add_argument("--json", action="store_true", help="print the full report as JSON instead of the table")
    ap.add_argument("--as-of", default=None, help="report date YYYY-MM-DD (default: today, ET)")
    args = ap.parse_args(argv)

    os.environ.setdefault("DRAMATIC_SKIP_DOTENV", "1")
    config = load_config()
    paths = resolve_paths(config)
    if not paths["db_exists"]:
        print(f"no database at {paths['db_path']}", file=sys.stderr)
        return 2
    as_of = date.fromisoformat(args.as_of) if args.as_of else datetime.now(ZoneInfo("America/New_York")).date()
    from data.cache import PointInTimeCache

    cache = PointInTimeCache(paths["cache_dir"], offline=True)
    conn = connect_ro(paths["db_path"])
    try:
        rep = cheap_repriced.report(conn, cache, config, as_of=as_of)
    finally:
        conn.close()
    print(json.dumps(rep, indent=2, sort_keys=True, default=str) if args.json else cheap_repriced.render(rep))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
