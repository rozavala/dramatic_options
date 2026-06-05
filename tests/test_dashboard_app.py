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
    assert len(at.tabs) >= 1  # the A–G tabs rendered


def test_dashboard_missing_db_is_fatal_soft(monkeypatch, tmp_path):
    monkeypatch.setenv("DRAMATIC_DB", str(tmp_path / "nope.db"))  # does not exist
    at = AppTest.from_file(_APP, default_timeout=60).run()
    assert not at.exception  # no crash
    assert any("no database" in e.value for e in at.error)  # the fail-soft fatal message rendered
