"""Market-data adapter (plan §B3) — bars, momentum, ADV, beta/RS, and the forward label.

All feature reads are **as-of**: they go through the point-in-time cache and only ever see
bars dated ``<= as_of``. The single exception is :meth:`MarketData.forward_return`, the
**label-only** accessor, which is allowed to read future bars (`t → t+h`) because the label
is never fed back as a feature.

Daily bars are fetched split+dividend-adjusted (``Adjustment.ALL``) so labels/momentum
aren't distorted by corporate actions on these high-beta names. Backtest eligibility uses
price + ADV from here only (no historical option liquidity exists — plan §B1).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

from data.cache import PointInTimeCache

SOURCE = "bars"


def _bar_val(bar: Any, key: str) -> Any:
    """Read a field from an alpaca Bar object or a plain dict (explicit — never via the
    ``x or y`` idiom, which mis-fires when a valid value like volume is 0.0)."""
    return bar[key] if isinstance(bar, dict) else getattr(bar, key)


def _bar_records(barset: Any, symbol: str) -> list[dict[str, Any]]:
    """Normalize an alpaca BarSet (or mapping) into cache records for one symbol."""
    data = getattr(barset, "data", barset)
    bars = data.get(symbol, []) if hasattr(data, "get") else data
    out: list[dict[str, Any]] = []
    for b in bars:
        ts = _bar_val(b, "timestamp")
        ts = ts.isoformat() if isinstance(ts, datetime) else str(ts)
        out.append(
            {
                "ts": ts,
                "open": float(_bar_val(b, "open")),
                "high": float(_bar_val(b, "high")),
                "low": float(_bar_val(b, "low")),
                "close": float(_bar_val(b, "close")),
                "volume": float(_bar_val(b, "volume")),
            }
        )
    return out


class MarketData:
    """As-of bar features for the universe, backed by the point-in-time cache."""

    def __init__(
        self,
        cache: PointInTimeCache,
        *,
        client: Any | None = None,
        fetch_start: datetime,
        fetch_end: datetime,
        feed: Any | None = None,
    ) -> None:
        self.cache = cache
        self.client = client
        self.fetch_start = fetch_start
        self.fetch_end = fetch_end
        self.feed = feed  # alpaca DataFeed for equity bars (discovery markers + context); None → client default (IEX)

    # ── fetch / read ──────────────────────────────────────────────────────
    def _ensure(self, symbol: str) -> None:
        if self.cache.covers(SOURCE, symbol, self.fetch_start, self.fetch_end):
            return
        if self.client is None:
            return  # offline: a subsequent read() raises CacheMiss if insufficient
        kw = {} if self.feed is None else {"feed": self.feed}
        barset = self.client.get_stock_bars(symbol, start=self.fetch_start, end=self.fetch_end, **kw)
        self.cache.write(
            SOURCE, symbol, _bar_records(barset, symbol),
            coverage_from=self.fetch_start, coverage_through=self.fetch_end,
        )

    def closes_asof(self, symbol: str, as_of: datetime) -> list[tuple[datetime, float]]:
        """(date, close) pairs with date <= as_of, ascending."""
        self._ensure(symbol)
        recs = self.cache.read(SOURCE, symbol, as_of)
        return [(datetime.fromisoformat(r["ts"]), r["close"]) for r in recs]

    # ── point-in-time features (never see > as_of) ─────────────────────────
    def latest_price(self, symbol: str, as_of: datetime) -> float | None:
        closes = self.closes_asof(symbol, as_of)
        return closes[-1][1] if closes else None

    def adv_usd(self, symbol: str, as_of: datetime, *, window: int = 20) -> float | None:
        """Average daily dollar volume over the trailing ``window`` sessions ≤ as_of."""
        self._ensure(symbol)
        recs = self.cache.read(SOURCE, symbol, as_of)
        if len(recs) < window:
            return None
        tail = recs[-window:]
        return sum(r["close"] * r["volume"] for r in tail) / len(tail)

    def momentum(
        self, symbol: str, as_of: datetime, *, lookback: int = 252, skip: int = 21
    ) -> float | None:
        """12-1 momentum: return from ``lookback`` sessions ago to ``skip`` sessions ago.

        Skipping the most recent month is standard to avoid the short-term reversal effect.
        """
        closes = [c for _, c in self.closes_asof(symbol, as_of)]
        if len(closes) < lookback + 1:
            return None
        old = closes[-(lookback + 1)]
        recent = closes[-(skip + 1)]
        if old <= 0:
            return None
        return recent / old - 1.0

    def _returns(self, symbol: str, as_of: datetime, *, window: int) -> list[float]:
        closes = [c for _, c in self.closes_asof(symbol, as_of)][-(window + 1):]
        return [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes)) if closes[i - 1] > 0]

    def beta(
        self, symbol: str, benchmark: str, as_of: datetime, *, window: int = 126
    ) -> float | None:
        """OLS beta of the symbol's daily returns to a benchmark's, over trailing ``window``."""
        sr = self._returns(symbol, as_of, window=window)
        br = self._returns(benchmark, as_of, window=window)
        n = min(len(sr), len(br))
        if n < window // 2:
            return None
        sr, br = sr[-n:], br[-n:]
        mb = sum(br) / n
        ms = sum(sr) / n
        cov = sum((br[i] - mb) * (sr[i] - ms) for i in range(n)) / n
        var = sum((br[i] - mb) ** 2 for i in range(n)) / n
        return cov / var if var > 0 else None

    # ── label (forward-looking BY DESIGN — never a feature) ────────────────
    def forward_return(
        self, symbol: str, as_of: datetime, horizon_days: int
    ) -> float | None:
        """Underlying return from the close ≤ as_of to the close ≈ ``horizon_days`` later.

        **Label only.** Uses :meth:`PointInTimeCache.read_between`, which intentionally reads
        future bars and does not touch the lookahead tripwire. Returns None if either anchor
        is missing (e.g. near the end of available data) so the observation is dropped.
        """
        self._ensure(symbol)
        entry = self.cache.read(SOURCE, symbol, as_of)
        if not entry:
            return None
        entry_close = entry[-1]["close"]
        # Forward window: calendar window generously sized to land ~horizon trading days out.
        end = as_of + timedelta(days=math.ceil(horizon_days * 1.6) + 4)
        fwd = self.cache.read_between(SOURCE, symbol, as_of, end)
        if len(fwd) < horizon_days:
            return None
        exit_close = fwd[horizon_days - 1]["close"]
        if entry_close <= 0:
            return None
        return exit_close / entry_close - 1.0


def default_fetch_window(as_of: datetime, *, warmup_days: int = 420) -> tuple[datetime, datetime]:
    """Convenience window for the live watchlist: [as_of - warmup, as_of]."""
    as_of = as_of if as_of.tzinfo else as_of.replace(tzinfo=UTC)
    return as_of - timedelta(days=warmup_days), as_of
