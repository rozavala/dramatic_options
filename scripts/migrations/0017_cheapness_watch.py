"""Migration 0017 — ``cheapness_watch`` table (PREREG_CHEAPNESS_WATCH, finding #1's gating instrument).

The live arm: per active sentinel, per day, the gate-cheap read on the **real tradeable structure**
(``select_structure`` + ``is_cheap_convexity`` — the same wing a live entry picks, the real-extractor)
plus the marker state, so the §2.1 state machine (break-onset / sustained-close / ``never_cheap`` / the
``marker_age_at_break`` JOINT / the N-floor verdict) is computed at report time over the daily history.

Read-only MEASUREMENT — never a trade, never wired into ``at_inflection`` (the hard seam). ``cheap`` is
NULL **only** when no eligible structure exists at all (``no_structure``). A fail-closed gate WITH a
structure present writes ``0`` (not NULL): the missing-input fail-close (``GateVerdict(False, None, …)``)
records ``cheap=0`` with ``iv_rv IS NULL`` — that pair is the ``unmeasurable`` marker the §2.1.8
reclassification reads (distinct from a genuine ``cheap=0`` rich read, which carries a present ``iv_rv``).
``marker_age_days`` is the staleness at the observation (``as_of − markers_asof``, the migration-0016
stamp); the onset row's value becomes ``marker_age_at_break``.

Idempotent: guard on the table's existence.
"""

from __future__ import annotations

import sqlite3


def apply(conn: sqlite3.Connection) -> None:
    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='cheapness_watch'"
    ).fetchone()
    if exists is None:
        conn.execute(
            "CREATE TABLE cheapness_watch ("
            " id INTEGER PRIMARY KEY,"
            " run_id INTEGER,"
            " as_of TEXT NOT NULL,"
            " symbol TEXT NOT NULL,"
            " contract_symbol TEXT,"
            " iv_rv REAL,"
            " otm_skew REAL,"
            " cheap INTEGER,"            # the gate's cheap boolean (1/0); NULL = no_structure ONLY (cheap=0 ∧ iv_rv IS NULL = the missing-input fail-close = unmeasurable, §2.1.8)
            " atm_iv REAL,"
            " wing_iv REAL,"
            " rv REAL,"
            " rv_rising REAL,"           # marker — break-onset detection at report time (§2.1.1)
            " mom_recent REAL,"
            " markers_asof TEXT,"        # the sentinel's last_seen_at (the markers' as-of)
            " marker_age_days REAL,"     # as_of − markers_asof (staleness at this obs; → marker_age_at_break)
            " created_at TEXT NOT NULL)"
        )
        conn.execute("CREATE INDEX ix_cheapness_watch_symbol_asof ON cheapness_watch(symbol, as_of)")
