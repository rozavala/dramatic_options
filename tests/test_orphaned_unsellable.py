"""#444, PREREG_REAL_MONEY_BROKER §3c (2026-11-18): an unsellable real position stays OPEN, tagged ``orphaned``.

On main, a triggered profit-take or time-stop whose bid was below ``convexity_exits.min_close_bid`` booked an in-DB
close at the mark and sent nothing, so the journal showed the position closed while the contract was still held at
the broker (and could finish in the money and be exercised). Now the row stays open with the reason, the trigger and
the first-orphaned date in its rationale; every open-market tick re-evaluates it (a real sell once the bid allows),
and expiry settles it through the expiry branch. DRY_RUN / sim keeps the in-DB close."""

import json
import logging
from datetime import timedelta

import pytest

import notify
import state
from broker import Fill
from clock import FixedClock, et_date
from convexity_data import StaticQuoteProvider
from monitor import ORPHAN_PAGE, monitor_positions
from tests.test_monitor import CONFIG, NOW, _FakeBroker, _open, _row

CFG = {**CONFIG, "convexity_exits": {**CONFIG["convexity_exits"], "min_close_bid": 0.05}}
CLOCK = FixedClock(NOW, market_open=True)
EXP = (NOW.date() + timedelta(days=9)).isoformat()             # 9 DTE ≤ 21 → time-stop
C = "FCX260610C00080000"


def _qp(bid):
    return StaticQuoteProvider({C: 0.10}, bids={C: bid})


def _tick(conn, qp, broker, *, clock=CLOCK, dry_run=False, up=45.0):
    return monitor_positions(conn=conn, clock=clock, quote_provider=qp, config=CFG, broker=broker,
                             dry_run=dry_run, underlying_price_of=lambda s: up)


def _rat(conn, pid):
    return json.loads(_row(conn, pid, "rationale")["rationale"] or "{}") or {}


def _pages(monkeypatch, delivered=True):
    sent = []

    def _send(title, message, **kw):
        sent.append((title, message))
        return delivered if not callable(delivered) else delivered()

    monkeypatch.setattr(notify, "send", _send)
    return sent


def test_an_unsellable_time_stop_stays_open_tagged_orphaned(convexity_db, monkeypatch, caplog):
    pages = _pages(monkeypatch)
    pid = _open(convexity_db, contract=C, entry_pc=500.0, expiry=EXP)
    broker = _FakeBroker()
    with caplog.at_level(logging.INFO, logger="monitor"):
        res = _tick(convexity_db, _qp(0.0), broker)
    assert broker.sells == []
    row = _row(convexity_db, pid, "status, exit_reason, realized_pnl, closed_at, mark")
    assert row["status"] == "open", "an unsellable exit booked a close the broker never saw (#444)"
    assert row["exit_reason"] is None and row["realized_pnl"] is None and row["closed_at"] is None
    assert row["mark"] == 0.10
    tag = _rat(convexity_db, pid)["orphaned"]
    assert tag["trigger"] == "time_stop_21dte" and "below min_close_bid 0.05" in tag["reason"]
    assert tag["since"] == str(et_date(NOW)) and tag["ticks"] == 1
    assert res.orphaned == 1 and res.time_stopped == 0 and res.closed == 0 and res.realized_pnl == 0.0
    assert any("EXIT UNSELLABLE" in r.getMessage() and r.levelno == logging.INFO for r in caplog.records)
    assert [t for t, _ in pages] == [ORPHAN_PAGE]


@pytest.mark.parametrize("bids", [{}, {"FCX261218C00080000": 0.0}, {"FCX261218C00080000": 0.04}],
                         ids=["no-bid", "zero-bid", "sub-min-bid"])
def test_a_profit_take_without_a_sellable_bid_is_not_triggered_so_not_orphaned(convexity_db, monkeypatch, bids):
    # #537: a profit-take needs a sellable bid (≥ min_close_bid); without one it does not trigger at all — no orphan
    # tag, no page, no sell. (Only the TIME-STOP is orphaned when unsellable, above.)
    pages = _pages(monkeypatch)
    pid = _open(convexity_db, contract="FCX261218C00080000", entry_pc=200.0)          # far expiry
    qp = StaticQuoteProvider({"FCX261218C00080000": 9.0}, bids=bids)                # $900 ≥ 4× $200
    broker = _FakeBroker()
    res = _tick(convexity_db, qp, broker)
    assert _row(convexity_db, pid, "status")["status"] == "open" and broker.sells == [] and pages == []
    assert (res.pt_unsellable_bid, res.orphaned, res.profit_taken) == (1, 0, 0)
    assert "orphaned" not in _rat(convexity_db, pid)


def test_each_tick_retries_logs_and_keeps_the_first_date_paging_once(convexity_db, monkeypatch):
    pages = _pages(monkeypatch)
    pid = _open(convexity_db, contract=C, entry_pc=500.0, expiry=EXP)
    broker = _FakeBroker()
    _tick(convexity_db, _qp(0.0), broker)
    later = FixedClock(NOW + timedelta(days=2), market_open=True)
    res = _tick(convexity_db, _qp(0.01), broker, clock=later)
    tag = _rat(convexity_db, pid)["orphaned"]
    assert tag["since"] == str(et_date(NOW)) and tag["ticks"] == 2 and tag["last_at"] == later.now().isoformat()
    assert res.orphaned == 1 and broker.sells == [] and _row(convexity_db, pid, "status")["status"] == "open"
    assert len(pages) == 1, "the orphan page repeats every day until expiry"


