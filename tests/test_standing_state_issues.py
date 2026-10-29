"""#371: the read-only STANDING_STATE "Open issues" drift check used by the scheduled reviews."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("ssi", ROOT / "scripts/ops/standing_state_issues.py")
ssi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ssi)

DOC = """## Board & book
- Book: real 1.
- Open issues: 3, display (filed 2026-10-27): #351 "why no entry" per name · #353 cached `/api/status` (PR #361)
  · #357 `GET /api/hub`. W43's #340–#343 are fixed (#344–#347).
- NVDA canary 1.05.
"""


def test_in_sync_is_ok_and_ranges_count_as_mentioned():
    d = ssi.diff(DOC, {351, 353, 357})
    assert d["ok"] and d["stated"] == 3 and d["unlisted_open"] == []
    assert 342 in d["mentioned_not_open"] and 361 in d["mentioned_not_open"]   # info only, never an error


def test_an_open_issue_the_bullet_never_mentions_is_drift():
    d = ssi.diff(DOC, {351, 353, 357, 371})
    assert not d["ok"] and d["unlisted_open"] == [371]


def test_a_wrong_count_is_drift_even_when_every_number_is_mentioned():
    d = ssi.diff(DOC, {351, 353})
    assert not d["ok"] and (d["stated"], d["actual"]) == (3, 2)


def test_the_bullet_stops_at_the_next_bullet_and_is_found_in_the_real_file():
    assert "NVDA" not in ssi.open_issues_bullet(DOC)
    assert ssi.open_issues_bullet((ROOT / "records/STANDING_STATE.md").read_text()) is not None


def test_missing_bullet_is_reported_not_guessed():
    assert ssi.diff("# nothing here\n", {1}) == {"ok": False, "error": "no '- Open issues:' bullet in STANDING_STATE"}
