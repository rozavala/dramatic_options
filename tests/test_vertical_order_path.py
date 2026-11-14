"""D3 step 2 — over-cap call verticals on the order path (PREREG_THEMATIC_CONVEXITY §5 amendment 2026-11-03b).

Inert when off; when on: the net debit is sized, one atomic multi-leg order, both legs journaled, spread marking,
spread expiry, multi-leg close, and the same rule in the shadow / 3A / 3B books."""

import copy
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import pytest

import broker as broker_mod
import fixed_basket
import monitor
import risk
import shadow_book
import state
from broker import AlpacaPaperBroker, PaperBroker
from clock import FixedClock
from convexity_data import SyntheticChainProvider
from convexity_gate import Contract
from paper_loop import run_paper_cycle
from structure import contract_eligible
from tests.test_broker import FakeTradingClient
from themes import Theme

NOW = datetime(2026, 11, 3, 20, 45, tzinfo=UTC)
EXP = NOW.date() + timedelta(days=270)
CFG = {
    "convexity_book": {"account_equity": 100_000.0, "book_fraction": 0.10, "per_name_fraction": 0.01,
                       "max_open_positions": 15},
    "convexity_gate": {"iv_rv_max": 1.2, "otm_skew_max_volpts": 10.0, "rv_window_days": 252,
                       "tenor_min_days": 180, "tenor_max_days": 365, "target_moneyness": 0.25,
                       "otm_side_guard": True},
    "eligibility": {"live": {"min_option_open_interest": 50, "max_bid_ask_pct": 0.25}},
    "kill_rule": {"book_drawdown_halt": 0.20, "dry_months_halt": 9},
    "convexity_exits": {"profit_take_multiple": 10.0, "time_stop_dte": 21, "min_close_bid": 0.05},
}


def _on(cfg=CFG):
    c = copy.deepcopy(cfg)
    c["convexity_gate"]["vertical_for_over_cap"] = {"enabled": True}
    return c


def _k(k, kind, bid, ask, iv, sym="BIG", exp=EXP):
    return Contract(symbol=f"{sym}{exp:%y%m%d}{kind}{int(k * 1000):08d}", expiry=exp, kind=kind, strike=k,
                    bid=bid, ask=ask, iv=iv, oi=500)


class OverCapProvider:
    """BIG @ 100: the 25%-OTM call costs $1,400 (over the $1,000 cap); the +75% call makes an $820 vertical."""

    def __init__(self, short_bid=5.6, short_ask=6.0):
        self._rv = SyntheticChainProvider(as_of=NOW.date(), profiles={"BIG": (100.0, 0.50, 0.50, 0.52)})
        self.quotes = {}
        self.chain_rows = [_k(100, "C", 19.8, 20.2, 0.50), _k(100, "P", 17.8, 18.2, 0.50),
                           _k(125, "C", 13.8, 14.2, 0.52), _k(150, "C", 9.0, 9.4, 0.55),
                           _k(175, "C", short_bid, short_ask, 0.60)]

    def underlying_price(self, symbol):
        return 100.0

    def closes(self, symbol, *, window):
        return self._rv.closes(symbol, window=window)

    def chain(self, symbol):
        return list(self.chain_rows)

    def option_mid(self, s):
        if s in self.quotes:
            return self.quotes[s]
        c = next((c for c in self.chain_rows if c.symbol == s), None)
        return None if c is None else 0.5 * (c.bid + c.ask)

    def option_bid(self, s):
        c = next((c for c in self.chain_rows if c.symbol == s), None)
        return None if c is None else c.bid


def _no_kill(monkeypatch):
    monkeypatch.delenv("KILL", raising=False)
    monkeypatch.setattr(risk, "KILL_FILE", Path("/nonexistent/KILL"))


def _cycle(conn, cfg, provider=None, broker=None):
    return run_paper_cycle(config=cfg, conn=conn, clock=FixedClock(NOW), provider=provider or OverCapProvider(),
                           broker=broker or PaperBroker(100_000.0),
                           themes=[Theme("t-big", "BIG", "bullish", "x")], run_id=None)


def _last_decision(conn):
    return conn.execute("SELECT decision, reasons FROM convexity_eval ORDER BY id DESC LIMIT 1").fetchone()


