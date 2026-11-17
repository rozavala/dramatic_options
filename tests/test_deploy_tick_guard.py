"""#513: deploy.sh's tick-collision guard reads systemd, not a hardcoded schedule.

The guard (2026-07-04) hardcoded the L1/L2 ticks in summer-time UTC (13:00-20:30 + the 19:45 L1). After DST ended on
2026-11-01 the timers fire an hour later in UTC, so it guarded none of the 20:45 L1, the 21:00/21:30 L2 or the 21:10
post-L1: a merge at ~20:47 UTC deployed into a running L1. These tests run the real ``wait_clear_of_ticks`` text with
fake ``systemctl`` / ``date`` / ``sleep`` and the real systemd timestamp format."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime

from tests.test_systemd_units import DEPLOY, _deploy_function

TIMERS = ("dramatic-options-l1.timer", "dramatic-options-l2.timer", "dramatic-options-post-l1.timer")
SERVICES = ("dramatic-options-l1.service", "dramatic-options-l2.service", "dramatic-options-post-l1.service")


def _epoch(s: str) -> int:
    return int(datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC).timestamp())


def _unix(v: str) -> str:
    """What ``systemctl show --timestamp=unix`` prints: ``@<epoch>``; empty / ``n/a`` pass through (inert timers)."""
    if v in ("", "n/a") or v.startswith("@") or v == "FAIL":
        return v
    return "@" + str(_epoch(v.removeprefix("Tue ").removesuffix(" UTC")))


def _run(*, now: str, next_elapse: dict[str, str], active_until_sleep: dict[str, int] | None = None,
         always_active: str | None = None) -> tuple[str, int]:
    """Run the real guard. ``active_until_sleep[unit] = n``: the unit reports active until n sleeps have happened.
    Each fake sleep advances the fake clock by 45 s. Returns (stdout, sleeps)."""
    active_until_sleep = active_until_sleep or {}
    nexts = "\n".join(f'    {t}) echo "{_unix(v)}" ;;' for t, v in next_elapse.items())
    actives = "\n".join(f'    {u}) [ "$SLEEPS" -lt {n} ] && {{ echo active; return 0; }} ;;'
                        for u, n in active_until_sleep.items())
    always = f'    {always_active}) echo activating; return 0 ;;' if always_active else ""
    script = f"""
set -e
SLEEPS=0
NOW={_epoch(now)}
TIMERS=({" ".join(TIMERS)})
SERVICES=({" ".join(SERVICES)})
sleep() {{ SLEEPS=$((SLEEPS+1)); NOW=$((NOW+45)); }}
date() {{ if [ "$1" = "+%s" ]; then echo "$NOW"; else command date "$@"; fi; }}
systemctl() {{
  if [ "$1" = is-active ]; then
    case "$2" in
{actives}
{always}
    esac
    echo inactive; return 3
  fi
  if [ "$1" = show ]; then
    case "$6" in
{nexts}
      *) echo "" ;;
    esac | {{ read -r out; [ "$out" = FAIL ] && return 1; echo "$out"; }}
  fi
}}
""" + _deploy_function("wait_clear_of_ticks") + 'wait_clear_of_ticks\necho "SLEEPS=$SLEEPS"\n'
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    sleeps = int(out.stdout.strip().rsplit("SLEEPS=", 1)[1])
    return out.stdout, sleeps


def test_the_winter_l1_is_guarded():
    # 20:44:30 UTC on an EST weekday: the 20:45 L1 is 30 s away. The old guard returned at once (it checked 19:45).
    out, sleeps = _run(now="2026-11-17 20:44:30",
                       next_elapse={"dramatic-options-l1.timer": "Tue 2026-11-17 20:45:00 UTC",
                                    "dramatic-options-post-l1.timer": "Tue 2026-11-17 21:10:00 UTC"})
    assert "dramatic-options-l1.timer fires at @" in out
    assert sleeps == 3        # 20:44:30 → 20:46:45: the tick is held through its 60 s dispatch allowance (AccuracySec)


def test_a_running_l1_holds_the_deploy_until_it_exits():
    # 20:47 UTC: the L1 is mid-council (active). The old guard let this deploy through.
    out, sleeps = _run(now="2026-11-17 20:47:00",
                       next_elapse={"dramatic-options-post-l1.timer": "Tue 2026-11-17 21:10:00 UTC"},
                       active_until_sleep={"dramatic-options-l1.service": 3})
    assert "dramatic-options-l1.service is running" in out and sleeps == 3


def test_the_post_l1_and_the_late_l2_ticks_are_guarded():
    out, _ = _run(now="2026-11-17 21:09:30", next_elapse={"dramatic-options-post-l1.timer": "Tue 2026-11-17 21:10:00 UTC"})
    assert "dramatic-options-post-l1.timer fires at @" in out
    out, _ = _run(now="2026-11-17 21:29:40", next_elapse={"dramatic-options-l2.timer": "Tue 2026-11-17 21:30:00 UTC"})
    assert "dramatic-options-l2.timer fires at @" in out


def test_clear_when_nothing_runs_and_no_timer_is_near_or_scheduled():
    # far-off ticks, plus an inert env's empty / n/a values (PROD: timers disabled)
    out, sleeps = _run(now="2026-11-17 03:00:00",
                       next_elapse={"dramatic-options-l1.timer": "Tue 2026-11-17 20:45:00 UTC",
                                    "dramatic-options-l2.timer": "n/a", "dramatic-options-post-l1.timer": ""})
    assert sleeps == 0 and "waiting" not in out


def test_the_wait_is_bounded():
    _, sleeps = _run(now="2026-11-17 20:47:00", next_elapse={}, always_active="dramatic-options-l1.service")
    assert sleeps == 24       # ~18 min, then the deploy proceeds regardless


def test_no_hardcoded_schedule_remains():
    fn = _deploy_function("wait_clear_of_ticks")
    assert "3600" not in fn and "10#$h" not in fn and "19:45" not in fn
    assert '"${SERVICES[@]}"' in fn and '"${TIMERS[@]}"' in fn
    text = DEPLOY.read_text()
    assert text.index("SERVICES=(") < text.index("\nwait_clear_of_ticks\n")   # the arrays exist when the guard runs


def test_a_due_but_undispatched_tick_still_holds_the_deploy():
    # #516 review: systemd may dispatch up to AccuracySec (1 min) after the scheduled instant; 30 s past 20:45 with the
    # L1 not yet active is still dangerous.
    out, sleeps = _run(now="2026-11-17 20:45:30", next_elapse={"dramatic-options-l1.timer": "Tue 2026-11-17 20:45:00 UTC"})
    assert "dramatic-options-l1.timer fires at @" in out and sleeps == 1


def test_a_failed_timer_read_is_reported_not_a_silent_abort():
    # set -e: a non-zero `systemctl show` used to abort the whole deploy with no message (#516 review).
    out, sleeps = _run(now="2026-11-17 03:00:00", next_elapse={"dramatic-options-l1.timer": "FAIL"})
    assert "could not read dramatic-options-l1.timer" in out and sleeps == 0
