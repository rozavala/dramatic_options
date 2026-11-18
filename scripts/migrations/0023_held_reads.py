"""Migration 0023 — ``held_reads``: the #464 held-name thesis reads (PREREG_COUNCIL_GATE_SEPARATION §10.13;
records/2026-11-16_held_name_thesis_tracking_optionB_PREREG.md §2).

One row per (L1 run, held real position): the full debate run once after the L1 on the pack the L1 would build from
the position's own lineage (active or dormant, rendered as-is). Append-only, measurement only: never read by the
council, the gates, sizing, exits, carries, the backfill rank or the persistence watch (§5), and never written to
``council_proposals`` / ``council_agent_outputs``. ``proposal_id`` is the position's ENTRY proposal (the lineage it
was read on), not a new one. ``mark_multiple`` and ``dte`` are for the timeline only and are never in the pack.

Per-role provider/model/cost columns let ``state.provider_month_spend`` attribute the pass's spend to each provider.

Idempotent: guarded on the table's existence.
"""

from __future__ import annotations

import sqlite3


def apply(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='held_reads'").fetchone():
        return
    conn.execute(
        "CREATE TABLE held_reads ("
        " id INTEGER PRIMARY KEY,"
        " position_id INTEGER NOT NULL,"
        " run_id INTEGER NOT NULL,"            # the L1 run this pass followed
        " proposal_id INTEGER,"                # the position's entry proposal (its lineage)
        " symbol TEXT NOT NULL,"
        " direction TEXT NOT NULL,"
        " as_of TEXT NOT NULL,"                # the pack's as_of (the L1 council's)
        " origin TEXT,"                        # hand-seed | sentinel
        " sentinel_id INTEGER,"
        " lineage_status TEXT,"                # the sentinel row's status at read time (candidate, dormant, ...);
                                               # 'hand-seed' for a themes.json name
        " conviction_raw TEXT,"                # the strategist's own conviction, before the quote filter
        " conviction TEXT,"                    # final (normalize_conviction), like the record
        " include INTEGER,"
        " structural_vs_fad TEXT,"
        " under_narrated INTEGER,"
        " at_inflection INTEGER,"
        " criteria_veto INTEGER,"
        " weakest_point TEXT,"
        " dropped TEXT,"                       # the early-exit reason (ungrounded / proposer abstained), else NULL
        " proposer_provider TEXT, proposer_model TEXT, proposer_cost_usd REAL,"
        " adversary_provider TEXT, adversary_model TEXT, adversary_cost_usd REAL,"
        " strategist_provider TEXT, strategist_model TEXT, strategist_cost_usd REAL,"
        " rationale TEXT,"                     # the debate's rationale JSON (as a proposal would carry it)
        " model_mix TEXT,"                     # runs.model_mix of the L1 (segments split on it)
        " cost_usd REAL,"
        " mark_multiple REAL,"                 # mark / entry premium at read time — timeline only, never in the pack
        " dte INTEGER,"                        # days to expiry at read time — timeline only
        " created_at TEXT NOT NULL,"
        " UNIQUE (run_id, position_id))"
    )
    conn.execute("CREATE INDEX ix_held_reads_position ON held_reads(position_id, run_id)")
