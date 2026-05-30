"""Orchestrator — Phase 0 skeleton.

Run-once: check the kill switch, connect to Alpaca (paper), print account equity,
record a run row, exit cleanly. The long-running asyncio loop (L1 schedule + L2
monitor) is built in later phases. Paper-only; ``--live`` is gated and a no-op here.

    python orchestrator.py                 # connect to paper, print equity
    touch KILL && python orchestrator.py   # halts before any work
"""

from __future__ import annotations

import argparse
import logging
import sys

from clock import LiveClock
from config_loader import ConfigError, live_allowed, load_config, require_alpaca_credentials
from data.alpaca_client import AlpacaClient
from risk import kill_switch_active
from state import get_db, record_run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("orchestrator")


def _banner(mode: str, data_feed: str) -> None:
    bar = "=" * 60
    log.info(bar)
    log.info("  DRAMATIC OPTIONS — %s MODE   (data feed: %s)", mode, data_feed)
    log.info(bar)


def run_once(cli_live: bool = False) -> int:
    # 1. Kill switch first — before any connection or work.
    if kill_switch_active():
        log.warning("KILL switch engaged — halting. Remove the KILL file/env to resume.")
        return 0

    config = load_config()
    is_live = live_allowed(config, cli_live)
    mode = "LIVE" if is_live else "PAPER"
    data_feed = config.get("safety", {}).get("data_feed", "indicative")
    _banner(mode, data_feed)

    if cli_live and not is_live:
        log.warning(
            "--live requested but gates not satisfied (need PAPER=false AND "
            "LIVE_TRADING_ENABLED=true). Continuing in PAPER mode."
        )

    # 2. Connect (paper) and read equity.
    try:
        api_key, secret_key = require_alpaca_credentials(config)
    except ConfigError as e:
        log.error("%s", e)
        return 1

    client = AlpacaClient(api_key, secret_key, paper=config["alpaca"]["paper"])
    _clock = LiveClock(client)  # wired for later phases (intraday loop)
    try:
        equity = client.get_equity()
        market_open = client.is_market_open()
    except Exception as e:  # noqa: BLE001 — fail-closed, report cleanly
        log.error("Could not reach Alpaca: %s", e)
        return 1

    log.info("Account equity: $%,.2f", equity)
    log.info("Market open: %s", market_open)

    # 3. Journal the run.
    conn = get_db(config)
    try:
        run_id = record_run(conn, mode=mode, equity=equity, note="phase0 run_once")
        log.info("Recorded run #%d", run_id)
    finally:
        conn.close()

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dramatic Options orchestrator")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Request live trading (still requires PAPER=false AND "
        "LIVE_TRADING_ENABLED=true). No-op trading path in Phase 0.",
    )
    args = parser.parse_args(argv)
    return run_once(cli_live=args.live)


if __name__ == "__main__":
    sys.exit(main())
