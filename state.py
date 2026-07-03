"""SQLite state/journal store.

Phase 0 creates only the ``runs`` table (+ the ``schema_version`` tracking table,
owned by the migration runner). Later phases add ``signals``/``theses``/``orders``/
``positions`` via their own migrations once those columns are actually designed.

WAL mode is enabled so the future intraday monitor can read while the orchestrator
writes. Writes use the connection as a context manager for atomic transactions.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open (creating parent dirs) a WAL-mode SQLite connection."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    # WAL lets a reader run while a writer holds the lock, but NOT two writers. The L1 entry
    # cycle and the L2 monitor are distinct timer-fired processes (T2.5) that can overlap (a
    # manual start, or a Persistent catch-up), so a second writer must WAIT for the lock rather
    # than throw SQLITE_BUSY immediately (which could orphan a half-written pending order).
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def get_db(config: dict[str, Any]) -> sqlite3.Connection:
    """Open the database at the configured path (default data/dramatic_options.db)."""
    db_path = config.get("database", {}).get("path", "data/dramatic_options.db")
    return connect(db_path)


def record_run(
    conn: sqlite3.Connection,
    *,
    mode: str,
    equity: float | None,
    note: str = "",
    frame_version: str | None = None,
    data_feed: str | None = None,
    discovery_funnel: str | None = None,
) -> int:
    """Insert a row into ``runs`` and return its id. Atomic.

    ``frame_version`` (migration 0009) stamps the live risk-frame/taxonomy version so positions — real
    and shadow, both carrying ``run_id`` — segment by risk regime at T4 and the breach audit can ask
    "was this entry admitted under the THEN-LIVE frame" (PREREG §5 cluster-cap amendment).
    ``data_feed`` (migration 0013) likewise stamps the resolved feed roles so the record segments
    by data regime (the gate's RV/option inputs + the discovery funnel hang off these).
    ``discovery_funnel`` (migration 0015) stamps the live discovery-prescreen funnel version so the
    forward-scored layers that join on ``run_id`` (the discovery null, the framer, the council Brier)
    segment by funnel regime — OLD (NULL = pre-re-target) vs NEW (PREREG_FRESH_INFLECTION_FUNNEL).
    """
    with conn:  # commits on success, rolls back on exception
        cur = conn.execute(
            "INSERT INTO runs (started_at, mode, equity, note, frame_version, data_feed, discovery_funnel) "
            "VALUES (datetime('now'), ?, ?, ?, ?, ?, ?)",
            (mode, equity, note, frame_version, data_feed, discovery_funnel),
        )
    return int(cur.lastrowid)


def append_run_note(conn: sqlite3.Connection, run_id: int, suffix: str) -> None:
    """Append ``suffix`` to an existing run's free-text note (atomic).

    ``record_run`` fires BEFORE the discovery scan, but the event-leg counters exist only AFTER
    it (PREREG_EVENT_LEG §4) — this is the post-scan write path that makes the scan status
    DB-durable (journald rotates; the runs row doesn't)."""
    with conn:
        conn.execute("UPDATE runs SET note = note || ' · ' || ? WHERE id = ?", (suffix, run_id))


def record_signals(
    conn: sqlite3.Connection,
    run_id: int | None,
    rows: list[dict[str, Any]],
) -> int:
    """Insert watchlist signal rows (name- and theme-scope). Returns the count inserted.

    Each row: ``as_of, scope, theme, symbol, narrative, substance, divergence, direction,
    rank, rationale`` (rationale is JSON-encoded by the caller or a dict). Atomic.
    """
    import json

    with conn:  # commits on success, rolls back on exception
        for r in rows:
            rationale = r.get("rationale")
            if not isinstance(rationale, str):
                rationale = json.dumps(rationale, default=str)
            conn.execute(
                "INSERT INTO signals (run_id, as_of, scope, theme, symbol, narrative, "
                "substance, divergence, direction, rank, rationale, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
                (
                    run_id, r["as_of"], r["scope"], r.get("theme"), r.get("symbol"),
                    r.get("narrative"), r.get("substance"), r["divergence"],
                    r.get("direction"), r.get("rank"), rationale,
                ),
            )
    return len(rows)


def record_convexity_eval(
    conn: sqlite3.Connection,
    *,
    run_id: int | None,
    as_of: str,
    theme: str,
    symbol: str,
    direction: str,
    decision: str,
    eligible: bool | None = None,
    gate_cheap: bool | None = None,
    iv_rv: float | None = None,
    otm_skew: float | None = None,
    position_id: int | None = None,
    proposal_id: int | None = None,
    reasons: Any = None,
    cluster_state: dict | None = None,
) -> int:
    """Append a survivorship-log row for EVERY evaluated bet (open or veto). Atomic.

    This is the only honest basis for judging edge vs. luck (PREREG_THEMATIC_CONVEXITY §5):
    every evaluation is recorded, winners and zeros alike. Append-only — never updated.
    ``proposal_id`` links the row back to the council proposal it came from (T2 forensics:
    "council proposed HIGH conviction, the IV gate vetoed it anyway").
    """
    import json

    # cluster_state (PREREG §5 amendment, un-backfillable): the per-decision cluster snapshot — name,
    # committed premium, cap, equity — so a future breach audit can RECOMPUTE within-cap-ness at the
    # admission instead of trusting the enforcement code. Nested under the existing reasons column only
    # when present, so every non-cluster call site stays byte-identical.
    payload = reasons if cluster_state is None else {"reasons": reasons, "cluster_state": cluster_state}
    if not isinstance(payload, str):
        payload = json.dumps(payload, default=str)
    with conn:
        cur = conn.execute(
            "INSERT INTO convexity_eval (run_id, evaluated_at, theme, symbol, direction, "
            "eligible, gate_cheap, iv_rv, otm_skew, decision, position_id, proposal_id, reasons, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
            (
                run_id, as_of, theme, symbol, direction,
                None if eligible is None else int(eligible),
                None if gate_cheap is None else int(gate_cheap),
                iv_rv, otm_skew, decision, position_id, proposal_id, payload,
            ),
        )
    return int(cur.lastrowid)


def record_gate_dualread(
    conn: sqlite3.Connection,
    *,
    run_id: int | None,
    as_of: str,
    symbol: str,
    feed: str,
    source: str,
    structured: bool | None = None,
    iv_rv: float | None = None,
    otm_skew: float | None = None,
    cheap: bool | None = None,
    wing: str | None = None,
    note: str | None = None,
) -> int:
    """Append one dual-read arm row (PREREG_DATA_FEED_OPRA_SEQUENCING §6). Append-only.

    ``feed`` = 'opra' (the gate-of-record verdict) | 'indicative' (the additive shadow arm).
    A failed arm is STILL a row (structured=0 + note) — the both-arms coverage guard."""
    with conn:
        cur = conn.execute(
            "INSERT INTO gate_dualread (run_id, evaluated_at, symbol, feed, source, structured, "
            "iv_rv, otm_skew, cheap, wing, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
            (
                run_id, as_of, symbol, feed, source,
                None if structured is None else int(structured),
                iv_rv, otm_skew,
                None if cheap is None else int(cheap),
                wing, note,
            ),
        )
    return int(cur.lastrowid)


def record_convexity_position(
    conn: sqlite3.Connection,
    *,
    run_id: int | None,
    opened_at: str,
    theme: str,
    symbol: str,
    direction: str,
    structure_kind: str,
    contract_symbol: str,
    expiry: str,
    strike: float,
    dte: int,
    moneyness: float,
    contracts: int,
    entry_premium_per_contract: float,
    total_premium: float,
    rationale: Any = None,
    status: str = "open",
    order_id: str | None = None,
    proposal_id: int | None = None,
    entry_spot: float | None = None,
) -> int:
    """Insert a paper position. Returns its id. Atomic.

    ``status`` is 'open' for a simulated/confirmed fill, or 'pending' when a real Alpaca
    order is resting and awaiting reconciliation (then ``order_id`` carries the broker id).
    ``proposal_id`` links a council-proposed trade back to its proposal (T2); ``entry_spot``
    captures the underlying price at entry — the robust basis for forward outcome resolution.
    """
    import json

    if not isinstance(rationale, str):
        rationale = json.dumps(rationale, default=str)
    with conn:
        cur = conn.execute(
            "INSERT INTO convexity_positions (run_id, opened_at, theme, symbol, direction, "
            "structure_kind, contract_symbol, expiry, strike, dte, moneyness, contracts, "
            "entry_premium_per_contract, total_premium, status, mark, rationale, order_id, "
            "proposal_id, entry_spot) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)",
            (
                run_id, opened_at, theme, symbol, direction, structure_kind, contract_symbol,
                expiry, strike, dte, moneyness, contracts, entry_premium_per_contract,
                total_premium, status, rationale, order_id, proposal_id, entry_spot,
            ),
        )
    return int(cur.lastrowid)


def open_convexity_positions(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """All currently-open convexity positions."""
    return conn.execute(
        "SELECT * FROM convexity_positions WHERE status = 'open' ORDER BY id"
    ).fetchall()


def pending_convexity_positions(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Positions whose real (non-dry) Alpaca order is resting / not yet confirmed filled."""
    return conn.execute(
        "SELECT * FROM convexity_positions WHERE status = 'pending' ORDER BY id"
    ).fetchall()


def mark_convexity_position(
    conn: sqlite3.Connection, position_id: int, *, mark: float, as_of: str
) -> None:
    """Update an open position's per-contract mark (mid) + marked_at timestamp. Atomic."""
    with conn:
        conn.execute(
            "UPDATE convexity_positions SET mark = ?, marked_at = ? WHERE id = ?",
            (float(mark), as_of, position_id),
        )


def confirm_convexity_fill(
    conn: sqlite3.Connection,
    position_id: int,
    *,
    entry_premium_per_contract: float,
    total_premium: float,
    opened_at: str,
) -> None:
    """Flip a 'pending' position to 'open' at the actual fill price (reconciliation). Atomic."""
    with conn:
        conn.execute(
            "UPDATE convexity_positions SET status = 'open', "
            "entry_premium_per_contract = ?, total_premium = ?, opened_at = ? WHERE id = ?",
            (float(entry_premium_per_contract), float(total_premium), opened_at, position_id),
        )


def close_convexity_position(
    conn: sqlite3.Connection,
    position_id: int,
    *,
    exit_price: float,
    realized_pnl: float,
    reason: str,
    as_of: str,
) -> None:
    """Close a position: status='closed', store exit mark, realized P&L, reason. Atomic."""
    with conn:
        conn.execute(
            "UPDATE convexity_positions SET status = 'closed', mark = ?, realized_pnl = ?, "
            "exit_reason = ?, closed_at = ?, marked_at = ? WHERE id = ?",
            (float(exit_price), float(realized_pnl), reason, as_of, as_of, position_id),
        )


def drop_convexity_position(conn: sqlite3.Connection, position_id: int, *, reason: str) -> None:
    """Mark a never-filled pending order as 'cancelled' (reconciliation). Atomic."""
    with conn:
        conn.execute(
            "UPDATE convexity_positions SET status = 'cancelled', exit_reason = ? WHERE id = ?",
            (reason, position_id),
        )


def closing_positions(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Positions whose real SELL_TO_CLOSE is resting / not yet confirmed filled (T2.5)."""
    return conn.execute(
        "SELECT * FROM convexity_positions WHERE status = 'closing' ORDER BY id"
    ).fetchall()


def begin_close_convexity_position(
    conn: sqlite3.Connection, position_id: int, *, close_order_id: str, reason: str, as_of: str
) -> None:
    """Flip an open position to 'closing' with the resting sell's broker id (T2.5). Atomic.

    The position keeps its real exposure (counts against caps/drawdown) until the sell fills;
    ``exit_reason`` records WHY we're exiting (profit_take/time_stop) for the eventual close.
    """
    with conn:
        conn.execute(
            "UPDATE convexity_positions SET status = 'closing', close_order_id = ?, "
            "exit_reason = ?, marked_at = ? WHERE id = ?",
            (close_order_id, reason, as_of, position_id),
        )


def revert_closing_to_open(conn: sqlite3.Connection, position_id: int, *, reason: str) -> None:
    """A close order failed terminally → reopen so the monitor re-evaluates next cycle. Atomic.

    Clears ``close_order_id`` so a re-fire mints a fresh (per-day) id rather than re-using the
    single-use one Alpaca already saw.
    """
    with conn:
        conn.execute(
            "UPDATE convexity_positions SET status = 'open', close_order_id = NULL, "
            "exit_reason = ? WHERE id = ?",
            (reason, position_id),
        )


def convexity_book_drawdown(conn: sqlite3.Connection, book_budget: float) -> tuple[float, bool]:
    """Book drawdown = (entry premium − marked value) / book_budget across OPEN positions.

    Returns ``(drawdown_fraction, have_marks)``. Unmarked positions carry at cost (no DD
    contribution). ``have_marks`` is False when nothing has been marked yet, so callers can
    treat drawdown as not-yet-meaningful. Closed/realized losses are NOT counted here — this
    is the open-book mark drawdown the kill rule watches.
    """
    rows = conn.execute(
        f"SELECT contracts, total_premium, mark FROM convexity_positions WHERE status IN {_EXPOSURE_STATES}"
    ).fetchall()
    entry_total = sum(float(r["total_premium"]) for r in rows)
    marked_total = 0.0
    have_marks = False
    for r in rows:
        if r["mark"] is None:
            marked_total += float(r["total_premium"])
        else:
            have_marks = True
            marked_total += float(r["mark"]) * int(r["contracts"]) * 100.0
    if not have_marks or book_budget <= 0:
        return (0.0, have_marks)
    return ((entry_total - marked_total) / book_budget, have_marks)


# A position mid-exit ('closing') still holds REAL exposure until its sell fills, so the
# concurrency cap, per-name dedup, premium-at-risk, and drawdown all count open + closing.
_EXPOSURE_STATES = "('open', 'closing')"


def open_position_symbols(conn: sqlite3.Connection) -> set[str]:
    """Underlyings with at least one live (open/closing) position (for per-cycle dedup)."""
    rows = conn.execute(
        f"SELECT DISTINCT symbol FROM convexity_positions WHERE status IN {_EXPOSURE_STATES}"
    ).fetchall()
    return {r["symbol"] for r in rows}


def count_open_convexity_positions(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        f"SELECT COUNT(*) AS n FROM convexity_positions WHERE status IN {_EXPOSURE_STATES}"
    ).fetchone()
    return int(row["n"]) if row else 0


def count_open_sentinel_positions(conn: sqlite3.Connection) -> int:
    """Live (open/closing) positions that originated from a sentinel discovery (the proposal carries
    ``sentinel_id``) — the basis for the discovery **slot reservation** so auto-traded discoveries
    can't starve hand-seed convictions (PREREG §5 / P1)."""
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM convexity_positions p "
        "JOIN council_proposals cp ON p.proposal_id = cp.id "
        f"WHERE p.status IN {_EXPOSURE_STATES} AND cp.sentinel_id IS NOT NULL"
    ).fetchone()
    return int(row["n"]) if row else 0


def convexity_book_open_premium(conn: sqlite3.Connection) -> float:
    """Total premium-at-risk across live (open/closing) positions (the book's current usage)."""
    row = conn.execute(
        f"SELECT COALESCE(SUM(total_premium), 0.0) AS s FROM convexity_positions WHERE status IN {_EXPOSURE_STATES}"
    ).fetchone()
    return float(row["s"]) if row else 0.0


def cluster_open_premium(conn: sqlite3.Connection, symbols) -> float:
    """Total **committed** entry-premium across a correlation cluster's symbols — the basis for the
    cluster cap (PREREG §5 amendment 2026-06-03). Counts ``status IN ('open','closing','pending')``.

    Unlike the book cap (open/closing only), the cluster cap MUST count a same-cycle just-submitted-
    but-``pending`` sibling: under ``DRY_RUN=false`` a resting limit is recorded 'pending' and
    ``reconcile_pending`` runs only in the monitor pass, so an open/closing-only basis would let a
    tight (e.g. 2-name) cluster over-admit on its 3rd same-cycle mate — the exact crowding the cap
    exists to stop. The ~10-slot book absorbs that window; a tight cluster cannot (a deliberate,
    documented divergence). Empty symbol set → 0.0."""
    syms = tuple(symbols)
    if not syms:
        return 0.0
    placeholders = ",".join("?" * len(syms))
    row = conn.execute(
        "SELECT COALESCE(SUM(total_premium), 0.0) AS s FROM convexity_positions "
        f"WHERE status IN ('open', 'closing', 'pending') AND symbol IN ({placeholders})",
        syms,
    ).fetchone()
    return float(row["s"]) if row else 0.0


def cluster_open_directions(conn: sqlite3.Connection, symbols) -> set[str]:
    """Distinct directions of a cluster's live (open/closing/pending) positions — for the non-fatal
    mixed-direction warning (the cap sums premium-at-risk regardless of direction; a coherent cluster
    is single-direction). Empty symbol set → empty set."""
    syms = tuple(symbols)
    if not syms:
        return set()
    placeholders = ",".join("?" * len(syms))
    rows = conn.execute(
        "SELECT DISTINCT direction FROM convexity_positions "
        f"WHERE status IN ('open', 'closing', 'pending') AND symbol IN ({placeholders})",
        syms,
    ).fetchall()
    return {r["direction"] for r in rows}


# ── brain-off NULL shadow book (T3 PR3b) ─────────────────────────────────────────────────────────
# A SEPARATE table + helpers from convexity_positions, ON PURPOSE: the shadow book is simulated-only
# and must never share a code path that can reach the broker (migration 0008). Its lifecycle is just
# open → closed (no pending/closing/order_id). Sizing/dedup mirror the real book but against the
# SHADOW book's OWN occupancy, so the only difference vs the real book is the brain-off selection.


def record_null_attempt(
    conn: sqlite3.Connection,
    *,
    run_id: int | None,
    book: str,
    attempt_idx: int,
    symbol: str,
    direction: str | None,
    origin: str | None,
    outcome: str,
    entry_premium_per_contract: float | None,
    as_of: str | None,
) -> None:
    """One per-name booking-attempt row for a capped null book (migration 0018) — the replay
    substrate for the cap-regime-bundled ``real − shadow`` read (per-name terminal outcome +
    walk order + premium-at-attempt; the UROY/aggregate-counters lesson, 2026-07-02). Telemetry
    only: callers wrap this fail-soft — a failed write must never block the booking pass."""
    conn.execute(
        "INSERT INTO null_book_attempts (run_id, book, attempt_idx, symbol, direction, origin,"
        " outcome, entry_premium_per_contract, as_of, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
        (run_id, book, attempt_idx, symbol, direction, origin, outcome,
         entry_premium_per_contract, as_of),
    )
    conn.commit()


def record_shadow_position(
    conn: sqlite3.Connection,
    *,
    run_id: int | None,
    origin: str,
    opened_at: str,
    theme: str,
    symbol: str,
    direction: str,
    structure_kind: str,
    contract_symbol: str,
    expiry: str,
    strike: float,
    dte: int,
    moneyness: float,
    contracts: int,
    entry_premium_per_contract: float,
    total_premium: float,
    entry_spot: float | None = None,
) -> int:
    """Book a simulated (NEVER broker) shadow position at the chain mid. Returns its id. Atomic."""
    with conn:
        cur = conn.execute(
            "INSERT INTO shadow_positions (run_id, origin, opened_at, theme, symbol, direction, "
            "structure_kind, contract_symbol, expiry, strike, dte, moneyness, contracts, "
            "entry_premium_per_contract, total_premium, entry_spot, status, mark) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', NULL)",
            (
                run_id, origin, opened_at, theme, symbol, direction, structure_kind,
                contract_symbol, expiry, strike, dte, moneyness, contracts,
                entry_premium_per_contract, total_premium, entry_spot,
            ),
        )
    return int(cur.lastrowid)


def open_shadow_positions(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM shadow_positions WHERE status = 'open' ORDER BY id").fetchall()


def shadow_open_symbols(conn: sqlite3.Connection) -> set[str]:
    """Underlyings with a live shadow position (per-cycle dedup — one shadow bet per name)."""
    rows = conn.execute("SELECT DISTINCT symbol FROM shadow_positions WHERE status = 'open'").fetchall()
    return {r["symbol"] for r in rows}


def count_open_shadow_positions(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM shadow_positions WHERE status = 'open'").fetchone()
    return int(row["n"]) if row else 0


def count_open_shadow_sentinel_positions(conn: sqlite3.Connection) -> int:
    """Open shadow positions of sentinel origin — so the shadow can apply the SAME slot reservation the
    real book uses (the brain-off difference is the council's include/exclude, never the deterministic cap)."""
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM shadow_positions WHERE status = 'open' AND origin = 'sentinel'"
    ).fetchone()
    return int(row["n"]) if row else 0


def shadow_book_open_premium(conn: sqlite3.Connection) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(total_premium), 0.0) AS s FROM shadow_positions WHERE status = 'open'"
    ).fetchone()
    return float(row["s"]) if row else 0.0


def shadow_cluster_open_premium(conn: sqlite3.Connection, symbols) -> float:
    """Total entry-premium across a cluster's symbols in the shadow book (``status='open'``). The
    shadow book records 'open' immediately (no broker → no 'pending'), so within-cycle cluster-mates
    are already counted — the real book's committed-basis pending fix is unnecessary here. Empty → 0.0."""
    syms = tuple(symbols)
    if not syms:
        return 0.0
    placeholders = ",".join("?" * len(syms))
    row = conn.execute(
        "SELECT COALESCE(SUM(total_premium), 0.0) AS s FROM shadow_positions "
        f"WHERE status = 'open' AND symbol IN ({placeholders})",
        syms,
    ).fetchone()
    return float(row["s"]) if row else 0.0


def mark_shadow_position(conn: sqlite3.Connection, position_id: int, *, mark: float, as_of: str) -> None:
    with conn:
        conn.execute(
            "UPDATE shadow_positions SET mark = ?, marked_at = ? WHERE id = ?",
            (float(mark), as_of, position_id),
        )


def close_shadow_position(
    conn: sqlite3.Connection,
    position_id: int,
    *,
    exit_price: float,
    realized_pnl: float,
    realized_multiple: float,
    reason: str,
    as_of: str,
) -> None:
    """Close a shadow position in-DB (always at mark/intrinsic — there is no broker). Atomic."""
    with conn:
        conn.execute(
            "UPDATE shadow_positions SET status = 'closed', mark = ?, realized_pnl = ?, "
            "realized_multiple = ?, exit_reason = ?, closed_at = ?, marked_at = ? WHERE id = ?",
            (float(exit_price), float(realized_pnl), float(realized_multiple), reason, as_of, as_of, position_id),
        )


def shadow_realized_multiples(conn: sqlite3.Connection) -> dict[str, list[float]]:
    """Closed shadow positions' per-position realized multiples, grouped by ``origin`` (the TAIL
    substrate — refinement #2: a convex book's value is in the tail, and the brain-off book is larger,
    so compare per-position multiples, never an aggregate book total)."""
    out: dict[str, list[float]] = {}
    for r in conn.execute(
        "SELECT origin, realized_multiple FROM shadow_positions "
        "WHERE status = 'closed' AND realized_multiple IS NOT NULL ORDER BY id"
    ):
        out.setdefault(str(r["origin"]), []).append(float(r["realized_multiple"]))
    return out


def convexity_realized_multiples(conn: sqlite3.Connection) -> list[float]:
    """The REAL (brain-on) book's per-position realized multiples (exit value ÷ entry premium) over
    closed positions — the other side of the brain-off-vs-brain-on tail comparison."""
    out: list[float] = []
    for r in conn.execute(
        "SELECT total_premium, realized_pnl FROM convexity_positions "
        "WHERE status = 'closed' AND realized_pnl IS NOT NULL AND total_premium > 0 ORDER BY id"
    ):
        out.append((float(r["total_premium"]) + float(r["realized_pnl"])) / float(r["total_premium"]))
    return out


# ── no-gate / fixed-basket null books (PREREG_FIXED_BASKET_NULL.md, migration 0010) ───────────────
# Mirror the shadow_* helpers field-for-field, keyed additionally by `book` ('union_nogate'=3A /
# 'basket_nogate'=3B), so the eventual null-book unification is a mechanical union. Simulated-only,
# NEVER the broker; open → closed lifecycle.

def record_fixed_basket_position(
    conn: sqlite3.Connection, *, run_id: int | None, book: str, origin: str, opened_at: str, theme: str,
    symbol: str, direction: str, structure_kind: str, contract_symbol: str, expiry: str, strike: float,
    dte: int, moneyness: float, contracts: int, entry_premium_per_contract: float, total_premium: float,
    entry_spot: float | None = None,
) -> int:
    """Book a simulated (NEVER broker) no-gate position at the chain mid. Returns its id. Atomic."""
    with conn:
        cur = conn.execute(
            "INSERT INTO fixed_basket_positions (run_id, book, origin, opened_at, theme, symbol, "
            "direction, structure_kind, contract_symbol, expiry, strike, dte, moneyness, contracts, "
            "entry_premium_per_contract, total_premium, entry_spot, status, mark) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', NULL)",
            (run_id, book, origin, opened_at, theme, symbol, direction, structure_kind, contract_symbol,
             expiry, strike, dte, moneyness, contracts, entry_premium_per_contract, total_premium, entry_spot),
        )
    return int(cur.lastrowid)


def open_fixed_basket_positions(conn: sqlite3.Connection, book: str | None = None) -> list[sqlite3.Row]:
    if book is None:
        return conn.execute("SELECT * FROM fixed_basket_positions WHERE status='open' ORDER BY id").fetchall()
    return conn.execute(
        "SELECT * FROM fixed_basket_positions WHERE status='open' AND book=? ORDER BY id", (book,)
    ).fetchall()


def fixed_basket_open_symbols(conn: sqlite3.Connection, book: str) -> set[str]:
    """Underlyings with a live position in this no-gate book (per-cycle dedup — one bet per name)."""
    rows = conn.execute(
        "SELECT DISTINCT symbol FROM fixed_basket_positions WHERE status='open' AND book=?", (book,)
    ).fetchall()
    return {r["symbol"] for r in rows}


def count_open_fixed_basket_positions(conn: sqlite3.Connection, book: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM fixed_basket_positions WHERE status='open' AND book=?", (book,)
    ).fetchone()
    return int(row["n"]) if row else 0


def count_open_fixed_basket_sentinel_positions(conn: sqlite3.Connection, book: str) -> int:
    """Open sentinel-origin positions — so a cap-ON book (3A) applies the SAME slot reservation."""
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM fixed_basket_positions WHERE status='open' AND book=? AND origin='sentinel'",
        (book,),
    ).fetchone()
    return int(row["n"]) if row else 0


def fixed_basket_book_open_premium(conn: sqlite3.Connection, book: str) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(total_premium),0.0) AS s FROM fixed_basket_positions WHERE status='open' AND book=?",
        (book,),
    ).fetchone()
    return float(row["s"]) if row else 0.0


