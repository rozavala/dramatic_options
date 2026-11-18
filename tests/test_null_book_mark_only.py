"""#477: on a closed-market tick the null books (shadow, 3A, 3B) mark and settle expiry, but skip profit-take and
time-stop — the real book's #451 mark-only rule (PREREG_FIXED_BASKET_NULL conformance note, 2026-11-18).

On main the null books booked a triggered exit at any tick's mark, so a wide after-hours quote could book a phantom
profit-take in a null book that the real book (mark-only since #451) could not. Each tick here is wired the way the
orchestrator wires it: ``monitor_mode`` from the fail-closed ``_safe_market_open`` read decides ``mark_only``, and the
same value goes to every null-book pass."""

import json
from datetime import UTC, datetime, timedelta

import fixed_basket
import orchestrator
import shadow_book
import state
from clock import FixedClock
from convexity_data import StaticQuoteProvider
from tests.test_fixed_basket import CONFIG as FB_CONFIG
from tests.test_fixed_basket import _insert_fb
from tests.test_shadow_book import CONFIG as SB_CONFIG
from tests.test_shadow_book import _insert_shadow

NOW = datetime(2026, 1, 2, 21, 0, tzinfo=UTC)                      # Fri 16:00 ET, the post-close tick
CLOSED = FixedClock(NOW, market_open=False)
OPEN = FixedClock(NOW + timedelta(days=3, hours=-5), market_open=True)   # Mon 11:00 ET
CONTRACT = "FCX261218C00080000"
PT_QP = StaticQuoteProvider({CONTRACT: 25.0})                       # $2500/ct ≥ 10 × $200 → profit-take


class _BrokenClock(FixedClock):
    def is_market_open(self) -> bool:
        raise RuntimeError("clock endpoint down")


def _mark_only(clock, *, dry_run=False, demo=False) -> bool:
    return orchestrator.monitor_mode(dry_run=dry_run, market_open=orchestrator._safe_market_open(clock),
                                     demo=demo)[1]


def _shadow_tick(conn, clock, qp, **kw):
    return shadow_book.mark_shadow_positions(conn=conn, clock=clock, quote_provider=qp, config=SB_CONFIG,
                                             underlying_price_of=lambda s: 45.0, mark_only=_mark_only(clock, **kw))


def _fb_tick(conn, clock, qp, **kw):
    return fixed_basket.mark_fixed_basket_positions(conn=conn, clock=clock, quote_provider=qp, config=FB_CONFIG,
                                                    underlying_price_of=lambda s: 45.0,
                                                    mark_only=_mark_only(clock, **kw))


def _shadow_row(conn, pid):
    return conn.execute("SELECT status, mark, exit_reason FROM shadow_positions WHERE id=?", (pid,)).fetchone()


def _fb_row(conn, pid):
    return conn.execute("SELECT status, mark, exit_reason FROM fixed_basket_positions WHERE id=?", (pid,)).fetchone()


# ── the shadow book ──────────────────────────────────────────────────────────────────────────────

def test_closed_tick_leaves_a_shadow_profit_take_open(convexity_db):
    pid = _insert_shadow(convexity_db, contract=CONTRACT, entry_pc=200.0)
    res = _shadow_tick(convexity_db, CLOSED, PT_QP)
    row = _shadow_row(convexity_db, pid)
    assert row["status"] == "open", "the shadow book booked a closed-tick profit-take the real book could not"
    assert row["mark"] == 25.0 and row["exit_reason"] is None
    assert res.marked == 1 and res.deferred == 1 and res.profit_taken == 0 and res.closed == 0


def test_closed_tick_leaves_a_shadow_time_stop_open(convexity_db):
    pid = _insert_shadow(convexity_db, contract=CONTRACT, expiry="2026-01-15")      # 13 DTE ≤ 21
    res = _shadow_tick(convexity_db, CLOSED, StaticQuoteProvider({CONTRACT: 1.0}))
    assert _shadow_row(convexity_db, pid)["status"] == "open"
    assert res.deferred == 1 and res.time_stopped == 0


def test_the_next_open_tick_books_the_deferred_shadow_exit(convexity_db):
    pid = _insert_shadow(convexity_db, contract=CONTRACT, entry_pc=200.0)
    _shadow_tick(convexity_db, CLOSED, PT_QP)
    res = _shadow_tick(convexity_db, OPEN, PT_QP)
    assert res.profit_taken == 1 and res.deferred == 0
    row = _shadow_row(convexity_db, pid)
    assert row["status"] == "closed" and row["exit_reason"].startswith("profit_take")


def test_closed_tick_still_settles_a_shadow_expiry(convexity_db):
    pid = _insert_shadow(convexity_db, contract=CONTRACT, expiry="2025-12-31")
    res = _shadow_tick(convexity_db, CLOSED, StaticQuoteProvider({}))
    assert res.expired == 1 and res.closed == 1 and res.deferred == 0
    assert _shadow_row(convexity_db, pid)["exit_reason"] == "expiry"


