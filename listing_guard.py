"""Listing-status and pending-deal guard (#458): delisting and take-private filings for universe and held names.

Atkore (ATKR) filed its Form 25-NSE on 2026-10-19 and its 15-12G on 10-29, and sat in the scan universe and on
every council slate until a human noticed on 11-08 (records/2026-11-09_atkr_removal.md). #437 and #440 fixed two
symptoms (an empty chain read as a tenor gap; a dead symbol aborting a mark pass); nothing detected the cause.
A takeover also changes a held option's payoff (a cash deal caps a call at the deal price), so a HELD name with a
pending deal is a money question, not only a slot question.

Once per L1 this reads, for every universe name, active sentinel and open position (real book and null books):

a. **Delisting / deregistration** forms on EDGAR — ``25``, ``25-NSE``, ``15-12G``, ``15-12B``, ``15-15D``, and the
   foreign-private-issuer forms ``15F-12G``, ``15F-12B``, ``15F-15D`` (the universe holds FPIs: CCJ, ERO, HBM, ...).
b. **Pending-deal / tender-offer** forms — ``DEFM14A``, ``PREM14A``, ``DEFM14C``, ``PREM14C`` (merger information
   statements, used when holders act by written consent), ``SC TO-T``, ``SC TO-I``, ``SC 13E3``, ``SC 14D9``.
   The tender-offer codes were confirmed from SECONDARY sources on 2026-11-10 (aggregator listings carrying May-2026
   filings; a Deloitte DART page updated 2026-02-11), NOT from EDGAR, which is unreachable from the build sandbox:
   they are still ``SC TO-T`` / ``SC TO-I`` / ``SC TO-C`` / ``SC 14D9`` / ``SC 13E3``, with no ``SCHEDULE 13D``-style
   rename. Confirm against a live CIK on DEV with the read-only smoke entry point, which prints the hits AND every
   distinct form type in the window with counts (so a renamed form is visible to a human; it writes nothing to the
   DB, only the usual EDGAR cache files, and pages nobody)::

       python -m listing_guard --symbol SYM [--as-of YYYY-MM-DD]

   Matching is EXACT MEMBERSHIP (``form ∈ {base, base + "/A"}``, ``data.structural_events.allowed_forms``), never
   a prefix: ``25`` must not match ``25-X``, ``SC TO-T`` must not match ``SC TO-C`` (pre-commencement
   communications, filed for deals that may never launch).
   **8-K Item 1.01 is deliberately left out.** The submissions path does expose item codes
   (``data.filings._normalize_filing_block`` parses the ``items`` column into ``record["items"]``), but Item 1.01
   is "entry into a material definitive agreement" — credit facilities and supply contracts as well as mergers.
   Telling a merger agreement apart needs the document text, and a held-name page on every credit amendment would
   teach the operator to ignore the page. A real deal reaches a merger proxy or a tender offer within weeks.
c. **Venue status** — the Alpaca asset's ``status`` / ``tradable`` (read-only ``AlpacaClient.get_asset``, a live read,
   never point-in-time). Optional: without a client, or when the read fails, the venue leg is reported unknown.
d. **Adjusted option class** (an OCC root other than the ticker) is already excluded by ``structure.py``
   (``select_structure``, #437 lineage); it is not duplicated here.

Source: ``data.filings.FilingsData`` — the per-company SUBMISSIONS path (PIT-cached, ticker→CIK, SEC-throttled,
fresh each run because coverage re-extends to ``fetch_end``). Not ``data/edgar_index.py``: the quarterly index
lags, which is the wrong property for a live check. A same-day filing that EDGAR returns without an
``acceptanceDateTime`` is stamped by the ``filingDate T20:00Z`` fallback, so a run before 20:00 UTC sees it the next day.

**Telemetry and paging only.** Nothing here closes a position, vetoes an entry, edits the universe or changes a
slate: removal stays the operator's dated act (PREREG_UNIVERSE_CURATION §3). It runs after entries are decided,
inside a wall-clock budget so a slow SEC can never push the L1 unit past its ``TimeoutStartSec``.

Fail-SOFT, never fail-SILENT: a name whose source fails, has no CIK, or is not reached inside the budget is counted
and reported unknown, never "no events"; when unknowns are most of the checked names the status line is a WARNING.
"""

from __future__ import annotations

import json
import logging
import math
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from data.structural_events import allowed_forms

log = logging.getLogger("listing_guard")

