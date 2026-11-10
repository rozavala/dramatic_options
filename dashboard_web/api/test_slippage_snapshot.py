"""#467 step 3: the web snapshot carries the net-of-slippage twin under its own key (read-only, an estimate)."""

from __future__ import annotations

import sys
from pathlib import Path

_API = Path(__file__).resolve().parent
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

import snapshot  # noqa: E402


def test_slippage_is_a_panel_key() -> None:
    assert "slippage" in snapshot.PANEL_KEYS


def test_snapshot_carries_the_twin_and_an_unknown(convexity_db, tmp_path) -> None:
    import state

    c = convexity_db
    for sym, rat in (("FLNC", {"quote": {"bid": 0.90, "ask": 1.10, "mid": 1.00}}), ("OLD", {})):
        state.record_convexity_position(
            c, run_id=None, opened_at="2026-11-04T15:00:00+00:00", theme=f"t-{sym}", symbol=sym, direction="bullish",
            structure_kind="long_call", contract_symbol=f"{sym}270521C00005000", expiry="2027-05-21", strike=5.0,
            dte=200, moneyness=0.25, contracts=10, entry_premium_per_contract=100.0, total_premium=1000.0,
            rationale=rat, status="open")
    db_path = c.execute("PRAGMA database_list").fetchone()[2]
    snap = snapshot.build_snapshot(db_path, str(tmp_path / "cache"), True)
    sl = snap["slippage"]
    assert "error" not in sl and "#467" in sl["note"]
    rows = {r["symbol"]: r for r in sl["rows"]}
    assert rows["FLNC"]["conservative_px"] == 1.10 and rows["FLNC"]["premium_conservative_usd"] == 1100.0
    assert rows["OLD"]["conservative_px"] is None and rows["OLD"]["premium_conservative_usd"] is None
    assert sl["totals"]["known"] == 1 and sl["totals"]["unknown"] == 1
