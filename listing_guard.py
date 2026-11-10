"""Listing-status and pending-deal guard (#458): delisting and take-private filings for universe and held names.

Atkore (ATKR) filed its Form 25-NSE on 2026-10-19 and its 15-12G on 10-29, and sat in the scan universe and on
every council slate until a human noticed on 11-08 (records/2026-11-09_atkr_removal.md). #437 and #440 fixed two
symptoms (an empty chain read as a tenor gap; a dead symbol aborting a mark pass); nothing detected the cause.
A cash takeover also caps a held call's upside at the deal price, so a HELD name with a pending deal is a money
question, not only a slot question.

Once per L1 this reads, for every universe name, active sentinel and open position (real book and null books):

a. **Delisting / deregistration** forms on EDGAR — ``25``, ``25-NSE``, ``15-12G``, ``15-12B``, ``15-15D``.
b. **Pending-deal** forms — ``DEFM14A``, ``PREM14A``, ``SC TO-T``, ``SC TO-I``, ``SC 13E3``, ``SC 14D9``.
   Matching is EXACT MEMBERSHIP (``form ∈ {base, base + "/A"}``, ``data.structural_events.allowed_forms``), never
   a prefix: ``25`` must not match ``25-NSE``'s neighbours by accident, ``SC TO-T`` must not match ``SC TO-C``
   (pre-commencement communications, filed for deals that may never launch).
   **8-K Item 1.01 is deliberately left out.** The submissions path does expose item codes
   (``data.filings._normalize_filing_block`` parses the ``items`` column into ``record["items"]``), but Item 1.01
   is "entry into a material definitive agreement" — credit facilities and supply contracts as well as mergers.
   Telling a merger agreement apart needs the document text, and a held-name page on every credit amendment would
   teach the operator to ignore the page. A real deal reaches PREM14A / DEFM14A or SC TO-T within weeks.
c. **Venue status** — the Alpaca asset's ``status`` / ``tradable`` (read-only ``AlpacaClient.get_asset``).
   Optional: without a client, or when the read fails, the venue leg is reported unknown, never "active".
d. **Adjusted option class** (an OCC root other than the ticker) is already excluded by ``structure.py``
   (``select_structure``, #437 lineage); it is not duplicated here.

Source: ``data.filings.FilingsData`` — the per-company SUBMISSIONS path (PIT-cached, ticker→CIK, SEC-throttled,
fresh each run because coverage re-extends to ``fetch_end``). Not ``data/edgar_index.py``: the quarterly index
lags, which is the wrong property for a live check.

**Telemetry and paging only.** Nothing here closes a position, vetoes an entry, edits the universe or changes a
slate: removal stays the operator's dated act (PREREG_UNIVERSE_CURATION §3). It runs after entries are decided.

Fail-SOFT, never fail-SILENT: a name whose source fails is counted as an error and reported unknown, never as
"no events"; when errors are most of the checked names the status line is a WARNING.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from data.structural_events import allowed_forms

log = logging.getLogger("listing_guard")

# Trailing window, closed [as_of − 45d, as_of]. 45 days covers the gap between a merger proxy (DEFM14A) and the
# close (ATKR: 09-09 → 10-19 is 40 days) and leaves a multi-week margin for a missed run, while a 25 / 15-12G
# from last quarter stops re-reporting once the operator has had several Sunday reviews to act on it.
WINDOW_DAYS = 45

DELISTING_BASES = ("25", "25-NSE", "15-12G", "15-12B", "15-15D")
DEAL_BASES = ("DEFM14A", "PREM14A", "SC TO-T", "SC TO-I", "SC 13E3", "SC 14D9")
DELISTING_FORMS = allowed_forms(DELISTING_BASES)
DEAL_FORMS = allowed_forms(DEAL_BASES)
CLASSES = ("delisting", "deal", "venue")

PAGE_KEY_PREFIX = "listing_guard:"   # key in a real position's rationale ``paged`` dict (monitor._page_once's dict)


@dataclass(frozen=True)
class Hit:
    """One finding on one name. ``accession`` is the debounce identity (the EDGAR accession, or a venue key)."""

    symbol: str
    klass: str          # "delisting" | "deal" | "venue"
    form: str
    accession: str
    ts: str


@dataclass
class GuardResult:
    """Per-run counts. ``errors`` / ``no_cik`` are EDGAR-leg unknowns; ``venue_errors`` the Alpaca leg's."""

    checked: int = 0
    no_cik: int = 0
    errors: int = 0
    venue_errors: int = 0
    venue_on: bool = False
    hits: list[Hit] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)

    def by_class(self) -> dict[str, int]:
        return {k: len({h.symbol for h in self.hits if h.klass == k}) for k in CLASSES}

    def mostly_failed(self) -> bool:
        """Errors on most checked names: the leg is effectively down, and a quiet line would read as all-clear."""
        return self.checked > 0 and self.errors * 2 > self.checked

    def status(self) -> str:
        c = self.by_class()
        venue = f"venue_err={self.venue_errors}" if self.venue_on else "venue=off"
        return (f"listing_guard: checked={self.checked} delisting={c['delisting']} deal={c['deal']} "
                f"venue={c['venue']} err={self.errors} no_cik={self.no_cik} {venue} window={WINDOW_DAYS}d")


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def classify_form(form: str) -> str | None:
    """'delisting' / 'deal' by exact membership (base or base + '/A'), else None."""
    if form in DELISTING_FORMS:
        return "delisting"
    if form in DEAL_FORMS:
        return "deal"
    return None


