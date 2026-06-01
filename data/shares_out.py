"""XBRL shares-outstanding adapter (FSSD plan §8b) — the float denominator + supply validator.

Two jobs for FSSD:
  1. **Float denominator** for the friction composite (SI%-of-shares-out, inverse-float) — the
     point-in-time shares-outstanding count as of an event (PREREG §5).
  2. **Supply-magnitude validator (#3)** — the shares-outstanding *delta* around an event is a
     deterministic check on the prospectus-parsed deal size, and doubles as a primary-vs-
     secondary subtype hint (a pure secondary sells existing holders' shares → shares-out
     unchanged; a primary/dilutive raise → shares-out jumps).

Reuses the companyfacts download/cache pattern of :mod:`data.fundamentals`. **Fallback chain**
(the canonical concept is often absent — e.g. PLTR exposes only ``EntityPublicFloat``):
  ``dei:EntityCommonStockSharesOutstanding`` (shares)
  → ``us-gaap:CommonStockSharesOutstanding`` (shares)
  → ``dei:EntityPublicFloat`` (USD) ÷ price  (a float-in-shares proxy; needs a price).

Point-in-time by construction: every datapoint carries a ``filed`` date; an as-of read uses
only facts filed ≤ as_of.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SOURCE = "shares_out"
_EARLY = datetime(2003, 1, 1, tzinfo=UTC)

SHARES_CONCEPTS = [
    ("dei", "EntityCommonStockSharesOutstanding"),
    ("us-gaap", "CommonStockSharesOutstanding"),
]
FLOAT_USD_CONCEPT = ("dei", "EntityPublicFloat")


def _ts(filed: str) -> str:
    return filed if len(filed) > 10 else filed + "T20:00:00+00:00"


def extract_shares_points(facts_json: dict) -> list[dict[str, Any]]:
    """Shares-outstanding datapoints via the fallback chain.

    Returns ``{ts, end, val, filed, source}`` records (one per (end, filed), latest-filed
    winning per instant). ``source`` records which concept supplied the value; ``EntityPublicFloat``
    points carry ``float_usd`` instead of a share count (the caller divides by price).
    """
    facts = facts_json.get("facts", {})
    best: dict[str, dict[str, Any]] = {}

    def _consume(taxo: str, concept: str, *, is_usd: bool) -> None:
        unit = "USD" if is_usd else "shares"
        for u in facts.get(taxo, {}).get(concept, {}).get("units", {}).get(unit, []):
            end, filed, val = u.get("end"), u.get("filed"), u.get("val")
            if not (end and filed and val is not None):
                continue
            key = end
            prev = best.get(key)
            # prefer a real share count over the float-USD proxy at the same instant; within
            # the same source, latest-filed wins (amendments).
            cand = {
                "ts": _ts(filed), "end": end, "filed": filed,
                "source": f"{taxo}:{concept}",
            }
            if is_usd:
                cand["float_usd"] = float(val)
                cand["val"] = None
            else:
                cand["val"] = float(val)
            if prev is None:
                best[key] = cand
            elif prev.get("val") is None and not is_usd:
                best[key] = cand  # upgrade USD-proxy → real share count
            elif (prev.get("val") is None) == (cand.get("val") is None) and filed > prev["filed"]:
                best[key] = cand  # same kind, newer filing

    for taxo, concept in SHARES_CONCEPTS:
        _consume(taxo, concept, is_usd=False)
    _consume(*FLOAT_USD_CONCEPT, is_usd=True)
    return sorted(best.values(), key=lambda r: r["end"])


def shares_out_asof(
    points: list[dict[str, Any]], as_of: datetime, *, price: float | None = None
) -> tuple[float | None, str | None]:
    """Latest shares-outstanding filed ≤ as_of → (value, source).

    For an ``EntityPublicFloat`` point, divides the float-USD by ``price`` to approximate a
    share count (None if no price). Returns (None, None) if nothing usable.
    """
    iso = as_of.isoformat()
    visible = [p for p in points if _ts(p["filed"]) <= iso]
    if not visible:
        return (None, None)
    latest = visible[-1]
    if latest.get("val") is not None:
        return (latest["val"], latest["source"])
    fu = latest.get("float_usd")
    if fu is not None and price and price > 0:
        return (fu / price, latest["source"] + "÷price")
    return (None, None)


def shares_out_delta(
    points: list[dict[str, Any]], event_ts: datetime, *, primary_threshold: float = 0.02
) -> dict[str, Any] | None:
    """Supply-magnitude validator (#3): shares-out just-before vs first-after the event.

    ``pre`` = latest share count with instant ``end`` ≤ event; ``post`` = first share count with
    ``end`` strictly after the event. Returns ``{pre, post, pct_change, subtype}`` where subtype
    is 'primary' (dilutive: pct_change ≥ threshold), 'secondary' (≈0 change), or 'unknown'.
    Uses only real share counts (skips the float-USD proxy, which has no clean delta). Lagged
    (``post`` is the next quarterly), but deterministic — the clean cross-check on the
    prospectus parse. Caveat: the delta conflates buybacks/option-exercise/other issuance.
    """
    counts = [p for p in points if p.get("val") is not None]
    if not counts:
        return None
    ev = event_ts.date().isoformat()
    pre = [p for p in counts if p["end"] <= ev]
    post = [p for p in counts if p["end"] > ev]
    if not pre or not post:
        return None
    pre_v, post_v = pre[-1]["val"], post[0]["val"]
    if pre_v <= 0:
        return None
    pct = post_v / pre_v - 1.0
    subtype = "primary" if pct >= primary_threshold else ("secondary" if pct < primary_threshold / 2 else "unknown")
    return {"pre": pre_v, "post": post_v, "pct_change": pct, "subtype": subtype}


class SharesOutData:
    """As-of shares-outstanding per name (companyfacts), point-in-time cached. Mirrors
    :class:`data.fundamentals.FundamentalsData`."""

    def __init__(
        self,
        cache: Any,
        *,
        edgar: Any | None,
        fetch_end: datetime,
        ua: str = "",
        cache_dir: str | Path = "data/cache",
        session: Any | None = None,
        cik_overrides: dict[str, str] | None = None,
    ) -> None:
        self.cache = cache
        self.edgar = edgar
        self.fetch_end = fetch_end
        self.ua = ua
        self.raw_dir = Path(cache_dir) / "xbrl_raw"  # shared with fundamentals (same source file)
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
        pts = extract_shares_points(raw) if raw else []
        if not self.cache.offline:
            self.cache.write(SOURCE, cik, pts, coverage_from=_EARLY, coverage_through=self.fetch_end)
        return pts

    def _download(self, cik: str) -> dict | None:
        path = self.raw_dir / f"CIK{cik}.json"
        if path.exists():
            return json.loads(path.read_text())
        if self.session is None:
            import requests
            self.session = requests.Session()
        resp = self.session.get(FACTS_URL.format(cik=cik), headers={"User-Agent": self.ua}, timeout=60)
        if resp.status_code != 200:
            return None
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(resp.text)
        return resp.json()

    def shares_out_asof(self, symbol: str, as_of: datetime, *, price: float | None = None):
        return shares_out_asof(self._points(symbol), as_of, price=price)

    def delta_around(self, symbol: str, event_ts: datetime):
        pts = self._points(symbol)
        return shares_out_delta(pts, event_ts) if pts else None
