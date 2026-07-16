"""Survivor-card pipeline — STAGE A (deterministic only) — OFFLINE OPERATOR TOOL.

Governing spec: ``records/2026-07-14_reach_channels_charter_RATIFIED.md`` §3b (the
survivor-card compression + the per-thesis provenance guard). The weekly unit delivered to
the operator is the SURVIVOR CARD: ticker-bearing digest item → deterministic feasibility
screen (price / ADV / optionability / band-fit+cap, pass-fail) → automated premise-currency
pull → (Stage B, NOT built here) draft thesis with falsifier. Charter law enforced by
construction:

- **Compression happens ONLY by sanctioned deterministic steps — never by ranking.**
  Survivors and screen-failures are listed ALPHABETICALLY; no scoring/rank/relevance field
  exists anywhere in this module's schema (a guard test pins each dataclass's exact field
  set so a future scoring field fails CI — the ``digest.Item`` discipline).
- **Stage A is mechanical: NO LLM calls anywhere.** The thesis-drafting layer is Stage B
  and enters through one clearly named seam (:func:`draft_thesis_section` /
  :data:`STAGE_B_SEAM`); Stage B also upgrades the provenance tag ``machine_surfaced`` →
  ``machine_surfaced_machine_drafted`` (charter §3b's per-thesis provenance guard).
- **Extraction is conservative** (high-precision patterns only — cashtags, exchange
  parentheticals, an exact-match pass against the SEC known-universe set, and the digest's
  own machine-generated orphan-watch title). NO fuzzy company-name matching: false
  positives poison the screen. Every extraction records the item/channel that surfaced it.
- **The restricted list is fail-CLOSED** (``records/2026-07-14_restricted_list_RATIFIED.md``):
  an unreadable/malformed ``restricted.json`` HALTS the run; restricted tickers are dropped
  BEFORE any further processing; an absent file proceeds with a loud WARNING in the card
  document (the enforcement PR is staged and may not have landed).
- **Screen-failures are never silently dropped** (survivorship honesty): they land in a
  compact ``## Screened out`` section with every axis's state visible.

Everything here is pure / injection-driven (offline-testable); the runner
(``scripts/survivor_cards_run.py``) wires live Alpaca/EDGAR-cache access. This is an
operator tool: it never touches the orchestrator, the deterministic live gates, the
council, or any book. Nothing here can stale the §5 clock.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from datetime import time as dtime  # noqa: I001 — keep the alias import separate/readable
from pathlib import Path
from typing import Any

from convexity_gate import Contract
from convexity_sizing import convexity_position_size
from data.structural_events import allowed_forms
from digest import Item, parse_date
from structure import contract_eligible, select_structure

# Charter §3b provenance tag for Stage A. Stage B (the drafting layer) upgrades survivors it
# drafts to "machine_surfaced_machine_drafted"; operator-originated theses use
# "operator_sourced" (charter §3b) — neither exists in Stage A.
PROVENANCE_STAGE_A = "machine_surfaced"

# THE STAGE-B SEAM (charter §3b): the LLM thesis-drafting layer, when built (its own PR, its
# own pre-reg), replaces this section's empty body with a drafted thesis + attached falsifier
# and flips the card's provenance tag. Stage A renders it EMPTY by construction.
STAGE_B_SEAM = "Draft thesis (Stage B pending)"

# Achieved-OTM admission band, PREREG_UNIVERSE_CURATION §11 Rule 1 (operator-confirmed
# 2026-06-10): a structure outside 15–35% achieved OTM is a different payoff object than the
# calibrated ~25% cell (IE "fit" 30% ITM; LTBR/ITRI ~9% near-ATM; DRS 37% overshoot).
OTM_BAND = (0.15, 0.35)

# The RTH window for the after-hours rule (records/2026-07-08 batch3 §docket item 1): option
# quotes read outside 13:30–20:00 UTC are indicative/stale → quote-dependent axes are
# PROVISIONAL, and the card document carries the run timestamp + the flag.
RTH_START_UTC = dtime(13, 30)
RTH_END_UTC = dtime(20, 0)

# Common all-caps English words / headline acronyms that collide with real US tickers
# (A=Agilent, IT=Gartner, ALL=Allstate, SO=Southern, ON=ON Semi, NOW=ServiceNow, …).
# Precision-first (charter §3b: false positives poison the screen): these are BLOCKED in the
# exact-match pass; the names stay reachable via the cashtag / exchange-parenthetical
# patterns, which carry explicit ticker intent.
TICKER_STOPWORDS: frozenset[str] = frozenset({
    "A", "AG", "AI", "ALL", "AM", "AN", "AND", "ANY", "ARE", "AS", "AT", "BE", "BIG", "BUY",
    "BY", "CAN", "CEO", "CFO", "CO", "COO", "CORP", "CTO", "DC", "DOD", "DOE", "EPA", "EPS",
    "ETF", "EU", "EUR", "EV", "FAQ", "FBI", "FCC", "FDA", "FERC", "FOR", "FTC", "GAAP",
    "GDP", "GO", "HAS", "HE", "HER", "HIS", "HOW", "II", "III", "INC", "IPO", "IRA", "IRS",
    "IS", "IT", "ITS", "LLC", "LNG", "LOW", "LP", "LTD", "MAY", "ME", "MOU", "MY", "NEW",
    "NEXT", "NO", "NOW", "NRC", "NV", "OF", "OFF", "ON", "ONE", "OR", "OUT", "PC", "PLC",
    "PM", "PR", "RFP", "SA", "SC", "SEC", "SEE", "SET", "SHE", "SO", "SPAC", "TOP", "TV",
    "TWO", "UK", "UN", "UP", "US", "USA", "USD", "WAS", "WHO", "WHY", "YOU",
})

# $TICK cashtag: 1–5 uppercase letters, not followed by more alphanumerics ($100 never matches).
_CASHTAG_RE = re.compile(r"\$([A-Z]{1,5})(?![A-Za-z0-9])")
# (NASDAQ: XXX)-style exchange parenthetical; the exchange label is validated against a pinned set.
_EXCHANGE_PAREN_RE = re.compile(r"\(\s*([A-Za-z ]{2,16})\s*:\s*([A-Z]{1,5}(?:\.[A-Z])?)\s*\)")
_EXCHANGES = frozenset({
    "NASDAQ", "NYSE", "NYSE AMERICAN", "NYSE ARCA", "NYSEARCA", "NYSE MKT", "AMEX",
    "CBOE", "CBOE BZX", "BATS",
})
# The digest orphan-watch channel's OWN machine-generated title (digest.orphan_new_listings) —
# a high-precision pattern because we wrote it.
_ORPHAN_TITLE_RE = re.compile(r"^([A-Z][A-Z0-9]{0,4}(?:[.-][A-Z]{1,2})?): options class now listed")
_UPPER_TOKEN_RE = re.compile(r"\b[A-Z]{2,5}\b")

# The digest markdown item line (digest._item_line): "- <when> — <title>[ — <link>]".
_ITEM_LINE_RE = re.compile(r"^- (?P<when>\d{4}-\d{2}-\d{2} \d{2}:\d{2}Z|undated) — (?P<rest>.+)$")


# ── stage 1a: digest input (the seam) ─────────────────────────────────────────
def parse_digest_markdown(text: str) -> list[Item]:
    """Re-derive ``digest.Item`` rows from a written weekly digest document.

    THE DIGEST-INPUT SEAM, and why this one: the written ``records/digests/<week>.md`` file
    is the EXACT artifact the operator read. Re-running the fetch (the importable
    ``scripts/digest_weekly`` channel runners) is NOT reproducible against it — feeds move
    between runs, and the orphan watch consumes first-seen events into its snapshot, so a
    re-fetch would see a *different* item set than the digest of record. A ``--digest-json``
    side artifact would need the digest runner to start emitting a second file. Parsing the
    document back keeps Stage A offline, deterministic, and provenance-faithful; the format
    is pinned by ``tests/test_digest.py`` (``assemble`` is the single writer).

    Tolerant of the document's non-item furniture: header bullets (before any ``##``
    channel), "… N older items dropped" truncation lines, and the ``## notes`` section are
    skipped. Orphan-watch items get their ``symbol`` re-derived from the machine-generated
    title prefix.
    """
    items: list[Item] = []
    channel: str | None = None
    source: str | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            channel = line[3:].strip()
            source = None
            continue
        if line.startswith("### "):
            source = line[4:].strip()
            continue
        if channel is None or channel == "notes" or source is None:
            continue
        m = _ITEM_LINE_RE.match(line)
        if not m:
            continue
        when, rest = m.group("when"), m.group("rest")
        published = None if when == "undated" else parse_date(when)
        head, sep, tail = rest.rpartition(" — ")
        if sep and tail.startswith(("http://", "https://")):
            title, link = head, tail
        else:
            title, link = rest, ""
        symbol = None
        if channel == "orphan_watch":
            om = _ORPHAN_TITLE_RE.match(title)
            symbol = om.group(1) if om else None
        items.append(Item(channel=channel, source=source, title=title, link=link,
                          published=published, symbol=symbol))
    return items


def load_known_tickers(path: str | Path) -> frozenset[str] | None:
    """The known-universe symbol set from a cached SEC ``company_tickers.json`` (the digest's
    cache file, ``data/cache/digest/company_tickers.json`` — see ``digest.sec_ticker_map``).

    Cache-first and network-free: an absent/unreadable cache returns ``None`` and the caller
    SKIPS the exact-match extraction pass with a counted note (fail-soft — never a fetch
    from this module; the runner may populate the cache via ``digest.sec_ticker_map``)."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text())
        return frozenset(str(r["ticker"]).upper() for r in raw.values())
    except Exception:  # noqa: BLE001 — a corrupt cache degrades to no-exact-match, counted
        return None


