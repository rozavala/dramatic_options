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
import json
import logging
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import clusters
import discovery
import fixed_basket
import notify
import sentinels
import shadow_book
import shares_basket
import state
from broker import AlpacaPaperBroker, PaperBroker
from clock import Clock, FixedClock, LiveClock
from config_loader import (
    ConfigError,
    data_feed_stamp,
    live_allowed,
    load_config,
    require_alpaca_credentials,
)
from config_loader import (
    frame_version as compute_frame_version,
)
from convexity_data import AlpacaChainProvider, AlpacaQuoteProvider, SyntheticChainProvider
from council.router import BudgetExceeded, FakeRouter, RouterError, build_router
from council.wiring import council_to_themes
from discovery import MarkerParams, scan_baskets
from feeds import to_equity_feed, to_option_feed
from monitor import monitor_positions, reconcile_pending
from paper_loop import kill_rule_status, run_paper_cycle
from risk import kill_switch_active
from sentinel_scoring import resolve_due_references
from state import append_run_note, get_db, record_run
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
    # Per-cluster occupancy vs the correlation cap (PREREG §5 amendment) — visible deploy/T4 surface.
    cap_val = float(book.get("account_equity", 0.0)) * float(book.get("cluster_fraction", 0.0) or 0.0)
    for cname, members in clusters.load_cluster_map(config).items():
        prem = state.cluster_open_premium(conn, members)
        pct = (100.0 * prem / cap_val) if cap_val else 0.0
        log.info("  cluster %-16s $%.0f / $%.0f (%.0f%%)", cname, prem, cap_val, pct)


def _stamp_council_health(conn, run_id: int, config: dict, router) -> None:
    """Page + stamp the cycle's proposer parse-health. A high parse-fail rate means the council was
    INERT for a BUG reason (a model/SDK regression), not deliberate abstention — the #37 trap, which
    looks identical to fail-closed selectivity and otherwise trips no page. Also stamps the resolved
    per-role model_mix (a record-segmentation key). Best-effort: never raises into the trade cycle."""
    try:
        health = state.council_parse_health(conn, run_id)
        mix = {role: "/".join(router.provider_model(role)) for role in ("proposer", "adversary", "strategist")}
        # Record-segmentation for PROMPT changes (the model_mix discipline applied to prompts):
        # hash the LIVE council strings at runtime — self-describing, catches future drift.
        import hashlib

        from council import agents as _agents
        mix["prompts"] = "/".join(
            hashlib.sha256(s.encode()).hexdigest()[:16]
            for s in (_agents._COMMON, _agents.ADVERSARY_SYSTEM, _agents.STRATEGIST_SYSTEM))
        mix["corpus"] = "fundamentals_v2"  # §9: pack-change record-segmentation (v2 = IFRS taxonomy + tag-recency + annual fallback; zero migration)
        if health["called"]:
            log.info("Council proposer parse-health: %d/%d failed (%.0f%%)",
                     health["parse_failed"], health["called"], health["rate"] * 100)
        page_rate = float(config.get("council", {}).get("parse_fail_page_rate", 0.5))
        inert = health["called"] >= 2 and health["rate"] >= page_rate
        if inert:
            log.error("Council proposer parse-fail %d/%d (>=%.0f%%) — apparatus INERT (likely a model/SDK "
                      "regression, not judgment). Inspect council_agent_outputs.raw.",
                      health["parse_failed"], health["called"], page_rate * 100)
            notify.send("Council parse-fail — inert apparatus",
                        f"{health['parse_failed']}/{health['called']} proposer calls failed to parse this "
                        f"cycle → the council included nothing for a BUG reason. Check council_agent_outputs.raw.")
        state.update_run_council_health(conn, run_id, council_health="parse_fail" if inert else "ok",
                                        model_mix=json.dumps(mix))
    except Exception as e:  # noqa: BLE001 — health/paging is a control, must never break the trade cycle
        log.warning("council health stamp failed (non-fatal): %s", e)


