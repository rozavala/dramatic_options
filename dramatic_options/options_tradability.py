"""Option-tradability ceiling (FSSD plan §8b, operator review #1) — pure logic.

The audit's "optionable" flag (a chain *exists*) is blind to the dimension most likely to
hollow the FSSD corner: **spread and borrow-implied option cost**. A chain you can't trade at
an economic price is not tradable. So for the surviving high-friction corner names we pull the
*current* option chain and summarize the **near-the-money put bid/ask spread** — an upper-bound
("ceiling") on historical tradability:

  - It is a *current* snapshot → survivorship-biased (delisted event names have no chain today)
    and only an UPPER bound on what was tradable at the historical event. Labeled as such; it is
    never treated as point-in-time. The stop-or-go logic is one-directional: if today's
    high-friction names lack tradable puts *now*, they certainly didn't at the event → stop.

This module is pure (OSI-symbol parse + spread summary over quote tuples) so it is offline-
testable; the network pull lives in the audit script via ``AlpacaClient.get_option_chain``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

# OSI/OCC symbol: ROOT(≤6, padded) + YYMMDD + C/P + strike(8 digits, ×1000).
# e.g. "LCID260618P00001000" → LCID 2026-06-18 PUT strike 1.000


def parse_osi(symbol: str) -> dict[str, Any] | None:
    """Parse an OSI option symbol → {root, expiry(date), kind('C'/'P'), strike(float)} or None."""
    s = symbol.strip().upper()
    if len(s) < 9:
        return None
    tail = s[-15:]
    if len(tail) != 15:
        return None
    root = s[: -15]
    ymd, kind, strike = tail[:6], tail[6], tail[7:]
    if kind not in ("C", "P") or not (ymd.isdigit() and strike.isdigit()):
        return None
    try:
        expiry = date(2000 + int(ymd[:2]), int(ymd[2:4]), int(ymd[4:6]))
    except ValueError:
        return None
    return {"root": root, "expiry": expiry, "kind": kind, "strike": int(strike) / 1000.0}


def spread_pct(bid: float | None, ask: float | None) -> float | None:
    """Relative bid/ask spread = (ask−bid)/mid. None if not a usable two-sided quote."""
    if bid is None or ask is None or ask <= 0 or bid <= 0 or ask < bid:
        return None
    mid = 0.5 * (bid + ask)
    if mid <= 0:
        return None
    return (ask - bid) / mid


@dataclass
class PutTradability:
    n_contracts: int            # total contracts in the chain
    n_puts_quoted: int          # near-money puts with a usable two-sided quote
    median_put_spread_pct: float | None
    tradable: bool              # any near-money put with a two-sided quote at all
    note: str = ""


def summarize_put_tradability(
    quotes: list[dict[str, Any]],
    *,
    underlying_price: float | None,
    moneyness_band: float = 0.30,
    max_expiry_days: int = 120,
    as_of: date | None = None,
) -> PutTradability:
    """Median near-the-money put spread % from chain quotes.

    ``quotes``: ``[{symbol, bid, ask}, ...]``. Keeps PUTs whose strike is within
    ``moneyness_band`` of ``underlying_price`` and expiry within ``max_expiry_days`` (the FSSD
    trade is short-dated, h=10td). Returns a ceiling summary — see module docstring.
    """
    as_of = as_of or datetime.utcnow().date()
    spreads: list[float] = []
    n_puts_quoted = 0
    for q in quotes:
        info = parse_osi(q.get("symbol", ""))
        if info is None or info["kind"] != "P":
            continue
        dte = (info["expiry"] - as_of).days
        if dte < 0 or dte > max_expiry_days:
            continue
        if underlying_price and underlying_price > 0:
            if abs(info["strike"] - underlying_price) / underlying_price > moneyness_band:
                continue
        sp = spread_pct(q.get("bid"), q.get("ask"))
        if sp is None:
            continue
        spreads.append(sp)
        n_puts_quoted += 1

    if not spreads:
        return PutTradability(
            n_contracts=len(quotes), n_puts_quoted=0, median_put_spread_pct=None,
            tradable=False, note="no near-money put with a two-sided quote (current snapshot)",
        )
    spreads.sort()
    med = spreads[len(spreads) // 2] if len(spreads) % 2 else \
        0.5 * (spreads[len(spreads) // 2 - 1] + spreads[len(spreads) // 2])
    return PutTradability(
        n_contracts=len(quotes), n_puts_quoted=n_puts_quoted,
        median_put_spread_pct=med, tradable=True,
    )
