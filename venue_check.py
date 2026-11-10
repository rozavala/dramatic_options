"""Venue-vs-journal expiry check (#444, option (a) of records/2026-11-10_expiry_exercise_audit_DRAFT.md).

The broker auto-exercises an in-the-money long option at expiry by default (the draft's F1). Five code paths can
leave a real contract at the venue while the journal shows it closed: the unsellable in-DB close, the closed-market
in-DB close (removed by #451), expiry booked at intrinsic on the expiry date's first tick, expiry while closing, and
a close that never fills. The journal models no exercise, so a held contract that finishes in the money becomes
stock nothing in the book knows about. This check sees that divergence before expiry, and pages it.

Each L2 tick (market open or closed), for every REAL-book contract (``convexity_positions``, long legs and a
vertical's short leg) whose row held exposure (``open``, ``closing`` or ``closed``):

- **Before expiry** (expiry on or after today, ET): read the venue quantity of that ONE contract
  (``broker.venue_quantity``, the §3a.3 per-contract read; never an account listing, since the live account is
  shared) and compare it with the journal's open + closing quantity (``state.journal_contract_quantity``'s rule).
  A row in flight widens what counts as a match: a ``closing`` sell may already have filled (wholly or partly)
  before the monitor reconciles it, and a ``pending`` buy may already have filled. A vertical's legs fill together
  (one atomic multi-leg order), so a pair used only by verticals must also agree jointly: long + short on the venue
  equals long + short in the journal.
- **After expiry**, for ``POST_EXPIRY_TRADING_DAYS`` NYSE trading days: read the contract once more (expected 0)
  and, on a paper account only, the underlying's share quantity (expected 0: the journal holds no stock, so shares
  there mean an exercise or assignment). On the live account the operator's own stock makes that read ambiguous;
  it is not taken (#468). Account activities (``OPEXC`` / ``OPEXP``) list account-wide events and need the
  operator's word under §3a.3 (the draft's D5), so they are not read.

Paging: ONE digest page per tick, listing every finding that is due this tick; its priority is the highest among
them (1 within ``PRIORITY_TRADING_DAYS`` NYSE trading days of expiry, and after it). Each finding is debounced per
(kind, contract or symbol, ET day), stamped in its rows' rationale ``paged`` dict (``monitor._page_once``'s dict;
no state file) only AFTER the digest was delivered, so an undelivered page is retried next tick. An orphan BY DESIGN
(the venue holds no more than the unsellable in-DB closes booked, same sign) is paged when first seen, then only
inside the priority window and after expiry; every other kind is due daily. Each line names the days to expiry
and the underlying's distance to the strike.

**Read-only. Telemetry and paging only.** Nothing here submits, cancels or edits an order, closes a position or
changes a row's status, quantity or price; the only write is the debounce stamp in a row's rationale.

Fail-soft, never fail-silent: a read that fails (``None`` or an exception), one not reached inside the budget, or a
row whose expiry cannot be parsed, is an UNKNOWN: counted, logged at WARNING, paged, and named in the run note. It
is never read as a match.

The calendar (``nyse_calendar``) covers 2026–2027; past it, trading days degrade to weekdays (holidays counted as
sessions) until the table is extended.

Off under DRY_RUN: nothing was transmitted, so the venue holds nothing the journal booked, and every open row would
read as a mismatch. The null books (``shadow_positions``, ``fixed_basket_positions``) never broker and are never read.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import nyse_calendar

log = logging.getLogger("venue_check")

ET = ZoneInfo("America/New_York")

# The draft's window: within 5 NYSE trading days of expiry a difference pages at priority 1.
PRIORITY_TRADING_DAYS = 5
# "After the expiry date, read the contract once more": the exercise settles overnight, so the first L2 tick of the
# next session sees the shares. Two trading days so one missed tick (a failed unit, a restart) still sees it.
POST_EXPIRY_TRADING_DAYS = 2
# The L2 unit's TimeoutStartSec is 180 s and the monitor pass runs first. Checked between reads (an in-flight read can
# overrun it by its own timeout); contracts not read inside it are UNKNOWN.
BUDGET_SECONDS = 30.0
NOTE_MAX = 10
PAGE_BODY_MAX = 1000   # Pushover caps the body at 1024 (notify.send truncates); the tail names what was cut

PAGE_KEY_PREFIX = "venue_check:"   # key in a real row's rationale ``paged`` dict (monitor._page_once's dict)
SCOPE_STATES = ("open", "closing", "closed")
KIND_LABEL = {
    "orphan": "expected orphan (the venue holds what the unsellable close booked closed)",
    "closed_but_held": "the venue holds a contract the journal shows closed",
    "quantity": "the venue quantity differs from the journal's",
    "held_after_expiry": "the venue still holds the contract after its expiry",
    "shares_after_expiry": "the venue holds shares of the underlying after an expiry (exercise or assignment?)",
    "unknown": "UNKNOWN, not a match",
}


@dataclass
class Leg:
    """One contract's journal view, over every real row that holds it (long leg or a vertical's short leg)."""

    contract: str
    symbol: str
    kind: str                 # "C" | "P"
    strike: float | None
    expiry: date
    exact: int = 0            # open + closing, signed (a short leg is negative): the journal's quantity
    lo: int = 0               # the widest match range once in-flight rows (closing, pending) are allowed for
    hi: int = 0
    unsellable: int = 0       # signed contracts of the closed rows the unsellable in-DB close booked
    row_ids: list[int] = field(default_factory=list)          # open / closing / closed rows (debounce stamps)
    statuses: dict[int, str] = field(default_factory=dict)
    reasons: dict[int, str] = field(default_factory=dict)     # closed rows' exit_reason
    pairs: set[tuple[str, str]] = field(default_factory=set)  # (long, short) of the vertical rows using this contract
    single: bool = False      # some row uses it as a single-leg position


@dataclass(frozen=True)
class Finding:
    key: str                  # the contract, or the underlying for a share read
    kind: str
    detail: str
    priority: int
    row_ids: tuple[int, ...]
    symbol: str
    shares: bool = False      # a share read (counted apart from the contract reads)


@dataclass
class CheckResult:
    contracts: int = 0
    matched: int = 0
    shares_matched: int = 0
    rows_skipped_window: int = 0
    budget_skipped: int = 0
    shares_read: bool = False
    findings: list[Finding] = field(default_factory=list)
    paged: int = 0            # findings in a DELIVERED digest
    digest: str = "none"      # "none" | "sent" | "undelivered"
    legs: dict[str, Leg] = field(default_factory=dict)   # contract -> its journal view (for the page copy)

    def _of(self, shares: bool, unknown: bool) -> list[Finding]:
        return [f for f in self.findings if f.shares == shares and (f.kind == "unknown") == unknown]

    def status(self) -> str:
        """``contracts`` = ``match`` + ``mismatch`` + ``unknown`` (contract reads); share reads are counted apart."""
        shares = (f"shares_match={self.shares_matched} shares_mismatch={len(self._of(True, False))} "
                  f"shares_unknown={len(self._of(True, True))}" if self.shares_read else "shares=off")
        return (f"venue_check: contracts={self.contracts} match={self.matched} "
                f"mismatch={len(self._of(False, False))} unknown={len(self._of(False, True))} {shares} "
                f"budget_skipped={self.budget_skipped} paged={self.paged} digest={self.digest} "
                f"skipped_window={self.rows_skipped_window} "
                f"window=prio{PRIORITY_TRADING_DAYS}td/post{POST_EXPIRY_TRADING_DAYS}td")


# ── time (ET dates, NYSE sessions) ───────────────────────────────────────────────────────────────────────────────
def et_date(now: datetime) -> date:
    """The ET calendar date of ``now`` (a naive ``now`` is read as UTC, as ``clock.Clock`` promises)."""
    from datetime import UTC

    return (now if now.tzinfo is not None else now.replace(tzinfo=UTC)).astimezone(ET).date()


def trading_days_between(a: date, b: date) -> int:
    """NYSE trading days ``d`` with ``a < d <= b``; 0 when ``b <= a``."""
    n, d = 0, a
    while d < b:
        d += timedelta(days=1)
        if nyse_calendar.is_trading_day(d):
            n += 1
    return n


def _parse_expiry(value: Any, contract: str) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        from options_tradability import parse_osi

        info = parse_osi(str(contract))
        return info["expiry"] if info else None


# ── the journal side ─────────────────────────────────────────────────────────────────────────────────────────────
def _widen(leg: Leg, signed: int) -> None:
    """An in-flight row's venue quantity may be anything between 0 and its signed quantity."""
    leg.lo += min(0, signed)
    leg.hi += max(0, signed)


