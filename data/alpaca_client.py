"""Alpaca client wrapper — Phase 0: READ-ONLY.

Exposes only read primitives: account, clock, positions, and stock bars. There is
deliberately NO order-submission path here in Phase 0 ("no trading logic"). The
option chain arrives in Phase 1 and the MLEG submit helper in Phase 2.

Signatures verified against alpaca-py==0.43.4:
  - TradingClient(api_key, secret_key, paper=True) → get_account/get_clock/get_all_positions
  - StockHistoricalDataClient(api_key, secret_key) → get_stock_bars(StockBarsRequest)
"""

from __future__ import annotations

from typing import Any

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient


class AlpacaClient:
    """Thin read-only wrapper around alpaca-py's trading + market-data clients."""

    def __init__(self, api_key: str, secret_key: str, *, paper: bool = True) -> None:
        self.paper = paper
        self._trading = TradingClient(api_key, secret_key, paper=paper)
        self._data = StockHistoricalDataClient(api_key, secret_key)

    # ── Account / status (read-only) ──────────────────────────────────────
    def get_account(self) -> Any:
        return self._trading.get_account()

    def get_equity(self) -> float:
        """Account equity as a float."""
        return float(self.get_account().equity)

    def get_clock(self) -> Any:
        return self._trading.get_clock()

    def is_market_open(self) -> bool:
        return bool(self.get_clock().is_open)

    def get_positions(self) -> list[Any]:
        return self._trading.get_all_positions()

    # ── Market data (read-only) ───────────────────────────────────────────
    def get_stock_bars(self, symbols, start, end=None, timeframe: TimeFrame | None = None):
        """Historical stock bars for one or more symbols."""
        req = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=timeframe or TimeFrame.Day,
            start=start,
            end=end,
        )
        return self._data.get_stock_bars(req)
