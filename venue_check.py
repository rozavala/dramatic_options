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
  before the monitor reconciles it, and a ``pending`` buy may already have filled.
- **After expiry**, for ``POST_EXPIRY_TRADING_DAYS`` NYSE trading days: read the contract once more (expected 0)
  and, on a paper account only, the underlying's share quantity (expected 0: the journal holds no stock, so shares
  there mean an exercise or assignment). On the live account the operator's own stock makes that read ambiguous;
  it is not taken (#468). Account activities (``OPEXC`` / ``OPEXP``) list account-wide events and need the
  operator's word under §3a.3 (the draft's D5), so they are not read.

A difference pages once per (contract, kind of mismatch, ET day), stamped in the rows' rationale ``paged`` dict as
``monitor._page_once`` does; no state file. Within ``PRIORITY_TRADING_DAYS`` NYSE trading days of expiry, and after
it, the page is priority 1. Every page names the days to expiry and the underlying's distance to the strike. A row
the unsellable close booked is an orphan BY DESIGN, and its page says so.

**Read-only. Telemetry and paging only.** Nothing here submits, cancels or edits an order, closes a position or
changes a row's status, quantity or price; the only write is the debounce stamp in a row's rationale.

Fail-soft, never fail-silent: a read that fails (``None`` or an exception), or one not reached inside the budget, is
an UNKNOWN: counted, logged at WARNING, paged, and named in the run note. It is never read as a match.

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

