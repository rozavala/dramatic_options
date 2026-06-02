"""Migration 0007 — sentinel inflection discovery (T3): the candidate-discovery substrate.

T3 adds a discovery layer UPSTREAM of the council (the hard seam is unchanged — discovery
PROPOSES candidates, the council JUDGES, the deterministic Layer-1 gates DISPOSE). This schema
is the **forward-scoring substrate** for that layer (guardrail §6 — validated forward, never
backtested):

``sentinel_candidates`` — one row per discovered lineage (a ``(symbol, direction)`` bet) plus the
per-scan random **control** cohort (``kind='control'`` — the forward null≈signal test). A lineage
is updated in place on re-surface (``surface_count``/``last_seen_at`` bump, ``status`` back to
'candidate'), so a secular theme that dips below threshold and returns stays **one continuous bet**
rather than fragmenting into "new discoveries". A tailwind→rollover flip is a *new* lineage with a
``related_lineage`` cross-ref. Forward fields (``outcome``/``brier``/``realized_multiple``/
``reference_return``/``terminal_event``) resolve months later at position close OR via the
label-only reference forward-return for never-traded names + controls.

Plus ``sentinel_id`` on ``council_proposals`` — the provenance chain sentinel → proposal →
position, so a discovered candidate's eventual trade outcome links back to the discovery that
surfaced it. Idempotent.
"""

from __future__ import annotations

import sqlite3


def apply(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sentinel_candidates ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  run_id INTEGER,"
        "  lineage_key TEXT NOT NULL,"        # '<SYMBOL>|<direction>' — the persistent identity
        "  kind TEXT NOT NULL DEFAULT 'sentinel',"  # 'sentinel' | 'control' (the null cohort)
        "  symbol TEXT NOT NULL,"
        "  basket TEXT,"                      # the scan basket the name came from (origin)
        "  theme TEXT,"                       # the framed theme (framer may name it; basket default)
        "  direction TEXT NOT NULL,"          # 'bullish' (tailwind) | 'bearish' (rollover)
        "  inflection_score REAL,"            # within-basket rank score (FUNNEL, not a signal)
        "  markers TEXT,"                     # JSON: the deterministic marker values (the grounding corpus)
        "  rationale_multi TEXT,"             # JSON: multi-theme rationale unioned onto the lineage
        "  framer_conviction TEXT,"           # LOW|MODERATE|HIGH|EXTREME|NEUTRAL (PR2; NULL in PR1)
        "  structural_vs_fad TEXT,"
        "  seed_thesis TEXT,"
        "  confound_label TEXT,"              # PR2: real_inflection | artifact | mean_reversion
        "  cost_usd REAL,"
        "  provider TEXT,"
        "  model TEXT,"
        "  status TEXT NOT NULL DEFAULT 'candidate',"  # candidate | dormant | expired | superseded | control
        "  surface_count INTEGER NOT NULL DEFAULT 1,"
        "  discovered_at TEXT NOT NULL,"
        "  last_seen_at TEXT,"
        "  related_lineage TEXT,"             # cross-ref to a flipped (opposite-direction) lineage
        "  proposal_id INTEGER,"              # set when the council traded this sentinel
        "  outcome INTEGER,"                  # 1 favorable / 0 unfavorable / NULL unresolved (never fabricated)
        "  brier REAL,"
        "  realized_multiple REAL,"           # realized P&L ÷ entry premium (tail-aware, not just binary)
        "  reference_return REAL,"            # label-only fwd return for never-traded names + controls
        "  terminal_event TEXT,"              # NULL | 'horizon' | 'acquired' | 'delisted' (survivorship guard)
        "  resolved_at TEXT,"
        "  created_at TEXT,"
        "  FOREIGN KEY (run_id) REFERENCES runs(id),"
        "  FOREIGN KEY (proposal_id) REFERENCES council_proposals(id)"
        ")"
    )
    # One live (non-terminal) lineage per identity — re-surface UPDATEs in place (provenance
    # continuity), it does not insert a duplicate. Controls are per-scan and excluded from the
    # uniqueness (many control rows share no lineage identity).
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_sentinel_live_lineage "
        "ON sentinel_candidates(lineage_key) "
        "WHERE kind = 'sentinel' AND status IN ('candidate', 'dormant')"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_sentinel_active "
        "ON sentinel_candidates(kind, status, inflection_score)"
    )
    # Provenance chain: a council proposal can originate from a sentinel discovery.
    try:
        conn.execute("ALTER TABLE council_proposals ADD COLUMN sentinel_id INTEGER")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e).lower():
            raise