def _build_council_io(config: dict, *, demo: bool, client, cache, clock):
    """(router, news, fundamentals) for the council. Demo → deterministic FakeRouter + synthetic
    packs (news/fundamentals=None); live → the heterogeneous router + CURRENT-news grounding + the
    §9 evidence-grounding corpus. Raises RouterError (fail-closed) when a mapped provider has no key
    in live."""
    council = config.get("council", {})
    cap = council.get("cost_cap_usd")
    if demo:
        return FakeRouter(cap_usd=float(cap) if cap is not None else None), None, None
    router = build_router(config, config.get("llm_keys", {}))
    from datetime import timedelta

    from data.news import NewsData

    now = clock.now()
    lookback = int(council.get("news_lookback_days", 90))
    news = NewsData(cache, client=client, fetch_start=now - timedelta(days=lookback), fetch_end=now)

    # §9 evidence-grounding corpus (council path: max_raw_age_days=7 + refetch-on-filing-event).
    # Fail-soft: no EDGAR_USER_AGENT or any setup error → fundamentals=None (the council degrades to
    # pre-§9 grounding, NEVER blocks the cycle). The live .env carries EDGAR_USER_AGENT.
    fundamentals = None
    try:
        ua = (config.get("edgar", {}) or {}).get("user_agent")
        if ua:
            from data.filings import EdgarClient
            from data.fundamentals import FundamentalsData
            cache_dir = config.get("cache", {}).get("dir", "data/cache")
            edgar_client = EdgarClient(ua, cache_dir=cache_dir)
            fundamentals = FundamentalsData(cache, edgar=edgar_client, fetch_end=now, ua=ua,
                                            max_raw_age_days=7)
    except Exception as e:  # noqa: BLE001 — corpus is enrichment; its absence must never block entries
        log.warning("§9 fundamentals corpus unavailable (non-fatal, pre-§9 grounding): %s", e)
        fundamentals = None
    return router, news, fundamentals


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
        equity_feed = gate_feed = None  # set in the live branch; demo uses Synthetic (feeds unused)
        event_provider, ev_reason = None, "demo"  # the structural-event leg — live branch only

        if demo:
            clock: Clock = FixedClock(datetime.now(UTC))
            as_of = clock.now()
            movers = [s for members in baskets.values() for s in members[:2]]  # first two per basket ramp
            market = discovery.synthetic_market(all_syms, as_of, movers=movers)
            run_id = record_run(conn, mode="DISCOVERY-DEMO", equity=None, note="discovery demo",
                                frame_version=compute_frame_version(config),
                                data_feed=data_feed_stamp(config),
                                discovery_funnel=discovery.DISCOVERY_FUNNEL_VERSION)
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
            # Data-feed roles (the data-feed upgrade): equity_bars (SIP) feeds the discovery markers via
            # MarketData + the null books' RV; option_gate feeds the null books' chains.
            equity_feed = to_equity_feed(config["data_feed"]["equity_bars"])
            gate_feed = to_option_feed(config["data_feed"]["option_gate"])
            market = MarketData(cache, client=client, fetch_start=fetch_start, fetch_end=as_of,
                                feed=equity_feed)
            run_id = record_run(conn, mode="DISCOVERY", equity=None, note="weekly scan",
                                frame_version=compute_frame_version(config),
                                data_feed=data_feed_stamp(config),
                                discovery_funnel=discovery.DISCOVERY_FUNNEL_VERSION)
            # The structural-event leg (PREREG_EVENT_LEG): fail-SOFT factory — a missing UA or
            # construction failure degrades to a motion-only scan, LOUDLY (status + note stamp).
            from data.structural_events import build_event_provider
            event_provider, ev_reason = build_event_provider(config, cache, as_of)

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
            event_provider=event_provider,
        )
        # Event-leg status — structured, logged AND stamped into runs.note (record_run fires
        # BEFORE the scan, so the counters need this post-scan write; journald rotates, the runs
        # row doesn't). 'ON, 0 fresh' must never be indistinguishable from a broken leg.
        if event_provider is not None:
            from data.structural_events import form_set_hash
            ctr = event_provider.counters
            ev_status = (f"events:ON ev={form_set_hash((disc.get('events', {}) or {}).get('forms', []))} "
                         f"{ctr.status()}")
            if ctr.fresh_names:
                ev_status += " fresh_names=" + ",".join(sorted(ctr.fresh_names))
            if ctr.systemic_failure():
                log.warning("Event leg SYSTEMIC failure — %s", ev_status)
                notify.send("Discovery event leg failing", ev_status)
        else:
            ev_status = f"events:OFF reason={ev_reason}"
            if not demo:
                log.warning("Event leg OFF (%s) — motion-only scan.", ev_reason)
        log.info("Discovery %s", ev_status)
        if not demo:
            append_run_note(conn, run_id, ev_status)
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

        # No-gate fixed-basket book 3B (PREREG_FIXED_BASKET_NULL, PR2b) — weekly, gate-OFF + EQUAL-WEIGHT
        # over the WHOLE eligible basket with the MOTION-derived direction. real−3B = the bundled
        # apparatus-vs-basket read. FAIL-SOFT + never-broker.
        if config.get("fixed_basket", {}).get("enabled", True):
            try:
                chain_provider = (SyntheticChainProvider(as_of=as_of.date()) if demo
                                  else AlpacaChainProvider(client, equity_feed=equity_feed,
                                                           option_feed=gate_feed))
                fbr3b = fixed_basket.run_fixed_basket_3b_cycle(
                    config=config, conn=conn, clock=clock, provider=chain_provider, market=market,
                    benchmark=benchmark, params=params, run_id=run_id,
                )
                if fbr3b.booked or fbr3b.halted:
                    log.info("No-gate(3B basket) book: booked=%d vetoed=%d skipped=%d errors=%d%s",
                             fbr3b.booked, fbr3b.vetoed, fbr3b.skipped, fbr3b.errors,
                             " HALTED" if fbr3b.halted else "")
            except Exception as e:  # noqa: BLE001 — fail-soft: never breaks the scan
                log.warning("no-gate 3B book pass failed (non-fatal): %s", e)
                notify.send("Fixed-basket 3B failed (non-fatal)", str(e))

        # Shares descriptive null (PREREG_FIXED_BASKET_NULL §2/§5, PR2c) — convexity vs LINEAR over the
        # SAME option-eligible basket names. The report is DESCRIPTIVE, shown ALONGSIDE the option tails,
        # NEVER scored against them (§5). FAIL-SOFT + never-broker.
        if config.get("shares_basket", {}).get("enabled", True):
            try:
                sh_provider = (SyntheticChainProvider(as_of=as_of.date()) if demo
                               else AlpacaChainProvider(client, equity_feed=equity_feed,
                                                        option_feed=gate_feed))
                sbr = shares_basket.run_shares_basket_cycle(
                    config=config, conn=conn, clock=clock, provider=sh_provider, market=market,
                    benchmark=benchmark, params=params, run_id=run_id,
                )
                if sbr.booked or sbr.halted:
                    log.info("Shares(null) book: booked=%d vetoed=%d skipped=%d errors=%d%s",
                             sbr.booked, sbr.vetoed, sbr.skipped, sbr.errors,
                             " HALTED" if sbr.halted else "")
                report = shares_basket.shares_return_report(conn, market, now=as_of)
                log.info("Shares(null) DESCRIPTIVE return report (NOT vs the option tails): %s", report["horizons"])
            except Exception as e:  # noqa: BLE001 — fail-soft: never breaks the scan
                log.warning("shares null book pass failed (non-fatal): %s", e)
                notify.send("Shares null failed (non-fatal)", str(e))

        # Cluster-cap curation backstop (PREREG §5, report-not-gate) — trailing-return correlations over the
        # names the system considers; surfaces co-moving pairs NOT co-clustered so the operator can curate
        # the map. It NEVER edits the map (hard seam) or gates a trade. The NO-FETCH read uses client=None so
        # it can't fetch beyond what the scan already cached. INDEPENDENT fail-soft block.
        if config.get("cluster_diagnostic", {}).get("enabled", True):
            try:
                import cluster_diagnostic
                from data.market import MarketData as _MarketData
                nofetch = _MarketData(market.cache, client=None, fetch_start=market.fetch_start,
                                      fetch_end=market.fetch_end)
                crep = cluster_diagnostic.cluster_curation_report(conn, config, as_of, nofetch)
                gaps = crep["gaps_full_n"]
                log.info("Cluster diagnostic: universe=%d median_corr=%s · %d full-N non-co-clustered gap(s)%s",
                         crep["universe_n"], crep["universe_median_corr"], len(gaps),
                         f" (top {gaps[0]['pair']} flag={gaps[0]['flag']})" if gaps else "")
            except Exception as e:  # noqa: BLE001 — fail-soft: never breaks the scan
                log.warning("cluster diagnostic failed (non-fatal): %s", e)
                notify.send("Cluster diagnostic failed (non-fatal)", str(e))

        # Basket-quality report (IMPLEMENTATION_PLAN.md:171; PREREG_FIXED_BASKET_NULL 74-79; report-not-gate) —
        # closes the survivorship→basket-curation loop over the curated scan baskets; surfaces curation drift so
        # the operator can curate universe.themes BY HAND (hard seam, never auto). Writes no DB row, no migration.
        # NO-FETCH (client=None). INDEPENDENT fail-soft block.
        if config.get("basket_quality", {}).get("enabled", True):
            try:
                import basket_quality
                from data.market import MarketData as _MarketData
                bq_nofetch = _MarketData(market.cache, client=None, fetch_start=market.fetch_start,
                                         fetch_end=market.fetch_end)
                brep = basket_quality.basket_quality_report(conn, config, as_of, bq_nofetch)
                drift = brep["curation_drift_indicators"]
                dd = sum(1 for d in drift if "data-dead" in d["indicator"])
                deg = sum(1 for d in drift if "degenerate" in d["indicator"])
                nsurf = sum(len(b["funnel"]["never_surfaced_curated"]) for b in brep["baskets"].values())
                log.info("Basket quality: %d baskets · %d data-dead · %d never-surfaced curated · %d degenerate%s",
                         len(brep["baskets"]), dd, nsurf, deg, "" if brep["mature"] else " (record ACCRUING)")
            except Exception as e:  # noqa: BLE001 — fail-soft: never breaks the scan
                log.warning("basket-quality report failed (non-fatal): %s", e)
                notify.send("Basket-quality report failed (non-fatal)", str(e))
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

        shadow_gate_provider = None  # the INDICATIVE dual-read arm — live branch only
        if demo:
            clock = FixedClock(datetime.now(UTC))
            provider = SyntheticChainProvider(as_of=clock.now().date())
            quote_provider = provider  # synthetic chain doubles as a QuoteProvider
            broker = PaperBroker(config.get("convexity_book", {}).get("account_equity", 100000.0))
            run_id = record_run(conn, mode="PAPER-DEMO", equity=broker.account_equity(), note="demo",
                                frame_version=compute_frame_version(config),
                                data_feed=data_feed_stamp(config))
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
            # Data-feed roles (the data-feed upgrade): RV/underlying on equity_bars (SIP); the gate
            # authorizes on option_gate (INDICATIVE in PR1, fail-closed); the L2 monitor marks on
            # option_monitor (free, degrade-and-continue).
            equity_feed = to_equity_feed(config["data_feed"]["equity_bars"])
            gate_feed = to_option_feed(config["data_feed"]["option_gate"])
            monitor_feed = to_option_feed(config["data_feed"]["option_monitor"])
            provider = AlpacaChainProvider(client, equity_feed=equity_feed, option_feed=gate_feed)
            # The INDICATIVE shadow arm (PREREG_DATA_FEED_OPRA_SEQUENCING §6): additive dual-read
            # beside the OPRA gate-of-record; it never authorizes (it can only tighten via the
            # date-gated disagree-veto) and every failure is a recorded coverage-guard row.
            shadow_gate_provider = AlpacaChainProvider(
                client, equity_feed=equity_feed, option_feed=to_option_feed("indicative"))
            quote_provider = AlpacaQuoteProvider(client, option_feed=monitor_feed)
            # Real paper-order broker; DRY_RUN (default) logs-and-simulates, never transmits.
            broker = AlpacaPaperBroker(api_key, secret_key, dry_run=dry_run, equity=equity)
            chain_cache = PointInTimeCache(config.get("cache", {}).get("dir", "data/cache"))
            run_id = record_run(conn, mode=mode, equity=equity, note="paper cycle",
                                frame_version=compute_frame_version(config),
                                data_feed=data_feed_stamp(config))
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

        # 1b. Brain-off NULL shadow book (T3 PR3b) — mark + exit the simulated control book alongside
        #     the real monitor, every cycle. FAIL-SOFT: a measurement-control bug must never halt the
        #     real trade cycle, and it never reaches the broker (shadow_book imports none).
        try:
            smr = shadow_book.mark_shadow_positions(
                conn=conn, clock=clock, quote_provider=quote_provider, config=config,
                underlying_price_of=provider.underlying_price,
            )
            if smr.marked or smr.closed:
                log.info("Shadow(null) monitor: marked=%d closed=%d (expiry=%d profit=%d time=%d)",
                         smr.marked, smr.closed, smr.expired, smr.profit_taken, smr.time_stopped)
        except Exception as e:  # noqa: BLE001 — fail-soft: the shadow control never breaks the cycle
            log.warning("shadow mark pass failed (non-fatal): %s", e)
            notify.send("Shadow book mark failed (non-fatal)", str(e))

        # 1c. No-gate 3A null book (PREREG_FIXED_BASKET_NULL, PR2a) — mark + exit the gate-off control
        #     alongside, same fail-soft + never-broker. shadow − 3A = the IV gate's marginal value.
        if config.get("fixed_basket", {}).get("enabled", True):
            try:
                fmr = fixed_basket.mark_fixed_basket_positions(
                    conn=conn, clock=clock, quote_provider=quote_provider, config=config,
                    underlying_price_of=provider.underlying_price,
                )
                if fmr.marked or fmr.closed:
                    log.info("No-gate(3A) monitor: marked=%d closed=%d (expiry=%d profit=%d time=%d)",
                             fmr.marked, fmr.closed, fmr.expired, fmr.profit_taken, fmr.time_stopped)
            except Exception as e:  # noqa: BLE001 — fail-soft: the gate null never breaks the cycle
                log.warning("no-gate 3A mark pass failed (non-fatal): %s", e)
                notify.send("Fixed-basket 3A mark failed (non-fatal)", str(e))

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
                            router, news_dep, fund_dep = _build_council_io(
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
                                clock=clock, news=news_dep, fundamentals=fund_dep, demo=demo,
                                run_id=run_id,
                            )
                            log.info(router.ledger.summary())
                            _stamp_council_health(conn, run_id, config, router)
                        except BudgetExceeded as e:
                            # Soft, exit-0 condition: OnFailure can't catch it → page in-app (PR2 R-C).
                            log.error("Council cost cap hit (%s) — fail-closed: NO entries this cycle.", e)
                            notify.send("Council cost cap hit", f"{e}\nNo entries submitted this cycle.")
                            themes = []
                            state.update_run_council_health(conn, run_id, council_health="cost_cap")
                        except RouterError as e:
                            log.error("Council unavailable (%s) — fail-closed: NO entries this cycle.", e)
                            notify.send("Council fail-closed — 0 entries", str(e))
                            themes = []
                            state.update_run_council_health(conn, run_id, council_health="fail_closed")

                # Post-council re-check (PR2 R7): the council can take minutes; re-confirm the
                # market is still open immediately before submitting so "no entry outside RTH"
                # is literally true, not merely bounded by TimeoutStartSec. demo always proceeds.
                if not demo and not _safe_market_open(clock):
                    log.warning("Market closed after the council ran — no entries submitted this cycle.")
                else:
                    result = run_paper_cycle(
                        config=config, conn=conn, clock=clock, provider=provider, broker=broker,
                        themes=themes, run_id=run_id, chain_cache=chain_cache,
                        shadow_provider=(None if demo else shadow_gate_provider),
                    )
                    log.info(
                        "Cycle #%d: evaluated=%d opened=%d vetoed=%d skipped=%d errors=%d%s",
                        run_id, result.evaluated, result.opened, result.vetoed, result.skipped,
                        result.errors, " HALTED" if result.halted else "",
                    )
                    # The §5 tripwire-population sweep (post-entries, fail-soft, live only): both
                    # feeds over the option-eligible universe → gate_dualread rows. Measurement
                    # only — it can never block or delay an authorization (entries are done).
                    if not demo:
                        try:
                            import gate_dualread as _dualread

                            uni_baskets, _bench = _scan_universe(config)
                            uni_syms = sorted({s for m in uni_baskets.values() for s in m})
                            elig_c = config.get("eligibility", {}).get("live", {})

                            def _sweep_elig(c):
                                from structure import contract_eligible

                                return contract_eligible(
                                    c, max_spread_pct=float(elig_c.get("max_bid_ask_pct", 0.25)),
                                    min_contract_price=0.10, max_contract_price=100.0,
                                    min_oi=elig_c.get("min_option_open_interest"))

                            counts = _dualread.sweep_universe(
                                conn, run_id=run_id, as_of_iso=clock.now().isoformat(),
                                symbols=uni_syms, provider_record=provider,
                                provider_shadow=shadow_gate_provider,
                                market_closes=lambda s: provider.closes(s, window=300),
                                gate=config.get("convexity_gate", {}), eligibility=_sweep_elig)
                            log.info("Gate dual-read sweep: %s", counts)
                        except Exception as e:  # noqa: BLE001 — measurement never halts the cycle
                            log.warning("gate dual-read sweep failed (non-fatal): %s", e)

                        # The §5 dual-read tripwire EXECUTOR (#72, post-sweep): single-sources the
                        # canonical gate_dualread_report (NO re-derivation), then disposes the
                        # CONVERGED per-class response — Phase 1 logs, Phase 2 pages (debounced),
                        # Phase 3 reverts ONLY when config.data_feed.dualread_revert_enabled is true
                        # (DEFAULT false ⇒ inert here). FAIL-SOFT (a crash never halts the cycle —
                        # entries already ran) but FAIL-LOUD on a degraded read (page, never silent).
                        try:
                            import dualread_executor
                            from dashboard_data import gate_dualread_report

                            report = gate_dualread_report(conn, config)
                            verdict = dualread_executor.run_executor(
                                report, config, notify=notify)
                            log.info("Gate dual-read §5 executor: delta=%s flip=%s structural=%s "
                                     "entitlement=%s reverted=%s",
                                     verdict["delta"]["tripped"],
                                     verdict["material_flip"]["tripped"],
                                     verdict["gap_structural"]["tripped"],
                                     verdict["entitlement"]["active"],
                                     verdict.get("revert_written", False))
                        except Exception as e:  # noqa: BLE001 — never halts; degrade LOUDLY
                            log.error("gate dual-read executor failed (DEGRADED, non-fatal): %s", e)
                            notify.send("Dual-read §5 executor DEGRADED",
                                        f"the runtime tripwire executor errored (entries already "
                                        f"ran; no revert/page evaluated this cycle): {e}", priority=1)
                    if result.halted:
                        # Kill switch / kill rule halted NEW entries (exit 0) → page in-app (PR2 R-C).
                        notify.send(
                            "Kill rule tripped — new entries halted",
                            "; ".join(result.notes) or "halted", priority=1,
                        )
                    _print_survivorship(conn, run_id)

                    # Brain-off NULL shadow book (T3 PR3b) — book EVERY gate-passer over the SAME
                    # candidate union the council saw, brain-OFF (no council narrowing, no framer
                    # drop). FAIL-SOFT + never-broker. The forward gap to the real book's tail = the
                    # LLM layer's marginal contribution.
                    try:
                        sbr = shadow_book.run_shadow_cycle(
                            config=config, conn=conn, clock=clock, provider=provider, run_id=run_id,
                        )
                        if sbr.booked or sbr.halted:
                            log.info("Shadow(null) book: booked=%d %s vetoed=%d skipped=%d%s",
                                     sbr.booked, dict(sbr.by_origin), sbr.vetoed, sbr.skipped,
                                     " HALTED" if sbr.halted else "")
                    except Exception as e:  # noqa: BLE001 — fail-soft: never breaks the real cycle
                        log.warning("shadow book pass failed (non-fatal): %s", e)
                        notify.send("Shadow book entry failed (non-fatal)", str(e))

                    # No-gate 3A null book (PREREG_FIXED_BASKET_NULL, PR2a) — book over the SAME union
                    # with the IV GATE OFF, cap-ON, alongside the shadow book. shadow − 3A = the gate's
                    # marginal value (the FSSD null≈signal on the edge). FAIL-SOFT + never-broker.
                    if config.get("fixed_basket", {}).get("enabled", True):
                        try:
                            fbr = fixed_basket.run_fixed_basket_3a_cycle(
                                config=config, conn=conn, clock=clock, provider=provider, run_id=run_id,
                            )
                            if fbr.booked or fbr.halted:
                                log.info("No-gate(3A) book: booked=%d %s vetoed=%d skipped=%d%s",
                                         fbr.booked, dict(fbr.by_origin), fbr.vetoed, fbr.skipped,
                                         " HALTED" if fbr.halted else "")
                        except Exception as e:  # noqa: BLE001 — fail-soft: never breaks the real cycle
                            log.warning("no-gate 3A book pass failed (non-fatal): %s", e)
                            notify.send("Fixed-basket 3A entry failed (non-fatal)", str(e))

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
