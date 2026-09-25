"""Stale-fundamentals flag (issue #269) — TELEMETRY ONLY.

Names the council's context pack or the direction-coherence rule judged on an **older quarter than the
company's latest filed periodic report**. Found by hand on 2026-09-25: NEE was read on its Q1 2026 figures
(filed 2026-04-23) although it filed its Q2 10-Q on 2026-07-24, because SEC's companyfacts never received the
Q2 facts. The loop's cache refresh cannot fix an upstream gap; this makes the gap visible every night.

Test (per name whose corpus was read this cycle): a name is **lagging** when the newest 10-Q / 10-K / 20-F /
40-F on EDGAR was filed AFTER the newest filing its corpus lines reflect, and more than ``GRACE_DAYS`` before
the run (a processing-lag allowance for SEC's structured data — not a tuned threshold). Amendments do not count
as a new period.

Discipline: never changes the context pack, never changes a rule verdict, never segments the record; fail-soft
(a check error is counted, never raised into the cycle). Import-light: the dashboard imports ``parse_summary``,
so the EDGAR client is imported lazily inside :func:`check_cycle` only.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

PERIODIC_FORMS = frozenset({"10-Q", "10-K", "20-F", "40-F"})
GRACE_DAYS = 3
PREFIX = "fundamentals-staleness:"


def newest_corpus_filed(lines: Iterable[dict] | None) -> str | None:
    """The newest filing date (YYYY-MM-DD) any corpus line reflects; ``None`` when there are no dated lines."""
    dates = [str(ln["filed"])[:10] for ln in lines or () if isinstance(ln, dict) and ln.get("filed")]
    return max(dates) if dates else None


def newest_periodic(records: Iterable[dict] | None) -> tuple[str, str] | None:
    """``(form, YYYY-MM-DD)`` of the newest periodic report among filing records. Amendments are excluded."""
    best: tuple[str, str] | None = None
    for r in records or ():
        form = str(r.get("form", "")).upper()
        if form not in PERIODIC_FORMS:
            continue
        day = str(r.get("ts", ""))[:10]
        if day and (best is None or day > best[1]):
            best = (form, day)
    return best


def is_lagging(corpus_filed: str | None, periodic: tuple[str, str] | None, now: datetime,
               *, grace_days: int = GRACE_DAYS) -> bool:
    """A newer periodic report exists than the corpus reflects, filed more than ``grace_days`` before ``now``."""
    if not corpus_filed or not periodic:
        return False
    _form, filed = periodic
    if filed <= corpus_filed:
        return False
    return filed <= (now - timedelta(days=grace_days)).date().isoformat()


@dataclass
class StalenessCheck:
    lines_of: Callable[[str], list[dict] | None]
    filings_of: Callable[[str], list[dict] | None]
    lagging: dict[str, dict] = field(default_factory=dict)
    checked: int = 0
    no_corpus: list[str] = field(default_factory=list)
    errors: int = 0

    def run(self, symbols: Iterable[str], now: datetime) -> StalenessCheck:
        for sym in sorted({str(s).upper() for s in symbols}):
            try:
                corpus_filed = newest_corpus_filed(self.lines_of(sym))
                if corpus_filed is None:
                    self.no_corpus.append(sym)
                    continue
                periodic = newest_periodic(self.filings_of(sym))
                self.checked += 1
                if is_lagging(corpus_filed, periodic, now):
                    self.lagging[sym] = {"corpus_filed": corpus_filed, "form": periodic[0], "filed": periodic[1]}
            except Exception as e:  # noqa: BLE001 — telemetry: a failed check is counted, never raised
                self.errors += 1
                log.warning("fundamentals-staleness: check failed for %s (skipped): %s", sym, e)
        return self

    def summary(self) -> str:
        items = ", ".join(f"{s}(corpus {v['corpus_filed']} < {v['form']} {v['filed']})"
                          for s, v in sorted(self.lagging.items()))
        return (f"{PREFIX} lagging=[{items}] checked={self.checked} "
                f"no_corpus={len(self.no_corpus)} errors={self.errors}")


def symbols_read_this_cycle(conn, run_id: int | None, coherence=None) -> set[str]:
    """This run's council proposals plus every name the direction rule examined — the names whose corpus the
    loop actually read (so a cache file that is merely old, and unread, is never flagged)."""
    out: set[str] = set()
    if conn is not None and run_id is not None:
        out |= {str(r[0]).upper() for r in conn.execute(
            "SELECT DISTINCT symbol FROM council_proposals WHERE run_id = ?", (run_id,))}
    if coherence is not None:
        out |= {s for (s, _d) in getattr(coherence, "withheld", {})}
        out |= set(getattr(coherence, "kept", []) or []) | set(getattr(coherence, "kept_no_accel", []) or [])
    return out


def check_cycle(conn, run_id: int | None, config: dict, fundamentals, now: datetime, *, cache,
                coherence=None, filings_of: Callable[[str], list[dict] | None] | None = None) -> str:
    """Run the check for this cycle and return the ``runs.note`` line. ``filings_of`` is injectable for tests;
    live, it is the existing throttled, point-in-time ``FilingsData`` over the EDGAR submissions API."""
    if fundamentals is None:
        return f"{PREFIX} fundamentals unavailable — nothing checked"
    if filings_of is None:
        ua = (config.get("edgar") or {}).get("user_agent")
        if not ua:
            return f"{PREFIX} no EDGAR user agent — nothing checked"
        from data.filings import (  # lazy: keeps the dashboard import graph light
            EdgarClient,
            FilingsData,
        )

        filings = FilingsData(cache, edgar=EdgarClient(ua, cache_dir=(config.get("cache") or {}).get("dir", "data/cache")),
                              fetch_end=now)

        def filings_of(sym: str) -> list[dict] | None:
            return filings.filings_asof(sym, now)

    def lines_of(sym: str) -> list[dict] | None:
        return (fundamentals.corpus_asof(sym, now) or {}).get("lines")

    return StalenessCheck(lines_of=lines_of, filings_of=filings_of).run(
        symbols_read_this_cycle(conn, run_id, coherence), now).summary()


# ── the read side (dashboard): one parser beside the one formatter ──────────────────────────────────

_ITEM_RE = re.compile(r"([A-Z][A-Z0-9.\-]*)\(corpus (\S+) < (\S+) (\S+)\)")
_NUM_RE = {k: re.compile(rf"\b{k}=(\d+)") for k in ("checked", "no_corpus", "errors")}


def parse_summary(note: str | None) -> dict | None:
    """Parse the ``fundamentals-staleness:`` segment out of a ``runs.note``; ``None`` if absent."""
    if not note or PREFIX not in note:
        return None
    seg = note[note.index(PREFIX):].split(" · ", 1)[0]
    if "nothing checked" in seg:
        return {"status": "unavailable", "lagging": [], "checked": 0, "no_corpus": 0, "errors": 0,
                "reason": seg[len(PREFIX):].strip()}
    m = re.search(r"lagging=\[(.*?)\]", seg)
    lagging = [{"symbol": a, "corpus_filed": b, "form": c, "filed": d}
               for a, b, c, d in _ITEM_RE.findall(m.group(1) if m else "")]
    nums = {k: int(rx.search(seg).group(1)) if rx.search(seg) else 0 for k, rx in _NUM_RE.items()}
    return {"status": "ok", "lagging": lagging, **nums}
