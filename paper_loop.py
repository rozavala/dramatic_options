"""The minimal paper loop (T1) — PREREG_THEMATIC_CONVEXITY, IMPLEMENTATION_PLAN T1.

Pipeline, per active hand-seeded theme:

    theme → current chain + trailing realized vol → eligibility gate → IV/cheap-convexity
    gate → defined-risk long-dated structure → flat-by-slots sizing (caps + book +
    concurrency) → paper fill → log position + survivorship-log every evaluation.

Deterministic gates dispose; the (future) council only proposes. **Fail-closed:** the kill
switch and the kill rule are checked before any entry, and any per-theme error is logged and
skipped (never opens a position). The goal of T1 is simply: **one paper position logged.**
Dependency-injected (clock, provider, broker, conn) → fully offline-testable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import clusters
import state
from broker import Broker, make_client_order_id
from clock import Clock
from convexity_data import ChainProvider
from convexity_gate import is_cheap_convexity, realized_vol
from risk import kill_switch_active
from structure import contract_eligible, select_structure
from themes import Theme, active_themes, load_themes

log = logging.getLogger("paper_loop")


@dataclass
class CycleResult:
    evaluated: int = 0
    opened: int = 0
    vetoed: int = 0
    skipped: int = 0
    errors: int = 0
    halted: bool = False
    opened_ids: list[int] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class KillRuleStatus:
    tripped: bool
    book_drawdown: float
    months_dry: float
    reasons: tuple[str, ...]
    dry_since: str | None = None      # the dry clock's ET start date (first real fill, or the last payoff close)
    dry_binds_on: str | None = None   # the ET date the dry leg trips absent a payoff


def drawdown_since(config: dict) -> str | None:
    """The drawdown leg's dated re-anchor (``kill_rule.drawdown_reanchored_on``): one reader for every drawdown caller."""
    return (config.get("kill_rule") or {}).get("drawdown_reanchored_on")


def _add_months(d, n: int):
    """``d`` plus ``n`` calendar months, the day clamped to the target month's length (01-31 + 1 → 02-28)."""
    import calendar
    from datetime import date

    y, m = divmod(d.month - 1 + n, 12)
    year, month = d.year + y, m + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def _et_date(ts: str):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return datetime.fromisoformat(str(ts)).astimezone(ZoneInfo("America/New_York")).date()


def kill_rule_status(conn, config: dict, clock: Clock) -> KillRuleStatus:
    """Evaluate the §6 kill rule from state (PREREG_THEMATIC_CONVEXITY §6 conformance notes, operator word 2026-11-12).
    A trip halts NEW real-book entries and the council; it never force-closes. The L0 scan and all four null books keep
    running (operator word 2026-11-12); only the KILL switch stops them.

    - **Drawdown leg:** the cumulative net loss since the first real fill ÷ the premium budget
      (``state.convexity_book_drawdown``) ≥ ``kill_rule.book_drawdown_halt``.
    - **Dry leg:** ``kill_rule.dry_months_halt`` calendar months (US-Eastern dates) since the first real fill, or since
      the last real close with ``realized_pnl > 0`` if later. Off while ``dry_months_halt`` is absent or no real
      position has filled. A state read that fails raises, so the cycle fails closed.
    - **Release:** a payoff close, a mark recovery, or the operator's dated re-anchor keys
      (``kill_rule.dry_clock_reanchored_on`` / ``drawdown_reanchored_on``; each moves ``frame_version``)."""
    kr = config.get("kill_rule", {})
    book = config.get("convexity_book", {})
    dd_halt = float(kr.get("book_drawdown_halt", 0.20))
    book_budget = float(book.get("account_equity", 0.0)) * float(book.get("book_fraction", 0.0))

    book_dd, _have_marks = state.convexity_book_drawdown(conn, book_budget, since=drawdown_since(config))

    reasons: list[str] = []
    tripped = False
    if book_dd >= dd_halt:
        tripped = True
        reasons.append(f"book drawdown {book_dd:.0%} >= {dd_halt:.0%}")

    months_dry, dry_since, dry_binds_on = 0.0, None, None
    dry_halt = kr.get("dry_months_halt")
    first_fill, last_payoff = state.real_book_dry_clock(conn)
    if dry_halt is not None and first_fill:
        today_et = _et_date(clock.now().isoformat())
        start = max(_et_date(first_fill), _et_date(last_payoff)) if last_payoff else _et_date(first_fill)
        if kr.get("dry_clock_reanchored_on"):   # the operator's dated re-anchor after a review (a frame boundary)
            from datetime import date
            anchor = date.fromisoformat(str(kr["dry_clock_reanchored_on"]))   # malformed → raises (fail-closed)
            if anchor > today_et:
                raise ValueError(f"kill_rule.dry_clock_reanchored_on {anchor} is in the future (would park the clock)")
            start = max(start, anchor)
        today = today_et
        binds = _add_months(start, int(dry_halt))
        whole = (today.year - start.year) * 12 + (today.month - start.month) - (1 if today.day < start.day else 0)
        # on or after the bind day the clock reads at least the limit (a month-end start clamps the bind day earlier)
        months_dry = float(max(0, whole, int(dry_halt) if today >= binds else 0))
        dry_since, dry_binds_on = start.isoformat(), binds.isoformat()
        if today >= binds:
            tripped = True
            reasons.append(f"book dry since {dry_since} (>= {int(dry_halt)} months, no realized payoff)")
    return KillRuleStatus(tripped=tripped, book_drawdown=book_dd, months_dry=months_dry, reasons=tuple(reasons),
                          dry_since=dry_since, dry_binds_on=dry_binds_on)


