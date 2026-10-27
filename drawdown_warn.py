"""Display-only book-drawdown WARN tier (issue #355).

The kill rule (``paper_loop.kill_rule_status``, ``kill_rule.book_drawdown_halt`` = 20%) is the ONLY thing that
halts entries and it is NOT touched here. This module adds a purely informational tier below it so the dashboard
does not read "inside frame" right up to the halt:

  • ``drawdown_level`` — ``ok`` / ``warn`` (≥ ``WARN_FRACTION``) / ``tripped`` (≥ the halt, the SAME ``>=`` the kill
    rule uses). It is derived from the drawdown + halt the kill rule already computed; it never feeds back.
  • ``page_on_upward_crossing`` — one normal-priority (0) Pushover each time the level rises ``ok`` → ``warn``. The
    last-seen level is remembered in a tiny sidecar JSON next to the DB (no schema change), so a restart or a
    steady 12% never re-pages, and an UNDELIVERED page stays armed (retried next cycle). Hysteresis: after a
    page the alert re-arms only once drawdown falls below ``REARM_RATIO`` × the warn level (~9%), so a book
    drifting 9.9% ↔ 10.1% pages once, not on every rise back over 10%. A trip is
    already paged (priority 1) by the orchestrator's kill-rule page, so a jump straight to ``tripped`` is not
    double-paged here. Best-effort: never raises, never blocks a cycle.

Where it runs: ``page_on_upward_crossing`` has no caller in this PR (the orchestrator hook is a separate, held PR).
When wired it runs ONLY in L1 (the once-a-day 15:45 ET non-monitor cycle) — never in the 30-minute L2
``--monitor`` runs that refresh the marks — so a crossing can page up to a trading day late, and never on a day L1
doesn't run (nor on PROD with the timers off). ``drawdown_level`` is what the dashboard shows, independent of paging.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path

log = logging.getLogger("drawdown_warn")

WARN_FRACTION = 0.10  # display-only; deliberately NOT in config.json's kill_rule block (that block is frozen)
REARM_RATIO = 0.9  # re-arm below warn × this (10% → 9%); a dip that stays in the 9–10% band does not re-arm
_RANK = {"ok": 0, "warn": 1, "tripped": 2}


def drawdown_level(book_drawdown: float, halt: float, warn: float = WARN_FRACTION) -> str:
    """``tripped`` mirrors ``kill_rule_status`` (``dd >= halt``); ``warn`` needs ``warn <= dd < halt``. A warn
    threshold at/above the halt is meaningless and is ignored (ok → tripped directly)."""
    if book_drawdown >= halt:
        return "tripped"
    if warn < halt and book_drawdown >= warn:
        return "warn"
    return "ok"


def _read_last(path: Path) -> str:
    try:
        last = json.loads(path.read_text()).get("level")
        return last if last in _RANK else "ok"
    except (OSError, ValueError, AttributeError):
        return "ok"


def page_on_upward_crossing(
    book_drawdown: float, halt: float, state_path: str | Path, send: Callable[..., bool],
    warn: float = WARN_FRACTION,
) -> bool:
    """Page once when the level climbs ``ok`` → ``warn``; record the level either way. Returns True iff paged.
    Back to ``ok`` is recorded only below ``warn × REARM_RATIO`` (hysteresis); in the band between, the
    remembered level is held so the next climb over ``warn`` does not page again."""
    try:
        path = Path(state_path)
        level = drawdown_level(book_drawdown, halt, warn)
        last = _read_last(path)
        if level == "ok" and last != "ok" and book_drawdown >= warn * REARM_RATIO:
            return False  # inside the hysteresis band: stay latched (no re-arm, nothing to record)
        paged = False
        if level == "warn" and last == "ok":
            paged = bool(send(
                "Book drawdown warning",
                f"Book drawdown {book_drawdown:.1%} crossed the {warn:.0%} warn level "
                f"(display-only; the kill rule halts new entries at {halt:.0%}).",
                priority=0,
            ))
            if not paged:
                return False  # undelivered (no creds / transient) → stay armed and retry next cycle
        if level != last:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"level": level}))
        return paged
    except Exception as e:  # noqa: BLE001 — paging is best-effort, never fatal to a cycle
        log.warning("drawdown warn page failed (non-fatal): %s", e)
        return False
