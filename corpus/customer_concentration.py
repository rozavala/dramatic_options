"""Stage-0 corpus — 10-K customer-concentration disclosures, the second-order-dependency surface.

Part of the deterministic theme-generation corpus (``PREREG_THEME_GENERATION_STUB`` Stage 0; the
``PREREG_UNIVERSE_CURATION`` §4 ">10%-customer disclosures" seed source). When a filer derives a
large share of revenue (or receivables) from one/few customers, that is a structural SECOND-ORDER
signal — a supplier's fortunes ride a big customer's theme. Reg S-K / ASC 280 require disclosing any
customer ≥10% of revenue.

**Why text, not XBRL (verified live 2026-06-17):** the concentration concept
``us-gaap:ConcentrationRiskPercentage1`` is ALWAYS reported with dimensional context (customer /
benchmark / type axes), and the structured SEC APIs drop dimensionally-qualified facts — companyfacts
returns NOTHING for famous concentration filers (CRUS/SWKS/QRVO/AAOI), and the frames API returns one
irrelevant filer. So the disclosure lives only in the 10-K NARRATIVE. This adapter does deterministic
TEXT extraction (regex over the stripped primary document) — a structural disclosure (a disclosed
percentage), NOT prices/IV/momentum/news-sentiment (the §2 prohibition; this module imports no market
source).

PIT: each record carries the 10-K's filing ``ts`` (acceptanceDateTime via ``FilingsData``), so an
as-of read surfaces a concentration disclosure exactly when its 10-K became public. v1 extracts the
latest full BASE 10-K per name (a newer 10-K/A amendment is often partial — Part III only, no
financials — so it must not shadow the base filing; forward-corpus, historical 10-Ks are a future
enhancement) and the NARRATIVE prose only. Known v1 misses (recall, never precision): table-formatted
concentration, and disclosures attributing the % to a NAMED customer without the literal "customer"
token near it (deterministic named-entity extraction is too noisy for a no-LLM Stage-0 corpus).
"""

from __future__ import annotations

import html
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from data.cache import PointInTimeCache
from data.filings import FilingsData

SOURCE = "corpus_customer_concentration"
_EARLY = datetime(1990, 1, 1, tzinfo=UTC)
DEFAULT_FORMS: tuple[str, ...] = ("10-K", "10-K/A")

_PCT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")
_CUSTOMER = re.compile(r"customers?", re.I)
_BENCH_REVENUE = re.compile(r"\b(net sales|revenues?|sales)\b", re.I)
_BENCH_AR = re.compile(r"\b(accounts receivable|receivables?)\b", re.I)
# Standard NEGATIVE disclosures ("no single customer accounted for more than 10%…") — these mean the
# OPPOSITE of concentration and must not be recorded as a positive signal.
_NEGATIVE = re.compile(
    r"\b(?:no|none of|not any|fewer than)\b[^.]{0,60}customer"
    r"|customer[^.]{0,40}(?:did not exceed|not exceed|no more than|less than|under \d)",
    re.I,
)
_NUMWORD = {"a": 1, "an": 1, "one": 1, "single": 1, "two": 2, "three": 3, "four": 4, "five": 5}
_COUNT = re.compile(r"\b(a|an|one|single|two|three|four|five|\d{1,2})\b\s+(?:[a-z]+\s+){0,2}customers?", re.I)


