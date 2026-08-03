"""Read-only data layer for the /api/reach endpoint — the weekly reach documents.

Serves the NEWEST weekly survivor-cards document (``records/cards/<YYYY>-W<ww>.md``, written
by ``scripts/survivor_cards_run.py``) and the NEWEST weekly digest (``records/digests/…``,
written by ``scripts/digest_weekly.py``) to the Reach panel. RENDER-ONLY by construction:
repo-relative file reads, no DB, no fetch, no keys, no write path anywhere — picks happen in
the operator's session, never here (charter: ``records/2026-07-14_reach_channels_charter_
RATIFIED.md``). Fail-soft: an absent/unreadable document is ``{available: false, reason}``,
never an HTTP error — the panel renders an explicit absent-state.

"Newest" = the lexicographically-last ``<YYYY>-W<ww>.md`` stem, the same rule the card runner
uses to pick its default digest (``scripts/survivor_cards_run.py:_find_digest``) — ISO week
stamps sort chronologically. No ranking/reordering of content: the raw markdown ships verbatim.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

_WEEK_STEM_RE = re.compile(r"^\d{4}-W\d{2}$")
# Both weekly writers stamp "- generated: <iso>" in the header — more honest than mtime
# (a git checkout / rsync resets mtime to deploy time, not generation time).
_GENERATED_RE = re.compile(r"^- generated: (\S+)", re.MULTILINE)


def newest_week_doc(dir_path: Path) -> dict:
    """The newest weekly markdown document under ``dir_path``, fail-soft.

    Returns ``{available: True, filename, week, content, mtime, generated}`` or
    ``{available: False, reason}`` — never raises.
    """
    try:
        if not dir_path.is_dir():
            return {"available": False,
                    "reason": f"{dir_path.name}/ not found — no weekly documents yet"}
        docs = sorted(p for p in dir_path.glob("*-W*.md") if _WEEK_STEM_RE.match(p.stem))
        if not docs:
            return {"available": False,
                    "reason": f"no <YYYY>-W<ww>.md documents in {dir_path.name}/ yet"}
        doc = docs[-1]
        content = doc.read_text()
        mtime = datetime.fromtimestamp(doc.stat().st_mtime, tz=UTC)
        m = _GENERATED_RE.search(content)
        return {
            "available": True,
            "filename": doc.name,
            "week": doc.stem,
            "content": content,
            "mtime": mtime.isoformat(timespec="seconds"),
            "generated": m.group(1) if m else None,
        }
    except Exception as e:  # noqa: BLE001 — fail-soft is the endpoint's contract
        return {"available": False, "reason": f"{type(e).__name__}: {e}"}


def build_reach(records_dir: Path) -> dict:
    """The /api/reach payload: newest cards + newest digest, each independently fail-soft."""
    return {
        "cards": newest_week_doc(records_dir / "cards"),
        "digest": newest_week_doc(records_dir / "digests"),
    }
