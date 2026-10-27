"""#355 — display-only drawdown WARN tier: levels, one page per upward crossing, the kill rule unchanged."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

import dashboard_data as dd
import drawdown_warn as dw
import state
from clock import FixedClock
from paper_loop import kill_rule_status

CONFIG = {
    "convexity_book": {"account_equity": 100_000.0, "book_fraction": 0.10, "per_name_fraction": 0.01,
                       "max_open_positions": 15, "cluster_fraction": 0.02},
    "kill_rule": {"book_drawdown_halt": 0.20, "dry_months_halt": 9},
    "council": {"cost_cap_usd": 5.0},
}
CLOCK = FixedClock(datetime(2026, 6, 1, tzinfo=UTC))


def _book_at_drawdown(conn, dd_frac: float) -> None:
    """One open position whose mark puts the open-book drawdown at ``dd_frac`` of the $10k book budget."""
    entry = 10_000.0
    pid = state.record_convexity_position(
        conn, run_id=None, opened_at="2026-01-01T00:00:00+00:00", theme="t", symbol="FCX", direction="bullish",
        structure_kind="long_call", contract_symbol="FCXC", expiry="2026-12-18", strike=80.0, dte=270,
        moneyness=0.25, contracts=1, entry_premium_per_contract=entry, total_premium=entry)
    state.mark_convexity_position(conn, pid, mark=entry * (1 - dd_frac) / 100.0, as_of="2026-06-01T00:00:00+00:00")


# ── levels ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("dd_frac,level", [
    (0.0, "ok"), (0.0999, "ok"), (0.10, "warn"), (0.12, "warn"), (0.1999, "warn"), (0.20, "tripped"), (0.21, "tripped"),
])
def test_drawdown_level_boundaries(dd_frac, level):
    assert dw.drawdown_level(dd_frac, 0.20) == level


def test_warn_at_or_above_halt_is_ignored():
    assert dw.drawdown_level(0.15, 0.20, warn=0.20) == "ok"


def test_12pct_fixture_shows_warn_and_21pct_shows_tripped(convexity_db):
    _book_at_drawdown(convexity_db, 0.12)
    kr = dd.risk_panel(convexity_db, CONFIG)["kill_rule"]
    assert kr["level"] == "warn" and kr["tripped"] is False and kr["drawdown_warn"] == 0.10
    convexity_db.execute("DELETE FROM convexity_positions")
    _book_at_drawdown(convexity_db, 0.21)
    kr = dd.risk_panel(convexity_db, CONFIG)["kill_rule"]
    assert kr["level"] == "tripped" and kr["tripped"] is True


def test_no_marks_reads_ok(convexity_db):
    assert dd.risk_panel(convexity_db, CONFIG)["kill_rule"]["level"] == "ok"


# ── the kill rule is unchanged ──────────────────────────────────────────────────────────────────
def test_kill_threshold_and_behavior_unchanged(convexity_db):
    import json as _json
    from pathlib import Path

    cfg = _json.loads((Path(__file__).resolve().parent.parent / "config.json").read_text())
    assert cfg["kill_rule"]["book_drawdown_halt"] == 0.20 and cfg["kill_rule"]["dry_months_halt"] == 9
    assert "book_drawdown_warn" not in cfg["kill_rule"]  # the warn tier lives outside the frozen kill block

    _book_at_drawdown(convexity_db, 0.12)  # warn tier must NOT halt entries
    krs = kill_rule_status(convexity_db, CONFIG, CLOCK)
    assert krs.tripped is False and krs.reasons == ()
    convexity_db.execute("DELETE FROM convexity_positions")
    _book_at_drawdown(convexity_db, 0.21)  # the unchanged 20% halt still trips
    krs = kill_rule_status(convexity_db, CONFIG, CLOCK)
    assert krs.tripped is True and "book drawdown" in krs.reasons[0] and "20%" in krs.reasons[0]
    assert dw.WARN_FRACTION < 0.20


# ── paging: exactly one per upward crossing ─────────────────────────────────────────────────────
class _Sender:
    def __init__(self, ok=True):
        self.calls, self.ok = [], ok

    def __call__(self, title, message, *, priority=0):
        self.calls.append((title, message, priority))
        return self.ok


def test_exactly_one_page_per_upward_crossing(tmp_path):
    p, s = tmp_path / "sub" / "w.json", _Sender()
    path = lambda d: dw.page_on_upward_crossing(d, 0.20, p, s)  # noqa: E731
    assert [path(0.05), path(0.09)] == [False, False] and not s.calls
    assert path(0.10) is True and len(s.calls) == 1                     # crossing #1
    assert [path(0.12), path(0.15), path(0.12)] == [False] * 3          # holding in warn: no re-page
    assert len(s.calls) == 1 and s.calls[0][2] == 0                     # normal priority
    assert path(0.08) is False and len(s.calls) == 1                    # falling is silent
    assert path(0.11) is True and len(s.calls) == 2                     # crossing #2
    assert path(0.21) is False and len(s.calls) == 2                    # trip is paged by the kill-rule page
    assert path(0.12) is False and len(s.calls) == 2                    # tripped → warn is downward
    assert json.loads(p.read_text()) == {"level": "warn"}


def test_hysteresis_drift_around_threshold_pages_once(tmp_path):
    p, s = tmp_path / "w.json", _Sender()
    path = lambda d: dw.page_on_upward_crossing(d, 0.20, p, s)  # noqa: E731
    assert path(0.101) is True and len(s.calls) == 1
    for d in (0.099, 0.101, 0.099, 0.101, 0.0905, 0.102):                # 9.9 <-> 10.1 drift, never below 9%
        assert path(d) is False
    assert len(s.calls) == 1 and json.loads(p.read_text()) == {"level": "warn"}
    assert path(0.088) is False and json.loads(p.read_text()) == {"level": "ok"}  # below ~9% → re-armed
    assert path(0.101) is True and len(s.calls) == 2                     # a genuine fresh climb pages again


def test_hysteresis_holds_tripped_in_band(tmp_path):
    p, s = tmp_path / "w.json", _Sender()
    assert dw.page_on_upward_crossing(0.21, 0.20, p, s) is False         # ok → tripped: kill page's job
    assert dw.page_on_upward_crossing(0.095, 0.20, p, s) is False        # 9–10% band: stays latched
    assert dw.page_on_upward_crossing(0.11, 0.20, p, s) is False and not s.calls


def test_restart_does_not_repage_but_undelivered_page_retries(tmp_path):
    p = tmp_path / "w.json"
    down = _Sender(ok=False)
    assert dw.page_on_upward_crossing(0.12, 0.20, p, down) is False     # Pushover down / no creds
    assert dw.page_on_upward_crossing(0.12, 0.20, p, down) is False and len(down.calls) == 2  # stays armed
    up = _Sender()
    assert dw.page_on_upward_crossing(0.12, 0.20, p, up) is True and len(up.calls) == 1
    assert dw.page_on_upward_crossing(0.12, 0.20, p, up) is False and len(up.calls) == 1  # persisted → no repeat


def test_paging_failure_never_raises(tmp_path):
    def boom(*a, **k):
        raise RuntimeError("pushover exploded")

    assert dw.page_on_upward_crossing(0.12, 0.20, tmp_path / "w.json", boom) is False
    (tmp_path / "bad.json").write_text("{not json")
    assert dw.page_on_upward_crossing(0.12, 0.20, tmp_path / "bad.json", _Sender()) is True  # corrupt → ok


# ── T4 condition 5 ──────────────────────────────────────────────────────────────────────────────
def test_t4_condition_5_says_manual_not_hardcoded_in_progress(convexity_db):
    c5 = next(c for c in dd.t4_scoreboard(convexity_db, CONFIG)["conditions"] if c["id"] == 5)
    assert c5["verdict"] is None and c5["checkable"] is False and c5["manual"] is True
    assert c5["detail"].startswith("manual")
