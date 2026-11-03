"""#417 — when the selector skips the strike nearest its target, the record says why (spread / OI), on every row.

Record-only: which contract is chosen, and every gate, are unchanged. The evidence #416 (the moneyness-band question)
needs: on L1 #1918 TITN's target-nearest call was refused by eligibility and the DB could not say why."""

from __future__ import annotations

import ast
import dataclasses
import inspect
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import paper_loop
import risk
import state
from broker import PaperBroker
from clock import FixedClock
from convexity_data import SyntheticChainProvider
from convexity_gate import Contract
from paper_loop import run_paper_cycle
from structure import contract_eligible, select_structure
from themes import Theme

AS_OF = date(2026, 1, 2)


def _c(strike, *, bid=2.0, ask=2.1, oi=500, dte=270):
    return Contract(symbol=f"XC{strike}", expiry=AS_OF + timedelta(days=dte), kind="C", strike=strike,
                    bid=bid, ask=ask, iv=0.4, oi=oi)


def _elig(c):
    return contract_eligible(c, max_spread_pct=0.25, min_contract_price=0.10, max_contract_price=100.0, min_oi=50)


def _select(chain):
    return select_structure(chain, direction="bullish", as_of=AS_OF, underlying_price=100.0, tenor_min_days=180,
                            tenor_max_days=365, target_moneyness=0.25, eligibility=_elig, require_otm_side=True)


def test_a_refused_target_nearest_strike_is_carried_with_its_reasons():
    # target strike 125: C125 fails on spread, C130 on open interest; C110 is the nearest eligible
    s, _ = _select([_c(125, bid=1.0, ask=2.0), _c(130, oi=10), _c(110), _c(150)])
    assert s.contract.symbol == "XC110"                                       # the choice itself is unchanged
    assert s.refused_nearer == (("XC125", ("spread 67%>25%",)), ("XC130", ("oi 10<50",)))


def test_nothing_is_carried_when_the_target_nearest_strike_is_chosen():
    s, _ = _select([_c(125), _c(110, bid=1.0, ask=2.0)])                     # a refused strike FARTHER away
    assert s.contract.symbol == "XC125" and s.refused_nearer == ()


def test_at_most_three_refused_strikes_nearest_first():
    s, _ = _select([_c(k, bid=1.0, ask=2.0) for k in (124, 126, 123, 127)] + [_c(105)])
    assert [sym for sym, _ in s.refused_nearer] == ["XC124", "XC126", "XC123"]


def test_the_eval_writer_nests_selection_and_stays_byte_identical_without_it(convexity_db):
    common = dict(run_id=None, as_of="2026-01-02", theme="t", symbol="X", direction="bullish", decision="open")
    state.record_convexity_eval(convexity_db, **common, reasons=["cheap"])
    state.record_convexity_eval(convexity_db, **common, reasons=["cheap"], selection={"refused_nearer": [1]})
    state.record_convexity_eval(convexity_db, **common, reasons=["cheap"], cluster_state={"c": 1},
                                selection={"refused_nearer": [1]})
    rows = [r[0] for r in convexity_db.execute("SELECT reasons FROM convexity_eval ORDER BY id")]
    assert rows[0] == '["cheap"]'                                              # pre-#417 shape, unchanged
    assert json.loads(rows[1]) == {"reasons": ["cheap"], "selection": {"refused_nearer": [1]}}
    assert json.loads(rows[2]) == {"reasons": ["cheap"], "cluster_state": {"c": 1}, "selection": {"refused_nearer": [1]}}


def test_every_eval_row_written_after_selection_carries_it():
    src = inspect.getsource(paper_loop._process_theme)
    fn = ast.parse(src.lstrip()).body[0]
    sel = next(n.lineno for n in ast.walk(fn) if isinstance(n, ast.Assign)
               and any(getattr(t, "id", "") == "selection" for t in n.targets))
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "record_convexity_eval"]
    after = [n for n in calls if n.lineno > sel]
    assert len(after) >= 8
    assert all(any(k.arg == "selection" for k in n.keywords) for n in after)


class _WidenNearest(SyntheticChainProvider):
    """The synthetic chain with the call nearest 25% OTM widened past the 25% spread cap (the TITN #1918 shape)."""

    def chain(self, symbol):
        ch = super().chain(symbol)
        spot = self.underlying_price(symbol)
        calls = [c for c in ch if c.kind == "C" and 180 <= (c.expiry - self._as_of_date()).days <= 365]
        near = min(calls, key=lambda c: (abs(c.strike - spot * 1.25), abs((c.expiry - self._as_of_date()).days - 272.5)))
        self.widened = near.symbol
        return [dataclasses.replace(c, bid=round(c.ask * 0.3, 2)) if c.symbol == near.symbol else c for c in ch]

    def _as_of_date(self):
        return CLOCK.now().date()


CLOCK = FixedClock(datetime(2026, 1, 2, tzinfo=UTC))
CONFIG = {
    "convexity_book": {"account_equity": 100_000.0, "book_fraction": 0.10, "per_name_fraction": 0.01,
                       "max_open_positions": 15},
    "convexity_gate": {"iv_rv_max": 1.2, "otm_skew_max_volpts": 10.0, "rv_window_days": 252, "tenor_min_days": 180,
                       "tenor_max_days": 365, "target_moneyness": 0.25, "otm_side_guard": True},
    "eligibility": {"live": {"min_option_open_interest": 50, "max_bid_ask_pct": 0.25}},
    "kill_rule": {"book_drawdown_halt": 0.20, "dry_months_halt": 9},
}


def test_a_paper_cycle_records_why_the_nearer_strike_was_refused(convexity_db, monkeypatch):
    monkeypatch.delenv("KILL", raising=False)
    monkeypatch.setattr(risk, "KILL_FILE", Path("/nonexistent/KILL"))
    prov = _WidenNearest(as_of=CLOCK.now().date())
    run_paper_cycle(config=CONFIG, conn=convexity_db, clock=CLOCK, provider=prov, broker=PaperBroker(100_000.0),
                    themes=[Theme("copper", "FCX", "bullish", "cheap industrial tailwind")], run_id=None)
    row = convexity_db.execute("SELECT decision, reasons FROM convexity_eval WHERE symbol='FCX'").fetchone()
    sel = json.loads(row["reasons"])["selection"]["refused_nearer"]
    assert sel[0]["contract"] == prov.widened and sel[0]["reasons"][0].startswith("spread ")
