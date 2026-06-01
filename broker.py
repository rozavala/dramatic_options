"""Execution seam — paper brokers (T1.5).

Two brokers behind one ``Broker`` protocol:
  - ``PaperBroker`` — simulated fill at the supplied mid, no I/O (offline demo + tests).
  - ``AlpacaPaperBroker`` — real Alpaca **paper** order submission, with its own
    ``TradingClient`` (the read-only ``AlpacaClient`` stays submit-free, a Phase-0 guardrail).
    **Sending is gated by DRY_RUN (guardrail §1):** when ``dry_run`` is true (the default) it
    logs the exact intended order and returns a *simulated* fill — nothing is transmitted.
    Only ``dry_run=false`` (still the paper endpoint) actually calls ``submit_order``.

A real far-OTM limit may rest unfilled, so ``AlpacaPaperBroker`` also exposes
``order_status``/``cancel_order`` for the monitor's reconciliation pass.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Protocol

log = logging.getLogger("broker")


def make_client_order_id(action: str, contract_symbol: str, trade_date: str) -> str:
    """Deterministic, idempotent order id keyed on the STABLE trade identity (T2.5).

    ``action`` is "open" | "close"; ``trade_date`` is the ET date string. Keyed on
    ``{action}-{contract}-{date}`` — NOT the run_id — so a timer re-fire after a crash submits
    the *same* id, Alpaca rejects the duplicate (idempotent), and reconciliation can recompute
    the expected id to detect a DB-less orphan. Per-(contract, date) is safe given the per-name
    dedup + caps. Sanitized to Alpaca's id charset.
    """
    raw = f"{action}-{contract_symbol}-{trade_date}"
    return re.sub(r"[^A-Za-z0-9._-]", "", raw)[:128]


@dataclass(frozen=True)
class Fill:
    filled: bool
    price: float            # per share
    qty: int
    note: str
    order_id: str | None = None
    pending: bool = False   # real order accepted but not yet confirmed filled


class Broker(Protocol):
    def account_equity(self) -> float: ...

    def submit_paper(
        self, *, contract_symbol: str, qty: int, side: str, limit_price: float,
        client_order_id: str | None = None,
    ) -> Fill: ...


class PaperBroker:
    """Simulated paper broker — fills at the supplied limit (mid). No I/O."""

    def __init__(self, account_equity: float) -> None:
        self._equity = float(account_equity)

    def account_equity(self) -> float:
        return self._equity

    def submit_paper(
        self, *, contract_symbol: str, qty: int, side: str, limit_price: float,
        client_order_id: str | None = None,
    ) -> Fill:
        if qty < 1 or limit_price <= 0:
            return Fill(False, 0.0, 0, f"rejected: qty={qty} px={limit_price}")
        return Fill(
            True, float(limit_price), int(qty),
            f"paper-sim {side} {qty}x {contract_symbol} @ {limit_price:.2f}",
        )


class AlpacaPaperBroker:
    """Real Alpaca paper-order broker (own TradingClient). DRY_RUN gates transmission."""

    def __init__(self, api_key: str, secret_key: str, *, dry_run: bool = True, equity: float | None = None) -> None:
        from alpaca.trading.client import TradingClient

        self._trading = TradingClient(api_key, secret_key, paper=True)
        self._dry_run = bool(dry_run)
        self._equity_override = equity

    def account_equity(self) -> float:
        if self._equity_override is not None:
            return float(self._equity_override)
        return float(self._trading.get_account().equity)

    def submit_paper(
        self, *, contract_symbol: str, qty: int, side: str, limit_price: float,
        client_order_id: str | None = None,
    ) -> Fill:
        if qty < 1 or limit_price <= 0:
            return Fill(False, 0.0, 0, f"rejected: qty={qty} px={limit_price}")
        limit = round(float(limit_price), 2)
        is_buy = str(side).lower() == "buy"
        intent_label = "buy_to_open" if is_buy else "sell_to_close"

        if self._dry_run:
            note = f"DRY_RUN (not sent): {intent_label} {qty}x {contract_symbol} LIMIT {limit:.2f} [paper]"
            log.info(note)
            return Fill(True, limit, int(qty), note)  # simulated fill, nothing transmitted

        # Real submission to the PAPER endpoint (BUY_TO_OPEN entries, SELL_TO_CLOSE exits).
        try:
            from alpaca.trading.enums import OrderSide, OrderType, PositionIntent, TimeInForce
            from alpaca.trading.requests import LimitOrderRequest

            req = LimitOrderRequest(
                symbol=contract_symbol,
                qty=int(qty),
                side=OrderSide.BUY if is_buy else OrderSide.SELL,
                type=OrderType.LIMIT,
                time_in_force=TimeInForce.DAY,
                limit_price=limit,
                position_intent=PositionIntent.BUY_TO_OPEN if is_buy else PositionIntent.SELL_TO_CLOSE,
                client_order_id=client_order_id,
            )
            order = self._trading.submit_order(req)
        except Exception as e:  # noqa: BLE001 — fail-closed: never crash the cycle
            note = f"alpaca {intent_label} FAILED for {contract_symbol}: {e}"
            log.error(note)
            return Fill(False, 0.0, 0, note)

        oid = str(getattr(order, "id", "") or "")
        filled_price = getattr(order, "filled_avg_price", None)
        if filled_price:  # immediate fill
            return Fill(True, float(filled_price), int(qty),
                        f"alpaca paper FILLED {intent_label} {qty}x {contract_symbol} @ {float(filled_price):.2f}",
                        order_id=oid)
        # Accepted but resting → pending, reconciled by the monitor.
        return Fill(True, limit, int(qty),
                    f"alpaca paper SUBMITTED {intent_label} {qty}x {contract_symbol} LIMIT {limit:.2f} (resting)",
                    order_id=oid, pending=True)

    # ── reconciliation surface (used by monitor.reconcile_pending) ─────────────
    def order_status(self, order_id: str) -> dict | None:
        try:
            o = self._trading.get_order_by_id(order_id)
        except Exception as e:  # noqa: BLE001
            log.warning("order_status(%s) failed: %s", order_id, e)
            return None
        return {
            "state": str(getattr(o, "status", "")),
            "filled_avg_price": getattr(o, "filled_avg_price", None),
            "filled_qty": getattr(o, "filled_qty", None),
        }

    def cancel_order(self, order_id: str) -> None:
        try:
            self._trading.cancel_order_by_id(order_id)
        except Exception as e:  # noqa: BLE001
            log.warning("cancel_order(%s) failed: %s", order_id, e)