def fixed_basket_cluster_open_premium(conn: sqlite3.Connection, symbols, book: str) -> float:
    """Cluster entry-premium in this no-gate book (open only — sim books 'open' immediately). Empty → 0.0."""
    syms = tuple(symbols)
    if not syms:
        return 0.0
    placeholders = ",".join("?" * len(syms))
    row = conn.execute(
        "SELECT COALESCE(SUM(total_premium),0.0) AS s FROM fixed_basket_positions "
        f"WHERE status='open' AND book=? AND symbol IN ({placeholders})",
        (book, *syms),
    ).fetchone()
    return float(row["s"]) if row else 0.0


def mark_fixed_basket_position(conn: sqlite3.Connection, position_id: int, *, mark: float, as_of: str) -> None:
    with conn:
        conn.execute(
            "UPDATE fixed_basket_positions SET mark=?, marked_at=? WHERE id=?", (float(mark), as_of, position_id)
        )


def close_fixed_basket_position(
    conn: sqlite3.Connection, position_id: int, *, exit_price: float, realized_pnl: float,
    realized_multiple: float, reason: str, as_of: str,
) -> None:
    """Close a no-gate position in-DB (always at mark/intrinsic — there is no broker). Atomic."""
    with conn:
        conn.execute(
            "UPDATE fixed_basket_positions SET status='closed', mark=?, realized_pnl=?, realized_multiple=?, "
            "exit_reason=?, closed_at=?, marked_at=? WHERE id=?",
            (float(exit_price), float(realized_pnl), float(realized_multiple), reason, as_of, as_of, position_id),
        )


