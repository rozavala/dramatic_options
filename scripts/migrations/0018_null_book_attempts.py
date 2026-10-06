"""Migration 0018 — ``null_book_attempts``: per-name booking-attempt telemetry for the capped
null books (shadow + 3A).

Why a TABLE and not a log line: the 2026-07-02 burst grade could not attribute UROY's terminal
veto (aggregate per-reason counters only — recorded as inference, not observation), and the
journald retention on the box is ~2 weeks (the 2026-06-19 L1 journal was already gone on
2026-07-02) while the capped-shadow counterfactual must stay replayable for MONTHS — from
vintage 2b the ``real − shadow`` read is cap-regime-bundled, and its cost is ~zero only if the
capped composition can be deterministically replayed: per-name attempt ORDER + terminal outcome
+ premium-at-attempt.

One row per candidate the booking pass touches, in walk order (``attempt_idx``): outcome is
``booked`` | a veto reason (``no_structure``/``not_cheap``/``cluster_cap``/``sizing``/
``sentinel_slots``) | ``skip_open`` | ``error``. ``entry_premium_per_contract`` is the
structure's premium at attempt time when one was selected (NULL before structure selection —
``no_structure``/``skip_open``/``sentinel_slots``/``error``). Telemetry only: written fail-soft
(a write failure logs WARNING and never blocks the pass), read at grade/replay time, never by
the booking path itself. Never-broker unaffected.

Idempotent: guard on the table's existence.
"""

from __future__ import annotations

import sqlite3


def apply(conn: sqlite3.Connection) -> None:
    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='null_book_attempts'"
    ).fetchone()
    if exists is None:
        conn.execute(
            "CREATE TABLE null_book_attempts ("
            " id INTEGER PRIMARY KEY,"
            " run_id INTEGER,"
            " book TEXT NOT NULL,"                 # 'shadow' | '3A'
            " attempt_idx INTEGER NOT NULL,"       # the union walk order within (run, book), 0-based
            " symbol TEXT NOT NULL,"
            " direction TEXT,"
            " origin TEXT,"                        # 'hand-seed' | 'sentinel'
            " outcome TEXT NOT NULL,"              # 'booked' | veto reason | 'skip_open' | 'error'
            " entry_premium_per_contract REAL,"    # premium at attempt when a structure was selected
            " as_of TEXT,"
            " created_at TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE INDEX ix_null_attempts_run_book ON null_book_attempts(run_id, book, attempt_idx)"
        )