@dataclass
class Journal:
    pre: list[Leg]
    post: list[Leg]
    skipped: int
    bad_expiry: list[Finding]   # in-scope rows whose expiry cannot be parsed: UNKNOWN, never skipped


def journal_legs(conn, today: date) -> Journal:
    """The REAL book only (``convexity_positions``), split into pre- and post-expiry contracts.

    A contract is in scope when it has an ``open``/``closing``/``closed`` row and its expiry is on or after ``today``
    (pre), or before it by at most ``POST_EXPIRY_TRADING_DAYS`` NYSE sessions (post). ``pending`` rows only widen the
    match range of a contract already in scope; ``carried`` intents and ``cancelled`` rows hold nothing."""
    rows = conn.execute(
        "SELECT id, symbol, structure_kind, contract_symbol, strike, short_contract_symbol, short_strike, contracts, "
        "status, expiry, exit_reason FROM convexity_positions "
        "WHERE status IN ('open', 'closing', 'closed', 'pending') ORDER BY id").fetchall()
    legs: dict[str, Leg] = {}
    skipped = 0
    bad: list[Finding] = []
    for r in rows:
        status, pid = r["status"], int(r["id"])
        expiry = _parse_expiry(r["expiry"], r["contract_symbol"])
        if expiry is None:
            if status in SCOPE_STATES:
                log.warning("venue check: #%d %s has an unparsable expiry %r — UNKNOWN, not checked", pid,
                            r["contract_symbol"], r["expiry"])
                bad.append(Finding(str(r["contract_symbol"]), "unknown",
                                   f"#{pid} {status}: expiry {r['expiry']!r} unparsable, so it was not checked", 1,
                                   (pid,), str(r["symbol"]).upper()))
            continue
        # (today − expiry) ≤ 7 calendar days first: two sessions never span more, and an old row costs no day walk
        in_window = expiry >= today or (
            (today - expiry).days <= 7 and trading_days_between(expiry, today) <= POST_EXPIRY_TRADING_DAYS)
        if not in_window:
            if status in SCOPE_STATES:
                skipped += 1
            continue
        n = int(r["contracts"] or 0)
        short = r["short_contract_symbol"]
        sides = [(r["contract_symbol"], n, r["strike"])] + ([(short, -n, r["short_strike"])] if short else [])
        for contract, signed, strike in sides:
            leg = legs.get(contract)
            if leg is None:
                leg = legs[contract] = Leg(contract=contract, symbol=str(r["symbol"]).upper(),
                                           kind=str(r["structure_kind"] or "C").upper()[:1],
                                           strike=(float(strike) if strike is not None else None), expiry=expiry)
            if short:
                leg.pairs.add((r["contract_symbol"], short))
            else:
                leg.single = True
            if status == "open":
                leg.exact += signed
                leg.lo += signed
                leg.hi += signed
            elif status == "closing":
                leg.exact += signed
                _widen(leg, signed)
            elif status == "pending":
                _widen(leg, signed)
            if status in SCOPE_STATES:
                leg.row_ids.append(pid)
                leg.statuses[pid] = status
                if status == "closed":
                    leg.reasons[pid] = str(r["exit_reason"] or "")
                    if leg.reasons[pid].endswith("_unsellable"):
                        leg.unsellable += signed
    scoped = [leg for leg in legs.values() if leg.row_ids]   # a pending-only contract is not in scope
    scoped.sort(key=lambda g: (g.expiry, g.contract))        # nearest expiry first: the budget goes where it matters
    return Journal([g for g in scoped if g.expiry >= today], [g for g in scoped if g.expiry < today], skipped, bad)


