"""Execution seam — brokers (T1.5 paper + the T4 real-money path).

Brokers behind one ``Broker`` protocol:
  - ``PaperBroker`` — simulated fill at the supplied mid, no I/O (offline demo + tests).
  - ``_AlpacaBrokerBase`` — the shared real-Alpaca submit/reconcile logic (own ``TradingClient``;
    the read-only ``AlpacaClient`` stays submit-free, a Phase-0 guardrail). **Sending is gated by
    DRY_RUN (guardrail §1):** ``dry_run`` true (default) logs the intended order + returns a
    *simulated* fill (nothing transmitted); only ``dry_run=false`` calls ``submit_order``.
  - ``AlpacaPaperBroker`` — the base fixed to the **paper** endpoint (``paper=True``).
  - ``AlpacaLiveBroker`` — the base fixed to the **real-money** endpoint (``paper=False``),
    constructed ONLY under the triple-gate (``config_loader.live_allowed``); adds a fail-closed
    per-order notional ceiling. This is the last T4 build — see ``PREREG_REAL_MONEY_BROKER.md``.

A real far-OTM limit may rest unfilled, so the base also exposes ``order_status``/``cancel_order``
for the monitor's reconciliation pass.
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


class _AlpacaBrokerBase:
    """Shared Alpaca order broker (own ``TradingClient``; the read-only ``AlpacaClient`` stays
    submit-free, a Phase-0 guardrail). **DRY_RUN gates transmission (guardrail §1):** ``dry_run``
    true (the default) logs the exact intended order + returns a SIMULATED fill — nothing is sent;
    only ``dry_run=false`` calls ``submit_order``. The ``_paper`` class attribute fixes the endpoint
    per subclass, so a paper broker can NEVER transmit real money (the real-money type is a distinct,
    auditable class). ``submit_paper`` is the ``Broker`` protocol method name — legacy, kept stable
    to avoid churning the protocol + monitor + paper_loop callers; the venue is in the class + logs.

    A real far-OTM limit may rest unfilled, so ``order_status``/``cancel_order`` back the monitor's
    reconciliation pass.
    """

    _paper: bool = True         # subclass fixes the endpoint (paper vs real-money)
    _venue: str = "paper"       # log tag ("paper" | "LIVE — REAL MONEY")

    def __init__(self, api_key: str, secret_key: str, *, dry_run: bool = True, equity: float | None = None) -> None:
        from alpaca.trading.client import TradingClient

        self._trading = TradingClient(api_key, secret_key, paper=self._paper)
        self._dry_run = bool(dry_run)
        self._equity_override = equity

    def account_equity(self) -> float:
        if self._equity_override is not None:
            return float(self._equity_override)
        return float(self._trading.get_account().equity)

    def _reject_precheck(self, *, contract_symbol: str, qty: int, limit: float) -> Fill | None:
        """Subclass hook for a pre-transmit rejection (a real-money safeguard). Returns a rejecting
        ``Fill`` to block the order (nothing transmitted, even under DRY_RUN), or ``None`` to proceed."""
        return None

    def submit_paper(
        self, *, contract_symbol: str, qty: int, side: str, limit_price: float,
        client_order_id: str | None = None,
    ) -> Fill:
        if qty < 1 or limit_price <= 0:
            return Fill(False, 0.0, 0, f"rejected: qty={qty} px={limit_price}")
        limit = round(float(limit_price), 2)
        is_buy = str(side).lower() == "buy"
        intent_label = "buy_to_open" if is_buy else "sell_to_close"

        # Real-money safeguard (§3) — checked BEFORE the DRY_RUN branch so a ceiling breach / missing
        # config rejects in every mode (surfaces a sizing bug even in simulation).
        rejected = self._reject_precheck(contract_symbol=contract_symbol, qty=int(qty), limit=limit)
        if rejected is not None:
            log.error(rejected.note)
            return rejected

        if self._dry_run:
            note = f"DRY_RUN (not sent): {intent_label} {qty}x {contract_symbol} LIMIT {limit:.2f} [{self._venue}]"
            log.info(note)
            return Fill(True, limit, int(qty), note)  # simulated fill, nothing transmitted

        # Real submission (BUY_TO_OPEN entries, SELL_TO_CLOSE exits) to the _paper/_live endpoint.
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
                        f"alpaca {self._venue} FILLED {intent_label} {qty}x {contract_symbol} @ {float(filled_price):.2f}",
                        order_id=oid)
        # Accepted but resting → pending, reconciled by the monitor.
        return Fill(True, limit, int(qty),
                    f"alpaca {self._venue} SUBMITTED {intent_label} {qty}x {contract_symbol} LIMIT {limit:.2f} (resting)",
                    order_id=oid, pending=True)

    # ── reconciliation surface (used by monitor.reconcile_pending) ─────────────
    def order_status(self, order_id: str) -> dict | None:
        try:
            o = self._trading.get_order_by_id(order_id)
        except Exception as e:  # noqa: BLE001
            log.warning("order_status(%s) failed: %s", order_id, e)
            return None
        # alpaca-py returns an ``OrderStatus`` enum whose ``str()`` is "OrderStatus.FILLED",
        # NOT "filled". The monitor's reconcilers compare against the lowercase VALUE
        # ("filled" / "canceled" / …), so emit the enum value (a plain string passes through).
        # Without this, reconcile_pending / _reconcile_closing never match a real order.
        status = getattr(o, "status", "")
        return {
            "state": getattr(status, "value", str(status)),
            "filled_avg_price": getattr(o, "filled_avg_price", None),
            "filled_qty": getattr(o, "filled_qty", None),
        }

    def cancel_order(self, order_id: str) -> None:
        try:
            self._trading.cancel_order_by_id(order_id)
        except Exception as e:  # noqa: BLE001
            log.warning("cancel_order(%s) failed: %s", order_id, e)


class AlpacaPaperBroker(_AlpacaBrokerBase):
    """Real Alpaca **paper**-order broker. DRY_RUN gates transmission. Public surface byte-unchanged
    from T1.5 (paper endpoint; ``_venue='paper'`` renders the historical log strings verbatim)."""

    _paper = True
    _venue = "paper"


class AlpacaLiveBroker(_AlpacaBrokerBase):
    """Real Alpaca **REAL-MONEY** broker (``paper=False``). Constructed ONLY under the triple-gate
    (``config_loader.live_allowed``; PREREG_REAL_MONEY_BROKER §2). DRY_RUN still simulates.

    **The SOLE broker-level real-money safeguard (§3): a hard per-order NOTIONAL CEILING.** Any order
    whose premium (``qty × limit × 100``) exceeds ``max_order_notional`` is rejected fail-closed; an
    ABSENT ceiling (``None``) rejects EVERYTHING (fail-closed — the operator must set
    ``safety.live_max_order_notional`` before arming real money). Bounds a sizing/pricing bug
    independently of the upstream book/cluster caps."""

    _paper = False
    _venue = "LIVE — REAL MONEY"

    def __init__(self, api_key: str, secret_key: str, *, dry_run: bool = True,
                 equity: float | None = None, max_order_notional: float | None = None) -> None:
        super().__init__(api_key, secret_key, dry_run=dry_run, equity=equity)
        self._max_order_notional = max_order_notional

    def _reject_precheck(self, *, contract_symbol: str, qty: int, limit: float) -> Fill | None:
        notional = float(qty) * float(limit) * 100.0
        if self._max_order_notional is None:
            return Fill(False, 0.0, 0,
                        f"LIVE rejected {contract_symbol}: no safety.live_max_order_notional configured "
                        f"(fail-closed — set the ceiling before arming real money)")
        if notional > float(self._max_order_notional):
            return Fill(False, 0.0, 0,
                        f"LIVE rejected {contract_symbol}: order notional ${notional:,.0f} exceeds the "
                        f"${float(self._max_order_notional):,.0f} per-order ceiling (fail-closed)")
        return None