# Per-class trailing windows, closed [as_of − window, as_of]. Deals: 365 days, because a deal under regulatory review
# runs 6–18 months from the merger proxy to the close, and a position opened mid-review must still see the proxy.
# Delistings: 90 days, long enough to survive missed runs and a few Sunday reviews, short enough that a name already
# gone stops re-reporting. Paging is debounced per accession per position, so a long window costs no repeat pages.
DEAL_WINDOW_DAYS = 365
DELISTING_WINDOW_DAYS = 90
WINDOWS = {"delisting": DELISTING_WINDOW_DAYS, "deal": DEAL_WINDOW_DAYS}

# Wall-clock budget for one run's reads. Every name refetches its submissions (``FilingsData`` coverage re-extends to
# ``fetch_end`` each run) and ``EdgarClient`` waits up to 30 s per request, so ~70 names against a hung SEC would be
# ~35 min — past the L1 unit's TimeoutStartSec=1800. Checked between names (one in-flight read can overrun it by its
# own timeout); the unread names are counted ``budget_skipped`` and reported unknown.
BUDGET_SECONDS = 300.0

DELISTING_BASES = ("25", "25-NSE", "15-12G", "15-12B", "15-15D", "15F-12G", "15F-12B", "15F-15D")
DEAL_BASES = ("DEFM14A", "PREM14A", "DEFM14C", "PREM14C", "SC TO-T", "SC TO-I", "SC 13E3", "SC 14D9")
DELISTING_FORMS = allowed_forms(DELISTING_BASES)
DEAL_FORMS = allowed_forms(DEAL_BASES)
CLASSES = ("delisting", "deal", "venue")
CLASS_LABEL = {"delisting": "delisting / deregistration", "deal": "pending deal or tender offer",
               "venue": "venue status"}
NOTE_MAX_SYMBOLS = 10

PAGE_KEY_PREFIX = "listing_guard:"   # key in a real position's rationale ``paged`` dict (monitor._page_once's dict)
TRADING_TO_CALENDAR = 365 / 252      # shares horizons are trading bars; the guard's clock is calendar days


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
    """Per-run counts, kept separate: ``errors`` / ``no_cik`` (EDGAR leg), ``venue_errors``, ``budget_skipped``."""

    checked: int = 0
    no_cik: int = 0
    errors: int = 0
    venue_errors: int = 0
    budget_skipped: int = 0
    venue_on: bool = False
    hits: list[Hit] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)

    def mark_unknown(self, sym: str) -> None:
        if sym not in self.unknown:
            self.unknown.append(sym)

    def by_class(self) -> dict[str, int]:
        return {k: len({h.symbol for h in self.hits if h.klass == k}) for k in CLASSES}

    def mostly_failed(self) -> bool:
        """Unknown names (errors, no CIK, budget skips) are most of the checked names: a quiet line would lie."""
        return self.checked > 0 and len(self.unknown) * 2 > self.checked

    def status(self) -> str:
        c = self.by_class()
        venue = f"venue_err={self.venue_errors}" if self.venue_on else "venue=off"
        return (f"listing_guard: checked={self.checked} delisting={c['delisting']} deal={c['deal']} "
                f"venue={c['venue']} err={self.errors} no_cik={self.no_cik} {venue} "
                f"budget_skipped={self.budget_skipped} window=deal{DEAL_WINDOW_DAYS}d/delist{DELISTING_WINDOW_DAYS}d")


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def classify_form(form: str) -> str | None:
    """'delisting' / 'deal' by exact membership (base or base + '/A'), else None."""
    if form in DELISTING_FORMS:
        return "delisting"
    if form in DEAL_FORMS:
        return "deal"
    return None


def _ts(r: dict[str, Any]) -> datetime | None:
    try:
        return _utc(datetime.fromisoformat(str(r.get("ts", ""))))
    except ValueError:
        return None


def match_filings(symbol: str, records: Iterable[dict[str, Any]], as_of: datetime,
                  windows: dict[str, int] | None = None) -> list[Hit]:
    """Hits among ``FilingsData`` records filed in their class's closed window ``[as_of − window, as_of]``.

    The ``ts <= as_of`` bound is re-applied here even though ``filings_asof`` already enforces it: nothing dated
    after the run's clock may influence the result, whatever the source hands back."""
    as_of = _utc(as_of)
    windows = windows or WINDOWS
    out: list[Hit] = []
    for r in records:
        form = str(r.get("form", ""))
        klass = classify_form(form)
        ts = _ts(r) if klass else None
        if klass is None or ts is None:
            continue
        if not as_of - timedelta(days=windows[klass]) <= ts <= as_of:
            continue
        out.append(Hit(symbol=symbol.upper(), klass=klass, form=form,
                       accession=str(r.get("accession") or f"{form}@{ts.isoformat()}"), ts=ts.isoformat()))
    return out


