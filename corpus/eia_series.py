"""Stage-0 corpus — EIA energy series (Open Data v2), the energy-supply/demand surface.

Part of the deterministic theme-generation corpus (``PREREG_THEME_GENERATION_STUB`` Stage 0).
Pulls U.S. Energy Information Administration series from the v2 API
(``api.eia.gov/v2/{route}/data/``) — generation, capacity, retail price, fuel stocks etc. are
structural energy statistics (where supply/demand is shifting), feeding themes like nuclear fuel,
grid equipment, and copper/power.

Requires ``EIA_API_KEY`` (in the live ``.env``; loaded fail-soft like the fundamentals UA — no key
⇒ ``[]``, never blocks). **The key is a secret: it is never logged, never written to a cache
filename, and never appears in a record.**

Which route / metric / facets is a CONTENT decision made by the caller (the puller is generic).
Worked example: ``route="electricity/retail-sales"``, ``value_field="price"``,
``params={"frequency": "monthly", "facets[sectorid][0]": "IND"}``.

NO prices/IV/momentum/sentiment in the §2 sense — an EIA statistical series (a generation MWh, a
retail ¢/kWh tariff) is government energy data, and this module imports no market source.

PIT: each datapoint is timestamped at its period END plus a conservative publication lag
(``pub_lag_days``, default 75 ≥ the typical EIA monthly lag), so an as-of read never sees a print
before it was public (the no-lookahead discipline; cf. ``data/finra_si``).
"""

from __future__ import annotations

import calendar
import hashlib
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

from data.cache import PointInTimeCache

SOURCE = "corpus_eia"
EIA_BASE = "https://api.eia.gov/v2"
_EARLY = datetime(1990, 1, 1, tzinfo=UTC)
DEFAULT_PUB_LAG_DAYS = 75


def _eia_period_end(period: str) -> tuple[int, int, int] | None:
    """EIA period string → (year, month, day) of its last day.

    Handles ``YYYY`` (annual), ``YYYY-MM`` (monthly), ``YYYY-QN`` (quarterly), and ``YYYY-MM-DD``
    (daily). Unknown shapes → None (skipped)."""
    p = period.strip()
    try:
        if len(p) == 4:
            return (int(p), 12, 31)
        if len(p) == 7 and p[4] == "-":
            if p[5] == "Q":
                m = int(p[6]) * 3
                return (int(p[:4]), m, calendar.monthrange(int(p[:4]), m)[1])
            y, m = int(p[:4]), int(p[5:7])
            return (y, m, calendar.monthrange(y, m)[1]) if 1 <= m <= 12 else None
        if len(p) == 10 and p[4] == "-" and p[7] == "-":
            return (int(p[:4]), int(p[5:7]), int(p[8:10]))
    except ValueError:
        return None
    return None


def parse_eia_series(
    response_json: dict, *, value_field: str, pub_lag_days: int = DEFAULT_PUB_LAG_DAYS
) -> list[dict[str, Any]]:
    """Pure: an EIA v2 response → records ``{ts, period, value, units, dims}``.

    ``value_field`` is the metric column (e.g. ``"price"``, ``"generation"``); ``dims`` carries the
    remaining facet columns (stateid, sectorid, …) so structural context is preserved generically.
    ``ts`` = period end + ``pub_lag_days``. Non-numeric / unknown-period rows dropped. Pure."""
    out: list[dict[str, Any]] = []
    units_key = f"{value_field}-units"
    for row in response_json.get("response", {}).get("data", []):
        period, raw_val = row.get("period"), row.get(value_field)
        if period is None or raw_val is None:
            continue
        try:
            val = float(raw_val)
        except (ValueError, TypeError):
            continue
        pe = _eia_period_end(str(period))
        if pe is None:
            continue
        ts = (datetime(pe[0], pe[1], pe[2], 20, 0, 0, tzinfo=UTC)
              + timedelta(days=pub_lag_days)).isoformat()
        dims = {k: v for k, v in row.items() if k not in (value_field, units_key, "period")}
        out.append({"ts": ts, "period": str(period), "value": val,
                    "units": row.get(units_key), "dims": dims})
    out.sort(key=lambda r: r["ts"])
    return out


