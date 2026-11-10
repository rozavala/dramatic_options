"""#466: the exit fire drill (scripts/drill_exit_paths.py), offline.

The drill places paper orders, so its guards are pinned here: no ``--send`` → nothing reaches the venue (two
independent layers); a live key, a live gate or a non-paper endpoint → refused; a production journal path → refused.
Each path then runs against a fake paper venue (the real ``AlpacaPaperBroker`` over a fake ``TradingClient``) and
drives the real ``monitor.monitor_positions`` on a scratch DB built by the real migrations.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sqlite3
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from alpaca.common.enums import BaseURL

import orchestrator
import risk
from clock import FixedClock
from convexity_data import StaticQuoteProvider
from convexity_gate import Contract

REPO = Path(__file__).resolve().parents[1]
_p = REPO / "scripts" / "drill_exit_paths.py"
_spec = importlib.util.spec_from_file_location("drill_exit_paths", _p)
drill = importlib.util.module_from_spec(_spec)
sys.modules["drill_exit_paths"] = drill          # dataclasses resolve their module through sys.modules
_spec.loader.exec_module(drill)

OTM = "F261113C00012000"        # expires Fri 2026-11-13; spot 11.50 → ~4% OTM
ITM = "F261113C00010000"
DAY1 = datetime(2026, 11, 10, 15, 0, tzinfo=UTC)            # Tue 10:00 ET
DAY2_PRE = datetime(2026, 11, 11, 13, 45, tzinfo=UTC)       # Wed 08:45 ET (pre-market)
DAY2 = datetime(2026, 11, 11, 15, 0, tzinfo=UTC)            # Wed 10:00 ET
EXPIRY_PM = datetime(2026, 11, 13, 21, 30, tzinfo=UTC)      # Fri 16:30 ET (after the close)
BASE_CONFIG = {**json.loads((REPO / "config.json").read_text()),
               "safety": {"paper": True, "live_trading_enabled": False, "dry_run": True}}


class _APIErr(Exception):
    def __init__(self, status_code, msg):
        super().__init__(msg)
        self.status_code = status_code


class FakeVenue:
    """A paper venue behind alpaca's TradingClient surface: a limit fills on read when marketable."""

    def __init__(self):
        self._base_url = BaseURL.TRADING_PAPER
        self.submitted, self.cancelled = [], []
        self.orders: dict[str, dict] = {}
        self.positions: dict[str, int] = {}
        self.quotes = {OTM: (0.20, 0.24), ITM: (1.45, 1.55)}
        self._n = 0

    def get_account(self):
        return SimpleNamespace(equity="100000", cash="50000", options_buying_power="50000")

    def submit_order(self, req):
        self.submitted.append(req)
        self._n += 1
        oid = f"ord-{self._n}"
        self.orders[oid] = {"req": req, "status": "new", "price": None, "qty": 0}
        return SimpleNamespace(id=oid, filled_avg_price=None, status="new")   # resting; fills on read

    def _try_fill(self, oid):
        o = self.orders[oid]
        req = o["req"]
        bid, ask = self.quotes[req.symbol]
        side = getattr(req.side, "value", req.side)
        lim = float(req.limit_price)
        if (side == "buy" and lim >= ask) or (side == "sell" and lim <= bid):
            o.update(status="filled", price=lim, qty=int(req.qty))
            sign = 1 if side == "buy" else -1
            self.positions[req.symbol] = self.positions.get(req.symbol, 0) + sign * int(req.qty)

    def get_order_by_id(self, oid):
        o = self.orders[oid]
        if o["status"] == "new":
            self._try_fill(oid)
        return SimpleNamespace(status=o["status"], filled_avg_price=o["price"], filled_qty=str(o["qty"]))

    def get_open_position(self, symbol):
        q = self.positions.get(symbol, 0)
        if not q:
            raise _APIErr(404, '{"code":40410000,"message":"position does not exist"}')
        return SimpleNamespace(qty=str(q))

    def cancel_order_by_id(self, oid):
        self.cancelled.append(oid)

    def end_session(self):
        for o in self.orders.values():
            if o["status"] == "new":
                o["status"] = "expired"


