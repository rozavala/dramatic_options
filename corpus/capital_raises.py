"""Stage-0 corpus — capital-raise filings (424B5 / S-1), the small-cap capital-formation surface.

Part of the deterministic theme-generation corpus (``PREREG_THEME_GENERATION_STUB`` Stage 0; the
``PREREG_UNIVERSE_CURATION`` §4 "424B5/S-1 flows" seed source). Reuses the FSSD EDGAR full-index
enumerator (``data.edgar_index.EdgarIndex``) over the quarterly ``form.idx`` — survivorship-clean
(includes later-delisted issuers) and point-in-time (filings timestamped conservative post-close).

Records are STRUCTURAL filing metadata only — issuer, CIK, form, filing date, accession, path. NO
prices / IV / momentum / news-sentiment (the §2 prohibition; this module imports no market source).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from data.cache import PointInTimeCache
from data.edgar_index import EdgarIndex

# 424B5 = registered-secondary prospectus supplement (capital raise by an existing issuer);
# S-1 = the initial registration. Exact form match (S-1/A amendments are excluded by the parser).
FORMS: tuple[str, ...] = ("424B5", "S-1")
SOURCE = "corpus_capital_raises"


def enumerate_capital_raises(
    start: datetime,
    end: datetime,
    *,
    edgar: Any | None,
    cache: PointInTimeCache,
    cache_dir: str | Path = "data/cache",
) -> list[dict[str, Any]]:
    """424B5 + S-1 filings with ``start <= filing date <= end``, deduped within form (by accession)
    and sorted by ``(date_filed, form, accession)`` for a deterministic corpus slice.

    Each record is the ``EdgarIndex`` structural row ``{ts, cik, company, accession, file,
    date_filed, form}`` — no prices (§2). **Fail-soft:** ``edgar=None`` / an offline cache yields
    ``[]`` (``EdgarIndex`` returns no events when it can neither fetch nor read), never raising — a
    corpus-source hiccup must not break the scheduled assembly.
    """
    out: list[dict[str, Any]] = []
    for form in FORMS:
        idx = EdgarIndex(cache, edgar=edgar, cache_dir=cache_dir, form=form)
        out.extend(idx.enumerate_events(start, end))
    out.sort(key=lambda r: (r["date_filed"], r["form"], r["accession"]))
    return out
