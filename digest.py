"""Weekly reach-digest harness v0 — OFFLINE OPERATOR TOOL.

Governing spec: ``records/2026-07-14_reach_channels_charter_DRAFT.md`` (§3, the digest).
This module scales REACH into the operator's judgment; it is deliberately incapable of
judging. Charter law enforced here by construction:

- **No scoring/rank/relevance field exists anywhere in the harness schema** (:class:`Item`
  is the schema; a guard test pins its exact field set so a future scoring field fails CI).
- **Ordering is chronological or source-grouped ONLY** — ordering is ranking in disguise,
  so :func:`assemble` sorts by publication time within a source group and nothing else.
- **Overflow is truncation, never selection**: per-source caps drop the OLDEST items with
  an explicit dropped-count line. The durable fix for persistent overflow is the operator
  tightening ``digest_feeds.json`` (the pond-naming act), not smarter filtering.
- **The orphan watch is IPO-age × options-class-existence ONLY** — both pure existence /
  expression events. A decayed-coverage/volume/analyst leg would be inverted-salience math
  (computing quietness, the operation charter §2 forbids) and is excluded by construction.

Everything here is stdlib-only (urllib.request / xml.etree / json / datetime / pathlib);
the orphan channel's checker leans on the EXISTING alpaca-py dependency via a deferred
import, and the 424B4 cohort rides the existing ``data/edgar_index.EdgarIndex`` in its
sanctioned HISTORICAL role (closed quarters only). Fetchers are fail-soft per feed: a dead
feed returns ``[]`` and is COUNTED into the caller's error list — dead-arm vs quiet-arm is
always distinguishable, and no feed failure ever raises out of a channel.

This is an operator tool: it never touches the orchestrator, the deterministic gates, the
council, or any book. Nothing here can stale the §5 clock.
"""

from __future__ import annotations

import calendar
import json
import time
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

CHANNELS = ("trade_press", "newsletters", "agency", "orphan_watch")

FEDERAL_REGISTER_URL = "https://www.federalregister.gov/api/v1/documents.json"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
DIGEST_CACHE_DIR = Path("data/cache/digest")
ORPHAN_SNAPSHOT_PATH = DIGEST_CACHE_DIR / "orphan_seen.json"

# Polite identifying UA for trade-press/agency feeds (SEC endpoints take the operator's
# configured contact UA instead — config.edgar.user_agent, threaded by the caller).
DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; dramatic-options-digest/0.1)"


@dataclass
class Item:
    """One digest line. Deliberately NO score/rank/relevance field — charter law
    ("no scoring field exists anywhere in the harness schema"); a guard test asserts
    this exact field set so a future scoring field fails CI."""

    channel: str  # "trade_press" | "newsletters" | "agency" | "orphan_watch"
    source: str  # feed / agency / newsletter name
    title: str
    link: str
    published: datetime | None
    symbol: str | None = None  # orphan watch only


# ── time helpers ──────────────────────────────────────────────────────────────
def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def parse_date(text: str | None) -> datetime | None:
    """Best-effort RFC-822 (RSS pubDate), ISO-8601 (Atom), or loose 'Jul 14, 2026 12:41pm'
    (seen live on Drupal feeds) date. None if unparseable — missing/garbled dates are
    tolerated (the item just sorts as undated). Timezone-less stamps are taken as UTC:
    dates are only ever used for ordering/truncation, never as evidence."""
    if not text:
        return None
    s = text.strip()
    try:
        return _as_utc(parsedate_to_datetime(s))
    except (TypeError, ValueError):
        pass
    try:
        return _as_utc(datetime.fromisoformat(s.replace("Z", "+00:00")))
    except ValueError:
        pass
    try:
        return _as_utc(datetime.strptime(s.lower(), "%b %d, %Y %I:%M%p"))
    except ValueError:
        return None