# ── stage 1b: conservative ticker extraction ──────────────────────────────────
@dataclass(frozen=True)
class Extraction:
    """One ticker extraction with full provenance (charter §3b: every extraction records
    which item/channel surfaced it). Deliberately NO score/rank/relevance field."""

    symbol: str
    method: str  # "cashtag" | "exchange_paren" | "orphan_title" | "item_symbol" | "exact_match"
    channel: str
    source: str
    title: str
    link: str


def extract_from_item(item: Item, known: frozenset[str] | None) -> list[Extraction]:
    """High-precision ticker extractions from one digest item, in method-priority order.

    Patterns (Stage A, charter §3b — NO fuzzy name matching): the item's own ``symbol``
    field (orphan watch), the machine-generated orphan title, ``$TICK`` cashtags,
    ``(NASDAQ: XXX)``-style exchange parentheticals, and an exact-match pass of ALL-CAPS
    2–5 letter tokens against the known-universe set (``known``; skipped when ``None``)
    minus :data:`TICKER_STOPWORDS`. One extraction per symbol per item — the
    highest-priority method wins."""
    found: dict[str, str] = {}  # symbol → method (first/highest-priority wins)

    def _add(symbol: str, method: str) -> None:
        s = symbol.upper()
        if s and s not in found:
            found[s] = method

    if item.symbol:
        _add(item.symbol, "item_symbol")
    om = _ORPHAN_TITLE_RE.match(item.title)
    if om:
        _add(om.group(1), "orphan_title")
    for m in _CASHTAG_RE.finditer(item.title):
        _add(m.group(1), "cashtag")
    for m in _EXCHANGE_PAREN_RE.finditer(item.title):
        if m.group(1).strip().upper() in _EXCHANGES:
            _add(m.group(2), "exchange_paren")
    if known is not None:
        for token in _UPPER_TOKEN_RE.findall(item.title):
            if token in known and token not in TICKER_STOPWORDS:
                _add(token, "exact_match")
    return [Extraction(sym, method, item.channel, item.source, item.title, item.link)
            for sym, method in found.items()]