class FakeMarket:
    def __init__(self, venue, clock, spot=11.5):
        self.venue, self.clock, self.spot = venue, clock, spot

    def quotes(self):
        q = self.venue.quotes
        return StaticQuoteProvider({s: (b + a) / 2 for s, (b, a) in q.items()}, bids={s: b for s, (b, _) in q.items()})

    def underlying_price(self, symbol):
        return self.spot

    def chain(self, symbol):
        return [Contract(s, date(2026, 11, 13), "C", float(s[-8:]) / 1000, b, a)
                for s, (b, a) in self.venue.quotes.items()]


@pytest.fixture
def env(monkeypatch, tmp_path):
    for k in ("ALPACA_LIVE_KEY_ID", "ALPACA_LIVE_SECRET_KEY", "LIVE_TRADING_ENABLED", "PAPER", "KILL",
              "DRAMATIC_DB"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(risk, "KILL_FILE", Path("/nonexistent/KILL"))
    venue = FakeVenue()
    import alpaca.trading.client as tc
    monkeypatch.setattr(tc, "TradingClient", lambda *a, **k: venue)
    clock = FixedClock(DAY1, market_open=True)
    market = FakeMarket(venue, clock)
    out = []

    def run(*argv, config=None):
        rc = drill.main([*argv, "--poll-s", "0.2"], config=copy.deepcopy(config or BASE_CONFIG), market=market,
                        credentials=("k", "s"), sleep=lambda s: None)
        out.append(rc)
        return rc
    return SimpleNamespace(venue=venue, clock=clock, market=market, run=run, tmp=tmp_path)


def _rows(db):
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM convexity_positions ORDER BY id")]
    finally:
        conn.close()


def _at(e, when, market_open):
    e.clock._now = when
    e.clock.set_market_open(market_open)


# ── safety: nothing without --send ───────────────────────────────────────────────────────────────

def test_without_send_nothing_is_submitted_and_nothing_persists(env, capsys):
    db = env.tmp / "pt.db"
    assert env.run("--path", "profit-take", "--db", str(db), "--step", "open", "--contract", OTM) == 0
    assert env.venue.submitted == []
    assert _rows(db) == []                                   # the plan ran on a discarded in-memory copy
    assert "PLAN: nothing sent" in capsys.readouterr().out


def test_a_planned_tick_runs_the_real_monitor_on_a_copy_and_sends_nothing(env, capsys):
    db = env.tmp / "pt.db"
    assert env.run("--path", "profit-take", "--db", str(db), "--step", "open", "--contract", OTM, "--send") == 0
    n = len(env.venue.submitted)
    capsys.readouterr()
    assert env.run("--path", "profit-take", "--db", str(db), "--step", "tick") == 0
    assert len(env.venue.submitted) == n                     # nothing new reached the venue
    assert _rows(db)[0]["status"] == "open"                  # the real DB is untouched
    out = capsys.readouterr().out
    assert "PLAN (not sent): sell 1x " + OTM in out and "do-drill-pt-close-" in out


def test_the_send_guard_holds_even_over_a_transmitting_inner_broker(env):
    b = drill.make_drill_broker("k", "s", send=False, tag="pt", contract=OTM, budget=250.0)
    b._dry_run = False                                       # as if the inner DRY_RUN layer were gone
    f = b.submit_paper(contract_symbol=OTM, qty=1, side="buy", limit_price=0.24, client_order_id="do-open-x")
    assert env.venue.submitted == [], "a plan (no --send) reached the venue"
    assert f.filled and "PLAN (not sent)" in f.note


def test_without_send_the_inner_broker_is_dry_run_too(env):
    assert drill.make_drill_broker("k", "s", send=False, tag="pt", contract=OTM, budget=250.0)._dry_run is True
    assert drill.make_drill_broker("k", "s", send=True, tag="pt", contract=OTM, budget=250.0)._dry_run is False


# ── safety: live, endpoint, production DB ────────────────────────────────────────────────────────

@pytest.mark.parametrize("var,val", [("ALPACA_LIVE_KEY_ID", "AKLIVE"), ("ALPACA_LIVE_SECRET_KEY", "s"),
                                     ("LIVE_TRADING_ENABLED", "true"), ("PAPER", "false")])
def test_a_live_shaped_environment_refuses(env, monkeypatch, capsys, var, val):
    monkeypatch.setenv(var, val)
    db = env.tmp / "pt.db"
    rc = env.run("--path", "profit-take", "--db", str(db), "--step", "open", "--contract", OTM, "--send")
    assert env.venue.submitted == [], f"{var} was set and an order was still submitted"
    assert rc == 2 and "REFUSED" in capsys.readouterr().out
    assert not db.exists()


def test_a_live_config_refuses(env):
    cfg = {**BASE_CONFIG, "safety": {"paper": False, "live_trading_enabled": True}}
    assert env.run("--path", "profit-take", "--db", str(env.tmp / "pt.db"), "--step", "open", "--contract", OTM,
                   "--send", config=cfg) == 2
    assert env.venue.submitted == []


def test_a_non_paper_endpoint_refuses(env):
    env.venue._base_url = BaseURL.TRADING_LIVE
    assert env.run("--path", "profit-take", "--db", str(env.tmp / "pt.db"), "--step", "open", "--contract", OTM,
                   "--send") == 2
    assert env.venue.submitted == []


def test_the_production_journal_path_refuses(env, capsys):
    prod = REPO / "data" / "dramatic_options.db"
    existed = prod.exists()
    assert env.run("--path", "profit-take", "--db", str(prod), "--step", "open", "--contract", OTM, "--send") == 2
    assert "production journal" in capsys.readouterr().out
    assert env.venue.submitted == [] and prod.exists() == existed


def test_the_configured_and_env_journal_paths_refuse(env, monkeypatch):
    cfg = {**BASE_CONFIG, "database": {"path": str(env.tmp / "live.sqlite")}}
    assert env.run("--path", "time-stop", "--db", str(env.tmp / "live.sqlite"), "--step", "open", "--contract", OTM,
                   "--send", config=cfg) == 2
    monkeypatch.setenv("DRAMATIC_DB", str(env.tmp / "elsewhere.sqlite"))
    assert env.run("--path", "time-stop", "--db", str(env.tmp / "elsewhere.sqlite"), "--step", "open",
                   "--contract", OTM, "--send") == 2
    assert env.venue.submitted == []


def test_a_db_holding_loop_rows_refuses(env):
    db = env.tmp / "copy_of_live.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE runs (id INTEGER PRIMARY KEY, note TEXT)")
    conn.execute("INSERT INTO runs (note) VALUES ('paper cycle')")
    conn.commit()
    conn.close()
    assert env.run("--path", "time-stop", "--db", str(db), "--step", "open", "--contract", OTM, "--send") == 2
    assert env.venue.submitted == []


