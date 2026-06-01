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
from clock import Clock
from convexity_data import QuoteProvider
from council import scoring
from options_tradability import parse_osi

log = logging.getLogger("monitor")

CONTRACT_MULTIPLIER = 100.0


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
) -> MonitorResult:
    """Mark + apply exits to every open position. Returns a MonitorResult.

    ``underlying_price_of(symbol) -> float | None`` is used only at expiry (intrinsic). When
    omitted, expiring positions close at their last available mid (or 0 if unmarked) — the
    far-OTM expectation is ~0 anyway.
    """
    exits = config.get("convexity_exits", {})
    profit_mult = float(exits.get("profit_take_multiple", 4.0))
    time_stop_dte = int(exits.get("time_stop_dte", 21))
    conv_map = config.get("council", {}).get("conviction_to_prob")
    now = clock.now()
    today = now.date()
    as_of_iso = now.isoformat()
    res = MonitorResult()

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
            state.close_convexity_position(
                conn, pid, exit_price=intrinsic, realized_pnl=pnl,
                reason="expiry", as_of=as_of_iso,
            )
            _maybe_resolve_proposal(conn, pos, reason="expiry", as_of=as_of_iso,
                                    conviction_to_prob=conv_map, intrinsic=intrinsic, exit_spot=up)
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
            pnl = _realized(mid, entry_pc, contracts)
            reason = f"profit_take_{profit_mult:g}x"
            state.close_convexity_position(
                conn, pid, exit_price=mid, realized_pnl=pnl, reason=reason, as_of=as_of_iso,
            )
            up = underlying_price_of(pos["symbol"]) if underlying_price_of else None
            _maybe_resolve_proposal(conn, pos, reason=reason, as_of=as_of_iso,
                                    conviction_to_prob=conv_map, exit_spot=up)
            res.profit_taken += 1
            res.closed += 1
            res.realized_pnl += pnl
            log.info("PROFIT-TAKE #%d %s @ %.2f (%.1fx) → P&L $%.0f", pid, pos["contract_symbol"], mid, mid * CONTRACT_MULTIPLIER / entry_pc, pnl)
            continue

        # 4. Time-stop: close when ≤ time_stop_dte days to expiry (avoid the theta/gamma endgame).
        if dte is not None and dte <= time_stop_dte:
            pnl = _realized(mid, entry_pc, contracts)
            reason = f"time_stop_{time_stop_dte}dte"
            state.close_convexity_position(
                conn, pid, exit_price=mid, realized_pnl=pnl, reason=reason, as_of=as_of_iso,
            )
            # Time-stop resolution genuinely needs the underlying (not consulted elsewhere).
            up = underlying_price_of(pos["symbol"]) if underlying_price_of else None
            _maybe_resolve_proposal(conn, pos, reason=reason, as_of=as_of_iso,
                                    conviction_to_prob=conv_map, exit_spot=up)
            res.time_stopped += 1
            res.closed += 1
            res.realized_pnl += pnl
            log.info("TIME-STOP #%d %s @ %.2f (%dd left) → P&L $%.0f", pid, pos["contract_symbol"], mid, dte, pnl)

    return res


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