def extract_candidates(
    items: Iterable[Item], known: frozenset[str] | None
) -> dict[str, list[Extraction]]:
    """symbol → every :class:`Extraction` that surfaced it (multi-item provenance kept)."""
    out: dict[str, list[Extraction]] = {}
    for item in items:
        for ex in extract_from_item(item, known):
            out.setdefault(ex.symbol, []).append(ex)
    return out


# ── stage 2: restricted list (fail-CLOSED) ────────────────────────────────────
class RestrictedListError(RuntimeError):
    """``restricted.json`` exists but is unreadable/malformed → the run HALTS (fail-closed:
    a broken restricted list must never be mistaken for an empty one —
    records/2026-07-14_restricted_list_RATIFIED.md, enforcement plan)."""


def load_restricted(path: str | Path) -> tuple[frozenset[str] | None, str]:
    """Load the repo-root ``restricted.json`` (opaque entry IDs + derived ticker arrays ONLY
    — the ID→person mapping lives at the governance layer, never in the repo).

    Returns ``(tickers, status_note)``. Absent file → ``(None, WARNING note)`` and the
    caller proceeds (the enforcement PR is staged post-2026-08-02 and may not have landed);
    present-but-unreadable/malformed → :class:`RestrictedListError` (HALT). Accepts either a
    bare list of entries or ``{"entries": [...]}``; every entry must carry a ``tickers``
    array of non-empty strings."""
    p = Path(path)
    if not p.exists():
        return None, (
            "WARNING: restricted.json ABSENT — restricted-list enforcement not active on this "
            "run (the enforcement PR is staged; records/2026-07-14_restricted_list_RATIFIED.md). "
            "Proceeding UNCHECKED."
        )
    try:
        raw = json.loads(p.read_text())
        entries = raw.get("entries") if isinstance(raw, dict) else raw
        if not isinstance(entries, list):
            raise ValueError("expected a list of entries (or {'entries': [...]})")
        tickers: set[str] = set()
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("tickers"), list):
                raise ValueError(f"entry missing a 'tickers' array: {entry!r}")
            for t in entry["tickers"]:
                if not isinstance(t, str) or not t.strip():
                    raise ValueError(f"non-string/empty ticker in entry {entry.get('id')!r}")
                tickers.add(t.strip().upper())
        return frozenset(tickers), f"restricted list enforced ({len(entries)} entry/ies, {len(tickers)} ticker(s))"
    except Exception as e:
        raise RestrictedListError(
            f"restricted.json exists but is unreadable/malformed — HALTING, fail-closed "
            f"(a broken restricted list is never an empty one): {type(e).__name__}: {e}"
        ) from e


