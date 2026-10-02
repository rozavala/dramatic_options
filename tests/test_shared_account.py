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

def test_the_loop_never_reads_account_positions():
    for rel, src in _py_sources():
        if rel == "data/alpaca_client.py":
            continue  # the thin client defines get_positions; nothing in the loop calls it
        assert "get_all_positions" not in src, rel
        assert not re.search(r"\.get_positions\(", src), rel


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