def test_one_scratch_db_per_path(env):
    db = env.tmp / "pt.db"
    assert env.run("--path", "profit-take", "--db", str(db), "--step", "open", "--contract", OTM, "--send") == 0
    assert env.run("--path", "time-stop", "--db", str(db), "--step", "tick", "--send") == 2


def test_the_kill_switch_refuses_a_trading_step(env, monkeypatch):
    monkeypatch.setenv("KILL", "1")
    assert env.run("--path", "time-stop", "--db", str(env.tmp / "ts.db"), "--step", "open", "--contract", OTM,
                   "--send") == 2
    assert env.venue.submitted == []


def test_the_drill_broker_trades_only_its_contract_one_lot_within_budget(env):
    b = drill.make_drill_broker("k", "s", send=True, tag="ts", contract=OTM, budget=20.0)
    assert not b.submit_paper(contract_symbol=ITM, qty=1, side="sell", limit_price=1.0).filled
    assert not b.submit_paper(contract_symbol=OTM, qty=2, side="sell", limit_price=0.2).filled
    assert not b.submit_paper(contract_symbol=OTM, qty=1, side="buy", limit_price=0.24).filled   # $24 > $20
    assert env.venue.submitted == []


def test_the_config_file_is_never_edited(env):
    before = (REPO / "config.json").read_text()
    cfg = copy.deepcopy(BASE_CONFIG)
    d = drill.drill_config(cfg, "unsellable")
    assert d["convexity_exits"]["min_close_bid"] == 1e6
    assert cfg == BASE_CONFIG and (REPO / "config.json").read_text() == before