def apply_restricted(
    candidates: dict[str, list[Extraction]], restricted: frozenset[str] | None
) -> tuple[dict[str, list[Extraction]], int]:
    """Drop restricted tickers BEFORE any further processing. Returns (kept, n_dropped).

    Dropped tickers are counted, never named, in the card document — a restricted name must
    not be propagated into a fresh record file (the null-book temptation-generator clause)."""
    if not restricted:
        return dict(candidates), 0
    kept = {s: e for s, e in candidates.items() if s.upper() not in restricted}
    return kept, len(candidates) - len(kept)


# ── stage 3: the four-axis feasibility screen ─────────────────────────────────
AXES = ("price", "adv", "optionable", "band_fit")

PASS, FAIL, UNAVAILABLE = "PASS", "FAIL", "UNAVAILABLE"


@dataclass(frozen=True)
class ScreenParams:
    """The frozen floors + cap-fit arithmetic, mirrored from the established feasibility
    semantics (``scripts/probe_basket_feasibility.py`` / PREREG_UNIVERSE_CURATION §2, §11).
    Defaults = the frozen config.json values; :func:`params_from_config` reads the live ones.
    NO cheapness (IV/RV) and NO motion axis — forbidden curation criteria (§2)."""

    price_floor: float = 3.0
    adv_floor_usd: float = 3_000_000.0
    adv_window_days: int = 20
    account_equity: float = 100_000.0
    book_fraction: float = 0.10
    per_name_fraction: float = 0.01
    max_open_positions: int = 15
    tenor_min_days: int = 180
    tenor_max_days: int = 365
    target_moneyness: float = 0.25
    otm_band_lo: float = OTM_BAND[0]
    otm_band_hi: float = OTM_BAND[1]
    max_spread_pct: float = 0.25
    min_contract_price: float = 0.10
    max_contract_price: float = 100.0
    min_oi: int | None = 50


def params_from_config(config: Mapping[str, Any]) -> ScreenParams:
    """ScreenParams from the live ``config.json`` blocks (gate / book / eligibility.live) —
    the same keys the feasibility probe reads; no new thresholds."""
    gate = config["convexity_gate"]
    book = config["convexity_book"]
    elig = config["eligibility"]["live"]
    return ScreenParams(
        price_floor=float(elig.get("min_price", 3.0)),
        adv_floor_usd=float(elig.get("min_adv_usd", 3_000_000.0)),
        adv_window_days=int(elig.get("adv_window_days", 20)),
        account_equity=float(book.get("account_equity", 100_000.0)),
        book_fraction=float(book["book_fraction"]),
        per_name_fraction=float(book["per_name_fraction"]),
        max_open_positions=int(book["max_open_positions"]),
        tenor_min_days=int(gate["tenor_min_days"]),
        tenor_max_days=int(gate["tenor_max_days"]),
        target_moneyness=float(gate["target_moneyness"]),
        max_spread_pct=float(elig.get("max_bid_ask_pct", 0.25)),
        min_oi=elig.get("min_option_open_interest"),
    )


