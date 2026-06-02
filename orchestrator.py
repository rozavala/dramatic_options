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

import discovery
import notify
import sentinels
import state
from broker import AlpacaPaperBroker, PaperBroker
from clock import Clock, FixedClock, LiveClock
from config_loader import ConfigError, live_allowed, load_config, require_alpaca_credentials
from convexity_data import AlpacaChainProvider, AlpacaQuoteProvider, SyntheticChainProvider
from council.router import BudgetExceeded, FakeRouter, RouterError, build_router
from council.wiring import council_to_themes
from discovery import MarkerParams, scan_baskets
from monitor import monitor_positions, reconcile_pending
from paper_loop import kill_rule_status, run_paper_cycle
from risk import kill_switch_active
from sentinel_scoring import resolve_due_references
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


def _build_framer_router(config: dict, *, demo: bool, disc: dict):
    """Router for the T3 discovery framer (PR2). Demo → deterministic FakeRouter; live → a router
    for the decorrelated framer role with the discovery cost cap. Returns None (fail-closed) when a
    mapped provider has no key — the scan then frames nothing."""
    cap = disc.get("cost_cap_usd")
    if demo:
        from council.sentinel import sentinel_fake_responder
        return FakeRouter(responder=sentinel_fake_responder,
                          cap_usd=float(cap) if cap is not None else None)
    from council.sentinel import build_framer_router
    try:
        return build_framer_router(config, config.get("llm_keys", {}))
    except RouterError as e:
        log.error("Framer unavailable (%s) — no candidates framed this scan (fail-closed).", e)
        notify.send("Discovery framer fail-closed", str(e))
        return None


def _safe_market_open(clock: Clock) -> bool:
    """``clock.is_market_open()`` wrapped FAIL-CLOSED (PR2 R5).

    The market-state call hits the broker/network; any error (outage, partial failure) must
    NOT be read as "open". Returning False means: no new entries, and the monitor runs
    mark-only (no real SELL_TO_CLOSE) — we never act on an unconfirmed market state.
    """
    try:
        return bool(clock.is_market_open())
    except Exception as e:  # noqa: BLE001 — fail-closed: unknown ⇒ treat as closed
        log.warning("market-state check failed (%s) — treating market as CLOSED (fail-closed).", e)
        return False


def entries_allowed(*, forward_enabled: bool, market_open: bool, demo: bool) -> tuple[bool, str]:
    """Whether to evaluate NEW entries this cycle (PR2 §B). Pure → unit-testable.

    Order matters: ``demo`` always evaluates (the offline experiment must run regardless of
    creds/market). Otherwise an env trades only if it opted in (``FORWARD_ENABLED``) AND the
    market is open — the latter, checked BEFORE the council build, means a holiday / half-day /
    post-close ``Persistent=true`` catch-up pays NO LLM cost and never submits into a closed
    book. The monitor (mark/exit) is gated separately and still runs.
    """
    if demo:
        return True, "demo"
    if not forward_enabled:
        return False, "FORWARD_ENABLED=false — env is installed-but-inert; no entries."
    if not market_open:
        return False, "market closed (holiday/half-day/after-hours) — no entries, no LLM spend."
    return True, "ok"


def _scan_universe(config: dict) -> tuple[dict[str, list[str]], str]:
    """The discovery scan baskets + benchmark from config.universe (curated thematic baskets)."""
    uni = config.get("universe", {})
    baskets = {
        str(k): [str(s).upper() for s in v]
        for k, v in uni.get("themes", {}).items()
        if not str(k).startswith("_")
    }
    benchmark = str(uni.get("benchmarks", {}).get("broad", "SPY")).upper()
    return baskets, benchmark


