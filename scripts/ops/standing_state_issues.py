#!/usr/bin/env python3
"""READ-ONLY drift check: does records/STANDING_STATE.md's "Open issues" bullet match GitHub's open issues? (#371)

Run by the scheduled reviews (the Sunday review fixes drift in its records PR). Never edits anything. One drift is an
error: an open issue the bullet never mentions. Issues the bullet mentions that are now closed are listed for
information only (the bullet may legitimately cite fixed ones, e.g. "W43's #340–#343 are fixed"). There is no stated
count to keep in step (#446): it forced a records PR for every issue opened or closed and duplicated `gh`.

    scripts/ops/standing_state_issues.py [path/to/STANDING_STATE.md]   # exit 0 = in sync, 1 = drift, 2 = can't read
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

_BULLET = re.compile(r"^- Open issues:")


def open_issues_bullet(text: str) -> str | None:
    """The "- Open issues: …" bullet including its indented continuation lines, or None if absent."""
    lines, out = text.splitlines(), []
    for i, ln in enumerate(lines):
        if _BULLET.match(ln):
            out.append(ln)
            for cont in lines[i + 1:]:
                if not cont.startswith("  ") or cont.lstrip().startswith("- "):
                    break
                out.append(cont)
            return "\n".join(out)
    return None


def diff(text: str, open_now: set[int]) -> dict:
    """Pure: compare the bullet with the set of open issue numbers."""
    bullet = open_issues_bullet(text)
    if bullet is None:
        return {"ok": False, "error": "no '- Open issues:' bullet in STANDING_STATE"}
    mentioned = {int(n) for n in re.findall(r"#(\d+)", bullet)}
    for a, b in re.findall(r"#(\d+)\s*[–-]\s*#?(\d+)", bullet):   # "#340–#343" mentions the whole range
        mentioned |= set(range(int(a), int(b) + 1))
    unlisted = sorted(open_now - mentioned)
    return {"ok": not unlisted, "actual": len(open_now), "unlisted_open": unlisted,
            "mentioned_not_open": sorted(mentioned - open_now)}


def _open_issue_numbers() -> set[int]:
    out = subprocess.run(["gh", "issue", "list", "--state", "open", "--limit", "200", "--json", "number"],
                         capture_output=True, text=True, timeout=30, check=True)
    return {int(i["number"]) for i in json.loads(out.stdout)}


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else Path("records/STANDING_STATE.md")
    try:
        text, open_now = path.read_text(), _open_issue_numbers()
    except Exception as e:  # noqa: BLE001 — a reporting tool: say it couldn't check, never guess
        print(f"standing-state-issues: cannot check ({type(e).__name__}: {e})")
        return 2
    d = diff(text, open_now)
    if d.get("error"):
        print(f"standing-state-issues: DRIFT — {d['error']}")
        return 1
    parts = [f"open {d['actual']}"]
    if d["unlisted_open"]:
        parts.append("open but not listed: " + ", ".join(f"#{n}" for n in d["unlisted_open"]))
    if d["mentioned_not_open"]:
        parts.append("mentioned, not open (info): " + ", ".join(f"#{n}" for n in d["mentioned_not_open"]))
    print(f"standing-state-issues: {'OK' if d['ok'] else 'DRIFT'} — " + " · ".join(parts))
    return 0 if d["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