@dataclass
class MarketAccess:
    """Injected market reads (live wiring in the runner; fakes in tests). Each callable may
    raise — :func:`run_screen` is the per-axis fail-soft boundary."""

    spot: Callable[[str], float | None]
    closes: Callable[[str, int], list[float]]  # (symbol, window) → trailing closes
    adv_usd: Callable[[str], float | None]
    optionable: Callable[[str], bool]
    chain: Callable[[str], list[Contract]]


@dataclass(frozen=True)
class AxisResult:
    """One screen axis's verdict. ``provisional`` marks a quote-dependent read taken outside
    RTH (the after-hours rule). Deliberately NO score field."""

    axis: str
    status: str  # PASS | FAIL | UNAVAILABLE
    detail: str
    provisional: bool = False


@dataclass(frozen=True)
class ScreenResult:
    symbol: str
    axes: tuple[AxisResult, ...]

    @property
    def passed(self) -> bool:
        """Survivor ⇔ every axis is PASS. UNAVAILABLE is never a pass (--skip-market rule)."""
        return all(a.status == PASS for a in self.axes)

    def axis(self, name: str) -> AxisResult:
        return next(a for a in self.axes if a.axis == name)


def quotes_are_live(dt: datetime) -> bool:
    """True inside the 13:30–20:00 UTC weekday window (the after-hours rule): outside it,
    quote-dependent axes are PROVISIONAL — readable, but re-screen mid-session before acting."""
    d = dt.astimezone(UTC)
    return d.weekday() < 5 and RTH_START_UTC <= d.time() < RTH_END_UTC


def run_screen(
    symbol: str,
    *,
    market: MarketAccess | None,
    params: ScreenParams,
    as_of: date,
    quotes_live: bool,
    errors: list[str] | None = None,
) -> ScreenResult:
    """The four-axis deterministic feasibility screen for one candidate (charter §3b).

    Axes (all four recorded, pass/fail per axis — mirror of the established
    ``probe_basket_feasibility`` semantics):

    1. ``price``      — spot ≥ the eligibility price floor (bars; not quote-dependent).
    2. ``adv``        — trailing average $ volume ≥ the ADV floor (bars; not quote-dependent).
    3. ``optionable`` — an options class exists (contract-listing existence; not quote-dependent).
    4. ``band_fit``   — the production-selected structure (``structure.select_structure`` +
       ``contract_eligible``, REUSED not reinvented) achieves OTM inside the §11 15–35% band
       AND one contract fits the frozen per-name cap (``convexity_sizing`` reused). This is
       the QUOTE-DEPENDENT axis: outside RTH it is marked PROVISIONAL.

    ``market=None`` (--skip-market, keyless) → every axis UNAVAILABLE — never passed.
    Per-axis fail-soft: an exception marks that axis UNAVAILABLE and is COUNTED into
    ``errors`` (dead-arm ≠ quiet-arm), never raises out of the screen.
    """
    sym = symbol.upper()
    if market is None:
        skip = "--skip-market (keyless run): not measured, NOT passed"
        return ScreenResult(sym, tuple(
            AxisResult(a, UNAVAILABLE, skip, provisional=False) for a in AXES
        ))

    axes: list[AxisResult] = []

    # 1. price floor
    spot: float | None = None
    try:
        spot = market.spot(sym)
        if spot is None or spot <= 0:
            axes.append(AxisResult("price", UNAVAILABLE, "no underlying price"))
        elif spot >= params.price_floor:
            axes.append(AxisResult("price", PASS, f"spot ${spot:.2f} >= ${params.price_floor:g} floor"))
        else:
            axes.append(AxisResult("price", FAIL, f"spot ${spot:.2f} < ${params.price_floor:g} floor"))
    except Exception as e:  # noqa: BLE001 — per-axis fail-soft, counted
        if errors is not None:
            errors.append(f"{sym}/price: {type(e).__name__}: {e}")
        axes.append(AxisResult("price", UNAVAILABLE, f"error: {e}"))

    # 2. ADV floor
    try:
        adv = market.adv_usd(sym)
        if adv is None:
            axes.append(AxisResult("adv", UNAVAILABLE, "no bars for ADV"))
        elif adv >= params.adv_floor_usd:
            axes.append(AxisResult(
                "adv", PASS, f"ADV ${adv / 1e6:.1f}M >= ${params.adv_floor_usd / 1e6:.1f}M floor"))
        else:
            axes.append(AxisResult(
                "adv", FAIL, f"ADV ${adv / 1e6:.1f}M < ${params.adv_floor_usd / 1e6:.1f}M floor"))
    except Exception as e:  # noqa: BLE001
        if errors is not None:
            errors.append(f"{sym}/adv: {type(e).__name__}: {e}")
        axes.append(AxisResult("adv", UNAVAILABLE, f"error: {e}"))

    # 3. optionability (existence event — the digest's options_class_exists check, injected)
    try:
        axes.append(AxisResult("optionable", PASS, "options class listed")
                    if market.optionable(sym)
                    else AxisResult("optionable", FAIL, "no options class"))
    except Exception as e:  # noqa: BLE001
        if errors is not None:
            errors.append(f"{sym}/optionable: {type(e).__name__}: {e}")
        axes.append(AxisResult("optionable", UNAVAILABLE, f"error: {e}"))

    # 4. band-fit + per-contract premium vs the per-name cap (quote-dependent → provisional
    #    outside RTH). Wing selection is the production path: select_structure over the live
    #    chain with the frozen tenor/target-moneyness + contract_eligible floors (REUSE).
    provisional = not quotes_live
    try:
        axes.append(_band_fit_axis(sym, spot, market, params, as_of, provisional))
    except Exception as e:  # noqa: BLE001
        if errors is not None:
            errors.append(f"{sym}/band_fit: {type(e).__name__}: {e}")
        axes.append(AxisResult("band_fit", UNAVAILABLE, f"error: {e}", provisional))

    return ScreenResult(sym, tuple(axes))


