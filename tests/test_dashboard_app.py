"""End-to-end render smoke for the Streamlit shell (`dashboard.py`).

CI runs WITHOUT streamlit (it's in requirements-dashboard.txt, not requirements.txt), so this is gated by
``importorskip`` — CI skips it; a checkout that installed the dashboard deps runs it. The smoke proves the
shell executes top-to-bottom and renders WITHOUT an uncaught exception (fail-soft) over a read-only DB.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit")  # noqa: E402 — gate before importing the streamlit test harness

from streamlit.testing.v1 import AppTest  # noqa: E402

import state  # noqa: E402

_APP = str(Path(__file__).resolve().parent.parent / "dashboard.py")


def test_dashboard_renders_failsoft(convexity_db, monkeypatch):
    db_path = convexity_db.execute("PRAGMA database_list").fetchone()[2]
    state.record_run(convexity_db, mode="PAPER", equity=100000.0)  # a little content so the heartbeat is live
    monkeypatch.setenv("DRAMATIC_DB", db_path)
    monkeypatch.setenv("DRAMATIC_CACHE_DIR", str(Path(db_path).parent / "cache"))  # absent → curation 'accruing'
    at = AppTest.from_file(_APP, default_timeout=60).run()
    assert not at.exception  # empty ElementList = the whole shell rendered fail-soft, no uncaught error
    assert len(at.tabs) >= 7  # the 7 renamed tabs rendered
    assert at.success or at.warning or at.error  # the one-glance status banner always renders a headline


def test_dashboard_renders_with_council_data(convexity_db, monkeypatch):
    # Exercise the NEW render paths end-to-end (council verdict + per-provider + recent-runs strip, the
    # deliberation table, position provenance, the redefined cond-1) with real seeded data — still fail-soft.
    rid = state.record_run(convexity_db, mode="PAPER", equity=100000.0)
    state.update_run_council_health(convexity_db, rid, council_health="ok")
    pid = state.record_council_proposal(convexity_db, run_id=rid, as_of="t", theme="ai_compute", symbol="SMCI",
                                        direction="bearish", conviction="MODERATE", status="proposed")
    for role, prov, stance in (("proposer", "gemini", "bearish"), ("adversary", "xai", "bullish"),
                               ("strategist", "anthropic", "bearish")):
        state.record_agent_output(convexity_db, proposal_id=pid, role=role, provider=prov, model="m",
                                  confidence="MODERATE", stance=stance,
                                  raw={"confidence": "MODERATE", "x": "y"}, cost_usd=0.003)
    convexity_db.commit()
    db_path = convexity_db.execute("PRAGMA database_list").fetchone()[2]
    monkeypatch.setenv("DRAMATIC_DB", db_path)
    monkeypatch.setenv("DRAMATIC_CACHE_DIR", str(Path(db_path).parent / "cache"))
    at = AppTest.from_file(_APP, default_timeout=60).run()
    assert not at.exception
    assert len(at.tabs) >= 7


def test_dashboard_missing_db_is_fatal_soft(monkeypatch, tmp_path):
    monkeypatch.setenv("DRAMATIC_DB", str(tmp_path / "nope.db"))  # does not exist
    at = AppTest.from_file(_APP, default_timeout=60).run()
    assert not at.exception  # no crash
    assert any("no database" in e.value for e in at.error)  # the fail-soft fatal message rendered
