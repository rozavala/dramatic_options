"""#444 option (a): the read-only venue-vs-journal expiry check.

The broker auto-exercises an in-the-money long option at expiry; the journal models no exercise. The unsellable in-DB
close (``monitor._exit_position``) and expiry booked at intrinsic on the expiry date's first tick both leave the
contract at the venue while the journal shows it closed. On main nothing reads the venue for such a row, so nothing
sees it. These tests drive ``venue_check`` over a migrated DB and a fake broker whose only allowed call is the
per-contract ``venue_quantity`` read."""

import ast
import json
import logging
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

import state
import venue_check as vc
from clock import FixedClock

PL = "PL270115C00040000"          # the draft's worked example: 1 x $40 call, expiry Fri 2027-01-15
PL_EXP = "2027-01-15"
MON = FixedClock(datetime(2027, 1, 11, 14, 0, tzinfo=UTC))      # 09:00 ET, 4 NYSE trading days to PL's expiry
MON_LATER = FixedClock(datetime(2027, 1, 11, 20, 30, tzinfo=UTC))   # 15:30 ET, same ET day
TUE = FixedClock(datetime(2027, 1, 12, 14, 0, tzinfo=UTC))
REPO = Path(__file__).resolve().parents[1]


class _Broker:
    """Answers ``venue_quantity`` from a dict; every order-path method fails the test if it is ever called."""

    def __init__(self, qty=None, *, raises=()):
        self.qty, self.raises, self.reads, self.forbidden = dict(qty or {}), set(raises), [], []

    def venue_quantity(self, symbol):
        self.reads.append(symbol)
        if symbol in self.raises:
            raise RuntimeError("venue 503")
        return self.qty.get(symbol, 0)

    def _forbid(self, name):
        def call(*a, **k):
            self.forbidden.append(name)
            raise AssertionError(f"the venue check called {name}")
        return call

    def __getattr__(self, name):   # submit_paper, submit_spread, cancel_order, replace_order, order_status, ...
        if name.startswith("__"):
            raise AttributeError(name)
        return self._forbid(name)


class _Pager:
    def __init__(self):
        self.sent = []

    def __call__(self, title, message, *, priority=0):
        self.sent.append({"title": title, "message": message, "priority": priority})
        return True


def _open(conn, *, contract=PL, expiry=PL_EXP, contracts=1, strike=40.0, kind="C", symbol="PL", short=None,
          status="open"):
    pid = state.record_convexity_position(
        conn, run_id=None, opened_at="2026-07-01T19:45:00+00:00", theme="space", symbol=symbol,
        direction="bullish", structure_kind=kind, contract_symbol=contract, expiry=expiry, strike=strike, dte=200,
        moneyness=0.3, contracts=contracts, entry_premium_per_contract=150.0, total_premium=150.0 * contracts,
        rationale={"thesis": "x"}, status=status, order_id="o-1",
        short_contract_symbol=short, short_strike=(strike + 10 if short else None))
    return pid


def _close(conn, pid, reason="time_stop_21dte_unsellable"):
    state.close_convexity_position(conn, pid, exit_price=0.015, realized_pnl=-148.5, reason=reason,
                                   as_of="2026-12-28T14:30:00+00:00")


def _run(conn, broker, clock=MON, pager=None, *, dry_run=False, paper=True, run_id=None, **kw):
    pager = pager if pager is not None else _Pager()
    line = vc.run_tick(conn, broker=broker, clock=clock, dry_run=dry_run, paper_account=paper, run_id=run_id,
                       underlying_price_of=lambda s: 38.0, notify_send=pager, **kw)
    return line, pager