def _band_fit_axis(
    sym: str,
    spot: float | None,
    market: MarketAccess,
    params: ScreenParams,
    as_of: date,
    provisional: bool,
) -> AxisResult:
    """Axis 4: the achieved-OTM band fit (§11's 15–35%) + one contract under the per-name cap."""
    if spot is None or spot <= 0:
        return AxisResult("band_fit", UNAVAILABLE, "no underlying price", provisional)
    chain = market.chain(sym)

    def _elig(c: Contract) -> tuple[bool, tuple[str, ...]]:
        return contract_eligible(
            c, max_spread_pct=params.max_spread_pct,
            min_contract_price=params.min_contract_price,
            max_contract_price=params.max_contract_price, min_oi=params.min_oi,
        )

    # Call side screened as the canonical structure (feasibility, not direction — the
    # probe_basket_feasibility convention; put premiums are same-scale).
    st, why = select_structure(
        chain, direction="bullish", as_of=as_of, underlying_price=spot,
        tenor_min_days=params.tenor_min_days, tenor_max_days=params.tenor_max_days,
        target_moneyness=params.target_moneyness, eligibility=_elig, underlying_symbol=sym,
    )
    if st is None:
        return AxisResult("band_fit", FAIL, f"no structure ({why[0] if why else '?'})", provisional)
    per_contract = st.entry_premium * 100.0
    sizing = convexity_position_size(
        account_equity=params.account_equity, book_fraction=params.book_fraction,
        per_name_fraction=params.per_name_fraction, max_open_positions=params.max_open_positions,
        open_positions_count=0, open_premium_total=0.0, entry_premium_per_share=st.entry_premium,
    )
    per_name_cap = params.account_equity * params.per_name_fraction
    ach = st.moneyness  # signed (strike − spot)/spot; calls: positive = OTM
    in_band = params.otm_band_lo <= ach <= params.otm_band_hi
    fits = sizing.contracts >= 1
    detail = (f"{st.contract.symbol} dte {st.dte}, achieved OTM {ach * 100.0:.1f}% "
              f"(band {params.otm_band_lo * 100:.0f}-{params.otm_band_hi * 100:.0f}%), "
              f"${per_contract:.0f}/contract vs ${per_name_cap:.0f} cap")
    if in_band and fits:
        return AxisResult("band_fit", PASS, detail, provisional)
    reasons = ([] if in_band else ["achieved OTM outside band"]) + ([] if fits else ["over per-name cap"])
    return AxisResult("band_fit", FAIL, f"{detail} — {'; '.join(reasons)}", provisional)


# ── stage 4: premise-currency pull (mechanical — numbers only, no judgment) ───
@dataclass(frozen=True)
class PremiseCurrency:
    """The numbers a premise-currency read needs (charter §3b Rule-5 stage) — mechanical
    pulls only, NO judgment, NO score field. ``None`` = unavailable (cache-miss honesty:
    a data gap is never rendered as a zero)."""

    ret_1m: float | None
    ret_12m: float | None
    analyst_count: int | None
    analyst_asof: str | None       # ISO date of the cached snapshot (staleness honesty)
    last_periodic_filing: str | None      # e.g. "10-Q 2026-05-08"
    structural_filings: tuple[str, ...]   # newest-first, e.g. ("424B5 2026-06-30", ...)


