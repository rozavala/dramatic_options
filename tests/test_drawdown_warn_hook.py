"""#355 hook — the orchestrator's L1 drawdown WARN page: skipped under --demo, display-only otherwise."""

from __future__ import annotations

import inspect
import json

import pytest

import drawdown_warn
import notify
import orchestrator
import state

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
