"""#466: the exit fire drill (scripts/drill_exit_paths.py), offline.

The drill places paper orders, so its guards are pinned here: no ``--send`` → no order and no cancel reaches the
venue (two independent layers for orders); a live key, a live gate or a non-paper endpoint → refused; a production
journal path → refused. Each path then runs against a fake paper venue (the real ``AlpacaPaperBroker`` over a fake
``TradingClient``) and drives the real ``monitor.monitor_positions`` on a scratch DB built by the real migrations.

Every test runs with the drill's ``REPO`` and the CWD pointed inside ``tmp_path``, so a broken DB guard can only ever
write to a temp file, never to a real journal.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from alpaca.common.enums import BaseURL

import config_loader
import notify
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

# The underlying is a high-volatility name (~100% IV, MARA-like) on purpose: at 3 DTE a call 5.3% OTM is worth
# about $0.18 at that vol (S·σ√t·[φ(d) − d·(1 − Φ(d))], σ√t ≈ 0.09, d ≈ 0.58), so 0.20/0.24 is a realistic quote.
# A low-vol name (F, ~30% IV) would quote that strike near $0.01, under the $0.05 bid floor.
OTM = "MARA261113C00012000"        # expires Fri 2026-11-13; spot 11.40 → ~5.3% OTM
ITM = "MARA261113C00010000"        # ~12% ITM
NEXT_DAY = "MARA261111C00012000"   # expires Wed 2026-11-11: 1 DTE on DAY1
TEN_DAY = "MARA261120C00012000"    # 10 DTE on DAY1
MONDAY = "MARA261116C00012000"     # expires Mon 2026-11-16: the session after a Friday open
TUESDAY = "MARA261117C00012000"    # expires Tue 2026-11-17
FRI = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)             # Fri 10:00 ET
DAY1 = datetime(2026, 11, 10, 15, 0, tzinfo=UTC)            # Tue 10:00 ET
DAY2_PRE = datetime(2026, 11, 11, 13, 45, tzinfo=UTC)       # Wed 08:45 ET (pre-market)
DAY2 = datetime(2026, 11, 11, 15, 0, tzinfo=UTC)            # Wed 10:00 ET
EXPIRY_AM = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)       # Fri 10:00 ET (expiry day, in session)
EXPIRY_PM = datetime(2026, 11, 13, 21, 30, tzinfo=UTC)      # Fri 16:30 ET (after the close)
BASE_CONFIG = {**json.loads((REPO / "config.json").read_text()),
               "safety": {"paper": True, "live_trading_enabled": False, "dry_run": True}}
LIVE_VARS = ("ALPACA_LIVE_KEY_ID", "ALPACA_LIVE_SECRET_KEY", "LIVE_TRADING_ENABLED", "PAPER", "KILL", "DRAMATIC_DB",
             "DRAMATIC_SKIP_DOTENV")


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
        self.quotes = {OTM: (0.20, 0.24), ITM: (1.45, 1.55), NEXT_DAY: (0.20, 0.24), TEN_DAY: (0.30, 0.34),
                       MONDAY: (0.20, 0.24), TUESDAY: (0.22, 0.26)}
        self.unreadable: set[str] = set()      # symbols whose position read fails (a 500, not a 404)
        self.hold_sells = False
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
        if side == "sell" and self.hold_sells:
            return
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
        if symbol in self.unreadable:
            raise _APIErr(500, "internal error")
        q = self.positions.get(symbol, 0)
        if not q:
            raise _APIErr(404, '{"code":40410000,"message":"position does not exist"}')
        return SimpleNamespace(qty=str(q))

    def cancel_order_by_id(self, oid):
        self.cancelled.append(oid)
        if oid in self.orders and self.orders[oid]["status"] == "new":
            self.orders[oid]["status"] = "canceled"

    def end_session(self):
        for o in self.orders.values():
            if o["status"] == "new":
                o["status"] = "expired"


class FakeMarket:
    def __init__(self, venue, clock, spot=11.4):
        self.venue, self.clock, self.spot = venue, clock, spot
        self.blank = False          # no usable quote at all (a dead feed)

    def quotes(self):
        if self.blank:
            return StaticQuoteProvider({}, bids={})
        q = self.venue.quotes
        return StaticQuoteProvider({s: (b + a) / 2 for s, (b, a) in q.items()}, bids={s: b for s, (b, _) in q.items()})

    def underlying_price(self, symbol):
        return self.spot

    def chain(self, symbol):
        from options_tradability import parse_osi
        return [Contract(s, parse_osi(s)["expiry"], "C", parse_osi(s)["strike"], b, a)
                for s, (b, a) in self.venue.quotes.items()]


@pytest.fixture
def env(monkeypatch, tmp_path):
    for k in LIVE_VARS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(risk, "KILL_FILE", Path("/nonexistent/KILL"))
    fake_repo, cwd = tmp_path / "repo", tmp_path / "cwd"
    (fake_repo / "data").mkdir(parents=True)
    cwd.mkdir()
    monkeypatch.setattr(drill, "REPO", fake_repo)          # the "production" journal lives inside tmp_path
    monkeypatch.chdir(cwd)
    venue = FakeVenue()
    import alpaca.trading.client as tc
    monkeypatch.setattr(tc, "TradingClient", lambda *a, **k: venue)
    clock = FixedClock(DAY1, market_open=True)
    market = FakeMarket(venue, clock)
    record = tmp_path / "record.md"

    def run(*argv, config=None, sleep=lambda s: None, out=True):
        extra = ["--poll-s", "0.2"] + (["--out", str(record)] if out else [])
        return drill.main([*argv, *extra], config=copy.deepcopy(config or BASE_CONFIG), market=market,
                          credentials=("k", "s"), sleep=sleep)
    return SimpleNamespace(venue=venue, clock=clock, market=market, run=run, tmp=tmp_path, repo=fake_repo,
                           record=record)


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


def _open(env, path, contract=OTM):
    db = env.tmp / f"{path}.db"
    assert env.run("--path", path, "--db", str(db), "--step", "open", "--contract", contract, "--send") == 0
    row = _rows(db)[0]
    assert row["status"] == "open" and json.loads(row["rationale"])["drill"] is True
    assert row["theme"] == "drill-466" and row["entry_premium_per_contract"] == pytest.approx(
        env.venue.quotes[contract][1] * 100)
    return db


def _sells(env):
    return [r for r in env.venue.submitted if getattr(r.side, "value", r.side) == "sell"]


# ── safety: nothing without --send ───────────────────────────────────────────────────────────────

def test_without_send_nothing_is_submitted_and_nothing_persists(env, capsys):
    db = env.tmp / "pt.db"
    assert env.run("--path", "profit-take", "--db", str(db), "--step", "open", "--contract", OTM) == 0
    assert env.venue.submitted == []
    assert _rows(db) == []                                   # the plan ran on a discarded in-memory copy
    assert "PLAN: nothing sent" in capsys.readouterr().out


def test_a_plan_without_db_uses_memory_and_leaves_no_temp_file(env, capsys):
    before = {p for p in os.listdir(tempfile.gettempdir()) if p.startswith("drill466")}
    assert env.run("--path", "profit-take", "--step", "open", "--contract", OTM) == 0
    after = {p for p in os.listdir(tempfile.gettempdir()) if p.startswith("drill466")}
    assert after == before and env.venue.submitted == []
    assert ":memory:" in capsys.readouterr().out


def test_send_without_db_or_out_refuses(env, capsys):
    assert env.run("--path", "profit-take", "--step", "open", "--contract", OTM, "--send") == 2
    assert "--send needs a persistent scratch --db" in capsys.readouterr().out
    assert env.run("--path", "profit-take", "--db", str(env.tmp / "pt.db"), "--step", "open", "--contract", OTM,
                   "--send", out=False) == 2
    assert "--send needs --out" in capsys.readouterr().out
    assert env.venue.submitted == []


def test_a_planned_tick_runs_the_real_monitor_on_a_copy_and_sends_nothing(env, capsys):
    db = _open(env, "profit-take")
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


# ── safety: cancels and multi-leg orders (S3) ────────────────────────────────────────────────────

def test_a_plan_never_sends_a_cancel_even_on_expiry_day_while_closing(env, capsys):
    db = _open(env, "resting-close")
    assert env.run("--path", "resting-close", "--db", str(db), "--step", "tick", "--send") == 0
    assert _rows(db)[0]["status"] == "closing"
    _at(env, EXPIRY_AM, True)                         # the resting close is still working on expiry day
    capsys.readouterr()
    env.run("--path", "resting-close", "--db", str(db), "--step", "tick")   # PLAN: reaches carry's cancel-and-settle
    assert env.venue.cancelled == [], "a plan tick sent a real cancel"
    assert "PLAN (not sent): cancel" in capsys.readouterr().out


def test_a_sent_cancel_is_limited_to_this_dbs_drill_orders(env):
    db = _open(env, "resting-close")
    assert env.run("--path", "resting-close", "--db", str(db), "--step", "tick", "--send") == 0
    close_oid = _rows(db)[0]["close_order_id"]
    _at(env, EXPIRY_AM, True)
    env.run("--path", "resting-close", "--db", str(db), "--step", "tick", "--send")
    assert env.venue.cancelled == [close_oid]          # the monitor's expiry-while-closing cancel of its own close
    b = drill.make_drill_broker("k", "s", send=True, tag="rc", contract=OTM, budget=250.0,
                                known_order_ids={close_oid})
    b.cancel_order("another-projects-order")
    assert env.venue.cancelled == [close_oid], "a cancel of an id this scratch DB never recorded was sent"


def test_a_multi_leg_order_is_always_refused(env):
    for send in (False, True):
        b = drill.make_drill_broker("k", "s", send=send, tag="pt", contract=OTM, budget=250.0)
        f = b.submit_spread(long_symbol=OTM, short_symbol=ITM, qty=1, action="close", limit_price=0.1,
                            client_order_id="do-close-x")
        assert not f.filled and "multi-leg" in f.note
    assert env.venue.submitted == [], "submit_spread bypassed the drill broker's limits"


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
    assert "REFUSED" in env.record.read_text()            # the refusal lands in the record too


def test_a_live_key_only_in_the_env_file_load_config_reads_refuses(env, monkeypatch):
    dotenv = env.tmp / "dot.env"
    dotenv.write_text("ALPACA_LIVE_KEY_ID=AKLIVE\n")
    monkeypatch.setattr(config_loader, "ENV_PATH", dotenv)
    config_loader.load_config.cache_clear()
    try:
        rc = drill.main(["--path", "profit-take", "--db", str(env.tmp / "pt.db"), "--step", "open", "--contract", OTM,
                         "--send", "--out", str(env.record), "--poll-s", "0.2"],
                        market=env.market, credentials=("k", "s"), sleep=lambda s: None)
    finally:
        os.environ.pop("ALPACA_LIVE_KEY_ID", None)
        config_loader.load_config.cache_clear()
    assert env.venue.submitted == [], "a live key loaded from .env by load_config did not refuse"
    assert rc == 2


@pytest.mark.parametrize("safety", [{"paper": False, "live_trading_enabled": False},
                                    {"paper": True, "live_trading_enabled": True}])
def test_each_live_config_flag_refuses_alone(env, safety):
    assert env.run("--path", "profit-take", "--db", str(env.tmp / "pt.db"), "--step", "open", "--contract", OTM,
                   "--send", config={**BASE_CONFIG, "safety": safety}) == 2
    assert env.venue.submitted == []


def test_a_non_paper_endpoint_refuses(env):
    env.venue._base_url = BaseURL.TRADING_LIVE
    assert env.run("--path", "profit-take", "--db", str(env.tmp / "pt.db"), "--step", "open", "--contract", OTM,
                   "--send") == 2
    assert env.venue.submitted == []


def test_the_endpoint_check_requires_the_paper_class(env):
    b = drill.make_drill_broker("k", "s", send=False, tag="pt", contract=OTM, budget=250.0)
    b._paper = False                                       # a paper URL on a non-paper broker is still refused
    assert drill.endpoint_refusal(b) is not None
    assert drill.endpoint_refusal(SimpleNamespace(_paper=True, _trading=env.venue)) is not None


def test_the_production_journal_path_refuses(env, capsys):
    prod = env.repo / "data" / "dramatic_options.db"
    assert env.run("--path", "profit-take", "--db", str(prod), "--step", "open", "--contract", OTM, "--send") == 2
    assert "is the production journal" in capsys.readouterr().out
    assert env.venue.submitted == [] and not prod.exists()


def test_the_configured_and_env_journal_paths_refuse(env, monkeypatch):
    cfg = {**BASE_CONFIG, "database": {"path": str(env.tmp / "live.sqlite")}}
    assert env.run("--path", "time-stop", "--db", str(env.tmp / "live.sqlite"), "--step", "open", "--contract", OTM,
                   "--send", config=cfg) == 2
    monkeypatch.setenv("DRAMATIC_DB", str(env.tmp / "elsewhere.sqlite"))
    assert env.run("--path", "time-stop", "--db", str(env.tmp / "elsewhere.sqlite"), "--step", "open",
                   "--contract", OTM, "--send") == 2
    assert env.venue.submitted == []


def test_a_hard_link_to_the_production_journal_refuses(env):
    prod = env.tmp / "live.sqlite"
    conn = sqlite3.connect(str(prod))
    conn.execute("CREATE TABLE drill_meta (key TEXT PRIMARY KEY, value TEXT)")   # looks like a drill DB otherwise
    conn.commit()
    conn.close()
    link = env.tmp / "innocent.sqlite"
    os.link(prod, link)
    cfg = {**BASE_CONFIG, "database": {"path": str(prod)}}
    assert env.run("--path", "time-stop", "--db", str(link), "--step", "open", "--contract", OTM, "--send",
                   config=cfg) == 2
    assert env.venue.submitted == []


def test_the_production_file_name_refuses_anywhere(env):
    other = env.tmp / "elsewhere" / "dramatic_options.db"
    assert env.run("--path", "time-stop", "--db", str(other), "--step", "open", "--contract", OTM, "--send") == 2
    assert env.venue.submitted == [] and not other.exists()


def test_a_db_holding_loop_rows_refuses(env):
    db = env.tmp / "copy_of_live.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE drill_meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("CREATE TABLE runs (id INTEGER PRIMARY KEY, note TEXT)")
    conn.execute("INSERT INTO runs (note) VALUES ('paper cycle')")
    conn.commit()
    conn.close()
    assert env.run("--path", "time-stop", "--db", str(db), "--step", "open", "--contract", OTM, "--send") == 2
    assert env.venue.submitted == []


def test_a_db_holding_a_non_drill_position_refuses(env):
    db = env.tmp / "mixed.sqlite"
    conn = drill.open_scratch(db)
    conn.execute("INSERT INTO convexity_positions (opened_at, theme, symbol, direction, structure_kind, "
                 "contract_symbol, expiry, strike, dte, moneyness, contracts, entry_premium_per_contract, "
                 "total_premium, status, rationale) VALUES ('2026-11-01','copper','FCX','bullish','C',"
                 "'FCX270319C00080000','2027-03-19',80,300,0.25,1,100,100,'open','{\"thesis\": \"real\"}')")
    conn.commit()
    conn.close()
    assert env.run("--path", "time-stop", "--db", str(db), "--step", "open", "--contract", OTM, "--send") == 2
    assert env.venue.submitted == []


def test_a_foreign_non_empty_file_is_refused_not_migrated(env):
    db = env.tmp / "notes.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE notes (t TEXT)")
    conn.commit()
    conn.close()
    assert env.run("--path", "time-stop", "--db", str(db), "--step", "open", "--contract", OTM, "--send") == 2
    conn = sqlite3.connect(str(db))
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert tables == {"notes"}                                  # untouched: no migration ran on it


def test_one_scratch_db_per_path(env):
    db = _open(env, "profit-take")
    assert env.run("--path", "time-stop", "--db", str(db), "--step", "tick", "--send") == 2


def test_the_kill_switch_refuses_a_trading_step(env, monkeypatch):
    monkeypatch.setenv("KILL", "1")
    assert env.run("--path", "time-stop", "--db", str(env.tmp / "ts.db"), "--step", "open", "--contract", OTM,
                   "--send") == 2
    assert env.venue.submitted == []


def test_open_refuses_with_the_market_closed(env):
    _at(env, DAY2_PRE, False)
    assert env.run("--path", "time-stop", "--db", str(env.tmp / "ts.db"), "--step", "open", "--contract", OTM,
                   "--send") == 2
    assert env.venue.submitted == []


def test_open_refuses_a_contract_beyond_the_short_dated_window(env):
    # profit-take has no time-stop check, so only the short-dated window refuses a 10-DTE contract
    assert env.run("--path", "profit-take", "--db", str(env.tmp / "pt.db"), "--step", "open", "--contract",
                   TEN_DAY, "--send") == 2
    assert env.venue.submitted == []


@pytest.mark.parametrize("path", ["pre-market", "resting-close"])
def test_the_two_day_paths_refuse_a_contract_expiring_tomorrow(env, path):
    assert env.run("--path", path, "--db", str(env.tmp / f"{path}.db"), "--step", "open", "--contract", NEXT_DAY,
                   "--send") == 2
    assert env.venue.submitted == []
    assert env.run("--path", "time-stop", "--db", str(env.tmp / "ts.db"), "--step", "open", "--contract", NEXT_DAY,
                   "--send") == 0                                      # a one-day path may use it


def test_open_refuses_when_the_venue_already_holds_the_contract(env):
    env.venue.positions[OTM] = 3                      # another holder of the same OCC symbol
    assert env.run("--path", "time-stop", "--db", str(env.tmp / "ts.db"), "--step", "open", "--contract", OTM,
                   "--send") == 2
    assert env.venue.submitted == []


def test_the_drill_broker_trades_only_its_contract_one_lot_within_budget(env):
    b = drill.make_drill_broker("k", "s", send=True, tag="ts", contract=OTM, budget=20.0)
    assert not b.submit_paper(contract_symbol=ITM, qty=1, side="sell", limit_price=1.0).filled
    assert not b.submit_paper(contract_symbol=OTM, qty=2, side="sell", limit_price=0.2).filled
    assert not b.submit_paper(contract_symbol=OTM, qty=1, side="buy", limit_price=0.24).filled   # $24 > $20
    assert env.venue.submitted == []


def test_pages_are_suppressed_during_the_drill(env, monkeypatch, capsys):
    pages = []
    monkeypatch.setattr(notify, "send", lambda *a, **k: pages.append(a) or True)
    _open(env, "time-stop")                            # the reconciled fill pages "REAL-BOOK FILL" in the loop
    assert pages == [], "the drill sent a real page"
    assert "PAGE suppressed in the drill: REAL-BOOK FILL" in capsys.readouterr().out


def test_a_resting_entry_is_never_cancelled_or_carried(env):
    # the real config has cancel_unfilled and carry_unfilled on; the drill's copy turns both off
    db = env.tmp / "ts.db"
    assert env.run("--path", "time-stop", "--db", str(db), "--step", "open", "--contract", OTM, "--limit", "0.21",
                   "--send") == 3                                       # below the ask: rests
    assert env.run("--path", "time-stop", "--db", str(db), "--step", "open", "--send") == 0   # reconcile only
    assert env.venue.cancelled == [], "reconcile cancelled the drill's resting entry"
    assert _rows(db)[0]["status"] == "pending"


def test_the_config_file_is_never_edited(env):
    before = (REPO / "config.json").read_text()
    cfg = copy.deepcopy(BASE_CONFIG)
    d = drill.drill_config(cfg, "unsellable")
    assert d["convexity_exits"]["min_close_bid"] == 1e6
    assert d["execution"]["cancel_unfilled"] is False and d["execution"]["carry_unfilled"] is False
    assert cfg == BASE_CONFIG and (REPO / "config.json").read_text() == before


# ── the paths, against the fake paper venue and the real monitor ─────────────────────────────────

def test_profit_take_sells_and_reconciles_to_closed(env, capsys):
    db = _open(env, "profit-take")
    assert env.run("--path", "profit-take", "--db", str(db), "--step", "tick", "--send") == 0
    row = _rows(db)[0]
    assert row["status"] == "closed" and row["exit_reason"] == "profit_take_0.01x"
    assert row["realized_pnl"] == pytest.approx(0.20 * 100 - 24.0)        # the venue's fill at the bid
    assert env.venue.positions[OTM] == 0
    assert len(_sells(env)) == 1 and float(_sells(env)[0].limit_price) == 0.20
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


def test_flatten_refuses_a_row_a_real_sell_closed(env):
    db = _open(env, "time-stop")
    assert env.run("--path", "time-stop", "--db", str(db), "--step", "tick", "--send") == 0
    env.venue.positions[OTM] = 1                     # something else holds the contract now
    n = len(env.venue.submitted)
    assert env.run("--path", "time-stop", "--db", str(db), "--step", "flatten", "--send") == 2
    assert len(env.venue.submitted) == n


def test_resting_close_rests_through_the_session_then_reopens_and_resells(env, capsys):
    db = _open(env, "resting-close")
    assert env.run("--path", "resting-close", "--db", str(db), "--step", "tick", "--send") == 0
    assert _rows(db)[0]["status"] == "closing"
    first = env.venue.submitted[-1]
    assert float(first.limit_price) == pytest.approx(0.48)                # ask × 2: rests
    out = capsys.readouterr().out
    assert "cannot exercise #449's partial-fill branch" in out             # the block says what it rehearses
    env.venue.end_session()                                                # the DAY order expires at the close
    _at(env, DAY2, True)
    assert env.run("--path", "resting-close", "--db", str(db), "--step", "observe") == 0
    assert "close order is expired while the journal still says closing" in capsys.readouterr().out
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


def test_pre_market_without_a_quote_fails_its_check_and_the_open_tick_still_sells(env, capsys):
    db = _open(env, "pre-market")
    _at(env, DAY2_PRE, False)
    env.market.blank = True                              # the closed-market tick gets no usable quote
    capsys.readouterr()
    assert env.run("--path", "pre-market", "--db", str(db), "--step", "tick", "--send") == 3
    assert "CHECK FAIL: a usable quote marked the position" in capsys.readouterr().out
    env.market.blank = False
    _at(env, DAY2, True)
    assert env.run("--path", "pre-market", "--db", str(db), "--step", "tick", "--send") == 0   # not a dead end
    assert _rows(db)[0]["status"] == "closed"


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
    text = env.record.read_text()                                          # the day-by-day record, one channel
    assert [ln.split(" · ")[2] for ln in text.splitlines() if ln.startswith("### #466 drill")] == \
        ["open", "tick", "tick", "observe"]


def test_expiry_itm_books_intrinsic_and_reports_exercised_shares(env, capsys):
    db = _open(env, "expiry-itm", contract=ITM)
    _at(env, EXPIRY_PM, False)
    assert env.run("--path", "expiry-itm", "--db", str(db), "--step", "tick", "--send") == 0
    row = _rows(db)[0]
    assert row["status"] == "closed" and row["exit_reason"] == "expiry" and row["mark"] == pytest.approx(1.4)
    env.venue.positions[ITM] = 0
    env.venue.positions["MARA"] = 100                                          # auto-exercised into shares
    capsys.readouterr()
    assert env.run("--path", "expiry-itm", "--db", str(db), "--step", "observe") == 0
    out = capsys.readouterr().out
    assert "+100 shares" in out and "auto-exercise" in out and "verdict: MISMATCH" in out


def test_a_share_change_is_a_mismatch_on_every_path(env, capsys):
    db = _open(env, "time-stop")
    assert env.run("--path", "time-stop", "--db", str(db), "--step", "tick", "--send") == 0
    env.venue.positions["MARA"] = 100                                          # shares appeared after the open
    capsys.readouterr()
    assert env.run("--path", "time-stop", "--db", str(db), "--step", "observe") == 0
    out = capsys.readouterr().out
    assert "verdict: MISMATCH" in out and "+100 shares" in out


def test_ctrl_c_in_the_poll_still_records_the_order_and_the_block(env):
    db = _open(env, "time-stop")
    env.venue.hold_sells = True                                            # the close rests; the tick polls

    def interrupt(_s):
        raise KeyboardInterrupt
    assert env.run("--path", "time-stop", "--db", str(db), "--step", "tick", "--send", sleep=interrupt) == 130
    conn = sqlite3.connect(str(db))
    sides = [r[0] for r in conn.execute("SELECT side FROM drill_orders ORDER BY id")]
    conn.close()
    assert sides == ["buy", "sell"]
    assert "INTERRUPTED (Ctrl-C)" in env.record.read_text()


def test_every_order_id_carries_the_drill_prefix(env):
    for path in ("profit-take", "time-stop", "resting-close"):
        db = _open(env, path)
        env.run("--path", path, "--db", str(db), "--step", "tick", "--send")
    ids = [r.client_order_id for r in env.venue.submitted]
    assert len(ids) >= 6 and all(i.startswith("do-drill-") for i in ids), ids
    assert {i.split("-")[2] for i in ids} == {"pt", "ts", "rc"}


def test_drill_order_id_rewrites_the_monitors_ids():
    assert drill.drill_order_id("do-close-MARA261113C00012000-2026-11-10", tag="ts", fallback="x") == \
        "do-drill-ts-close-MARA261113C00012000-2026-11-10"
    assert drill.drill_order_id("do-drill-ts-open-x", tag="ts", fallback="x") == "do-drill-ts-open-x"


def test_pick_chooses_a_short_dated_liquid_call_at_least_5pct_otm():
    today = date(2026, 11, 10)
    chain = [Contract("MARA261113C00011800", date(2026, 11, 13), "C", 11.8, 0.30, 0.31),      # 3.5% OTM: too near
             Contract("MARA261113C00012000", date(2026, 11, 13), "C", 12.0, 0.20, 0.24),      # 5.3% OTM
             Contract("MARA261113C00012500", date(2026, 11, 13), "C", 12.5, 0.01, 0.05),      # no real bid
             Contract("F261218C00012000", date(2026, 12, 18), "C", 12.0, 0.40, 0.44),      # too far out
             Contract("MARA261113C00010000", date(2026, 11, 13), "C", 10.0, 1.45, 1.55),      # 12% ITM
             Contract("MARA261111C00012000", date(2026, 11, 11), "C", 12.0, 0.20, 0.24)]      # 1 DTE
    kw = {"underlying_price": 11.4, "today": today, "max_dte": 7, "budget": 250.0}
    assert drill.pick_short_dated(chain, **kw).symbol == "MARA261111C00012000"              # nearest expiry
    two_day = drill.earliest_expiry("pre-market", today)
    assert drill.pick_short_dated(chain, **kw, earliest=two_day).symbol == "MARA261113C00012000"
    assert drill.pick_short_dated(chain, **kw, moneyness="itm").symbol == "MARA261113C00010000"
    assert drill.pick_short_dated(chain[2:4], **kw) is None


def test_pick_through_the_cli_honours_the_two_day_minimum(env, capsys):
    db = env.tmp / "pm.db"
    assert env.run("--path", "pre-market", "--db", str(db), "--step", "open", "--pick", "--symbol", "MARA",
                   "--send") == 0
    assert _rows(db)[0]["contract_symbol"] == OTM                       # not the 1-DTE NEXT_DAY contract
    assert "picked " + OTM in capsys.readouterr().out


def test_out_file_holds_every_block(env):
    db = _open(env, "time-stop")
    assert env.run("--path", "time-stop", "--db", str(db), "--step", "tick", "--send") == 0
    text = env.record.read_text()
    assert text.count("### #466 drill · time-stop") == 2
    assert "| | venue (paper; read per symbol / per order id) | journal (scratch DB) |" in text


# ── review 2 ─────────────────────────────────────────────────────────────────────────────────────

def test_the_two_day_paths_count_nyse_sessions_not_calendar_days():
    fri, wed_before_thanksgiving = date(2026, 11, 13), date(2026, 11, 25)
    assert drill.next_trading_day(fri) == date(2026, 11, 16)
    assert drill.earliest_expiry("pre-market", fri) == date(2026, 11, 17)       # Monday is the next session
    assert drill.earliest_expiry("resting-close", wed_before_thanksgiving) == date(2026, 11, 28)  # Thu is a holiday
    assert drill.earliest_expiry("time-stop", fri) == date(2026, 11, 14)
    chain = [Contract(MONDAY, date(2026, 11, 16), "C", 12.0, 0.20, 0.24),
             Contract(TUESDAY, date(2026, 11, 17), "C", 12.0, 0.22, 0.26)]
    kw = {"underlying_price": 11.4, "today": fri, "max_dte": 7, "budget": 250.0}
    assert drill.pick_short_dated(chain, **kw, earliest=drill.earliest_expiry("pre-market", fri)).symbol == TUESDAY
    assert drill.pick_short_dated(chain, **kw).symbol == MONDAY


@pytest.mark.parametrize("path", ["pre-market", "resting-close"])
def test_a_friday_open_refuses_a_monday_expiry_on_the_two_day_paths(env, path):
    _at(env, FRI, True)                                   # calendar DTE 3 ≥ 2, but Monday is the next session
    assert env.run("--path", path, "--db", str(env.tmp / f"{path}.db"), "--step", "open", "--contract", MONDAY,
                   "--send") == 2
    assert env.venue.submitted == []
    assert env.run("--path", path, "--db", str(env.tmp / f"{path}-tue.db"), "--step", "open", "--contract", TUESDAY,
                   "--send") == 0


def test_an_unopenable_out_refuses_before_any_step(env, capsys):
    db = env.tmp / "ts.db"
    rc = drill.main(["--path", "time-stop", "--db", str(db), "--step", "open", "--contract", OTM, "--send",
                     "--out", str(env.tmp / "no-such-dir" / "record.md"), "--poll-s", "0.2"],
                    config=copy.deepcopy(BASE_CONFIG), market=env.market, credentials=("k", "s"), sleep=lambda s: None)
    assert env.venue.submitted == [], "the step traded before --out was known to be writable"
    assert rc == 2 and "cannot be opened for append" in capsys.readouterr().out
    assert not db.exists()


def _out_run(env, out, db):
    return drill.main(["--path", "time-stop", "--db", str(db), "--step", "open", "--contract", OTM, "--send",
                       "--out", str(out), "--poll-s", "0.2"],
                      config=copy.deepcopy(BASE_CONFIG), market=env.market, credentials=("k", "s"),
                      sleep=lambda s: None)


def test_out_may_not_be_the_scratch_db(env):
    db = env.tmp / "ts.db"
    assert _out_run(env, db, db) == 2
    assert env.venue.submitted == [] and not db.exists()


def test_out_may_not_be_a_production_journal_candidate(env, capsys):
    prod = env.repo / "data" / "dramatic_options.db"
    assert _out_run(env, prod, env.tmp / "ts.db") == 2
    assert "is the production journal" in capsys.readouterr().out
    assert env.venue.submitted == [] and not prod.exists()


def test_out_may_not_be_an_existing_sqlite_file(env):
    other = env.tmp / "some.sqlite"
    conn = sqlite3.connect(str(other))
    conn.execute("CREATE TABLE t (x)")
    conn.commit()
    conn.close()
    before = other.read_bytes()
    assert _out_run(env, other, env.tmp / "ts.db") == 2
    assert other.read_bytes() == before and env.venue.submitted == []


def test_an_unreadable_share_baseline_refuses_the_open(env):
    env.venue.unreadable.add("MARA")
    assert env.run("--path", "time-stop", "--db", str(env.tmp / "ts.db"), "--step", "open", "--contract", OTM,
                   "--send") == 2
    assert env.venue.submitted == []


def test_unreadable_shares_are_a_mismatch(env, capsys):
    db = _open(env, "time-stop")
    env.venue.unreadable.add("MARA")
    capsys.readouterr()
    assert env.run("--path", "time-stop", "--db", str(db), "--step", "observe") == 0
    out = capsys.readouterr().out
    assert "verdict: MISMATCH" in out and "share quantity is unreadable" in out


def test_db_refusal_opens_a_foreign_file_read_only(env, monkeypatch):
    db = env.tmp / "foreign.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE notes (t TEXT)")
    conn.execute("INSERT INTO notes VALUES ('keep')")
    conn.commit()
    conn.close()
    os.utime(db, (1_700_000_000, 1_700_000_000))
    before, mtime = db.read_bytes(), db.stat().st_mtime
    opened = []
    real_connect = drill.sqlite3.connect

    def spy(target, *a, **k):
        opened.append((str(target), k.get("uri", False)))
        return real_connect(target, *a, **k)
    monkeypatch.setattr(drill.sqlite3, "connect", spy)
    assert drill.db_refusal(db, BASE_CONFIG) is not None
    assert db.read_bytes() == before and db.stat().st_mtime == mtime
    assert not (env.tmp / "foreign.sqlite-journal").exists()
    on_db = [(t, uri) for t, uri in opened if "foreign.sqlite" in t]
    assert on_db and all(uri and t.endswith("?mode=ro") for t, uri in on_db), on_db


def test_flatten_refuses_with_the_market_closed(env):
    db = _open(env, "unsellable")
    assert env.run("--path", "unsellable", "--db", str(db), "--step", "tick", "--send") == 0
    assert env.venue.positions[OTM] == 1
    n = len(env.venue.submitted)
    _at(env, DAY2_PRE, False)
    assert env.run("--path", "unsellable", "--db", str(db), "--step", "flatten", "--send") == 2
    assert len(env.venue.submitted) == n and env.venue.positions[OTM] == 1


def test_pre_market_on_an_unknown_clock_read_fails_its_check(env, monkeypatch, capsys):
    db = _open(env, "pre-market")
    _at(env, DAY2, True)                                   # in session, but the clock read fails

    def boom():
        raise RuntimeError("clock down")
    monkeypatch.setattr(env.clock, "is_market_open", boom)
    capsys.readouterr()
    assert env.run("--path", "pre-market", "--db", str(db), "--step", "tick", "--send") == 3
    out = capsys.readouterr().out
    assert "closed state: UNKNOWN" in out and "CHECK FAIL: the closed market was confirmed by the clock" in out
    assert env.venue.submitted[1:] == []                   # still nothing sent (treated as closed)


def test_a_confirmed_closed_tick_says_so(env, capsys):
    db = _open(env, "pre-market")
    _at(env, DAY2_PRE, False)
    capsys.readouterr()
    assert env.run("--path", "pre-market", "--db", str(db), "--step", "tick", "--send") == 0
    assert "closed state: CONFIRMED closed by the clock" in capsys.readouterr().out
