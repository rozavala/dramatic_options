"""The §5 smoke script (scripts/smoke_order_roundtrip.py) — offline guards + the sim round-trip.

The script is OUT OF BAND by construction (never imports the loop, never writes the journal);
these tests pin its safety surface: the in-script budget guard (independent of any broker
class), the fail-closed contract pick, and the full simulated round-trip.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path

_p = Path(__file__).resolve().parent.parent / "scripts" / "smoke_order_roundtrip.py"
_spec = importlib.util.spec_from_file_location("smoke_order_roundtrip", _p)
smoke = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(smoke)


@dataclass
class C:
    symbol: str
    strike: float
    bid: float
    ask: float
    kind: str = "C"


def test_pick_contract_fail_closed_filters():
    spot = 100.0
    chain = [
        C("DEADBID", 125, 0.00, 0.30),          # no bid → SELL_TO_CLOSE couldn't complete
        C("WIDE", 125, 0.05, 0.50),             # spread 164% of mid → out
        C("NEAR", 105, 0.50, 0.60),             # 5% OTM → below the band
        C("RICH", 130, 3.00, 3.20),             # ask×100 = $320 > budget
        C("GOOD", 125, 0.90, 1.00),             # 25% OTM, tight, $100 ≤ budget
        C("ALSOGOOD", 130, 1.10, 1.20),         # qualifying but pricier ask than GOOD
    ]
    best = smoke.pick_contract(chain, underlying_price=spot, budget=250.0)
    assert best is not None and best.symbol == "GOOD"
    assert smoke.pick_contract([], underlying_price=spot, budget=250.0) is None


def test_budget_guard_is_script_level():
    # Even a broker with no ceiling must be bounded by the script's own budget check.
    from broker import PaperBroker
    rc = smoke.run_roundtrip(PaperBroker(100_000.0), contract_symbol="X", buy_limit=3.00,
                             sell_limit=1.00, budget=250.0, log=lambda *_: None)
    assert rc == 2  # 3.00×100 = $300 > $250 → refused before any submit


def test_sim_roundtrip_completes():
    from broker import PaperBroker
    lines = []
    rc = smoke.run_roundtrip(PaperBroker(100_000.0), contract_symbol="PL270115C00040000",
                             buy_limit=1.00, sell_limit=0.50, budget=250.0, log=lines.append)
    assert rc == 0
    assert any("ROUND-TRIP COMPLETE" in ln for ln in lines)


def test_script_never_touches_the_journal():
    src = _p.read_text()
    assert "state." not in src and "import state" not in src
    assert "council" not in src.lower() or "never the council" in src  # doc mention only
    assert "record_convexity_position" not in src
