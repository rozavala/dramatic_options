"""Analyst-coverage meter — the sell-side attention axis for under-narration grounding.

A per-name count of covering sell-side analysts, summed from stockanalysis.com's
``/api/symbol/s/{TICKER}/overview`` ``analystChart`` buckets (``strongBuy``/``buy``/``hold``/
``sell``/``strongSell``). Free, no auth — the same stockanalysis.com source the project already
scrapes for ``corpus/etf_constituents`` (a different endpoint).

**Why this replaces news-count as the coverage proxy** (accel-feed record §19, 2026-06-30): the
free Alpaca/Benzinga news feed is a *broken* attention meter (sparse, saturates); analyst-count
is a materially better one — analyst-quiet and news-quiet overlap only Jaccard ~0.46 (they disagree
on ~half the names; spot-checks AAPL 47, GATX 4, RVLV 15, all verified against the live API). It is
the council's ``under_narrated`` (§9) coverage input.

**Scope caveat (record §19, do NOT over-read):** analyst-count measures *attention* (is there
sell-side coverage), NOT the thesis target *under-narrated-at-inflection*. A low count is a
quietness proxy, never proof of an inflection.

**PIT semantics:** the ``overview`` endpoint is a CURRENT snapshot with no history, so each record
is stamped at the pull's ``fetch_end`` (as the etf_constituents holdings snapshot is). An as-of read
at ``as_of ≥ fetch_end`` sees it; a read at an earlier ``as_of`` returns empty → ``None`` — so the
snapshot can never leak backward into a historical as-of (naturally lookahead-safe). This is correct
for the forward-only live loop (guardrail §6), which always judges as-of ≈ now; it is NOT a
historical-replay source.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from data.cache import PointInTimeCache


def _to_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)

SOURCE = "analyst_coverage"
OVERVIEW_URL = "https://stockanalysis.com/api/symbol/s/{symbol}/overview"
_EARLY = datetime(1990, 1, 1, tzinfo=UTC)
# stockanalysis.com serves its API only to browser-like User-Agents.
_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
       "Chrome/120.0 Safari/537.36")


def sum_analyst_chart(analyst_chart: Any) -> int | None:
    """Sum the analystChart rating buckets → the covering-analyst count.

    A dict (even all-zero) → the summed count (0 is a valid "no ratings"); anything else
    (``None`` / absent / non-dict, e.g. a thin ADR whose ``analystChart`` is ``null``) → ``None``
    = "unknown", NOT 0 — the §19 do-not-over-read discipline (a data gap is not a quietness signal).
    Pure / offline-testable."""
    if not isinstance(analyst_chart, dict):
        return None
    return int(sum(v for v in analyst_chart.values() if isinstance(v, (int, float))))


class AnalystCoverageData:
    """As-of analyst-coverage counts per symbol, backed by the point-in-time cache.

    Mirrors ``corpus/etf_constituents`` discipline (shared stockanalysis.com source): fail-soft
    (offline / no session / network error / missing field → ``None``), transient failures left
    uncached so a later run retries. Unlike etf_constituents there is NO permanent raw-JSON layer:
    the count must refresh (the PIT ``covers(_EARLY, fetch_end)`` check refetches when ``fetch_end``
    advances — i.e. daily in the live loop).
    """

    def __init__(
        self,
        cache: PointInTimeCache,
        *,
        fetch_end: datetime,
        session: Any | None = None,
        rate_limit_per_sec: float = 2.0,
        ua: str = _UA,
    ) -> None:
        self.cache = cache
        self.fetch_end = fetch_end
        # session=None ⇒ no-fetch mode (demo / offline tests): reads the PIT cache only.
        self.session = session
        self.ua = ua
        self.min_interval = 1.0 / rate_limit_per_sec if rate_limit_per_sec > 0 else 0.0
        self._last = 0.0

    def _throttle(self) -> None:
        if self.min_interval:
            wait = self.min_interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
        self._last = time.monotonic()

    def _fetch(self, symbol: str) -> int | None:
        """Live analyst count for one symbol, or ``None`` on any transient/unknown outcome
        (offline / no session / network error / non-200 / missing envelope / null analystChart)."""
        if self.cache.offline or self.session is None:
            return None
        try:
            self._throttle()
            resp = self.session.get(OVERVIEW_URL.format(symbol=symbol.upper()),
                                    headers={"User-Agent": self.ua, "Accept": "application/json"},
                                    timeout=30)
        except Exception:  # noqa: BLE001 — transient network error → retry next run
            return None
        if resp.status_code != 200:
            return None
        try:
            payload = resp.json()
        except ValueError:
            return None
        if payload.get("status") != 200 or "data" not in payload:
            return None
        return sum_analyst_chart((payload.get("data") or {}).get("analystChart"))

    def ensure_loaded(self, symbol: str) -> None:
        if self.cache.covers(SOURCE, symbol.upper(), _EARLY, self.fetch_end):
            return
        count = self._fetch(symbol)
        if count is None:
            return  # transient / unknown — leave uncached so a later run retries (no false 0)
        rec = {"ts": self.fetch_end.isoformat(), "symbol": symbol.upper(), "analyst_count": count}
        if not self.cache.offline:
            self.cache.write(SOURCE, symbol.upper(), [rec], coverage_from=_EARLY,
                             coverage_through=self.fetch_end)

    def count_asof(self, symbol: str, as_of: datetime) -> int | None:
        """Covering-analyst count for ``symbol`` as of ``as_of`` (the snapshot's pull time), or
        ``None`` when unknown (fail-soft — the council degrades to the pre-§19 grounding line).

        The snapshot record is stamped at ``fetch_end``, so we read at ``min(as_of, fetch_end)``: a
        live ``as_of`` that drifts PAST ``fetch_end`` (the council's ``clock.now()`` is a strictly
        later call than the provider's — LiveClock.now() advances) still sees the snapshot, while an
        ``as_of`` BEFORE ``fetch_end`` reads at ``as_of`` and finds nothing → None (no lookahead).
        Without the clamp the read would ``CacheMiss`` on ``as_of > coverage_through`` and the meter
        would silently never fire in the live loop."""
        self.ensure_loaded(symbol)
        read_at = min(_to_utc(as_of), _to_utc(self.fetch_end))
        try:
            recs = self.cache.read(SOURCE, symbol.upper(), read_at)
        except Exception:  # noqa: BLE001 — no coverage / as_of before the snapshot → unknown
            return None
        return recs[-1].get("analyst_count") if recs else None