def match_filings(symbol: str, records: Iterable[dict[str, Any]], as_of: datetime,
                  window_days: int = WINDOW_DAYS) -> list[Hit]:
    """Hits among ``FilingsData`` records filed in the closed window ``[as_of − window_days, as_of]``.

    The ``ts <= as_of`` bound is re-applied here even though ``filings_asof`` already enforces it: nothing dated
    after the run's clock may influence the result, whatever the source hands back."""
    as_of = _utc(as_of)
    floor = as_of - timedelta(days=window_days)
    out: list[Hit] = []
    for r in records:
        form = str(r.get("form", ""))
        klass = classify_form(form)
        if klass is None:
            continue
        try:
            ts = _utc(datetime.fromisoformat(str(r.get("ts", ""))))
        except ValueError:
            continue
        if not floor <= ts <= as_of:
            continue
        out.append(Hit(symbol=symbol.upper(), klass=klass, form=form,
                       accession=str(r.get("accession") or f"{form}@{ts.isoformat()}"), ts=ts.isoformat()))
    return out


def venue_hit(symbol: str, asset: Any, as_of: datetime) -> Hit | None:
    """A hit when the venue says the asset is not active or not tradable (an Alpaca ``Asset`` or a dict)."""
    get = asset.get if isinstance(asset, dict) else (lambda k, d=None: getattr(asset, k, d))
    raw = get("status", None)
    status = str(getattr(raw, "value", raw) or "").lower()
    tradable = bool(get("tradable", False))
    if status == "active" and tradable:
        return None
    return Hit(symbol=symbol.upper(), klass="venue", form=f"status={status or 'none'} tradable={tradable}",
               accession=f"venue:{status or 'none'}:{tradable}", ts=_utc(as_of).isoformat())


