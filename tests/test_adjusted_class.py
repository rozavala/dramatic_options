"""The OCC adjusted-class guard + per-position mark resilience (the 2026-07-06 CDE2 defect).

3A booked ``CDE2270115P00012000`` — a corporate-action-ADJUSTED class whose root (CDE2) is not
the underlying ticker: a different payoff object (non-standard deliverables) that the gate and
sizing math would misprice, and unquotable on underlying-keyed endpoints (every L2 mark pass
then failed + paged). Two fixes under test: ``select_structure`` excludes adjusted roots when
``underlying_symbol`` is passed (all seven library call sites pass it, including the REAL
book's), and one unquotable row can no longer abort a mark pass.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

import risk
import shadow_book
import state
from clock import FixedClock
from structure import contract_eligible, occ_root, select_structure

AS_OF = date(2026, 7, 6)


def test_occ_root_hand_checked():
    assert occ_root("CDE2270115P00012000") == "CDE2"
    assert occ_root("CDE270115C00020000") == "CDE"
    assert occ_root("PL270115C00040000") == "PL"
    assert occ_root("UUUU270115C00017000") == "UUUU"


class _C:
    def __init__(self, symbol, kind, expiry, strike, bid, ask, oi=500):
        self.symbol, self.kind, self.expiry, self.strike = symbol, kind, expiry, strike
        self.bid, self.ask, self.oi = bid, ask, oi


def _elig(c):
    return contract_eligible(c, max_spread_pct=0.25, min_contract_price=0.10,
                             max_contract_price=100.0, min_oi=50)


def test_adjusted_class_never_selected_even_when_nearest():
    # The adjusted contract sits EXACTLY at the 25%-OTM target; the standard one is further out.
    # Without the guard the adjusted class wins on strike distance — with it, never.
    chain = [
        _C("CDE2270115P00012000", "P", date(2027, 1, 15), 12.0, 1.00, 1.10),  # adjusted, at-target
        _C("CDE270115P00011000", "P", date(2027, 1, 15), 11.0, 0.90, 1.00),   # standard
    ]
    s, _ = select_structure(chain, direction="bearish", as_of=AS_OF, underlying_price=16.0,
                            tenor_min_days=180, tenor_max_days=365, target_moneyness=0.25,
                            eligibility=_elig, underlying_symbol="CDE")
    assert s is not None and s.contract.symbol == "CDE270115P00011000"
    # Only adjusted contracts in the window → fail-closed to no_structure.
    s2, why = select_structure(chain[:1], direction="bearish", as_of=AS_OF, underlying_price=16.0,
                               tenor_min_days=180, tenor_max_days=365, target_moneyness=0.25,
                               eligibility=_elig, underlying_symbol="CDE")
    assert s2 is None and "no_eligible_contract_in_tenor_window" in why
    # Back-compat: without underlying_symbol the old behavior stands (callers all pass it now).
    s3, _ = select_structure(chain, direction="bearish", as_of=AS_OF, underlying_price=16.0,
                             tenor_min_days=180, tenor_max_days=365, target_moneyness=0.25,
                             eligibility=_elig)
    assert s3 is not None and s3.contract.symbol == "CDE2270115P00012000"


def test_mark_pass_survives_one_unquotable_row(convexity_db, monkeypatch):
    # Two open shadow positions; the quote provider RAISES on the first (the CDE2 shape) —
    # the second must still mark, nothing escapes to the batch layer.
    monkeypatch.delenv("KILL", raising=False)
    monkeypatch.setattr(risk, "KILL_FILE", Path("/nonexistent/KILL"))
    for sym, contract in (("CDE", "CDE2270115P00012000"), ("PAAS", "PAAS270319P00035000")):
        state.record_shadow_position(
            convexity_db, run_id=None, origin="sentinel", opened_at="2026-07-06T19:48:00+00:00",
            theme="t", symbol=sym, direction="bearish", structure_kind="P",
            contract_symbol=contract, expiry="2027-01-15", strike=12.0, dte=190,
            moneyness=0.25, contracts=1, entry_premium_per_contract=300.0, total_premium=300.0,
            entry_spot=16.0)

    class _Boom:
        def option_mid(self, contract_symbol):
            if contract_symbol.startswith("CDE2"):
                raise RuntimeError('{"message":"invalid underlying symbol: CDE2"}')
            return 3.10

    res = shadow_book.mark_shadow_positions(
        conn=convexity_db, clock=FixedClock(datetime(2026, 7, 6, 20, 0, tzinfo=UTC)),
        quote_provider=_Boom(), config={"convexity_exits": {"profit_take_multiple": 10.0,
                                                            "time_stop_dte": 21}})
    assert res.marked == 1 and res.unmarked == 1
    marks = {r["symbol"]: r["mark"] for r in convexity_db.execute(
        "SELECT symbol, mark FROM shadow_positions")}
    assert marks["PAAS"] == pytest.approx(3.10) and marks["CDE"] is None
