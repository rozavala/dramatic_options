"""Streamlit-free snapshot assembly for the read-only observability API.

Mirrors ``dashboard.load_all()`` (dashboard.py:49) panel-for-panel, but:

  - imports **no streamlit** — the serving runtime stays streamlit-free (``dashboard_data`` is the
    pure, tested data layer by design; ``dashboard.py`` is only the st.* render shell);
  - injects ``system_status`` — ``dd.system_status`` runs over the ASSEMBLED snapshot, so it is NOT
    one of ``load_all``'s panels; the UI status banner has no source without it;
  - sanitizes numpy scalars/arrays → native Python so the dict is JSON-serializable (``dashboard_data``
    ``round()``s most floats, but percentile/bootstrap paths can still leak ``np.float64``).

SAFETY — identical contract to the Streamlit shell: read-only (``dd.connect_ro`` → ``?mode=ro``; a write
raises), NO-FETCH (``MarketData(client=None)`` ⇒ a cache miss surfaces as "accruing", never a network
call), fail-soft (every panel via ``dd.safe`` — one failure never blanks the snapshot), keyless (the
caller sets ``DRAMATIC_SKIP_DOTENV=1``), short-lived connection (opened per call, closed in ``finally``).
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# dashboard_data / config_loader live at the repo root (two levels up); make them importable when this
# module is loaded directly (tests) or by the API server, regardless of CWD.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import numpy as np  # noqa: E402

import dashboard_data as dd  # noqa: E402
from config_loader import load_config  # noqa: E402

# The load_all panels in order. Kept as data so the parity test (test_snapshot_parity.py) can assert this
# list == dashboard.load_all's keys (catching drift if the live shell gains/loses a panel).
PANEL_KEYS: tuple[str, ...] = (
    "header", "t4", "risk", "account", "regime", "sentinels", "positions", "council", "deliberation",
    "performance", "nulls", "attribution", "funnel", "council_stage", "gate_reasons", "cap_flow",
    "cost", "market_ctx", "dualread", "dualread_runtime", "cheapness", "curation", "data_gathered",
)


def _no_fetch_market(cache_dir: str):
    """A NO-FETCH ``MarketData`` over the cache (``client=None`` ⇒ a cache miss raises ``CacheMiss`` →
    surfaced "accruing" by ``dd.safe``). Mirrors ``dashboard._market``; returns None on any setup error
    (curation then renders "accruing")."""
    try:
        from data.cache import PointInTimeCache
        from data.market import MarketData, default_fetch_window

        now = datetime.now(UTC)
        start, _ = default_fetch_window(now)
        return MarketData(PointInTimeCache(cache_dir), client=None, fetch_start=start, fetch_end=now)
    except Exception:  # noqa: BLE001 — curation degrades to "accruing", never blocks the snapshot
        return None


def to_jsonable(obj: Any) -> Any:
    """Recursively coerce numpy scalars/arrays → native Python so the snapshot survives JSON encoding."""
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def build_snapshot(db_path: str, cache_dir: str, db_exists: bool) -> dict:
    """One read-only snapshot = ``dashboard.load_all()``'s panels + ``system_status``, JSON-sanitized.

    A short-lived read-only connection per call so the WAL reader can't linger and block a deploy-time
    migration. Mirrors ``dashboard.load_all`` — keep ``PANEL_KEYS`` and these calls in sync (parity-tested).
    """
    if not db_exists:
        return {"_fatal": f"no database at {db_path} — set DRAMATIC_DB to the live checkout's DB"}
    config = load_config()
    conn = dd.connect_ro(db_path)
    market = _no_fetch_market(cache_dir)
    try:
        snap: dict[str, Any] = {
            "header": dd.safe(dd.header_status, conn),
            "t4": dd.safe(dd.t4_scoreboard, conn, config),
            "risk": dd.safe(dd.risk_panel, conn, config),
            "account": dd.safe(dd.account_panel, conn, config),
            "regime": dd.safe(dd.regime_panel, conn, config),
            "sentinels": dd.safe(dd.sentinels_panel, conn),
            "positions": dd.safe(dd.positions_panel, conn),
            "council": dd.safe(dd.council_panel, conn, config),
            "deliberation": dd.safe(dd.latest_run_deliberation, conn),
            "performance": dd.safe(dd.performance_panel, conn),
            "nulls": dd.safe(dd.null_hierarchy, conn),
            "attribution": dd.safe(dd.attribution_panel, conn, config),
            "funnel": dd.safe(dd.funnel_panel, conn),
            "council_stage": dd.safe(dd.council_stage_funnel, conn, config),
            "gate_reasons": dd.safe(dd.gate_reasons, conn),
            "cap_flow": dd.safe(dd.cap_binding_flow, conn),
            "cost": dd.safe(dd.cost_ledger, conn),
            "market_ctx": dd.safe(dd.market_context, conn),
            "dualread": dd.safe(dd.gate_dualread_report, conn, config),
            "dualread_runtime": dd.safe(dd.dualread_runtime_panel, conn, config),
            "cheapness": dd.safe(dd.cheapness_watch_panel, conn),
            "curation": dd.safe(dd.curation_panel, conn, config, market),
            "data_gathered": dd.safe(dd.data_gathered_panel, cache_dir),
        }
    finally:
        conn.close()
    # system_status runs over the assembled snapshot (NOT a load_all panel) — the banner's only source.
    snap["system_status"] = dd.safe(dd.system_status, snap)
    return to_jsonable(snap)
