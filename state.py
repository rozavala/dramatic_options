"""SQLite state/journal store.

Phase 0 creates only the ``runs`` table (+ the ``schema_version`` tracking table,
owned by the migration runner). Later phases add ``signals``/``theses``/``orders``/
``positions`` via their own migrations once those columns are actually designed.

WAL mode is enabled so the future intraday monitor can read while the orchestrator
writes. Writes use the connection as a context manager for atomic transactions.
"""

from __future__ import annotations

import sqlite3
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
) -> int:
    """Insert a row into ``runs`` and return its id. Atomic."""
    with conn:  # commits on success, rolls back on exception
        cur = conn.execute(
            "INSERT INTO runs (started_at, mode, equity, note) "
            "VALUES (datetime('now'), ?, ?, ?)",
            (mode, equity, note),
        )
    return int(cur.lastrowid)


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
) -> int:
    """Append a survivorship-log row for EVERY evaluated bet (open or veto). Atomic.

    This is the only honest basis for judging edge vs. luck (PREREG_THEMATIC_CONVEXITY §5):
    every evaluation is recorded, winners and zeros alike. Append-only — never updated.
    ``proposal_id`` links the row back to the council proposal it came from (T2 forensics:
    "council proposed HIGH conviction, the IV gate vetoed it anyway").
    """
    import json

    if not isinstance(reasons, str):
        reasons = json.dumps(reasons, default=str)
    with conn:
        cur = conn.execute(
            "INSERT INTO convexity_eval (run_id, evaluated_at, theme, symbol, direction, "
            "eligible, gate_cheap, iv_rv, otm_skew, decision, position_id, proposal_id, reasons, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
            (
                run_id, as_of, theme, symbol, direction,
                None if eligible is None else int(eligible),
                None if gate_cheap is None else int(gate_cheap),
                iv_rv, otm_skew, decision, position_id, proposal_id, reasons,
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


def convexity_book_drawdown(conn: sqlite3.Connection, book_budget: float) -> tuple[float, bool]:
    """Book drawdown = (entry premium − marked value) / book_budget across OPEN positions.

    Returns ``(drawdown_fraction, have_marks)``. Unmarked positions carry at cost (no DD
    contribution). ``have_marks`` is False when nothing has been marked yet, so callers can
    treat drawdown as not-yet-meaningful. Closed/realized losses are NOT counted here — this
    is the open-book mark drawdown the kill rule watches.
    """
    rows = conn.execute(
        "SELECT contracts, total_premium, mark FROM convexity_positions WHERE status = 'open'"
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


def open_position_symbols(conn: sqlite3.Connection) -> set[str]:
    """Underlyings with at least one open convexity position (for per-cycle dedup)."""
    rows = conn.execute(
        "SELECT DISTINCT symbol FROM convexity_positions WHERE status = 'open'"
    ).fetchall()
    return {r["symbol"] for r in rows}


def count_open_convexity_positions(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM convexity_positions WHERE status = 'open'"
    ).fetchone()
    return int(row["n"]) if row else 0


def convexity_book_open_premium(conn: sqlite3.Connection) -> float:
    """Total premium-at-risk across open positions (the book's current usage)."""
    row = conn.execute(
        "SELECT COALESCE(SUM(total_premium), 0.0) AS s FROM convexity_positions WHERE status = 'open'"
    ).fetchone()
    return float(row["s"]) if row else 0.0


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
) -> int:
    """Insert a council theme proposal (T2). Returns its id. Atomic.

    Records EVERY proposal the strategist emitted, traded or not — the forward-scoring
    substrate (guardrail §6: the council is validated forward, never backtested).
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
            "status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
            (
                run_id, as_of, theme, symbol, direction, conviction, structural_vs_fad,
                weakest_point, rationale, strategist_summary, cost_usd, model_mix, status,
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


def schema_version(conn: sqlite3.Connection) -> int:
    """Highest applied migration version, or 0 if none/uninitialized."""
    try:
        row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    except sqlite3.OperationalError:
        return 0
    return int(row["v"]) if row and row["v"] is not None else 0
