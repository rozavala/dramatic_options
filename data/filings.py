"""EDGAR filings adapter (plan §B5) — the substance/delivery source.

Keyless SEC access over HTTPS with a polite, contact-identifying User-Agent and a rate
limiter (SEC asks for < 10 req/s). Identity is resolved by **CIK** (stable) rather than
ticker, so de-SPAC ticker changes don't break early-period attribution — once we have a
company's CIK, the submissions API returns *all* its filings regardless of ticker history.

Filings are timestamped by **``acceptanceDateTime``** (the instant a filing becomes public,
often intraday after 16:00 ET), NOT the ``filingDate`` — using the date would leak ~hours
of lookahead (plan no-lookahead contract, item 2).

v1 substance uses the reliable submissions-index events (8-K item codes, 13D/G, S-1/424B,
Form-4 presence). Two richer signals are scaffolded as documented upgrade hooks but **not
wired** into v1: :func:`form4_net_shares` (insider buy/sell direction — the designated first
iteration knob) and a 10-K/Q SHA-256 section diff.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import requests

from data.cache import PointInTimeCache

SOURCE = "filings"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SUBMISSIONS_FILE_URL = "https://data.sec.gov/submissions/{name}"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"


def _to_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


class EdgarClient:
    """Low-level EDGAR HTTP with UA, rate limiting, and a static ticker→CIK map."""

    def __init__(
        self,
        user_agent: str,
        *,
        cache_dir: str | Path = "data/cache",
        rate_limit_per_sec: float = 8.0,
        session: Any | None = None,
    ) -> None:
        if not user_agent:
            raise ValueError(
                "EDGAR requires a contact User-Agent. Set EDGAR_USER_AGENT in .env "
                "(e.g. 'dramatic-options you@example.com')."
            )
        self.ua = user_agent
        self.min_interval = 1.0 / rate_limit_per_sec if rate_limit_per_sec > 0 else 0.0
        self.edgar_dir = Path(cache_dir) / "edgar"
        self.session = session or requests.Session()
        self._last_call = 0.0
        self._ticker_map: dict[str, str] | None = None

    def _throttle(self) -> None:
        if self.min_interval:
            wait = self.min_interval - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
        self._last_call = time.monotonic()

    def _get_json(self, url: str) -> Any:
        self._throttle()
        resp = self.session.get(url, headers={"User-Agent": self.ua}, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _get_text(self, url: str) -> str:
        self._throttle()
        resp = self.session.get(url, headers={"User-Agent": self.ua}, timeout=30)
        resp.raise_for_status()
        return resp.text

    # ── ticker → CIK ───────────────────────────────────────────────────────
    def ticker_to_cik(self, ticker: str, *, overrides: dict[str, str] | None = None) -> str | None:
        """Resolve a ticker to a zero-padded 10-digit CIK. ``overrides`` wins (for names
        not in the current map / historical ticker changes)."""
        ticker = ticker.upper()
        if overrides and ticker in overrides:
            return str(overrides[ticker]).zfill(10)
        if self._ticker_map is None:
            self._ticker_map = self._load_ticker_map()
        return self._ticker_map.get(ticker)

    def _load_ticker_map(self) -> dict[str, str]:
        path = self.edgar_dir / "company_tickers.json"
        if path.exists():
            raw = json.loads(path.read_text())
        else:
            raw = self._get_json(TICKERS_URL)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(raw))
        out: dict[str, str] = {}
        for row in raw.values():
            out[str(row["ticker"]).upper()] = str(row["cik_str"]).zfill(10)
        return out

    # ── submissions → normalized filing records ─────────────────────────────
    def fetch_filings(self, cik: str) -> list[dict[str, Any]]:
        """All filings for a CIK as normalized records (recent + any older index files)."""
        cik = str(cik).zfill(10)
        sub = self._get_json(SUBMISSIONS_URL.format(cik=cik))
        records: list[dict[str, Any]] = []
        recent = sub.get("filings", {}).get("recent", {})
        records.extend(_normalize_filing_block(recent, cik))
        for f in sub.get("filings", {}).get("files", []):
            name = f.get("name")
            if name:
                records.extend(_normalize_filing_block(self._get_json(
                    SUBMISSIONS_FILE_URL.format(name=name)), cik))
        return records

    def fetch_form4_doc(self, cik: str, accession: str, primary_document: str) -> str:
        """Fetch the primary document (XML) for a Form 4 filing (upgrade hook)."""
        acc = accession.replace("-", "")
        return self._get_text(
            ARCHIVES_URL.format(cik=str(int(cik)), acc=acc, doc=primary_document)
        )


def _normalize_filing_block(block: dict[str, list], cik: str) -> list[dict[str, Any]]:
    """Turn EDGAR's column-array filing block into per-filing records, timestamped by
    acceptanceDateTime (falling back to filingDate + 16:00 ET ≈ 20:00 UTC if absent)."""
    forms = block.get("form", [])
    out: list[dict[str, Any]] = []
    for i, form in enumerate(forms):
        acc_dt = (block.get("acceptanceDateTime") or [None] * len(forms))[i]
        if acc_dt:
            ts = _to_utc(datetime.fromisoformat(acc_dt.replace("Z", "+00:00"))).isoformat()
        else:
            fdate = (block.get("filingDate") or [None] * len(forms))[i]
            if not fdate:
                continue
            ts = f"{fdate}T20:00:00+00:00"  # conservative post-close fallback
        items_raw = (block.get("items") or [""] * len(forms))[i] or ""
        out.append(
            {
                "ts": ts,
                "form": form,
                "items": [s.strip() for s in items_raw.split(",") if s.strip()],
                "accession": (block.get("accessionNumber") or [""] * len(forms))[i],
                "primary_document": (block.get("primaryDocument") or [""] * len(forms))[i],
                "cik": cik,
            }
        )
    return out


class FilingsData:
    """As-of filing events for the universe, backed by the point-in-time cache."""

    def __init__(
        self,
        cache: PointInTimeCache,
        *,
        edgar: EdgarClient | None = None,
        fetch_end: datetime,
        cik_overrides: dict[str, str] | None = None,
    ) -> None:
        self.cache = cache
        self.edgar = edgar
        self.fetch_end = fetch_end
        self.cik_overrides = cik_overrides or {}

    def _cik(self, symbol: str) -> str | None:
        if self.edgar is None:
            # offline: derive cik from overrides only (tests inject these)
            ov = self.cik_overrides.get(symbol.upper())
            return str(ov).zfill(10) if ov else None
        return self.edgar.ticker_to_cik(symbol, overrides=self.cik_overrides)

    def _ensure(self, symbol: str) -> None:
        if self.cache.has_coverage(SOURCE, symbol, self.fetch_end):
            return
        if self.edgar is None:
            return
        cik = self._cik(symbol)
        if cik is None:
            # Record an empty payload so we don't refetch a name with no CIK every time.
            self.cache.write(SOURCE, symbol, [], coverage_through=self.fetch_end)
            return
        records = self.edgar.fetch_filings(cik)
        self.cache.write(SOURCE, symbol, records, coverage_through=self.fetch_end)

    def filings_asof(self, symbol: str, as_of: datetime) -> list[dict[str, Any]]:
        """Filing event records with ``acceptanceDateTime <= as_of``, ascending."""
        self._ensure(symbol)
        return self.cache.read(SOURCE, symbol, as_of)


# ── upgrade hooks (scaffolded, NOT wired into v1 substance) ──────────────────
def form4_net_shares(form4_xml: str) -> float:
    """Net open-market shares (purchases − sales) from a Form 4 ownership XML.

    The designated first iteration knob (plan §B5): replaces Form-4 *presence* with signed
    insider *direction*, and lets 10b5-1 automated sales be filtered. Best-effort; returns
    0.0 if the document can't be parsed.
    """
    try:
        root = ET.fromstring(form4_xml)
    except ET.ParseError:
        return 0.0
    net = 0.0
    for txn in root.iter("nonDerivativeTransaction"):
        code_el = txn.find(".//transactionCoding/transactionCode")
        shares_el = txn.find(".//transactionAmounts/transactionShares/value")
        if code_el is None or shares_el is None:
            continue
        try:
            shares = float(shares_el.text)
        except (TypeError, ValueError):
            continue
        code = (code_el.text or "").strip().upper()
        if code == "P":
            net += shares
        elif code == "S":
            net -= shares
    return net


def section_sha256(text: str) -> str:
    """SHA-256 of normalized text — for the deferred 10-K/Q year-over-year section diff."""
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()
