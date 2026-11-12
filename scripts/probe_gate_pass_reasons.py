"""READ-ONLY gate pass-reason audit (#454) — the thin CLI over ``gate_audit``.

    PYTHONPATH=. venv/bin/python scripts/probe_gate_pass_reasons.py --last 5           # table
    PYTHONPATH=. venv/bin/python scripts/probe_gate_pass_reasons.py --last 5 --json    # machine-readable
    PYTHONPATH=. venv/bin/python scripts/probe_gate_pass_reasons.py --date 2026-11-06 --names

Opens the journal with ``dashboard_data.connect_ro`` (a write raises) and reads bars from the point-in-time cache
with ``offline=True`` and no client, so a cache miss is an "unknown" row, never a fetch. No network, no LLM, no
file writes; stdout only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gate_audit  # noqa: E402
from config_loader import load_config  # noqa: E402
from dashboard_data import connect_ro, resolve_paths  # noqa: E402


def no_fetch_closes(cache_dir: str) -> gate_audit.ClosesFor:
    """closes_for over an OFFLINE cache: ``MarketData(client=None)`` never fetches, and ``offline=True`` makes any
    write raise. The read asks as of the END of the sweep date in New York; ``gate_audit`` re-filters by bar date."""
    from data.cache import PointInTimeCache
    from data.market import MarketData

    cache = PointInTimeCache(cache_dir, offline=True)
    now = datetime.now(ZoneInfo("UTC"))
    market = MarketData(cache, client=None, fetch_start=now, fetch_end=now)
    et = ZoneInfo("America/New_York")

    def closes_for(symbol: str, sweep_date: date):
        as_of = datetime.combine(sweep_date + timedelta(days=1), time(0), tzinfo=et) - timedelta(microseconds=1)
        return market.closes_asof(symbol, as_of)

    return closes_for


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Read-only pass-reason audit of the cheapness gate (#454)")
    ap.add_argument("--date", action="append", help="a sweep date YYYY-MM-DD (repeatable); default every date")
    ap.add_argument("--last", type=int, default=None, help="keep only the most recent N sweep dates")
    ap.add_argument("--names", action="store_true", help="list every structured row in the table")
    ap.add_argument("--json", action="store_true", help="print the full report as JSON instead of the table")
    args = ap.parse_args(argv)

    # Keyless, like the dashboard: this probe never needs a secret, so it never loads .env. Paths come from
    # config.json (relative to the CWD: run from the live checkout) or the DRAMATIC_DB / DRAMATIC_CACHE_DIR overrides.
    os.environ.setdefault("DRAMATIC_SKIP_DOTENV", "1")
    config = load_config()
    paths = resolve_paths(config)
    if not paths["db_exists"]:
        print(f"no database at {paths['db_path']}", file=sys.stderr)
        return 2
    conn = connect_ro(paths["db_path"])
    try:
        report = gate_audit.audit(conn, config, no_fetch_closes(paths["cache_dir"]), dates=args.date, last=args.last)
    finally:
        conn.close()
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else gate_audit.render(report, names=args.names))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