def fixed_basket_realized_multiples(conn: sqlite3.Connection, book: str | None = None) -> dict[str, list[float]]:
    """Closed positions' per-position realized multiples, grouped by `book` (the tail substrate for
    `shadow − 3A` etc.). `book=None` → all books. Compared on the TAIL (PREREG §5), never an aggregate."""
    out: dict[str, list[float]] = {}
    if book is None:
        q = ("SELECT book, realized_multiple FROM fixed_basket_positions "
             "WHERE status='closed' AND realized_multiple IS NOT NULL ORDER BY id")
        params: tuple = ()
    else:
        q = ("SELECT book, realized_multiple FROM fixed_basket_positions "
             "WHERE status='closed' AND realized_multiple IS NOT NULL AND book=? ORDER BY id")
        params = (book,)
    for r in conn.execute(q, params):
        out.setdefault(str(r["book"]), []).append(float(r["realized_multiple"]))
    return out


# ── shares descriptive null (PREREG_FIXED_BASKET_NULL §2/§5, migration 0012) ──────────────────────
# An append-only ENTRY LOG (not a position book): convexity-vs-linear context. Signed returns are
# computed at REPORT time from bars (shares_basket.shares_return_report), so there is no mark/close here.

def record_shares_position(
    conn: sqlite3.Connection, *, run_id: int | None, basket: str | None, symbol: str, direction: str,
    entry_spot: float, entry_at: str,
) -> int:
    """Log a simulated (NEVER broker) shares entry — the forward linear bet on a basket name. Atomic."""
    with conn:
        cur = conn.execute(
            "INSERT INTO shares_positions (run_id, basket, symbol, direction, entry_spot, entry_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, basket, symbol, direction, float(entry_spot), entry_at),
        )
    return int(cur.lastrowid)