def strip_html(raw: str) -> str:
    """HTML/inline-XBRL document → normalized plain text (script/style dropped, entities unescaped)."""
    raw = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", raw)
    txt = re.sub(r"(?s)<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(txt)).strip()


def extract_concentration(text: str, *, min_pct: float = 10.0) -> list[dict[str, Any]]:
    """Pure: customer-concentration disclosures from a 10-K's plain text.

    Sentence scan keeping sentences that mention a customer AND a revenue/sales/receivables benchmark
    AND a percentage ≥ ``min_pct`` (the disclosure threshold), excluding the standard negative
    disclosures. Returns ``{percentage, benchmark, n_customers, snippet}`` per distinct disclosure,
    revenue benchmark preferred when both appear. Pure / offline-testable."""
    out: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for sent in re.split(r"(?<=[.;])\s+", text):
        if len(sent) > 600 or not _CUSTOMER.search(sent):  # skip table-blobs / non-customer text
            continue
        rev, ar = bool(_BENCH_REVENUE.search(sent)), bool(_BENCH_AR.search(sent))
        if not (rev or ar) or _NEGATIVE.search(sent):
            continue
        pcts = [float(p) for p in _PCT.findall(sent) if min_pct <= float(p) <= 100.0]
        if not pcts:
            continue
        pct = max(pcts)
        benchmark = "revenue" if rev else "accounts_receivable"
        n_customers = None
        cm = _COUNT.search(sent)
        if cm:
            tok = cm.group(1).lower()
            n_customers = _NUMWORD.get(tok) or (int(tok) if tok.isdigit() else None)
        snippet = " ".join(sent.split())[:300]
        key = (round(pct, 2), benchmark, snippet[:60])
        if key in seen:
            continue
        seen.add(key)
        out.append({"percentage": pct, "benchmark": benchmark,
                    "n_customers": n_customers, "snippet": snippet})
    return out


class CustomerConcentration:
    """As-of customer-concentration disclosures per name, backed by the point-in-time cache.

    Resolves the latest 10-K (via ``FilingsData``), fetches its primary document (raw HTML cached on
    disk for network-free re-extraction), and extracts the narrative concentration disclosures. The
    extracted records are stored point-in-time at the 10-K's filing ts. **Fail-soft:** no edgar client
    / offline / a fetch error → ``[]`` (never raises into the scheduled assembly)."""

    def __init__(
        self,
        cache: PointInTimeCache,
        *,
        edgar: Any | None,
        fetch_end: datetime,
        cache_dir: str | Path = "data/cache",
        forms: tuple[str, ...] = DEFAULT_FORMS,
        min_pct: float = 10.0,
        cik_overrides: dict[str, str] | None = None,
    ) -> None:
        self.cache = cache
        self.edgar = edgar
        self.fetch_end = fetch_end
        self.filings = FilingsData(cache, edgar=edgar, fetch_end=fetch_end,
                                   cik_overrides=cik_overrides)
        self.forms = set(forms)
        self.min_pct = min_pct
        self.raw_dir = Path(cache_dir) / "tenk_raw"

    def _latest_10k(self, symbol: str) -> dict[str, Any] | None:
        """The latest full BASE 10-K (≤ fetch_end), falling back to an amendment only if no base
        10-K exists. A newer 10-K/A is often PARTIAL (e.g. Part III only — no financials, hence no
        concentration note), so it must not shadow the complete base 10-K (the SWKS case)."""
        try:
            recs = self.filings.filings_asof(symbol, self.fetch_end)
        except Exception:  # noqa: BLE001 — no coverage / no cik → no 10-K
            return None

        def latest(form_set: set[str]) -> dict[str, Any] | None:
            cand = [r for r in recs
                    if str(r.get("form", "")) in form_set and r.get("primary_document")]
            return max(cand, key=lambda r: r.get("ts", "")) if cand else None

        base = {f for f in self.forms if not f.endswith("/A")}
        return latest(base) or latest(self.forms)

    def _fetch_doc(self, cik: str, accession: str, primary_document: str) -> str | None:
        """Raw 10-K primary document (disk-cached). ``None`` on a transient failure (so it is not
        cached as a false empty); the edgar client carries the SEC UA + throttle."""
        raw_path = self.raw_dir / f"{accession}.html"
        if raw_path.exists():
            return raw_path.read_text(encoding="utf-8", errors="ignore")
        if self.edgar is None or self.cache.offline:
            return None
        try:
            doc = self.edgar.fetch_document(cik, accession, primary_document)
        except Exception:  # noqa: BLE001 — transient fetch error → refetch next run
            return None
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(doc, encoding="utf-8")
        return doc

    def ensure_loaded(self, symbol: str) -> None:
        if self.cache.covers(SOURCE, symbol.upper(), _EARLY, self.fetch_end):
            return
        tenk = self._latest_10k(symbol)
        if tenk is None:
            if not self.cache.offline:  # cache an empty so a name with no 10-K isn't refetched
                self.cache.write(SOURCE, symbol.upper(), [], coverage_from=_EARLY,
                                 coverage_through=self.fetch_end)
            return
        doc = self._fetch_doc(tenk["cik"], tenk["accession"], tenk["primary_document"])
        if doc is None:
            return  # transient fetch failure — leave uncached so a later run retries
        recs = [
            {"ts": tenk["ts"], "cik": tenk["cik"], "accession": tenk["accession"],
             "form": tenk["form"], **c}
            for c in extract_concentration(strip_html(doc), min_pct=self.min_pct)
        ]
        if not self.cache.offline:
            self.cache.write(SOURCE, symbol.upper(), recs, coverage_from=_EARLY,
                             coverage_through=self.fetch_end)

    def concentration_asof(self, symbol: str, as_of: datetime) -> list[dict[str, Any]]:
        """Customer-concentration disclosures public as of ``as_of`` (by the 10-K's filing ts)."""
        self.ensure_loaded(symbol)
        try:
            return self.cache.read(SOURCE, symbol.upper(), as_of)
        except Exception:  # noqa: BLE001 — no coverage for this name → empty
            return []
