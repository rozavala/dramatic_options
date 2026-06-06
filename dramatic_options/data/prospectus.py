"""424B5 prospectus deal-size extractor (FSSD plan §8b, #3 — recall-measured, best-effort).

The supply-shock *magnitude* (shares offered ÷ float) is arguably the core FSSD variable, but
it lives in the free-text prospectus supplement (heterogeneous HTML/text), so extraction is
**best-effort with imperfect recall** — which is exactly why the audit *measures* recall against
``deal_size.min_recall`` and cross-checks against the deterministic XBRL shares-out delta
(:func:`data.shares_out.shares_out_delta`). If neither path clears the recall floor, size-
conditioning is dropped for v1 and friction carries the gate (PREREG §3).

Pure parsing here (``parse_offering_size``) so it is offline-testable on fixtures; the fetch
side reuses :class:`data.filings.EdgarClient` HTTP discipline. No returns computed.
"""

from __future__ import annotations

import re
from typing import Any

# "12,500,000 shares" / "up to 4,000,000 shares of common stock"
_SHARES = re.compile(
    r"(?:up to\s+)?([0-9][0-9,]{3,})\s+shares\s+of\s+(?:our\s+)?common\s+stock",
    re.IGNORECASE,
)
# "$15.00 per share" / "public offering price of $7.25 per share"
_PRICE = re.compile(r"\$\s*([0-9]+(?:\.[0-9]{1,4})?)\s*per\s+share", re.IGNORECASE)
# "aggregate offering price of $50,000,000" / "gross proceeds of $25.0 million"
_GROSS = re.compile(
    r"(?:aggregate offering price|gross proceeds|aggregate principal amount)[^$]{0,40}"
    r"\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(million|billion)?",
    re.IGNORECASE,
)


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def parse_offering_size(text: str) -> dict[str, Any] | None:
    """Best-effort {shares, price, gross_usd} from prospectus text, or None if nothing found.

    Recall over precision (the audit only needs presence/absence to score recall): takes the
    first plausible shares count and per-share price near the top of the document; computes
    gross = shares×price when both present, else falls back to an explicit aggregate/gross line.
    """
    head = text[:200_000]  # the cover/summary carries the terms; cap work on huge filings
    shares = price = gross = None

    m = _SHARES.search(head)
    if m:
        shares = _num(m.group(1))
    m = _PRICE.search(head)
    if m:
        price = _num(m.group(1))
    if shares is not None and price is not None:
        gross = shares * price
    else:
        mg = _GROSS.search(head)
        if mg:
            val = _num(mg.group(1))
            scale = {"million": 1e6, "billion": 1e9}.get((mg.group(2) or "").lower(), 1.0)
            gross = val * scale

    if shares is None and price is None and gross is None:
        return None
    return {"shares": shares, "price": price, "gross_usd": gross}


def offering_vs_float(shares: float | None, shares_out: float | None) -> float | None:
    """Offered shares as a fraction of shares outstanding (the supply-shock magnitude). None if
    either is missing or shares_out ≤ 0."""
    if shares is None or shares_out is None or shares_out <= 0:
        return None
    return shares / shares_out