def trailing_returns(closes: list[float] | None) -> tuple[float | None, float | None]:
    """(1-month, 12-month) trailing simple returns from daily closes (21/252 trading days).
    Insufficient history → ``None`` for that horizon (never a partial-window guess)."""
    if not closes:
        return None, None
    px = [c for c in closes if c is not None and c > 0]
    r1 = (px[-1] / px[-22] - 1.0) if len(px) >= 22 else None
    r12 = (px[-1] / px[-253] - 1.0) if len(px) >= 253 else None
    return r1, r12


_PERIODIC_FORMS = allowed_forms(["10-K", "10-Q"])


def latest_periodic_filing(records: list[dict[str, Any]] | None) -> str | None:
    """Most recent 10-K/10-Q (incl. /A) from cached filing records → ``"FORM YYYY-MM-DD"``."""
    newest = _newest_filings(records, _PERIODIC_FORMS, 1)
    return newest[0] if newest else None


def recent_structural_filings(
    records: list[dict[str, Any]] | None,
    event_forms: frozenset[str],
    n: int = 3,
) -> tuple[str, ...]:
    """The ``n`` most recent structural filings (the event-leg pinned form set,
    ``data.structural_events.allowed_forms`` — EXACT membership, never a prefix)."""
    return tuple(_newest_filings(records, event_forms, n))


def _newest_filings(records: list[dict[str, Any]] | None, forms: frozenset[str],
                    n: int) -> list[str]:
    matched: list[tuple[str, str]] = []
    for r in records or []:
        form = str(r.get("form", ""))
        ts = str(r.get("ts", ""))
        if form in forms and ts:
            matched.append((ts, form))
    matched.sort(reverse=True)  # ISO timestamps sort lexicographically = newest first
    return [f"{form} {ts[:10]}" for ts, form in matched[:n]]


def build_premise(
    closes: list[float] | None,
    filings_records: list[dict[str, Any]] | None,
    analyst_record: dict[str, Any] | None,
    event_forms: frozenset[str],
) -> PremiseCurrency:
    """Assemble one survivor's premise-currency block from raw pulls (pure)."""
    r1, r12 = trailing_returns(closes)
    count = asof = None
    if analyst_record:
        c = analyst_record.get("analyst_count")
        count = int(c) if isinstance(c, (int, float)) else None
        ts = str(analyst_record.get("ts", ""))
        asof = ts[:10] or None
    return PremiseCurrency(
        ret_1m=r1, ret_12m=r12, analyst_count=count, analyst_asof=asof,
        last_periodic_filing=latest_periodic_filing(filings_records),
        structural_filings=recent_structural_filings(filings_records, event_forms),
    )


# ── stage 5: card assembly (alphabetical — NO ranking of any kind) ────────────
@dataclass(frozen=True)
class SurvivorCard:
    """One screen survivor's card. ``provenance`` is the charter §3b tag — Stage A emits
    ``machine_surfaced``; Stage B adds ``machine_surfaced_machine_drafted`` when the drafting
    layer lands. Deliberately NO score/rank field (guard-tested)."""

    symbol: str
    surfaced_via: tuple[Extraction, ...]
    screen: ScreenResult
    premise: PremiseCurrency | None
    provenance: str = PROVENANCE_STAGE_A


def draft_thesis_section(card: SurvivorCard) -> list[str]:
    """THE STAGE-B SEAM (charter §3b). Stage B — the LLM thesis-drafting layer, NOT built in
    Stage A — replaces this empty body with a drafted thesis + attached falsifier and flips
    the card's provenance to ``machine_surfaced_machine_drafted``. Stage A renders the
    section EMPTY by construction (no LLM calls anywhere in this module)."""
    return [
        f"### {STAGE_B_SEAM}",
        "",
        "_(empty — Stage B, the thesis-drafting layer, is not built; everything above this "
        "line is mechanical.)_",
        "",
    ]


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100.0:+.1f}%"


def _axis_line(a: AxisResult) -> str:
    flag = " (PROVISIONAL — quotes read outside 13:30-20:00 UTC)" if (
        a.provisional and a.status != UNAVAILABLE) else ""
    return f"  - {a.axis}: {a.status}{flag} — {a.detail}"


