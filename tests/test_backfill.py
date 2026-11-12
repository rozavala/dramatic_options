"""Ranked backfill (PREREG_THEMATIC_CONVEXITY §5 amendment 2026-11-03): inert when off, one per week, gates intact."""

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import backfill
import risk
import state
from broker import PaperBroker
from clock import FixedClock
from convexity_data import SyntheticChainProvider
from council.router import FakeRouter, _parse_candidate_header
from council.wiring import council_to_themes
from paper_loop import run_paper_cycle
from themes import Theme

NOW = datetime(2026, 1, 2, 20, 45, tzinfo=UTC)
CLOCK = FixedClock(NOW)
BASE = {
    "convexity_book": {"account_equity": 100_000.0, "book_fraction": 0.10,
                       "per_name_fraction": 0.01, "max_open_positions": 15},
    "convexity_gate": {"iv_rv_max": 1.2, "otm_skew_max_volpts": 10.0, "rv_window_days": 252,
                       "tenor_min_days": 180, "tenor_max_days": 365, "target_moneyness": 0.25},
    "eligibility": {"live": {"min_option_open_interest": 50, "max_bid_ask_pct": 0.25}},
    "kill_rule": {"book_drawdown_halt": 0.20, "dry_months_halt": 9},
    "convexity_exits": {"profit_take_multiple": 10.0, "time_stop_dte": 21},
    "council": {"enabled": True, "conviction_floor": "MODERATE", "max_candidates": 50, "news_lookback_days": 90,
                "conviction_to_prob": {"LOW": 0.55, "MODERATE": 0.65, "HIGH": 0.75, "EXTREME": 0.85}},
    "themes_path": "themes.json",
}


def _cfg(on=True, **kw):
    c = copy.deepcopy(BASE)
    if on:
        c["convexity_book"]["backfill"] = {"enabled": True, **kw}
    return c


def _no_kill(monkeypatch):
    monkeypatch.delenv("KILL", raising=False)
    monkeypatch.setattr(risk, "KILL_FILE", Path("/nonexistent/KILL"))


# Strategist verdicts by symbol: (conviction, structural_vs_fad, at_inflection). at_inflection False ⇒ dropped.
VERDICTS = {"FCX": ("MODERATE", "structural", False), "SYM01": ("LOW", "structural", False),
            "SYM02": ("HIGH", "fad", False), "SYM03": ("HIGH", "structural", True)}


def _responder(role, system, user):
    c = _parse_candidate_header(user)
    conv, sf, inf = VERDICTS.get(c["symbol"], ("HIGH", "structural", True))
    if role == "proposer":
        return json.dumps({"theme": c["theme"], "symbol": c["symbol"], "direction": c["direction"],
                           "structural_vs_fad": sf, "inflection_thesis": "t", "confidence": conv, "cited": []})
    if role == "adversary":
        return json.dumps({"counter_case": "c", "weakest_point": "w", "is_fad": False,
                           "already_consensus": False, "confidence": "MODERATE", "cited": []})
    return json.dumps({"include": True, "theme": c["theme"], "symbol": c["symbol"], "direction": c["direction"],
                       "conviction": conv, "structural_vs_fad": sf, "under_narrated": True, "at_inflection": inf,
                       "weakest_point": "w", "summary": "s"})


def _cands(*syms):
    return [Theme(f"t-{s}", s, "bullish", "x") for s in syms]


def _l1(conn, cfg, syms, clock=CLOCK):
    themes = council_to_themes(conn, candidates=_cands(*syms), router=FakeRouter(responder=_responder), config=cfg,
                               clock=clock, demo=True, run_id=None)
    res = run_paper_cycle(config=cfg, conn=conn, clock=clock, provider=SyntheticChainProvider(as_of=clock.now().date()),
                          broker=PaperBroker(100_000.0), themes=themes, run_id=None)
    return themes, res


def _decisions(conn):
    return {r["symbol"]: r["decision"] for r in conn.execute("SELECT symbol, decision FROM convexity_eval ORDER BY id")}


