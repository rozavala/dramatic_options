"""Stage-0 corpus — theme-ETF/index constituents, the investable-universe surface.

Part of the deterministic theme-generation corpus (``PREREG_THEME_GENERATION_STUB`` Stage 0; the
``PREREG_UNIVERSE_CURATION`` §4 "ETF/index constituent files" seed source). A theme ETF's holdings
ARE the curated investable universe for that theme (URNM/NLR = uranium·nuclear, GRID = grid
infrastructure, COPX = copper miners) — structural membership that seeds + cross-checks the baskets.

Source: ``stockanalysis.com/api/symbol/e/{ETF}/holdings`` — the project's established constituent
source (``universe_register.json`` already cites stockanalysis.com for URNM/NLR/COPX/UFO/ARKX), a
uniform JSON API across funds (the issuer sites are JS-rendered / redirect-loop / Cloudflare-blocked).

Records are STRUCTURAL composition only — constituent name, ticker, and the fund WEIGHT/shares (a
portfolio composition figure, not a market price/IV/momentum/sentiment; the §2 prohibition — this
module imports no market source).

PIT: a holdings list is a current snapshot with no inherent date, so each record is stamped at the
pull's ``fetch_end`` (the as-of high-water); an as-of read at ``as_of ≥ fetch_end`` sees the snapshot.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from data.cache import PointInTimeCache

SOURCE = "corpus_etf_constituents"
HOLDINGS_URL = "https://stockanalysis.com/api/symbol/e/{etf}/holdings"
_EARLY = datetime(1990, 1, 1, tzinfo=UTC)
# stockanalysis.com serves its API only to browser-like User-Agents.
_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
       "Chrome/120.0 Safari/537.36")


def _parse_symbol(raw: str | None) -> tuple[str | None, str | None, bool]:
    """stockanalysis symbol token → (ticker, exchange, us_listed).

    ``"$CCJ"`` → US (``"CCJ", None, True``); ``"!tsx/NXE"`` → foreign (``"NXE", "tsx", False``);
    absent / name-only holding → ``(None, None, False)``."""
    raw = (raw or "").strip()
    if not raw:
        return None, None, False
    if raw.startswith("$"):
        return (raw[1:].strip() or None), None, True
    if raw.startswith("!"):
        ex, _, tk = raw[1:].partition("/")
        return (tk.strip() or None), (ex.strip() or None), False
    return raw, None, False


def _pct(s: Any) -> float | None:
    try:
        return float(str(s).replace("%", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _int(s: Any) -> int | None:
    if s in (None, ""):
        return None
    try:
        return int(str(s).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def parse_holdings(payload: dict, etf: str, *, as_of_ts: str) -> list[dict[str, Any]]:
    """Pure: a stockanalysis holdings payload → structural constituent records, stamped at as_of_ts.

    Record: ``{ts, etf, rank, name, symbol, exchange, us_listed, weight_pct, shares}``. NO prices
    (§2) — ``weight_pct`` is the fund composition, ``shares`` the held count. Pure / offline-testable.
    """
    out: list[dict[str, Any]] = []
    for h in payload.get("data", {}).get("holdings", []):
        symbol, exchange, us_listed = _parse_symbol(h.get("s"))
        out.append({
            "ts": as_of_ts, "etf": etf.upper(), "rank": h.get("no"), "name": h.get("n"),
            "symbol": symbol, "exchange": exchange, "us_listed": us_listed,
            "weight_pct": _pct(h.get("as")), "shares": _int(h.get("sh")),
        })
    return out


class ETFConstituents:
    """As-of theme-ETF constituents per fund, backed by the point-in-time cache.

    Mirrors ``data/finra_si`` discipline: raw JSON cached on disk (network-free re-parse), parsed
    records in the point-in-time cache, transient-vs-genuine-empty split, fail-soft (offline → ``[]``).
    """

    def __init__(
        self,
        cache: PointInTimeCache,
        *,
        fetch_end: datetime,
        session: Any | None = None,
        cache_dir: str | Path = "data/cache",
        rate_limit_per_sec: float = 2.0,
        ua: str = _UA,
    ) -> None:
        self.cache = cache
        self.fetch_end = fetch_end
        self.session = session or requests.Session()
        self.ua = ua
        self.min_interval = 1.0 / rate_limit_per_sec if rate_limit_per_sec > 0 else 0.0
        self.raw_dir = Path(cache_dir) / "etf_holdings_raw"
        self._last = 0.0

    def _throttle(self) -> None:
        if self.min_interval:
            wait = self.min_interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
        self._last = time.monotonic()

    def _fetch(self, etf: str) -> dict | None:
        """Raw holdings payload for one ETF. ``None`` on a transient failure (network / non-200 /
        missing data envelope) so it is not cached as a false empty."""
        raw_path = self.raw_dir / f"{etf.upper()}.json"
        if raw_path.exists():
            return json.loads(raw_path.read_text())
        if self.cache.offline:
            return None
        try:
            self._throttle()
            resp = self.session.get(HOLDINGS_URL.format(etf=etf.upper()),
                                    headers={"User-Agent": self.ua, "Accept": "application/json"},
                                    timeout=30)
        except Exception:  # noqa: BLE001 — transient network error → refetch next run
            return None
        if resp.status_code != 200:
            return None
        payload = resp.json()
        if payload.get("status") != 200 or "data" not in payload:
            return None
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(json.dumps(payload))
        return payload

    def ensure_loaded(self, etf: str) -> None:
        if self.cache.covers(SOURCE, etf.upper(), _EARLY, self.fetch_end):
            return
        payload = self._fetch(etf)
        if payload is None:
            return  # transient — leave uncached so a later run retries (no false empty)
        recs = parse_holdings(payload, etf, as_of_ts=self.fetch_end.isoformat())
        if not self.cache.offline:
            self.cache.write(SOURCE, etf.upper(), recs, coverage_from=_EARLY,
                             coverage_through=self.fetch_end)

    def constituents_asof(self, etf: str, as_of: datetime) -> list[dict[str, Any]]:
        """Constituents of ``etf`` public as of ``as_of`` (the snapshot's pull time)."""
        self.ensure_loaded(etf)
        try:
            return self.cache.read(SOURCE, etf.upper(), as_of)
        except Exception:  # noqa: BLE001 — no coverage for this ETF → empty
            return []
