"""#504 — the selector's fail-closed moneyness CEILING, the mirror of the #416 floor (operator word 2026-11-16;
PREREG_THEMATIC_CONVEXITY maximum-moneyness amendment; boundary B 2026-12-07).

A sparse chain's "nearest eligible to the 25% target" landed at 81.2% OTM (KLAR C25 on the W46 probe). With the
ceiling the admitted band is 15–40%: inside it the choice stays nearest-to-target; beyond it, no structure."""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

import state
from clock import FixedClock
from convexity_data import StaticQuoteProvider
from convexity_gate import Contract
from structure import SPREAD_LIMIT_EPS, contract_eligible, select_structure

ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 1, 2)
CEIL = "no_eligible_contract_within_max_moneyness"
FLOOR = "no_eligible_contract_beyond_min_moneyness"


def _c(kind, strike, *, bid=2.0, ask=2.1, oi=500, dte=226):
    return Contract(symbol=f"X{kind}{strike}", expiry=AS_OF + timedelta(days=dte), kind=kind, strike=strike,
                    bid=bid, ask=ask, iv=0.4, oi=oi)


def _elig(c):
    return contract_eligible(c, max_spread_pct=0.25, min_contract_price=0.10, max_contract_price=100.0, min_oi=50)


def _select(chain, *, spot=100.0, direction="bullish", floor=0.15, ceiling=0.40):
    return select_structure(chain, direction=direction, as_of=AS_OF, underlying_price=spot, tenor_min_days=180,
                            tenor_max_days=365, target_moneyness=0.25, eligibility=_elig, require_otm_side=True,
                            min_otm_moneyness=floor, max_otm_moneyness=ceiling)


# ── the selector ─────────────────────────────────────────────────────────────────────────────────────────────────

def test_the_klar_w46_shape_fails_closed_instead_of_buying_81pct_otm():
    # spot 13.80: C25 = 81.2% OTM is the only eligible strike; the nearer C17.5 (26.8%) is refused on its spread
    chain = [_c("C", 25.0), _c("C", 17.5, bid=0.5, ask=1.5)]
    s, _ = _select(chain, spot=13.80, ceiling=None)
    assert s.contract.symbol == "XC25.0" and s.moneyness == pytest.approx(0.8116, abs=1e-4)   # the defect, no ceiling
    s, why = _select(chain, spot=13.80)
    assert s is None and why == (CEIL, "refused XC17.5: spread 100%>25%")                        # #494 detail


def test_inside_the_band_the_nearest_to_target_is_chosen():
    chain = [_c("C", 110.0), _c("C", 118.0), _c("C", 138.0), _c("C", 160.0)]
    assert _select(chain)[0].contract.symbol == "XC118.0"           # 18% beats 38% (|118−125|=7 < 13); 60% excluded
    chain = [_c("C", 110.0), _c("C", 138.0), _c("C", 145.0)]
    assert _select(chain)[0].contract.symbol == "XC138.0"           # 38% is the nearest ADMITTED (45% is beyond 40%)


def test_beyond_the_ceiling_is_refused_even_when_nearer_the_target_than_nothing():
    s, why = _select([_c("C", 150.0), _c("C", 141.0)])
    assert s is None and why == (CEIL,)


def test_puts_measure_the_ceiling_on_the_downside():
    chain = [_c("P", 55.0), _c("P", 62.0)]                          # spot 100: 45% and 38% OTM
    assert _select(chain, direction="bearish")[0].contract.symbol == "XP62.0"
    s, why = _select([_c("P", 55.0)], direction="bearish")
    assert s is None and why[0] == CEIL


def test_exactly_the_ceiling_is_admitted_and_just_beyond_is_not():
    assert _select([_c("C", 140.0)])[0].contract.symbol == "XC140.0"   # 40.0% exactly (float: 0.4000000000000001)
    beyond = 100.0 * (1.40 + 10 * SPREAD_LIMIT_EPS)
    assert _select([_c("C", beyond)])[1] == (CEIL,)


def test_precedence_the_floor_reason_when_the_floor_empties_the_set():
    # every eligible contract below the floor (10%) → the floor's reason, not the ceiling's
    assert _select([_c("C", 110.0)])[1] == (FLOOR,)
    # both sides of the band only: the floor removes 10%, leaving 60% → the ceiling is what empties it
    assert _select([_c("C", 110.0), _c("C", 160.0)])[1] == (CEIL,)
    # nothing eligible at all → the tenor/eligibility reason, before either
    assert _select([_c("C", 125.0, oi=10)])[1][0] == "no_eligible_contract_in_tenor_window"


