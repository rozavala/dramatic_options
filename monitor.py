"""L2 position monitor (T1.5) — deterministic, no LLM (the fast reflex, SPEC §3).

Marks open convexity positions to their current option mid and applies the frozen exit
rules (PREREG_THEMATIC_CONVEXITY §6a): **profit-take** at a configured multiple of entry
premium, **time-stop** near expiry, and **expiry** close at intrinsic. The intelligence was
front-loaded at entry; this loop only watches and fires deterministic exits. It also
**reconciles** real (non-dry) Alpaca orders that were left 'pending'.

Pure-ish: all I/O is injected (a ``QuoteProvider`` for marks, a ``Clock`` for now, the DB
conn). No network here — the providers own that. Offline-testable with ``StaticQuoteProvider``
and ``FixedClock``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime

import state
from broker import make_client_order_id
from clock import Clock
from convexity_data import QuoteProvider
from council import scoring
from options_tradability import parse_osi

log = logging.getLogger("monitor")

CONTRACT_MULTIPLIER = 100.0


def _close_and_resolve(conn, pos, *, exit_price, realized_pnl, reason, as_of, conv_map,
                       intrinsic=None, exit_spot=None) -> None:
    """Book a position closed (in-DB) and resolve its council proposal at the actual exit."""
    state.close_convexity_position(conn, int(pos["id"]), exit_price=exit_price,
                                   realized_pnl=realized_pnl, reason=reason, as_of=as_of)
    _maybe_resolve_proposal(conn, pos, reason=reason, as_of=as_of, conviction_to_prob=conv_map,
                            intrinsic=intrinsic, exit_spot=exit_spot)


def _maybe_resolve_proposal(
    conn, pos, *, reason: str, as_of: str, conviction_to_prob, intrinsic=None, exit_spot=None
) -> None:
    """Resolve a council proposal's forward outcome when its position closes (T2 substrate).

    No-op for hand-seeded positions (no ``proposal_id``). Outcome is favorable/unfavorable/None;
    None (genuinely unresolved — spot unavailable on a time-stop) is recorded, never fabricated.
    """
    pid = pos["proposal_id"]
    if not pid:
        return
    prop = state.council_proposal_by_id(conn, int(pid))
    if prop is None:
        return
    outcome, b = scoring.resolve(
        reason, direction=pos["direction"], conviction=prop["conviction"],
        intrinsic=intrinsic, exit_spot=exit_spot, entry_spot=pos["entry_spot"],
        conviction_to_prob=conviction_to_prob,
    )
    state.resolve_proposal(conn, int(pid), outcome=outcome, brier=b, resolved_at=as_of)


@dataclass
class MonitorResult:
    marked: int = 0
    closed: int = 0
    closing: int = 0          # real SELL_TO_CLOSE submitted, awaiting fill (T2.5 two-sided)
    expired: int = 0
    profit_taken: int = 0
    time_stopped: int = 0
    unmarked: int = 0
    realized_pnl: float = 0.0
    notes: list[str] = field(default_factory=list)


def intrinsic_value(kind: str, strike: float, underlying_price: float | None) -> float:
    """Per-share intrinsic value of an option at expiry. 0 if underlying unknown."""
    if underlying_price is None:
        return 0.0
    if kind == "C":
        return max(0.0, underlying_price - strike)
    return max(0.0, strike - underlying_price)


def _realized(exit_mid: float, entry_per_contract: float, contracts: int) -> float:
    """Realized P&L = (exit_mid·100 − entry_per_contract)·contracts."""
    return (exit_mid * CONTRACT_MULTIPLIER - entry_per_contract) * contracts


def monitor_positions(
    *,
    conn,
    clock: Clock,
    quote_provider: QuoteProvider,
    config: dict,
    underlying_price_of=None,
    broker=None,
    dry_run: bool = True,
) -> MonitorResult:
    """Mark + apply exits to every open position. Returns a MonitorResult.

    Exits are **two-sided** when ``broker`` is supplied and ``dry_run`` is False (T2.5): a
    profit-take or time-stop on a **marketable** name transmits a real SELL_TO_CLOSE (booked at
    the *actual* fill on reconcile — an honest exit price, not the mid); an **un-sellable** far-OTM
    (bid below ``min_close_bid``) books in-DB at mark, avoiding an open↔closing churn deadlock;
    expiry books intrinsic. In DRY_RUN / sim (no broker) every exit books in-DB at mark, as before.
    ``underlying_price_of(symbol)`` is used at expiry (intrinsic) + to resolve time-stops.
    """
    exits = config.get("convexity_exits", {})
    profit_mult = float(exits.get("profit_take_multiple", 4.0))
    time_stop_dte = int(exits.get("time_stop_dte", 21))
    min_close_bid = float(exits.get("min_close_bid", 0.05))
    conv_map = config.get("council", {}).get("conviction_to_prob")
    now = clock.now()
    today = now.date()
    as_of_iso = now.isoformat()
    res = MonitorResult()
    real_submit = broker is not None and not dry_run

    # 0. Reconcile in-flight SELL_TO_CLOSE orders first (fill → closed at the real fill, terminal →
    #    reopen, expiry-while-closing → cancel + intrinsic). Closing positions are NOT re-evaluated
    #    for exit below (they're not in open_convexity_positions).
    if real_submit:
        _reconcile_closing(conn, broker=broker, today=today, as_of_iso=as_of_iso,
                           underlying_price_of=underlying_price_of, conv_map=conv_map, res=res)

    for pos in state.open_convexity_positions(conn):
        pid = int(pos["id"])
        kind = pos["structure_kind"]
        contracts = int(pos["contracts"])
        entry_pc = float(pos["entry_premium_per_contract"])
        expiry = _parse_date(pos["expiry"])
        dte = (expiry - today).days if expiry else None

        # 1. Expiry → close at intrinsic.
        if expiry is not None and today >= expiry:
            up = underlying_price_of(pos["symbol"]) if underlying_price_of else None
            intrinsic = intrinsic_value(kind, float(pos["strike"]), up)
            pnl = _realized(intrinsic, entry_pc, contracts)
            _close_and_resolve(conn, pos, exit_price=intrinsic, realized_pnl=pnl, reason="expiry",
                               as_of=as_of_iso, conv_map=conv_map, intrinsic=intrinsic, exit_spot=up)
            res.expired += 1
            res.closed += 1
            res.realized_pnl += pnl
            log.info("EXPIRED #%d %s @ intrinsic %.2f → P&L $%.0f", pid, pos["contract_symbol"], intrinsic, pnl)
            continue

        # 2. Mark to current mid.
        mid = quote_provider.option_mid(pos["contract_symbol"])
        if mid is None:
            res.unmarked += 1
            log.warning("no quote to mark #%d %s — left unmarked", pid, pos["contract_symbol"])
            continue
        state.mark_convexity_position(conn, pid, mark=mid, as_of=as_of_iso)
        res.marked += 1

        # 3. Profit-take: mark ≥ profit_mult × entry (per-contract basis).
        if entry_pc > 0 and mid * CONTRACT_MULTIPLIER >= profit_mult * entry_pc:
            _exit_position(conn, pos, mid=mid, entry_pc=entry_pc, contracts=contracts,
                           reason=f"profit_take_{profit_mult:g}x", real_submit=real_submit,
                           broker=broker, quote_provider=quote_provider, min_close_bid=min_close_bid,
                           today=today, as_of_iso=as_of_iso, underlying_price_of=underlying_price_of,
                           conv_map=conv_map, res=res, counter="profit_taken")
            continue

        # 4. Time-stop: close when ≤ time_stop_dte days to expiry (avoid the theta/gamma endgame).
        if dte is not None and dte <= time_stop_dte:
            _exit_position(conn, pos, mid=mid, entry_pc=entry_pc, contracts=contracts,
                           reason=f"time_stop_{time_stop_dte}dte", real_submit=real_submit,
                           broker=broker, quote_provider=quote_provider, min_close_bid=min_close_bid,
                           today=today, as_of_iso=as_of_iso, underlying_price_of=underlying_price_of,
                           conv_map=conv_map, res=res, counter="time_stopped")

    return res


def _exit_position(
    conn, pos, *, mid, entry_pc, contracts, reason, real_submit, broker, quote_provider,
    min_close_bid, today, as_of_iso, underlying_price_of, conv_map, res, counter,
) -> None:
    """Exit a triggered position. Two-sided real submit when marketable; else book in-DB at mark.

    ``counter`` is the trigger counter to bump ('profit_taken'/'time_stopped'). Realized P&L only
    accrues when the position is actually *booked closed* (an immediate fill, an in-DB book, or —
    later — a reconciled sell); a resting SELL_TO_CLOSE bumps ``res.closing`` and waits.
    """
    pid = int(pos["id"])
    contract = pos["contract_symbol"]
    setattr(res, counter, getattr(res, counter) + 1)

    if real_submit:
        bid = quote_provider.option_bid(contract)
        if bid is not None and bid >= min_close_bid:
            coid = make_client_order_id("close", contract, str(today))
            fill = broker.submit_paper(contract_symbol=contract, qty=contracts, side="sell",
                                       limit_price=round(float(bid), 2), client_order_id=coid)
            if not fill.filled:
                log.warning("SELL_TO_CLOSE submit failed #%d %s — left open to retry: %s", pid, contract, fill.note)
                return  # stays 'open' → re-evaluated next cycle
            if getattr(fill, "pending", False):
                state.begin_close_convexity_position(conn, pid, close_order_id=(fill.order_id or coid),
                                                     reason=reason, as_of=as_of_iso)
                res.closing += 1
                log.info("SELL_TO_CLOSE submitted #%d %s @ %.2f (resting) → closing", pid, contract, float(bid))
                return
            up = underlying_price_of(pos["symbol"]) if underlying_price_of else None
            pnl = _realized(fill.price, entry_pc, contracts)
            _close_and_resolve(conn, pos, exit_price=fill.price, realized_pnl=pnl, reason=reason,
                               as_of=as_of_iso, conv_map=conv_map, exit_spot=up)
            res.closed += 1
            res.realized_pnl += pnl
            log.info("SELL_TO_CLOSE FILLED #%d %s @ %.2f → P&L $%.0f", pid, contract, fill.price, pnl)
            return
        # Non-marketable (worthless/illiquid) → book in-DB at mark, no churn (the `reason` prefix
        # is preserved so the forward-scoring resolution still keys correctly).
        reason = reason + "_unsellable"

    up = underlying_price_of(pos["symbol"]) if underlying_price_of else None
    pnl = _realized(mid, entry_pc, contracts)
    _close_and_resolve(conn, pos, exit_price=mid, realized_pnl=pnl, reason=reason, as_of=as_of_iso,
                       conv_map=conv_map, exit_spot=up)
    res.closed += 1
    res.realized_pnl += pnl
    log.info("EXIT(in-DB) #%d %s @ %.2f (%s) → P&L $%.0f", pid, contract, mid, reason, pnl)


def _reconcile_closing(
    conn, *, broker, today, as_of_iso, underlying_price_of, conv_map, res,
) -> None:
    """Reconcile in-flight SELL_TO_CLOSE orders. Closes are left resting until they fill (NOT
    cancel_unfilled'd — that would re-use the single-use per-day id); a terminal order reopens the
    position to retry next cycle; expiry-while-closing cancels the sell and books intrinsic."""
    for pos in state.closing_positions(conn):
        pid = int(pos["id"])
        contracts = int(pos["contracts"])
        entry_pc = float(pos["entry_premium_per_contract"])
        oid = pos["close_order_id"]
        reason = pos["exit_reason"] or "close"
        expiry = _parse_date(pos["expiry"])

        if expiry is not None and today >= expiry:  # expiry while closing → cancel + intrinsic
            if oid and hasattr(broker, "cancel_order"):
                broker.cancel_order(oid)
            up = underlying_price_of(pos["symbol"]) if underlying_price_of else None
            intrinsic = intrinsic_value(pos["structure_kind"], float(pos["strike"]), up)
            pnl = _realized(intrinsic, entry_pc, contracts)
            _close_and_resolve(conn, pos, exit_price=intrinsic, realized_pnl=pnl, reason="expiry",
                               as_of=as_of_iso, conv_map=conv_map, intrinsic=intrinsic, exit_spot=up)
            res.expired += 1
            res.closed += 1
            res.realized_pnl += pnl
            continue

        if not oid or not hasattr(broker, "order_status"):
            continue
        info = broker.order_status(oid)
        if info is None:
            continue
        st = str(info.get("state", "")).lower()
        if st == "filled":
            price = float(info.get("filled_avg_price") or (entry_pc / CONTRACT_MULTIPLIER))
            up = underlying_price_of(pos["symbol"]) if underlying_price_of else None
            pnl = _realized(price, entry_pc, contracts)
            _close_and_resolve(conn, pos, exit_price=price, realized_pnl=pnl, reason=reason,
                               as_of=as_of_iso, conv_map=conv_map, exit_spot=up)
            res.closed += 1
            res.realized_pnl += pnl
            log.info("CLOSE FILLED (reconciled) #%d %s @ %.2f → P&L $%.0f", pid, pos["contract_symbol"], price, pnl)
        elif st in ("canceled", "cancelled", "expired", "rejected"):
            state.revert_closing_to_open(conn, pid, reason=f"close_{st}")  # retry next cycle (fresh id)
            log.info("CLOSE %s (reconciled) #%d %s — reopened to retry", st, pid, pos["contract_symbol"])
        # resting (new/accepted/partially_filled) → leave it working; no cancel_unfilled for closes


def reconcile_pending(*, conn, broker, clock: Clock, config: dict) -> int:
    """Reconcile real (non-dry) Alpaca orders left 'pending': fill→open, terminal→cancel.

    ``broker`` must expose ``order_status(order_id) -> dict|None`` with at least
    ``{state, filled_avg_price, filled_qty}``. DRY_RUN positions are never pending, so this is
    a no-op in the default path. Returns the number of positions reconciled.
    """
    if not hasattr(broker, "order_status"):
        return 0
    cancel_unfilled = bool(config.get("execution", {}).get("cancel_unfilled", True))
    now_iso = clock.now().isoformat()
    n = 0
    for pos in state.pending_convexity_positions(conn):
        oid = pos["order_id"]
        if not oid:
            continue
        info = broker.order_status(oid)
        if info is None:
            continue
        st = str(info.get("state", "")).lower()
        if st == "filled":
            price = float(info.get("filled_avg_price") or pos["entry_premium_per_contract"] / CONTRACT_MULTIPLIER)
            per_contract = price * CONTRACT_MULTIPLIER
            state.confirm_convexity_fill(
                conn, int(pos["id"]), entry_premium_per_contract=per_contract,
                total_premium=per_contract * int(pos["contracts"]), opened_at=now_iso,
            )
            n += 1
            log.info("FILLED (reconciled) #%d %s @ %.2f", pos["id"], pos["contract_symbol"], price)
        elif st in ("canceled", "cancelled", "expired", "rejected"):
            state.drop_convexity_position(conn, int(pos["id"]), reason=f"order_{st}")
            n += 1
        elif cancel_unfilled and st in ("new", "accepted", "pending_new", "partially_filled"):
            if hasattr(broker, "cancel_order"):
                broker.cancel_order(oid)
            state.drop_convexity_position(conn, int(pos["id"]), reason="cancelled_unfilled")
            n += 1
    return n


def _parse_date(value) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)).date() if "T" in str(value) else date.fromisoformat(str(value))
    except ValueError:
        info = parse_osi(str(value))
        return info["expiry"] if info else None