# ── the paths, against the fake paper venue and the real monitor ─────────────────────────────────

def _open(env, path, contract=OTM):
    db = env.tmp / f"{path}.db"
    assert env.run("--path", path, "--db", str(db), "--step", "open", "--contract", contract, "--send") == 0
    row = _rows(db)[0]
    assert row["status"] == "open" and json.loads(row["rationale"])["drill"] is True
    assert row["theme"] == "drill-466" and row["entry_premium_per_contract"] == pytest.approx(
        env.venue.quotes[contract][1] * 100)
    return db


def test_profit_take_sells_and_reconciles_to_closed(env, capsys):
    db = _open(env, "profit-take")
    assert env.run("--path", "profit-take", "--db", str(db), "--step", "tick", "--send") == 0
    row = _rows(db)[0]
    assert row["status"] == "closed" and row["exit_reason"] == "profit_take_0.01x"
    assert row["realized_pnl"] == pytest.approx(0.20 * 100 - 24.0)        # the venue's fill at the bid
    assert env.venue.positions[OTM] == 0
    sells = [r for r in env.venue.submitted if getattr(r.side, "value", r.side) == "sell"]
    assert len(sells) == 1 and float(sells[0].limit_price) == 0.20
    out = capsys.readouterr().out
    assert "verdict: MATCH" in out and "CHECK FAIL" not in out


def test_time_stop_sells_and_closes(env):
    db = _open(env, "time-stop")
    assert env.run("--path", "time-stop", "--db", str(db), "--step", "tick", "--send") == 0
    row = _rows(db)[0]
    assert row["status"] == "closed" and row["exit_reason"] == "time_stop_21dte"
    assert env.venue.positions[OTM] == 0


def test_unsellable_books_in_db_and_the_venue_still_holds_it_then_flatten(env, capsys):
    db = _open(env, "unsellable")
    n = len(env.venue.submitted)
    capsys.readouterr()
    assert env.run("--path", "unsellable", "--db", str(db), "--step", "tick", "--send") == 0
    row = _rows(db)[0]
    assert row["status"] == "closed" and row["exit_reason"] == "time_stop_21dte_unsellable"
    assert len(env.venue.submitted) == n                                   # nothing sent
    assert env.venue.positions[OTM] == 1                                   # the venue still holds it (#444)
    out = capsys.readouterr().out
    assert "MISMATCH: venue 1 vs journal 0" in out and "#444" in out
    assert env.run("--path", "unsellable", "--db", str(db), "--step", "flatten", "--send") == 0
    assert env.venue.positions[OTM] == 0 and _rows(db)[0]["status"] == "closed"


def test_resting_close_rests_through_the_session_then_reopens_and_resells(env, capsys):
    db = _open(env, "resting-close")
    assert env.run("--path", "resting-close", "--db", str(db), "--step", "tick", "--send") == 0
    assert _rows(db)[0]["status"] == "closing"
    first = env.venue.submitted[-1]
    assert float(first.limit_price) == pytest.approx(0.48)                # ask × 2: rests
    env.venue.end_session()                                                # the DAY order expires at the close
    _at(env, DAY2, True)
    capsys.readouterr()
    assert env.run("--path", "resting-close", "--db", str(db), "--step", "tick", "--send") == 0
    row = _rows(db)[0]
    assert row["status"] == "closed" and row["exit_reason"] == "time_stop_21dte"
    second = env.venue.submitted[-1]
    assert float(second.limit_price) == 0.20 and second.client_order_id != first.client_order_id
    assert second.client_order_id.endswith("2026-11-11")
    assert "reopened to retry" in capsys.readouterr().out
    assert env.venue.positions[OTM] == 0


