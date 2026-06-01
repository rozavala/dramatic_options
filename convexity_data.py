"""Chain/price providers for the paper loop (T1).

The loop depends on a small ``ChainProvider`` protocol (dependency injection → offline
tests). Two implementations:

  - ``AlpacaChainProvider`` — live: flattens the current Alpaca option chain into
    ``Contract`` rows (OSI parse + snapshot IV/greeks/quote) and pulls trailing closes for
    realized vol. Forward-only/current data — there is no historical-IV path (PREREG §4).
  - ``SyntheticChainProvider`` — deterministic fixtures so ``orchestrator.py --demo`` and a
    fresh operator (with their own themes) can exercise the full pipeline with no network.

``AlpacaChainProvider`` is exercised only against the live SDK (not in CI); the unit tests
use fakes/Synthetic.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Protocol

from convexity_gate import Contract
from options_tradability import parse_osi

SNAPSHOT_SOURCE = "option_chain_snapshot"


def snapshot_record(symbol: str, chain: list[Contract], underlying_price: float | None,
                    as_of_dt: datetime) -> dict:
    """Compact, append-friendly snapshot of a chain's vol surface for IV-baseline accrual.

    Keeps only what an IV-rank/percentile baseline needs (PREREG §4b): the underlying price
    and, per contract carrying an IV, ``{expiry, kind, strike, iv}`` — bulky quotes/greeks are
    dropped. Carries an ISO ``ts`` so the point-in-time cache can store/read it by date.
    """
    surface = [
        {"expiry": c.expiry.isoformat(), "kind": c.kind, "strike": c.strike, "iv": c.iv}
        for c in chain
        if c.iv is not None and c.iv > 0
    ]
    return {
        "ts": as_of_dt.isoformat(),
        "symbol": symbol,
        "underlying_price": underlying_price,
        "n_contracts": len(chain),
        "surface": surface,
    }


def persist_chain_snapshot(cache, symbol: str, chain: list[Contract],
                           underlying_price: float | None, as_of_dt: datetime) -> None:
    """Append today's chain snapshot to the point-in-time cache (read-append-write).

    The cache stores one superset payload per ``(source, key)`` and replaces it on write, so
    accrual reads the existing records, appends the new one, and rewrites with a widened
    coverage window. Over months this builds the IV history the gate can later graduate onto.
    """
    existing = cache.read_between(SNAPSHOT_SOURCE, symbol, None, as_of_dt)
    record = snapshot_record(symbol, chain, underlying_price, as_of_dt)
    # One snapshot per calendar day: a same-day re-run replaces the day's record rather than
    # stacking duplicates (the IV baseline is a daily series).
    today = as_of_dt.date().isoformat()
    kept = [r for r in existing if r["ts"][:10] != today]
    records = [*kept, record]
    coverage_from = datetime.fromisoformat(records[0]["ts"]) if records else as_of_dt
    cache.write(SNAPSHOT_SOURCE, symbol, records,
                coverage_from=coverage_from, coverage_through=as_of_dt)


class ChainProvider(Protocol):
    def underlying_price(self, symbol: str) -> float | None: ...

    def chain(self, symbol: str) -> list[Contract]: ...

    def closes(self, symbol: str, *, window: int) -> list[float]: ...


# ── live ────────────────────────────────────────────────────────────────────
class AlpacaChainProvider:
    """Live provider over the read-only ``AlpacaClient`` wrapper."""

    def __init__(self, client) -> None:  # noqa: ANN001 — AlpacaClient, duck-typed
        self._client = client

    def closes(self, symbol: str, *, window: int) -> list[float]:
        from datetime import datetime

        start = datetime.now().astimezone() - timedelta(days=int(window * 1.6) + 10)
        bars = self._client.get_stock_bars(symbol, start=start)
        data = getattr(bars, "data", {}) or {}
        rows = data.get(symbol, [])
        return [float(b.close) for b in rows if getattr(b, "close", None)]

    def underlying_price(self, symbol: str) -> float | None:
        c = self.closes(symbol, window=5)
        return c[-1] if c else None

    def chain(self, symbol: str) -> list[Contract]:
        raw = self._client.get_option_chain(symbol)
        items = raw.items() if hasattr(raw, "items") else []
        out: list[Contract] = []
        for osym, snap in items:
            info = parse_osi(osym)
            if info is None:
                continue
            lq = getattr(snap, "latest_quote", None)
            greeks = getattr(snap, "greeks", None)
            out.append(
                Contract(
                    symbol=osym,
                    expiry=info["expiry"],
                    kind=info["kind"],
                    strike=info["strike"],
                    bid=getattr(lq, "bid_price", None) if lq else None,
                    ask=getattr(lq, "ask_price", None) if lq else None,
                    iv=getattr(snap, "implied_volatility", None),
                    oi=getattr(snap, "open_interest", None),
                    delta=getattr(greeks, "delta", None) if greeks else None,
                )
            )
        return out


# ── option quote provider (for marking open positions; the L2 monitor) ─────────
class QuoteProvider(Protocol):
    def option_mid(self, contract_symbol: str) -> float | None: ...

    def option_bid(self, contract_symbol: str) -> float | None: ...


class AlpacaQuoteProvider:
    """Marks an option to its current mid via the read-only Alpaca chain snapshot.

    Reuses ``AlpacaClient.option_quote_tuples`` (current-snapshot quotes), keyed by the
    underlying parsed from the OSI symbol. Forward-only/current data — consistent with the
    no-historical-options wall (PREREG §4). Caches one chain pull per underlying per call-set.
    """

    def __init__(self, client) -> None:  # noqa: ANN001 — AlpacaClient, duck-typed
        self._client = client
        self._cache: dict[str, dict[str, tuple[float | None, float | None]]] = {}

    def _underlying_quotes(self, underlying: str) -> dict[str, tuple[float | None, float | None]]:
        if underlying not in self._cache:
            quotes = self._client.option_quote_tuples(underlying)
            self._cache[underlying] = {
                q["symbol"]: (q.get("bid"), q.get("ask")) for q in quotes
            }
        return self._cache[underlying]

    def option_mid(self, contract_symbol: str) -> float | None:
        info = parse_osi(contract_symbol)
        if info is None:
            return None
        quotes = self._underlying_quotes(info["root"])
        ba = quotes.get(contract_symbol)
        if ba is None:
            return None
        bid, ask = ba
        if bid is None or ask is None or ask <= 0 or bid < 0 or ask < bid:
            return None
        return 0.5 * (bid + ask)

    def option_bid(self, contract_symbol: str) -> float | None:
        """Current bid — the marketable price a SELL_TO_CLOSE crosses to (T2.5 honest exit)."""
        info = parse_osi(contract_symbol)
        if info is None:
            return None
        ba = self._underlying_quotes(info["root"]).get(contract_symbol)
        if ba is None:
            return None
        bid, _ask = ba
        return bid if (bid is not None and bid >= 0) else None


class StaticQuoteProvider:
    """Offline quote provider: a fixed ``{contract_symbol: mid}`` map (tests / replay).

    ``bids`` is an optional ``{contract_symbol: bid}`` map for the SELL_TO_CLOSE path; when
    omitted, ``option_bid`` falls back to the mid (fine for tests that don't exercise closes).
    """

    def __init__(self, marks: dict[str, float], bids: dict[str, float] | None = None) -> None:
        self._marks = marks
        self._bids = bids

    def option_mid(self, contract_symbol: str) -> float | None:
        return self._marks.get(contract_symbol)

    def option_bid(self, contract_symbol: str) -> float | None:
        if self._bids is not None:
            return self._bids.get(contract_symbol)
        return self._marks.get(contract_symbol)


# ── synthetic (offline demo / fallback) ───────────────────────────────────────
# Per-symbol profiles for the shipped EXAMPLE themes: (spot, realized_vol, atm_iv, wing_iv).
# FCX = cheap convexity (atm_iv≈rv, flat wing) → passes. NVDA = rich (atm_iv≫rv, fat wing) → veto.
_PROFILES: dict[str, tuple[float, float, float, float]] = {
    "FCX": (45.0, 0.38, 0.40, 0.43),
    "NVDA": (120.0, 0.45, 0.78, 0.95),
}
_DEFAULT_PROFILE = (50.0, 0.40, 0.42, 0.45)  # cheap-ish default for operator-supplied names


class SyntheticChainProvider:
    """Deterministic chain/price fixtures keyed off the symbol's profile."""

    def __init__(self, *, as_of: date, profiles: dict[str, tuple[float, float, float, float]] | None = None) -> None:
        self._as_of = as_of
        self._profiles = profiles or _PROFILES

    def _p(self, symbol: str) -> tuple[float, float, float, float]:
        return self._profiles.get(symbol.upper(), _DEFAULT_PROFILE)

    def underlying_price(self, symbol: str) -> float | None:
        return self._p(symbol)[0]

    def closes(self, symbol: str, *, window: int) -> list[float]:
        """Synthesize a price path whose realized vol ≈ the profile's rv (deterministic)."""
        spot, rv, _, _ = self._p(symbol)
        daily = rv / math.sqrt(252.0)
        n = window + 1
        # Deterministic zig-zag of per-day log-returns with std == daily (mean 0).
        px = [spot]
        for i in range(n - 1):
            step = daily if i % 2 == 0 else -daily
            px.append(px[-1] * math.exp(step))
        return px

    def chain(self, symbol: str) -> list[Contract]:
        spot, _, atm_iv, wing_iv = self._p(symbol)
        exp = self._as_of + timedelta(days=270)  # ~9 months, inside the 180–365 tenor window
        rows: list[Contract] = []
        # ATM-ish ladder + the ~25% OTM wings (both call and put) with the profile IVs.
        for mny in (-0.05, 0.0, 0.05):
            k = round(spot * (1 + mny), 1)
            for kind in ("C", "P"):
                rows.append(_synth_contract(symbol, exp, kind, k, atm_iv))
        for mny, kind in ((0.25, "C"), (-0.25, "P")):
            k = round(spot * (1 + mny), 1)
            rows.append(_synth_contract(symbol, exp, kind, k, wing_iv))
        return rows

    def option_mid(self, contract_symbol: str) -> float | None:
        """Mark a contract from its underlying's synthetic chain (doubles as QuoteProvider)."""
        info = parse_osi(contract_symbol)
        if info is None:
            return None
        for c in self.chain(info["root"]):
            if c.symbol == contract_symbol and c.bid is not None and c.ask is not None:
                return 0.5 * (c.bid + c.ask)
        return None

    def option_bid(self, contract_symbol: str) -> float | None:
        info = parse_osi(contract_symbol)
        if info is None:
            return None
        for c in self.chain(info["root"]):
            if c.symbol == contract_symbol and c.bid is not None:
                return c.bid
        return None


def _synth_contract(symbol: str, exp: date, kind: str, strike: float, iv: float) -> Contract:
    # Crude but two-sided: premium scales with iv and (rough) moneyness; tight spread, ample OI.
    base = max(0.20, iv * 4.0)
    mid = round(base, 2)
    osi = f"{symbol.upper()}{exp:%y%m%d}{kind}{int(round(strike * 1000)):08d}"
    return Contract(
        symbol=osi, expiry=exp, kind=kind, strike=strike,
        bid=round(mid * 0.97, 2), ask=round(mid * 1.03, 2),
        iv=iv, oi=500, delta=None,
    )