def test_refusal_detail_lists_only_contracts_inside_the_band():
    chain = [_c("C", 160.0), _c("C", 130.0, oi=10), _c("C", 170.0, oi=10), _c("C", 105.0, oi=10)]
    s, why = _select(chain)
    assert s is None and why == (CEIL, "refused XC130.0: oi 10<50")      # C170 (70%) and C105 (5%) never listed


def test_refused_nearer_excludes_contracts_beyond_the_ceiling():
    # chosen C138 (38%); C126 (26%) refused on OI and nearer the target → listed; C112 (12%) is below the floor.
    s, _ = _select([_c("C", 138.0), _c("C", 126.0, oi=10), _c("C", 112.0, oi=10)])
    assert s.contract.symbol == "XC138.0" and [sym for sym, _ in s.refused_nearer] == ["XC126.0"]
    # without the ceiling a 45%-OTM refusal tied-nearer would be listed; with it, never
    chain = [_c("C", 105.0), _c("C", 145.0, oi=10)]                      # spot 100, floor off: C105 chosen (|105−125|=20)
    s, _ = _select(chain, floor=0.0, ceiling=None)
    assert [sym for sym, _ in s.refused_nearer] == ["XC145.0"]
    s, _ = _select(chain, floor=0.0)
    assert s.contract.symbol == "XC105.0" and s.refused_nearer == ()


@pytest.mark.parametrize("off", [None, 0.0])
def test_no_ceiling_is_byte_identical(off):
    chain = [_c("C", 105.0), _c("C", 125.0, bid=1.0, ask=2.0), _c("C", 181.0), _c("C", 150.0, oi=10)]
    base = select_structure(chain, direction="bullish", as_of=AS_OF, underlying_price=100.0, tenor_min_days=180,
                            tenor_max_days=365, target_moneyness=0.25, eligibility=_elig, require_otm_side=True,
                            min_otm_moneyness=0.15)
    assert base == _select(chain, ceiling=off)
    assert base[0].contract.symbol == "XC181.0"     # C125 refused (spread), C150 refused (OI): the 81% wing, as today


# ── config, frame, callers ───────────────────────────────────────────────────────────────────────────────────────

def test_the_ceiling_is_in_config_and_moves_the_frame():
    from config_loader import frame_version
    cfg = json.loads((ROOT / "config.json").read_text())
    gate = cfg["convexity_gate"]
    assert gate["max_otm_moneyness"] == 0.40 and gate["min_otm_moneyness"] == 0.15
    c = gate["_comment_max_otm_moneyness"]
    assert "#504" in c and "2026-11-16" in c and "2026-12-07" in c
    off = {**cfg, "convexity_gate": {k: v for k, v in gate.items() if k != "max_otm_moneyness"}}
    assert frame_version(cfg) != frame_version(off)                       # the boundary


_WIRE = 'max_otm_moneyness=float(gate.get("max_otm_moneyness", 0.0) or 0.0)'


@pytest.mark.parametrize("module", ["paper_loop.py", "shadow_book.py", "fixed_basket.py", "shares_basket.py",
                                    "gate_dualread.py", "cheapness_watch.py", "scripts/probe_miss_baserate.py",
                                    "scripts/probe_basket_gate_baserate.py", "scripts/probe_basket_feasibility.py",
                                    "scripts/probe_vertical_feasibility.py"])
def test_every_book_gate_and_sweep_path_passes_the_ceiling(module):
    src = (ROOT / module).read_text()
    calls = len(re.findall(r"select_structure\(", src)) - src.count("def select_structure(")
    assert calls >= 1 and src.count(_WIRE) == calls, f"{module}: {calls} call(s), {src.count(_WIRE)} wired"


def test_every_caller_that_passes_the_floor_passes_the_ceiling():
    """AST pin over the whole repo (the #276 side-guard pin's walker): the band is one decision, so no caller may
    carry the floor without the ceiling. Survivor cards pass neither (their own 15–35% band)."""
    from tests.test_otm_side_guard import _select_structure_calls

    calls = list(_select_structure_calls())
    floor = [(rel, ln) for rel, ln, kw in calls if "min_otm_moneyness" in kw]
    assert len(floor) >= 11
    missing = [f"{rel}:{ln}" for rel, ln, kw in calls if "min_otm_moneyness" in kw and "max_otm_moneyness" not in kw]
    assert not missing, f"floor without ceiling: {missing}"
    stray = [f"{rel}:{ln}" for rel, ln, kw in calls if "max_otm_moneyness" in kw and "min_otm_moneyness" not in kw]
    assert not stray
    assert not [rel for rel, _ln, kw in calls if rel == "survivor_cards.py" and "max_otm_moneyness" in kw]


