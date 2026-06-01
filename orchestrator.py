"""Orchestrator — thematic cheap-convexity paper loop (T1.5).

    python orchestrator.py            # one cycle on themes.json (needs Alpaca creds)
    python orchestrator.py --demo     # one cycle offline on deterministic synthetic data
    python orchestrator.py --monitor  # mark + apply exits to open positions, NO new entries
    touch KILL && python orchestrator.py   # halts before any work

A cycle is: reconcile pending real orders → mark open positions + fire deterministic exits
(profit-take / time-stop / expiry, the L2 reflex) → then evaluate new entries. Paper-only;
real Alpaca submission is gated by ``safety.dry_run`` (default true = log, never send).
``--live`` is gated (PREREG §7).
"""

from __future__ import annotations

import argparse
import importlib.util
import logging
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import state
from broker import AlpacaPaperBroker, PaperBroker
from clock import FixedClock, LiveClock
from config_loader import ConfigError, live_allowed, load_config, require_alpaca_credentials
from convexity_data import AlpacaChainProvider, AlpacaQuoteProvider, SyntheticChainProvider
from council.router import FakeRouter, RouterError, build_router
from council.wiring import council_to_themes
from monitor import monitor_positions, reconcile_pending
from paper_loop import kill_rule_status, run_paper_cycle
from risk import kill_switch_active
from state import get_db, record_run
from themes import active_themes, load_themes

log = logging.getLogger("orchestrator")
if not log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)
    log.propagate = False


def _banner(mode: str) -> None:
    bar = "=" * 60
    log.info(bar)
    log.info("  DRAMATIC OPTIONS — %s   (thematic cheap-convexity)", mode)
    log.info(bar)


def _ensure_schema(conn) -> None:
    """Apply pending SQLite migrations (idempotent) so the convexity tables exist."""
    path = Path(__file__).resolve().parent / "scripts" / "run_migrations.py"
    spec = importlib.util.spec_from_file_location("run_migrations", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    applied = {int(r["version"]) for r in conn.execute("SELECT version FROM schema_version")}
    for version, p in mod._discover():
        if version in applied:
            continue
        with conn:
            mod._load_apply(p)(conn)
            conn.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, datetime('now'))",
                (version,),
            )


def _print_survivorship(conn, run_id: int) -> None:
    rows = conn.execute(
        "SELECT theme, symbol, decision, iv_rv, otm_skew FROM convexity_eval "
        "WHERE run_id = ? ORDER BY id",
        (run_id,),
    ).fetchall()
    if not rows:
        return
    log.info("Survivorship log (run #%d) — every evaluated bet:", run_id)
    for r in rows:
        ivrv = f"{r['iv_rv']:.2f}" if r["iv_rv"] is not None else "—"
        skew = f"{r['otm_skew']:.1f}vp" if r["otm_skew"] is not None else "—"
        log.info("  %-28s %-6s %-17s iv/rv=%s skew=%s", r["theme"], r["symbol"], r["decision"], ivrv, skew)


def _print_book_summary(conn, config: dict) -> None:
    book = config.get("convexity_book", {})
    budget = float(book.get("account_equity", 0.0)) * float(book.get("book_fraction", 0.0))
    open_prem = state.convexity_book_open_premium(conn)
    dd, have_marks = state.convexity_book_drawdown(conn, budget)
    halt = float(config.get("kill_rule", {}).get("book_drawdown_halt", 0.20))
    n_open = state.count_open_convexity_positions(conn)
    log.info(
        "Book: %d open · $%.0f / $%.0f premium-at-risk · drawdown %s (halt @ %.0f%%)",
        n_open, open_prem, budget,
        f"{dd:.0%}" if have_marks else "n/a (unmarked)", halt * 100,
    )


def _build_council_io(config: dict, *, demo: bool, client, cache, clock):
    """(router, news) for the council. Demo → deterministic FakeRouter + synthetic packs
    (news=None); live → the heterogeneous router + a CURRENT-news grounding source. Raises
    RouterError (fail-closed) when a mapped provider has no key in live."""
    council = config.get("council", {})
    cap = council.get("cost_cap_usd")
    if demo:
        return FakeRouter(cap_usd=float(cap) if cap is not None else None), None
    router = build_router(config, config.get("llm_keys", {}))
    from datetime import timedelta

    from data.news import NewsData

    now = clock.now()
    lookback = int(council.get("news_lookback_days", 90))
    news = NewsData(cache, client=client, fetch_start=now - timedelta(days=lookback), fetch_end=now)
    return router, news


