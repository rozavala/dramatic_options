"""Migration 0005 — the council (T2): proposals, per-agent outputs, trade linkage.

The council PROPOSES themes; the deterministic gates still dispose (PREREG §2). This schema
is the **forward-scoring substrate** (guardrail §6 — the council is validated forward, never
backtested): every proposal and every agent's contribution is recorded, and a proposal is
linked to the position it became so its outcome (+ Brier) can be resolved months later at close.

``council_proposals``     — one row per theme proposal the strategist emitted (traded or not).
``council_agent_outputs`` — one row per agent (proposer / adversary / strategist) per proposal.
Plus two columns on ``convexity_positions``: ``proposal_id`` (back-link to the proposal) and
``entry_spot`` (the underlying price at entry — the robust basis for forward outcome resolution,
so the resolver never depends on the moneyness sign convention surviving). Idempotent.
"""

from __future__ import annotations

import sqlite3

_POSITION_COLUMNS = [
    ("proposal_id", "INTEGER"),
    ("entry_spot", "REAL"),
]


def apply(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS council_proposals ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  run_id INTEGER,"
        "  as_of TEXT NOT NULL,"
        "  theme TEXT NOT NULL,"
        "  symbol TEXT NOT NULL,"
        "  direction TEXT NOT NULL,"
        "  conviction TEXT NOT NULL,"
        "  structural_vs_fad TEXT,"
        "  weakest_point TEXT,"
        "  rationale TEXT,"            # JSON: per-role summaries + the for/against case
        "  strategist_summary TEXT,"
        "  cost_usd REAL,"
        "  model_mix TEXT,"           # JSON: {role: "provider/model"}
        "  status TEXT NOT NULL DEFAULT 'proposed',"  # proposed | traded | dropped
        "  position_id INTEGER,"
        "  outcome INTEGER,"          # 1 favorable / 0 unfavorable / NULL unresolved
        "  brier REAL,"
        "  resolved_at TEXT,"
        "  created_at TEXT,"
        "  FOREIGN KEY (run_id) REFERENCES runs(id),"
        "  FOREIGN KEY (position_id) REFERENCES convexity_positions(id)"
        ")"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS council_agent_outputs ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  proposal_id INTEGER NOT NULL,"
        "  role TEXT NOT NULL,"        # proposer | adversary | strategist
        "  provider TEXT,"
        "  model TEXT,"
        "  confidence TEXT,"           # LOW | MODERATE | HIGH | EXTREME | NEUTRAL
        "  stance TEXT,"               # the direction this agent argued (for/against the proposal)
        "  weakest_point TEXT,"
        "  raw TEXT,"                  # JSON: the parsed structured output
        "  flagged_unsupported INTEGER DEFAULT 0,"  # # of claims the authenticity filter stripped
        "  cost_usd REAL,"
        "  created_at TEXT,"
        "  FOREIGN KEY (proposal_id) REFERENCES council_proposals(id)"
        ")"
    )
    # Back-link a trade to its proposal + capture entry spot for forward resolution.
    for name, decl in _POSITION_COLUMNS:
        try:
            conn.execute(f"ALTER TABLE convexity_positions ADD COLUMN {name} {decl}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise
    # Survivorship log carries the proposal too (forensics: "council proposed HIGH, gate vetoed").
    try:
        conn.execute("ALTER TABLE convexity_eval ADD COLUMN proposal_id INTEGER")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e).lower():
            raise
