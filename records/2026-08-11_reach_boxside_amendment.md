# Reach-channels charter amendment — Sunday digest+cards move box-side (2026-08-11)

**Operator decision (TRUE form):** presented with the miss record and two options ("amend:
box-side + review" vs "keep session-run + Monday repair"), the operator chose **"Amend:
box-side + review"** (2026-08-11, structured ask; recommended option).

## Why (the miss record)

The ratified charter (records/2026-07-14_reach_channels_charter_RATIFIED.md) pinned cards as
operator-session acts, "NEVER systemd, unless the operator amends." Three Sunday session-side
misses since: **07-19** (no session awake; repaired Monday), **08-04** (the grading cron's
silent 7-day expiry — adjacent class), **08-09** (wakeup fired into an idle session; repaired
Monday, W32 has no file by label as a result). The systemd half (L0) ran clean every time.
Session-bound automation decays silently; production of the weekly record should not depend on
a session being awake.

## The amendment

- **Production moves to `dramatic-options-reach.{service,timer}`** (Sun 09:40 ET, after the
  08:00 ET L0): `digest_weekly.py` then `survivor_cards_run.py --draft`, sequential, oneshot,
  OnFailure→Pushover, TimeoutStartSec=900, keys via the standard EnvironmentFile.
- **The session/operator layer becomes the REVIEW layer:** reads the output, re-screens any
  near-survivor in-window (Sunday cards stay PROVISIONAL by the weekday rule — unchanged),
  commits the records to the repo SAME DAY (an uncommitted digest is exposed to the next
  deploy's `git clean -fd`), and delivers the graded read + labeled signals brief.
- **The judgment boundary is unchanged:** the harness still cannot rank or judge (schema
  guard-tested); the four-axis screen is deterministic; Stage-B drafting stays bounded
  (kill-before-spend, $0.50/run cap). What moved is *scheduling*, not judgment.
- Timer `Persistent=false` on purpose: a Monday catch-up would stamp the new ISO week (the
  2026-07-20 mislabel class); a missed box-Sunday falls to the review layer instead.
- PROD: installed-but-disabled (the standard FORWARD_ENABLED arming), like every timer.

## Activation

Merging this PR auto-arms the timer on DEV (the deploy.sh TIMERS-array behavior, known since
2026-06-03) — first fire **Sun 2026-08-16 09:40 ET (13:40 UTC)**. The 08-16 session wakeup is
repointed from "produce" to "review".
