"""Real-book order visibility (2026-10-27): the quote at decision time is recorded, and an order that rests or
dies unfilled pages. HL (L1 #1816) was the first above-floor order since July; it was cancelled unfilled 12 minutes
after submission and the operator learned of it from the nightly grade."""
import json
from datetime import UTC, datetime
from pathlib import Path

import risk
import state
from broker import Fill, PaperBroker
from clock import FixedClock
from convexity_gate import Contract
from monitor import reconcile_pending
from paper_loop import _quote


class _RestingBroker(PaperBroker):
    """A real broker's shape: the limit is accepted and rests (pending), not filled on submit."""

    def submit_paper(self, *, contract_symbol, qty, side, limit_price, client_order_id=None):
        return Fill(True, float(limit_price), int(qty), f"SUBMITTED {qty}x {contract_symbol} (resting)",
                    order_id="ord-1", pending=True)


def _cycle(conn, monkeypatch, broker_obj):
    import notify
    from convexity_data import SyntheticChainProvider
    from paper_loop import run_paper_cycle
    from themes import Theme

    monkeypatch.delenv("KILL", raising=False)
    monkeypatch.setattr(risk, "KILL_FILE", Path("/nonexistent/KILL"))
    pages: list[tuple] = []
    monkeypatch.setattr(notify, "send", lambda *a, **k: pages.append(a))
    clock = FixedClock(datetime(2026, 1, 2, tzinfo=UTC))
    cfg = {"convexity_book": {"account_equity": 100_000.0, "book_fraction": 0.10, "per_name_fraction": 0.01,
                              "max_open_positions": 15},
           "convexity_gate": {"iv_rv_max": 1.2, "otm_skew_max_volpts": 10.0, "rv_window_days": 252,
                              "tenor_min_days": 180, "tenor_max_days": 365, "target_moneyness": 0.25},
           "eligibility": {"live": {"min_option_open_interest": 50, "max_bid_ask_pct": 0.25}},
           "kill_rule": {"book_drawdown_halt": 0.20, "dry_months_halt": 9}}
    res = run_paper_cycle(config=cfg, conn=conn, clock=clock,
                          provider=SyntheticChainProvider(as_of=clock.now().date()), broker=broker_obj,
                          themes=[Theme("copper", "FCX", "bullish", "cheap")], run_id=None)
    row = conn.execute("SELECT status, rationale FROM convexity_positions ORDER BY id DESC LIMIT 1").fetchone()
    return res, row, pages


def test_quote_math():
    c = Contract(symbol="HL270617C00017000", expiry=datetime(2027, 6, 17).date(), kind="C", strike=17.0,
                 bid=1.65, ask=1.87)
    assert _quote(c) == {"bid": 1.65, "ask": 1.87, "mid": 1.76, "spread_pct": 12.5}
    one_sided = Contract(symbol="X", expiry=datetime(2027, 6, 17).date(), kind="C", strike=1.0, bid=None, ask=1.0)
    assert _quote(one_sided) == {"bid": None, "ask": 1.0, "mid": None, "spread_pct": None}


def test_a_resting_real_order_pages_and_records_its_quote(convexity_db, monkeypatch):
    res, row, pages = _cycle(convexity_db, monkeypatch, _RestingBroker(100_000.0))
    assert res.opened == 1 and row["status"] == "pending"
    q = json.loads(row["rationale"])["quote"]
    assert q["bid"] is not None and q["ask"] >= q["bid"] and q["mid"] and q["spread_pct"] is not None
    titles = [p[0] for p in pages]
    assert titles.count("REAL-BOOK ORDER SUBMITTED") == 1
    body = pages[titles.index("REAL-BOOK ORDER SUBMITTED")][1]
    assert "FCX" in body and "LIMIT" in body and "spread" in body


def test_a_simulated_fill_records_the_quote_but_does_not_page(convexity_db, monkeypatch):
    res, row, pages = _cycle(convexity_db, monkeypatch, PaperBroker(100_000.0))
    assert res.opened == 1 and row["status"] == "open"
    assert "quote" in json.loads(row["rationale"])
    assert not any(p[0] == "REAL-BOOK ORDER SUBMITTED" for p in pages)


# ── reconcile: an entry that ends without a fill pages ─────────────────────────────────────────────────────

class _StatusBroker:
    def __init__(self, statuses):
        self._s, self.cancelled = statuses, []

    def order_status(self, oid):
        return self._s.get(oid)

    def cancel_order(self, oid):
        self.cancelled.append(oid)
        if (self._s.get(oid) or {}).get("state") in ("new", "accepted", "pending_new", "partially_filled"):
            self._s[oid] = {"state": "canceled"}   # the real venue reports the cancel


def _pending(conn, oid):
    return state.record_convexity_position(
        conn, run_id=None, opened_at="2026-10-26T19:48:30+00:00", theme="silver_deficit", symbol="HL",
        direction="bullish", structure_kind="C", contract_symbol="HL270617C00017000", expiry="2027-06-17",
        strike=17.0, dte=234, moneyness=0.22, contracts=5, entry_premium_per_contract=176.0, total_premium=880.0,
        status="pending", order_id=oid,
    )


def _reconcile(conn, monkeypatch, statuses):
    import notify
    pages: list[tuple] = []
    monkeypatch.setattr(notify, "send", lambda *a, **k: pages.append(a))
    reconcile_pending(conn=conn, broker=_StatusBroker(statuses), clock=FixedClock(datetime(2026, 10, 26, 20,
                      tzinfo=UTC)), config={"execution": {"cancel_unfilled": True}})
    return pages


def test_cancelled_unfilled_pages(convexity_db, monkeypatch):
    _pending(convexity_db, "o1")
    pages = _reconcile(convexity_db, monkeypatch, {"o1": {"state": "new"}})
    assert [p[0] for p in pages] == ["REAL-BOOK ORDER NOT FILLED"]
    assert "HL270617C00017000" in pages[0][1] and "$880" in pages[0][1] and "cancelled unfilled" in pages[0][1]


def test_a_terminal_broker_state_pages(convexity_db, monkeypatch):
    _pending(convexity_db, "o2")
    pages = _reconcile(convexity_db, monkeypatch, {"o2": {"state": "expired"}})
    assert [p[0] for p in pages] == ["REAL-BOOK ORDER NOT FILLED"] and "order expired" in pages[0][1]


def test_a_fill_pages_only_the_fill(convexity_db, monkeypatch):
    _pending(convexity_db, "o3")
    pages = _reconcile(convexity_db, monkeypatch, {"o3": {"state": "filled", "filled_avg_price": 1.76,
                                                          "filled_qty": 5}})
    assert [p[0] for p in pages] == ["REAL-BOOK FILL"]


def test_a_page_failure_never_breaks_the_reconcile(convexity_db, monkeypatch):
    import notify

    def boom(*a, **k):
        raise RuntimeError("pushover down")
    monkeypatch.setattr(notify, "send", boom)
    pid = _pending(convexity_db, "o4")
    reconcile_pending(conn=convexity_db, broker=_StatusBroker({"o4": {"state": "new"}}),
                      clock=FixedClock(datetime(2026, 10, 26, 20, tzinfo=UTC)),
                      config={"execution": {"cancel_unfilled": True}})
    assert convexity_db.execute("SELECT status FROM convexity_positions WHERE id=?", (pid,)).fetchone()[0] \
        == "cancelled"