def check_names(symbols: Iterable[str], filings: Any, as_of: datetime, *,
                asset_of: Callable[[str], Any] | None = None, window_days: int = WINDOW_DAYS) -> GuardResult:
    """Read every name; a per-name failure degrades that name only and is COUNTED (``EventCounters`` discipline).

    ``filings`` duck-types ``FilingsData`` (``_cik``, ``filings_asof``); ``None`` means the EDGAR leg could not be
    built, and every name is then an error, not a clean read."""
    res = GuardResult(venue_on=asset_of is not None)
    for sym in sorted({s.upper() for s in symbols if s}):
        res.checked += 1
        try:
            if filings is None:
                raise RuntimeError("EDGAR source unavailable")
            if filings._cik(sym) is None:
                res.no_cik += 1
                res.unknown.append(sym)
            else:
                res.hits.extend(match_filings(sym, filings.filings_asof(sym, as_of), as_of, window_days))
        except Exception as e:  # noqa: BLE001 — a per-name failure is an unknown, never "no events"
            res.errors += 1
            res.unknown.append(sym)
            log.warning("listing guard: EDGAR read failed for %s: %s", sym, e)
        if asset_of is not None:
            try:
                h = venue_hit(sym, asset_of(sym), as_of)
                if h is not None:
                    res.hits.append(h)
            except Exception as e:  # noqa: BLE001 — the venue leg is optional; its failure is counted
                res.venue_errors += 1
                log.warning("listing guard: venue read failed for %s: %s", sym, e)
    return res


# ── inputs ────────────────────────────────────────────────────────────────────────────────────────────────────────
def names_to_check(config: dict, conn, *, as_of: datetime) -> dict[str, set[str]]:
    """``symbol -> roles`` over the universe, active sentinels, the real book ("real") and the null books ("null").

    Shares entries are an append-only log with no close, so a shares name counts as held while its longest return
    horizon is still in flight (the same window ``shares_basket`` dedups on)."""
    import state

    roles: dict[str, set[str]] = {}

    def add(sym: Any, role: str) -> None:
        if isinstance(sym, str) and sym.strip():
            roles.setdefault(sym.strip().upper(), set()).add(role)

    for k, members in ((config.get("universe", {}) or {}).get("themes", {}) or {}).items():
        if not str(k).startswith("_") and isinstance(members, list):
            for s in members:
                add(s, "universe")
    for s in state.active_sentinel_symbols(conn):
        add(s, "sentinel")
    for p in state.open_convexity_positions(conn):
        add(p["symbol"], "real")
    for p in list(state.open_shadow_positions(conn)) + list(state.open_fixed_basket_positions(conn)):
        add(p["symbol"], "null")
    from shares_basket import DEFAULT_HORIZONS

    horizon = int(max((config.get("shares_basket", {}) or {}).get("horizons") or DEFAULT_HORIZONS))
    for s in state.shares_recent_symbols(conn, since_iso=(_utc(as_of) - timedelta(days=horizon)).isoformat()):
        add(s, "null")
    return roles


# ── outputs ───────────────────────────────────────────────────────────────────────────────────────────────────────
def page_held(conn, symbol: str, hits: list[Hit], *, as_of: datetime, notify_send: Callable[..., Any]) -> int:
    """Page once per (symbol, accession) for an OPEN REAL position. Returns the number of new hits paged.

    Debounce lives in the open position's rationale JSON, in the same ``paged`` dict ``monitor._page_once`` stamps
    (key ``listing_guard:<accession>``), so it needs no state file and dies with the position. The stamp is written
    before the push: a lost push is better than a nightly repeat."""
    rows = conn.execute("SELECT id, rationale FROM convexity_positions WHERE status = 'open' AND symbol = ?",
                        (symbol,)).fetchall()
    if not rows:
        return 0
    rats: list[tuple[int, dict]] = []
    for row in rows:
        try:
            rat = json.loads(row["rationale"]) if row["rationale"] else {}
        except (TypeError, ValueError):
            rat = {"_unparsed_rationale": row["rationale"]}
        rats.append((int(row["id"]), rat if isinstance(rat, dict) else {"_rationale": rat}))
    seen = {k for _, r in rats if isinstance(r.get("paged"), dict) for k in r["paged"]}
    new = [h for h in hits if PAGE_KEY_PREFIX + h.accession not in seen]
    if not new:
        return 0
    stamp = _utc(as_of).date().isoformat()
    with conn:
        for pid, rat in rats:
            paged = rat.get("paged") if isinstance(rat.get("paged"), dict) else {}
            for h in new:
                paged[PAGE_KEY_PREFIX + h.accession] = stamp
            rat["paged"] = paged
            conn.execute("UPDATE convexity_positions SET rationale = ? WHERE id = ?",
                         (json.dumps(rat, default=str), pid))
    ids = ", ".join(f"#{pid}" for pid, _ in rats)
    body = "; ".join(f"{h.klass} {h.form} {h.ts[:10]} ({h.accession})" for h in new)
    notify_send(f"LISTING GUARD: held {symbol}",
                f"{symbol} (open real {ids}): {body}. A cash deal caps a call's upside at the deal price. "
                "Nothing was closed; the call is the operator's.", priority=1)
    return len(new)