def _card_lines(card: SurvivorCard) -> list[str]:
    lines = [f"## {card.symbol}", "", f"- provenance: {card.provenance}", "- surfaced via:"]
    for ex in card.surfaced_via:
        link = f" — {ex.link}" if ex.link else ""
        lines.append(f"  - {ex.channel}/{ex.source} [{ex.method}] — {ex.title}{link}")
    lines.append("- screen:")
    lines += [_axis_line(a) for a in card.screen.axes]
    p = card.premise
    lines.append("- premise currency:")
    if p is None:
        lines.append("  - (unavailable — market/cache pulls skipped)")
    else:
        lines.append(f"  - trailing return 1m / 12m: {_pct(p.ret_1m)} / {_pct(p.ret_12m)}")
        lines.append(
            f"  - analyst count: {p.analyst_count} (cached {p.analyst_asof})"
            if p.analyst_count is not None
            else "  - analyst count: n/a (not in cache)"
        )
        lines.append(f"  - last 10-K/10-Q: {p.last_periodic_filing or 'n/a (not in cache)'}")
        sf = [s for s in p.structural_filings if s]
        lines.append(
            "  - recent structural filings (event-leg forms): " + (" · ".join(sf) if sf
                                                                   else "none in cache")
        )
    lines.append("")
    lines += draft_thesis_section(card)
    return lines


def _screened_out_line(sr: ScreenResult) -> str:
    failed = [a.axis for a in sr.axes if a.status == FAIL]
    unavailable = [a.axis for a in sr.axes if a.status == UNAVAILABLE]
    if failed:
        head = f"failed {'+'.join(failed)}"
    elif unavailable:
        head = "screen unavailable"
    else:  # pragma: no cover — a passing result never reaches Screened out
        head = "?"
    states = " · ".join(f"{a.axis} {a.status}{'*' if a.provisional else ''}" for a in sr.axes)
    return f"- {sr.symbol} — {head} [{states}]"


def assemble_cards(
    survivors: list[SurvivorCard],
    screened_out: list[ScreenResult],
    *,
    week: str,
    digest_path: str,
    restricted_note: str,
    n_extracted: int,
    n_restricted_dropped: int,
    quotes_live: bool,
    notes: list[str],
    errors: list[str],
    generated_at: datetime | None = None,
) -> str:
    """One survivor-card markdown document (charter §3b). Survivors AND screen-failures are
    ordered ALPHABETICALLY — compression only by the sanctioned deterministic steps, never by
    ranking. Screen-failures are listed compactly with every axis state (never silently
    dropped). ``generated_at`` is injectable so tests pin a deterministic document."""
    gen = (generated_at or datetime.now(UTC)).astimezone(UTC)
    survivors = sorted(survivors, key=lambda c: c.symbol)
    screened_out = sorted(screened_out, key=lambda s: s.symbol)
    quote_ctx = ("live (13:30-20:00 UTC)" if quotes_live
                 else "PROVISIONAL — generated outside 13:30-20:00 UTC; quote-dependent axes "
                      "must be re-screened mid-session before acting")
    head = [
        f"# Survivor cards — {week}",
        "",
        f"- generated: {gen.isoformat(timespec='seconds')}",
        f"- digest: {digest_path}",
        f"- quote context: {quote_ctx}",
        f"- restricted list: {restricted_note}",
        f"- restricted drops: {n_restricted_dropped} candidate(s) dropped before screening "
        "(tickers withheld from this document)",
        f"- funnel: {n_extracted} extracted -> {len(survivors) + len(screened_out)} screened "
        f"-> {len(survivors)} survivor(s)",
        "- ordering: alphabetical (no ranking anywhere — charter §3b)",
        "- stage: A (deterministic; no LLM calls). Stage B drafting pending.",
        "",
    ]
    body: list[str] = []
    if not survivors:
        body += ["(no survivors this week)", ""]
    for card in survivors:
        body += _card_lines(card)
    body += ["## Screened out", ""]
    if screened_out:
        body += [_screened_out_line(s) for s in screened_out]
    else:
        body.append("(none)")
    body.append("")
    tail: list[str] = []
    if notes or errors:
        tail = ["## notes", ""] + [f"- {n}" for n in notes] + [
            f"- FAILED — {e}" for e in errors] + [""]
    return "\n".join(head + body + tail)
