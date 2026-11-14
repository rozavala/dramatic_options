"""Migration 0022 — the #456 council repeat-read probe's own tables (PREREG_COUNCIL_GATE_SEPARATION §10.12;
records/2026-11-14_council_repeat_probe_armA_PREREG.md §5).

- ``council_repeat_packs``: the capture. One row per council proposal whose candidate reached the strategist, written
  by the council path ONLY while ``council.repeat_probe.enabled`` is on: the serialized ``ContextPack`` and the sha256
  of the strategist's rendered user text. ``proposal_id`` links it to the ``council_proposals`` row of record.
- ``council_repeat_reads``: one row per strategist repeat the probe makes (k per name), post-processed exactly like
  the record (the same quote filter + the shared §10.7 coercion). ``excluded_reason`` is NULL for a repeat that
  counts toward agreement, else ``understudy`` | ``parse_error`` | ``provider_error``.
- ``council_repeat_sessions``: one row per L1 run the probe acted on (its own session count — it refuses an 11th —
  and the segment's model_mix anchor + stop status).

Measurement only, never read by the council, the gates, sizing or any entry. The probe NEVER writes
``council_proposals`` or ``council_agent_outputs`` (Brier, contribution scoring and the forward record stay untouched).

Idempotent: guarded on each table's existence.
"""

from __future__ import annotations

import sqlite3


def _exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def apply(conn: sqlite3.Connection) -> None:
    if not _exists(conn, "council_repeat_packs"):
        conn.execute(
            "CREATE TABLE council_repeat_packs ("
            " id INTEGER PRIMARY KEY,"
            " run_id INTEGER,"
            " proposal_id INTEGER NOT NULL UNIQUE,"   # the council_proposals row of record
            " symbol TEXT NOT NULL,"
            " pack_json TEXT NOT NULL,"               # council/repeat_capture.py pack_to_json (lossless, checked)
            " prompt_sha256 TEXT NOT NULL,"           # sha256 of the strategist's rendered user text at L1 time
            " created_at TEXT NOT NULL)"
        )
        conn.execute("CREATE INDEX ix_council_repeat_packs_run ON council_repeat_packs(run_id)")
    if not _exists(conn, "council_repeat_sessions"):
        conn.execute(
            "CREATE TABLE council_repeat_sessions ("
            " id INTEGER PRIMARY KEY,"
            " run_id INTEGER NOT NULL UNIQUE,"        # the L1 run probed (one probe session per council of record)
            " session_date_et TEXT NOT NULL,"
            " model_mix TEXT,"                        # runs.model_mix of that L1 (the segment anchor)
            " status TEXT NOT NULL,"                  # running | done | stopped_session_cap | stopped_segment_cap |
                                                      # stopped_provider_error | stopped_model_mix
            " k INTEGER,"
            " names_captured INTEGER,"
            " names_probed INTEGER,"
            " repeats INTEGER,"
            " summary TEXT,"                          # JSON: excluded/skipped counts by reason
            " cost_usd REAL,"
            " started_at TEXT NOT NULL,"
            " finished_at TEXT)"
        )
    if not _exists(conn, "council_repeat_reads"):
        conn.execute(
            "CREATE TABLE council_repeat_reads ("
            " id INTEGER PRIMARY KEY,"
            " session_id INTEGER,"
            " run_id INTEGER NOT NULL,"
            " proposal_id INTEGER NOT NULL,"
            " symbol TEXT NOT NULL,"
            " repeat_idx INTEGER NOT NULL,"           # 0..k-1
            " provider TEXT,"                         # who actually answered (the understudy shows here)
            " model TEXT,"
            " raw TEXT,"                              # the parsed (and coerced) strategist JSON, like the record's raw
            " raw_confidence TEXT,"                   # the strategist's own conviction, before the quote filter
            " conviction TEXT,"                       # final, post-filter (normalize_conviction), like the record
            " include INTEGER,"
            " structural_vs_fad TEXT,"                # strategist-or-proposer fallback, like the record
            " under_narrated INTEGER,"                # 1/0, NULL = not asserted as a bool
            " at_inflection INTEGER,"
            " criteria_veto INTEGER,"
            " flagged_unsupported INTEGER,"
            " order_shown TEXT,"                      # for_first | against_first (the record's order, replayed)
            " prompt_sha256 TEXT,"
            " cost_usd REAL,"
            " excluded_reason TEXT,"                  # NULL = counts; understudy | parse_error | provider_error
            " created_at TEXT NOT NULL)"
        )
        conn.execute("CREATE INDEX ix_council_repeat_reads_run ON council_repeat_reads(run_id, proposal_id)")
        conn.execute("CREATE INDEX ix_council_repeat_reads_provider ON council_repeat_reads(provider, created_at)")
