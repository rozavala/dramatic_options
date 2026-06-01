"""Insider-transactions adapter (Phase 1 iteration k=3 — substance refinement).

Replaces the crude Form-4 *presence* signal (which counted every routine RSU-vesting /
10b5-1 filing as positive "delivery") with **signed insider net-buying**, the delivery
signal the literature actually supports: insiders buy for one reason, but sell for many
(liquidity, diversification, automated 10b5-1 plans).

Source: SEC's bulk **Form 345 insider-transactions data sets** (quarterly TSV zips) — all
transactions in ~17 files for the window, instead of thousands of per-filing XML fetches.
Per Form-4: net_buy = Σ(open-market purchases, code P) − Σ(open-market sales, code S that
are NOT flagged 10b5-1). Records are keyed by issuer CIK (stable across ticker changes),
timestamped by filing date (post-close), and read as-of through the point-in-time cache.
"""

from __future__ import annotations

import csv
import io
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from data.cache import PointInTimeCache

SOURCE = "insider"
ZIP_URL = "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{y}q{q}_form345.zip"
_EARLY = datetime(2003, 1, 1, tzinfo=UTC)  # Form 345 datasets begin 2006; sentinel below that


def quarters_between(start: datetime, end: datetime) -> list[tuple[int, int]]:
    """Calendar quarters spanning [start, end] inclusive."""
    out: list[tuple[int, int]] = []
    y, q = start.year, (start.month - 1) // 3 + 1
    ey, eq = end.year, (end.month - 1) // 3 + 1
    while (y, q) <= (ey, eq):
        out.append((y, q))
        q += 1
        if q > 4:
            q, y = 1, y + 1
    return out


def _parse_filing_date(s: str) -> datetime | None:
    """SEC DERA dates appear as 'DD-MON-YYYY' or 'YYYY-MM-DD'. Return post-close UTC."""
    s = (s or "").strip()
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d-%B-%Y"):
        try:
            d = datetime.strptime(s, fmt)
            return d.replace(hour=20, tzinfo=UTC)  # conservative post-close
        except ValueError:
            continue
    return None


def parse_quarter_netbuy(
    zip_bytes: bytes, ciks: set[str], *, exclude_10b5_1: bool = True
) -> dict[str, list[dict[str, Any]]]:
    """Per-CIK net-buy events from one quarterly Form-345 zip, restricted to ``ciks``.

    Returns {cik(10-digit): [{"ts", "net_buy"} ...]}, one record per Form-4 accession that
    had any open-market purchase or (non-10b5-1) sale.
    """
    z = zipfile.ZipFile(io.BytesIO(zip_bytes))
    # SUBMISSION: accession → (cik, filing_date, is_10b5_1), Form 4 only.
    sub: dict[str, tuple[str, datetime, bool]] = {}
    with z.open("SUBMISSION.tsv") as f:
        for row in csv.DictReader(io.TextIOWrapper(f, "utf-8", errors="replace"), delimiter="\t"):
            if (row.get("DOCUMENT_TYPE") or "").strip() not in ("4", "4/A"):
                continue
            cik = (row.get("ISSUERCIK") or "").strip().zfill(10)
            if cik not in ciks:
                continue
            fd = _parse_filing_date(row.get("FILING_DATE", ""))
            if fd is None:
                continue
            sub[row["ACCESSION_NUMBER"].strip()] = (
                cik, fd, (row.get("AFF10B5ONE") or "").strip() in ("1", "Y", "true", "True"),
            )
    # NONDERIV_TRANS: aggregate P/S shares per accession.
    agg: dict[str, float] = {}
    with z.open("NONDERIV_TRANS.tsv") as f:
        for row in csv.DictReader(io.TextIOWrapper(f, "utf-8", errors="replace"), delimiter="\t"):
            acc = (row.get("ACCESSION_NUMBER") or "").strip()
            if acc not in sub:
                continue
            code = (row.get("TRANS_CODE") or "").strip().upper()
            if code not in ("P", "S"):
                continue
            try:
                shares = float(row.get("TRANS_SHARES") or 0)
            except ValueError:
                continue
            _, _, is_plan = sub[acc]
            if code == "P":
                agg[acc] = agg.get(acc, 0.0) + shares
            elif code == "S" and not (exclude_10b5_1 and is_plan):
                agg[acc] = agg.get(acc, 0.0) - shares
    out: dict[str, list[dict[str, Any]]] = {}
    for acc, net in agg.items():
        if net == 0.0:
            continue
        cik, fd, _ = sub[acc]
        out.setdefault(cik, []).append({"ts": fd.isoformat(), "net_buy": net})
    return out


