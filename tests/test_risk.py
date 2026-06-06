"""Risk guards: kill switch (file + env), market-hours guard, daily-loss halt."""

from datetime import UTC, datetime

from dramatic_options import risk
from dramatic_options.clock import FixedClock


def test_kill_switch_via_file(tmp_path, monkeypatch):
    kill = tmp_path / "KILL"
    monkeypatch.setattr(risk, "KILL_FILE", kill)
    monkeypatch.delenv("KILL", raising=False)
    assert risk.kill_switch_active() is False
    kill.touch()
    assert risk.kill_switch_active() is True


def test_kill_switch_via_env(tmp_path, monkeypatch):
    monkeypatch.setattr(risk, "KILL_FILE", tmp_path / "nope")
    monkeypatch.setenv("KILL", "true")
    assert risk.kill_switch_active() is True
    monkeypatch.setenv("KILL", "0")
    assert risk.kill_switch_active() is False


def test_market_hours_guard_uses_clock():
    open_clock = FixedClock(datetime(2026, 1, 2, 15, 0, tzinfo=UTC), market_open=True)
    closed_clock = FixedClock(datetime(2026, 1, 3, 15, 0, tzinfo=UTC), market_open=False)
    assert risk.market_hours_guard(open_clock) is True
    assert risk.market_hours_guard(closed_clock) is False


def test_daily_loss_halt():
    # 6% loss on 100k with a 5% halt → halt.
    assert risk.daily_loss_halt(realized_pnl=-6000, equity=100_000, halt_pct=0.05) is True
    # 4% loss → no halt.
    assert risk.daily_loss_halt(realized_pnl=-4000, equity=100_000, halt_pct=0.05) is False
    # Fail-closed on non-positive equity.
    assert risk.daily_loss_halt(realized_pnl=0, equity=0, halt_pct=0.05) is True