def months_ago(dt: datetime, months: int) -> datetime:
    """``dt`` shifted back by calendar months (day clamped to the target month's length)."""
    y, m = dt.year, dt.month - months
    while m <= 0:
        m += 12
        y -= 1
    return dt.replace(year=y, month=m, day=min(dt.day, calendar.monthrange(y, m)[1]))


def last_closed_quarter_end(now: datetime) -> datetime:
    """End of the last fully CLOSED calendar quarter before ``now`` — the EdgarIndex
    full-index is only complete for closed quarters (its sanctioned historical role;
    the in-progress-quarter staleness bug is why the event leg left this path)."""
    prev_q = (now.month - 1) // 3  # 0 → previous year's Q4
    if prev_q == 0:
        return datetime(now.year - 1, 12, 31, 23, 59, 59, tzinfo=UTC)
    m = prev_q * 3
    return datetime(now.year, m, calendar.monthrange(now.year, m)[1], 23, 59, 59, tzinfo=UTC)


def iso_week_stamp(dt: datetime) -> str:
    """ISO-week digest stamp, e.g. ``2026-W29`` (also the output filename stem)."""
    iso = dt.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


# ── fetch plumbing ────────────────────────────────────────────────────────────
def _http_get(url: str, *, timeout: float, user_agent: str = DEFAULT_USER_AGENT) -> bytes:
    """Plain keyless GET (stdlib). Raises on any failure — callers are the fail-soft layer."""
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (https URLs only)
        return resp.read()


def _local(tag: str) -> str:
    """Element tag without its namespace ('{ns}item' → 'item')."""
    return tag.rsplit("}", 1)[-1]


def _child_text(el: ET.Element, name: str) -> str | None:
    for child in el:
        if _local(child.tag) != name:
            continue
        # itertext(): some real feeds nest markup inside <title> (e.g. an <a> element),
        # leaving .text empty — join all descendant text instead.
        text = " ".join("".join(child.itertext()).split())
        if text:
            return text
    return None


def _entry_link(el: ET.Element) -> str:
    """RSS ``<link>text</link>`` or Atom ``<link rel="alternate" href=…/>``."""
    fallback = ""
    for child in el:
        if _local(child.tag) != "link":
            continue
        if child.text and child.text.strip():  # RSS 2.0 style
            return child.text.strip()
        href = child.get("href", "").strip()
        if href:
            if child.get("rel") in (None, "", "alternate"):
                return href
            fallback = fallback or href
    return fallback


def parse_feed(text: str | bytes, *, source: str, channel: str) -> list[Item]:
    """Parse RSS 2.0 (``<item>``) or Atom (``<entry>``) into Items. Pure / no I/O.

    Missing dates are tolerated (``published=None``). Raises ``ET.ParseError`` on
    non-XML input and ``ValueError`` on XML that is not a feed (e.g. an HTML error page
    — that is a DEAD arm, not a quiet one) — :func:`fetch_rss` is the fail-soft wrapper."""
    root = ET.fromstring(text)
    if _local(root.tag) not in ("rss", "feed", "RDF"):  # RDF = RSS 1.0, same <item> shape
        raise ValueError(f"not an RSS/Atom document (root <{_local(root.tag)}>)")
    entry_tag = "entry" if _local(root.tag) == "feed" else "item"
    items: list[Item] = []
    for el in root.iter():
        if _local(el.tag) != entry_tag:
            continue
        title = _child_text(el, "title") or "(untitled)"
        published = parse_date(
            _child_text(el, "pubDate") or _child_text(el, "published")
            or _child_text(el, "updated") or _child_text(el, "date")  # dc:date
        )
        items.append(
            Item(channel=channel, source=source, title=" ".join(title.split()),
                 link=_entry_link(el), published=published)
        )
    return items


