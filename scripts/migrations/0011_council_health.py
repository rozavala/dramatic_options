"""Migration 0011 — council-health + model-mix run stamps (silent-inert council fix).

L1 #37 ran the first live council, but the gemini-3.5-flash proposer thinking-starved on EVERY call
(Gemini-3.x default thinking ate ``max_output_tokens`` → truncated JSON → fail-closed NEUTRAL) → the
apparatus was INERT for a BUG reason, not judgment, and SILENTLY. That run's council-marginal reads
(the ``real − shadow`` gap + the proposer Brier) are bug-polluted.

Going forward the orchestrator stamps each council cycle's HEALTH ('ok' | 'parse_fail' | 'cost_cap' |
'fail_closed') so the T4 analysis can CENSOR the council-marginal attribution of a contaminated run —
NOT the brain-off null books (``shadow_positions`` / ``fixed_basket_positions``), which never ran the
council and stay valid. It also stamps the resolved per-role MODEL_MIX so a deliberate model upgrade is
a record-segmenting event (companion to ``frame_version`` / migration 0009).

Backfill is COMPUTED, not hardcoded to #37: any already-recorded council run whose proposer
``agent_outputs`` are majority ``parse_error`` is stamped 'parse_fail' — catching #37 plus any daily L1s
that fire before this lands.

Idempotent: SQLite has no ``ADD COLUMN IF NOT EXISTS`` → guard on ``PRAGMA table_info``; the backfill
only stamps still-NULL rows.
"""

from __future__ import annotations

import sqlite3


def apply(conn: sqlite3.Connection) -> None:
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(runs)").fetchall()}
    if "council_health" not in cols:
        conn.execute("ALTER TABLE runs ADD COLUMN council_health TEXT")
    if "model_mix" not in cols:
        conn.execute("ALTER TABLE runs ADD COLUMN model_mix TEXT")

    # Computed backfill: stamp any council run whose proposer outputs are MAJORITY parse_error. The raw
    # is persisted via json.dumps → the parse_error fallback serializes as '"parse_error": true'.
    conn.execute(
        "UPDATE runs SET council_health = 'parse_fail' "
        "WHERE council_health IS NULL AND id IN ("
        "  SELECT cp.run_id FROM council_proposals cp "
        "  JOIN council_agent_outputs ao ON ao.proposal_id = cp.id AND ao.role = 'proposer' "
        "  GROUP BY cp.run_id "
        "  HAVING SUM(CASE WHEN ao.raw LIKE '%\"parse_error\": true%' THEN 1 ELSE 0 END) * 2 > COUNT(*)"
        ")"
    )