# ── copy ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def distance_to_strike(leg: Leg, spot: float | None) -> str:
    """'X% OTM' / 'X% ITM' of the underlying vs this leg's strike; 'distance unknown' without both prices."""
    if spot is None or not leg.strike:
        return "distance to strike unknown"
    pct = (float(spot) / leg.strike - 1.0) * 100.0
    itm = pct > 0 if leg.kind == "C" else pct < 0
    return f"underlying {float(spot):.2f} vs strike {leg.strike:g}: {abs(pct):.1f}% {'ITM' if itm else 'OTM'}"


def _rows_text(leg: Leg) -> str:
    parts = []
    for pid in leg.row_ids:
        st = leg.statuses[pid]
        parts.append(f"#{pid} {st}" + (f" ({leg.reasons[pid]})" if st == "closed" and leg.reasons.get(pid) else ""))
    return ", ".join(parts)


def orphan_by_design(leg: Leg, venue: int) -> bool:
    """The venue holds no more than the unsellable in-DB closes booked closed, with the same sign (a short leg is
    negative). Anything else (more, the other sign, or no unsellable close at all) the journal does not explain."""
    u = leg.unsellable
    return venue != 0 and u != 0 and (venue > 0) == (u > 0) and abs(venue) <= abs(u)


def _why_closed(leg: Leg, today: date) -> str:
    if leg.expiry >= today and any(r == "expiry" for r in leg.reasons.values()):
        return "The journal booked expiry at intrinsic before the venue's expiry processing (#444 path 3)."
    return "The journal explains none of it."