def fetch_rss(
    url: str,
    *,
    source: str,
    channel: str,
    timeout: float = 20,
    errors: list[str] | None = None,
) -> list[Item]:
    """Fetch + parse one RSS/Atom feed. Fail-soft: a dead/unparseable feed returns ``[]``
    and is COUNTED into ``errors`` (never raises out) — a dead arm is never mistaken for
    a quiet one."""
    try:
        return parse_feed(_http_get(url, timeout=timeout), source=source, channel=channel)
    except Exception as e:  # noqa: BLE001 — the fail-soft boundary is the point
        if errors is not None:
            errors.append(f"{channel}/{source}: {type(e).__name__}: {e}")
        return []


def federal_register_items(
    agency_slugs: list[str],
    *,
    days: int,
    timeout: float = 20,
    errors: list[str] | None = None,
    now: datetime | None = None,
) -> list[Item]:
    """Keyless Federal Register API pull — documents published in the last ``days`` days
    for each agency slug. channel="agency", source="federal_register/<slug>". Fail-soft
    per slug (a failed slug is counted and skipped, never raises out)."""
    since = (_as_utc(now or datetime.now(UTC)) - timedelta(days=days)).date().isoformat()
    out: list[Item] = []
    for slug in agency_slugs:
        source = f"federal_register/{slug}"
        query = urllib.parse.urlencode(
            [
                ("conditions[agencies][]", slug),
                ("conditions[publication_date][gte]", since),
                ("per_page", "100"),
            ]
        )
        try:
            data = json.loads(_http_get(f"{FEDERAL_REGISTER_URL}?{query}", timeout=timeout))
        except Exception as e:  # noqa: BLE001 — the fail-soft boundary is the point
            if errors is not None:
                errors.append(f"agency/{source}: {type(e).__name__}: {e}")
            continue
        for row in data.get("results") or []:
            pub = row.get("publication_date")
            out.append(
                Item(
                    channel="agency",
                    source=source,
                    title=" ".join(str(row.get("title") or "(untitled)").split()),
                    link=str(row.get("html_url") or ""),
                    published=parse_date(pub and f"{pub}T00:00:00+00:00"),
                )
            )
    return out


# ── orphan watch (charter §3: IPO-age × options-class-existence ONLY) ─────────
def sec_ticker_map(
    user_agent: str,
    *,
    cache_dir: str | Path = DIGEST_CACHE_DIR,
    timeout: float = 20,
) -> dict[str, str]:
    """CIK(10-digit) → TICKER from the SEC's ``company_tickers.json`` (keyless; the
    configured EDGAR contact UA is required by the SEC). Cached to ``cache_dir`` so
    reruns are network-free; delete the cache file to refresh."""
    path = Path(cache_dir) / "company_tickers.json"
    if path.exists():
        raw = json.loads(path.read_text())
    else:
        raw = json.loads(_http_get(SEC_TICKERS_URL, timeout=timeout, user_agent=user_agent))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(raw))
    return {str(r["cik_str"]).zfill(10): str(r["ticker"]).upper() for r in raw.values()}