def cache_key(route: str, value_field: str, params: dict | None) -> str:
    """Stable point-in-time-cache key for a query (route × metric × facets). The api_key is
    deliberately EXCLUDED — the secret never enters the cache identity. Public so the corpus content
    layer (``corpus/content.py``) can derive a pull's read coord without re-running the fetch."""
    ident = json.dumps([route.strip("/"), value_field, sorted((params or {}).items())],
                       sort_keys=True, default=str)
    return "eia_" + hashlib.sha1(ident.encode()).hexdigest()[:12]


class EIASeries:
    """As-of EIA series values, backed by the point-in-time cache (per route×metric×facets query).

    Mirrors ``data/finra_si`` discipline: raw JSON cached on disk (network-free re-parse; the
    filename is a hash of the QUERY, never the api_key), parsed records in the point-in-time cache,
    transient-vs-empty split. **No api_key ⇒ no fetch ⇒ empty** (fail-soft).
    """

    def __init__(
        self,
        cache: PointInTimeCache,
        *,
        api_key: str | None,
        fetch_end: datetime,
        pub_lag_days: int = DEFAULT_PUB_LAG_DAYS,
        rate_limit_per_sec: float = 4.0,
        session: Any | None = None,
        cache_dir: str | Path = "data/cache",
        base_url: str = EIA_BASE,
    ) -> None:
        self.cache = cache
        self.api_key = api_key or ""  # secret — never logged / never in a filename
        self.fetch_end = fetch_end
        self.pub_lag_days = pub_lag_days
        self.min_interval = 1.0 / rate_limit_per_sec if rate_limit_per_sec > 0 else 0.0
        self.session = session or requests.Session()
        self.raw_dir = Path(cache_dir) / "eia_raw"
        self.base_url = base_url.rstrip("/")
        self._last = 0.0

    def _key(self, route: str, value_field: str, params: dict | None) -> str:
        return cache_key(route, value_field, params)

    def _throttle(self) -> None:
        if self.min_interval:
            wait = self.min_interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
        self._last = time.monotonic()

    def _fetch(self, route: str, value_field: str, params: dict | None, key: str) -> dict | None:
        """Raw EIA v2 response. ``None`` on a transient failure (network / non-200 / missing
        ``response`` envelope) so it is not cached as a false empty. The api_key rides the query
        string only — it is never logged here."""
        raw_path = self.raw_dir / f"{key}.json"
        if raw_path.exists():
            return json.loads(raw_path.read_text())
        if self.cache.offline or not self.api_key:
            return None
        query = dict(params or {})
        query["data[0]"] = value_field
        query["api_key"] = self.api_key
        url = f"{self.base_url}/{route.strip('/')}/data/?" + urlencode(query, safe="[]")
        try:
            self._throttle()
            resp = self.session.get(
                url, headers={"User-Agent": "dramatic-options corpus"}, timeout=40
            )
        except Exception:  # noqa: BLE001 — transient (NB: never log url; it carries the key)
            return None
        if resp.status_code != 200:
            return None
        payload = resp.json()
        if "response" not in payload:
            return None  # malformed / error envelope → transient, do not cache
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(json.dumps(payload))
        return payload

    def ensure_loaded(self, route: str, *, value_field: str, params: dict | None = None) -> str:
        key = self._key(route, value_field, params)
        if self.cache.covers(SOURCE, key, _EARLY, self.fetch_end):
            return key
        payload = self._fetch(route, value_field, params, key)
        if payload is None:
            return key  # transient / no key — leave uncached so a later run retries
        recs = parse_eia_series(payload, value_field=value_field, pub_lag_days=self.pub_lag_days)
        if not self.cache.offline:
            self.cache.write(
                SOURCE, key, recs, coverage_from=_EARLY, coverage_through=self.fetch_end
            )
        return key

    def series_asof(
        self, route: str, *, value_field: str, as_of: datetime, params: dict | None = None
    ) -> list[dict[str, Any]]:
        """All datapoints for a query public as of ``as_of`` (publication-lagged), ascending."""
        key = self.ensure_loaded(route, value_field=value_field, params=params)
        try:
            return self.cache.read(SOURCE, key, as_of)
        except Exception:  # noqa: BLE001 — no coverage for this query → empty
            return []