# ── the check ────────────────────────────────────────────────────────────────────────────────────────────────────
def _read(read_qty: Callable[[str], Any], symbol: str) -> int | None:
    try:
        q = read_qty(symbol)
    except Exception as e:  # noqa: BLE001 — a failed read is UNKNOWN, never zero and never a match
        log.warning("venue check: venue read raised for %s: %s", symbol, e)
        return None
    if q is None:
        log.warning("venue check: venue read failed for %s (UNKNOWN, not a match)", symbol)
        return None
    try:
        return int(q)
    except (TypeError, ValueError):
        log.warning("venue check: venue read for %s returned %r (UNKNOWN)", symbol, q)
        return None


def _joint_vertical_findings(res: CheckResult, venues: dict[str, int], matched: set[str],
                             prio_of: dict[str, int]) -> None:
    """A vertical opens and closes as ONE multi-leg order, so in flight both legs move together: long + short on the
    venue equals long + short in the journal. Checked where each leg passed alone and the pair is used only by
    verticals (a single-leg row in either contract could move one leg by itself)."""
    for leg in res.legs.values():
        for long_c, short_c in sorted(leg.pairs):
            if leg.contract != long_c or long_c not in matched or short_c not in matched:
                continue
            lg, sg = res.legs[long_c], res.legs[short_c]
            if lg.single or sg.single or lg.pairs != {(long_c, short_c)} or sg.pairs != {(long_c, short_c)}:
                continue
            if venues[long_c] + venues[short_c] == lg.exact + sg.exact:
                continue
            res.matched -= 2
            matched -= {long_c, short_c}
            rows = tuple(sorted(set(lg.row_ids) | set(sg.row_ids)))
            detail = (f"vertical legs disagree: venue long {venues[long_c]} / short {venues[short_c]} ({short_c}); "
                      f"the journal holds {lg.exact} / {sg.exact} (rows {_rows_text(lg)}); one atomic order moves both")
            log.warning("venue check: %s quantity — %s", long_c, detail)
            prio = prio_of.get(long_c, 0)
            res.findings.append(Finding(long_c, "quantity", detail, prio, rows, lg.symbol))
            res.findings.append(Finding(short_c, "quantity", detail, prio, rows, sg.symbol))


