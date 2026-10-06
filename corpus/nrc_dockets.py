"""Stage-0 corpus — NRC power-reactor units (the nuclear fleet/docket surface).

Part of the deterministic theme-generation corpus (``PREREG_THEME_GENERATION_STUB`` Stage 0; the
``PREREG_UNIVERSE_CURATION`` §4 "NRC dockets" seed source). The operating-reactor fleet (units,
dockets, licensees, reactor type) is structural context for the nuclear theme — which operators run
which reactors, where, and the fleet's composition.

Source: the NRC "List of Power Reactor Units" HTML table
(``nrc.gov/reactors/operating/list-power-reactor-units``) — a stable scrapeable table (the ADAMS
document API needs per-query param construction, and the new-reactor/SMR licensing pages have moved;
those richer docket feeds are a future enhancement). Records are STRUCTURAL only — name, docket,
license, reactor type, location, operator, NRC region (no prices/IV/momentum/sentiment, the §2
prohibition; this module imports no market source).

PIT: the list is a current snapshot with no per-row date, so each record is stamped at the pull's
``fetch_end`` (the as-of high-water); the fleet changes only over years.
"""

from __future__ import annotations

import html
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from data.cache import PointInTimeCache

SOURCE = "corpus_nrc_dockets"
KEY = "power_reactors"
REACTOR_LIST_URL = "https://www.nrc.gov/reactors/operating/list-power-reactor-units"
_EARLY = datetime(1990, 1, 1, tzinfo=UTC)
_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
       "Chrome/120.0 Safari/537.36")


def _celltext(cell_html: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", cell_html))).strip()


def parse_reactor_list(html_text: str, *, as_of_ts: str) -> list[dict[str, Any]]:
    """Pure: the NRC reactor-list HTML → structural reactor records, stamped at ``as_of_ts``.

    The first table cell is ``"<Plant Name> <Docket>"`` (e.g. ``"Arkansas Nuclear 1 05000313"``) —
    the trailing digit-run is the docket. The header row (no trailing docket digits) is skipped, so
    no fragile header-text matching. Pure / offline-testable."""
    m = re.search(r"(?is)<table.*?</table>", html_text)
    if not m:
        return []
    out: list[dict[str, Any]] = []
    for row in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", m.group(0)):
        cells = [_celltext(c) for c in re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", row)]
        if len(cells) < 6:
            continue
        dm = re.search(r"(\d{6,})\s*$", cells[0])
        if dm is None:  # header row / no docket → skip
            continue
        out.append({
            "ts": as_of_ts, "name": cells[0][:dm.start()].strip(), "docket": dm.group(1),
            "license": cells[1], "reactor_type": cells[2], "location": cells[3],
            "operator": cells[4], "region": cells[5],
        })
    return out


class NRCReactors:
    """As-of NRC power-reactor units, backed by the point-in-time cache (one snapshot list).

    Mirrors the other corpus adapters: raw HTML cached on disk (network-free re-parse), parsed records
    in the point-in-time cache, fail-soft (offline / fetch error / no table → ``[]``)."""

    def __init__(
        self,
        cache: PointInTimeCache,
        *,
        fetch_end: datetime,
        session: Any | None = None,
        cache_dir: str | Path = "data/cache",
        ua: str = _UA,
        rate_limit_per_sec: float = 2.0,
    ) -> None:
        self.cache = cache
        self.fetch_end = fetch_end
        self.session = session or requests.Session()
        self.ua = ua
        self.min_interval = 1.0 / rate_limit_per_sec if rate_limit_per_sec > 0 else 0.0
        self.raw_dir = Path(cache_dir) / "nrc_raw"
        self._last = 0.0

    def _fetch(self) -> str | None:
        """Raw reactor-list HTML (disk-cached). ``None`` on a transient failure."""
        raw_path = self.raw_dir / f"{KEY}.html"
        if raw_path.exists():
            return raw_path.read_text(encoding="utf-8", errors="ignore")
        if self.cache.offline:
            return None
        try:
            if self.min_interval:
                wait = self.min_interval - (time.monotonic() - self._last)
                if wait > 0:
                    time.sleep(wait)
            self._last = time.monotonic()
            resp = self.session.get(REACTOR_LIST_URL, headers={"User-Agent": self.ua}, timeout=30)
        except Exception:  # noqa: BLE001 — transient network error → refetch next run
            return None
        if resp.status_code != 200:
            return None
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        resp_text = resp.text
        raw_path.write_text(resp_text, encoding="utf-8")
        return resp_text

    def ensure_loaded(self) -> None:
        if self.cache.covers(SOURCE, KEY, _EARLY, self.fetch_end):
            return
        doc = self._fetch()
        if doc is None:
            return  # transient — leave uncached so a later run retries
        recs = parse_reactor_list(doc, as_of_ts=self.fetch_end.isoformat())
        if not self.cache.offline:
            self.cache.write(SOURCE, KEY, recs, coverage_from=_EARLY, coverage_through=self.fetch_end)

    def reactors_asof(self, as_of: datetime) -> list[dict[str, Any]]:
        """NRC power-reactor units public as of ``as_of`` (the snapshot's pull time)."""
        self.ensure_loaded()
        try:
            return self.cache.read(SOURCE, KEY, as_of)
        except Exception:  # noqa: BLE001 — no coverage → empty
            return []
