"""The no-arbitrage mark bound every book's mark goes through (#533).

On 2026-11-18 a broken opening quote (bid 0, ask ≈20.2) marked the real book's $6-strike RDW put at 10.10. A put
cannot be worth more than its strike, yet ``option_mid`` accepted it (bid ≥ 0, ask ≥ bid), the mark crossed the 10×
profit-take, and the journal booked a phantom +$9,150 close. This module is the one place a position's mark is
taken from a quote provider and checked against the most the option can be worth:

* a **put** (single leg) — its strike, read from the OSI symbol (``parse_osi``); needs nothing else;
* a **vertical** (the debit spreads in ``verticals``) — its strike width; needs nothing else;
* a **call** (single leg) — the underlying price, from the monitor's own ``underlying_price_of``. It is fetched only
  for a call that has a quote, once per underlying per mark pass (memoized), and never for an adjusted OCC class
  (root ≠ ticker: a non-standard deliverable, which the ticker's price doesn't bound). When the price is not
  available (no ``underlying_price_of``, a failed or non-positive lookup) the call is marked exactly as before the
  bound existed — no bound is invented. The first failed lookup in a pass stops further lookups for that pass, so
  a data outage costs one timeout per pass, not one per name (the 2026-09-11 mark-budget lesson).

A mark above its bound is **rejected**: ``BoundedMarker.mark`` returns None, so the caller counts the position
unmarked, leaves its stored mark untouched and fires no exit on it this tick; a WARNING names the bid, ask and bound.
Every book (the real monitor, the shadow null book, the 3A/3B no-gate books) marks through ``BoundedMarker``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import verticals
from convexity_gate import occ_root
from options_tradability import parse_osi

log = logging.getLogger(__name__)


class BoundedMarker:
    """One mark pass's marker for ``book`` (a label for the log). Build one per pass; it memoizes underlying prices."""

    def __init__(self, quote_provider, underlying_price_of: Callable[[str], Any] | None = None, *,
                 book: str) -> None:
        self._qp = quote_provider
        self._price_of = underlying_price_of
        self._book = book
        self._spots: dict[str, float | None] = {}
        self._spot_down = False
        self.rejected = 0

    def mark(self, pos) -> float | None:
        """The position's per-share mark, or None (no quote, or a quote above its no-arbitrage bound).

        Quote-provider exceptions propagate unchanged (each monitor already handles them per position)."""
        if verticals.is_vertical(pos):
            mid = verticals.position_mid(pos, self._qp)
            if mid is None:
                return None
            bound = abs(float(pos["short_strike"]) - float(pos["strike"]))
            return self._checked(pos, mid, bound, "spread width")
        contract = pos["contract_symbol"]
        mid = self._qp.option_mid(contract)
        if mid is None:
            return None
        info = parse_osi(contract)
        if info is None:
            return mid
        if info["kind"] == "P":
            return self._checked(pos, mid, float(info["strike"]), "put strike")
        if occ_root(contract) != str(pos["symbol"]).upper():
            return mid    # adjusted class: the ticker's price is not its deliverable's value
        spot = self._spot(str(pos["symbol"]))
        if spot is None:
            return mid    # no underlying price: no bound invented (the pre-#533 behaviour for this call)
        return self._checked(pos, mid, spot, "underlying price")

    def _checked(self, pos, mid: float, bound: float, what: str) -> float | None:
        if float(mid) <= bound:
            return mid
        self.rejected += 1
        bid = ask = None
        if not verticals.is_vertical(pos):
            try:
                bid = self._qp.option_bid(pos["contract_symbol"])
            except Exception:  # noqa: BLE001 — only feeds the log line
                bid = None
            ask = (2.0 * float(mid) - float(bid)) if bid is not None else None
        log.warning("%s mark REJECTED #%s %s: mid %.2f (bid %s, ask %s) is above its no-arbitrage bound %.2f (%s) — "
                    "left unmarked this tick, stored mark kept, no exit evaluated", self._book, pos["id"],
                    pos["contract_symbol"], float(mid), _fmt(bid), _fmt(ask), bound, what)
        return None

    def _spot(self, symbol: str) -> float | None:
        if symbol in self._spots:
            return self._spots[symbol]
        if self._price_of is None or self._spot_down:
            return None
        try:
            p = self._price_of(symbol)
        except Exception as e:  # noqa: BLE001 — the bound is a guard on marks, never a reason to stop marking
            self._spot_down = True
            log.warning("%s mark bound: underlying price lookup failed for %s (%s) — calls in the rest of this pass "
                        "are marked without the underlying-price bound", self._book, symbol, e)
            return None
        spot = float(p) if isinstance(p, int | float) and p > 0 else None
        self._spots[symbol] = spot
        return spot


def _fmt(x: float | None) -> str:
    return "none" if x is None else f"{float(x):.2f}"
