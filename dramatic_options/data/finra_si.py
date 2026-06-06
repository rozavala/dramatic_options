"""FINRA consolidated short-interest adapter (FSSD plan §8b — the keystone friction input).

Short interest is the most direct *short-sale-cost / limits-to-arbitrage* proxy in the FSSD
friction composite (PREREG §5, FREEZE-B #4). Source: FINRA's free, keyless query API
``api.finra.org/data/group/otcMarket/name/consolidatedShortInterest`` (per-symbol POST filter;
fields incl. ``currentShortPositionQuantity``, ``averageDailyVolumeQuantity``,
``daysToCoverQuantity``, ``settlementDate``).

**No-lookahead (the critical bit, PREREG §5):** SI is reported for a bi-monthly *settlement
date* but only becomes public ~8 trading days later. Using the settlement date as the
as-of timestamp would leak ~8 sessions of future information. So each record's cache ``ts`` is
a **conservative publication date = settlement_date + ``pub_lag_days`` calendar days**
(default 14 ≥ ~8 trading days), and ``si_asof`` filters on that. Erring late is safe (staler
friction proxy, never early).

Coverage-only in the audit — no returns are computed here.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from dramatic_options.data.cache import PointInTimeCache

SOURCE = "finra_si"
API_URL = "https://api.finra.org/data/group/otcMarket/name/consolidatedShortInterest"
# Conservative: real dissemination is ~8 *trading* days after settlement; 14 calendar days
# is safely ≥ that, so an as-of read never sees an SI print before it was public.
DEFAULT_PUB_LAG_DAYS = 14


def _d(s: str) -> datetime:
    """Parse an ISO date (YYYY-MM-DD) to aware UTC midnight."""
    return datetime.fromisoformat(s[:10]).replace(tzinfo=UTC)


def publication_date(settlement_date: str, *, pub_lag_days: int = DEFAULT_PUB_LAG_DAYS) -> str:
    """Conservative public-availability instant for an SI print settled on ``settlement_date``."""
    return (_d(settlement_date) + timedelta(days=pub_lag_days)).isoformat()


def parse_si_records(
    rows: list[dict[str, Any]], *, pub_lag_days: int = DEFAULT_PUB_LAG_DAYS
) -> list[dict[str, Any]]:
    """Normalize FINRA rows → cache records timestamped by **publication date**.

    Each record: ``{ts(=publication), settlement_date, si_shares, adv, days_to_cover}``.
    Pure / offline-testable. Rows missing a settlement date or short position are dropped.
    """
    out: list[dict[str, Any]] = []
    for r in rows:
        sd = r.get("settlementDate")
        si = r.get("currentShortPositionQuantity")
        if not sd or si is None:
            continue
        try:
            si_shares = float(si)
        except (TypeError, ValueError):
            continue
        adv = r.get("averageDailyVolumeQuantity")
        dtc = r.get("daysToCoverQuantity")
        out.append(
            {
                "ts": publication_date(sd, pub_lag_days=pub_lag_days),
                "settlement_date": sd[:10],
                "si_shares": si_shares,
                "adv": float(adv) if adv not in (None, "") else None,
                "days_to_cover": float(dtc) if dtc not in (None, "") else None,
            }
        )
    out.sort(key=lambda x: x["ts"])
    return out


def si_pct_of_shares(si_shares: float | None, shares_out: float | None) -> float | None:
    """Short interest as a fraction of shares outstanding (the friction input). None if either
    is missing or shares_out ≤ 0."""
    if si_shares is None or shares_out is None or shares_out <= 0:
        return None
    return si_shares / shares_out


class FinraShortInterest:
    """As-of consolidated short interest per symbol, backed by the point-in-time cache.

    Per-symbol fetch (targeted: the audit needs SI only for event names, and runs slice-first).
    Mirrors the disk+point-in-time caching discipline of the other data adapters.
    """

    def __init__(
        self,
        cache: PointInTimeCache,
        *,
        fetch_start: datetime,
        fetch_end: datetime,
        pub_lag_days: int = DEFAULT_PUB_LAG_DAYS,
        rate_limit_per_sec: float = 4.0,
        session: Any | None = None,
        cache_dir: str | Path = "data/cache",
    ) -> None:
        self.cache = cache
        self.fetch_start = fetch_start
        self.fetch_end = fetch_end
        self.pub_lag_days = pub_lag_days
        self.min_interval = 1.0 / rate_limit_per_sec if rate_limit_per_sec > 0 else 0.0
        self.session = session or requests.Session()
        self.raw_dir = Path(cache_dir) / "finra_si_raw"
        self._last = 0.0

    def _throttle(self) -> None:
        if self.min_interval:
            wait = self.min_interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
        self._last = time.monotonic()

    def _fetch_symbol(self, symbol: str) -> list[dict[str, Any]] | None:
        """POST-filter all SI rows for one symbol over the fetch window (raw JSON cached).

        Returns a list (possibly empty — a genuine "no SI for this symbol" that is safe to
        cache) or **None** on a transient failure (network error / retryable status), which the
        caller must NOT cache so it is re-fetched next run rather than poisoning the cache with a
        false empty. This split is what prevents a transient blip from permanently zeroing a
        name's short-interest (the keystone friction input)."""
        raw_path = self.raw_dir / f"{symbol.upper()}.json"
        if raw_path.exists():
            return json.loads(raw_path.read_text())
        if self.cache.offline:
            return []
        body = {
            "limit": 1000,
            "compareFilters": [
                {"compareType": "EQUAL", "fieldName": "symbolCode", "fieldValue": symbol.upper()}
            ],
            "dateRangeFilters": [
                {
                    "fieldName": "settlementDate",
                    "startDate": self.fetch_start.date().isoformat(),
                    "endDate": self.fetch_end.date().isoformat(),
                }
            ],
        }
        # Retry transient errors once. A name that errors on every attempt returns [] (and is
        # cached as empty by ensure_loaded), so it is never silently lost — it just carries no
        # si_pct (mean-imputed downstream). Silent loss is the failure mode we must avoid: an
        # un-cached name would re-fetch forever and quietly shrink the friction cross-section.
        for attempt in range(2):
            self._throttle()
            try:
                resp = self.session.post(
                    API_URL, json=body,
                    headers={"Accept": "application/json", "Content-Type": "application/json"},
                    timeout=60,
                )
            except Exception:  # noqa: BLE001 — transient network error
                if attempt == 0:
                    continue
                return None  # persistent transient failure → do NOT cache; refetch next run
            if resp.status_code == 200:
                rows = resp.json()
                self.raw_dir.mkdir(parents=True, exist_ok=True)
                raw_path.write_text(json.dumps(rows))
                return rows
            if resp.status_code in (429, 500, 502, 503, 504) and attempt == 0:
                continue  # transient server/rate error → one retry
            if resp.status_code in (429, 500, 502, 503, 504):
                return None  # still transient after retry → don't cache
            return []  # genuine non-200 (symbol not found) → empty, safe to cache
        return None

    def ensure_loaded(self, symbol: str) -> None:
        if self.cache.covers(SOURCE, symbol.upper(), self.fetch_start, self.fetch_end):
            return
        rows = self._fetch_symbol(symbol)
        if rows is None:
            return  # transient failure — leave uncached so a later run retries (no false empty)
        recs = parse_si_records(rows, pub_lag_days=self.pub_lag_days)
        if not self.cache.offline:
            self.cache.write(
                SOURCE, symbol.upper(), recs,
                coverage_from=self.fetch_start, coverage_through=self.fetch_end,
            )

    def si_asof(self, symbol: str, as_of: datetime) -> dict[str, Any] | None:
        """Latest SI print **public as of** ``as_of`` (publication-lagged), or None."""
        self.ensure_loaded(symbol)
        try:
            recs = self.cache.read(SOURCE, symbol.upper(), as_of)
        except Exception:  # noqa: BLE001 — no coverage for this name → no SI
            return None
        return recs[-1] if recs else None
