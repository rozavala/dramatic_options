"""Stage-0 corpus — federal contract awards (USASpending / DoD), the government-capital surface.

Part of the deterministic theme-generation corpus (``PREREG_THEME_GENERATION_STUB`` Stage 0; the
``PREREG_UNIVERSE_CURATION`` §4 "SAM.gov/DoD awards" seed source). Pulls the largest contract
awards (by obligated amount) for an agency (default Department of Defense, USAspending toptier 097)
over a window from USAspending's keyless ``spending_by_award`` API — recipient, NAICS, and obligated
dollars reveal where federal capital is flowing into a sector, a structural (non-narrated) theme
signal.

Records are STRUCTURAL only — recipient, NAICS, federal obligation amount, agency. The award AMOUNT
is a government obligation, NOT a market price/IV/momentum/sentiment (the §2 prohibition; this module
imports no market source).

PIT note: ``spending_by_award`` does not reliably populate a per-award action date (the field is null
on award summaries), so the corpus stamps every award at the **window end ``end``** (the pull's
as-of high-water). The ``time_period`` filter selects awards with an action in ``[start, end]``
(default ``date_type=action_date``), so by ``end`` each returned award is already public — stamping
there errs LATE, never early (the no-lookahead discipline; cf. ``data/finra_si`` publication lag).
``end`` doubles as ``coverage_through``, so an as-of read at ``as_of ≥ end`` sees the slice.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from data.cache import PointInTimeCache

SOURCE = "corpus_federal_awards"
AWARD_URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
# Department of Defense, awarding toptier (USAspending agency 097).
DEFAULT_AGENCIES: list[dict[str, str]] = [
    {"type": "awarding", "tier": "toptier", "name": "Department of Defense"}
]
# Definitive + IDV contract award types (A/B/C/D). Grants/loans excluded by default.
DEFAULT_AWARD_TYPE_CODES: tuple[str, ...] = ("A", "B", "C", "D")
# Requested result fields (the API names; "Award Amount" sort is the only verified-stable sort key).
_FIELDS = ["Award ID", "Recipient Name", "Award Amount", "NAICS", "recipient_id", "Awarding Agency"]


def _query_key(
    agencies: list[dict[str, str]],
    award_type_codes: tuple[str, ...] | list[str],
    naics_codes: list[str] | None,
) -> str:
    """Stable cache key for a query shape (agency set × award types × NAICS filter)."""
    ident = json.dumps(
        [agencies, sorted(award_type_codes), sorted(naics_codes or [])],
        sort_keys=True, default=str,
    )
    return "awards_" + hashlib.sha1(ident.encode()).hexdigest()[:10]


def parse_federal_awards(results: list[dict[str, Any]], *, as_of_ts: str) -> list[dict[str, Any]]:
    """Pure: USAspending ``results[]`` → structural award records, all stamped at ``as_of_ts``.

    Drops rows with no Award ID (no identity). Sorted by amount desc (award_id tiebreak) for a
    deterministic slice. NO prices (§2) — ``amount`` is a federal obligation, not a market quote.
    """
    out: list[dict[str, Any]] = []
    for r in results:
        award_id = r.get("Award ID")
        if not award_id:
            continue
        amt = r.get("Award Amount")
        naics = r.get("NAICS")
        naics = naics if isinstance(naics, dict) else {}
        out.append(
            {
                "ts": as_of_ts,
                "award_id": award_id,
                "recipient": r.get("Recipient Name"),
                "recipient_id": r.get("recipient_id"),
                "amount": float(amt) if amt is not None else None,
                "naics_code": naics.get("code"),
                "naics_desc": naics.get("description"),
                "agency": r.get("Awarding Agency"),
            }
        )
    out.sort(key=lambda r: (-(r["amount"] or 0.0), str(r["award_id"])))
    return out


def _fetch_paginated(
    session: Any,
    filters: dict[str, Any],
    *,
    page_size: int,
    max_pages: int,
    rate_limit_per_sec: float,
) -> list[dict[str, Any]] | None:
    """Top awards by Award Amount over ``max_pages`` pages. Fail-soft: returns whatever was
    fetched before an error (``None`` only if the FIRST page fails outright)."""
    min_interval = 1.0 / rate_limit_per_sec if rate_limit_per_sec > 0 else 0.0
    out: list[dict[str, Any]] = []
    last = 0.0
    for page in range(1, max_pages + 1):
        if min_interval:
            wait = min_interval - (time.monotonic() - last)
            if wait > 0:
                time.sleep(wait)
        last = time.monotonic()
        body = {
            "filters": filters, "fields": _FIELDS, "page": page,
            "limit": page_size, "sort": "Award Amount", "order": "desc",
        }
        try:
            resp = session.post(
                AWARD_URL, json=body,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                timeout=60,
            )
            if resp.status_code != 200:
                return out or None
            payload = resp.json()
        except Exception:  # noqa: BLE001 — fail-soft: a corpus hiccup must not break assembly
            return out or None
        out.extend(payload.get("results", []) or [])
        if not (payload.get("page_metadata", {}) or {}).get("hasNext"):
            break
    return out


def enumerate_federal_awards(
    start: datetime,
    end: datetime,
    *,
    session: Any | None = None,
    cache: PointInTimeCache,
    cache_dir: str | Path = "data/cache",
    agencies: list[dict[str, str]] | None = None,
    award_type_codes: tuple[str, ...] | list[str] = DEFAULT_AWARD_TYPE_CODES,
    naics_codes: list[str] | None = None,
    page_size: int = 100,
    max_pages: int = 5,
    rate_limit_per_sec: float = 4.0,
) -> list[dict[str, Any]]:
    """Top agency (default DoD) contract awards active in ``[start, end]``, by obligated amount.

    Each record carries ``ts = end`` (the pull's as-of high-water — see module docstring). Raw
    paginated results are cached to ``<cache_dir>/federal_awards_raw/`` (network-free re-parse);
    parsed records go to the point-in-time cache for as-of reads. ``session`` defaults to a fresh
    ``requests.Session`` when online; an offline cache never attempts the network. **Fail-soft:** an
    offline+uncached read, or an HTTP error on the first page, yields ``[]`` — never raises.
    """
    agencies = agencies or DEFAULT_AGENCIES
    key = _query_key(agencies, award_type_codes, naics_codes)
    # Network-free reuse if a prior (≥ this-window) pull is already cached point-in-time.
    if cache.covers(SOURCE, key, start, end):
        ct = cache.coverage_through(SOURCE, key)
        return cache.read_between(SOURCE, key, None, ct) if ct else []

    raw_dir = Path(cache_dir) / "federal_awards_raw"
    raw_path = raw_dir / f"{key}_{start.date().isoformat()}_{end.date().isoformat()}.json"
    if raw_path.exists():
        raw_results: list[dict[str, Any]] | None = json.loads(raw_path.read_text())
    elif cache.offline:
        return []  # offline + uncached → nothing to assemble (never a network attempt)
    else:
        filters: dict[str, Any] = {
            "time_period": [
                {"start_date": start.date().isoformat(), "end_date": end.date().isoformat()}
            ],
            "agencies": agencies,
            "award_type_codes": list(award_type_codes),
        }
        if naics_codes:
            filters["naics_codes"] = list(naics_codes)
        raw_results = _fetch_paginated(
            session or requests.Session(), filters, page_size=page_size, max_pages=max_pages,
            rate_limit_per_sec=rate_limit_per_sec,
        )
        if raw_results is None:
            return []  # first-page failure → do not cache (refetch next run, no false-empty)
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(json.dumps(raw_results))

    recs = parse_federal_awards(raw_results or [], as_of_ts=end.isoformat())
    if not cache.offline and recs:
        cache.write(SOURCE, key, recs, coverage_from=start, coverage_through=end)
    return recs
