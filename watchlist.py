"""Watchlist (plan §B9, task 1.7) — ranked divergence on the seed universe, as-of now.

Computes the divergence panel for the price+ADV-eligible cross-section at the live clock's
``now()``, ranks names and themes, persists them to the ``signals`` journal, and prints.

Eligibility for *inclusion* uses the price+ADV floor (the point-in-time-consistent gate,
plan §B1). The option-liquidity floor (OI + bid/ask%) is the live-only gate; here it is a
**best-effort advisory annotation**, not a hard drop — chain snapshots can be flaky and the
Phase-1 deliverable is the ranked research watchlist. The enforced option-liquidity gate
lives in the Phase-2 options selector.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import timedelta

from clock import LiveClock
from config_loader import ConfigError, load_config, require_alpaca_credentials
from data.cache import PointInTimeCache
from data.filings import EdgarClient, FilingsData
from data.market import MarketData
from data.news import NewsData
from divergence import build_panel
from state import get_db, record_run, record_signals
from universe import check_eligibility, load_universe

WARMUP_DAYS = 420

log = logging.getLogger("watchlist")
if not log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)
    log.propagate = False


def build_watchlist(config: dict, *, clock: LiveClock, client, edgar) -> dict:
    as_of = clock.now()
    uni = load_universe(config)
    fetch_start = as_of - timedelta(days=WARMUP_DAYS)
    cache = PointInTimeCache(config.get("edgar", {}).get("cache_dir", "data/cache"))
    market = MarketData(cache, client=client, fetch_start=fetch_start, fetch_end=as_of)
    news = NewsData(cache, client=client, fetch_start=fetch_start, fetch_end=as_of)
    filings = FilingsData(cache, edgar=edgar, fetch_end=as_of)

    adv_window = config.get("eligibility", {}).get("live", {}).get("adv_window_days", 20)
    eligible = []
    for sym in uni.symbols:
        price = market.latest_price(sym, as_of)
        adv = market.adv_usd(sym, as_of, window=adv_window)
        if check_eligibility(sym, as_of, price=price, adv_usd=adv,
                             config=config, mode="backtest").eligible:
            eligible.append(sym)

    panel = build_panel(as_of, eligible, uni.theme_of, news=news, filings=filings, config=config)
    return {"as_of": as_of, "panel": panel, "n_eligible": len(eligible),
            "n_universe": len(uni.symbols)}


def _persist(config: dict, result: dict) -> int:
    panel = result["panel"]
    conn = get_db(config)
    try:
        run_id = record_run(conn, mode="WATCHLIST", equity=None, note="phase1 watchlist")
        rows = []
        for rank, n in enumerate(panel.names, 1):
            rows.append({
                "as_of": panel.as_of.isoformat(), "scope": "name", "theme": n.theme,
                "symbol": n.symbol, "narrative": n.narrative_z, "substance": n.substance_z,
                "divergence": n.divergence, "direction": n.direction, "rank": rank,
                "rationale": n.rationale,
            })
        for rank, t in enumerate(panel.themes, 1):
            rows.append({
                "as_of": panel.as_of.isoformat(), "scope": "theme", "theme": t.theme,
                "symbol": None, "narrative": None, "substance": None,
                "divergence": t.divergence, "direction": t.direction, "rank": rank,
                "rationale": {"members": t.members, "n_members": t.n_members},
            })
        record_signals(conn, run_id, rows)
        return run_id
    finally:
        conn.close()


def _print(result: dict) -> None:
    panel = result["panel"]
    log.info("Watchlist as-of %s  (eligible %d/%d)", result["as_of"].isoformat(),
             result["n_eligible"], result["n_universe"])
    if panel.skipped:
        log.warning("Cross-section too thin (%s) — no ranking produced.", panel.reason)
        return
    log.info("Sign convention: divergence = z(narrative) − z(substance); "
             ">0 = FADE (hype), <0 = LONG (under-radar).")
    log.info("── NAMES (most-LONG first) ──")
    for rank, n in enumerate(panel.names, 1):
        log.info("  %2d. %-5s [%-11s] div=%+.2f  narr_z=%+.2f subst_z=%+.2f  %s",
                 rank, n.symbol, n.theme or "?", n.divergence, n.narrative_z,
                 n.substance_z, n.direction)
    log.info("── THEMES (median divergence) ──")
    for t in panel.themes:
        log.info("  %-12s div=%+.2f  (%d members)  %s",
                 t.theme, t.divergence, t.n_members, t.direction)


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description="Dramatic Options divergence watchlist").parse_args(argv)
    config = load_config()
    try:
        key, secret = require_alpaca_credentials(config)
    except ConfigError as e:
        log.error("%s", e)
        return 1
    from data.alpaca_client import AlpacaClient
    client = AlpacaClient(key, secret, paper=config["alpaca"]["paper"])
    edgar = EdgarClient(
        config.get("edgar", {}).get("user_agent", ""),
        cache_dir=config.get("edgar", {}).get("cache_dir", "data/cache"),
        rate_limit_per_sec=config.get("edgar", {}).get("rate_limit_per_sec", 8.0),
    )
    try:
        result = build_watchlist(config, clock=LiveClock(client), client=client, edgar=edgar)
    except Exception as e:  # noqa: BLE001 — fail-closed, report cleanly
        log.error("Watchlist build failed: %s", e)
        return 1
    run_id = _persist(config, result)
    _print(result)
    log.info("Persisted to signals (run #%d).", run_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
