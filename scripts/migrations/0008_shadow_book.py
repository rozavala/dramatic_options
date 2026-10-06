"""Migration 0008 — the brain-off NULL shadow book (T3 PR3b): the forward control.

The strategic null for "does the council/framer JUDGMENT add value?" — the forward analog of the
FSSD null≈signal test, run at the BOOK level (guardrail §6: validated forward, never backtested). A
parallel, **simulated-only** book that runs the SAME deterministic pipeline the real book uses
(eligibility → IV/cheap-convexity gate → defined-risk structure → sizing → exits) over the SAME
candidate union the council sees, but **BRAIN-OFF**: it books EVERY gate-passer — no council
include/exclude, no framer drop. The gap between this book's forward payoff **tail** and the real
(brain-on) book's is exactly the LLM layer's marginal contribution.

**Load-bearing safety:** this book is simulated-only and **NEVER reaches the broker** — hence its OWN
table with a deliberately simple ``open → closed`` lifecycle (no ``pending``/``closing``/``order_id``,
because there is no broker path to reconcile). Physical isolation (a separate table + a module that
never imports the broker) is what makes "a shadow position can never be submitted" structurally true,
not merely intended (see ``tests/test_shadow_book.py::test_shadow_path_never_touches_the_broker``).

``origin`` ('hand_seed'|'sentinel') decomposes the comparison so the T3 question — does the LLM add
value ON THE DISCOVERED names — is answerable, not just the pooled one. Idempotent.

Scope: this isolates the **LLM layer**. It does NOT answer "does the prescreen+LLM apparatus beat a
fixed thematic basket" — that fixed-basket null is a cheaper, separate sibling (no LLM) on the near
list, and is the null the T4 real-money decision actually hinges on.
"""

from __future__ import annotations

import sqlite3


def apply(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS shadow_positions ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  run_id INTEGER,"
        "  origin TEXT NOT NULL DEFAULT 'hand_seed',"   # 'hand_seed' | 'sentinel' — decompose the LLM contribution
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
        "  status TEXT NOT NULL DEFAULT 'open',"        # 'open' | 'closed' (no broker ⇒ no pending/closing)
        "  mark REAL,"
        "  marked_at TEXT,"
        "  realized_pnl REAL,"
        "  realized_multiple REAL,"                     # exit value ÷ entry premium — the tail-aware magnitude
        "  exit_reason TEXT,"
        "  closed_at TEXT,"
        "  created_at TEXT DEFAULT (datetime('now'))"
        ")"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_shadow_status ON shadow_positions(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_shadow_origin ON shadow_positions(origin)")