def test_an_undelivered_orphan_page_is_retried_next_tick(convexity_db, monkeypatch):
    results = iter([False, True])
    pages = _pages(monkeypatch, delivered=lambda: next(results))
    _open(convexity_db, contract=C, entry_pc=500.0, expiry=EXP)
    _tick(convexity_db, _qp(0.0), _FakeBroker())
    _tick(convexity_db, _qp(0.0), _FakeBroker())
    _tick(convexity_db, _qp(0.0), _FakeBroker())
    assert len(pages) == 2


def test_a_later_tick_with_a_sellable_bid_sells_through_the_normal_path(convexity_db, monkeypatch):
    _pages(monkeypatch)
    pid = _open(convexity_db, contract=C, entry_pc=500.0, expiry=EXP)
    broker = _FakeBroker(sell=Fill(True, 0.08, 1, "filled", order_id="cl-9", pending=False))
    _tick(convexity_db, _qp(0.0), broker)
    assert broker.sells == []
    res = _tick(convexity_db, _qp(0.08), broker, clock=FixedClock(NOW + timedelta(days=1), market_open=True))
    assert len(broker.sells) == 1 and broker.sells[0]["side"] == "sell" and broker.sells[0]["limit"] == 0.08
    row = _row(convexity_db, pid, "status, exit_reason, realized_pnl")
    assert row["status"] == "closed" and row["exit_reason"] == "time_stop_21dte"             # no _unsellable
    assert row["realized_pnl"] == 0.08 * 100 - 500.0                                         # the fill
    assert res.time_stopped == 1 and res.orphaned == 0


def test_an_orphan_settles_at_expiry_through_the_expiry_branch(convexity_db, monkeypatch):
    _pages(monkeypatch)
    pid = _open(convexity_db, contract=C, entry_pc=500.0, expiry=EXP, strike=80.0)
    _tick(convexity_db, _qp(0.0), _FakeBroker())
    at_expiry = FixedClock(NOW + timedelta(days=9, hours=21), market_open=False)
    res = _tick(convexity_db, StaticQuoteProvider({}), _FakeBroker(), clock=at_expiry, up=83.0)
    row = _row(convexity_db, pid, "status, exit_reason, mark, realized_pnl")
    assert res.expired == 1 and row["status"] == "closed" and row["exit_reason"] == "expiry"
    assert row["mark"] == 3.0 and row["realized_pnl"] == 3.0 * 100 - 500.0          # intrinsic, not the mark
    assert "orphaned" in _rat(convexity_db, pid)                                           # the history stays


def test_an_unsellable_vertical_is_orphaned(convexity_db, monkeypatch):
    _pages(monkeypatch)
    short = "FCX260610C00090000"
    pid = state.record_convexity_position(
        convexity_db, run_id=None, opened_at="2026-01-01T00:00:00+00:00", theme="t", symbol="FCX",
        direction="bullish", structure_kind="C", contract_symbol=C, expiry=EXP, strike=80.0, dte=270,
        moneyness=0.25, contracts=1, entry_premium_per_contract=300.0, total_premium=300.0, rationale={},
        status="open", short_contract_symbol=short, short_strike=90.0)

    class _SpreadBroker(_FakeBroker):
        spreads: list = []

        def submit_spread(self, **kw):
            self.spreads.append(kw)
            return Fill(True, 0.0, 1, "x", order_id="sp-1", pending=True)

    broker = _SpreadBroker()
    qp = StaticQuoteProvider({C: 0.04, short: 0.01}, bids={C: 0.02, short: 0.0})          # long bid < 0.05
    res = _tick(convexity_db, qp, broker)
    assert broker.spreads == [] and broker.sells == []
    assert _row(convexity_db, pid, "status")["status"] == "open" and res.orphaned == 1
    assert "no sellable spread" in _rat(convexity_db, pid)["orphaned"]["reason"]


def test_dry_run_still_books_the_exit_in_db_at_the_mark(convexity_db, monkeypatch):
    # DRY_RUN / sim sends nothing for ANY exit and no broker holds the contract: the in-DB close is the simulation.
    pages = _pages(monkeypatch)
    pid = _open(convexity_db, contract=C, entry_pc=500.0, expiry=EXP)
    broker = _FakeBroker()
    res = _tick(convexity_db, _qp(0.0), broker, dry_run=True)
    row = _row(convexity_db, pid, "status, exit_reason, mark")
    assert row["status"] == "closed" and row["exit_reason"] == "time_stop_21dte" and row["mark"] == 0.10
    assert res.time_stopped == 1 and res.closed == 1 and res.orphaned == 0 and broker.sells == []
    assert "orphaned" not in _rat(convexity_db, pid) and pages == []
