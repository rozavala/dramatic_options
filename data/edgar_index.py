"""EDGAR full-index 424B5 event enumerator (FSSD plan §8a — see PREREG_FSSD.md).

Builds the **survivorship-clean** population of registered secondary-offering events
(424B5 prospectus supplements) over a date window from EDGAR's **quarterly full-index**
``form.idx`` files. The full-index lists every dissemination-feed filing for the quarter,
*including issuers that later delisted*, so the enumerated event set is unbiased — unlike
a list built from today's tickers, which would silently drop the names most likely to have
been forced sellers (plan §4, §8a).

Quarterly (≈24 files for 2019-24), not daily (~1500): identical rows, ~60× fewer fetches.

Coverage-only / no-lookahead notes:
  - The full-index is *filing-date* granular (no intraday acceptance time), so events are
    timestamped at a conservative **post-close 20:00 UTC** of the filing date. 8b upgrades
    entry timing to ``acceptanceDateTime`` (via the submissions API) where needed.
  - This module computes **no returns** — it only enumerates events (plan §8a).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from data.cache import PointInTimeCache
from data.insider import quarters_between

SOURCE = "fssd_events"

# Row: "424B5   COMPANY NAME ...   CIK   YYYY-MM-DD   edgar/data/CIK/ACCESSION.txt"
# (full-index is space-padded fixed-ish; anchor on the digit-run CIK, ISO date, and the
# edgar/ path so company names containing digits/spaces don't break the parse.)
_ROW = re.compile(
    r"^(?P<form>\S+)\s+(?P<company>.+?)\s+(?P<cik>\d+)\s+"
    r"(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<path>edgar/\S+?)\s*$"
)


def _ts_postclose(date_filed: str) -> str:
    """Filing date → conservative post-close UTC instant (no acceptance time in the index)."""
    return f"{date_filed}T20:00:00+00:00"


def _accession_from_path(path: str) -> str:
    """'edgar/data/899629/0001104659-22-028897.txt' → '0001104659-22-028897'."""
    return path.rsplit("/", 1)[-1].removesuffix(".txt")


def parse_form_index(text: str, *, form: str = "424B5") -> list[dict[str, Any]]:
    """Parse one quarterly ``form.idx`` into normalized event records for ``form``.

    Returns ``{ts, cik, company, accession, file, date_filed}`` per matching row. Pure /
    offline-testable: no I/O. Rows that don't match the expected layout are skipped.
    """
    out: list[dict[str, Any]] = []
    for line in text.splitlines():
        # fast reject: the form type is the first token on the line
        if not line.startswith(form):
            continue
        m = _ROW.match(line)
        if m is None or m.group("form") != form:
            continue
        cik = m.group("cik").zfill(10)
        path = m.group("path")
        date_filed = m.group("date")
        out.append(
            {
                "ts": _ts_postclose(date_filed),
                "cik": cik,
                "company": m.group("company").strip(),
                "accession": _accession_from_path(path),
                "file": path,
                "date_filed": date_filed,
                "form": form,
            }
        )
    return out


class EdgarIndex:
    """Enumerate 424B5 events from the quarterly full-index, with disk + point-in-time cache.

    Raw quarterly index text is cached under ``<cache_dir>/full_index_raw/`` (one file per
    quarter) so reruns are network-free; the deduped, windowed event list is written to the
    point-in-time cache (``source='fssd_events'``) for 8b's as-of reads.
    """

    def __init__(
        self,
        cache: PointInTimeCache,
        *,
        edgar: Any | None,
        cache_dir: str | Path = "data/cache",
        form: str = "424B5",
        source: str = SOURCE,
    ) -> None:
        self.cache = cache
        self.edgar = edgar
        self.form = form
        # The PIT-cache namespace. Defaults to the FSSD ``fssd_events`` (back-compat for the
        # parked Stage-1 harness); the Stage-0 corpus passes its own (``corpus_capital_raises``)
        # so corpus filings never share/collide with the FSSD enumeration.
        self.source = source
        self.raw_dir = Path(cache_dir) / "full_index_raw"

    def _quarter_text(self, year: int, quarter: int) -> str | None:
        path = self.raw_dir / f"{year}q{quarter}_form.idx"
        if path.exists():
            return path.read_text(encoding="latin-1")
        if self.edgar is None or self.cache.offline:
            return None
        text = self.edgar.fetch_form_index(year, quarter)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="latin-1")
        return text

    def enumerate_events(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        """All ``form`` events with ``start <= filing date <= end``, deduped by accession.

        Walks the quarters spanning [start, end], parsing each quarter's full-index. Results
        are cached to the point-in-time cache keyed by ``form`` (ts = post-close filing date),
        so a later as-of read in 8b is deterministic.
        """
        key = self.form
        lo, hi = start.date().isoformat(), end.date().isoformat()
        # Reuse a prior (possibly wider) enumeration if it already spans this window. Filter
        # on date_filed with the SAME inclusive string bounds as the fresh path below, so the
        # two code paths return byte-identical event sets (determinism is the cache's whole
        # point — a boundary-day post-close event must not appear/vanish by which path ran).
        if self.cache.covers(self.source, key, start, end):
            ct = self.cache.coverage_through(self.source, key)
            recs = self.cache.read_between(self.source, key, None, ct) if ct else []
            return [r for r in recs if lo <= r["date_filed"] <= hi]

        seen: set[str] = set()
        events: list[dict[str, Any]] = []
        for year, quarter in quarters_between(start, end):
            text = self._quarter_text(year, quarter)
            if text is None:
                continue
            for rec in parse_form_index(text, form=self.form):
                if not (lo <= rec["date_filed"] <= hi):
                    continue
                if rec["accession"] in seen:
                    continue
                seen.add(rec["accession"])
                events.append(rec)
        events.sort(key=lambda r: r["ts"])
        if not self.cache.offline and events:
            self.cache.write(
                self.source, key, events,
                coverage_from=start, coverage_through=end,
            )
        return events


def month_key(ts: str) -> str:
    """ISO 'YYYY-MM' calendar-month bucket for a record ts (the FSSD resampling unit)."""
    return datetime.fromisoformat(ts).astimezone(UTC).strftime("%Y-%m")