def venue_hit(symbol: str, asset: Any, as_of: datetime) -> Hit | None:
    """A hit when the venue says the asset is not active or not tradable (an Alpaca ``Asset`` or a dict).

    The debounce key is the venue STATE, so a state that recurs later for the same position does not re-page."""
    get = asset.get if isinstance(asset, dict) else (lambda k, d=None: getattr(asset, k, d))
    raw = get("status", None)
    status = str(getattr(raw, "value", raw) or "").lower()
    tradable = bool(get("tradable", False))
    if status == "active" and tradable:
        return None
    return Hit(symbol=symbol.upper(), klass="venue", form=f"status={status or 'none'} tradable={tradable}",
               accession=f"venue:{status or 'none'}:{tradable}", ts=_utc(as_of).isoformat())


def order_names(roles: dict[str, set[str]]) -> list[str]:
    """Spend the budget where it matters: open real positions, then sentinels and universe, then null-book-only."""
    def rank(sym: str) -> tuple[int, str]:
        r = roles[sym]
        return (0 if "real" in r else 1 if r & {"sentinel", "universe"} else 2, sym)

    return sorted(roles, key=rank)


def check_names(symbols: Iterable[str], filings: Any, as_of: datetime, *,
                asset_of: Callable[[str], Any] | None = None, windows: dict[str, int] | None = None,
                budget_s: float = BUDGET_SECONDS, monotonic: Callable[[], float] = time.monotonic) -> GuardResult:
    """Read every name IN THE ORDER GIVEN; a per-name failure degrades that name only and is COUNTED.

    ``filings`` duck-types ``FilingsData`` (``_cik``, ``filings_asof``); ``None`` means the EDGAR leg could not be
    built, and every name is then an error, not a clean read. Past ``budget_s`` the remaining names are not read."""
    res = GuardResult(venue_on=asset_of is not None)
    start = monotonic()
    seen: set[str] = set()
    for raw in symbols:
        sym = str(raw or "").upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        res.checked += 1
        if monotonic() - start > budget_s:
            res.budget_skipped += 1
            res.mark_unknown(sym)
            continue
        try:
            if filings is None:
                raise RuntimeError("EDGAR source unavailable")
            if filings._cik(sym) is None:
                res.no_cik += 1
                res.mark_unknown(sym)
            else:
                res.hits.extend(match_filings(sym, filings.filings_asof(sym, as_of), as_of, windows))
        except Exception as e:  # noqa: BLE001 — a per-name failure is an unknown, never "no events"
            res.errors += 1
            res.mark_unknown(sym)
            log.warning("listing guard: EDGAR read failed for %s: %s", sym, e)
        if asset_of is not None:
            try:
                h = venue_hit(sym, asset_of(sym), as_of)
                if h is not None:
                    res.hits.append(h)
            except Exception as e:  # noqa: BLE001 — the venue leg is optional; its failure is counted
                res.venue_errors += 1
                res.mark_unknown(sym)
                log.warning("listing guard: venue read failed for %s: %s", sym, e)
    return res


# ── inputs ────────────────────────────────────────────────────────────────────────────────────────────────────────
def names_to_check(config: dict, conn, *, as_of: datetime) -> dict[str, set[str]]:
    """``symbol -> roles`` over the universe, active sentinels, the real book ("real") and the null books ("null").

    Shares entries are an append-only log with no close, so a shares name counts as held while its longest return
    horizon is still in flight. Those horizons are TRADING bars (``shares_basket``); they are converted to calendar
    days (bars × 365/252, rounded up) before being subtracted from the calendar clock."""
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

    bars = int(max((config.get("shares_basket", {}) or {}).get("horizons") or DEFAULT_HORIZONS))
    days = math.ceil(bars * TRADING_TO_CALENDAR)
    for s in state.shares_recent_symbols(conn, since_iso=(_utc(as_of) - timedelta(days=days)).isoformat()):
        add(s, "null")
    return roles


# ── outputs ───────────────────────────────────────────────────────────────────────────────────────────────────────
def page_body(symbol: str, ids: str, hits: list[Hit]) -> str:
    """Neutral, class-specific copy: an SC TO-I is an issuer self-tender, and an acquirer files these forms too."""
    parts = [f"{CLASS_LABEL[h.klass]}: {h.form} {h.ts[:10]} ({h.accession})" for h in hits]
    return f"{symbol} (open real {ids}): " + "; ".join(parts) + ". Nothing was closed; the call is the operator's."


