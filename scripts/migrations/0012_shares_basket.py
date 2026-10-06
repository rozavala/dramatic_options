"""Migration 0012 — the SHARES descriptive null (PREREG_FIXED_BASKET_NULL.md §2/§5, PR2c).

The last, secondary book of the fixed-basket null hierarchy: **convexity vs linear** — what holding the
SHARES (linear, no premium bleed) of the same option-eligible basket names would have returned, as context
for whether the convex book's bounded-downside / fat-upside is worth the premium bleed. Read as
calibration, **never a pass-gate** (guardrail §6); explicitly **not** scored against the option tails.

Unlike the option null books (`fixed_basket_positions`, which mirror `shadow_positions` field-for-field),
this is an **append-only ENTRY LOG**: it stores only the forward entry (spot / as-of / motion-direction).
Signed returns are computed **at report time from bars** at a horizon SET {180, 270, 365} with the §6
terminal-event survivorship guard — so the read is horizon-comparable to the option lifecycle (~250d
median hold) and an event the fixed-180d resolve would miss is captured at the longer horizons. There is
NO broker, no marking, no stored return.
"""

from __future__ import annotations

import sqlite3


def apply(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS shares_positions ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  run_id INTEGER,"
        "  basket TEXT,"                                 # the curated theme the name was drawn from
        "  symbol TEXT NOT NULL,"
        "  direction TEXT NOT NULL,"                     # MOTION-derived (discovery.direction_of)
        "  entry_spot REAL NOT NULL,"                    # the SAME underlying spot the eligibility pass saw
        "  entry_at TEXT NOT NULL,"                      # as-of of the forward entry (returns measured from here)
        "  created_at TEXT DEFAULT (datetime('now'))"
        ")"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_shares_symbol_entry ON shares_positions(symbol, entry_at)")