def test_off_by_default_the_over_cap_name_still_vetoes_on_sizing(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    res = _cycle(convexity_db, CFG)
    assert res.opened == 0 and _last_decision(convexity_db)["decision"] == "veto-sizing"


def test_on_the_over_cap_name_opens_as_a_vertical(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    res = _cycle(convexity_db, _on())
    assert res.opened == 1
    row = convexity_db.execute("SELECT * FROM convexity_positions").fetchone()
    assert row["contract_symbol"].endswith("C00125000") and row["short_contract_symbol"].endswith("C00175000")
    assert row["short_strike"] == 175 and row["structure_kind"] == "C"
    assert row["entry_premium_per_contract"] == pytest.approx(820.0) and row["contracts"] == 1     # net debit 14.0 − 5.8
    import json
    rat = json.loads(row["rationale"])
    assert rat["vertical"]["width"] == 50 and rat["vertical"]["naked_premium"] == 14.0
    # the short leg is a NEGATIVE journal quantity in its contract
    assert state.journal_contract_quantity(convexity_db, row["short_contract_symbol"]) == -1
    assert state.journal_contract_quantity(convexity_db, row["contract_symbol"]) == 1


def test_no_eligible_wing_is_a_recorded_veto(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    p = OverCapProvider()
    p.chain_rows = [c for c in p.chain_rows if c.strike not in (150, 175)]
    assert _cycle(convexity_db, _on(), provider=p).opened == 0
    d = _last_decision(convexity_db)
    assert d["decision"] == "veto-vertical" and "no_eligible_short_leg" in d["reasons"]


def test_a_broker_without_multi_leg_fails_closed(convexity_db, monkeypatch):
    _no_kill(monkeypatch)

    class SingleLegOnly:
        def account_equity(self):
            return 100_000.0

        def submit_paper(self, **kw):
            raise AssertionError("a vertical must never be legged")
    assert _cycle(convexity_db, _on(), broker=SingleLegOnly()).opened == 0
    assert _last_decision(convexity_db)["decision"] == "veto-fill"


def test_alpaca_sends_one_atomic_mleg_order(monkeypatch):
    fake = FakeTradingClient()
    monkeypatch.setattr(broker_mod, "TradingClient", lambda *a, **k: fake, raising=False)
    import alpaca.trading.client as tc
    monkeypatch.setattr(tc, "TradingClient", lambda *a, **k: fake)
    b = AlpacaPaperBroker("k", "s", dry_run=False, equity=100_000.0)
    f = b.submit_spread(long_symbol="BIG270731C00125000", short_symbol="BIG270731C00175000", qty=2,
                        action="open", limit_price=8.204, client_order_id="do-open-x")
    assert f.filled and f.pending and len(fake.submitted) == 1
    req = fake.submitted[0]
    assert str(req.order_class.value) == "mleg" and req.limit_price == 8.2 and req.qty == 2
    assert [(leg.symbol, leg.side.value, leg.position_intent.value) for leg in req.legs] == [
        ("BIG270731C00125000", "buy", "buy_to_open"), ("BIG270731C00175000", "sell", "sell_to_open")]
    b.submit_spread(long_symbol="BIG270731C00125000", short_symbol="BIG270731C00175000", qty=2,
                    action="close", limit_price=3.0)
    assert [(leg.side.value, leg.position_intent.value) for leg in fake.submitted[1].legs] == [
        ("sell", "sell_to_close"), ("buy", "buy_to_close")]
    # dry run sends nothing; a reserved root on EITHER leg is rejected in every mode
    d = AlpacaPaperBroker("k", "s", dry_run=True, equity=100_000.0)
    assert d.submit_spread(long_symbol="BIG270731C00125000", short_symbol="BIG270731C00175000", qty=1,
                           action="open", limit_price=8.2).filled and len(fake.submitted) == 2
    bad = d.submit_spread(long_symbol="BIG270731C00125000", short_symbol="SPY270731C00700000", qty=1,
                          action="open", limit_price=8.2)
    assert not bad.filled and "reserved" in bad.note


def test_monitor_marks_takes_profit_and_expires_the_spread(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    p = OverCapProvider()
    _cycle(convexity_db, _on(), provider=p)
    row = convexity_db.execute("SELECT * FROM convexity_positions").fetchone()
    # mark = long mid − short mid
    monitor.monitor_positions(conn=convexity_db, clock=FixedClock(NOW + timedelta(days=1)), quote_provider=p,
                              config=_on())
    assert convexity_db.execute("SELECT mark FROM convexity_positions").fetchone()["mark"] == pytest.approx(8.2)
    # the spread worth 10× its 8.20 debit = 82 > its 50 width: unreachable; at expiry it books the spread intrinsic
    # 16:30 ET on the expiry date (#480: 00:00 UTC on it is still the evening before in New York)
    monitor.monitor_positions(conn=convexity_db, clock=FixedClock(datetime.combine(EXP, time(21, 30), UTC)),
                              quote_provider=p, config=_on(), underlying_price_of=lambda s: 160.0)
    r = convexity_db.execute("SELECT * FROM convexity_positions").fetchone()
    assert r["status"] == "closed" and r["exit_reason"] == "expiry"
    assert r["realized_pnl"] == pytest.approx((35.0 * 100 - 820.0) * row["contracts"])     # (160−125) − 0 (short OTM)


def test_spread_intrinsic_is_capped_at_the_width():
    from verticals import position_intrinsic
    row = {"strike": 125.0, "short_strike": 175.0, "short_contract_symbol": "x"}
    assert position_intrinsic(row, 300.0) == 50.0 and position_intrinsic(row, 120.0) == 0.0


def _elig(c):
    return contract_eligible(c, max_spread_pct=0.25, min_contract_price=0.10, max_contract_price=100.0, min_oi=50)


def test_null_books_apply_the_same_rule(convexity_db):
    p = OverCapProvider()
    t = Theme("t-big", "BIG", "bullish", "x")
    kw = dict(conn=convexity_db, provider=p, eligibility=_elig, account_equity=100_000.0, as_of=NOW.date(),
              as_of_iso=NOW.isoformat(), run_id=None, cluster_map={}, cluster_fraction=0.0)
    off_gate, on_gate = CFG["convexity_gate"], _on()["convexity_gate"]
    assert shadow_book._eval_and_book(t, origin="o", gate=off_gate, book=CFG["convexity_book"], rv_window=252,
                                      **kw)[0] == "sizing"
    assert shadow_book._eval_and_book(t, origin="o", gate=on_gate, book=CFG["convexity_book"], rv_window=252,
                                      **kw) == ("booked", pytest.approx(820.0))
    assert fixed_basket._eval_and_book_nogate(t, origin="o", gate=on_gate, book_cfg=CFG["convexity_book"],
                                              **kw) == ("booked", pytest.approx(820.0))
    assert fixed_basket._eval_and_book_3b(sym="BIG", basket="b", direction="bullish", conn=convexity_db, provider=p,
                                          eligibility=_elig, account_equity=100_000.0, per_name_fraction=0.01,
                                          gate=on_gate, as_of=NOW.date(), as_of_iso=NOW.isoformat(),
                                          run_id=None) == "booked"
    for table in ("shadow_positions", "fixed_basket_positions"):
        shorts = {r[0] for r in convexity_db.execute(f"SELECT short_strike FROM {table}")}
        assert shorts == {175.0}
    # their monitors mark the spread
    shadow_book.mark_shadow_positions(conn=convexity_db, clock=FixedClock(NOW + timedelta(days=1)),
                                      quote_provider=p, config=_on())
    assert convexity_db.execute("SELECT mark FROM shadow_positions").fetchone()["mark"] == pytest.approx(8.2)
    assert date.fromisoformat(str(EXP))


def test_time_stop_closes_with_one_multi_leg_order(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    p = OverCapProvider()
    _cycle(convexity_db, _on(), provider=p)

    class Rec(PaperBroker):
        def __init__(self):
            super().__init__(100_000.0)
            self.spreads = []

        def submit_spread(self, **kw):
            self.spreads.append(kw)
            return super().submit_spread(**kw)

        def submit_paper(self, **kw):
            raise AssertionError("a vertical close must never be legged")
    b = Rec()
    late = FixedClock(datetime.combine(EXP - timedelta(days=10), datetime.min.time(), UTC))
    monitor.monitor_positions(conn=convexity_db, clock=late, quote_provider=p, config=_on(), broker=b, dry_run=False)
    assert len(b.spreads) == 1 and b.spreads[0]["action"] == "close"
    assert b.spreads[0]["limit_price"] == 7.8   # the NATURAL credit: long bid 13.8 − short ask 6.0
    assert b.spreads[0]["short_symbol"].endswith("C00175000")
    r = convexity_db.execute("SELECT status, exit_reason FROM convexity_positions").fetchone()
    assert r["status"] == "closed" and r["exit_reason"].startswith("time_stop")


def test_refusals_page_and_never_book_a_live_spread_closed(convexity_db, monkeypatch):
    _no_kill(monkeypatch)
    import notify
    pages = []
    monkeypatch.setattr(notify, "send", lambda title, msg, **kw: pages.append(title) or True)   # delivered (#479)
    p = OverCapProvider()

    class Refuses(PaperBroker):
        def submit_spread(self, **kw):
            return broker_mod.Fill(False, 0.0, 0, "403 options level")
    # a refused OPEN is a veto-fill and a page
    assert _cycle(convexity_db, _on(), provider=p, broker=Refuses(100_000.0)).opened == 0
    assert pages == ["VERTICAL ORDER REFUSED"]
    # a refused CLOSE leaves the spread OPEN and pages once per day, however many L2 ticks retry it
    _cycle(convexity_db, _on(), provider=p)
    late = datetime.combine(EXP - timedelta(days=10), datetime.min.time(), UTC)
    for minutes in (0, 30, 60):
        monitor.monitor_positions(conn=convexity_db, clock=FixedClock(late + timedelta(minutes=minutes)),
                                  quote_provider=p, config=_on(), broker=Refuses(100_000.0), dry_run=False)
    assert convexity_db.execute("SELECT status FROM convexity_positions WHERE status != 'cancelled'"
                                ).fetchone()["status"] == "open"
    assert pages.count("VERTICAL CLOSE REFUSED") == 1


def test_short_leg_filters_to_the_minimum_width_first():
    from structure import Structure
    from verticals import select_vertical
    lg = _k(125, "C", 13.8, 14.2, 0.52)
    chain = [lg, _k(145, "C", 9.4, 9.8, 0.55), _k(210, "C", 3.0, 3.4, 0.6)]
    v, why = select_vertical(chain, Structure("bullish", "C", lg, 270, 0.25, 14.0, 14.0), underlying_price=100.0,
                             eligibility=_elig, underlying_symbol="BIG")
    assert why == () and v.short.strike == 210      # +45% is under the +50% floor; +110% qualifies