def page_held(conn, symbol: str, hits: list[Hit], *, as_of: datetime, notify_send: Callable[..., Any]) -> int:
    """Page once per (symbol, accession) for an OPEN REAL position. Returns the number of new hits paged.

    Debounce lives in the open position's rationale JSON, in the same ``paged`` dict ``monitor._page_once`` stamps
    (key ``listing_guard:<accession>``), so it needs no state file and dies with the position. The stamp is written
    before the push by design (unlike ``monitor._page_once``, which since #479 stamps only a delivered page, because
    its L2 retries every 30 minutes): for this nightly job a failed push is not retried rather than repeated nightly. Only ``status='open'`` rows page: a ``closing`` row is already being sold, and ``pending`` / ``carried``
    rows belong to the carry worker, which rewrites their rationale."""
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
    notify_send(f"LISTING GUARD: held {symbol}", page_body(symbol, ids, new), priority=1)
    return len(new)


def latest_per_class(hits: list[Hit]) -> list[Hit]:
    """One hit per class (the newest) — keeps the run note bounded under the long deal window."""
    best: dict[str, Hit] = {}
    for h in hits:
        if h.klass not in best or h.ts > best[h.klass].ts:
            best[h.klass] = h
    return [best[k] for k in CLASSES if k in best]


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
        desc = ",".join(f"{h.klass}:{h.form}@{h.ts[:10]}" for h in latest_per_class(hits))
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
        more = len(result.unknown) - NOTE_MAX_SYMBOLS
        line += " unknown=" + ",".join(result.unknown[:NOTE_MAX_SYMBOLS]) + (f",+{more}" if more > 0 else "")
    if noted:
        more = len(noted) - NOTE_MAX_SYMBOLS
        line += " hits=" + "; ".join(noted[:NOTE_MAX_SYMBOLS]) + (f"; +{more}" if more > 0 else "")
    if result.mostly_failed() or result.budget_skipped:
        log.warning("%s — names UNKNOWN (errors / no CIK / budget): fail-soft is not fail-silent", line)
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
                notify_send: Callable[..., Any] | None = None,
                monotonic: Callable[[], float] = time.monotonic) -> str:
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
    result = check_names(order_names(roles), filings, as_of, asset_of=asset_of, monotonic=monotonic)
    return dispose(conn, result, roles, as_of=as_of, run_id=run_id, notify_send=notify_send)


# ── read-only smoke entry point (DEV: confirm form codes against a live CIK) ─────────────────────────────────────
def smoke_report(symbol: str, filings: Any, as_of: datetime) -> str:
    """Hits plus EVERY distinct form type in the longest window, with counts — so a renamed form is visible."""
    as_of = _utc(as_of)
    floor = as_of - timedelta(days=max(WINDOWS.values()))
    records = [r for r in filings.filings_asof(symbol, as_of) if (t := _ts(r)) is not None and floor <= t <= as_of]
    counts: dict[str, int] = {}
    for r in records:
        counts[str(r.get("form", ""))] = counts.get(str(r.get("form", "")), 0) + 1
    hits = match_filings(symbol, records, as_of)
    lines = [f"{symbol.upper()} as of {as_of.isoformat()} (cik={filings._cik(symbol)})", f"hits: {len(hits)}"]
    lines += [f"  {h.klass:9s} {h.form:10s} {h.ts}  {h.accession}" for h in hits]
    lines.append(f"forms in the trailing {max(WINDOWS.values())}d:")
    lines += [f"  {f:12s} {n}" for f, n in sorted(counts.items())]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Listing guard smoke read (#458): read-only, no DB, no page")
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--as-of", help="YYYY-MM-DD (end of that UTC day); default now")
    args = ap.parse_args(argv)
    from config_loader import load_config
    from data.cache import PointInTimeCache

    config = load_config()
    now = datetime.now(UTC)
    as_of = (datetime.fromisoformat(args.as_of).replace(hour=23, minute=59, tzinfo=UTC) if args.as_of else now)
    cache = PointInTimeCache(config.get("cache", {}).get("dir", "data/cache"))
    filings = _filings_source(config, cache, now)
    if filings is None:
        print("no EDGAR_USER_AGENT configured — cannot read")
        return 1
    print(smoke_report(args.symbol, filings, min(as_of, now)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