def submissions_ticker_fallback(
    ciks: Iterable[str],
    user_agent: str,
    *,
    cache_dir: str | Path = DIGEST_CACHE_DIR,
    timeout: float = 20,
    rate_limit_per_sec: float = 8.0,
    errors: list[str] | None = None,
) -> dict[str, str | None]:
    """Current ticker for CIKs MISSING from ``company_tickers.json``, via the per-CIK
    SEC submissions JSON (its top-level ``tickers`` array carries the current symbol(s)).

    Returns cik(10-digit) → ticker, or → ``None`` when the CIK legitimately has no
    current ticker (delisted/withdrawn — expected for aged IPOs; that's signal, not
    failure, and it IS cached). A CIK whose fetch fails is OMITTED from the result
    (fail-soft per CIK: counted into ``errors``, NOT cached, re-tried next run).

    Callers pass only the missing CIKs; fetches are throttled to ``rate_limit_per_sec``
    (SEC asks < 10 req/s — mirrors ``data/filings.EdgarClient``) and resolutions are
    cached under ``cache_dir`` so repeat weeks are network-free."""
    path = Path(cache_dir) / "submissions_tickers.json"
    cache: dict[str, str | None] = json.loads(path.read_text()) if path.exists() else {}
    out: dict[str, str | None] = {}
    min_interval = 1.0 / rate_limit_per_sec if rate_limit_per_sec > 0 else 0.0
    last_call = 0.0
    dirty = False
    for cik in ciks:
        cik10 = str(cik).zfill(10)
        if cik10 in cache:
            out[cik10] = cache[cik10]
            continue
        if min_interval:
            wait = min_interval - (time.monotonic() - last_call)
            if wait > 0:
                time.sleep(wait)
        last_call = time.monotonic()
        try:
            raw = json.loads(
                _http_get(
                    SEC_SUBMISSIONS_URL.format(cik=cik10), timeout=timeout, user_agent=user_agent
                )
            )
            tickers = [str(t).strip() for t in (raw.get("tickers") or []) if str(t).strip()]
            ticker = tickers[0].upper() if tickers else None
        except Exception as e:  # noqa: BLE001 — the fail-soft boundary is the point
            if errors is not None:
                errors.append(
                    f"orphan_watch/submissions-fallback CIK{cik10}: {type(e).__name__}: {e}"
                )
            continue
        cache[cik10] = out[cik10] = ticker
        dirty = True
    if dirty:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dict(sorted(cache.items())), indent=1) + "\n")
    return out


def orphan_cohort(
    edgar_index: Any,
    *,
    start: datetime,
    end: datetime,
    limit: int,
    ticker_map: Mapping[str, str],
    notes: list[str] | None = None,
    fallback_lookup: Callable[[list[str]], Mapping[str, str | None]] | None = None,
) -> list[dict[str, Any]]:
    """The 424B4 IPO cohort in [start, end] as ``{symbol, cik, company, date_filed}`` dicts.

    ``edgar_index`` must be an ``EdgarIndex`` constructed with ``form="424B4"`` (closed
    quarters only — the caller clamps ``end`` via :func:`last_closed_quarter_end`).
    ``ticker_map`` (CIK→ticker, :func:`sec_ticker_map`) is injected so this stays pure /
    offline-testable. Deduped by ticker (first filing wins), chronological; capped at
    ``limit`` by dropping the OLDEST with an explicit dropped-count note (truncation,
    never selection).

    CIKs absent from ``ticker_map`` go to ``fallback_lookup`` (only the MISSING CIKs,
    deduped — :func:`submissions_ticker_fallback` wired by the runner): a returned ticker
    rejoins the cohort (counted); a returned ``None`` is a filer with legitimately no
    current ticker (delisted/withdrawn — counted as signal, not failure); a CIK omitted
    from the result stays unmapped (counted; the fallback's own ``errors`` carry why)."""
    events = edgar_index.enumerate_events(start, end)  # ts-ascending, accession-deduped
    missing = list(dict.fromkeys(ev["cik"] for ev in events if not ticker_map.get(ev["cik"])))
    fallback: Mapping[str, str | None] = {}
    if fallback_lookup is not None and missing:
        fallback = fallback_lookup(missing)
    seen: set[str] = set()
    unmapped_ciks: set[str] = set()
    no_ticker_ciks: set[str] = set()
    recovered_ciks: set[str] = set()
    cohort: list[dict[str, Any]] = []
    for ev in events:
        symbol = ticker_map.get(ev["cik"])
        if not symbol:
            if ev["cik"] in fallback:
                fb = fallback[ev["cik"]]
                if fb:
                    symbol = fb
                    recovered_ciks.add(ev["cik"])
                else:
                    no_ticker_ciks.add(ev["cik"])
                    continue
            else:
                unmapped_ciks.add(ev["cik"])
                continue
        if symbol in seen:
            continue
        seen.add(symbol)
        cohort.append(
            {
                "symbol": symbol,
                "cik": ev["cik"],
                "company": ev.get("company", ""),
                "date_filed": ev.get("date_filed", ""),
            }
        )
    if notes is not None:
        if recovered_ciks:
            notes.append(
                f"orphan_watch: {len(recovered_ciks)} ticker(s) resolved via "
                "SEC submissions fallback"
            )
        if no_ticker_ciks:
            notes.append(
                f"orphan_watch: {len(no_ticker_ciks)} 424B4 filer(s) with no current ticker "
                "(delisted/withdrawn) skipped"
            )
        if unmapped_ciks:
            notes.append(
                f"orphan_watch: {len(unmapped_ciks)} 424B4 filer(s) with no current "
                "ticker mapping skipped"
            )
    if len(cohort) > limit:
        dropped = len(cohort) - limit
        if notes is not None:
            notes.append(f"orphan_watch: cohort capped at {limit}; {dropped} older issuers dropped")
        cohort = cohort[dropped:]
    return cohort