def run_paper_cycle(
    *,
    config: dict,
    conn,
    clock: Clock,
    provider: ChainProvider,
    broker: Broker,
    themes: list[Theme] | None = None,
    run_id: int | None = None,
    chain_cache=None,
    shadow_provider: ChainProvider | None = None,
    walk: dict[str, dict] | None = None,
) -> CycleResult:
    """Run one paper cycle over the active themes. Returns a CycleResult.

    ``chain_cache`` (optional ``PointInTimeCache``): when supplied, each theme's current
    chain snapshot is persisted (append-only) so an IV-rank baseline accrues over time
    (PREREG §4b). ``None`` (e.g. the offline demo) skips persistence.

    ``walk`` (#386, the carry-over): ``{symbol: {"intent_id", "step", "fraction"}}`` for a carried entry's
    next-session attempt. That theme goes through EVERY check below exactly as an L1 entry does; only the limit
    differs (``mid + fraction × (ask − mid)``, never above the ask), its order id gets a ``-c<step>`` suffix and
    its rationale records the carry. ``None`` = the ordinary L1 path, unchanged.
    """
    result = CycleResult()
    as_of_dt = clock.now()
    as_of = as_of_dt.date()
    as_of_iso = as_of_dt.isoformat()

    # 1. Always-on kill switch (file/env), fail-closed.
    if kill_switch_active():
        result.halted = True
        result.notes.append("KILL switch engaged — no entries this cycle.")
        log.warning("KILL switch engaged — halting paper cycle.")
        return result

    # 2. The pre-registered kill rule (§6).
    krs = kill_rule_status(conn, config, clock)
    if krs.tripped:
        result.halted = True
        result.notes.append("kill rule tripped: " + "; ".join(krs.reasons))
        log.warning("Kill rule tripped (%s) — halting NEW entries for review.", "; ".join(krs.reasons))
        return result

    if themes is None:
        themes = active_themes(load_themes(config.get("themes_path", "themes.json")))

    book = config.get("convexity_book", {})
    gate = config.get("convexity_gate", {})
    elig = config.get("eligibility", {}).get("live", {})
    # The convexity book is sized off the operator-set notional (PREREG §5), NOT the broker's
    # paper-account equity — a sandbox figure that drifts with unrelated paper fills and would
    # make the per-slot slice (and thus entries) non-deterministic. Live (T4) reconciles the
    # notional against real equity before any capital. Broker equity is logged, not sized on.
    # Issue #279: there is NO fallback to broker equity. At real money the account is shared (~$250k of
    # unrelated holdings), so sizing off it would silently multiply every cap. Unset → no entries (paged).
    account_equity = float(book.get("account_equity") or 0.0)
    if account_equity <= 0:
        result.halted = True
        result.notes.append("convexity_book.account_equity is not configured — no entries (issue #279: "
                            "the book never sizes off whole-account broker equity).")
        log.error("convexity_book.account_equity not configured — halting NEW entries (fail-closed).")
        return result

    # Correlation-cluster exposure cap (PREREG §5 amendment 2026-06-03): an operator-curated
    # symbol→cluster map caps aggregate ENTRY-premium per correlated cluster — the per-name cap alone
    # reads a correlated basket (e.g. the AI-capex-into-power names) as false diversification. Inert
    # without a positive cluster_fraction (then every name is its own singleton). load raises on a
    # malformed map (overlap / cap < per-name) — fail-closed.
    cluster_fraction = float(book.get("cluster_fraction") or 0.0)
    cluster_map = clusters.load_cluster_map(config) if cluster_fraction > 0 else {}

    # Dedup: one open position per underlying for T1 (one name per theme). Re-running the loop
    # must not stack duplicate bets on a theme that is already on.
    # pending counts too (#386): a working order — an L1 entry or a carry attempt whose cancel isn't confirmed yet —
    # must never be joined by a second buy for the same name
    open_syms = state.entry_blocked_symbols(conn)

    def _eligibility(c):
        return contract_eligible(
            c,
            max_spread_pct=float(elig.get("max_bid_ask_pct", 0.25)),
            min_contract_price=0.10,
            max_contract_price=100.0,
            min_oi=elig.get("min_option_open_interest"),
        )

    # The OPRA dual-read (PREREG_DATA_FEED_OPRA_SEQUENCING §5): the date-gated disagree-veto is
    # computed once per cycle; one entitlement page per run (the soft-trip precedent), not per name.
    import gate_dualread as _dualread

    dualread_veto_active = _dualread.disagree_veto_active(config, as_of)
    entitlement_paged = False

    # PREREG §5 amendment 2026-11-03 (ranked backfill): the weekly quota, computed once per cycle and spent as backfill
    # entries open. A carry attempt (walk) is the same approved entry, so it never draws on the quota again.
    backfill_left: int | None = None

    for theme in themes:
        if not theme.active:
            continue
        result.evaluated += 1
        is_backfill = theme.entry_origin == "backfill" and walk is None
        if is_backfill:
            if backfill_left is None:
                import backfill as _backfill

                cfg_bf = _backfill.settings(config)
                backfill_left = (0 if cfg_bf is None
                                 else cfg_bf.per_week - _backfill.used_this_week(conn, now=as_of_dt))
            if backfill_left <= 0:
                result.skipped += 1
                state.record_convexity_eval(
                    conn, run_id=run_id, as_of=as_of_iso, theme=theme.name, symbol=theme.symbol,
                    direction=theme.direction, decision="skip-backfill-quota", proposal_id=theme.proposal_id,
                    reasons=["the week's backfill entry is already taken (or backfill is off)"],
                )
                continue
        opened_before = result.opened
        if theme.symbol in open_syms:
            result.skipped += 1
            state.record_convexity_eval(
                conn, run_id=run_id, as_of=as_of_iso, theme=theme.name, symbol=theme.symbol,
                direction=theme.direction, decision="skip-already-open", proposal_id=theme.proposal_id,
                reasons=[f"{theme.symbol} already has an open position or a working order"],
            )
            continue
        try:
            _process_theme(
                theme, config=config, conn=conn, provider=provider, broker=broker,
                eligibility=_eligibility, account_equity=account_equity, gate=gate, book=book,
                cluster_map=cluster_map, cluster_fraction=cluster_fraction,
                as_of=as_of, as_of_dt=as_of_dt, as_of_iso=as_of_iso, run_id=run_id,
                result=result, chain_cache=chain_cache,
                shadow_provider=shadow_provider, dualread_veto_active=dualread_veto_active,
                walk=(walk or {}).get(theme.symbol),
            )
            if is_backfill and result.opened > opened_before:
                backfill_left -= 1
        except Exception as e:  # noqa: BLE001 — fail-closed: log, never open on error
            result.errors += 1
            # PREREG_DATA_FEED_OPRA_SEQUENCING §7: an ENTITLEMENT lapse on the premium gate feed is
            # a distinct, page-worthy veto — never a silent downgrade (the candidate drops either
            # way; the gate is fail-closed by construction). Transient/other errors keep the
            # existing 'error' decision.
            from feeds import classify_feed_error

            kind = classify_feed_error(e)
            decision = "veto-feed-entitlement" if kind == "entitlement" else "error"
            state.record_convexity_eval(
                conn, run_id=run_id, as_of=as_of_iso, theme=theme.name, symbol=theme.symbol,
                direction=theme.direction, decision=decision, proposal_id=theme.proposal_id,
                reasons=[f"{kind}: {e}"],
            )
            if kind == "entitlement" and not entitlement_paged:
                entitlement_paged = True
                try:
                    import notify

                    notify.send("OPRA gate entitlement lapse",
                                f"premium feed fetch refused ({theme.symbol}): {e}")
                except Exception:  # noqa: BLE001 — paging must never break the cycle
                    log.warning("entitlement page failed to send")
            log.error("Theme %s (%s) errored (%s): %s", theme.name, theme.symbol, kind, e)

    # Non-fatal mixed-direction warning per cluster (the cap sums premium-at-risk regardless of
    # direction; a coherent cluster is single-direction — PREREG §5 / R2 2d). Per-cluster occupancy %
    # is surfaced visibly by the orchestrator's book summary.
    for cname, members in cluster_map.items():
        dirs = state.cluster_open_directions(conn, members)
        if len(dirs) > 1:
            log.warning(
                "Cluster %s holds mixed directions %s — cap sums them as additive risk "
                "(clusters are assumed directionally coherent)", cname, sorted(dirs),
            )

    log.info(
        "Paper cycle: evaluated=%d opened=%d vetoed=%d skipped=%d errors=%d",
        result.evaluated, result.opened, result.vetoed, result.skipped, result.errors,
    )
    # A REAL-BOOK ENTRY is the rarest healthy event the system produces — page it (the 2026-07-01
    # PL entry went unnoticed for THREE DAYS because only failures paged;
    # records/2026-07-04_first_real_entry_ERRATUM.md §3.2). Entries are rare-by-design, so the
    # page cost is ~zero; paging must never break the cycle.
    if result.opened > 0 and walk is None:   # a carry attempt pages through its own ORDER SUBMITTED / FILL pages
        try:
            import notify

            notify.send(
                "REAL-BOOK ENTRY",
                f"{result.opened} position(s) submitted/opened this cycle "
                f"(ids {result.opened_ids}) — run #{run_id}.",
            )
        except Exception:  # noqa: BLE001 — paging must never break the cycle
            log.warning("entry page failed to send")
    return result