def venue_journal_check(conn, read_qty: Callable[[str], Any], today: date, *, read_shares: bool = False,
                        budget_s: float = BUDGET_SECONDS,
                        monotonic: Callable[[], float] = time.monotonic) -> CheckResult:
    """Compare the venue with the journal, per contract. ``read_qty(symbol)`` is ``broker.venue_quantity``.

    Pure apart from the reads: writes nothing, pages nobody (``dispose`` does). ``today`` is the ET date."""
    j = journal_legs(conn, today)
    res = CheckResult(contracts=len(j.pre) + len(j.post) + len(j.bad_expiry), rows_skipped_window=j.skipped,
                      shares_read=read_shares, legs={g.contract: g for g in j.pre + j.post})
    res.findings.extend(j.bad_expiry)
    start = monotonic()
    venues: dict[str, int] = {}
    matched: set[str] = set()
    prio_of: dict[str, int] = {}

    def over_budget() -> bool:
        return monotonic() - start > budget_s

    for leg in j.post + j.pre:   # post-expiry first: the exercise question is the most urgent
        expired = leg.expiry < today
        tdte = trading_days_between(today, leg.expiry)
        prio = prio_of[leg.contract] = 1 if expired or tdte <= PRIORITY_TRADING_DAYS else 0
        when = (f"expired {leg.expiry.isoformat()}" if expired
                else f"{tdte} NYSE trading day(s) to expiry {leg.expiry.isoformat()}")
        rows = tuple(leg.row_ids)
        if over_budget():
            res.budget_skipped += 1
            res.findings.append(Finding(leg.contract, "unknown", f"not read inside the {budget_s:g}s budget; {when}",
                                        prio, rows, leg.symbol))
            continue
        venue = _read(read_qty, leg.contract)
        if venue is None:
            res.findings.append(Finding(leg.contract, "unknown", f"venue read failed; {when}", prio, rows, leg.symbol))
            continue
        venues[leg.contract] = venue
        if expired:
            if venue == 0:
                res.matched += 1
                continue
            kind, detail = "held_after_expiry", f"venue holds {venue}, expected 0; rows {_rows_text(leg)}; {when}"
        elif leg.lo <= venue <= leg.hi:
            res.matched += 1
            matched.add(leg.contract)
            continue
        elif not any(leg.statuses[pid] in ("open", "closing") for pid in leg.row_ids):
            if orphan_by_design(leg, venue):
                kind, detail = "orphan", (f"venue holds {venue}, the unsellable in-DB close booked {leg.unsellable} "
                                          f"closed and sent no order (#444 path 1; rows {_rows_text(leg)}); {when}")
            else:
                kind, detail = "closed_but_held", (f"venue holds {venue}, the journal holds 0 "
                                                   f"(rows {_rows_text(leg)}); {when}. {_why_closed(leg, today)}")
        else:
            rng = f"{leg.exact}" if leg.lo == leg.hi else f"{leg.exact} (in flight: {leg.lo}..{leg.hi})"
            kind, detail = "quantity", f"venue holds {venue}, the journal holds {rng} (rows {_rows_text(leg)}); {when}"
        log.warning("venue check: %s %s — %s", leg.contract, kind, detail)
        res.findings.append(Finding(leg.contract, kind, detail, prio, rows, leg.symbol))

    _joint_vertical_findings(res, venues, matched, prio_of)

    if read_shares:   # paper only: the journal holds no stock, so any share here is an exercise or an assignment
        by_symbol: dict[str, list[Leg]] = {}
        for leg in j.post:
            by_symbol.setdefault(leg.symbol, []).append(leg)
        for sym, legs in sorted(by_symbol.items()):
            rows = tuple(sorted({pid for g in legs for pid in g.row_ids}))
            what = ", ".join(f"{g.contract} (expired {g.expiry.isoformat()})" for g in legs)
            if over_budget():
                res.budget_skipped += 1
                res.findings.append(Finding(sym, "unknown", f"share read not reached inside the {budget_s:g}s budget; "
                                            f"after {what}", 1, rows, sym, shares=True))
                continue
            shares = _read(read_qty, sym)
            if shares is None:
                res.findings.append(Finding(sym, "unknown", f"share read failed; after {what}", 1, rows, sym,
                                            shares=True))
            elif shares == 0:
                res.shares_matched += 1
            else:
                detail = f"the paper venue holds {shares} share(s) of {sym}, which the journal never holds; after {what}"
                log.warning("venue check: %s shares_after_expiry — %s", sym, detail)
                res.findings.append(Finding(sym, "shares_after_expiry", detail, 1, rows, sym, shares=True))
    return res