# ── the new reason is classified like the floor's: a structural, OPRA-correct absence ───────────────────────────

def test_the_dual_read_gap_partition_reads_the_ceiling_as_structural():
    from dashboard_data import _gap_note_class
    for note in (CEIL, FLOOR, "no_eligible_contract_in_tenor_window"):
        assert _gap_note_class(note) == "structural"


def test_the_gate_dual_read_records_the_ceiling_reason_from_config():
    """The real dual-read arm, reading the shipped convexity_gate block: a KLAR-shaped chain is recorded as
    ¬structured with the ceiling's reason as its note (then partitioned as structural, above)."""
    import gate_dualread

    gate = json.loads((ROOT / "config.json").read_text())["convexity_gate"]

    class _P:
        def chain(self, symbol):
            return [Contract(symbol="KLAR270617C00025000", expiry=AS_OF + timedelta(days=226), kind="C",
                             strike=25.0, bid=2.0, ask=2.1, iv=0.4, oi=500)]

    row = gate_dualread.shadow_gate_eval(_P(), symbol="KLAR", direction="bullish", rv=0.5, underlying_price=13.80,
                                         gate=gate, eligibility=_elig, as_of=AS_OF)
    assert row == {"structured": False, "note": CEIL}
    row = gate_dualread.shadow_gate_eval(_P(), symbol="KLAR", direction="bullish", rv=0.5, underlying_price=13.80,
                                         gate={k: v for k, v in gate.items() if k != "max_otm_moneyness"},
                                         eligibility=_elig, as_of=AS_OF)
    assert row["structured"] is True and row["wing"] == "KLAR270617C00025000"     # no ceiling: the 81% wing


# ── exits never read the band ────────────────────────────────────────────────────────────────────────────────────

def test_an_open_position_beyond_40pct_is_marked_and_exited_normally(convexity_db):
    """IRDM C75 at 46.7% sits open in two null books: the band is an ENTRY rule, so an 81%-OTM open position still
    marks and still takes profit under the shipped config (which carries the ceiling)."""
    from monitor import monitor_positions

    cfg = json.loads((ROOT / "config.json").read_text())
    config = {"convexity_book": {"account_equity": 100_000.0, "book_fraction": 0.10, "per_name_fraction": 0.01,
                                 "max_open_positions": 15},
              "convexity_exits": {"profit_take_multiple": 4.0, "time_stop_dte": 21},
              "kill_rule": {"book_drawdown_halt": 0.20, "dry_months_halt": 9},
              "convexity_gate": cfg["convexity_gate"]}
    clock = FixedClock(datetime(2026, 6, 1, tzinfo=UTC))
    keep = state.record_convexity_position(
        convexity_db, run_id=None, opened_at="2026-01-01T00:00:00+00:00", theme="t", symbol="KLAR",
        direction="bullish", structure_kind="C", contract_symbol="KLAR261218C00025000", expiry="2026-12-18",
        strike=25.0, dte=270, moneyness=0.812, contracts=1, entry_premium_per_contract=40.0, total_premium=40.0)
    take = state.record_convexity_position(
        convexity_db, run_id=None, opened_at="2026-01-01T00:00:00+00:00", theme="t", symbol="IRDM",
        direction="bullish", structure_kind="C", contract_symbol="IRDM261218C00075000", expiry="2026-12-18",
        strike=75.0, dte=270, moneyness=0.467, contracts=1, entry_premium_per_contract=100.0, total_premium=100.0)
    qp = StaticQuoteProvider({"KLAR261218C00025000": 0.30, "IRDM261218C00075000": 5.0})
    res = monitor_positions(conn=convexity_db, clock=clock, quote_provider=qp, config=config)
    assert res.marked == 2 and res.profit_taken == 1
    rows = {r["id"]: r for r in convexity_db.execute("SELECT id, status, mark, exit_reason FROM convexity_positions")}
    assert rows[keep]["status"] == "open" and rows[keep]["mark"] == 0.30
    assert rows[take]["status"] == "closed" and "profit_take" in rows[take]["exit_reason"]
