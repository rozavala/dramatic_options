"""EDGAR-backed structural-event provider — the discovery surface gate's event leg (PREREG_EVENT_LEG).

Implements ``discovery.EventProvider`` over the per-company SUBMISSIONS path
(``data/filings.FilingsData`` — PIT-cached, ticker→CIK, SEC-throttled, fresh by construction:
coverage re-extends with ``fetch_end`` each scan). This supersedes the frozen
`PREREG_UNIVERSE_CURATION §7(a)` reuse wording ("data/edgar_index / data/prospectus") by dated
amendment (PREREG_EVENT_LEG §2): ``edgar_index._quarter_text`` never re-fetches a cached
in-progress quarter — disqualifying for a weekly LIVE leg; the quarterly-index path stays the
historical tool.

The event is a REACHABILITY trigger only — no drift/alpha claim (the FSSD 424B5 grave:
event ≈ random-date null). Matching is EXACT MEMBERSHIP — ``form ∈ {base, base + "/A"}`` per
pinned base — never a prefix (S-1 must not match S-11/S-1MEF; S-3 must not match
S-3ASR/S-3MEF/S-3D; 424B5 must not match 424B1/B2/B3/B4; F-10 must not match F-10POS/F-10EF).

Fail-SOFT, never invisible (the anti-silent-dormancy discipline): per-name failures degrade that
name only and are COUNTED; the counters feed the scan's structured status line + the
``runs.note`` stamp, and a systemic failure (errors ≈ checked, or zero CIK resolution on a
non-empty scan) is the caller's cue to page. ``no_cik`` is distinguished from fetch errors —
ticker-map gaps are the likelier failure on new small-caps.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from data.filings import FilingsData

log = logging.getLogger("structural_events")


def _base_form(form: str) -> str:
    """'SC 13D/A' -> 'SC 13D'; 'F-10/A' -> 'F-10'; a base form passes through."""
    return form[:-2] if form.endswith("/A") else form


def allowed_forms(bases: list[str] | tuple[str, ...] | frozenset[str]) -> frozenset[str]:
    """The exact-membership match set: each pinned base + its '/A' amendment. Never a prefix."""
    out: set[str] = set()
    for b in bases:
        b = str(b).strip()
        if b:
            out.add(b)
            out.add(b + "/A")
    return frozenset(out)


def form_set_hash(bases: list[str] | tuple[str, ...] | frozenset[str]) -> str:
    """6-char identity of the pinned base set — stamps every scan self-describing (runs.note)."""
    joined = ",".join(sorted(str(b).strip() for b in bases if str(b).strip()))
    return hashlib.sha1(joined.encode()).hexdigest()[:6]


@dataclass
class EventCounters:
    """Per-scan visibility (PREREG_EVENT_LEG §4) — 'ON, 0 fresh' must never be indistinguishable
    from a broken leg."""

    checked: int = 0
    cik_resolved: int = 0
    no_cik: int = 0
    fresh: int = 0
    errors: int = 0
    fresh_names: list[str] = field(default_factory=list)

    def status(self) -> str:
        return (f"checked={self.checked} cik={self.cik_resolved} no_cik={self.no_cik} "
                f"fresh={self.fresh} err={self.errors}")

    def systemic_failure(self) -> bool:
        """Errors ≈ checked, or zero CIK resolution, on a non-trivial scan → page-worthy."""
        if self.checked < 5:
            return False
        if self.errors >= max(1, int(self.checked * 0.8)):
            return True
        return self.cik_resolved == 0


class EdgarEventProvider:
    """``discovery.EventProvider`` over ``FilingsData`` — exact-membership forms, closed lookback.

    A filing is FRESH iff ``form ∈ allowed`` and ``as_of − lookback_days ≤ ts ≤ as_of``
    (closed interval — day-14 IN, day-15 OUT). Returns the NEWEST match's base form as the kind
    (flows into the markers JSON + ``marker_summary`` → framer/council grounding).
    """

    def __init__(self, filings: FilingsData, *, forms: frozenset[str] | list[str],
                 lookback_days: int = 14) -> None:
        self.filings = filings
        self.allowed = allowed_forms(forms) if not isinstance(forms, frozenset) else forms
        self.lookback_days = int(lookback_days)
        self.counters = EventCounters()

    def has_structural_event(self, symbol: str, as_of: datetime) -> tuple[bool, str | None]:
        self.counters.checked += 1
        try:
            cik = self.filings._cik(symbol)
            if cik is None:
                self.counters.no_cik += 1
                return False, None
            self.counters.cik_resolved += 1
            records = self.filings.filings_asof(symbol, as_of)  # ts <= as_of by construction
            floor = as_of - timedelta(days=self.lookback_days)
            newest: tuple[datetime, str] | None = None
            for r in records:
                form = str(r.get("form", ""))
                if form not in self.allowed:
                    continue
                try:
                    ts = datetime.fromisoformat(str(r.get("ts", "")))
                except ValueError:
                    continue
                if ts < floor:  # closed [as_of - lookback, as_of]
                    continue
                if newest is None or ts > newest[0]:
                    newest = (ts, _base_form(form))
            if newest is not None:
                self.counters.fresh += 1
                self.counters.fresh_names.append(symbol.upper())
                return True, newest[1]
            return False, None
        except Exception as e:  # noqa: BLE001 — a per-name failure degrades that name only
            self.counters.errors += 1
            log.warning("event provider failed for %s: %s", symbol, e)
            return False, None


def build_event_provider(config: dict, cache, as_of: datetime,
                         edgar_client=None) -> tuple[EdgarEventProvider | None, str]:
    """Factory — fail-soft to ``(None, reason)``; the reason feeds the scan status line.

    Reads ``config.discovery.events`` (funnel knobs, dated-edit-only) and the EXISTING
    ``config.edgar.user_agent`` seam (config_loader maps EDGAR_USER_AGENT there — never read
    os.environ here). ``edgar_client`` is injectable for tests.
    """
    ev_cfg = (config.get("discovery", {}) or {}).get("events", {}) or {}
    if not ev_cfg.get("enabled", False):
        return None, "disabled"
    bases = ev_cfg.get("forms", [])
    if not bases:
        return None, "no forms pinned"
    ua = (config.get("edgar", {}) or {}).get("user_agent", "")
    if edgar_client is None:
        if not ua:
            return None, "no EDGAR_USER_AGENT"
        try:
            from data.filings import EdgarClient
            edgar_client = EdgarClient(ua, cache_dir=config.get("cache", {}).get("dir", "data/cache"))
        except Exception as e:  # noqa: BLE001 — construction failure degrades to motion-only
            return None, f"client error: {e}"
    filings = FilingsData(cache, edgar=edgar_client, fetch_end=as_of)
    provider = EdgarEventProvider(filings, forms=allowed_forms(bases),
                                  lookback_days=int(ev_cfg.get("lookback_days", 14)))
    return provider, "on"