# ── paging: one digest per tick, each finding debounced in its rows' rationale ──────────────────────────────────
def _stamp_key(f: Finding) -> str:
    return f"{PAGE_KEY_PREFIX}{f.kind}:{f.key}"


def _rationale(raw: Any) -> dict:
    """A row's rationale as a dict: NULL/empty is ``{}``; unparsable or non-dict JSON is kept under a key."""
    if not raw:
        return {}
    try:
        rat = json.loads(raw)
    except (TypeError, ValueError):
        return {"_unparsed_rationale": raw}
    if rat is None:
        return {}
    return rat if isinstance(rat, dict) else {"_rationale": rat}


def _rationales(conn, ids: set[int]) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for pid in sorted(ids):
        row = conn.execute("SELECT rationale FROM convexity_positions WHERE id = ?", (pid,)).fetchone()
        if row is not None:
            out[pid] = _rationale(row["rationale"])
    return out


def is_due(f: Finding, rats: dict[int, dict], today: date) -> bool:
    """Daily per (kind, key, ET day); an orphan by design only when first seen, then in the priority window (and
    after expiry, where it is a ``held_after_expiry`` finding of its own)."""
    key = _stamp_key(f)
    stamps = []
    for pid in f.row_ids:
        paged = rats.get(pid, {}).get("paged")
        if isinstance(paged, dict) and paged.get(key):
            stamps.append(paged[key])
    if today.isoformat() in stamps:
        return False
    if f.kind == "orphan" and stamps:
        return f.priority >= 1
    return True


def _stamp(conn, due: list[Finding], rats: dict[int, dict], today: date) -> None:
    """Record the delivered findings in their rows' rationale ``paged`` dict (the only write this module makes)."""
    touched: set[int] = set()
    for f in due:
        for pid in f.row_ids:
            if pid in rats:
                rat = rats[pid]
                paged = rat.get("paged") if isinstance(rat.get("paged"), dict) else {}
                paged[_stamp_key(f)] = today.isoformat()
                rat["paged"] = paged
                touched.add(pid)
    with conn:
        for pid in sorted(touched):
            conn.execute("UPDATE convexity_positions SET rationale = ? WHERE id = ?",
                         (json.dumps(rats[pid], default=str), pid))


def _spot(underlying_price_of: Callable[[str], Any] | None, symbol: str) -> float | None:
    if underlying_price_of is None:
        return None
    try:
        p = underlying_price_of(symbol)
        return float(p) if p is not None else None
    except Exception as e:  # noqa: BLE001 — the page goes out without the distance
        log.warning("venue check: underlying price for %s failed (distance unknown): %s", symbol, e)
        return None


def digest(res: CheckResult, due: list[Finding], underlying_price_of: Callable[[str], Any] | None) -> tuple[str, str, int]:
    """``(title, body, priority)`` of the one page for this tick's due findings, highest priority first."""
    spots: dict[str, float | None] = {}
    lines = []
    for f in due:
        leg = res.legs.get(f.key)
        dist = ""
        if leg is not None and f.kind != "unknown":
            if f.symbol not in spots:
                spots[f.symbol] = _spot(underlying_price_of, f.symbol)
            dist = "; " + distance_to_strike(leg, spots[f.symbol])
        lines.append(f"- {f.key} [{KIND_LABEL[f.kind]}]: {f.detail}{dist}")
    head = f"Read-only check (#444): nothing was sent, cancelled, closed or changed. {len(due)} finding(s):"
    body, shown = head, 0
    for line in lines:
        if len(body) + 1 + len(line) > PAGE_BODY_MAX - 40:
            break
        body, shown = body + "\n" + line, shown + 1
    if shown < len(lines):
        body += f"\n+{len(lines) - shown} more (see the run note)"
    syms = list(dict.fromkeys(f.symbol for f in due))
    label = "VENUE READ UNKNOWN" if all(f.kind == "unknown" for f in due) else "VENUE ≠ JOURNAL"
    title = f"{label}: " + ", ".join(syms[:5]) + (f" +{len(syms) - 5}" if len(syms) > 5 else "")
    return title, body, max(f.priority for f in due)


