"""Backtest CLI (plan §B8, §D) — the human-reviewed edge gate.

    # §A0 pre-flight FIRST (coverage only, no IC) — review, then freeze the boundary:
    python -m backtest.run --audit --start 2022-01-01 --end 2024-06-30

    # Explore-set gate run (judged against the pre-registered §A1 bands):
    python -m backtest.run --start 2022-01-01 --end 2024-06-30 --k 1

    # Lockbox — looked at exactly ONCE, records the frozen explore-config hash:
    python -m backtest.run --unlock --k 1

    # Reproduce offline from the warmed cache (network-free, deterministic):
    python -m backtest.run --offline --start 2022-01-01 --end 2024-06-30

NOT run in CI (needs network/data). The no-lookahead/positive/null logic is unit-tested
offline against synthetic fixtures.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtest import metrics  # noqa: E402
from backtest.engine import Backtest  # noqa: E402
from config_loader import load_config, require_alpaca_credentials  # noqa: E402
from data.cache import PointInTimeCache  # noqa: E402
from data.filings import EdgarClient, FilingsData  # noqa: E402
from data.insider import InsiderData  # noqa: E402
from data.market import MarketData  # noqa: E402
from data.news import NewsData  # noqa: E402
from universe import load_universe  # noqa: E402

WARMUP_DAYS = 420


def _dt(s: str | None, default: str | None) -> datetime | None:
    s = s or default
    if s is None:
        return None
    return datetime.fromisoformat(s).replace(tzinfo=UTC)


def _signal_config_hash(config: dict) -> str:
    blob = json.dumps({"signal": config.get("signal"), "universe": config.get("universe"),
                       "backtest": config.get("backtest"), "eligibility": config.get("eligibility")},
                      sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Dramatic Options divergence backtest (edge gate)")
    p.add_argument("--audit", action="store_true", help="§A0 coverage pre-flight only (no IC)")
    p.add_argument("--unlock", action="store_true", help="Run the look-once LOCKBOX window")
    p.add_argument("--offline", action="store_true", help="Cache-only, network-free replay")
    p.add_argument("--start", help="ISO date (default: config explore/lockbox start)")
    p.add_argument("--end", help="ISO date (default: config explore/lockbox end or today)")
    p.add_argument("--k", type=int, default=1, help="signal-iteration rounds consumed (Bonferroni)")
    args = p.parse_args(argv)

    config = load_config()
    bt = config.get("backtest", {})
    if args.unlock:
        start = _dt(args.start, bt.get("lockbox_start"))
        end = _dt(args.end, bt.get("lockbox_end")) or datetime.now(UTC)
    else:
        start = _dt(args.start, bt.get("explore_start"))
        end = _dt(args.end, bt.get("explore_end"))
    if start is None or end is None:
        print("ERROR: start/end required (or set config backtest dates).", file=sys.stderr)
        return 2

    uni = load_universe(config)
    max_h = max([int(bt.get("horizon_days", 21)), *[int(x) for x in bt.get("horizon_sweep_days", [])]])
    fetch_start = start - timedelta(days=WARMUP_DAYS)
    bars_end = end + timedelta(days=math.ceil(max_h * 1.6) + 10)  # forward bars for labels

    cache = PointInTimeCache(config.get("edgar", {}).get("cache_dir", "data/cache"),
                             offline=args.offline)
    client = edgar = None
    if not args.offline:
        key, secret = require_alpaca_credentials(config)
        from data.alpaca_client import AlpacaClient
        client = AlpacaClient(key, secret, paper=config["alpaca"]["paper"])
        edgar = EdgarClient(
            config.get("edgar", {}).get("user_agent", ""),
            cache_dir=config.get("edgar", {}).get("cache_dir", "data/cache"),
            rate_limit_per_sec=config.get("edgar", {}).get("rate_limit_per_sec", 8.0),
        )

    market = MarketData(cache, client=client, fetch_start=fetch_start, fetch_end=bars_end)
    news = NewsData(cache, client=client, fetch_start=fetch_start, fetch_end=end)
    filings = FilingsData(cache, edgar=edgar, fetch_end=end)
    insider = InsiderData(
        cache, edgar=edgar, fetch_start=fetch_start, fetch_end=end,
        ua=config.get("edgar", {}).get("user_agent", ""),
        cache_dir=config.get("edgar", {}).get("cache_dir", "data/cache"),
        rate_limit_per_sec=config.get("edgar", {}).get("rate_limit_per_sec", 8.0),
        exclude_10b5_1=config.get("signal", {}).get("substance", {}).get("exclude_10b5_1", True),
    )
    # Benchmarks must be fetchable for momentum/beta/calendar.
    engine = Backtest(config, uni, cache=cache, market=market, news=news, filings=filings,
                      insider=insider)

    if args.audit:
        report = engine.audit(start, end)
        print(report.to_text())
        return 0

    print(f"GATE RUN  window={start.date()}→{end.date()}  "
          f"{'LOCKBOX' if args.unlock else 'EXPLORE'}  config={_signal_config_hash(config)}")
    if args.unlock:
        print("  ⚠ LOCKBOX is weak-confirmation/veto only — a bare pass does NOT upgrade a band.")
    data = engine.run(start, end)
    print(f"  rebalance dates={data.n_dates}  scored={data.n_dates - data.n_skipped}  "
          f"skipped(n<n_min)={data.n_skipped}")

    results = {"window": [start.isoformat(), end.isoformat()], "mode": "lockbox" if args.unlock
               else "explore", "config_hash": _signal_config_hash(config), "k": args.k,
               "horizons": {}}
    primary = engine.primary_horizon
    for h in data.horizons:
        res = metrics.evaluate(data.panels_for_horizon(h), config=config,
                               k_iterations=args.k, horizon_days=h)
        tag = "PRIMARY (gated)" if h == primary else "sweep (diagnostic)"
        print(f"\n── horizon {h}td — {tag} ──\n{res.to_text()}")
        results["horizons"][h] = res.__dict__

    out_dir = Path(bt.get("artifacts_dir", "data/backtest")) / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(json.dumps(results, default=str, indent=2))
    print(f"\nArtifacts → {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