def run_discover(demo: bool = False) -> int:
    """L0 weekly discovery scan (T3) — surface NEW candidates into the sentinel store.

    DISCOVERS only: it never trades, never submits, runs no monitor. The candidates it persists
    are judged by the council on the next L1 cycle and disposed by the deterministic gates (the
    hard seam is unchanged). Kill-before-spend + FORWARD_ENABLED gating apply (PR1 spends nothing
    — the LLM framer is PR2). Safe market-closed (reads as-of data, submits nothing).
    """
    if kill_switch_active():
        log.warning("KILL switch engaged — discovery halted (no scan, no spend).")
        return 0

    config = load_config()
    disc = config.get("discovery", {})
    if not demo and not disc.get("enabled", False):
        log.info("Discovery disabled (config.discovery.enabled=false).")
        return 0
    if not demo and not bool(config.get("forward_enabled", False)):
        log.info("FORWARD_ENABLED=false — discovery inert (no scan, no spend).")
        return 0
    _banner("DISCOVERY (sentinel scan)" + (" · DEMO" if demo else ""))

    demo_db = None
    if demo:
        demo_db = tempfile.NamedTemporaryFile(prefix="dramatic_disc_", suffix=".db", delete=False)
        demo_db.close()
        conn = state.connect(demo_db.name)
    else:
        conn = get_db(config)
    client = None
    try:
        _ensure_schema(conn)
        baskets, benchmark = _scan_universe(config)
        if not baskets:
            log.warning("No scan baskets configured (config.universe.themes) — nothing to discover.")
            return 0
        all_syms = sorted({s for members in baskets.values() for s in members} | {benchmark})
        params = MarkerParams(**dict(disc.get("markers", {})))
        horizon = int(disc.get("reference_horizon_days", 180))

        if demo:
            clock: Clock = FixedClock(datetime.now(UTC))
            as_of = clock.now()
            movers = [s for members in baskets.values() for s in members[:2]]  # first two per basket ramp
            market = discovery.synthetic_market(all_syms, as_of, movers=movers)
            run_id = record_run(conn, mode="DISCOVERY-DEMO", equity=None, note="discovery demo")
            log.info("(demo: ephemeral DB %s — real sentinel store untouched)", demo_db.name)
        else:
            try:
                api_key, secret_key = require_alpaca_credentials(config)
            except ConfigError as e:
                log.error("%s", e)
                return 1
            from data.alpaca_client import AlpacaClient
            from data.cache import PointInTimeCache
            from data.market import MarketData, default_fetch_window

            client = AlpacaClient(api_key, secret_key, paper=config["alpaca"]["paper"])
            clock = LiveClock(client)
            as_of = clock.now()
            fetch_start, _ = default_fetch_window(as_of)
            cache = PointInTimeCache(config.get("cache", {}).get("dir", "data/cache"))
            market = MarketData(cache, client=client, fetch_start=fetch_start, fetch_end=as_of)
            run_id = record_run(conn, mode="DISCOVERY", equity=None, note="weekly scan")

        # Kill-before-spend seam (the council-build discipline). PR1 spends nothing; the framer
        # (PR2) sits behind this same guard.
        if kill_rule_status(conn, config, clock).tripped:
            log.warning("Kill rule tripped — discovery scan skipped (no spend).")
            return 0

        # Novelty/dedup: never re-surface a hand-seed name, an open position, or a live sentinel.
        exclude = set(state.open_position_symbols(conn)) | state.active_sentinel_symbols(conn)
        try:
            exclude |= {t.symbol for t in active_themes(load_themes(config.get("themes_path", "themes.json")))}
        except Exception as e:  # noqa: BLE001 — a missing themes.json must not break a scan
            log.warning("themes.json load failed (%s) — scanning without hand-seed exclusion.", e)

        result = scan_baskets(
            baskets, as_of, market=market, benchmark=benchmark, params=params,
            exclude_symbols=exclude, max_scan_names=int(disc.get("max_scan_names", 200)),
            top_k=int(disc.get("scan_top_k", 8)), n_controls=int(disc.get("n_random_controls", 5)),
        )
        # PR2: the bounded LLM framer adjudicates the confounds + grounds on the MARKERS over the
        # top-K. Fail-closed: framer over-budget / unavailable → frame nothing (no new sentinels this
        # scan). The skeptic disposes — only the framed survive (artifacts / NEUTRAL are dropped).
        framings: dict = {}
        if result.surfaced:
            framer_router = _build_framer_router(config, demo=demo, disc=disc)
            if framer_router is None:
                result.surfaced = []
            else:
                from council.sentinel import frame_candidates

                framings = frame_candidates(result.surfaced, framer_router, as_of=as_of)
                log.info(framer_router.ledger.summary())
                result.surfaced = [s for s in result.surfaced if s.markers.symbol in framings]
        counts = sentinels.persist_discovery(conn, result, run_id=run_id,
                                             as_of_iso=as_of.isoformat(), framings=framings)
        dormant = state.expire_stale_sentinels(
            conn, as_of=as_of, ttl_days=int(disc.get("sentinel_ttl_days", 35))
        )
        resolved = resolve_due_references(conn, market, now=as_of, horizon_days=horizon)
        log.info(
            "Discovery: scanned=%d cleared=%d surfaced=%d controls=%d · dormant(ttl)=%d refs_resolved=%d",
            result.n_scanned, result.n_cleared, counts["sentinels"], counts["controls"], dormant, resolved,
        )
        for s in result.surfaced:
            log.info("  + %-6s %-7s score=%.2f (%s) — basket=%s", s.markers.symbol, s.direction,
                     s.inflection_score, s.gate_reason, s.markers.basket)
        return 0
    finally:
        conn.close()
        if demo_db is not None:
            Path(demo_db.name).unlink(missing_ok=True)


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

        # Market state, checked ONCE per cycle, FAIL-CLOSED (PR2 R5). Gates both the monitor's
        # real submits (below) and the entry path (§2). Unknown/error ⇒ treated as closed.
        market_open = _safe_market_open(clock)

        # 1. Monitor pass — reconcile pending real orders, then mark + fire exits.
        #    When the market is CLOSED the monitor runs MARK-ONLY: dry_run is forced true so a
        #    real SELL_TO_CLOSE never transmits into a closed options book (PR2 R1) — covers
        #    half-days, holidays, and a Persistent=true post-close catch-up. Real exits fire on
        #    an open-market cycle (L1 at 15:45 ET; the L2 intraday ticks).
        reconciled = reconcile_pending(conn=conn, broker=broker, clock=clock, config=config)
        if reconciled:
            log.info("Reconciled %d pending order(s).", reconciled)
        mres = monitor_positions(
            conn=conn, clock=clock, quote_provider=quote_provider, config=config,
            underlying_price_of=provider.underlying_price, broker=broker,
            dry_run=dry_run or not market_open,
        )
        log.info(
            "Monitor: marked=%d closed=%d (expiry=%d profit=%d time=%d) unmarked=%d realized=$%.0f",
            mres.marked, mres.closed, mres.expired, mres.profit_taken, mres.time_stopped,
            mres.unmarked, mres.realized_pnl,
        )

        # 2. Council pass → themes (T2). The council PROPOSES; the deterministic gates in
        #    run_paper_cycle still DISPOSE. Entries are gated BEFORE any LLM spend by
        #    FORWARD_ENABLED + market-open (PR2 §B): an inert env or a closed market pays
        #    nothing and submits nothing. Kill checks then run FIRST so no spend when halted.
        #    council.enabled=false → themes=None → run_paper_cycle uses themes.json (T1 fallback).
        if not monitor_only:
            allowed, why = entries_allowed(
                forward_enabled=bool(config.get("forward_enabled", False)),
                market_open=market_open, demo=demo,
            )
            if not allowed:
                log.info("Entries skipped: %s", why)
            else:
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
                            # Candidate set = hand-seed (themes.json, FIRST/protected) ⊕ ranked
                            # active sentinels (T3 discovery). Hand-seed-first ordering means the
                            # council's [:max_candidates] truncation drops the WEAKEST sentinel,
                            # never a hand-seed conviction or the newest arrival.
                            candidates = sentinels.union_candidates(
                                active_themes(load_themes(config.get("themes_path", "themes.json"))),
                                sentinels.active_sentinel_candidates(conn),
                            )
                            themes = council_to_themes(
                                conn, candidates=candidates, router=router, config=config,
                                clock=clock, news=news_dep, demo=demo, run_id=run_id,
                            )
                            log.info(router.ledger.summary())
                        except BudgetExceeded as e:
                            # Soft, exit-0 condition: OnFailure can't catch it → page in-app (PR2 R-C).
                            log.error("Council cost cap hit (%s) — fail-closed: NO entries this cycle.", e)
                            notify.send("Council cost cap hit", f"{e}\nNo entries submitted this cycle.")
                            themes = []
                        except RouterError as e:
                            log.error("Council unavailable (%s) — fail-closed: NO entries this cycle.", e)
                            notify.send("Council fail-closed — 0 entries", str(e))
                            themes = []

                # Post-council re-check (PR2 R7): the council can take minutes; re-confirm the
                # market is still open immediately before submitting so "no entry outside RTH"
                # is literally true, not merely bounded by TimeoutStartSec. demo always proceeds.
                if not demo and not _safe_market_open(clock):
                    log.warning("Market closed after the council ran — no entries submitted this cycle.")
                else:
                    result = run_paper_cycle(
                        config=config, conn=conn, clock=clock, provider=provider, broker=broker,
                        themes=themes, run_id=run_id, chain_cache=chain_cache,
                    )
                    log.info(
                        "Cycle #%d: evaluated=%d opened=%d vetoed=%d skipped=%d errors=%d%s",
                        run_id, result.evaluated, result.opened, result.vetoed, result.skipped,
                        result.errors, " HALTED" if result.halted else "",
                    )
                    if result.halted:
                        # Kill switch / kill rule halted NEW entries (exit 0) → page in-app (PR2 R-C).
                        notify.send(
                            "Kill rule tripped — new entries halted",
                            "; ".join(result.notes) or "halted", priority=1,
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
    parser.add_argument("--discover", action="store_true", help="L0 weekly sentinel discovery scan (no trading); surfaces candidates the council later judges.")
    args = parser.parse_args(argv)
    if args.discover:
        return run_discover(demo=args.demo)
    return run_once(cli_live=args.live, demo=args.demo, monitor_only=args.monitor)


if __name__ == "__main__":
    sys.exit(main())
