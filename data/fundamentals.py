"""Fundamentals adapter (Phase 1 iteration k=4 — substance INFORMATIVENESS).

The deterministic substance proxy through k=3 measured tangible-event *presence* (8-K item
codes, 13D/G, insider flows) — activity, not whether delivery actually backs the story. This
adapter measures **reported delivery** itself: year-over-year growth of revenue from SEC
**XBRL companyfacts** (`data.sec.gov/api/xbrl/companyfacts`).

Point-in-time by construction: every XBRL datapoint carries a ``filed`` date, so an as-of
read uses only facts filed ≤ as_of (amendments superseding by latest filed). Quarterly
datapoints (duration ≈ 90d) are summed into a trailing-twelve-month (TTM) figure; YoY growth
compares the latest TTM available as-of to the TTM one year earlier. Names whose year-ago
TTM revenue is below a materiality floor return None (excluded from that date's cross-section
— consistent with the N_min discipline): for pre-revenue names YoY growth on a ~0 base is
noise, not delivery.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REV_CONCEPTS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
]
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SOURCE = "fundamentals"
_EARLY = datetime(2003, 1, 1, tzinfo=UTC)


def _d(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=UTC) if len(s) == 10 else \
        datetime.fromisoformat(s)


def extract_quarterly_revenue(facts_json: dict) -> list[dict[str, Any]]:
    """Quarterly (≈90-day) revenue datapoints from a companyfacts payload.

    Returns records {"start","end","val","filed"} (ISO strings), one per (start,end) period
    keeping the LATEST-filed value (amendments win). Annual/YTD durations are dropped so the
    TTM sum doesn't double-count.
    """
    usg = facts_json.get("facts", {}).get("us-gaap", {})
    best: dict[tuple[str, str], dict[str, Any]] = {}
    for concept in REV_CONCEPTS:
        for u in usg.get(concept, {}).get("units", {}).get("USD", []):
            start, end, filed = u.get("start"), u.get("end"), u.get("filed")
            if not (start and end and filed and u.get("val") is not None):
                continue
            dur = (_d(end) - _d(start)).days
            if not (80 <= dur <= 100):  # quarterly only
                continue
            key = (start, end)
            prev = best.get(key)
            if prev is None or filed > prev["filed"]:
                best[key] = {"start": start, "end": end, "val": float(u["val"]), "filed": filed}
    return sorted(best.values(), key=lambda r: r["end"])


def _ttm_at(points: list[dict[str, Any]], anchor_end: str) -> float | None:
    """Sum of the 4 quarterly values ending at or before ``anchor_end`` (need exactly 4)."""
    elig = [p for p in points if p["end"] <= anchor_end]
    if len(elig) < 4:
        return None
    return sum(p["val"] for p in elig[-4:])


def revenue_yoy(points: list[dict[str, Any]], as_of: datetime, *, min_base: float) -> float | None:
    """YoY growth of TTM revenue using only points filed ≤ as_of.

    None if: <8 quarters available, no period ~1y before the latest, or year-ago TTM below
    ``min_base`` (immaterial → growth is noise).
    """
    iso = as_of.isoformat()
    visible = sorted((p for p in points if p["filed"] <= iso), key=lambda r: r["end"])
    if len(visible) < 8:
        return None
    latest_end = visible[-1]["end"]
    ttm_now = _ttm_at(visible, latest_end)
    if ttm_now is None:
        return None
    # find a period ~1 year before latest_end (within ±45 days)
    target = (_d(latest_end).replace(year=_d(latest_end).year - 1)).date().isoformat()
    prior = [p for p in visible if abs((_d(p["end"]) - _d(target)).days) <= 45]
    if not prior:
        return None
    ttm_prior = _ttm_at(visible, prior[-1]["end"])
    if ttm_prior is None or ttm_prior < min_base:
        return None
    return ttm_now / ttm_prior - 1.0


class FundamentalsData:
    """As-of revenue-growth (delivery) per name, backed by the point-in-time cache.

    Raw companyfacts JSON is cached on disk (keyed by CIK); the parsed quarterly series is
    cached in the point-in-time cache. ``edgar`` resolves ticker→CIK; ``None`` ⇒ offline.
    """

    def __init__(
        self,
        cache: Any,
        *,
        edgar: Any | None,
        fetch_end: datetime,
        ua: str = "",
        cache_dir: str | Path = "data/cache",
        min_base_revenue: float = 10_000_000.0,
        session: Any | None = None,
        cik_overrides: dict[str, str] | None = None,
    ) -> None:
        self.cache = cache
        self.edgar = edgar
        self.fetch_end = fetch_end
        self.ua = ua
        self.raw_dir = Path(cache_dir) / "xbrl_raw"
        self.min_base = min_base_revenue
        self.session = session
        self.cik_overrides = cik_overrides or {}

    def _cik(self, symbol: str) -> str | None:
        if self.edgar is not None:
            return self.edgar.ticker_to_cik(symbol, overrides=self.cik_overrides)
        ov = self.cik_overrides.get(symbol.upper())
        return str(ov).zfill(10) if ov else None

    def _points(self, symbol: str) -> list[dict[str, Any]]:
        cik = self._cik(symbol)
        if cik is None:
            return []
        if self.cache.covers(SOURCE, cik, _EARLY, self.fetch_end):
            return self.cache.read_between(SOURCE, cik, None, self.fetch_end)
        if self.edgar is None or self.cache.offline:
            return []
        raw = self._download(cik)
        points = extract_quarterly_revenue(raw) if raw else []
        # store with ts = filed date so as-of reads filter correctly via read_between
        recs = [{"ts": p["filed"] if len(p["filed"]) > 10 else p["filed"] + "T20:00:00+00:00",
                 "start": p["start"], "end": p["end"], "val": p["val"], "filed": p["filed"]}
                for p in points]
        self.cache.write(SOURCE, cik, recs, coverage_from=_EARLY, coverage_through=self.fetch_end)
        return recs

    def _download(self, cik: str) -> dict | None:
        path = self.raw_dir / f"CIK{cik}.json"
        if path.exists():
            return json.loads(path.read_text())
        if not self.ua or self.session is None:
            import requests
            self.session = self.session or requests.Session()
        resp = self.session.get(FACTS_URL.format(cik=cik), headers={"User-Agent": self.ua},
                                timeout=60)
        if resp.status_code != 200:
            return None
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(resp.text)
        return resp.json()

    def revenue_growth_asof(self, symbol: str, as_of: datetime) -> float | None:
        pts = self._points(symbol)
        if not pts:
            return None
        return revenue_yoy(pts, as_of, min_base=self.min_base)