def shares_recent_symbols(conn: sqlite3.Connection, *, since_iso: str) -> set[str]:
    """Underlyings entered since ``since_iso`` — the time-dedup window (≈ the longest horizon), so a name
    isn't re-booked while its longest-horizon return is still in flight (the linear analog of the option
    books' 'skip already-open')."""
    rows = conn.execute(
        "SELECT DISTINCT symbol FROM shares_positions WHERE entry_at >= ?", (since_iso,)
    ).fetchall()
    return {r["symbol"] for r in rows}


def all_shares_positions(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Every shares entry (the report computes per-horizon signed returns from bars on demand)."""
    return conn.execute("SELECT * FROM shares_positions ORDER BY id").fetchall()


def record_council_proposal(
    conn: sqlite3.Connection,
    *,
    run_id: int | None,
    as_of: str,
    theme: str,
    symbol: str,
    direction: str,
    conviction: str,
    structural_vs_fad: str | None = None,
    weakest_point: str | None = None,
    rationale: Any = None,
    strategist_summary: str | None = None,
    cost_usd: float | None = None,
    model_mix: Any = None,
    status: str = "proposed",
    sentinel_id: int | None = None,
    markers_asof: str | None = None,
) -> int:
    """Insert a council theme proposal (T2). Returns its id. Atomic.

    Records EVERY proposal the strategist emitted, traded or not — the forward-scoring
    substrate (guardrail §6: the council is validated forward, never backtested).

    ``markers_asof`` (migration 0016, finding #1 / §7.1): the sentinel's ``last_seen_at`` AT JUDGMENT
    — i.e. when the markers the binding ``at_inflection`` leg reasoned over were last recomputed at an
    L0. Stamped point-in-time + frozen so marker-age (= ``as_of − markers_asof``) is non-corruptible.
    NULL for hand-seed proposals (news-grounded, no markers).
    """
    import json

    if not isinstance(rationale, str):
        rationale = json.dumps(rationale, default=str)
    if not isinstance(model_mix, str):
        model_mix = json.dumps(model_mix, default=str)
    with conn:
        cur = conn.execute(
            "INSERT INTO council_proposals (run_id, as_of, theme, symbol, direction, conviction, "
            "structural_vs_fad, weakest_point, rationale, strategist_summary, cost_usd, model_mix, "
            "status, sentinel_id, markers_asof, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
            (
                run_id, as_of, theme, symbol, direction, conviction, structural_vs_fad,
                weakest_point, rationale, strategist_summary, cost_usd, model_mix, status,
                sentinel_id, markers_asof,
            ),
        )
    return int(cur.lastrowid)


def record_agent_output(
    conn: sqlite3.Connection,
    *,
    proposal_id: int,
    role: str,
    provider: str | None,
    model: str | None,
    confidence: str | None,
    stance: str | None = None,
    weakest_point: str | None = None,
    raw: Any = None,
    flagged_unsupported: int = 0,
    cost_usd: float | None = None,
) -> int:
    """Insert one agent's contribution to a proposal (proposer/adversary/strategist). Atomic."""
    import json

    if not isinstance(raw, str):
        raw = json.dumps(raw, default=str)
    with conn:
        cur = conn.execute(
            "INSERT INTO council_agent_outputs (proposal_id, role, provider, model, confidence, "
            "stance, weakest_point, raw, flagged_unsupported, cost_usd, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
            (
                proposal_id, role, provider, model, confidence, stance, weakest_point, raw,
                int(flagged_unsupported), cost_usd,
            ),
        )
    return int(cur.lastrowid)


def _is_parse_error(raw) -> bool:
    """True if a stored agent_output ``raw`` is the fail-closed parse_error fallback. Robust to the
    JSON-string form it's persisted in (``record_agent_output`` json.dumps it) or a dict."""
    if not raw:
        return False
    if isinstance(raw, dict):
        return bool(raw.get("parse_error"))
    try:
        import json
        return bool(json.loads(raw).get("parse_error"))
    except Exception:  # noqa: BLE001 — non-JSON raw can't be a structured parse_error
        return '"parse_error": true' in str(raw)


def council_parse_health(conn: sqlite3.Connection, run_id: int) -> dict:
    """Cycle-level proposer parse-health for a run: how many proposer LLM calls were made and how many
    FAILED to parse. Excludes ungrounded $0 early-exits (those record no proposer agent_output), so a
    high rate means the apparatus was INERT for a BUG reason — not deliberate abstention."""
    rows = conn.execute(
        "SELECT ao.raw AS raw FROM council_agent_outputs ao "
        "JOIN council_proposals cp ON cp.id = ao.proposal_id "
        "WHERE cp.run_id = ? AND ao.role = 'proposer'",
        (run_id,),
    ).fetchall()
    called = len(rows)
    failed = sum(1 for r in rows if _is_parse_error(r["raw"]))
    return {"called": called, "parse_failed": failed, "rate": (failed / called) if called else 0.0}


def _weekday_age(d0, d1) -> int:
    """Weekdays strictly after ``d0`` up to and including ``d1`` (dates). Holiday-blind by design:
    a holiday inflates the count, which can only EXPIRE a read early — the fail-closed direction
    for the reserve's staleness gate (PREREG gate_cheap_reserve §3)."""
    from datetime import timedelta
    if d1 <= d0:
        return 0
    age, cur = 0, d0
    for _ in range((d1 - d0).days):
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            age += 1
    return age


def _iso_date(value):
    """Date part of a persisted ISO timestamp cell (fail-soft → None)."""
    try:
        from datetime import datetime
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except Exception:  # noqa: BLE001 — an unparseable cell is simply not fresh
        return None


def gate_cheap_reads(conn: sqlite3.Connection, *, now, max_age_td: int = 5) -> dict[str, float]:
    """The reserve's §3 data contract: the most recent GATE-OF-RECORD cheap read per symbol, aged
    ≤ ``max_age_td`` weekdays. Returns ``{SYMBOL: iv_rv}`` for eligible names only (fail-closed:
    no qualifying read ⇒ absent ⇒ not reserve-eligible — the reserve never infers cheapness).

    Primary = ``cheapness_watch`` (the real tradeable structure); a symbol's LATEST watch row is
    the verdict of record — fresh ∧ cheap=1 ⇒ eligible; fresh ∧ cheap=0 ⇒ NOT eligible and the
    fallback is NOT consulted (the fallback covers coverage gaps, never disagreement). Only
    symbols with NO fresh primary row fall back to the latest ``gate_dualread`` opra row
    (fresh ∧ cheap=1). Both sources are written AFTER the council each cycle, so the read is
    necessarily prior-cycle (staleness ≥ 1 trading day, pinned honestly in the pre-reg)."""
    today = now.date() if hasattr(now, "date") else now
    out: dict[str, float] = {}
    blocked: set[str] = set()   # fresh primary said NOT cheap — fallback must not overrule
    seen: set[str] = set()
    for r in conn.execute(
        "SELECT symbol, iv_rv, cheap, as_of FROM cheapness_watch ORDER BY as_of DESC, id DESC"
    ):
        sym = str(r["symbol"]).upper()
        if sym in seen:
            continue
        seen.add(sym)
        d = _iso_date(r["as_of"])
        if d is None or _weekday_age(d, today) > max_age_td:
            continue  # stale primary → the symbol may still qualify via the fallback
        if int(r["cheap"] or 0) == 1 and r["iv_rv"] is not None:
            out[sym] = float(r["iv_rv"])
        else:
            blocked.add(sym)
    seen_fb: set[str] = set()
    for r in conn.execute(
        "SELECT symbol, iv_rv, cheap, evaluated_at FROM gate_dualread WHERE feed='opra' "
        "ORDER BY evaluated_at DESC, id DESC"
    ):
        sym = str(r["symbol"]).upper()
        if sym in seen_fb or sym in out or sym in blocked:
            continue
        seen_fb.add(sym)
        d = _iso_date(r["evaluated_at"])
        if d is None or _weekday_age(d, today) > max_age_td:
            continue
        if int(r["cheap"] or 0) == 1 and r["iv_rv"] is not None:
            out[sym] = float(r["iv_rv"])
    return out


def council_last_judged(conn: sqlite3.Connection) -> dict[str, str]:
    """{SYMBOL: most recent council ``as_of``} over ALL recorded proposals (any council row —
    including drops and parse errors — consumed a judged slot; never-judged names are simply
    absent, and the reserve's §4 rank sorts them FIRST)."""
    return {
        str(r["symbol"]).upper(): r["last"]
        for r in conn.execute(
            "SELECT symbol, MAX(as_of) AS last FROM council_proposals GROUP BY symbol"
        )
        if r["last"]
    }


def _json_or_none(raw):
    """Parse a persisted JSON cell (``rationale`` / ``raw``) → dict, or None. Fail-soft (never raises)."""
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        import json
        d = json.loads(raw)
        return d if isinstance(d, dict) else None
    except Exception:  # noqa: BLE001 — a non-JSON cell is simply unreadable
        return None


def council_first_judgment_under_narrated(conn: sqlite3.Connection) -> dict[str, dict]:
    """Per symbol, the council's FIRST-judgment ``under_narrated`` read — the substrate the cheapness-watch
    clock-start gate (PREREG_CHEAPNESS_WATCH §2.1.7) reads. Returns ``{symbol: {...}}`` where the value is::

        {"as_of": <first deliberated proposal's as_of>,
         "under_narrated": True | False | None,   # the STRATEGIST's read (the binding tri-criteria role)
         "parse_error": <bool>,                    # strategist agent_output was the fail-closed fallback
         "confirmed_quiet": <bool>,                # under_narrated is True AND parse_error is False
         "per_role": {role: True|False|None, ...}} # each role's under_narrated read (audit composition)

    "First judgment" = the EARLIEST ``council_proposals.as_of`` for the symbol that reached the strategist
    (``rationale.strategist`` present — a deliberated row; pre-strategist drops carry no tri-criteria and are
    skipped). The read is timestamped at that judgment (anti-survivorship: a name that NARRATES later is
    judged on its FIRST read, never re-confirmed away — §2.1.7). The aggregate ``under_narrated`` /
    ``confirmed_quiet`` mirror the production read path (``dashboard_data.council_stage_funnel``): the
    rationale JSON (``under_narrated`` is a strategist-only key — no column exists). ``per_role`` is read from
    each role's ``council_agent_outputs.raw`` so the cohort's quietness COMPOSITION is auditable later.

    Read-only; never raises (fail-soft per row). Symbols with no deliberated proposal are absent from the map.
    """
    # Earliest deliberated proposal per symbol. Ordered so the first deliberated row per symbol wins;
    # the Python pass below keeps the first (a pre-strategist drop is skipped, never claiming the slot).
    rows = conn.execute(
        "SELECT id, symbol, as_of, rationale FROM council_proposals ORDER BY symbol, as_of, id"
    ).fetchall()
    out: dict[str, dict] = {}
    for r in rows:
        symbol = r["symbol"]
        if symbol in out:
            continue  # already have this symbol's first deliberated judgment
        rat = _json_or_none(r["rationale"])
        strat = (rat or {}).get("strategist")
        if not isinstance(strat, dict):
            continue  # not a deliberated row (ungrounded / proposer-abstained / pre-strategist drop)
        un = strat.get("under_narrated")
        under_narrated = un if isinstance(un, bool) else None
        # parse_error + per-role composition from the persisted agent outputs of THIS proposal.
        per_role: dict[str, bool | None] = {}
        strat_parse_error = False
        for ao in conn.execute(
            "SELECT role, raw FROM council_agent_outputs WHERE proposal_id = ?", (r["id"],)
        ):
            ar = _json_or_none(ao["raw"]) or {}
            v = ar.get("under_narrated")
            per_role[ao["role"]] = v if isinstance(v, bool) else None
            if ao["role"] == "strategist" and bool(ar.get("parse_error")):
                strat_parse_error = True
        out[symbol] = {
            "as_of": r["as_of"],
            "under_narrated": under_narrated,
            "parse_error": strat_parse_error,
            "confirmed_quiet": (under_narrated is True) and (strat_parse_error is False),
            "per_role": per_role,
        }
    return out


def update_run_council_health(
    conn: sqlite3.Connection, run_id: int, *, council_health: str, model_mix: str | None = None
) -> None:
    """Stamp a run's council HEALTH ('ok'|'parse_fail'|'cost_cap'|'fail_closed') and resolved per-role
    MODEL_MIX (migration 0011). The health stamp lets the T4 analysis CENSOR the council-marginal
    attribution of a bug-contaminated run (the brain-off null books stay valid); the model_mix stamp
    makes a deliberate model upgrade a record-segmenting event (companion to ``frame_version``)."""
    with conn:
        if model_mix is not None:
            conn.execute(
                "UPDATE runs SET council_health = ?, model_mix = ? WHERE id = ?",
                (council_health, model_mix, run_id),
            )
        else:
            conn.execute("UPDATE runs SET council_health = ? WHERE id = ?", (council_health, run_id))


def stamp_run_clock_basis(conn: sqlite3.Connection, run_id: int, clock_basis: str) -> None:
    """Record-segment a run by the cheapness-watch §2.1.7 fail-closed clock-start basis. Merges
    ``{"clock_basis": <basis>}`` into the run's existing ``model_mix`` JSON (preserving the council
    ``model_mix``/prompts/corpus keys ``_stamp_council_health`` writes), so a basis change is a
    record-segmenting event (rate values across bases are NOT comparable) — the same self-describing-version
    idiom as the prompt-sha / corpus stamps, zero migration. Atomic; fail-soft on a non-JSON existing cell."""
    import json

    row = conn.execute("SELECT model_mix FROM runs WHERE id = ?", (run_id,)).fetchone()
    existing = _json_or_none(row["model_mix"]) if row else None
    mix = existing if isinstance(existing, dict) else {}
    mix["clock_basis"] = clock_basis
    with conn:
        conn.execute("UPDATE runs SET model_mix = ? WHERE id = ?", (json.dumps(mix), run_id))


def link_proposal_position(
    conn: sqlite3.Connection, proposal_id: int, position_id: int, *, status: str = "traded"
) -> None:
    """Link a proposal to the position it became, and flip its status. Atomic."""
    with conn:
        conn.execute(
            "UPDATE council_proposals SET position_id = ?, status = ? WHERE id = ?",
            (position_id, status, proposal_id),
        )


def resolve_proposal(
    conn: sqlite3.Connection,
    proposal_id: int,
    *,
    outcome: int | None,
    brier: float | None,
    resolved_at: str,
) -> None:
    """Record a proposal's forward outcome at position close. Atomic.

    ``outcome`` is 1 (favorable), 0 (unfavorable), or None (genuinely unresolved — spot
    unavailable; never fabricated). ``brier`` is the per-proposal Brier contribution.
    """
    with conn:
        conn.execute(
            "UPDATE council_proposals SET outcome = ?, brier = ?, resolved_at = ? WHERE id = ?",
            (outcome, brier, resolved_at, proposal_id),
        )


def council_proposal_for_position(conn: sqlite3.Connection, position_id: int) -> sqlite3.Row | None:
    """The proposal a given position came from, or None."""
    return conn.execute(
        "SELECT * FROM council_proposals WHERE position_id = ?", (position_id,)
    ).fetchone()


def council_proposal_by_id(conn: sqlite3.Connection, proposal_id: int) -> sqlite3.Row | None:
    """A proposal by id (used at close to resolve its forward outcome), or None."""
    return conn.execute(
        "SELECT * FROM council_proposals WHERE id = ?", (proposal_id,)
    ).fetchone()


# ── Sentinel discovery (T3) ─────────────────────────────────────────────────────────────────
# Discovery PROPOSES candidates into the set the council judges (the hard seam is unchanged).
# A sentinel lineage is keyed by ``(symbol, direction)`` and updated IN PLACE on re-surface so a
# secular theme that dips below threshold and returns stays one continuous bet (PREREG §7 /
# forward-scoring substrate). ``kind='control'`` rows are the per-scan random null cohort.


def _sentinel_live_lineage(conn: sqlite3.Connection, lineage_key: str) -> sqlite3.Row | None:
    """The live (candidate|dormant) sentinel row for a lineage, or None."""
    return conn.execute(
        "SELECT * FROM sentinel_candidates WHERE kind='sentinel' AND lineage_key=? "
        "AND status IN ('candidate','dormant') ORDER BY id DESC LIMIT 1",
        (lineage_key,),
    ).fetchone()


def record_sentinel_candidate(
    conn: sqlite3.Connection,
    *,
    run_id: int | None,
    as_of: str,
    symbol: str,
    direction: str,
    basket: str | None,
    inflection_score: float | None,
    markers: Any,
    theme: str | None = None,
    kind: str = "sentinel",
    status: str = "candidate",
    seed_thesis: str | None = None,
    framer_conviction: str | None = None,
    structural_vs_fad: str | None = None,
    confound_label: str | None = None,
    cost_usd: float | None = None,
    provider: str | None = None,
    model: str | None = None,
    rationale_multi: Any = None,
    related_lineage: str | None = None,
) -> int:
    """Upsert a discovered sentinel (or insert a control). Returns the row id. Atomic.

    For ``kind='sentinel'`` a re-surfaced lineage UPDATEs in place (bumps ``surface_count`` /
    ``last_seen_at``, revives 'dormant' → 'candidate', refreshes markers/score, merges the
    multi-theme rationale) — provenance stays continuous, never fragmented into a "new"
    discovery. ``kind='control'`` always inserts (the per-scan null cohort).
    """
    import json

    symbol = symbol.upper()
    lineage_key = f"{symbol}|{direction}"
    if not isinstance(markers, str):
        markers = json.dumps(markers, default=str)
    if rationale_multi is not None and not isinstance(rationale_multi, str):
        rationale_multi = json.dumps(rationale_multi, default=str)
    theme = theme or basket
    with conn:
        existing = _sentinel_live_lineage(conn, lineage_key) if kind == "sentinel" else None
        if existing is not None:
            conn.execute(
                "UPDATE sentinel_candidates SET status='candidate', "
                "surface_count = surface_count + 1, last_seen_at=?, run_id=?, inflection_score=?, "
                "markers=?, theme=?, basket=?, seed_thesis=COALESCE(?, seed_thesis), "
                "framer_conviction=COALESCE(?, framer_conviction), "
                "structural_vs_fad=COALESCE(?, structural_vs_fad), "
                "confound_label=COALESCE(?, confound_label), "
                "rationale_multi=COALESCE(?, rationale_multi), cost_usd=?, provider=?, model=? "
                "WHERE id=?",
                (as_of, run_id, inflection_score, markers, theme, basket, seed_thesis,
                 framer_conviction, structural_vs_fad, confound_label, rationale_multi,
                 cost_usd, provider, model, int(existing["id"])),
            )
            return int(existing["id"])
        cur = conn.execute(
            "INSERT INTO sentinel_candidates (run_id, lineage_key, kind, symbol, basket, theme, "
            "direction, inflection_score, markers, rationale_multi, framer_conviction, "
            "structural_vs_fad, seed_thesis, confound_label, cost_usd, provider, model, status, "
            "surface_count, discovered_at, last_seen_at, related_lineage, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?,?,datetime('now'))",
            (run_id, lineage_key, kind, symbol, basket, theme, direction, inflection_score,
             markers, rationale_multi, framer_conviction, structural_vs_fad, seed_thesis,
             confound_label, cost_usd, provider, model, status, as_of, as_of, related_lineage),
        )
        return int(cur.lastrowid)


def active_sentinel_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Live tradeable sentinels, **ranked by inflection_score desc** (the union order). Controls
    (kind='control') are NEVER returned — they only forward-score the null."""
    return conn.execute(
        "SELECT * FROM sentinel_candidates WHERE kind='sentinel' AND status='candidate' "
        "ORDER BY inflection_score DESC, id ASC"
    ).fetchall()


def active_sentinel_symbols(conn: sqlite3.Connection) -> set[str]:
    """Symbols with a live sentinel candidate (for discovery novelty/dedup)."""
    rows = conn.execute(
        "SELECT DISTINCT symbol FROM sentinel_candidates WHERE kind='sentinel' AND status='candidate'"
    ).fetchall()
    return {r["symbol"] for r in rows}


def expire_stale_sentinels(conn: sqlite3.Connection, *, as_of: datetime, ttl_days: int) -> int:
    """Flip candidates not re-surfaced within ``ttl_days`` to 'dormant' (kept in history, no
    longer unioned to the council). Returns the count flipped. Date math in Python so a tz-aware
    ISO ``last_seen_at`` parses reliably (SQLite julianday is finicky with tz offsets)."""
    cutoff = as_of - timedelta(days=ttl_days)
    rows = conn.execute(
        "SELECT id, last_seen_at FROM sentinel_candidates WHERE kind='sentinel' AND status='candidate'"
    ).fetchall()
    stale: list[int] = []
    for r in rows:
        try:
            seen = datetime.fromisoformat(r["last_seen_at"])
        except (ValueError, TypeError):
            continue
        if seen < cutoff:
            stale.append(int(r["id"]))
    if stale:
        with conn:
            conn.executemany("UPDATE sentinel_candidates SET status='dormant' WHERE id=?",
                             [(i,) for i in stale])
    return len(stale)


def set_sentinel_status(conn: sqlite3.Connection, sentinel_id: int, *, status: str) -> None:
    """Set a sentinel's lifecycle status (e.g. daily re-validation → 'dormant'). Atomic."""
    with conn:
        conn.execute("UPDATE sentinel_candidates SET status=? WHERE id=?", (status, sentinel_id))


def link_sentinel_proposal(conn: sqlite3.Connection, sentinel_id: int, proposal_id: int) -> None:
    """Link a sentinel to the council proposal it became (provenance chain). Atomic."""
    with conn:
        conn.execute("UPDATE sentinel_candidates SET proposal_id=? WHERE id=?",
                     (proposal_id, sentinel_id))
        conn.execute("UPDATE council_proposals SET sentinel_id=? WHERE id=?",
                     (sentinel_id, proposal_id))


def resolve_sentinel(
    conn: sqlite3.Connection,
    sentinel_id: int,
    *,
    resolved_at: str,
    outcome: int | None = None,
    brier: float | None = None,
    realized_multiple: float | None = None,
    reference_return: float | None = None,
    terminal_event: str | None = None,
) -> None:
    """Record a sentinel's forward outcome (traded→close, or never-traded→reference return).

    ``outcome`` is 1/0/None (None = genuinely unresolved — never fabricated). ``terminal_event``
    tags an early bar-series end ('acquired'/'delisted') so the upper-tail test isn't blind to
    the fattest part of the tail. Atomic.
    """
    with conn:
        conn.execute(
            "UPDATE sentinel_candidates SET outcome=?, brier=?, realized_multiple=?, "
            "reference_return=?, terminal_event=?, resolved_at=? WHERE id=?",
            (outcome, brier, realized_multiple, reference_return, terminal_event,
             resolved_at, sentinel_id),
        )


def sentinel_by_id(conn: sqlite3.Connection, sentinel_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM sentinel_candidates WHERE id=?", (sentinel_id,)
    ).fetchone()


def schema_version(conn: sqlite3.Connection) -> int:
    """Highest applied migration version, or 0 if none/uninitialized."""
    try:
        row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    except sqlite3.OperationalError:
        return 0
    return int(row["v"]) if row and row["v"] is not None else 0
