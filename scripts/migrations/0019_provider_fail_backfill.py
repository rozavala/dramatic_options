"""Migration 0019 — COMPUTED backfill of ``runs.council_health='provider_fail'`` (the
2026-08-26 anthropic spend-cap incident; the 0011 parse_fail-backfill pattern).

A per-candidate provider failure records a dropped proposal whose ``rationale.error``
starts ``provider_error:`` but carries no parse_error flag — so an outage night stamped
``council_health='ok'`` and graded as benign abstention (the #37 silent-inert class in a
third costume; run #1076 on the live DB: 9/12 candidates dropped when the strategist's
provider hit its usage cap). The forward stamp now lives in ``_stamp_council_health``;
this backfill censors already-recorded outage runs from the council-marginal/Brier
attribution the same way 0011 censored #37. The brain-off null books stay valid (they
never run the council).

Computed, not hardcoded: any 'ok' run whose provider-error drop rate ≥ 0.5 over ≥2
recorded proposals flips to 'provider_fail'. Idempotent by construction (a flipped run no
longer matches the 'ok' filter). No schema change — data-only.
"""

from __future__ import annotations

import json
import sqlite3

_RATE = 0.5  # mirrors config council.parse_fail_page_rate's default at backfill time


def apply(conn: sqlite3.Connection) -> None:
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(runs)")}
    if "council_health" not in cols:
        return  # pre-0011 DB shape (fresh test DBs apply 0011 first; nothing to backfill)
    run_ids = [r["id"] for r in conn.execute(
        "SELECT id FROM runs WHERE council_health = 'ok'"
    )]
    for rid in run_ids:
        rows = conn.execute(
            "SELECT rationale FROM council_proposals WHERE run_id = ?", (rid,)
        ).fetchall()
        if len(rows) < 2:
            continue
        drops = 0
        for row in rows:
            try:
                err = (json.loads(row["rationale"] or "{}") or {}).get("error", "")
            except (ValueError, TypeError):
                continue
            if isinstance(err, str) and err.startswith("provider_error"):
                drops += 1
        if drops / len(rows) >= _RATE:
            conn.execute(
                "UPDATE runs SET council_health = 'provider_fail' WHERE id = ?", (rid,)
            )
