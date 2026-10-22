"""The unattended scheduled runs (scripts/ops/scheduled_review.sh) — static guards on the safety properties.

Pins: the script parses; both jobs deny merges and other PR/issue writes; the grade additionally denies commits,
pushes and PR creation; the prompts carry the HEADLINE contract and read expectations from the record rather than
hard-coding dated stamps (a hard-coded frame stamp went stale twice in October 2026).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "ops" / "scheduled_review.sh"
PROMPTS = REPO / "scripts" / "ops" / "prompts"


def test_script_parses_and_is_executable():
    assert subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True).returncode == 0
    assert SCRIPT.stat().st_mode & 0o111


def test_both_jobs_deny_merges_and_issue_writes():
    text = SCRIPT.read_text()
    base = text[text.index("DENY=("):text.index("if [ \"$JOB\" = grade ]")]
    for pat in ("gh pr merge", "gh pr close", "gh issue", "gh api -X", "git push --force", "sudo",
                "systemctl restart", "-m orchestrator"):
        assert pat in base, pat


def test_grade_is_read_only():
    text = SCRIPT.read_text()
    grade = text[text.index("if [ \"$JOB\" = grade ]"):text.index("else\n  BUDGET=")]
    for pat in ("git commit", "git push", "gh pr create", "gh pr comment", "gh pr ready"):
        assert pat in grade, pat


def test_spend_cap_and_lock_present():
    text = SCRIPT.read_text()
    assert "--max-budget-usd" in text and "flock -n" in text and "--permission-mode auto" in text


def test_prompts_carry_the_headline_contract_and_no_dated_stamps():
    for name in ("nightly_grade.md", "sunday_review.md"):
        body = (PROMPTS / name).read_text()
        assert "HEADLINE:" in body, name
        assert not re.search(r"frame-[0-9a-f]{12}", body), f"{name}: hard-coded frame stamp"
        assert "STANDING_STATE" in body and "newest" in body.lower(), name
    assert "may NOT merge" in (PROMPTS / "sunday_review.md").read_text()
    assert "READ-ONLY" in (PROMPTS / "nightly_grade.md").read_text()