def test_pre_market_tick_defers_through_monitor_mode_then_the_open_tick_sells(env, monkeypatch, capsys):
    calls = []
    real = orchestrator.monitor_mode

    def spy(**kw):
        calls.append(kw)
        return real(**kw)
    monkeypatch.setattr(orchestrator, "monitor_mode", spy)
    db = _open(env, "pre-market")
    assert env.run("--path", "pre-market", "--db", str(db), "--step", "tick", "--send") == 2   # first tick: closed only
    n = len(env.venue.submitted)
    _at(env, DAY2_PRE, False)
    capsys.readouterr()
    assert env.run("--path", "pre-market", "--db", str(db), "--step", "tick", "--send") == 0
    assert calls[-1] == {"dry_run": False, "market_open": False, "demo": False}
    row = _rows(db)[0]
    assert row["status"] == "open" and row["exit_reason"] is None and row["mark"] == pytest.approx(0.22)
    assert len(env.venue.submitted) == n                                   # nothing sent pre-market
    out = capsys.readouterr().out
    assert "CHECK ok: the triggered time-stop was DEFERRED" in out and "CHECK FAIL" not in out
    _at(env, DAY2, True)
    assert env.run("--path", "pre-market", "--db", str(db), "--step", "tick", "--send") == 0
    assert calls[-1] == {"dry_run": False, "market_open": True, "demo": False}
    row = _rows(db)[0]
    assert row["status"] == "closed" and row["exit_reason"] == "time_stop_21dte"


def test_pre_market_fails_its_check_if_the_exit_were_booked(env, monkeypatch, capsys):
    # if monitor_mode regressed to the pre-#451 wiring (dry_run forced, no mark-only), the drill must say so
    monkeypatch.setattr(orchestrator, "monitor_mode", lambda **kw: (True, False))
    db = _open(env, "pre-market")
    _at(env, DAY2_PRE, False)
    assert env.run("--path", "pre-market", "--db", str(db), "--step", "tick", "--send") == 3
    assert "CHECK FAIL: the triggered time-stop was DEFERRED" in capsys.readouterr().out


def test_expiry_otm_holds_then_books_zero_and_observes_the_venue(env, capsys):
    db = _open(env, "expiry-otm")
    assert env.run("--path", "expiry-otm", "--db", str(db), "--step", "tick", "--send") == 0
    assert _rows(db)[0]["status"] == "open"
    _at(env, EXPIRY_PM, False)
    env.market.spot = 11.0
    capsys.readouterr()
    assert env.run("--path", "expiry-otm", "--db", str(db), "--step", "tick", "--send") == 0
    row = _rows(db)[0]
    assert row["status"] == "closed" and row["exit_reason"] == "expiry" and row["mark"] == 0.0
    assert "record when the venue settles" in capsys.readouterr().out       # venue still shows 1 that evening
    env.venue.positions[OTM] = 0                                           # next day: the venue expired it
    assert env.run("--path", "expiry-otm", "--db", str(db), "--step", "observe") == 0
    assert "verdict: MATCH" in capsys.readouterr().out
    conn = sqlite3.connect(str(db))
    steps = [r[0] for r in conn.execute("SELECT step FROM drill_log ORDER BY id")]
    conn.close()
    assert steps == ["open", "tick", "tick", "observe"]                    # the day-by-day record


def test_expiry_itm_books_intrinsic_and_reports_exercised_shares(env, capsys):
    db = _open(env, "expiry-itm", contract=ITM)
    _at(env, EXPIRY_PM, False)
    assert env.run("--path", "expiry-itm", "--db", str(db), "--step", "tick", "--send") == 0
    row = _rows(db)[0]
    assert row["status"] == "closed" and row["exit_reason"] == "expiry" and row["mark"] == pytest.approx(1.5)
    env.venue.positions[ITM] = 0
    env.venue.positions["F"] = 100                                          # auto-exercised into shares
    capsys.readouterr()
    assert env.run("--path", "expiry-itm", "--db", str(db), "--step", "observe") == 0
    out = capsys.readouterr().out
    assert "+100 shares" in out and "auto-exercise" in out


