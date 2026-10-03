"""Issue #279 — the shared live Alpaca account (operator's stocks, Finance, alpha_options).

Alpaca nets positions per OCC contract across the whole account, so this project must (1) never touch
alpha_options' reserved SPY/XSP/SPX options, (2) never act on the account's positions, (3) never size off
the account's equity, and (4) mark every order it sends as its own. Items 5 (a buying-power reserve) and 6
(venue-named env keys) need operator numbers / a coordinated .env change and are out of this PR.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

import broker
import restricted as restricted_list
import risk
from broker import (
    CLIENT_ORDER_ID_PREFIX,
    AlpacaPaperBroker,
    PaperBroker,
    make_client_order_id,
    shared_account_reject,
)

REPO = Path(__file__).resolve().parents[1]


def _alpaca_broker(dry_run=True):
    b = object.__new__(AlpacaPaperBroker)   # no network client: the guard runs before any transmission
    b._dry_run, b._equity_override = dry_run, None

    class _NoSend:
        def submit_order(self, req):
            raise AssertionError("a rejected order must never reach the API")
    b._trading = _NoSend()
    return b


# ── 1. reserved option roots (alpha_options) ─────────────────────────────────────────────────────

@pytest.mark.parametrize("sym", ["SPY261218P00500000", "XSP261218P00050000", "SPX261218P05000000",
                                 "SPXW261218P05000000"])
@pytest.mark.parametrize("is_buy", [True, False])
def test_reserved_roots_rejected_on_both_sides(sym, is_buy):
    note = shared_account_reject(sym, is_buy=is_buy)
    assert note and "reserved for alpha_options" in note


def test_an_ordinary_contract_passes():
    assert shared_account_reject("FCX270319C00080000", is_buy=True) is None
    assert shared_account_reject("FCX270319C00080000", is_buy=False) is None


@pytest.mark.parametrize("dry_run", [True, False])
def test_the_broker_rejects_a_reserved_contract_in_every_mode(dry_run):
    fill = _alpaca_broker(dry_run).submit_paper(contract_symbol="SPY261218P00500000", qty=1, side="buy",
                                                limit_price=1.0, client_order_id="do-open-x")
    assert not fill.filled and "reserved" in fill.note
    fill = _alpaca_broker(dry_run).submit_paper(contract_symbol="SPY261218P00500000", qty=1, side="sell",
                                                limit_price=1.0, client_order_id="do-close-x")
    assert not fill.filled and "reserved" in fill.note


# ── the restricted list at the order layer (defense in depth under the union check) ───────────────

def test_restricted_buy_rejected_but_close_allowed(monkeypatch):
    monkeypatch.setattr(restricted_list, "load_restricted", lambda path=None: frozenset({"FCX"}))
    assert "restricted list" in shared_account_reject("FCX270319C00080000", is_buy=True)
    assert shared_account_reject("FCX270319C00080000", is_buy=False) is None   # never traps a position


def test_unreadable_restricted_list_rejects_the_buy(monkeypatch):
    def boom(path=None):
        raise restricted_list.RestrictedListError("malformed")
    monkeypatch.setattr(restricted_list, "load_restricted", boom)
    assert "unreadable" in shared_account_reject("FCX270319C00080000", is_buy=True)


def test_the_shipped_restricted_list_blocks_its_entry():
    assert "restricted list" in shared_account_reject("LIFE270319C00010000", is_buy=True)


# ── 4. every order id carries the project prefix ─────────────────────────────────────────────────

def test_client_order_ids_carry_the_project_prefix():
    for action in ("open", "close"):
        coid = make_client_order_id(action, "FCX270319C00080000", "2026-10-05")
        assert coid.startswith(CLIENT_ORDER_ID_PREFIX + action + "-")
    assert CLIENT_ORDER_ID_PREFIX == "do-" and not CLIENT_ORDER_ID_PREFIX.startswith("ao-")


def _py_sources():
    for p in REPO.rglob("*.py"):
        rel = p.relative_to(REPO).as_posix()
        if rel.startswith(("tests/", "shelf/", "venv/", ".venv/")) or "/site-packages/" in rel:
            continue
        yield rel, p.read_text()


def test_no_cancel_all_or_close_all_path_exists():
    for rel, src in _py_sources():
        for forbidden in ("cancel_orders(", "close_all_positions(", "close_position("):
            assert forbidden not in src, f"{rel} has an account-wide {forbidden!r} path"


def test_cancels_only_take_ids_from_this_projects_journal():
    # The only live cancel callers are the monitor's reconcilers, which pass ids read from this project's
    # own journal rows (pos['close_order_id'] / the pending entry's order id) — never an id listed from
    # the account.
    callers = [rel for rel, src in _py_sources() if re.search(r"\.cancel_order\(", src)]
    assert sorted(callers) == ["monitor.py", "scripts/smoke_order_roundtrip.py"]
    mon = (REPO / "monitor.py").read_text()
    assert "get_orders" not in mon and "list_orders" not in mon


# ── 2. positions are this project's, never the account's ─────────────────────────────────────────

def test_the_loop_never_lists_account_positions():
    # The foreign-quantity check reads ONE contract (get_open_position, broker.venue_quantity) — never a
    # listing of the account, which holds other projects' legs and the operator's stock.
    for rel, src in _py_sources():
        if rel == "data/alpaca_client.py":
            continue  # the thin client defines get_positions; nothing in the loop calls it
        assert "get_all_positions" not in src, rel
        assert not re.search(r"\.get_positions\(", src), rel
    readers = [rel for rel, src in _py_sources() if "get_open_position(" in src]
    assert readers == ["broker.py"]


# ── 3. sizing never falls back to whole-account equity ───────────────────────────────────────────

def test_missing_capital_base_halts_entries_instead_of_reading_broker_equity(convexity_db, monkeypatch):
    from clock import FixedClock
    from convexity_data import SyntheticChainProvider
    from paper_loop import run_paper_cycle
    from themes import Theme

    monkeypatch.delenv("KILL", raising=False)
    monkeypatch.setattr(risk, "KILL_FILE", Path("/nonexistent/KILL"))
    clock = FixedClock(datetime(2026, 1, 2, tzinfo=UTC))

    class _RichAccount(PaperBroker):
        def account_equity(self):
            raise AssertionError("sizing must never read whole-account equity")

    cfg = {"convexity_book": {"book_fraction": 0.10, "per_name_fraction": 0.01, "max_open_positions": 15},
           "convexity_gate": {"iv_rv_max": 1.2, "otm_skew_max_volpts": 10.0, "rv_window_days": 252,
                              "tenor_min_days": 180, "tenor_max_days": 365, "target_moneyness": 0.25},
           "eligibility": {"live": {"min_option_open_interest": 50, "max_bid_ask_pct": 0.25}},
           "kill_rule": {"book_drawdown_halt": 0.20, "dry_months_halt": 9}}
    res = run_paper_cycle(config=cfg, conn=convexity_db, clock=clock,
                          provider=SyntheticChainProvider(as_of=clock.now().date()),
                          broker=_RichAccount(250_000.0),
                          themes=[Theme("copper", "FCX", "bullish", "cheap")], run_id=None)
    assert res.halted and res.opened == 0
    assert any("account_equity is not configured" in n for n in res.notes)


def test_the_live_config_pins_the_capital_base():
    import json
    assert float(json.loads((REPO / "config.json").read_text())["convexity_book"]["account_equity"]) > 0


def test_broker_module_exports():
    assert broker.RESERVED_OPTION_ROOTS >= {"SPY", "XSP", "SPX"}


# ── finance#947 §3: the pre-open foreign-quantity check (one contract, never the account) ──────────

class _APIErr(Exception):
    def __init__(self, status_code, msg):
        super().__init__(msg)
        self.status_code = status_code


def _venue_broker(get_open_position):
    b = _alpaca_broker()
    b._trading = type("T", (), {"get_open_position": staticmethod(get_open_position)})()
    return b


def test_venue_quantity_reads_one_contract():
    assert _venue_broker(lambda s: type("P", (), {"qty": "3"})()).venue_quantity("FCX270319C00080000") == 3
    assert _venue_broker(lambda s: type("P", (), {"qty": "-2"})()).venue_quantity("FCX270319C00080000") == -2


def test_venue_quantity_no_position_is_zero_and_other_errors_are_unknown():
    def none(s):
        raise _APIErr(404, '{"code":40410000,"message":"position does not exist"}')

    def down(s):
        raise _APIErr(500, "internal error")
    assert _venue_broker(none).venue_quantity("FCX270319C00080000") == 0
    assert _venue_broker(down).venue_quantity("FCX270319C00080000") is None


def _cycle(convexity_db, monkeypatch, broker_obj):
    import notify
    from clock import FixedClock
    from convexity_data import SyntheticChainProvider
    from paper_loop import run_paper_cycle
    from themes import Theme

    monkeypatch.delenv("KILL", raising=False)
    monkeypatch.setattr(risk, "KILL_FILE", Path("/nonexistent/KILL"))
    pages = []
    monkeypatch.setattr(notify, "send", lambda *a, **k: pages.append(a))
    clock = FixedClock(datetime(2026, 1, 2, tzinfo=UTC))
    cfg = {"convexity_book": {"account_equity": 100_000.0, "book_fraction": 0.10, "per_name_fraction": 0.01,
                              "max_open_positions": 15},
           "convexity_gate": {"iv_rv_max": 1.2, "otm_skew_max_volpts": 10.0, "rv_window_days": 252,
                              "tenor_min_days": 180, "tenor_max_days": 365, "target_moneyness": 0.25},
           "eligibility": {"live": {"min_option_open_interest": 50, "max_bid_ask_pct": 0.25}},
           "kill_rule": {"book_drawdown_halt": 0.20, "dry_months_halt": 9}}
    res = run_paper_cycle(config=cfg, conn=convexity_db, clock=clock,
                          provider=SyntheticChainProvider(as_of=clock.now().date()), broker=broker_obj,
                          themes=[Theme("copper", "FCX", "bullish", "cheap")], run_id=None)
    decisions = [r[0] for r in convexity_db.execute("SELECT decision FROM convexity_eval")]
    return res, decisions, pages


class _VenueBroker(PaperBroker):
    """The simulated fill path plus a venue: the quantity another project may hold in the contract."""

    def __init__(self, venue_qty):
        super().__init__(100_000.0)
        self._venue_qty = venue_qty
        self.asked: list[str] = []

    def venue_quantity(self, contract_symbol):
        self.asked.append(contract_symbol)
        return self._venue_qty


def test_foreign_quantity_refuses_the_open_and_pages(convexity_db, monkeypatch):
    b = _VenueBroker(venue_qty=2)      # another project holds 2 of the contract; our journal explains 0
    res, decisions, pages = _cycle(convexity_db, monkeypatch, b)
    assert res.opened == 0 and "veto-foreign-quantity" in decisions
    assert pages and "Foreign quantity" in pages[0][0]
    assert len(b.asked) == 1           # read the ONE contract being traded


def test_unreadable_venue_quantity_refuses_the_open(convexity_db, monkeypatch):
    res, decisions, _ = _cycle(convexity_db, monkeypatch, _VenueBroker(venue_qty=None))
    assert res.opened == 0 and "veto-foreign-quantity" in decisions


def test_matching_venue_quantity_opens(convexity_db, monkeypatch):
    res, decisions, pages = _cycle(convexity_db, monkeypatch, _VenueBroker(venue_qty=0))
    assert res.opened == 1 and "veto-foreign-quantity" not in decisions
    assert not any("Foreign quantity" in p[0] for p in pages)


def test_a_broker_without_a_venue_skips_the_check(convexity_db, monkeypatch):
    res, decisions, _ = _cycle(convexity_db, monkeypatch, PaperBroker(100_000.0))
    assert res.opened == 1


def test_journal_quantity_counts_open_and_closing_only(convexity_db):
    import state
    for status, n in (("open", 2), ("closing", 1), ("pending", 5), ("closed", 7)):
        convexity_db.execute(
            "INSERT INTO convexity_positions (opened_at, theme, symbol, direction, structure_kind, contract_symbol,"
            " expiry, strike, dte, moneyness, contracts, entry_premium_per_contract, total_premium, status) "
            "VALUES ('2026-01-02','t','FCX','bullish','C','FCX270319C00080000','2027-03-19',80,300,0.25,?,100,100,?)",
            (n, status))
    assert state.journal_contract_quantity(convexity_db, "FCX270319C00080000") == 3


# ── finance#947 §4: the live buying-power reserve for the other projects ──────────────────────────

def _live(reserve, available=None, boom=False):
    b = object.__new__(broker.AlpacaLiveBroker)
    b._dry_run, b._equity_override, b._max_order_notional, b._shared_reserve = True, None, 5_000.0, reserve

    class _T:
        def get_account(self):
            if boom:
                raise RuntimeError("down")
            return type("A", (), {"options_buying_power": str(available), "cash": "0"})()

        def submit_order(self, req):
            raise AssertionError("must not transmit")
    b._trading = _T()
    return b


def test_reserve_unset_rejects_every_live_buy():
    f = _live(None, 50_000).submit_paper(contract_symbol="FCX270319C00080000", qty=1, side="buy", limit_price=2.0)
    assert not f.filled and "shared_account_reserve_usd" in f.note


def test_a_buy_that_breaches_the_reserve_is_rejected():
    # $6,000 available − $1,000 premium = $5,000 < $5,250
    f = _live(5_250, 6_000).submit_paper(contract_symbol="FCX270319C00080000", qty=1, side="buy", limit_price=10.0)
    assert not f.filled and "reserve" in f.note


def test_a_buy_within_the_reserve_passes_to_dry_run():
    f = _live(5_250, 20_000).submit_paper(contract_symbol="FCX270319C00080000", qty=1, side="buy", limit_price=10.0)
    assert f.filled and "DRY_RUN" in f.note


def test_unreadable_account_rejects_the_buy():
    f = _live(5_250, boom=True).submit_paper(contract_symbol="FCX270319C00080000", qty=1, side="buy",
                                             limit_price=1.0)
    assert not f.filled and "fail-closed" in f.note


def test_a_close_is_never_reserve_blocked():
    f = _live(5_250, 0).submit_paper(contract_symbol="FCX270319C00080000", qty=1, side="sell", limit_price=1.0)
    assert f.filled and "DRY_RUN" in f.note


def test_the_live_config_declares_alpha_options_reserve():
    import json
    assert json.loads((REPO / "config.json").read_text())["safety"]["shared_account_reserve_usd"] == 5250