def run_once(cli_live: bool = False, demo: bool = False, monitor_only: bool = False) -> int:
    if kill_switch_active():
        log.warning("KILL switch engaged — halting. Remove the KILL file/env to resume.")
        return 0

    config = load_config()
    is_live = live_allowed(config, cli_live)
    mode = "DEMO (offline synthetic)" if demo else ("LIVE" if is_live else "PAPER")
    _banner(mode + (" · MONITOR-ONLY" if monitor_only else ""))
    if cli_live and not is_live:
        log.warning("--live requested but gates not satisfied — continuing in PAPER mode.")

    demo_db = None
    if demo:
        demo_db = tempfile.NamedTemporaryFile(prefix="dramatic_demo_", suffix=".db", delete=False)
        demo_db.close()
        conn = state.connect(demo_db.name)
    else:
        conn = get_db(config)
    chain_cache = None
    client = None
    try:
        _ensure_schema(conn)
        dry_run = bool(config.get("safety", {}).get("dry_run", True))

        if demo:
            clock = FixedClock(datetime.now(UTC))
            provider = SyntheticChainProvider(as_of=clock.now().date())
            quote_provider = provider  # synthetic chain doubles as a QuoteProvider
            broker = PaperBroker(config.get("convexity_book", {}).get("account_equity", 100000.0))
            run_id = record_run(conn, mode="PAPER-DEMO", equity=broker.account_equity(), note="demo")
            log.info("(demo: ephemeral DB %s — real book untouched)", demo_db.name)
        else:
            try:
                api_key, secret_key = require_alpaca_credentials(config)
            except ConfigError as e:
                log.error("%s", e)
                log.error("(No Alpaca creds — use `python orchestrator.py --demo` for an offline run.)")
                return 1
            from data.alpaca_client import AlpacaClient
            from data.cache import PointInTimeCache

            client = AlpacaClient(api_key, secret_key, paper=config["alpaca"]["paper"])
            try:
                equity = client.get_equity()
            except Exception as e:  # noqa: BLE001 — fail-closed
                log.error("Could not reach Alpaca: %s", e)
                return 1
            clock = LiveClock(client)
            provider = AlpacaChainProvider(client)
            quote_provider = AlpacaQuoteProvider(client)
            # Real paper-order broker; DRY_RUN (default) logs-and-simulates, never transmits.
            broker = AlpacaPaperBroker(api_key, secret_key, dry_run=dry_run, equity=equity)
            chain_cache = PointInTimeCache(config.get("cache", {}).get("dir", "data/cache"))
            run_id = record_run(conn, mode=mode, equity=equity, note="paper cycle")
            log.info("Execution: %s", "DRY_RUN (orders logged, not sent)" if dry_run else "LIVE PAPER SUBMIT")

        # 1. Monitor pass — reconcile pending real orders, then mark + fire exits.
        reconciled = reconcile_pending(conn=conn, broker=broker, clock=clock, config=config)
        if reconciled:
            log.info("Reconciled %d pending order(s).", reconciled)
        mres = monitor_positions(
            conn=conn, clock=clock, quote_provider=quote_provider, config=config,
            underlying_price_of=provider.underlying_price,
        )
        log.info(
            "Monitor: marked=%d closed=%d (expiry=%d profit=%d time=%d) unmarked=%d realized=$%.0f",
            mres.marked, mres.closed, mres.expired, mres.profit_taken, mres.time_stopped,
            mres.unmarked, mres.realized_pnl,
        )

        # 2. Council pass → themes (T2). The council PROPOSES; the deterministic gates in
        #    run_paper_cycle still DISPOSE. Kill checks run FIRST so no LLM spend when halted.
        #    council.enabled=false → themes=None → run_paper_cycle uses themes.json (T1 fallback).
        if not monitor_only:
            themes = None
            if config.get("council", {}).get("enabled", False):
                if kill_switch_active() or kill_rule_status(conn, config, clock).tripped:
                    log.info("Kill state active — council skipped (no LLM spend).")
                    themes = []  # run_paper_cycle re-checks and halts; no entries
                else:
                    try:
                        router, news_dep = _build_council_io(
                            config, demo=demo, client=client, cache=chain_cache, clock=clock,
                        )
                        candidates = active_themes(load_themes(config.get("themes_path", "themes.json")))
                        themes = council_to_themes(
                            conn, candidates=candidates, router=router, config=config,
                            clock=clock, news=news_dep, demo=demo, run_id=run_id,
                        )
                        log.info(router.ledger.summary())
                    except RouterError as e:
                        log.error("Council unavailable (%s) — fail-closed: NO entries this cycle.", e)
                        themes = []

            result = run_paper_cycle(
                config=config, conn=conn, clock=clock, provider=provider, broker=broker,
                themes=themes, run_id=run_id, chain_cache=chain_cache,
            )
            log.info(
                "Cycle #%d: evaluated=%d opened=%d vetoed=%d skipped=%d errors=%d%s",
                run_id, result.evaluated, result.opened, result.vetoed, result.skipped,
                result.errors, " HALTED" if result.halted else "",
            )
            _print_survivorship(conn, run_id)

        _print_book_summary(conn, config)
        return 0
    finally:
        conn.close()
        if demo_db is not None:
            Path(demo_db.name).unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dramatic Options orchestrator (thematic cheap-convexity)")
    parser.add_argument("--live", action="store_true", help="Request live (still gated by PAPER/LIVE_TRADING_ENABLED).")
    parser.add_argument("--once", action="store_true", help="Run a single cycle (default; accepted for clarity).")
    parser.add_argument("--demo", action="store_true", help="Offline run on deterministic synthetic data (no creds/network).")
    parser.add_argument("--monitor", action="store_true", help="Mark + apply exits to open positions only; no new entries.")
    args = parser.parse_args(argv)
    return run_once(cli_live=args.live, demo=args.demo, monitor_only=args.monitor)


if __name__ == "__main__":
    sys.exit(main())