def test_off_by_default_changes_nothing(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    assert backfill.settings(BASE) is None
    assert backfill.settings(_cfg(on=False) | {"convexity_book": {"backfill": {"enabled": False}}}) is None
    themes, res = _l1(convexity_db, _cfg(on=False), ["FCX", "SYM01"])
    assert themes == [] and res.opened == 0


def test_one_backfill_per_week_through_every_gate(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    cfg = _cfg()
    themes, res = _l1(convexity_db, cfg, ["FCX", "SYM01", "SYM02", "SYM03"])
    # SYM03 cleared the floor (ordinary path, first); FCX then SYM01 are ranked backfill; SYM02 is a fad (ineligible).
    assert [t.symbol for t in themes] == ["SYM03", "FCX", "SYM01"]
    assert [t.entry_origin for t in themes] == [None, "backfill", "backfill"]
    assert res.opened == 2
    d = _decisions(convexity_db)
    assert d["FCX"] == "open" and d["SYM01"] == "skip-backfill-quota"
    rat = json.loads(convexity_db.execute(
        "SELECT rationale FROM convexity_positions WHERE symbol='FCX'").fetchone()["rationale"])
    assert rat["origin"] == "backfill"
    prop = convexity_db.execute("SELECT status, rationale FROM council_proposals WHERE symbol='FCX'").fetchone()
    assert prop["status"] == "traded" and json.loads(prop["rationale"])["backfill"] == {"rank": 1}
    assert "origin" not in json.loads(convexity_db.execute(
        "SELECT rationale FROM convexity_positions WHERE symbol='SYM03'").fetchone()["rationale"])
    # Next session, same week: the quota is used, so no candidate is even sent.
    nxt = FixedClock(NOW + timedelta(days=1))
    themes2, res2 = _l1(convexity_db, cfg, ["SYM01"], clock=nxt)
    assert themes2 == [] and res2.opened == 0


def test_a_carry_walk_never_draws_on_the_quota(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    cfg = _cfg()
    _l1(convexity_db, cfg, ["FCX"])            # uses the week's backfill
    t = Theme("t-SYM05", "SYM05", "bullish", "x", entry_origin="backfill")
    res = run_paper_cycle(config=cfg, conn=convexity_db, clock=CLOCK, provider=SyntheticChainProvider(as_of=NOW.date()),
                          broker=PaperBroker(100_000.0), themes=[t], run_id=None,
                          walk={"SYM05": {"intent_id": 1, "step": 1, "fraction": 1 / 3}})
    assert res.opened == 1


def _pos(conn, sym, opened, *, status="open", premium=500.0, mark=None, origin=None, closed=None):
    pid = state.record_convexity_position(
        conn, run_id=None, opened_at=opened.isoformat(), theme="t", symbol=sym, direction="bullish",
        structure_kind="long_call", contract_symbol=f"{sym}C", expiry="2027-01-15", strike=10.0, dte=200,
        moneyness=0.25, contracts=1, entry_premium_per_contract=premium, total_premium=premium,
        rationale=({"origin": origin} if origin else {}), status=status)
    if mark is not None:
        state.mark_convexity_position(conn, pid, mark=mark, as_of=opened.isoformat())
    if closed is not None:
        conn.execute("UPDATE convexity_positions SET closed_at = ?, status = 'closed', realized_pnl = ? WHERE id = ?",
                     (closed.isoformat(), -premium, pid))
        conn.commit()
    return pid


def test_trigger_needs_an_idle_lookback(convexity_db):
    cfg = backfill.settings(_cfg())
    assert backfill.trigger(convexity_db, cfg, max_open=15, now=NOW)[0] is True
    # Six committed ten days ago, all closed since: the lookback still saw a busy book.
    for i in range(6):
        _pos(convexity_db, f"B{i}", NOW - timedelta(days=12), closed=NOW - timedelta(days=5))
    fires, why = backfill.trigger(convexity_db, cfg, max_open=15, now=NOW)
    assert fires is False and "peak 6" in why
    assert backfill.trigger(convexity_db, cfg, max_open=15, now=NOW + timedelta(days=40))[0] is True


def test_rank_is_deterministic():
    class P:
        def __init__(self, sym, conv, sf="structural", un=True, inf=False):
            self.symbol, self.conviction, self.structural_vs_fad = sym, conv, sf
            self.under_narrated, self.at_inflection = un, inf
    ps = [P("ZZZ", "HIGH", un=False), P("AAA", "LOW"), P("BBB", "MODERATE"), P("CCC", "MODERATE"),
          P("FAD", "EXTREME", sf="fad"), P("ABS", "NEUTRAL")]
    order = [p.symbol for p in backfill.rank(ps, cheap_reads={"CCC": 0.9, "BBB": 1.1})]
    assert order == ["CCC", "BBB", "AAA", "ZZZ"]   # 2 true: conviction then IV/RV; then 1 true


def test_stop_rule(convexity_db):
    cfg = backfill.settings(_cfg())
    old = NOW - timedelta(days=120)
    for i in range(8):
        _pos(convexity_db, f"BF{i}", old, origin="backfill", mark=0.5)      # $50 of $500: bled 90%
    # Fewer than 3 aged above-floor entries ⇒ the shadow book is the comparator; it is empty here.
    suspended, why = backfill.stop_status(convexity_db, cfg, now=NOW)
    assert suspended is False and "no comparator" in why
    for i in range(3):
        _pos(convexity_db, f"AF{i}", old, mark=4.0)                            # $400 of $500: bled 20%
    suspended, why = backfill.stop_status(convexity_db, cfg, now=NOW)
    assert suspended and "above-floor" in why
    picks, why2 = backfill.select(convexity_db, _cfg(), dropped=[], cheap_reads={}, now=NOW)
    assert picks == [] and why2.startswith("SUSPENDED")


def test_stop_rule_waits_for_enough_aged_entries(convexity_db):
    cfg = backfill.settings(_cfg())
    for i in range(7):
        _pos(convexity_db, f"BF{i}", NOW - timedelta(days=120), origin="backfill", mark=0.0)
    suspended, why = backfill.stop_status(convexity_db, cfg, now=NOW)
    assert suspended is False and "7 of 8" in why


# ── #418: the council summary line counts a backfill pick once, not as both dropped and to-gates ──────────────

def _council_line(caplog):
    return next(r.getMessage() for r in caplog.records if r.getMessage().startswith("Council: "))


def test_the_council_line_adds_up_on_a_backfill_night(convexity_db, monkeypatch, caplog):
    import re
    _no_kill(monkeypatch)
    with caplog.at_level("INFO", logger="council.wiring"):
        _l1(convexity_db, _cfg(), ["FCX", "SYM01", "SYM02", "SYM03"])
    line = _council_line(caplog)
    n, gates, dropped = map(int, re.match(r"Council: (\d+) proposal\(s\) → (\d+) to gates, (\d+) dropped", line).groups())
    assert (n, gates, dropped) == (4, 3, 1) and gates + dropped == n and "backfilled=2" in line


def test_the_council_line_is_unchanged_without_a_backfill(convexity_db, monkeypatch, caplog):
    _no_kill(monkeypatch)
    with caplog.at_level("INFO", logger="council.wiring"):
        _l1(convexity_db, _cfg(on=False), ["FCX", "SYM01"])
    assert "backfilled" not in _council_line(caplog) and ", 2 dropped (" in _council_line(caplog)