def test_an_unconfirmed_market_reads_as_closed_for_the_shadow_book(convexity_db):
    pid = _insert_shadow(convexity_db, contract=CONTRACT, entry_pc=200.0)
    res = _shadow_tick(convexity_db, _BrokenClock(NOW), PT_QP)                       # fail-closed
    assert res.deferred == 1 and _shadow_row(convexity_db, pid)["status"] == "open"


def test_dry_run_and_demo_closed_ticks_still_book_like_the_real_book(convexity_db):
    # The null books mirror the real book's decision exactly: in DRY_RUN and demo the real monitor still books exits
    # in-DB at the mark on a closed tick (pure simulation), so the null books do too.
    a = _insert_shadow(convexity_db, contract=CONTRACT, entry_pc=200.0)
    assert _shadow_tick(convexity_db, CLOSED, PT_QP, dry_run=True).profit_taken == 1
    b = _insert_shadow(convexity_db, contract=CONTRACT, entry_pc=200.0)
    assert _shadow_tick(convexity_db, CLOSED, PT_QP, demo=True).profit_taken == 1
    assert {_shadow_row(convexity_db, p)["status"] for p in (a, b)} == {"closed"}


# ── 3A and 3B (one pass marks both books) ────────────────────────────────────────────────────────

def test_closed_tick_leaves_3a_and_3b_exits_open(convexity_db):
    pa = _insert_fb(convexity_db, symbol="FCX", contract=CONTRACT, total_premium=200.0,
                    book=fixed_basket.BOOK_UNION_NOGATE)
    pb = _insert_fb(convexity_db, symbol="FCX", contract="FCX260115C00080000", total_premium=200.0,
                    expiry="2026-01-15", book=fixed_basket.BOOK_BASKET_NOGATE)          # 13 DTE → time-stop
    qp = StaticQuoteProvider({CONTRACT: 25.0, "FCX260115C00080000": 1.0})
    res = _fb_tick(convexity_db, CLOSED, qp)
    assert _fb_row(convexity_db, pa)["status"] == "open", "3A booked a closed-tick profit-take"
    assert _fb_row(convexity_db, pb)["status"] == "open", "3B booked a closed-tick time-stop"
    assert res.marked == 2 and res.deferred == 2 and res.closed == 0
    res = _fb_tick(convexity_db, OPEN, qp)
    assert res.profit_taken == 1 and res.time_stopped == 1 and res.deferred == 0
    assert _fb_row(convexity_db, pa)["exit_reason"].startswith("profit_take")
    assert _fb_row(convexity_db, pb)["exit_reason"].startswith("time_stop")


def test_closed_tick_still_settles_a_3a_expiry(convexity_db):
    pid = _insert_fb(convexity_db, symbol="FCX", contract=CONTRACT, total_premium=200.0, expiry="2025-12-31")
    res = _fb_tick(convexity_db, CLOSED, StaticQuoteProvider({}))
    assert res.expired == 1 and _fb_row(convexity_db, pid)["exit_reason"] == "expiry"


# ── the orchestrator threads its one decision to every null book, and stamps the rule ──────────────────────

def test_the_orchestrator_passes_its_mark_only_to_both_null_book_passes(monkeypatch):
    monkeypatch.delenv("KILL", raising=False)
    seen: dict[str, object] = {}
    real_sb, real_fb = shadow_book.mark_shadow_positions, fixed_basket.mark_fixed_basket_positions

    def _sb(**kw):
        seen["shadow"] = kw.get("mark_only")
        return real_sb(**kw)

    def _fb(**kw):
        seen["fixed_basket"] = kw.get("mark_only")
        return real_fb(**kw)

    monkeypatch.setattr(shadow_book, "mark_shadow_positions", _sb)
    monkeypatch.setattr(fixed_basket, "mark_fixed_basket_positions", _fb)
    monkeypatch.setattr(orchestrator, "monitor_mode", lambda **kw: (True, True))     # a closed tick outside DRY_RUN
    assert orchestrator.run_once(demo=True) == 0
    assert seen == {"shadow": True, "fixed_basket": True}


def test_model_mix_stamps_the_null_book_exit_rule(convexity_db):
    from council.router import FakeRouter

    run_id = state.record_run(convexity_db, mode="TEST", equity=None, note="t")
    orchestrator._stamp_council_health(convexity_db, run_id, {}, FakeRouter(), catalysts=None)
    mix = json.loads(convexity_db.execute("SELECT model_mix FROM runs WHERE id=?", (run_id,)).fetchone()["model_mix"])
    assert mix["null_exits"] == "closed_tick_mark_only_v1"
