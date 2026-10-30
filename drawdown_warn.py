"""Display-only book-drawdown WARN tier (issue #355).

The kill rule (``paper_loop.kill_rule_status``, ``kill_rule.book_drawdown_halt`` = 20%) is the ONLY thing that
halts entries and it is NOT touched here. This module adds a purely informational tier below it so the dashboard
does not read "inside frame" right up to the halt:

  • ``drawdown_level`` — ``ok`` / ``warn`` (≥ ``WARN_FRACTION``) / ``tripped`` (≥ the halt, the SAME ``>=`` the kill
    rule uses). It is derived from the drawdown + halt the kill rule already computed; it never feeds back.
  • ``page_on_upward_crossing`` — one Pushover each time the level rises: ``ok`` → ``warn`` at normal priority (0),
    and into ``tripped`` at priority 1 (#370: the kill rule's halt, paged by the first tick that sees it, L2
    included, instead of waiting for the next L1). The last-seen level is remembered in a tiny sidecar JSON next
    to the DB (no schema change), so a restart or a steady 12% never re-pages, and an UNDELIVERED page stays
    armed (retried next cycle). Hysteresis: a fall is recorded only below ``REARM_RATIO`` × the threshold it
    falls through (~18% for a trip, ~9% for the warn), so a book drifting 9.9% ↔ 10.1% or 19.9% ↔ 20.1% pages
    once, not on every rise back over the line. Best-effort: never raises, never blocks a cycle.

Where it runs (#366, operator 2026-10-27 "L1 + L2"): the orchestrator evaluates it once per cycle right after the
monitor pass, so in L1 and in every 30-minute L2 ``--monitor`` tick; a crossing pages within one tick. Never under
``--demo``, never on PROD with the timers off. ``drawdown_level`` is what the dashboard shows, independent of paging.

Latch writes are atomic (temp file + ``os.replace``, which needs only the directory writable, so a read-only latch
file left by a manual run doesn't wedge it) and happen BEFORE the page: if the latch can't be written, nothing is
paged (a WARNING is logged and the dashboard tier still shows ``warn``). Paging first and failing the write would
re-page on every 30-minute tick. An undelivered page rolls the latch back, so the next cycle retries.
"""

from __future__ import annotations

import json
import logging
import os
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


def _write_level(path: Path, level: str) -> None:
    """Atomically record the level: a temp file then ``os.replace`` (only the directory must be writable)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps({"level": level}))
    os.replace(tmp, path)


def _held_level(book_drawdown: float, last: str, halt: float, warn: float) -> str:
    """The level to remember: the current level, except that a fall re-arms only below ``REARM_RATIO`` × the
    threshold it falls through. A trip is held down to ~18%; a warn (or a trip falling that far) down to ~9%."""
    level = drawdown_level(book_drawdown, halt, warn)
    if last == "tripped" and level != "tripped" and book_drawdown >= halt * REARM_RATIO:
        return "tripped"
    if last != "ok" and level == "ok" and warn < halt and book_drawdown >= warn * REARM_RATIO:
        return "warn"
    return level


def page_on_upward_crossing(
    book_drawdown: float, halt: float, state_path: str | Path, send: Callable[..., bool],
    warn: float = WARN_FRACTION,
) -> bool:
    """Page once per upward crossing: ``ok`` → ``warn`` (priority 0) and ``ok``/``warn`` → ``tripped`` (priority 1,
    #370). Record the level either way; falls are silent and held by the hysteresis in ``_held_level``. Returns
    True iff paged."""
    try:
        path = Path(state_path)
        last = _read_last(path)
        level = _held_level(book_drawdown, last, halt, warn)
        if level == last:
            return False
        try:
            _write_level(path, level)   # record FIRST: an unwritable latch must never become a page every tick
        except OSError as e:
            log.warning("drawdown warn latch unwritable (%s) — not paging, so it can't repeat every tick: %s",
                        path, e)
            return False
        if _RANK[level] <= _RANK[last]:
            return False
        if level == "tripped":
            paged = bool(send(
                "Kill rule tripped — new entries halted",
                f"Book drawdown {book_drawdown:.1%} reached the {halt:.0%} kill rule: new entries are halted while "
                f"it stays there (the monitor and exits keep running).",
                priority=1,
            ))
        else:
            paged = bool(send(
                "Book drawdown warning",
                f"Book drawdown {book_drawdown:.1%} crossed the {warn:.0%} warn level "
                f"(display-only; the kill rule halts new entries at {halt:.0%}).",
                priority=0,
            ))
        if not paged:   # undelivered (no creds / transient) → roll back so the next cycle retries
            try:
                _write_level(path, last)
            except OSError:
                pass    # the retry is lost; the dashboard tier still shows the level
        return paged
    except Exception as e:  # noqa: BLE001 — paging is best-effort, never fatal to a cycle
        log.warning("drawdown warn page failed (non-fatal): %s", e)
        return False
