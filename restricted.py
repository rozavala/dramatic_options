"""Restricted-list enforcement (``records/2026-07-14_restricted_list_RATIFIED.md``) — fail-CLOSED.

The rule is person-anchored and bound at ratification (2026-07-15): any name where the operator
has a personal relationship with an insider is permanently excluded from EVERY path — register
admission, scan baskets, ``themes.json``, probe files, forward-catalyst pins, and all books
including the null books (a restricted name printing a 10× in a shadow book is a temptation
generator with no offsetting informational value). This module is the defense-in-depth code
layer under that already-effective rule.

**The repo file carries no relationship data.** ``restricted.json`` holds opaque entry IDs +
derived ticker arrays ONLY (e.g. ``{"id": "R-001", "tickers": ["LIFE"]}``) — the ID→person
mapping, relationship prose, and review cadence live at the governance layer (the records
file), never in infrastructure. Enforcement needs only tickers to fail closed.

**Fail-closed semantics:** the file ships in-repo WITH this enforcement PR, so an absent file
is a DEFECT (deleted/unreadable checkout), not a pre-enforcement state — absent OR malformed
both raise :class:`RestrictedListError` (a missing list blocks admission acts, never silently
passes). The parse semantics are aligned byte-for-byte with ``survivor_cards.load_restricted``,
which keeps its absent-TOLERANT tuple variant only because it predates the file shipping (its
WARNING note documents exactly that staging window).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger("restricted")

# Repo root (this module sits there) — cwd-independent, so systemd units / tests / scripts all
# resolve the same shipped file.
DEFAULT_PATH = Path(__file__).resolve().parent / "restricted.json"

RECORD = "records/2026-07-14_restricted_list_RATIFIED.md"


class RestrictedListError(RuntimeError):
    """``restricted.json`` is absent OR unreadable/malformed → the caller HALTS (fail-closed:
    a broken restricted list must never be mistaken for an empty one — the enforcement plan in
    ``records/2026-07-14_restricted_list_RATIFIED.md``; a trade cycle erroring is the correct
    outcome)."""


def load_restricted(path: str | Path | None = None) -> frozenset[str]:
    """Load the repo-root ``restricted.json`` → the derived ticker set, UPPERCASED.

    Absent OR malformed → :class:`RestrictedListError` (fail-closed — the file ships in-repo,
    so absence is a defect, not a state). Accepts either a bare list of entries or
    ``{"entries": [...]}``; every entry must carry a ``tickers`` array of non-empty strings
    (the ``survivor_cards.load_restricted`` parse semantics, aligned)."""
    p = Path(path) if path is not None else DEFAULT_PATH
    if not p.exists():
        raise RestrictedListError(
            f"restricted.json not found at {p} — HALTING, fail-closed (the file ships in-repo; "
            f"absence is a defect, never an empty list — {RECORD})"
        )
    try:
        raw = json.loads(p.read_text())
        entries = raw.get("entries") if isinstance(raw, dict) else raw
        if not isinstance(entries, list):
            raise ValueError("expected a list of entries (or {'entries': [...]})")
        tickers: set[str] = set()
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("tickers"), list):
                raise ValueError(f"entry missing a 'tickers' array: {entry!r}")
            for t in entry["tickers"]:
                if not isinstance(t, str) or not t.strip():
                    raise ValueError(f"non-string/empty ticker in entry {entry.get('id')!r}")
                tickers.add(t.strip().upper())
        return frozenset(tickers)
    except Exception as e:
        raise RestrictedListError(
            f"restricted.json exists but is unreadable/malformed — HALTING, fail-closed "
            f"(a broken restricted list is never an empty one — {RECORD}): "
            f"{type(e).__name__}: {e}"
        ) from e


def is_restricted(symbol: str, restricted: frozenset[str]) -> bool:
    """Case-insensitive membership: is ``symbol`` on the restricted list?"""
    return str(symbol).strip().upper() in restricted