def _rows(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM convexity_positions ORDER BY id")]


# ── the orphan the issue names ───────────────────────────────────────────────────────────────────────────────────
def test_a_closed_in_db_row_the_venue_still_holds_pages_once_per_day(convexity_db):
    pid = _open(convexity_db)
    _close(convexity_db, pid)                       # the unsellable in-DB close: nothing was sent
    broker = _Broker({PL: 1})
    line, pager = _run(convexity_db, broker)
    assert len(pager.sent) == 1, "a contract the venue holds while the journal shows it closed did not page"
    page = pager.sent[0]
    assert page["title"] == "VENUE ≠ JOURNAL: PL" and page["priority"] == 1
    assert "the venue holds a contract the journal shows closed" in page["message"]
    assert "Orphan by design" in page["message"] and "4 NYSE trading day(s) to expiry 2027-01-15" in page["message"]
    assert "strike 40: 5.0% OTM" in page["message"]
    assert "mismatch=1" in line and f"mismatches={PL}:closed_but_held" in line and "paged=1" in line

    _, again = _run(convexity_db, broker, MON_LATER)          # the L2 runs every 30 min: same ET day, no repeat
    assert again.sent == [], "the same mismatch paged twice on one ET day"
    _, tue = _run(convexity_db, broker, TUE)                  # the next ET day pages again
    assert len(tue.sent) == 1
    paged = json.loads(state_row(convexity_db, pid)["rationale"])["paged"]
    assert paged[f"venue_check:closed_but_held:{PL}"] == "2027-01-12"


def state_row(conn, pid):
    return conn.execute("SELECT * FROM convexity_positions WHERE id = ?", (pid,)).fetchone()


def test_expiry_booked_at_intrinsic_on_the_morning_of_expiry_while_the_venue_holds_it(convexity_db):
    pid = _open(convexity_db)
    _close(convexity_db, pid, reason="expiry")
    fri = FixedClock(datetime(2027, 1, 15, 14, 0, tzinfo=UTC))   # 09:00 ET on the expiry date
    _, pager = _run(convexity_db, _Broker({PL: 1}), fri)
    assert len(pager.sent) == 1 and pager.sent[0]["priority"] == 1
    assert "booked expiry at intrinsic before the venue's expiry processing" in pager.sent[0]["message"]
    assert "0 NYSE trading day(s) to expiry" in pager.sent[0]["message"]


def test_the_debounce_stamp_is_the_et_date_not_the_utc_date(convexity_db):
    pid = _open(convexity_db)
    _close(convexity_db, pid)
    late = FixedClock(datetime(2027, 1, 12, 3, 0, tzinfo=UTC))   # 22:00 ET on Mon 01-11; already 01-12 in UTC
    _, first = _run(convexity_db, _Broker({PL: 1}), MON)
    _, second = _run(convexity_db, _Broker({PL: 1}), late)
    assert len(first.sent) == 1 and second.sent == [], "a UTC date split one ET day into two pages"


# ── quantities ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_a_quantity_mismatch_pages(convexity_db):
    _open(convexity_db, contracts=3)
    line, pager = _run(convexity_db, _Broker({PL: 2}))
    assert len(pager.sent) == 1, "a venue quantity that differs from the journal's did not page"
    assert "the venue quantity differs from the journal's" in pager.sent[0]["message"]
    assert "venue holds 2, the journal holds 3" in pager.sent[0]["message"]
    assert f"mismatches={PL}:quantity" in line


def test_a_journal_open_row_the_venue_does_not_hold_pages(convexity_db):
    _open(convexity_db, contracts=1)
    _, pager = _run(convexity_db, _Broker({PL: 0}))
    assert len(pager.sent) == 1 and "venue holds 0, the journal holds 1" in pager.sent[0]["message"]


def test_matches_do_not_page(convexity_db):
    _open(convexity_db, contracts=2)
    other = _open(convexity_db, contract="FCX270115C00080000", symbol="FCX", strike=80.0)
    _close(convexity_db, other, reason="profit_take_10x")          # really sold: the venue holds none
    broker = _Broker({PL: 2, "FCX270115C00080000": 0})
    line, pager = _run(convexity_db, broker)
    assert pager.sent == [], "a match paged"
    assert sorted(broker.reads) == sorted([PL, "FCX270115C00080000"])
    assert "contracts=2 match=2 mismatch=0 unknown=0" in line


def test_in_flight_rows_widen_the_match_but_not_beyond(convexity_db):
    closing = _open(convexity_db, contracts=2)
    state.begin_close_convexity_position(convexity_db, closing, close_order_id="cl-1", reason="time_stop_21dte",
                                         as_of="2027-01-11T14:30:00+00:00")
    for venue in (0, 1, 2):                       # the resting sell filled wholly, partly, or not yet
        _, pager = _run(convexity_db, _Broker({PL: venue}), FixedClock(datetime(2027, 1, 4 + venue, 15, tzinfo=UTC)))
        assert pager.sent == [], f"a closing row with venue {venue} paged"
    _, pager = _run(convexity_db, _Broker({PL: 3}))
    assert len(pager.sent) == 1 and "in flight: 0..2" in pager.sent[0]["message"]


def test_a_pending_buy_that_filled_is_not_a_mismatch(convexity_db):
    _open(convexity_db, contracts=1)
    _open(convexity_db, contracts=2, status="pending")
    for venue in (1, 3):
        _, pager = _run(convexity_db, _Broker({PL: venue}))
        assert pager.sent == []


def test_a_vertical_reads_both_legs_and_the_short_is_negative(convexity_db):
    short = "PL270115C00050000"
    _open(convexity_db, contracts=2, short=short)
    broker = _Broker({PL: 2, short: -2})
    _, pager = _run(convexity_db, broker)
    assert pager.sent == [] and sorted(broker.reads) == sorted([PL, short])
    _, pager = _run(convexity_db, _Broker({PL: 2, short: 0}))
    assert len(pager.sent) == 1 and short in pager.sent[0]["message"]


# ── fail-soft, not fail-silent ───────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("broker", [_Broker({PL: None}), _Broker(raises={PL})], ids=["none", "raises"])
def test_a_venue_read_error_is_an_unknown_not_a_match(convexity_db, caplog, broker):
    pid = _open(convexity_db)
    _close(convexity_db, pid)
    run_id = state.record_run(convexity_db, mode="PAPER", equity=None, note="l2")
    with caplog.at_level(logging.WARNING, logger="venue_check"):
        line, pager = _run(convexity_db, broker, run_id=run_id)
    assert "match=0" in line and "unknown=1" in line and f"unknown={PL}" in line, line
    assert any(r.levelno == logging.WARNING and PL in r.getMessage() for r in caplog.records)
    note = convexity_db.execute("SELECT note FROM runs WHERE id = ?", (run_id,)).fetchone()["note"]
    assert f"unknown={PL}" in note
    assert len(pager.sent) == 1 and pager.sent[0]["title"] == "VENUE READ UNKNOWN: PL"
    assert "UNKNOWN, not a match" in pager.sent[0]["message"]


def test_contracts_past_the_budget_are_unknown(convexity_db):
    _open(convexity_db)
    _open(convexity_db, contract="FCX270115C00080000", symbol="FCX", strike=80.0)
    ticks = iter([0.0, 0.0, 99.0, 99.0, 99.0])
    line, _ = _run(convexity_db, _Broker({PL: 1, "FCX270115C00080000": 1}), monotonic=lambda: next(ticks))
    assert "budget_skipped=1" in line and "unknown=1" in line and "match=1" in line


# ── the window ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_rows_outside_the_window_are_skipped(convexity_db):
    old = _open(convexity_db, contract="PL261218C00040000", expiry="2026-12-18")   # expired weeks before MON
    _close(convexity_db, old, reason="expiry")
    gone = _open(convexity_db, contract="PL270108C00040000", expiry="2027-01-08", status="pending")
    state.drop_convexity_position(convexity_db, gone, reason="order_canceled")
    broker = _Broker({"PL261218C00040000": 1, "PL270108C00040000": 1})
    line, pager = _run(convexity_db, broker)
    assert broker.reads == [] and pager.sent == []
    assert "contracts=0" in line and "skipped_window=1" in line


def test_far_from_expiry_pages_at_normal_priority(convexity_db):
    pid = _open(convexity_db, contract="PL270618C00040000", expiry="2027-06-18")
    _close(convexity_db, pid)
    _, pager = _run(convexity_db, _Broker({"PL270618C00040000": 1}))
    assert len(pager.sent) == 1 and pager.sent[0]["priority"] == 0


def test_trading_days_use_the_nyse_calendar():
    assert vc.trading_days_between(date(2027, 1, 11), date(2027, 1, 15)) == 4
    assert vc.trading_days_between(date(2026, 12, 23), date(2026, 12, 28)) == 2   # Christmas is not a session
    assert vc.trading_days_between(date(2027, 1, 15), date(2027, 1, 15)) == 0


# ── after expiry ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_after_expiry_a_held_contract_and_shares_page_on_paper(convexity_db):
    pid = _open(convexity_db)
    _close(convexity_db, pid, reason="expiry")
    mon_after = FixedClock(datetime(2027, 1, 18, 14, tzinfo=UTC))   # MLK day: no session yet, still in the window
    tue_after = FixedClock(datetime(2027, 1, 19, 14, tzinfo=UTC))   # the first session after expiry
    broker = _Broker({PL: 1, "PL": 100})
    _, pager = _run(convexity_db, broker, tue_after)
    assert len(pager.sent) == 2 and all(p["priority"] == 1 for p in pager.sent)
    assert any("still holds the contract after its expiry" in p["message"] for p in pager.sent)
    assert any("holds 100 share(s) of PL" in p["message"] for p in pager.sent)
    assert broker.reads == [PL, "PL"]
    _, pager = _run(convexity_db, _Broker({PL: 0, "PL": 0}), mon_after)
    assert pager.sent == []


def test_the_live_account_never_reads_the_underlyings_shares(convexity_db):
    pid = _open(convexity_db)
    _close(convexity_db, pid, reason="expiry")
    broker = _Broker({PL: 0, "PL": 100})
    line, pager = _run(convexity_db, broker, FixedClock(datetime(2027, 1, 19, 14, tzinfo=UTC)), paper=False)
    assert broker.reads == [PL] and pager.sent == [] and "shares=off" in line


# ── what it never touches ────────────────────────────────────────────────────────────────────────────────────────
def test_the_null_books_are_never_read(convexity_db):
    state.record_shadow_position(
        convexity_db, run_id=None, origin="null", opened_at="2026-07-01T00:00:00+00:00", theme="t", symbol="RKLB",
        direction="bullish", structure_kind="C", contract_symbol="RKLB270115C00030000", expiry=PL_EXP, strike=30.0,
        dte=200, moneyness=0.3, contracts=1, entry_premium_per_contract=100.0, total_premium=100.0)
    state.record_fixed_basket_position(
        convexity_db, run_id=None, book="union_nogate", origin="null", opened_at="2026-07-01T00:00:00+00:00",
        theme="t", symbol="ASTS", direction="bullish", structure_kind="C", contract_symbol="ASTS270115C00060000",
        expiry=PL_EXP, strike=60.0, dte=200, moneyness=0.3, contracts=1, entry_premium_per_contract=100.0,
        total_premium=100.0)
    broker = _Broker({"RKLB270115C00030000": 1, "ASTS270115C00060000": 1})
    line, pager = _run(convexity_db, broker)
    assert broker.reads == [] and pager.sent == [] and "contracts=0" in line


def test_nothing_is_submitted_cancelled_or_edited(convexity_db):
    a = _open(convexity_db, contracts=3)
    b = _open(convexity_db, contract="FCX270115C00080000", symbol="FCX", strike=80.0)
    _close(convexity_db, b)
    before = _rows(convexity_db)
    broker = _Broker({PL: 1, "FCX270115C00080000": 1}, raises=set())
    _run(convexity_db, broker)
    assert broker.forbidden == [], f"the check reached the order path: {broker.forbidden}"
    assert set(broker.reads) == {PL, "FCX270115C00080000"}
    after = _rows(convexity_db)
    for x, y in zip(before, after, strict=True):    # only the debounce stamp in the rationale may change
        assert {k: v for k, v in x.items() if k != "rationale"} == {k: v for k, v in y.items() if k != "rationale"}
        rx, ry = json.loads(x["rationale"]), json.loads(y["rationale"])
        ry.pop("paged", None)
        assert rx == ry
    assert {a, b} == {r["id"] for r in after}


def test_dry_run_reads_nothing(convexity_db):
    pid = _open(convexity_db)
    _close(convexity_db, pid)
    broker = _Broker({PL: 1})
    run_id = state.record_run(convexity_db, mode="PAPER", equity=None, note="l2")
    line, pager = _run(convexity_db, broker, dry_run=True, run_id=run_id)
    assert broker.reads == [] and pager.sent == [] and line.startswith("venue_check: off (DRY_RUN")
    assert "venue_check: off" in convexity_db.execute("SELECT note FROM runs WHERE id = ?", (run_id,)).fetchone()[0]


def test_a_broker_with_no_venue_read_is_off(convexity_db):
    from broker import PaperBroker

    _open(convexity_db)
    line, pager = _run(convexity_db, PaperBroker(100_000.0))
    assert "off (the broker has no per-contract venue read)" in line and pager.sent == []


def test_a_failing_pager_never_raises(convexity_db):
    pid = _open(convexity_db)
    _close(convexity_db, pid)

    def boom(*a, **k):
        raise RuntimeError("pushover down")
    line = vc.run_tick(convexity_db, broker=_Broker({PL: 1}), clock=MON, dry_run=False, paper_account=True,
                       run_id=None, notify_send=boom)
    assert "mismatch=1" in line and "paged=0" in line


def test_the_module_lists_no_account_positions():
    src = (REPO / "venue_check.py").read_text()
    for forbidden in ("get_all_positions", "get_positions(", "get_open_position(", "get_account_activities",
                      "submit_", "cancel_", "replace_order", "close_position"):
        assert forbidden not in src, forbidden


# ── the orchestrator wiring ──────────────────────────────────────────────────────────────────────────────────────
def _parents(tree):
    out = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            out[child] = node
    return out


def test_orchestrator_wiring_runs_in_the_l2_after_the_monitor_in_a_non_raising_try():
    tree = ast.parse((REPO / "orchestrator.py").read_text())
    run_once = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "run_once")
    calls = [n for n in ast.walk(run_once) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "run_tick" and getattr(n.func.value, "id", None) == "venue_check"]
    assert len(calls) == 1
    call, parents = calls[0], _parents(run_once)
    kw = {k.arg: k.value for k in call.keywords}
    # the CONFIGURED dry_run: monitor_dry_run is forced true on a closed tick and would switch the check off there
    assert getattr(kw["dry_run"], "id", None) == "dry_run"
    assert ast.unparse(kw["paper_account"]) == "not is_live"
    chain, node = [], call
    while node in parents:
        node, child = parents[node], node
        chain.append((node, child))
    ifs = [n for n, c in chain if isinstance(n, ast.If) and c in n.body]
    assert any(ast.unparse(n.test) == "monitor_only and (not demo)" for n in ifs), [ast.unparse(n.test) for n in ifs]
    tries = [n for n, c in chain if isinstance(n, ast.Try) and c in n.body]
    assert tries, "the call must sit in a try body"
    for handler in tries[0].handlers:
        assert handler.type is not None and getattr(handler.type, "id", "") == "Exception"
        assert not any(isinstance(x, ast.Raise) for x in ast.walk(handler))
    notes = [n for h in tries[0].handlers for n in ast.walk(h)
             if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "append_run_note"]
    assert notes, "a whole-check failure must leave a run note"
    monitor = [n for n in ast.walk(run_once) if isinstance(n, ast.Call) and getattr(n.func, "id", "") ==
               "monitor_positions"]
    assert monitor and all(m.lineno < call.lineno for m in monitor), "the check must read this tick's closes"
