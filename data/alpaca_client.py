"""Alpaca client wrapper — READ-ONLY (Phase 0 + Phase 1 reads).

Exposes only read primitives: account, clock, positions, stock bars, news, and the
option chain. There is deliberately NO order-submission path here ("no trading logic"
until Phase 2); the Phase-0 guardrail test asserts no submit surface exists.

Signatures verified against alpaca-py==0.43.4:
  - TradingClient(api_key, secret_key, paper=True) → get_account/get_clock/get_all_positions
  - StockHistoricalDataClient(api_key, secret_key) → get_stock_bars(StockBarsRequest)
  - NewsClient(api_key, secret_key) → get_news(NewsRequest)
  - OptionHistoricalDataClient(api_key, secret_key) → get_option_chain(OptionChainRequest)
"""

from __future__ import annotations

from typing import Any

from alpaca.data.enums import Adjustment, DataFeed, OptionsFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.news import NewsClient
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.requests import NewsRequest, OptionChainRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient


class AlpacaClient:
    """Thin read-only wrapper around alpaca-py's trading + market-data clients."""

    def __init__(self, api_key: str, secret_key: str, *, paper: bool = True) -> None:
        self.paper = paper
        self._trading = TradingClient(api_key, secret_key, paper=paper)
        self._data = StockHistoricalDataClient(api_key, secret_key)
        self._news = NewsClient(api_key, secret_key)
        self._options = OptionHistoricalDataClient(api_key, secret_key)

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
    def get_stock_bars(
        self,
        symbols,
        start,
        end=None,
        timeframe: TimeFrame | None = None,
        adjustment: Adjustment = Adjustment.ALL,
        feed: DataFeed = DataFeed.IEX,
    ):
        """Historical stock bars for one or more symbols.

        ``adjustment`` defaults to ALL (split + dividend) so forward-return labels and
        momentum aren't distorted by corporate actions on these names. ``feed`` defaults to
        IEX: the free/paper data plan cannot query recent SIP data ("subscription does not
        permit querying recent SIP data"), and IEX daily history is sufficient for the
        divergence signal. Switch to SIP/OPRA only on a paid feed before live.
        """
        req = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=timeframe or TimeFrame.Day,
            start=start,
            end=end,
            adjustment=adjustment,
            feed=feed,
        )
        return self._data.get_stock_bars(req)

    def get_news(self, symbols, start, end=None, *, limit: int = 50):
        """Historical news articles for one or more symbols (read-only)."""
        req = NewsRequest(
            symbols=",".join(symbols) if isinstance(symbols, (list, tuple)) else symbols,
            start=start,
            end=end,
            limit=limit,
            include_content=False,
            exclude_contentless=False,
        )
        return self._news.get_news(req)

    def get_option_chain(self, underlying: str, *, feed: OptionsFeed = OptionsFeed.INDICATIVE):
        """Option chain snapshot for an underlying (live watchlist liquidity gate only).

        Uses the INDICATIVE (free) feed by default. There is no historical option-chain
        path here on purpose: point-in-time option liquidity back to 2022 does not exist, so
        the backtest must never gate on it (plan §B1).
        """
        req = OptionChainRequest(underlying_symbol=underlying, feed=feed)
        return self._options.get_option_chain(req)
