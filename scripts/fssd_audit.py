"""FSSD eligible-N audit CLI (PREREG_FSSD.md §8) — the cheap stop-or-go.

COVERAGE ONLY. This computes **no CAR / no returns** and **consumes no Bonferroni k-round**
(exactly like backtest.engine.Backtest.audit). Its sole job is to decide whether the FSSD
event population — and, in --phase corner, the friction ∩ optionable ∩ tradable corner — is
powered enough (≥ fssd.audit.n_min_months distinct calendar months) to justify building the
Stage-1 CAR gate. A STOP here is a valid, cheap finding (PREREG §12).

Phases:
  count   §8a — enumerate 424B5 events, count distinct calendar months. Free, no bulk fetch.
  corner  §8b — (only after 8a PASS) friction/optionability/tradability corner audit.

Usage:
  python scripts/fssd_audit.py --phase count --start 2019-01-01 --end 2024-12-31
  python scripts/fssd_audit.py --phase count --offline      # cache-only replay

Not run in CI (needs network). Parsers/logic are unit-tested offline against fixtures.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config_loader import load_config  # noqa: E402
from data.cache import PointInTimeCache  # noqa: E402
from data.edgar_index import EdgarIndex, month_key  # noqa: E402

BANNER = "FSSD ELIGIBLE-N AUDIT — coverage only · NO CAR computed · NO Bonferroni k consumed"


def _dt(s: str | None, default: str) -> datetime:
    return datetime.fromisoformat(s or default).replace(tzinfo=UTC)


def _edgar_user_agent(config: dict) -> str:
    """EDGAR contact UA: config edgar.user_agent, else EDGAR_USER_AGENT from env/.env."""
    ua = config.get("edgar", {}).get("user_agent") or os.environ.get("EDGAR_USER_AGENT", "")
    if not ua:
        raise SystemExit(
            "ERROR: EDGAR contact User-Agent required. Set EDGAR_USER_AGENT in .env "
            "(e.g. 'dramatic-options you@example.com')."
        )
    return ua


def phase_count(config: dict, start: datetime, end: datetime, *, offline: bool) -> int:
    fssd = config.get("fssd", {})
    forms = fssd.get("event", {}).get("forms", ["424B5"])
    form = forms[0]
    n_min_months = int(fssd.get("audit", {}).get("n_min_months", 24))
    cache_dir = config.get("edgar", {}).get("cache_dir", "data/cache")

    cache = PointInTimeCache(cache_dir, offline=offline)
    edgar = None
    if not offline:
        from data.filings import EdgarClient

        edgar = EdgarClient(
            _edgar_user_agent(config),
            cache_dir=cache_dir,
            rate_limit_per_sec=config.get("edgar", {}).get("rate_limit_per_sec", 8.0),
        )
    idx = EdgarIndex(cache, edgar=edgar, cache_dir=cache_dir, form=form)
    events = idx.enumerate_events(start, end)

    months = Counter(month_key(e["ts"]) for e in events)
    distinct_months = len(months)
    distinct_ciks = len({e["cik"] for e in events})

    print("=" * 78)
    print(BANNER)
    print("=" * 78)
    print(f"PHASE 8a — event count   form={form}   window={start.date()}→{end.date()}"
          f"   {'OFFLINE' if offline else 'online'}")
    print(f"  total {form} events        : {len(events)}")
    print(f"  distinct issuers (CIK)     : {distinct_ciks}")
    print(f"  distinct calendar months   : {distinct_months}   (FSSD resampling unit)")
    print(f"  n_min_months (frozen gate) : {n_min_months}")
    print("  events per calendar month:")
    for ym in sorted(months):
        n = months[ym]
        print(f"    {ym}: {'#' * min(n, 60)} {n}")

    passed = distinct_months >= n_min_months
    print("-" * 78)
    if passed:
        print(f"  RESULT: PASS — {distinct_months} ≥ {n_min_months} distinct months. "
              "Phase 8a power floor cleared; 8b corner audit is justified.")
        print("  NOTE: 8a counts the RAW event population. The binding test is 8b's "
              "friction ∩ optionable ∩ tradable corner × distinct months.")
    else:
        print(f"  RESULT: STOP — only {distinct_months} < {n_min_months} distinct months. "
              "Underpowered at the raw level; do not build 8b. (PREREG §8/§12)")
    print("=" * 78)
    return 0 if passed else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="FSSD eligible-N audit (coverage only)")
    p.add_argument("--phase", choices=["count", "corner"], default="count")
    p.add_argument("--start")
    p.add_argument("--end")
    p.add_argument("--offline", action="store_true", help="cache-only, no network")
    args = p.parse_args(argv)

    config = load_config()
    fssd = config.get("fssd", {})
    start = _dt(args.start, fssd.get("explore_start", "2019-01-01"))
    # default end = lockbox_end (full pre-registered window) so the audit sees all events
    end = _dt(args.end, fssd.get("lockbox_end") or "2024-12-31")

    if args.phase == "count":
        return phase_count(config, start, end, offline=args.offline)
    print("phase 'corner' (8b) not yet implemented — gated on an 8a PASS.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
