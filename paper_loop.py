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


def kill_rule_status(conn, config: dict, clock: Clock) -> KillRuleStatus:
    """Evaluate the §6 kill rule from state. Halts NEW entries (does not force-close).

    T1 scope: book-drawdown is computed from position *marks* when present (NULL marks →
    no drawdown yet, since T1 does not mark-to-market — that lands with position tracking in
    Phase 2). ``months_dry`` is surfaced for visibility but does not trip until realized
    payoff tracking exists. The check is wired and called every cycle so it activates
    automatically once marks/outcomes are recorded.
    """
    kr = config.get("kill_rule", {})
    book = config.get("convexity_book", {})
    dd_halt = float(kr.get("book_drawdown_halt", 0.20))
    book_budget = float(book.get("account_equity", 0.0)) * float(book.get("book_fraction", 0.0))

    book_dd, _have_marks = state.convexity_book_drawdown(conn, book_budget)

    reasons: list[str] = []
    tripped = False
    if book_dd >= dd_halt:
        tripped = True
        reasons.append(f"book drawdown {book_dd:.0%} >= {dd_halt:.0%}")
    return KillRuleStatus(tripped=tripped, book_drawdown=book_dd, months_dry=0.0, reasons=tuple(reasons))


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
) -> CycleResult:
    """Run one paper cycle over the active themes. Returns a CycleResult.

    ``chain_cache`` (optional ``PointInTimeCache``): when supplied, each theme's current
    chain snapshot is persisted (append-only) so an IV-rank baseline accrues over time
    (PREREG §4b). ``None`` (e.g. the offline demo) skips persistence.
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
    account_equity = float(book.get("account_equity") or broker.account_equity())

    # Correlation-cluster exposure cap (PREREG §5 amendment 2026-06-03): an operator-curated
    # symbol→cluster map caps aggregate ENTRY-premium per correlated cluster — the per-name cap alone
    # reads a correlated basket (e.g. the AI-capex-into-power names) as false diversification. Inert
    # without a positive cluster_fraction (then every name is its own singleton). load raises on a
    # malformed map (overlap / cap < per-name) — fail-closed.
    cluster_fraction = float(book.get("cluster_fraction") or 0.0)
    cluster_map = clusters.load_cluster_map(config) if cluster_fraction > 0 else {}

    # Dedup: one open position per underlying for T1 (one name per theme). Re-running the loop
    # must not stack duplicate bets on a theme that is already on.
    open_syms = state.open_position_symbols(conn)

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

    for theme in themes:
        if not theme.active:
            continue
        result.evaluated += 1
        if theme.symbol in open_syms:
            result.skipped += 1
            state.record_convexity_eval(
                conn, run_id=run_id, as_of=as_of_iso, theme=theme.name, symbol=theme.symbol,
                direction=theme.direction, decision="skip-already-open", proposal_id=theme.proposal_id,
                reasons=[f"{theme.symbol} already has an open position"],
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
            )
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
    return result


def _process_theme(
    theme: Theme, *, config, conn, provider, broker, eligibility, account_equity, gate, book,
    cluster_map, cluster_fraction, as_of, as_of_dt, as_of_iso, run_id, result: CycleResult,
    chain_cache=None, shadow_provider=None, dualread_veto_active=False,
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

    # 2. The IV / cheap-convexity gate (the hard veto).
    verdict = is_cheap_convexity(
        chain, underlying_price=underlying_price, wing=structure.contract, rv=rv,
        iv_rv_max=float(gate.get("iv_rv_max", 1.2)),
        otm_skew_max_volpts=float(gate.get("otm_skew_max_volpts", 10.0)),
    )
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
            decision="veto-iv-gate", proposal_id=theme.proposal_id, reasons=list(verdict.reasons),
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
            reasons=[f"OPRA cheap but INDICATIVE shadow disagrees: {shadow_row}"],
        )
        return

    # 3. Sizing under the frozen caps. FINE cluster check first — a cluster with room but < one
    # contract records the structural veto-cluster-cap (not a generic veto-sizing); otherwise the
    # cluster budget tightens the greedy allocation to a bounded partial (composes into sizing's min()).
    from convexity_sizing import convexity_position_size

    premium_per_contract = structure.entry_premium * 100.0
    if cluster_remaining is not None and cluster_remaining < premium_per_contract:
        result.vetoed += 1
        state.record_convexity_eval(
            conn, run_id=run_id, as_of=as_of_iso, theme=theme.name, symbol=theme.symbol,
            direction=theme.direction, eligible=True, gate_cheap=True,
            iv_rv=verdict.iv_rv_ratio, otm_skew=verdict.otm_skew_volpts,
            decision="veto-cluster-cap", proposal_id=theme.proposal_id,
            reasons=[f"cluster {cluster!r} budget ${cluster_remaining:.0f} < one contract ${premium_per_contract:.0f}"],
            cluster_state=cluster_state,
        )
        return

    sizing = convexity_position_size(
        account_equity=account_equity,
        book_fraction=float(book.get("book_fraction", 0.10)),
        per_name_fraction=float(book.get("per_name_fraction", 0.01)),
        max_open_positions=int(book.get("max_open_positions", 15)),
        open_positions_count=state.count_open_convexity_positions(conn),
        open_premium_total=state.convexity_book_open_premium(conn),
        entry_premium_per_share=structure.entry_premium,
        cluster_remaining=cluster_remaining,
    )
    if sizing.contracts < 1:
        result.vetoed += 1
        state.record_convexity_eval(
            conn, run_id=run_id, as_of=as_of_iso, theme=theme.name, symbol=theme.symbol,
            direction=theme.direction, eligible=True, gate_cheap=True,
            iv_rv=verdict.iv_rv_ratio, otm_skew=verdict.otm_skew_volpts,
            decision="veto-sizing", proposal_id=theme.proposal_id, reasons=list(sizing.reasons),
            cluster_state=cluster_state,
        )
        return

    # 4. Paper fill (simulated at mid).
    fill = broker.submit_paper(
        contract_symbol=structure.contract.symbol, qty=sizing.contracts, side="buy",
        limit_price=structure.entry_premium,
        client_order_id=make_client_order_id("open", structure.contract.symbol, str(as_of)),
    )
    if not fill.filled:
        result.vetoed += 1
        state.record_convexity_eval(
            conn, run_id=run_id, as_of=as_of_iso, theme=theme.name, symbol=theme.symbol,
            direction=theme.direction, eligible=True, gate_cheap=True,
            iv_rv=verdict.iv_rv_ratio, otm_skew=verdict.otm_skew_volpts,
            decision="veto-fill", proposal_id=theme.proposal_id, reasons=[fill.note],
        )
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
    }
    pos_id = state.record_convexity_position(
        conn, run_id=run_id, opened_at=as_of_iso, theme=theme.name, symbol=theme.symbol,
        direction=theme.direction, structure_kind=structure.kind,
        contract_symbol=structure.contract.symbol, expiry=structure.contract.expiry.isoformat(),
        strike=structure.contract.strike, dte=structure.dte, moneyness=structure.moneyness,
        contracts=sizing.contracts, entry_premium_per_contract=fill_premium_per_contract,
        total_premium=fill_premium_per_contract * sizing.contracts, rationale=rationale,
        status=status, order_id=getattr(fill, "order_id", None),
        proposal_id=theme.proposal_id, entry_spot=underlying_price,
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
        decision=("submit-pending" if pending else "open"), position_id=pos_id,
        proposal_id=theme.proposal_id, reasons=list(verdict.reasons), cluster_state=cluster_state,
    )
    result.opened += 1
    result.opened_ids.append(pos_id)
    log.info(
        "%s #%d %s %s %dx %s @ %.2f (%.1f%% OTM, %dd) — %s",
        "SUBMITTED" if pending else "OPENED", pos_id, theme.name, structure.kind,
        sizing.contracts, structure.contract.symbol, fill.price,
        structure.moneyness * 100, structure.dte, theme.thesis[:60],
    )