_WARRANT_UNIT_SUFFIXES = ("-WT", "-WS", "-U", "-R")
_WARRANT_UNIT_INFIXES = (".WS", ".U")


def is_warrant_or_unit(symbol: str) -> bool:
    """True for warrant/unit/rights share classes (``-WT``/``-WS``/``-U``/``-R`` suffixes
    or dotted ``.WS``/``.U`` classes). These have no options class by construction and
    Alpaca's contract endpoint rejects them (the EVAC-WT APIError class), so they are
    skipped BEFORE the options-class check — counted in a note, never sent to the
    endpoint, and kept distinct from genuine checker errors."""
    s = symbol.upper()
    return s.endswith(_WARRANT_UNIT_SUFFIXES) or any(m in s for m in _WARRANT_UNIT_INFIXES)


def options_class_exists(trading_client: Any, symbol: str) -> bool:
    """True iff Alpaca lists ≥1 option contract on ``symbol`` — a pure existence event
    (alpaca-py is an existing dependency; imported lazily so the keyless ``--skip-orphan``
    path never needs it)."""
    from alpaca.trading.requests import GetOptionContractsRequest

    resp = trading_client.get_option_contracts(
        GetOptionContractsRequest(underlying_symbols=[symbol], limit=1)
    )
    contracts = resp.get("option_contracts") if isinstance(resp, dict) else resp.option_contracts
    return bool(contracts)


def orphan_new_listings(
    candidates: Iterable[Mapping[str, Any]],
    snapshot: dict[str, str],
    checker: Callable[[str], bool],
    *,
    now: datetime | None = None,
    errors: list[str] | None = None,
    notes: list[str] | None = None,
) -> tuple[list[Item], dict[str, str]]:
    """Items for cohort symbols whose options class exists NOW and which are NOT in the
    prior ``snapshot`` (symbol → first_seen ISO date). Returns (items, updated snapshot).

    The filter is IPO-age × options-class-existence ONLY — no coverage/volume/analyst leg
    of any kind (charter §3: a decayed-coverage leg is forbidden inverted-salience math).
    Warrant/unit classes (:func:`is_warrant_or_unit`) are skipped BEFORE the options-class
    check and counted into ``notes`` — never sent to the endpoint, never an ``errors``
    entry (genuine checker failures stay counted separately). A checker failure for one
    symbol is counted and skipped (the symbol is NOT marked seen, so it is re-checked
    next run) — fail-soft, never raises out."""
    now_dt = _as_utc(now or datetime.now(UTC))
    updated = dict(snapshot)
    items: list[Item] = []
    warrant_unit_skipped = 0
    for cand in candidates:
        symbol = str(cand["symbol"])
        if is_warrant_or_unit(symbol):
            warrant_unit_skipped += 1
            continue  # no options class by construction; never probe the endpoint
        if symbol in snapshot:
            continue  # already known-listed; not new
        try:
            if not checker(symbol):
                continue
        except Exception as e:  # noqa: BLE001 — the fail-soft boundary is the point
            if errors is not None:
                errors.append(f"orphan_watch/{symbol}: {type(e).__name__}: {e}")
            continue
        updated[symbol] = now_dt.date().isoformat()
        cik = str(cand.get("cik", "")).lstrip("0")
        items.append(
            Item(
                channel="orphan_watch",
                source="orphan_watch/424B4",
                title=(
                    f"{symbol}: options class now listed "
                    f"(424B4 {cand.get('date_filed', '?')}, {cand.get('company', '')})"
                ),
                link=(
                    "https://www.sec.gov/cgi-bin/browse-edgar"
                    f"?action=getcompany&CIK={cik}&type=424B4" if cik else ""
                ),
                published=now_dt,
                symbol=symbol,
            )
        )
    if warrant_unit_skipped and notes is not None:
        notes.append(f"orphan_watch: {warrant_unit_skipped} warrant/unit class(es) skipped")
    return items, updated