def dispose(conn, result: GuardResult, roles: dict[str, set[str]], *, as_of: datetime, run_id: int | None,
            notify_send: Callable[..., Any]) -> str:
    """Log, page held names, note universe/sentinel hits on the run. Returns the status line."""
    by_sym: dict[str, list[Hit]] = {}
    for h in result.hits:
        by_sym.setdefault(h.symbol, []).append(h)
    noted: list[str] = []
    paged = 0
    for sym in sorted(by_sym):
        hits = by_sym[sym]
        r = roles.get(sym, set())
        desc = ",".join(f"{h.klass}:{h.form}@{h.ts[:10]}" for h in hits)
        log.info("listing guard hit: %s [%s] %s", sym, "/".join(sorted(r)) or "?", desc)
        if "real" in r:
            try:
                paged += page_held(conn, sym, hits, as_of=as_of, notify_send=notify_send)
            except Exception as e:  # noqa: BLE001 — a paging failure is logged, never raised into the cycle
                log.warning("listing guard: page for %s failed: %s", sym, e)
        if r & {"universe", "sentinel", "real"}:
            noted.append(f"{sym}({'/'.join(sorted(r & {'universe', 'sentinel', 'real'}))}) {desc}")
    line = result.status() + f" paged={paged}"
    if result.unknown:   # capped: an outage would otherwise paste the whole universe into the run note
        more = len(result.unknown) - 10
        line += " unknown=" + ",".join(result.unknown[:10]) + (f",+{more}" if more > 0 else "")
    if noted:
        line += " hits=" + "; ".join(noted)
    if result.mostly_failed():
        log.warning("%s — EDGAR errors on most names: fail-soft is not fail-silent, these names are UNKNOWN", line)
    else:
        log.info("%s", line)
    if run_id is not None:
        import state

        state.append_run_note(conn, run_id, line)
    return line


def _filings_source(config: dict, cache, as_of: datetime):
    """``FilingsData`` over the existing seams (``config.edgar.user_agent``, ``config.cache.dir``), as the council's
    fundamentals path and ``build_event_provider`` build it; ``None`` when there is no User-Agent."""
    ua = (config.get("edgar", {}) or {}).get("user_agent", "")
    if not ua:
        log.warning("listing guard: no EDGAR_USER_AGENT — the EDGAR leg is unavailable")
        return None
    from data.filings import EdgarClient, FilingsData

    edgar = EdgarClient(ua, cache_dir=config.get("cache", {}).get("dir", "data/cache"))
    return FilingsData(cache, edgar=edgar, fetch_end=as_of)


def run_nightly(conn, config: dict, *, run_id: int | None, cache, client, as_of: datetime,
                notify_send: Callable[..., Any] | None = None) -> str:
    """The L1 entry point (one fail-soft call in orchestrator.py, after entries are decided)."""
    if notify_send is None:
        import notify

        notify_send = notify.send
    roles = names_to_check(config, conn, as_of=as_of)
    try:
        filings = _filings_source(config, cache, as_of)
    except Exception as e:  # noqa: BLE001 — construction failure → every name unknown, counted
        log.warning("listing guard: EDGAR source construction failed: %s", e)
        filings = None
    asset_of = getattr(client, "get_asset", None) if client is not None else None
    result = check_names(roles, filings, as_of, asset_of=asset_of)
    return dispose(conn, result, roles, as_of=as_of, run_id=run_id, notify_send=notify_send)
