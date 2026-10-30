"""#355/#366 hook — the orchestrator's drawdown WARN page, evaluated once per cycle after the monitor pass (L1 and every
L2 --monitor tick, operator 2026-10-27): skipped under --demo, display-only otherwise."""

from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime

import pytest

import drawdown_warn
import notify
import orchestrator
import state
from clock import FixedClock
from paper_loop import kill_rule_status

CONFIG = {
    "convexity_book": {"account_equity": 100_000.0, "book_fraction": 0.10},
    "kill_rule": {"book_drawdown_halt": 0.20, "dry_months_halt": 9},
}


def _book_at_drawdown(conn, dd_frac: float) -> None:
    entry = 10_000.0
    pid = state.record_convexity_position(
        conn, run_id=None, opened_at="2026-01-01T00:00:00+00:00", theme="t", symbol="FCX", direction="bullish",
        structure_kind="long_call", contract_symbol="FCXC", expiry="2026-12-18", strike=80.0, dte=270,
        moneyness=0.25, contracts=1, entry_premium_per_contract=entry, total_premium=entry)
    state.mark_convexity_position(conn, pid, mark=entry * (1 - dd_frac) / 100.0, as_of="2026-06-01T00:00:00+00:00")


@pytest.fixture
def sent(monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(notify, "send", lambda title, message, *, priority=0: calls.append((title, priority)) or True)
    return calls


def _cfg(tmp_path):
    return {**CONFIG, "database": {"path": str(tmp_path / "real.db")}}


def test_demo_skips_the_hook_entirely(convexity_db, tmp_path, sent):
    _book_at_drawdown(convexity_db, 0.12)  # would page if not demo
    assert orchestrator._page_drawdown_warn(convexity_db, _cfg(tmp_path), demo=True) is False
    assert sent == []
    assert not (tmp_path / "drawdown_warn_state.json").exists()  # the real latch is never touched


def test_demo_does_not_clobber_a_real_warn_latch(convexity_db, tmp_path, sent):
    latch = tmp_path / "drawdown_warn_state.json"
    latch.write_text(json.dumps({"level": "warn"}))
    # demo book is at 0% (would record "ok" and re-arm a duplicate page on the next real run)
    assert orchestrator._page_drawdown_warn(convexity_db, _cfg(tmp_path), demo=True) is False
    assert json.loads(latch.read_text()) == {"level": "warn"} and sent == []


def test_real_run_pages_once_per_crossing_and_never_changes_the_kill_rule(convexity_db, tmp_path, sent):
    _book_at_drawdown(convexity_db, 0.12)
    cfg = _cfg(tmp_path)
    assert orchestrator._page_drawdown_warn(convexity_db, cfg, demo=False) is True
    assert sent == [("Book drawdown warning", 0)]
    assert orchestrator._page_drawdown_warn(convexity_db, cfg, demo=False) is False  # latched
    assert len(sent) == 1
    assert json.loads((tmp_path / "drawdown_warn_state.json").read_text()) == {"level": "warn"}


def test_hook_failure_never_raises(convexity_db, tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(drawdown_warn, "page_on_upward_crossing", boom)
    assert orchestrator._page_drawdown_warn(convexity_db, _cfg(tmp_path), demo=False) is False


def test_run_once_passes_demo_to_the_hook():
    assert "_page_drawdown_warn(conn, config, demo=demo)" in inspect.getsource(orchestrator.run_once)
    assert "kill_rule_status" not in inspect.getsource(orchestrator._page_drawdown_warn)


# ── #366: L1 + L2 (operator 2026-10-27) ─────────────────────────────────────────────────────────────────────────

def _remark(conn, dd_frac: float) -> None:
    pid = conn.execute("SELECT id FROM convexity_positions ORDER BY id LIMIT 1").fetchone()[0]
    state.mark_convexity_position(conn, pid, mark=10_000.0 * (1 - dd_frac) / 100.0, as_of="2026-06-02T00:00:00+00:00")


def test_hook_runs_once_per_cycle_in_the_monitor_pass_so_l2_ticks_evaluate_it():
    src = inspect.getsource(orchestrator.run_once)
    call = "_page_drawdown_warn(conn, config, demo=demo)"
    assert src.count(call) == 1                                  # one evaluation per cycle, L1 included
    assert src.index("mres = monitor_positions(") < src.index(call) < src.index("if not monitor_only:")
    # before the monitor_only branch ⇒ the L2 --monitor runs reach it; after monitor_positions ⇒ fresh marks


def test_an_l1_and_an_l2_run_on_one_crossing_send_one_page_and_a_new_crossing_pages_again(convexity_db, tmp_path, sent):
    cfg = _cfg(tmp_path)
    _book_at_drawdown(convexity_db, 0.12)
    assert orchestrator._page_drawdown_warn(convexity_db, cfg, demo=False) is True    # the L2 tick that crosses
    assert orchestrator._page_drawdown_warn(convexity_db, cfg, demo=False) is False   # the same day's L1
    _remark(convexity_db, 0.095)                                                       # 9–10% band: no re-arm
    assert orchestrator._page_drawdown_warn(convexity_db, cfg, demo=False) is False
    _remark(convexity_db, 0.11)
    assert orchestrator._page_drawdown_warn(convexity_db, cfg, demo=False) is False
    _remark(convexity_db, 0.05)                                                        # below ~9%: re-arms
    assert orchestrator._page_drawdown_warn(convexity_db, cfg, demo=False) is False
    _remark(convexity_db, 0.12)                                                        # a new upward crossing
    assert orchestrator._page_drawdown_warn(convexity_db, cfg, demo=False) is True
    assert sent == [("Book drawdown warning", 0), ("Book drawdown warning", 0)]


# ── #370: the kill-rule trip pages from the L2 monitor too ───────────────────────────────────────────────────────

def test_an_l2_tick_that_finds_the_book_tripped_pages_the_kill_rule_once(convexity_db, tmp_path, sent):
    cfg = _cfg(tmp_path)
    _book_at_drawdown(convexity_db, 0.21)
    assert kill_rule_status(convexity_db, cfg, FixedClock(datetime(2026, 6, 1, tzinfo=UTC))).tripped  # same rule
    assert orchestrator._page_drawdown_warn(convexity_db, cfg, demo=False) is True     # the L2 tick that trips
    assert sent == [("Kill rule tripped — new entries halted", 1)]
    assert orchestrator._page_drawdown_warn(convexity_db, cfg, demo=False) is False    # later ticks: latched
    assert len(sent) == 1


def test_the_l1_halt_page_is_skipped_only_for_the_kill_rule_halt_1d_paged():
    src = inspect.getsource(orchestrator.run_once)
    dedup = 'trip_paged = dd_paged and any(n.startswith("kill rule tripped") for n in result.notes)'
    assert "dd_paged = _page_drawdown_warn(conn, config, demo=demo)" in src
    assert dedup in src and "if result.halted and not trip_paged:" in src
    assert src.index("dd_paged = _page_drawdown_warn(") < src.index(dedup) < src.index("if result.halted and not trip_paged:")


def test_the_dedup_matches_the_note_the_kill_rule_halt_writes(convexity_db):
    from paper_loop import run_paper_cycle

    _book_at_drawdown(convexity_db, 0.21)
    cfg = {**CONFIG, "convexity_book": {**CONFIG["convexity_book"], "account_equity": 100_000.0}}
    res = run_paper_cycle(config=cfg, conn=convexity_db, clock=FixedClock(datetime(2026, 6, 1, tzinfo=UTC)),
                          provider=None, broker=None, themes=[])
    assert res.halted and any(n.startswith("kill rule tripped") for n in res.notes)
