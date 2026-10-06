"""News adapter (plan §B4) — the narrative source.

Alpaca/Benzinga headlines, timestamped by ``created_at``, read **as-of** through the
point-in-time cache. Also emits a per-name **coverage-density audit** (articles per year) so
thin early-SPAC coverage is *visible* rather than silently biasing the cross-sectional
narrative z-score toward better-covered names (plan §B4, §A0).
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from data.cache import PointInTimeCache

SOURCE = "news"


def _news_items(newsset: Any) -> list[Any]:
    """Pull the list of News objects out of a NewsSet / raw dict, defensively."""
    if isinstance(newsset, dict):
        return newsset.get("news", [])
    data = getattr(newsset, "data", None)
    if isinstance(data, dict):
        return data.get("news", [])
    if isinstance(data, list):
        return data
    return getattr(newsset, "news", []) or []


def _field(item: Any, key: str) -> Any:
    return item.get(key) if isinstance(item, dict) else getattr(item, key, None)


def _news_records(newsset: Any, symbol: str) -> list[dict[str, Any]]:
    """Normalize News objects into cache records (one per article)."""
    out: list[dict[str, Any]] = []
    for n in _news_items(newsset):
        created = _field(n, "created_at")
        if created is None:
            continue
        ts = created.isoformat() if isinstance(created, datetime) else str(created)
        out.append(
            {
                "ts": ts,
                "headline": _field(n, "headline") or "",
                "source": _field(n, "source") or "",
                "symbols": list(_field(n, "symbols") or []),
                "id": _field(n, "id"),
            }
        )
    return out


class NewsData:
    """As-of news for the universe, backed by the point-in-time cache."""

    def __init__(
        self,
        cache: PointInTimeCache,
        *,
        client: Any | None = None,
        fetch_start: datetime,
        fetch_end: datetime,
        fetch_limit: int = 50000,
    ) -> None:
        self.cache = cache
        self.client = client
        self.fetch_start = fetch_start
        self.fetch_end = fetch_end
        self.fetch_limit = fetch_limit

    def _ensure(self, symbol: str) -> None:
        if self.cache.covers(SOURCE, symbol, self.fetch_start, self.fetch_end):
            return
        if self.client is None:
            return
        newsset = self.client.get_news(
            [symbol], start=self.fetch_start, end=self.fetch_end, limit=self.fetch_limit
        )
        self.cache.write(
            SOURCE, symbol, _news_records(newsset, symbol),
            coverage_from=self.fetch_start, coverage_through=self.fetch_end,
        )

    def headlines_asof(self, symbol: str, as_of: datetime) -> list[dict[str, Any]]:
        """All articles with ``created_at <= as_of``, ascending.

        In the live/forward loop the council's ``as_of`` is a strictly later ``clock.now()`` than
        this provider's ``fetch_end`` (built a few calls earlier in the cycle), so a bare
        ``cache.read(as_of)`` would ``CacheMiss`` on ``as_of > coverage_through`` and the caller
        would SILENTLY lose every headline (the pack drops its news grounding). Clamp forward-drift
        to ``fetch_end`` — we fetched only through ``fetch_end``, so that IS all the news there is.
        Offline/backtest keeps the strict ``as_of`` so the "widen your fetch" tripwire still fires
        (the cache.py contract — never silently truncate a point-in-time replay)."""
        self._ensure(symbol)
        read_at = as_of if self.cache.offline else min(to_utc(as_of), to_utc(self.fetch_end))
        return self.cache.read(SOURCE, symbol, read_at)

    # ── coverage-density audit (plan §B4 / §A0) ────────────────────────────
    def coverage_by_year(self, symbol: str) -> dict[int, int]:
        """Article counts per calendar year across the full cached payload."""
        recs = self.cache.read_between(SOURCE, symbol, None, self.fetch_end)
        counts: Counter[int] = Counter()
        for r in recs:
            counts[datetime.fromisoformat(r["ts"]).year] += 1
        return dict(sorted(counts.items()))

    def coverage_count(self, symbol: str, as_of: datetime) -> int:
        return len(self.headlines_asof(symbol, as_of))


def to_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