def _quote(c) -> dict:
    """The selected contract's two-sided quote at decision time (telemetry; 2026-10-27). The chain snapshot keeps
    IVs only (PREREG §4b), so without this nothing records how wide the market was when an order went in, the
    evidence any limit-walk parameter needs."""
    bid, ask = getattr(c, "bid", None), getattr(c, "ask", None)
    mid = 0.5 * (bid + ask) if bid is not None and ask is not None and ask > 0 else None
    spr = round((ask - bid) / mid * 100.0, 1) if mid else None
    return {"bid": bid, "ask": ask, "mid": round(mid, 4) if mid else None, "spread_pct": spr}


def _process_theme(
    theme: Theme, *, config, conn, provider, broker, eligibility, account_equity, gate, book,
    cluster_map, cluster_fraction, as_of, as_of_dt, as_of_iso, run_id, result: CycleResult,
    chain_cache=None, shadow_provider=None, dualread_veto_active=False, walk: dict | None = None,
) -> None:
    # Correlation-cluster exposure cap (PREREG §5 amendment) — COARSE check FIRST, before the slot
    # reservation: a structurally-full cluster records the structural ``veto-cluster-cap`` (the true
    # binding constraint) over the transient ``veto-sentinel-slots``, keeping the survivorship log's
    # reason honest for a future reason-segmented score (R2 2b/R3). ``cluster_state`` is the
    # per-decision breach-audit substrate — recompute within-cap-ness at the admission, never trust the
    # enforcement code (R4 2a). None cluster ⇒ unclustered singleton ⇒ cap inert (per-name still binds).
    cluster = clusters.cluster_of(theme.symbol, cluster_map)
    cluster_remaining = cluster_state = None
    if cluster is not None:
        members = clusters.members_of(cluster, cluster_map)
        cluster_premium = state.cluster_open_premium(conn, members)
        cluster_cap = account_equity * cluster_fraction
        cluster_remaining = cluster_cap - cluster_premium
        cluster_state = {"cluster": cluster, "premium": cluster_premium, "cap": cluster_cap,
                         "equity": account_equity, "remaining": cluster_remaining}
        if cluster_remaining <= 0:
            result.vetoed += 1
            state.record_convexity_eval(
                conn, run_id=run_id, as_of=as_of_iso, theme=theme.name, symbol=theme.symbol,
                direction=theme.direction, decision="veto-cluster-cap", proposal_id=theme.proposal_id,
                reasons=[f"cluster {cluster!r} at/over budget (${cluster_premium:.0f} >= ${cluster_cap:.0f})"],
                cluster_state=cluster_state,
            )
            return

    # Discovery slot reservation (PREREG §5 / P1): a sentinel-origin candidate may not consume more
    # than config.discovery.sentinel_max_slots of the book's live positions, so auto-traded
    # discoveries can't starve hand-seed convictions. Hand-seed (sentinel_id None) is unbounded here.
    max_slots = config.get("discovery", {}).get("sentinel_max_slots")
    if (theme.sentinel_id is not None and max_slots is not None
            and state.count_open_sentinel_positions(conn) >= int(max_slots)):
        result.vetoed += 1
        state.record_convexity_eval(
            conn, run_id=run_id, as_of=as_of_iso, theme=theme.name, symbol=theme.symbol,
            direction=theme.direction, decision="veto-sentinel-slots", proposal_id=theme.proposal_id,
            reasons=[f"sentinel slot reservation full (>= {max_slots} open discovery positions)"],
        )
        return

    underlying_price = provider.underlying_price(theme.symbol)
    chain = provider.chain(theme.symbol)
    # Accrue the IV baseline (PREREG §4b): persist this cycle's snapshot, append-only.
    if chain_cache is not None:
        try:
            from convexity_data import persist_chain_snapshot

            persist_chain_snapshot(chain_cache, theme.symbol, chain, underlying_price, as_of_dt)
        except Exception as e:  # noqa: BLE001 — accrual is best-effort, never blocks a trade
            log.warning("snapshot persist failed for %s: %s", theme.symbol, e)
    rv_window = int(gate.get("rv_window_days", 252))
    closes = provider.closes(theme.symbol, window=rv_window)
    rv = realized_vol(closes, window=rv_window)

    # 1. Eligibility + defined-risk structure selection.
    structure, sreasons = select_structure(
        chain,
        direction=theme.direction,
        as_of=as_of,
        underlying_price=underlying_price,
        underlying_symbol=theme.symbol,
        require_otm_side=bool(gate.get("otm_side_guard", False)), min_otm_moneyness=float(gate.get("min_otm_moneyness", 0.0) or 0.0),
        tenor_min_days=int(gate.get("tenor_min_days", 180)),
        tenor_max_days=int(gate.get("tenor_max_days", 365)),
        target_moneyness=float(gate.get("target_moneyness", 0.25)),
        eligibility=eligibility,
    )
    if structure is None:
        result.vetoed += 1
        state.record_convexity_eval(
            conn, run_id=run_id, as_of=as_of_iso, theme=theme.name, symbol=theme.symbol,
            direction=theme.direction, eligible=False, decision="veto-eligibility",
            proposal_id=theme.proposal_id, reasons=list(sreasons),
        )
        return
    # #417: when a contract nearer the target strike was refused, say why on every row this evaluation writes.
    selection = ({"refused_nearer": [{"contract": sym, "reasons": list(why)} for sym, why in structure.refused_nearer]}
                 if structure.refused_nearer else None)
    if selection:
        log.info("Strike fallback %s: chose %s; nearer refused %s", theme.symbol, structure.contract.symbol,
                 "; ".join(f"{sym} ({', '.join(why)})" for sym, why in structure.refused_nearer))

    # 2. The IV / cheap-convexity gate (the hard veto).
    verdict = is_cheap_convexity(
        chain, underlying_price=underlying_price, wing=structure.contract, rv=rv,
        iv_rv_max=float(gate.get("iv_rv_max", 1.2)),
        otm_skew_max_volpts=float(gate.get("otm_skew_max_volpts", 10.0)),
    )
    q = _quote(structure.contract)
    log.info("Quote %s %s: bid %s ask %s mid %s spread %s%% (gate %s)", theme.symbol, structure.contract.symbol,
             q["bid"], q["ask"], q["mid"], q["spread_pct"], "cheap" if verdict.cheap else "veto")
    # The OPRA dual-read, INLINE arm (PREREG_DATA_FEED_OPRA_SEQUENCING §5–§6): record the
    # of-record verdict + the additive INDICATIVE shadow read for every gate-evaluated name.
    # Fail-SOFT — a shadow failure becomes a structured=0 note row, never a blocked evaluation.
    shadow_row = None
    if shadow_provider is not None:
        import gate_dualread as _dualread

        try:
            _dualread.record_arm(
                conn, run_id=run_id, as_of_iso=as_of_iso, symbol=theme.symbol, feed="opra",
                source="inline",
                row={"structured": True, "iv_rv": verdict.iv_rv_ratio,
                     "otm_skew": verdict.otm_skew_volpts, "cheap": bool(verdict.cheap),
                     "wing": structure.contract.symbol},
            )
            try:
                shadow_row = _dualread.shadow_gate_eval(
                    shadow_provider, symbol=theme.symbol, direction=theme.direction, rv=rv,
                    underlying_price=underlying_price, gate=gate, eligibility=eligibility)
                _dualread.record_arm(conn, run_id=run_id, as_of_iso=as_of_iso,
                                     symbol=theme.symbol, feed="indicative", source="inline",
                                     row=shadow_row)
            except Exception as e:  # noqa: BLE001 — the shadow arm never blocks
                _dualread.record_arm(conn, run_id=run_id, as_of_iso=as_of_iso,
                                     symbol=theme.symbol, feed="indicative", source="inline",
                                     error=str(e))
        except Exception as e:  # noqa: BLE001 — dual-read persistence itself is fail-soft
            log.warning("dual-read recording failed for %s: %s", theme.symbol, e)
    if not verdict.cheap:
        result.vetoed += 1
        state.record_convexity_eval(
            conn, run_id=run_id, as_of=as_of_iso, theme=theme.name, symbol=theme.symbol,
            direction=theme.direction, eligible=True, gate_cheap=False,
            iv_rv=verdict.iv_rv_ratio, otm_skew=verdict.otm_skew_volpts,
            decision="veto-iv-gate", proposal_id=theme.proposal_id, reasons=list(verdict.reasons), selection=selection,
        )
        return

    # The §5 disagree-veto (date-gated, auto-lapsing): the OPRA gate-of-record says CHEAP but the
    # INDICATIVE shadow arm disagrees (vetoes or can't structure) → no entry pending investigation.
    # The shadow can only TIGHTEN — it never authorizes — and the rule lapses at the dated
    # close-out (config.data_feed.dualread_disagree_veto_until) unless renewed by a dated edit.
    if (dualread_veto_active and shadow_row is not None
            and not (shadow_row.get("structured") and shadow_row.get("cheap"))):
        result.vetoed += 1
        state.record_convexity_eval(
            conn, run_id=run_id, as_of=as_of_iso, theme=theme.name, symbol=theme.symbol,
            direction=theme.direction, eligible=True, gate_cheap=True,
            iv_rv=verdict.iv_rv_ratio, otm_skew=verdict.otm_skew_volpts,
            decision="veto-dualread-disagree", proposal_id=theme.proposal_id,
            reasons=[f"OPRA cheap but INDICATIVE shadow disagrees: {shadow_row}"], selection=selection,
        )
        return

    # 2c. Over-cap call vertical (PREREG §5 amendment 2026-11-03b; inert unless
    # convexity_gate.vertical_for_over_cap.enabled). A bullish name whose ONE naked contract exceeds the per-name cap
    # is expressed as long this gated wing / short ≈+75%; the NET debit is then the premium-at-risk for every cap.
    import verticals

    vert, vwhy = verticals.maybe_vertical(
        chain, structure, config=config, direction=theme.direction, underlying_price=underlying_price,
        eligibility=eligibility, symbol=theme.symbol,
        per_name_cap=account_equity * float(book.get("per_name_fraction", 0.01)))
    if vwhy is not None:
        result.vetoed += 1
        state.record_convexity_eval(
            conn, run_id=run_id, as_of=as_of_iso, theme=theme.name, symbol=theme.symbol,
            direction=theme.direction, eligible=True, gate_cheap=True,
            iv_rv=verdict.iv_rv_ratio, otm_skew=verdict.otm_skew_volpts,
            decision="veto-vertical", proposal_id=theme.proposal_id,
            reasons=[f"naked contract over the per-name cap and no vertical: {vwhy}"], selection=selection,
        )
        return

    # 3. Sizing under the frozen caps. FINE cluster check first — a cluster with room but < one
    # contract records the structural veto-cluster-cap (not a generic veto-sizing); otherwise the
    # cluster budget tightens the greedy allocation to a bounded partial (composes into sizing's min()).
    from convexity_sizing import convexity_position_size

    # The entry limit: mid for an L1 entry; for a carried attempt (#386) the walk price — mid + fraction × (ask − mid),
    # never above the ask. Sizing and every cap below use THIS price, so a walked limit can only shrink the order.
    entry_px = structure.entry_premium
    if vert is not None:   # the vertical's mid debit; a carry walks it toward the natural debit (long ask − short bid)
        entry_px = (verticals.walk_limit(vert, float(walk.get("fraction", 0.0))) if walk is not None
                    else round(vert.net_debit, 2))
    elif walk is not None:
        ask = structure.contract.ask
        frac = min(max(float(walk.get("fraction", 0.0)), 0.0), 1.0)
        if ask is not None and ask > entry_px:
            entry_px = round(min(entry_px + frac * (ask - entry_px), ask), 2)
    premium_per_contract = entry_px * 100.0
    if cluster_remaining is not None and cluster_remaining < premium_per_contract:
        result.vetoed += 1
        state.record_convexity_eval(
            conn, run_id=run_id, as_of=as_of_iso, theme=theme.name, symbol=theme.symbol,
            direction=theme.direction, eligible=True, gate_cheap=True,
            iv_rv=verdict.iv_rv_ratio, otm_skew=verdict.otm_skew_volpts,
            decision="veto-cluster-cap", proposal_id=theme.proposal_id,
            reasons=[f"cluster {cluster!r} budget ${cluster_remaining:.0f} < one contract ${premium_per_contract:.0f}"],
            cluster_state=cluster_state, selection=selection,
        )
        return

    sizing = convexity_position_size(
        account_equity=account_equity,
        book_fraction=float(book.get("book_fraction", 0.10)),
        per_name_fraction=float(book.get("per_name_fraction", 0.01)),
        max_open_positions=int(book.get("max_open_positions", 15)),
        # committed = open + closing + pending (#386): a working order reserves its slot and premium, so a carried
        # attempt and a same-cycle entry can't both be sized against budget the other already holds
        open_positions_count=state.count_committed_positions(conn),
        open_premium_total=state.committed_book_premium(conn),
        entry_premium_per_share=entry_px,
        cluster_remaining=cluster_remaining,
    )
    if sizing.contracts < 1:
        result.vetoed += 1
        state.record_convexity_eval(
            conn, run_id=run_id, as_of=as_of_iso, theme=theme.name, symbol=theme.symbol,
            direction=theme.direction, eligible=True, gate_cheap=True,
            iv_rv=verdict.iv_rv_ratio, otm_skew=verdict.otm_skew_volpts,
            decision="veto-sizing", proposal_id=theme.proposal_id, reasons=list(sizing.reasons),
            cluster_state=cluster_state, selection=selection,
        )
        return

    # 3b. Foreign-quantity check (issue #279; finance#947 §3). The live account is shared and Alpaca nets
    # per OCC contract, so before opening, the venue quantity in THIS contract must equal what this
    # project's journal explains. A mismatch (another project holds it) or an unreadable venue → no entry.
    # A broker with no venue (the simulated PaperBroker) has no ``venue_quantity`` and skips the check.
    if callable(getattr(broker, "venue_quantity", None)):
        # a vertical reads BOTH contracts (the short leg is a negative venue quantity the journal must explain)
        why = None
        for leg in ([structure.contract.symbol] + ([vert.short.symbol] if vert is not None else [])):
            venue_qty = broker.venue_quantity(leg)
            journal_qty = state.journal_contract_quantity(conn, leg)
            if venue_qty is None or venue_qty != journal_qty:
                why = ("venue quantity unreadable" if venue_qty is None
                       else f"venue holds {venue_qty} but this journal explains {journal_qty}")
                if leg != structure.contract.symbol:
                    why = f"short leg {leg}: {why}"
                break
        if why is not None:
            result.vetoed += 1
            state.record_convexity_eval(
                conn, run_id=run_id, as_of=as_of_iso, theme=theme.name, symbol=theme.symbol,
                direction=theme.direction, eligible=True, gate_cheap=True,
                iv_rv=verdict.iv_rv_ratio, otm_skew=verdict.otm_skew_volpts,
                decision="veto-foreign-quantity", proposal_id=theme.proposal_id,
                reasons=[f"{structure.contract.symbol}: {why} (shared account, fail-closed)"], selection=selection,
            )
            log.error("foreign-quantity veto %s: %s", structure.contract.symbol, why)
            try:
                import notify
                notify.send("Foreign quantity — entry refused",
                            f"{structure.contract.symbol}: {why}. Reconcile across projects before resuming "
                            "(finance#947 §6).", priority=1)
            except Exception:  # noqa: BLE001 — paging never breaks the cycle
                log.warning("foreign-quantity page failed to send")
            return

    # 4. Paper fill (simulated at mid). A vertical is ONE atomic multi-leg order, never legged.
    coid = (make_client_order_id("open", structure.contract.symbol, str(as_of))
            + (f"-c{int(walk['step'])}" if walk is not None else ""))
    if vert is not None:
        if not callable(getattr(broker, "submit_spread", None)):
            from broker import Fill

            fill = Fill(False, 0.0, 0, "broker has no multi-leg order path (fail-closed)")
        else:
            fill = broker.submit_spread(long_symbol=structure.contract.symbol, short_symbol=vert.short.symbol,
                                        qty=sizing.contracts, action="open", limit_price=entry_px,
                                        client_order_id=coid)
    else:
        fill = broker.submit_paper(
            contract_symbol=structure.contract.symbol, qty=sizing.contracts, side="buy",
            limit_price=entry_px, client_order_id=coid,
        )
    if not fill.filled:
        result.vetoed += 1
        state.record_convexity_eval(
            conn, run_id=run_id, as_of=as_of_iso, theme=theme.name, symbol=theme.symbol,
            direction=theme.direction, eligible=True, gate_cheap=True,
            iv_rv=verdict.iv_rv_ratio, otm_skew=verdict.otm_skew_volpts,
            decision="veto-fill", proposal_id=theme.proposal_id, reasons=[fill.note], selection=selection,
        )
        if vert is not None:   # a refused multi-leg open (e.g. the account's options level) must not be silent
            try:
                import notify

                notify.send("VERTICAL ORDER REFUSED",
                            f"{theme.symbol} +{structure.contract.symbol}/-{vert.short.symbol} {sizing.contracts}x "
                            f"@ {entry_px:.2f} debit: {fill.note}", priority=1)
            except Exception:  # noqa: BLE001 — paging never breaks the cycle
                log.warning("vertical refusal page failed to send")
        return

    # 5. Log the paper position + the survivorship-log row.
    # A real Alpaca limit may rest unfilled → record 'pending' (the monitor reconciles it);
    # a simulated/immediate fill is 'open'. Use the broker's actual fill price.
    pending = getattr(fill, "pending", False)
    status = "pending" if pending else "open"
    fill_premium_per_contract = fill.price * 100.0
    rationale = {
        "thesis": theme.thesis,
        "gate": list(verdict.reasons),
        "sizing": list(sizing.reasons),
        "fill": fill.note,
        "rv": verdict.rv, "atm_iv": verdict.atm_iv, "wing_iv": verdict.wing_iv,
        "quote": q,
    }
    if theme.entry_origin:
        rationale["origin"] = theme.entry_origin   # PREREG §5 amendment 2026-11-03: scored apart (real_by_origin)
    if vert is not None:
        rationale["vertical"] = {"short": vert.short.symbol, "short_strike": vert.short.strike,
                                 "short_moneyness": round(vert.short_moneyness, 4), "width": vert.width,
                                 "naked_premium": round(structure.entry_premium, 4),
                                 "short_quote": _quote(vert.short)}
    if walk is not None:
        rationale["carry"] = {"of": walk.get("intent_id"), "step": int(walk.get("step", 0)), "limit": entry_px}
    pos_id = state.record_convexity_position(
        conn, run_id=run_id, opened_at=as_of_iso, theme=theme.name, symbol=theme.symbol,
        direction=theme.direction, structure_kind=structure.kind,
        contract_symbol=structure.contract.symbol, expiry=structure.contract.expiry.isoformat(),
        strike=structure.contract.strike, dte=structure.dte, moneyness=structure.moneyness,
        contracts=sizing.contracts, entry_premium_per_contract=fill_premium_per_contract,
        total_premium=fill_premium_per_contract * sizing.contracts, rationale=rationale,
        status=status, order_id=getattr(fill, "order_id", None),
        proposal_id=theme.proposal_id, entry_spot=underlying_price,
        short_contract_symbol=(vert.short.symbol if vert is not None else None),
        short_strike=(vert.short.strike if vert is not None else None),
    )
    # Link the council proposal to the position it became (T2 forward-scoring substrate).
    if theme.proposal_id is not None:
        state.link_proposal_position(conn, theme.proposal_id, pos_id)
        # T3: a sentinel that actually TRADED is now linked (sentinel.proposal_id set) → it resolves
        # at close (monitor) rather than via the never-traded reference-return sweep.
        if theme.sentinel_id is not None:
            state.link_sentinel_proposal(conn, theme.sentinel_id, theme.proposal_id)
    state.record_convexity_eval(
        conn, run_id=run_id, as_of=as_of_iso, theme=theme.name, symbol=theme.symbol,
        direction=theme.direction, eligible=True, gate_cheap=True,
        iv_rv=verdict.iv_rv_ratio, otm_skew=verdict.otm_skew_volpts,
        decision=(("carry-" if walk is not None else "") + ("submit-pending" if pending else "open")), position_id=pos_id,
        proposal_id=theme.proposal_id, reasons=list(verdict.reasons), cluster_state=cluster_state, selection=selection,
    )
    result.opened += 1
    result.opened_ids.append(pos_id)
    log.info(
        "%s #%d %s %s %dx %s @ %.2f (%.1f%% OTM, %dd) — %s",
        "SUBMITTED" if pending else "OPENED", pos_id, theme.name, structure.kind,
        sizing.contracts, structure.contract.symbol, fill.price,
        structure.moneyness * 100, structure.dte, theme.thesis[:60],
    )
    # A real order is resting at the broker: page it as it happens (2026-10-27 — HL's first above-floor order since
    # July was submitted and cancelled unfilled 12 minutes later, and the operator learned of it from the grade).
    if pending and (walk is None or int(walk.get("step", 0)) == 0):   # a carry pages its first attempt only
        try:
            import notify

            legs = (f"+{structure.contract.symbol}/-{vert.short.symbol} (vertical, net debit)" if vert is not None
                    else structure.contract.symbol)
            notify.send("REAL-BOOK ORDER SUBMITTED",
                        f"#{pos_id} {theme.symbol} {sizing.contracts}x {legs} LIMIT "
                        f"{fill.price:.2f} (${fill_premium_per_contract * sizing.contracts:,.0f}); quote "
                        f"{q['bid']}/{q['ask']} spread {q['spread_pct']}%. Reconciles at the next L2.")
        except Exception:  # noqa: BLE001 — paging never breaks the cycle
            log.warning("order page failed to send")