def test_every_order_id_carries_the_drill_prefix(env):
    for path in ("profit-take", "time-stop", "resting-close"):
        db = _open(env, path)
        env.run("--path", path, "--db", str(db), "--step", "tick", "--send")
    ids = [r.client_order_id for r in env.venue.submitted]
    assert len(ids) >= 6 and all(i.startswith("do-drill-") for i in ids), ids
    assert {i.split("-")[2] for i in ids} == {"pt", "ts", "rc"}


def test_drill_order_id_rewrites_the_monitors_ids():
    assert drill.drill_order_id("do-close-F261113C00012000-2026-11-10", tag="ts", fallback="x") == \
        "do-drill-ts-close-F261113C00012000-2026-11-10"
    assert drill.drill_order_id("do-drill-ts-open-x", tag="ts", fallback="x") == "do-drill-ts-open-x"


def test_pick_chooses_a_short_dated_liquid_call(env):
    today = date(2026, 11, 10)
    chain = [Contract("F261113C00012000", date(2026, 11, 13), "C", 12.0, 0.20, 0.24),
             Contract("F261113C00012500", date(2026, 11, 13), "C", 12.5, 0.01, 0.05),      # no real bid
             Contract("F261218C00012000", date(2026, 12, 18), "C", 12.0, 0.40, 0.44),      # too far out
             Contract("F261113C00010000", date(2026, 11, 13), "C", 10.0, 1.45, 1.55)]
    assert drill.pick_short_dated(chain, underlying_price=11.5, today=today, max_dte=7,
                                  budget=250.0).symbol == "F261113C00012000"
    assert drill.pick_short_dated(chain, underlying_price=11.5, today=today, max_dte=7, budget=250.0,
                                  moneyness="itm").symbol == "F261113C00010000"
    assert drill.pick_short_dated(chain[1:3], underlying_price=11.5, today=today, max_dte=7, budget=250.0) is None


def test_pick_through_the_cli(env, capsys):
    db = env.tmp / "ts.db"
    assert env.run("--path", "time-stop", "--db", str(db), "--step", "open", "--pick", "--symbol", "F",
                   "--send") == 0
    assert _rows(db)[0]["contract_symbol"] == OTM
    assert "picked " + OTM in capsys.readouterr().out


def test_out_file_and_record_step(env, capsys):
    db, rec = env.tmp / "ts.db", env.tmp / "record.md"
    assert env.run("--path", "time-stop", "--db", str(db), "--step", "open", "--contract", OTM, "--send",
                   "--out", str(rec)) == 0
    assert env.run("--path", "time-stop", "--db", str(db), "--step", "tick", "--send", "--out", str(rec)) == 0
    text = rec.read_text()
    assert text.count("### #466 drill · time-stop") == 2
    assert "| | venue (paper; read per contract / per order id) | journal (scratch DB) |" in text
    capsys.readouterr()
    assert env.run("--path", "time-stop", "--db", str(db), "--step", "record") == 0
    assert capsys.readouterr().out.count("### #466 drill · time-stop") == 2


def test_open_refuses_a_contract_beyond_the_short_dated_window(env):
    assert env.run("--path", "time-stop", "--db", str(env.tmp / "ts.db"), "--step", "open", "--contract",
                   "F261218C00012000", "--limit", "0.44", "--send") == 2
    assert env.venue.submitted == []


def test_open_refuses_when_the_venue_already_holds_the_contract(env):
    env.venue.positions[OTM] = 3                      # another holder of the same OCC symbol
    assert env.run("--path", "time-stop", "--db", str(env.tmp / "ts.db"), "--step", "open", "--contract", OTM,
                   "--send") == 2
    assert env.venue.submitted == []


def test_days_since_open_fixture_sanity():
    assert (date(2026, 11, 13) - DAY1.date()) == timedelta(days=3)