def load_snapshot(path: str | Path = ORPHAN_SNAPSHOT_PATH) -> dict[str, str]:
    """The prior orphan snapshot (symbol → first_seen ISO date); absent file → {}."""
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else {}


def save_snapshot(snapshot: dict[str, str], path: str | Path = ORPHAN_SNAPSHOT_PATH) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(dict(sorted(snapshot.items())), indent=1) + "\n")


# ── assembly (chronological / source-grouped ONLY — no ranking of any kind) ───
def _sort_key(pair: tuple[int, Item]) -> tuple[int, float, int]:
    idx, item = pair
    if item.published is None:
        return (1, 0.0, idx)  # undated last, input order
    return (0, _as_utc(item.published).timestamp(), idx)


def _item_line(item: Item) -> str:
    when = (
        _as_utc(item.published).strftime("%Y-%m-%d %H:%MZ") if item.published else "undated"
    )
    line = f"- {when} — {item.title}"
    return f"{line} — {item.link}" if item.link else line


def assemble(
    items: list[Item],
    *,
    caps: dict[str, int],
    week: str,
    dropped_notes: list[str],
    generated_at: datetime | None = None,
) -> str:
    """One markdown digest: grouped by channel then source, chronological within each
    source group (undated items last, input order), per-SOURCE truncation to
    ``caps[channel]`` with an explicit dropped line. Overflow is truncation, never
    selection (charter §3); there is NO ranking of any kind. ``generated_at`` is
    injectable so tests pin a deterministic document."""
    gen = _as_utc(generated_at or datetime.now(UTC))
    grouped: dict[str, dict[str, list[tuple[int, Item]]]] = {}
    for idx, item in enumerate(items):
        grouped.setdefault(item.channel, {}).setdefault(item.source, []).append((idx, item))

    body: list[str] = []
    counts: dict[str, tuple[int, int]] = {}  # channel → (kept, fetched)
    for channel in CHANNELS:
        body += [f"## {channel}", ""]
        sources = grouped.get(channel, {})
        kept_total = fetched_total = 0
        if not sources:
            body += ["(no items)", ""]
        for source in sorted(sources):
            ordered = [item for _, item in sorted(sources[source], key=_sort_key)]
            cap = caps.get(channel, len(ordered))
            dropped = max(0, len(ordered) - cap)
            kept = ordered[dropped:]
            kept_total += len(kept)
            fetched_total += len(ordered)
            body += [f"### {source}", ""]
            if dropped:
                body.append(f"… {dropped} older items dropped (per-source cap)")
            body += [_item_line(item) for item in kept]
            body.append("")
        counts[channel] = (kept_total, fetched_total)

    count_line = " · ".join(
        f"{ch} {counts[ch][0]}/{counts[ch][1]}" for ch in CHANNELS
    )
    head = [
        f"# Reach digest — {week}",
        "",
        f"- generated: {gen.isoformat(timespec='seconds')}",
        f"- provenance: {'/'.join(CHANNELS)}",
        f"- items (shown/fetched): {count_line}",
        "",
    ]
    tail: list[str] = []
    if dropped_notes:
        tail = ["## notes", ""] + [f"- {note}" for note in dropped_notes] + [""]
    return "\n".join(head + body + tail)