class InsiderData:
    """As-of signed insider net-buying per issuer CIK, backed by the point-in-time cache."""

    def __init__(
        self,
        cache: PointInTimeCache,
        *,
        edgar: Any | None,
        fetch_start: datetime,
        fetch_end: datetime,
        ua: str = "",
        cache_dir: str | Path = "data/cache",
        rate_limit_per_sec: float = 8.0,
        exclude_10b5_1: bool = True,
        session: Any | None = None,
    ) -> None:
        self.cache = cache
        self.edgar = edgar
        self.fetch_start = fetch_start
        self.fetch_end = fetch_end
        self.ua = ua
        self.raw_dir = Path(cache_dir) / "insider_raw"
        self.min_interval = 1.0 / rate_limit_per_sec if rate_limit_per_sec > 0 else 0.0
        self.exclude_10b5_1 = exclude_10b5_1
        self.session = session or requests.Session()
        self._last = 0.0
        self._loaded = False

    def _download_quarter(self, y: int, q: int) -> bytes | None:
        path = self.raw_dir / f"{y}q{q}_form345.zip"
        if path.exists():
            return path.read_bytes()
        if self.cache.offline or not self.ua:
            return None
        if self.min_interval:
            wait = self.min_interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
        self._last = time.monotonic()
        resp = self.session.get(ZIP_URL.format(y=y, q=q), headers={"User-Agent": self.ua}, timeout=120)
        if resp.status_code != 200:
            return None
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        path.write_bytes(resp.content)
        return resp.content

    def ensure_loaded(self, symbols: list[str], cik_overrides: dict[str, str] | None = None) -> None:
        """Populate the cache 'insider' source for all symbols' CIKs in one pass over the
        quarterly files (cheaper than per-symbol). Idempotent via cache.covers()."""
        if self._loaded:
            return
        sym_cik = {}
        for s in symbols:
            cik = self.edgar.ticker_to_cik(s, overrides=cik_overrides) if self.edgar else None
            if cik:
                sym_cik[s] = cik
        ciks = set(sym_cik.values())
        # If every CIK already covered, skip the (expensive) parse.
        if ciks and all(self.cache.covers(SOURCE, c, self.fetch_start, self.fetch_end) for c in ciks):
            self._loaded = True
            return
        per_cik: dict[str, list[dict[str, Any]]] = {c: [] for c in ciks}
        for y, q in quarters_between(self.fetch_start, self.fetch_end):
            zb = self._download_quarter(y, q)
            if zb is None:
                continue
            for cik, recs in parse_quarter_netbuy(zb, ciks, exclude_10b5_1=self.exclude_10b5_1).items():
                per_cik[cik].extend(recs)
        if not self.cache.offline:
            for cik, recs in per_cik.items():
                self.cache.write(SOURCE, cik, recs,
                                 coverage_from=self.fetch_start, coverage_through=self.fetch_end)
        self._loaded = True

    def netbuy_asof(self, symbol: str, as_of: datetime,
                    cik_overrides: dict[str, str] | None = None) -> list[dict[str, Any]]:
        cik = self.edgar.ticker_to_cik(symbol, overrides=cik_overrides) if self.edgar else None
        if cik is None:
            return []
        try:
            return self.cache.read(SOURCE, cik, as_of)
        except Exception:  # noqa: BLE001 — no insider coverage for this name → empty
            return []
