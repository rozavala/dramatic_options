"""#494: an eligibility veto names the contracts it refused and why. RDW #8's carry attempt at 10:00 ET was vetoed on
"no_eligible_contract_beyond_min_moneyness" with nothing else recorded, although RDW (8.40) never neared the floor."""

import logging
from datetime import UTC, date, datetime
from pathlib import Path

import risk
from broker import PaperBroker
from clock import FixedClock
from convexity_gate import Contract
from paper_loop import run_paper_cycle
from structure import contract_eligible, select_structure
from themes import Theme

AS_OF = date(2026, 11, 12)


def _p(strike, bid, ask, oi=500):
    return Contract(symbol=f"RDW270521P{int(strike * 1000):08d}", expiry=date(2027, 5, 21), kind="P", strike=strike,
                    bid=bid, ask=ask, iv=0.9, oi=oi)


# the 10:00 ET shape: the far puts' quotes are wide at the open; only the near-money put is tight
CHAIN = [_p(6.0, 0.40, 0.80), _p(7.0, 0.70, 1.10), _p(7.5, 1.00, 1.05)]


def _elig(c):
    return contract_eligible(c, max_spread_pct=0.25, min_contract_price=0.10, max_contract_price=100.0, min_oi=50)


def test_a_floor_veto_names_the_refused_far_contracts_and_why():
    s, why = select_structure(CHAIN, direction="bearish", as_of=AS_OF, underlying_price=8.40, underlying_symbol="RDW",
                              tenor_min_days=180, tenor_max_days=365, target_moneyness=0.25, eligibility=_elig,
                              require_otm_side=True, min_otm_moneyness=0.15)
    assert s is None and why[0] == "no_eligible_contract_beyond_min_moneyness"     # the code stays first
    assert why[1:] == ("refused RDW270521P00006000: spread 67%>25%", "refused RDW270521P00007000: spread 44%>25%")


class _Provider:
    def underlying_price(self, sym):
        return 8.40

    def closes(self, sym, *, window):
        return [8.0 + 0.01 * i for i in range(window)]

    def chain(self, sym):
        return list(CHAIN)


def test_the_veto_is_recorded_and_logged(convexity_db, monkeypatch, caplog):
    monkeypatch.delenv("KILL", raising=False)
    monkeypatch.setattr(risk, "KILL_FILE", Path("/nonexistent/KILL"))
    cfg = {"convexity_book": {"account_equity": 100_000.0, "book_fraction": 0.10, "per_name_fraction": 0.01,
                              "max_open_positions": 15},
           "convexity_gate": {"iv_rv_max": 1.2, "otm_skew_max_volpts": 10.0, "rv_window_days": 30,
                              "tenor_min_days": 180, "tenor_max_days": 365, "target_moneyness": 0.25,
                              "otm_side_guard": True, "min_otm_moneyness": 0.15},
           "convexity_exits": {"profit_take_multiple": 10.0, "time_stop_dte": 21},
           "eligibility": {"live": {"min_option_open_interest": 50, "max_bid_ask_pct": 0.25}},
           "kill_rule": {"book_drawdown_halt": 0.20}}
    with caplog.at_level(logging.INFO, logger="paper_loop"):
        res = run_paper_cycle(config=cfg, conn=convexity_db, clock=FixedClock(datetime(2026, 11, 12, 15, tzinfo=UTC)),
                              provider=_Provider(), broker=PaperBroker(100_000.0),
                              themes=[Theme("space_smallcap", "RDW", "bearish", "x")], run_id=None)
    assert res.vetoed == 1 and res.opened == 0
    row = convexity_db.execute("SELECT decision, reasons FROM convexity_eval ORDER BY id DESC LIMIT 1").fetchone()
    assert row["decision"] == "veto-eligibility" and "refused RDW270521P00006000: spread 67%>25%" in row["reasons"]
    assert any(r.getMessage().startswith("Eligibility veto RDW: no_eligible_contract_beyond_min_moneyness; refused ")
               for r in caplog.records)


def test_a_tenor_veto_names_only_contracts_the_side_guard_and_floor_would_keep():
    # #496 review: an ITM or below-floor refusal would have been vetoed anyway, so it is not named
    chain = [_p(12.0, 2.0, 3.0), _p(9.0, 1.0, 1.6), _p(6.0, 0.40, 0.80)]   # ITM, 10% OTM, 29% OTM: all too wide
    s, why = select_structure(chain, direction="bearish", as_of=AS_OF, underlying_price=8.40, underlying_symbol="RDW",
                              tenor_min_days=180, tenor_max_days=365, target_moneyness=0.25, eligibility=_elig,
                              require_otm_side=True, min_otm_moneyness=0.15)
    assert s is None and why == ("no_eligible_contract_in_tenor_window", "refused RDW270521P00006000: spread 67%>25%")
