# Skill-Impact Ledger

Audit trail for every rule in `.claude/skills/{triage,ship,handoff}/SKILL.md` that was added for this repo: what
motivated it and whether it earned its place. `/ship` Step 8 appends a row whenever a run merges a skill-rule change;
`/triage` Step 0 reads it back and, once a row's recurrence check is due, records whether the motivating failure
recurred (in a PR or a PR comment, never as an edit on `main`). A rule that recurred twice is a candidate for rewrite
or deletion, not another patch.

The three skills were adapted on 2026-10-27 from the alpha_options and real_options siblings, folding in this repo's
earlier local skills (`review-logs`, `tackle-issues`, `review-prs`, `handoff`). Rules carried over from the siblings
are baseline here, not rows. Rows below are rules added for this repo.

| Date | Skill / step | Rule (short) | Motivating failure (issue/PR) | Commit | Recurrence check due | Outcome |
|---|---|---|---|---|---|---|
| 2026-10-27 | triage Step 2B; ship Step 4 | Fail-soft is not fail-silent: every fail-soft adapter logs its hit count (WARNING at zero) and shows "unknown", never a stand-in; triage checks each returned real data on the latest weekday RTH run | #337 / PR #338: the analyst endpoint 404'd from ~2026-07-10, and sentinel packs showed the marker count as "articles" for three months | (this PR) | 2026-11-10 | pending |
| 2026-10-27 | triage Step 2F; ship Step 4 | Anything that claims to measure "the gate" uses the gate's own path, or a test pins them together | #343 / PR #345: the feasibility probe, the cards and two sweeps skipped the OTM side guard | (this PR) | 2026-11-10 | pending |
| 2026-10-27 | ship Step 4 (PIT and time rules) | Schedule-anchored times compare ET dates or trading days, never seconds or the UTC date; holidays from `nyse_calendar.py` | #342 / PR #346 (TTL decided by start-second jitter); #341 / PR #344 (UTC crontab vs ET timers); #367 / PR #372 | (this PR) | 2026-11-10 | pending |
| 2026-10-27 | ship Step 1 (in-flight check) | Re-check claims, remote branches and open PRs right before starting each issue; claim with a comment, release with the reason | 2026-10-27: an inventory missed three PRs (#359–#361) pushed minutes later by another agent; offered duplicate work | (this PR) | 2026-11-10 | pending |
| 2026-10-27 | triage Op. Constraints; ship Step 6 | No subagent or reviewer finding is posted or filed until the main session verifies it at the cited line | 2026-10-27: a PR #363 reviewer swapped L1 and L2 in its finding; caught before posting | (this PR) | 2026-11-10 | pending |
| 2026-10-27 | ship Step 4 (test rules) | No time-of-day-dependent tests; `dd.safe(f, g(x))` evaluates `g(x)` outside the guard, so pass a lambda; test runs strip the Pushover keys | PR #347 (a test passed at 17:00 UTC and failed at 00:50 UTC); PR #362 review; PR #350 (`conftest.py`) | (this PR) | 2026-11-10 | pending |
| 2026-10-27 | ship Step 7 | Merging needs the operator's explicit word, inside a UTC 02–26 / 32–56 window, after `update-branch` (never on a `main → production` PR); a draft is never merged | 2026-10-27: the auto-mode classifier refused merges on "sure"; PR #356 (update-branch would have written production's merges into main) | (this PR) | 2026-11-10 | pending |
| 2026-10-27 | ship Op. Constraints (record-segmenting) | A change to what the council sees or what a verdict maps to adds a `runs.model_mix` stamp and a STANDING_STATE entry in the same PR | PR #336: the new `quote_filter` stamp would have been reported as unexplained by the nightly grade | (this PR) | 2026-11-10 | pending |
| 2026-10-28 | ship Step 3 (worktree venv) | A worktree links a venv with the dev tools (the interactive worktree's, or a fresh one from requirements-dev.txt), never the live checkout's runtime-only venv | 2026-10-28 `/ship 366`: the worktree linked `$LIVE/venv` as the skill said, and `pytest`/`ruff` were missing | (this PR) | 2026-11-11 | pending |

**Untraced rows: 0.**
