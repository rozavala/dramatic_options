"""Pushover notifier (T2.5 PR2) — best-effort operational paging.

Two call paths, one sender:

  • **In-app** (orchestrator): the three soft, exit-0 conditions that systemd ``OnFailure``
    can NEVER catch because the process exits cleanly — a kill-rule trip, a fail-closed
    council, a cost-cap trip. ``send()`` is imported and called directly.
  • **systemd ``OnFailure``** (the ``dramatic-options-notify@.service`` template): a hard,
    NON-zero exit (no creds, broker unreachable, a hang killed by ``TimeoutStartSec``). The
    unit runs ``python notify.py --systemd-failure <failed-unit>``.

**Guarantees (load-bearing):**
  • ``send()`` NEVER raises — a paging failure must never break a trade cycle.
  • No ``PUSHOVER_API_TOKEN`` / ``PUSHOVER_USER_KEY`` → it **no-ops** (returns False, logs a
    debug line). So the offline demo, the tests, and CI need no keys and no network.

Keys are read from the environment (``config_loader`` calls ``load_dotenv`` for the in-app
path; the systemd unit injects them via ``EnvironmentFile``). A defensive ``load_dotenv`` is
attempted so a bare ``python notify.py`` from a checkout also works.
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys

log = logging.getLogger("notify")

PUSHOVER_URL = "https://api.pushover.net/1/messages.json"
_TITLE_PREFIX = "Dramatic Options"


def _load_env() -> None:
    """Best-effort .env load for the standalone CLI path; never fatal."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:  # noqa: BLE001 — dotenv missing/unreadable is fine; env may already be set
        pass


def send(title: str, message: str, *, priority: int = 0) -> bool:
    """Send a Pushover push. Returns True on a 2xx, False otherwise. NEVER raises.

    No-ops (returns False) when the Pushover credentials are unset — this is the normal state
    for demo/tests/CI. ``priority`` follows the Pushover scale (-2..2); we use 0 for normal and
    1 for the kill-rule trip (bypasses quiet hours).
    """
    token = os.getenv("PUSHOVER_API_TOKEN")
    user = os.getenv("PUSHOVER_USER_KEY")
    if not token or not user:
        log.debug("notify: PUSHOVER_* unset — skipping push (%s)", title)
        return False

    full_title = f"{_TITLE_PREFIX} — {title}" if title else _TITLE_PREFIX
    # Pushover caps the body at 1024 chars.
    body = (message or "")[:1024]
    try:
        import requests

        resp = requests.post(
            PUSHOVER_URL,
            data={
                "token": token,
                "user": user,
                "title": full_title[:250],
                "message": body or "(no message)",
                "priority": int(priority),
            },
            timeout=10,
        )
        if resp.status_code // 100 == 2:
            return True
        log.warning("notify: Pushover returned %s — %s", resp.status_code, resp.text[:200])
        return False
    except Exception as e:  # noqa: BLE001 — paging is best-effort, never fatal to the caller
        log.warning("notify: push failed (%s): %s", title, e)
        return False


def _journal_tail(unit: str, lines: int = 20) -> str:
    """Best-effort recent journal for a failed unit (empty string on any error)."""
    try:
        out = subprocess.run(
            ["journalctl", "-u", unit, "-n", str(lines), "--no-pager", "-o", "cat"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        return (out.stdout or "").strip()
    except Exception:  # noqa: BLE001 — journal may be unreadable; the title alone still pages
        return ""


def main(argv: list[str] | None = None) -> int:
    _load_env()
    parser = argparse.ArgumentParser(description="Pushover notifier (best-effort).")
    parser.add_argument("--systemd-failure", metavar="UNIT",
                        help="Page that the given systemd unit failed (OnFailure target).")
    parser.add_argument("--priority", type=int, default=0, help="Pushover priority (-2..2).")
    parser.add_argument("title", nargs="?", help="Notification title.")
    parser.add_argument("message", nargs="?", default="", help="Notification message.")
    args = parser.parse_args(argv)

    if args.systemd_failure:
        unit = args.systemd_failure
        tail = _journal_tail(unit)
        title = f"UNIT FAILED: {unit}"
        message = f"{unit} entered a failed state on the forward loop host."
        if tail:
            message += f"\n\nrecent log:\n{tail}"
        # A non-zero exit deserves to bypass quiet hours.
        send(title, message, priority=max(args.priority, 1))
        return 0

    if not args.title:
        parser.error("a title is required (or use --systemd-failure UNIT)")
    send(args.title, args.message, priority=args.priority)
    return 0


if __name__ == "__main__":
    sys.exit(main())
