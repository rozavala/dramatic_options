"""Migration 0010 — the no-gate / fixed-basket null books (PREREG_FIXED_BASKET_NULL.md).

The forward null that tests the IV **gate** itself (the existing real/shadow pair only tests the
council). A parallel, **simulated-only** options book that runs the SAME deterministic pipeline minus
the IV gate, so `shadow − 3A` is the FSSD null≈signal control on the edge.

`fixed_basket_positions` **mirrors `shadow_positions` field-for-field** (an explicit design goal — so
the eventual unification of the null books into one gate×universe×instrument table is a mechanical
union, not a reconciliation), plus a **`book`** discriminator: 'union_nogate' = 3A (gate-off over the
candidate union, cap-ON, PR2a); 'basket_nogate' = 3B (gate-off over the whole basket, equal-weight,
PR2b). Same never-broker `open → closed` lifecycle (no pending/closing/order_id — there is no broker).
"""

from __future__ import annotations

import sqlite3


def apply(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS fixed_basket_positions ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  run_id INTEGER,"
        "  book TEXT NOT NULL,"                          # 'union_nogate' (3A) | 'basket_nogate' (3B)
        "  origin TEXT NOT NULL DEFAULT 'hand_seed',"    # 'hand_seed' | 'sentinel' — decompose like the shadow book
        "  opened_at TEXT NOT NULL,"
        "  theme TEXT,"
        "  symbol TEXT NOT NULL,"
        "  direction TEXT NOT NULL,"
        "  structure_kind TEXT,"
        "  contract_symbol TEXT NOT NULL,"
        "  expiry TEXT,"
        "  strike REAL,"
        "  dte INTEGER,"
        "  moneyness REAL,"
        "  contracts INTEGER NOT NULL,"
        "  entry_premium_per_contract REAL NOT NULL,"
        "  total_premium REAL NOT NULL,"
        "  entry_spot REAL,"
        "  status TEXT NOT NULL DEFAULT 'open',"         # 'open' | 'closed' (no broker ⇒ no pending/closing)
        "  mark REAL,"
        "  marked_at TEXT,"
        "  realized_pnl REAL,"
        "  realized_multiple REAL,"                      # exit value ÷ entry premium — the tail-aware magnitude
        "  exit_reason TEXT,"
        "  closed_at TEXT,"
        "  created_at TEXT DEFAULT (datetime('now'))"
        ")"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fixedbasket_book_status ON fixed_basket_positions(book, status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fixedbasket_origin ON fixed_basket_positions(origin)")