PAGE_KEY_PREFIX = "venue_check:"   # key in a real row's rationale ``paged`` dict (monitor._page_once's dict)
SCOPE_STATES = ("open", "closing", "closed")
KINDS = ("closed_but_held", "quantity", "held_after_expiry", "shares_after_expiry", "unknown")
KIND_LABEL = {
    "closed_but_held": "the venue holds a contract the journal shows closed",
    "quantity": "the venue quantity differs from the journal's",
    "held_after_expiry": "the venue still holds the contract after its expiry",
    "shares_after_expiry": "the venue holds shares of the underlying after an expiry (exercise or assignment?)",
    "unknown": "the venue read failed (UNKNOWN, not a match)",
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
    row_ids: list[int] = field(default_factory=list)          # open / closing / closed rows (debounce stamps)
    statuses: dict[int, str] = field(default_factory=dict)
    reasons: dict[int, str] = field(default_factory=dict)     # closed rows' exit_reason


@dataclass(frozen=True)
class Finding:
    key: str                  # the contract, or the underlying for a share read
    kind: str
    venue: int | None
    detail: str
    priority: int
    row_ids: tuple[int, ...]
    symbol: str


@dataclass
class CheckResult:
    contracts: int = 0
    matched: int = 0
    rows_skipped_window: int = 0
    budget_skipped: int = 0
    shares_read: bool = False
    findings: list[Finding] = field(default_factory=list)
    paged: int = 0
    legs: dict[str, Leg] = field(default_factory=dict)   # contract -> its journal view (for the page copy)

    def count(self, kind: str) -> int:
        return sum(1 for f in self.findings if f.kind == kind)

    def mismatches(self) -> list[Finding]:
        return [f for f in self.findings if f.kind != "unknown"]

    def unknowns(self) -> list[Finding]:
        return [f for f in self.findings if f.kind == "unknown"]

    def status(self) -> str:
        return (f"venue_check: contracts={self.contracts} match={self.matched} mismatch={len(self.mismatches())} "
                f"unknown={len(self.unknowns())} budget_skipped={self.budget_skipped} paged={self.paged} "
                f"skipped_window={self.rows_skipped_window} shares={'on' if self.shares_read else 'off'} "
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


def journal_legs(conn, today: date) -> tuple[list[Leg], list[Leg], int]:
    """``(pre_expiry, post_expiry, rows_skipped)`` over the REAL book only (``convexity_positions``).

    A contract is in scope when it has an ``open``/``closing``/``closed`` row and its expiry is on or after ``today``
    (pre), or before it by at most ``POST_EXPIRY_TRADING_DAYS`` NYSE sessions (post). ``pending`` rows only widen the
    match range of a contract already in scope; ``carried`` intents and ``cancelled`` rows hold nothing."""
    rows = conn.execute(
        "SELECT id, symbol, structure_kind, contract_symbol, strike, short_contract_symbol, short_strike, contracts, "
        "status, expiry, exit_reason FROM convexity_positions "
        "WHERE status IN ('open', 'closing', 'closed', 'pending') ORDER BY id").fetchall()
    legs: dict[str, Leg] = {}
    skipped = 0
    for r in rows:
        expiry = _parse_expiry(r["expiry"], r["contract_symbol"])
        # (today − expiry) ≤ 7 calendar days first: two sessions never span more, and an old row costs no day walk
        in_window = expiry is not None and (expiry >= today or (
            (today - expiry).days <= 7 and trading_days_between(expiry, today) <= POST_EXPIRY_TRADING_DAYS))
        if not in_window:
            if r["status"] in SCOPE_STATES:
                skipped += 1
            continue
        n = int(r["contracts"] or 0)
        sides = [(r["contract_symbol"], n, r["strike"])]
        if r["short_contract_symbol"]:
            sides.append((r["short_contract_symbol"], -n, r["short_strike"]))
        for contract, signed, strike in sides:
            leg = legs.get(contract)
            if leg is None:
                leg = legs[contract] = Leg(contract=contract, symbol=str(r["symbol"]).upper(),
                                           kind=str(r["structure_kind"] or "C").upper()[:1],
                                           strike=(float(strike) if strike is not None else None), expiry=expiry)
            status, pid = r["status"], int(r["id"])
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
    scoped = [leg for leg in legs.values() if leg.row_ids]   # a pending-only contract is not in scope
    scoped.sort(key=lambda g: (g.expiry, g.contract))        # nearest expiry first: the budget goes where it matters
    return [g for g in scoped if g.expiry >= today], [g for g in scoped if g.expiry < today], skipped


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


def _why_closed(leg: Leg, today: date) -> str:
    reasons = [r for pid, r in leg.reasons.items() if leg.statuses.get(pid) == "closed"]
    if any(r.endswith("_unsellable") for r in reasons):
        return ("Orphan by design: the unsellable in-DB close booked it at the mark and sent no order (#444 path 1); "
                "the venue keeps it until expiry.")
    if leg.expiry >= today and any(r == "expiry" for r in reasons):
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


def venue_journal_check(conn, read_qty: Callable[[str], Any], today: date, *, read_shares: bool = False,
                        budget_s: float = BUDGET_SECONDS,
                        monotonic: Callable[[], float] = time.monotonic) -> CheckResult:
    """Compare the venue with the journal, per contract. ``read_qty(symbol)`` is ``broker.venue_quantity``.

    Pure apart from the reads: writes nothing, pages nobody (``dispose`` does). ``today`` is the ET date."""
    pre, post, skipped = journal_legs(conn, today)
    res = CheckResult(contracts=len(pre) + len(post), rows_skipped_window=skipped, shares_read=read_shares,
                      legs={g.contract: g for g in pre + post})
    start = monotonic()

    def over_budget() -> bool:
        return monotonic() - start > budget_s

    def unknown(key: str, symbol: str, rows: list[int], prio: int, what: str) -> None:
        res.findings.append(Finding(key, "unknown", None, what, prio, tuple(rows), symbol))

    for leg in post + pre:   # post-expiry first: the exercise question is the most urgent
        expired = leg.expiry < today
        tdte = trading_days_between(today, leg.expiry)
        prio = 1 if expired or tdte <= PRIORITY_TRADING_DAYS else 0
        when = (f"expired {leg.expiry.isoformat()}" if expired
                else f"{tdte} NYSE trading day(s) to expiry {leg.expiry.isoformat()}")
        if over_budget():
            res.budget_skipped += 1
            unknown(leg.contract, leg.symbol, leg.row_ids, prio, f"not read inside the {budget_s:g}s budget; {when}")
            continue
        venue = _read(read_qty, leg.contract)
        if venue is None:
            unknown(leg.contract, leg.symbol, leg.row_ids, prio, f"venue read failed; {when}")
            continue
        if expired:
            if venue == 0:
                res.matched += 1
                continue
            kind, detail = "held_after_expiry", (f"venue holds {venue}, expected 0 after expiry; journal rows "
                                                 f"{_rows_text(leg)}; {when}")
        elif leg.lo <= venue <= leg.hi:
            res.matched += 1
            continue
        elif not any(leg.statuses[pid] in ("open", "closing") for pid in leg.row_ids):
            kind, detail = "closed_but_held", (f"venue holds {venue}, the journal holds 0 (rows {_rows_text(leg)}); "
                                               f"{when}. {_why_closed(leg, today)}")
        else:
            rng = f"{leg.exact}" if leg.lo == leg.hi else f"{leg.exact} (in flight: {leg.lo}..{leg.hi})"
            kind, detail = "quantity", f"venue holds {venue}, the journal holds {rng} (rows {_rows_text(leg)}); {when}"
        log.warning("venue check: %s %s — %s", leg.contract, kind, detail)
        res.findings.append(Finding(leg.contract, kind, venue, detail, prio, tuple(leg.row_ids), leg.symbol))

    if read_shares:   # paper only: the journal holds no stock, so any share here is an exercise or an assignment
        by_symbol: dict[str, list[Leg]] = {}
        for leg in post:
            by_symbol.setdefault(leg.symbol, []).append(leg)
        for sym, legs in sorted(by_symbol.items()):
            rows = sorted({pid for g in legs for pid in g.row_ids})
            what = ", ".join(f"{g.contract} (expired {g.expiry.isoformat()})" for g in legs)
            if over_budget():
                res.budget_skipped += 1
                unknown(sym, sym, rows, 1, f"share read not reached inside the {budget_s:g}s budget; after {what}")
                continue
            shares = _read(read_qty, sym)
            if shares is None:
                unknown(sym, sym, rows, 1, f"share read failed; after {what}")
            elif shares == 0:
                res.matched += 1
            else:
                detail = (f"the paper venue holds {shares} share(s) of {sym}, which the journal never holds; "
                          f"after {what}")
                log.warning("venue check: %s shares_after_expiry — %s", sym, detail)
                res.findings.append(Finding(sym, "shares_after_expiry", shares, detail, 1, tuple(rows), sym))
    return res


# ── paging (debounced in the rows' rationale) ────────────────────────────────────────────────────────────────────
def page_once(conn, finding: Finding, today: date, *, notify_send: Callable[..., Any], body: str) -> bool:
    """Page ``finding`` at most once per (key, kind, ET day). The stamp ``venue_check:<kind>:<key>`` = the ET date
    goes into every row's rationale ``paged`` dict (``monitor._page_once``'s dict), written before the push, as
    ``_page_once`` does. Returns True when it paged. Never raises."""
    key = f"{PAGE_KEY_PREFIX}{finding.kind}:{finding.key}"
    stamp = today.isoformat()
    try:
        rats: list[tuple[int, dict]] = []
        for pid in finding.row_ids:
            row = conn.execute("SELECT rationale FROM convexity_positions WHERE id = ?", (pid,)).fetchone()
            if row is None:
                continue
            try:
                rat = json.loads(row["rationale"]) if row["rationale"] else {}
            except (TypeError, ValueError):
                rat = {"_unparsed_rationale": row["rationale"]}
            rats.append((pid, rat if isinstance(rat, dict) else {"_rationale": rat}))
        if not rats:
            return False
        if any(isinstance(r.get("paged"), dict) and r["paged"].get(key) == stamp for _, r in rats):
            return False
        with conn:
            for pid, rat in rats:
                paged = rat.get("paged") if isinstance(rat.get("paged"), dict) else {}
                paged[key] = stamp
                rat["paged"] = paged
                conn.execute("UPDATE convexity_positions SET rationale = ? WHERE id = ?",
                             (json.dumps(rat, default=str), pid))
        title = ("VENUE READ UNKNOWN" if finding.kind == "unknown" else "VENUE ≠ JOURNAL") + f": {finding.symbol}"
        notify_send(title, body, priority=finding.priority)
        return True
    except Exception as e:  # noqa: BLE001 — paging never breaks the cycle
        log.warning("venue check: page for %s %s failed: %s", finding.key, finding.kind, e)
        return False


def _spot(underlying_price_of: Callable[[str], Any] | None, symbol: str) -> float | None:
    if underlying_price_of is None:
        return None
    try:
        p = underlying_price_of(symbol)
        return float(p) if p is not None else None
    except Exception as e:  # noqa: BLE001 — the page goes out without the distance
        log.warning("venue check: underlying price for %s failed (distance unknown): %s", symbol, e)
        return None


def dispose(conn, res: CheckResult, today: date, *, run_id: int | None,
            notify_send: Callable[..., Any], underlying_price_of: Callable[[str], Any] | None = None) -> str:
    """Page each finding (debounced), then log the status line and append it to the run note. Returns the line."""
    spots: dict[str, float | None] = {}
    for f in res.findings:
        leg = res.legs.get(f.key)
        if leg is not None:
            if f.symbol not in spots:
                spots[f.symbol] = _spot(underlying_price_of, f.symbol)
            dist = distance_to_strike(leg, spots[f.symbol])
        else:
            dist = ""
        body = (f"{f.key}: {KIND_LABEL[f.kind]}. {f.detail}" + (f"; {dist}" if dist else "") +
                ". Read-only check (#444): nothing was sent, cancelled, closed or changed.")
        if page_once(conn, f, today, notify_send=notify_send, body=body):
            res.paged += 1
    line = res.status()
    mm = res.mismatches()
    if mm:
        more = len(mm) - NOTE_MAX
        line += " mismatches=" + ",".join(f"{f.key}:{f.kind}" for f in mm[:NOTE_MAX]) + (f",+{more}" if more > 0 else "")
    unk = res.unknowns()
    if unk:
        more = len(unk) - NOTE_MAX
        line += " unknown=" + ",".join(f.key for f in unk[:NOTE_MAX]) + (f",+{more}" if more > 0 else "")
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
