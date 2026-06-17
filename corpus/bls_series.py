"""Stage-0 corpus — BLS time series (energy / labor), the macro-activity surface.

Part of the deterministic theme-generation corpus (``PREREG_THEME_GENERATION_STUB`` Stage 0).
Pulls Bureau of Labor Statistics series from the keyless public API v1
(``api.bls.gov/publicAPI/v1/timeseries/data/{seriesID}``) — energy-price CPI/PPI and
sector-employment series are structural macro signals (where labor/cost pressure is building),
never market prices.

Which series is a CONTENT decision made by the caller / the assembly step (the puller is generic).
Worked examples (energy/labor):
  - ``CUUR0000SEHF01`` — CPI, electricity (U.S. city average)
  - ``CUUR0000SETB01`` — CPI, gasoline (all types)
  - ``CES1021100001``  — All employees, oil & gas extraction

NO prices/IV/momentum/sentiment in the §2 sense — a CPI index level or an employment count is a
government statistical series, and this module imports no market source.

PIT: each datapoint is timestamped at its reference-period END plus a conservative publication lag
(``pub_lag_days``, default 30 ≥ the slowest monthly BLS release), so an as-of read never sees a print
before it was public (the no-lookahead discipline; cf. ``data/finra_si`` publication lag). Series with
unusually long lags (e.g. QCEW) should be pulled with a larger ``pub_lag_days``.
"""

from __future__ import annotations

import calendar
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from data.cache import PointInTimeCache

SOURCE = "corpus_bls"
SERIES_URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/{series_id}"
_EARLY = datetime(1990, 1, 1, tzinfo=UTC)  # GET returns recent history → coverage start sentinel
DEFAULT_PUB_LAG_DAYS = 30


def _period_end(year: int, period: str) -> tuple[int, int, int] | None:
    """(year, BLS period code) → (year, month, day) of the reference period's last day.

    ``M01``–``M12`` monthly (``M13`` = annual average), ``Q01``–``Q04`` quarterly (``Q05`` =
    annual), ``A01`` annual, ``S01``/``S02`` semiannual. Unknown codes → None (skipped)."""
    p = period.upper()
    code, _, rest = p[0], p[1:2], p[1:]
    try:
        n = int(rest)
    except ValueError:
        return None
    if code == "M":
        if n == 13:
            return (year, 12, 31)
        return (year, n, calendar.monthrange(year, n)[1]) if 1 <= n <= 12 else None
    if code == "Q":
        if n == 5:
            return (year, 12, 31)
        return (year, n * 3, calendar.monthrange(year, n * 3)[1]) if 1 <= n <= 4 else None
    if code == "A":
        return (year, 12, 31)
    if code == "S":
        return (year, 6, 30) if n == 1 else (year, 12, 31)
    return None


def parse_bls_series(results_json: dict, *, pub_lag_days: int = DEFAULT_PUB_LAG_DAYS) -> list[dict[str, Any]]:
    """Pure: a BLS v1 response → records ``{ts, series_id, year, period, value}``.

    ``ts`` = reference-period end + ``pub_lag_days`` (conservative publication date). Non-numeric
    values (``"-"``, suppressed) and unknown period codes are dropped. Pure / offline-testable."""
    out: list[dict[str, Any]] = []
    for s in results_json.get("Results", {}).get("series", []):
        sid = s.get("seriesID")
        for d in s.get("data", []):
            try:
                year, period, val = int(d["year"]), str(d["period"]), float(d["value"])
            except (KeyError, ValueError, TypeError):
                continue
            pe = _period_end(year, period)
            if pe is None:
                continue
            ts = (datetime(pe[0], pe[1], pe[2], 20, 0, 0, tzinfo=UTC)
                  + timedelta(days=pub_lag_days)).isoformat()
            out.append({"ts": ts, "series_id": sid, "year": year, "period": period, "value": val})
    out.sort(key=lambda r: (r["ts"], str(r["series_id"])))
    return out


class BLSSeries:
    """As-of BLS series values, backed by the point-in-time cache (per-series fetch).

    Mirrors ``data/finra_si`` discipline: raw JSON cached on disk (network-free re-parse), parsed
    records in the point-in-time cache, and a transient-vs-genuine-empty split so a rate-limit blip
    never poisons the cache with a false empty.
    """

    def __init__(
        self,
        cache: PointInTimeCache,
        *,
        fetch_end: datetime,
        pub_lag_days: int = DEFAULT_PUB_LAG_DAYS,
        rate_limit_per_sec: float = 4.0,
        session: Any | None = None,
        cache_dir: str | Path = "data/cache",
    ) -> None:
        self.cache = cache
        self.fetch_end = fetch_end
        self.pub_lag_days = pub_lag_days
        self.min_interval = 1.0 / rate_limit_per_sec if rate_limit_per_sec > 0 else 0.0
        self.session = session or requests.Session()
        self.raw_dir = Path(cache_dir) / "bls_raw"
        self._last = 0.0

    def _throttle(self) -> None:
        if self.min_interval:
            wait = self.min_interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
        self._last = time.monotonic()

    def _fetch_series(self, series_id: str) -> dict | None:
        """Raw BLS v1 response for one series. ``None`` on a transient failure (network / non-200 /
        ``status != REQUEST_SUCCEEDED`` — likely a rate-limit) so the caller does NOT cache it;
        a succeeded-but-empty response returns a real payload (safe to cache as empty)."""
        raw_path = self.raw_dir / f"{series_id}.json"
        if raw_path.exists():
            return json.loads(raw_path.read_text())
        if self.cache.offline:
            return None
        try:
            self._throttle()
            resp = self.session.get(
                SERIES_URL.format(series_id=series_id),
                headers={"User-Agent": "dramatic-options corpus"}, timeout=30,
            )
        except Exception:  # noqa: BLE001 — transient network error → refetch next run
            return None
        if resp.status_code != 200:
            return None
        payload = resp.json()
        if payload.get("status") != "REQUEST_SUCCEEDED":
            return None  # rate-limit / not-processed → transient, do not cache
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(json.dumps(payload))
        return payload

    def ensure_loaded(self, series_id: str) -> None:
        if self.cache.covers(SOURCE, series_id, _EARLY, self.fetch_end):
            return
        payload = self._fetch_series(series_id)
        if payload is None:
            return  # transient — leave uncached so a later run retries (no false empty)
        recs = parse_bls_series(payload, pub_lag_days=self.pub_lag_days)
        if not self.cache.offline:
            self.cache.write(
                SOURCE, series_id, recs, coverage_from=_EARLY, coverage_through=self.fetch_end
            )

    def series_asof(self, series_id: str, as_of: datetime) -> list[dict[str, Any]]:
        """All datapoints for ``series_id`` public as of ``as_of`` (publication-lagged), ascending."""
        self.ensure_loaded(series_id)
        try:
            return self.cache.read(SOURCE, series_id, as_of)
        except Exception:  # noqa: BLE001 — no coverage for this series → empty
            return []
