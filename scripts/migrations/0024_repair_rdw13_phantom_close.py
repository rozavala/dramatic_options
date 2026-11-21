"""Migration 0024 — revert the 2026-11-18 phantom close of real-book position #13 (#534; incident #533 / #444).

At the L2 opening tick of 2026-11-18 a broken quote (bid 0, ask ≈20.2) marked #13 (RDW270521P00006000, a $6 put) at
10.10, past the 10× profit-take; the bid was under ``min_close_bid``, so the pre-#444 monitor booked an in-DB
``profit_take_10x_unsellable`` close (+$9,150) and sent nothing. The broker still holds all 10 contracts. The close
(``monitor._close_and_resolve``) wrote three rows, and this reverts exactly what it wrote:

* ``convexity_positions`` #13 — ``state.close_convexity_position`` set status, mark, realized_pnl, exit_reason,
  closed_at and marked_at (contracts / total_premium are COALESCEd with None when there was no partial close, so
  unchanged). Reverted: status 'open'; mark and marked_at NULL (the junk mark overwrote the last real one, so the
  next L2 re-marks it); realized_pnl, exit_reason and closed_at NULL. A dated note goes into its rationale JSON.
* ``council_proposals`` #1342 — ``state.resolve_proposal`` set outcome, brier, resolved_at. Reverted to NULL.
* ``sentinel_candidates`` #26 — ``state.resolve_sentinel`` set outcome, brier, realized_multiple, reference_return
  (None), terminal_event ('traded') and resolved_at. Reverted to NULL (reference_return is already NULL).

Each row is changed only if it is still in the exact phantom state (every field the close wrote, plus its identity).
Anything else — already repaired, a different row under that id (another host's DB), or a missing row — leaves that
row untouched and prints why. No other row is touched. Idempotent: after a repair no guard matches again. On a DB
without these rows (a fresh test DB, or a host where #13 is not this position) it is a no-op.

Deploy only together with (or after) the #533 mark bound and the #527 orphan policy, so the same junk quote cannot
book the row closed again.
"""

from __future__ import annotations

import json
import sqlite3

POSITION_ID, PROPOSAL_ID, SENTINEL_ID = 13, 1342, 26
CONTRACT = "RDW270521P00006000"
PHANTOM_AT = "2026-11-18T14:30:00.969652+00:00"     # the close's as_of: closed_at, marked_at and both resolved_at
PHANTOM_MARK, PHANTOM_PNL = 10.1, 9150.0
PHANTOM_REASON = "profit_take_10x_unsellable"
NOTE_KEY = "repaired_2026-11-19"
NOTE = ("phantom close reverted (#533/#534): it had been booked closed at " + PHANTOM_AT + " as " + PHANTOM_REASON +
        " at mark 10.10 with realized_pnl +9150 while the broker still held all 10 contracts; status, mark, "
        "marked_at, realized_pnl, exit_reason and closed_at reset; proposal #1342 and sentinel #26 resolutions cleared")


def _say(msg: str) -> None:
    print(f"  0024: {msg}")


def _near(a, b: float) -> bool:
    return a is not None and abs(float(a) - b) < 1e-6


def _repair_position(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT symbol, contract_symbol, status, exit_reason, realized_pnl, close_order_id, mark, closed_at, "
        "marked_at, rationale FROM convexity_positions WHERE id = ?", (POSITION_ID,)).fetchone()
    if row is None:
        _say(f"position #{POSITION_ID} not found — nothing to repair")
        return
    symbol, contract, status, reason, pnl, close_oid, mark, closed_at, marked_at, rationale = tuple(row)
    expected = {"symbol": (symbol, "RDW"), "contract_symbol": (contract, CONTRACT), "status": (status, "closed"),
                "exit_reason": (reason, PHANTOM_REASON), "close_order_id": (close_oid, None),
                "closed_at": (closed_at, PHANTOM_AT), "marked_at": (marked_at, PHANTOM_AT)}
    off = [f"{k}={got!r}" for k, (got, want) in expected.items() if got != want]
    if not _near(pnl, PHANTOM_PNL):
        off.append(f"realized_pnl={pnl!r}")
    if not _near(mark, PHANTOM_MARK):
        off.append(f"mark={mark!r}")
    if off:
        _say(f"position #{POSITION_ID} left untouched — not in the phantom state ({', '.join(off)})")
        return
    try:
        rat = json.loads(rationale) if rationale else {}
    except (TypeError, ValueError):
        _say(f"position #{POSITION_ID} left untouched — its rationale is not JSON")
        return
    if not isinstance(rat, dict):
        _say(f"position #{POSITION_ID} left untouched — its rationale is not a JSON object")
        return
    rat[NOTE_KEY] = NOTE
    conn.execute(
        "UPDATE convexity_positions SET status = 'open', mark = NULL, marked_at = NULL, realized_pnl = NULL, "
        "exit_reason = NULL, closed_at = NULL, rationale = ? WHERE id = ? AND status = 'closed'",
        (json.dumps(rat), POSITION_ID))
    _say(f"position #{POSITION_ID} {CONTRACT} reopened (phantom +$9,150 close reverted; next L2 re-marks it)")


def _repair_proposal(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT position_id, sentinel_id, outcome, resolved_at FROM council_proposals WHERE id = ?",
                       (PROPOSAL_ID,)).fetchone()
    if row is None:
        _say(f"proposal #{PROPOSAL_ID} not found — nothing to repair")
        return
    position_id, sentinel_id, outcome, resolved_at = tuple(row)
    if (position_id, sentinel_id, outcome, resolved_at) != (POSITION_ID, SENTINEL_ID, 1, PHANTOM_AT):
        _say(f"proposal #{PROPOSAL_ID} left untouched — not the phantom resolution (position_id={position_id!r}, "
             f"sentinel_id={sentinel_id!r}, outcome={outcome!r}, resolved_at={resolved_at!r})")
        return
    conn.execute("UPDATE council_proposals SET outcome = NULL, brier = NULL, resolved_at = NULL WHERE id = ?",
                 (PROPOSAL_ID,))
    _say(f"proposal #{PROPOSAL_ID} resolution cleared")


def _repair_sentinel(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT proposal_id, outcome, terminal_event, reference_return, resolved_at "
                       "FROM sentinel_candidates WHERE id = ?", (SENTINEL_ID,)).fetchone()
    if row is None:
        _say(f"sentinel #{SENTINEL_ID} not found — nothing to repair")
        return
    proposal_id, outcome, terminal_event, reference_return, resolved_at = tuple(row)
    if (proposal_id, outcome, terminal_event, reference_return, resolved_at) != (PROPOSAL_ID, 1, "traded", None,
                                                                                PHANTOM_AT):
        _say(f"sentinel #{SENTINEL_ID} left untouched — not the phantom resolution (proposal_id={proposal_id!r}, "
             f"outcome={outcome!r}, terminal_event={terminal_event!r}, reference_return={reference_return!r}, "
             f"resolved_at={resolved_at!r})")
        return
    conn.execute("UPDATE sentinel_candidates SET outcome = NULL, brier = NULL, realized_multiple = NULL, "
                 "terminal_event = NULL, resolved_at = NULL WHERE id = ?", (SENTINEL_ID,))
    _say(f"sentinel #{SENTINEL_ID} resolution cleared")


def apply(conn: sqlite3.Connection) -> None:
    # No ``with conn`` here: the runner wraps each migration in its own transaction.
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if "convexity_positions" in tables:
        _repair_position(conn)
    if "council_proposals" in tables:
        _repair_proposal(conn)
    if "sentinel_candidates" in tables:
        _repair_sentinel(conn)
