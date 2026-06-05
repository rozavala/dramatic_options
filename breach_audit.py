"""Cluster-cap BREACH AUDIT (T4-unlock condition #3) — an INDEPENDENT recompute.

The cluster cap (PREREG_THEMATIC_CONVEXITY §5 amendment 2026-06-03) bounds aggregate entry-premium-at-risk
per correlation cluster. Its enforcement lives in the sizing path (`paper_loop` → `clusters.cluster_open_premium`
+ `convexity_sizing`). This module is the *audit* the amendment was designed to enable: it answers "was every
admitted position within the THEN-LIVE cluster cap?" by **recomputing from first principles** — and it
deliberately **does NOT import the enforcement helpers** (`cluster_open_premium` / `convexity_position_size`),
so a bug in either is *visible* to the audit rather than hidden by re-invoking it (operator red-team R2).

What it trusts (facts / definitions, not enforcement logic):
  - **raw booked `total_premium`** per position (`convexity_positions`) — the realized commitment, a fact;
  - the **cluster MAP** (`clusters.load_cluster_map` — the curated *definition* of which names share a budget);
  - the **stamped cap** per admission (`convexity_eval.cluster_state.cap`, the then-live threshold; falls back
    to the current config cap), with `runs.frame_version` reported as the cross-check, never the source.

A breach = at some position P's admission, the cluster's committed premium (P + every same-cluster position
live at P's `opened_at`, on the committed-incl-pending basis the cap uses) exceeded the cap. **0 breaches over
0 admissions is VACUOUS, not a pass** (`vacuous=True`) — the IMPLEMENTATION_PLAN warns against graduating on
≈zero trades. Read-only; never writes. Scoped to the REAL book (the risk frame T4 graduates).

    python breach_audit.py            # audit the configured live DB
"""

from __future__ import annotations

import json
from typing import Any

import clusters

_EPS = 1e-6
# Booked = ever admitted to the book (held real/sim exposure). 'cancelled' never committed → excluded.
_ADMITTED = ("open", "closing", "pending", "closed")


def _cluster_state_of(reasons: Any) -> dict | None:
    """Extract the per-decision cluster_state stamp from a ``convexity_eval.reasons`` value.

    ``state.record_convexity_eval`` nests it as ``{"reasons": [...], "cluster_state": {...}}`` when present,
    else stores a bare list — so a missing stamp returns None (the cap was inert for that decision)."""
    if not reasons:
        return None
    try:
        obj = json.loads(reasons) if isinstance(reasons, str) else reasons
    except (ValueError, TypeError):
        return None
    return obj.get("cluster_state") if isinstance(obj, dict) else None


def _stamped_caps(conn) -> dict[int, float]:
    """``{position_id: then-live cluster cap}`` from the admission's stamped cluster_state."""
    out: dict[int, float] = {}
    for r in conn.execute(
        "SELECT position_id, reasons FROM convexity_eval WHERE position_id IS NOT NULL"
    ):
        cs = _cluster_state_of(r["reasons"])
        if cs and cs.get("cap") is not None:
            try:
                out[int(r["position_id"])] = float(cs["cap"])
            except (ValueError, TypeError):
                continue
    return out


def _frame_versions(conn) -> dict[int, str | None]:
    """``{run_id: frame_version}`` for the cross-check column (migration 0009)."""
    out: dict[int, str | None] = {}
    try:
        for r in conn.execute("SELECT id, frame_version FROM runs"):
            out[int(r["id"])] = r["frame_version"]
    except Exception:  # noqa: BLE001 — pre-0009 DB: no frame_version column → cross-check unavailable
        pass
    return out


def audit_cluster_breaches(conn, config: dict) -> dict:
    """Independently recompute cluster-cap compliance over the REAL book. Read-only.

    Returns ``{n_admissions, n_clustered_admissions, n_breaches, vacuous, breaches: [...], cap_config,
    frame_versions: [...]}``. ``n_admissions`` counts every booked position; ``n_clustered_admissions`` the
    subset in a curated cluster (only those the cap can bind). ``vacuous`` is True when there is nothing to
    audit (no clustered admission) — a 0/0 pass is NOT evidence the cap works.
    """
    cmap = clusters.load_cluster_map(config)  # the curated DEFINITION (data), not the enforcement code
    book = config.get("convexity_book", {})
    cap_cfg = float(book.get("account_equity", 0.0)) * float(book.get("cluster_fraction", 0.0))
    caps = _stamped_caps(conn)
    frames = _frame_versions(conn)

    placeholders = ",".join("?" * len(_ADMITTED))
    rows = conn.execute(
        f"SELECT id, symbol, total_premium, opened_at, closed_at, run_id FROM convexity_positions "
        f"WHERE status IN ({placeholders}) ORDER BY opened_at, id",
        _ADMITTED,
    ).fetchall()
    positions = [dict(r) for r in rows]

    n_admissions = len(positions)
    n_clustered = 0
    breaches: list[dict] = []
    seen_frames: set = set()

    for p in positions:
        cluster = clusters.cluster_of(p["symbol"], cmap)
        if cluster is None:
            continue  # unclustered singleton → the cluster cap is inert (per-name still binds)
        n_clustered += 1
        members = clusters.members_of(cluster, cmap)
        cap = caps.get(int(p["id"]), cap_cfg)
        # Committed-incl-pending at P's admission: P + every same-cluster position live at P.opened_at
        # (opened on/before, not closed before). Recomputed from RAW booked premia — never cluster_open_premium.
        committed = float(p["total_premium"] or 0.0)
        for q in positions:
            if q["id"] == p["id"] or q["symbol"] not in members:
                continue
            if q["opened_at"] <= p["opened_at"] and (q["closed_at"] is None or q["closed_at"] > p["opened_at"]):
                committed += float(q["total_premium"] or 0.0)
        seen_frames.add(frames.get(int(p["run_id"])) if p["run_id"] is not None else None)
        if committed > cap + _EPS:
            breaches.append({
                "position_id": int(p["id"]), "symbol": p["symbol"], "cluster": cluster,
                "committed": round(committed, 2), "cap": round(cap, 2), "opened_at": p["opened_at"],
                "frame_version": frames.get(int(p["run_id"])) if p["run_id"] is not None else None,
            })

    return {
        "n_admissions": n_admissions,
        "n_clustered_admissions": n_clustered,
        "n_breaches": len(breaches),
        "vacuous": n_clustered == 0,
        "breaches": breaches,
        "cap_config": round(cap_cfg, 2),
        "frame_versions": sorted(f for f in seen_frames if f is not None),
    }


def main() -> int:
    import state
    from config_loader import load_config

    config = load_config()
    conn = state.get_db(config)
    try:
        print(json.dumps(audit_cluster_breaches(conn, config), indent=2))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