def dispose(conn, res: CheckResult, today: date, *, run_id: int | None,
            notify_send: Callable[..., Any], underlying_price_of: Callable[[str], Any] | None = None) -> str:
    """Send one digest of the due findings, stamp them only if it was delivered, then log the status line and append
    it to the run note. Returns the line. Paging never raises."""
    try:
        rats = _rationales(conn, {pid for f in res.findings for pid in f.row_ids})
        due = sorted((f for f in res.findings if is_due(f, rats, today)), key=lambda f: -f.priority)
        if due:
            title, body, prio = digest(res, due, underlying_price_of)
            try:
                delivered = bool(notify_send(title, body, priority=prio))
            except Exception as e:  # noqa: BLE001 — an undelivered page; retried next tick
                log.warning("venue check: digest page raised: %s", e)
                delivered = False
            if delivered:
                _stamp(conn, due, rats, today)
                res.digest, res.paged = "sent", len(due)
            else:   # notify.send returns False when undelivered: no stamp, so the next tick retries
                res.digest = "undelivered"
                log.warning("venue check: digest of %d finding(s) NOT delivered — retried next tick", len(due))
    except Exception as e:  # noqa: BLE001 — paging never breaks the cycle
        log.warning("venue check: paging failed: %s", e)
    line = res.status()
    mm = [f for f in res.findings if f.kind != "unknown"]
    if mm:
        more = len(mm) - NOTE_MAX
        line += " mismatches=" + ",".join(f"{f.key}:{f.kind}" for f in mm[:NOTE_MAX]) + (f",+{more}" if more > 0 else "")
    unk = [f for f in res.findings if f.kind == "unknown"]
    if unk:
        more = len(unk) - NOTE_MAX
        line += " unknown_keys=" + ",".join(f.key for f in unk[:NOTE_MAX]) + (f",+{more}" if more > 0 else "")
    if mm or unk:
        log.warning("%s — fail-soft is not fail-silent", line)
    else:
        log.info("%s", line)
    if run_id is not None:
        import state

        state.append_run_note(conn, run_id, line)
    return line


def run_tick(conn, *, broker, clock, dry_run: bool, paper_account: bool, run_id: int | None,
             underlying_price_of: Callable[[str], Any] | None = None, notify_send: Callable[..., Any] | None = None,
             monotonic: Callable[[], float] = time.monotonic) -> str:
    """The L2 entry point (one fail-soft call in ``orchestrator.run_once``, after the monitor pass). Returns the line.

    ``dry_run`` is the CONFIGURED DRY_RUN, not the monitor's closed-market override: the check runs on closed ticks.
    ``paper_account`` allows the post-expiry share read (never on the shared live account)."""
    if dry_run or not callable(getattr(broker, "venue_quantity", None)):
        line = ("venue_check: off (DRY_RUN: nothing was transmitted, so the venue holds nothing the journal booked)"
                if dry_run else "venue_check: off (the broker has no per-contract venue read)")
        log.info("%s", line)
        if run_id is not None:
            import state

            state.append_run_note(conn, run_id, line)
        return line
    if notify_send is None:
        import notify

        notify_send = notify.send
    today = et_date(clock.now())
    res = venue_journal_check(conn, broker.venue_quantity, today, read_shares=bool(paper_account),
                              monotonic=monotonic)
    return dispose(conn, res, today, run_id=run_id, notify_send=notify_send, underlying_price_of=underlying_price_of)
