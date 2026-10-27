---
name: ship
description: End-to-end issue resolution AND PR review for Dramatic Options in one pass. Validates open issues, checks nobody else is on them, fixes them at the root cause in per-issue worktrees (full-ceremony lane for money-moving or seam-adjacent work, batched sweep lane for small fixes, simplify lane for removing mechanism, protocol lane that drafts dated records instead of code), adversarially reviews every diff (its own and other agents') with fresh-context reviewers, runs one batch merge-result suite, then presents a merge plan for the operator's explicit word and executes it inside a merge window, verifying the deploy. Use when the user asks to ship, tackle issues, fix pending issues, review PRs, or merge what's ready.
argument-hint: [optional: an issue or PR number, OR "sweep" for only the batch-small-fixes lane, OR "review" for only reviewing open PRs, OR a label filter]
---

# Ship Skill — Dramatic Options

One pass, typically after `/triage`: issues → fixes → PRs → review → the operator's merge word → merge, deploy
check and cleanup. Other agents' PRs enter at review; issues enter at in-flight check and validation.

**Issues and PRs are the documentation.** Every PR body lets a future reader reconstruct the root cause, the approach
and what was consciously not done. Every issue close records the outcome.

**Guiding rules.** (1) The system exists to find a real edge without fooling itself: the deterministic gates dispose,
the council only proposes, the council is never backtested, and a fix that quietly changes a frozen number, the
floor, a prompt, a cap or the universe is a defect, not a fix. (2) Prefer deleting mechanism to adding it;
`lane:simplify` is first-class work. (3) Merging to `main` deploys the DEV paper book; merging to `production`
deploys PROD. Never leave `main` red.

## Model & effort

| Work | Model | Effort |
|---|---|---|
| Inventory, dedup tables, worktree setup, suite execution, label mechanics | haiku | low |
| Issue validation (reproduce on main), mutation-check execution | sonnet | medium |
| Fixes — sweep lane | sonnet | medium |
| Fixes — full ceremony, SIMPLIFY consolidation, protocol-record drafting | opus | high |
| Review — non-critical diffs (dashboard, docs, ops) | sonnet | medium |
| Review — safety-critical set, PIT-touching code, anything near a frozen number or the seam | **fable** | **xhigh** |
| Lane assignment, close-vs-fix, verifying reviewer findings, merge plan | main session | — |

## Operating Constraints

- **Safety-critical set** (fable review; a regression test that fails on `main`; fail-closed kept): `broker.py`,
  `monitor.py`, `paper_loop.py`, `convexity_gate.py`, `convexity_sizing.py`, `structure.py`, `clusters.py`,
  `risk.py`, `orchestrator.py`, `state.py`, `restricted.py`, `config_loader.py`, `config.json`, `council/*`,
  `scripts/migrations/*`, `deploy.sh`, `scripts/systemd/*`.
- **PIT / evidence set** (fable review; first question: "can this see the future, or show the council something
  untrue?"): `data/*`, `discovery.py`, `sentinels.py`, `marker_refresh.py`, `council/context.py`,
  `council/filters.py`, `miss_baserate.py`, `shadow_book.py`, `fixed_basket.py`, `shares_basket.py`.
- **Frozen things live in records, not code.** `config.json` `convexity_book` / `convexity_gate` /
  `convexity_exits` / `kill_rule` / clusters, the conviction floor, the council prompts (their hashes are stamped),
  the universe (`universe_register.json`, string-spliced, never `json.dump`), the TTL, every `PREREG_*.md` number. A
  diff that changes one needs the operator's dated word recorded in `records/STANDING_STATE.md` (and the PREREG, if
  any) in the same PR. A **record-segmenting** change (anything that changes what the council sees or what a verdict
  maps to) adds a `runs.model_mix` stamp and a STANDING_STATE entry, or the nightly grade reports the stamp as
  unexplained.
- **Secrets:** `.env` only; never logged, never in a PR body; print key names, never values. The operator's email
  is never sent anywhere by code we write.
- **Paths:** derive `LIVE` (the main worktree: `git worktree list --porcelain | awk '/^worktree/{print $2; exit}'`).
  Never write under it. Worktrees are siblings: `$LIVE-claude-<issue#>`.
- **Tests:** `venv/bin/python -m pytest -q` (the full suite; `dashboard_web/api` is excluded from bare pytest, so
  also `venv/bin/python -m pytest -q dashboard_web/api` for any API change), `venv/bin/ruff check .`, and for UI
  changes `npm ci && npx tsc --noEmit && npx vitest run` in `dashboard_web/ui`. A worktree gets no `.env`; tests run
  with the Pushover keys stripped (`conftest.py`), so a test run can never page.
- **Labels** this skill uses: `lane:profit`, `lane:protocol`, `lane:sweep`, `lane:simplify`, `needs-operator`,
  `needs-triage`, `claude-fix`, `Ready to be merged`. Create one that's missing with `gh label create <name>` before
  first use.

## Step 1: Inventory, and who else is on it

```bash
gh issue list --state open --limit 100 --json number,title,labels,updatedAt,body,comments
gh pr list   --state open --limit 60  --json number,title,headRefName,isDraft,labels,body,createdAt
gh pr list   --state merged --limit 30 --json number,title,mergedAt,body
git ls-remote --heads origin | grep -v 'refs/heads/\(main\|production\)$'
git worktree list
```

`$ARGUMENTS`: a number scopes to that issue or PR; `sweep` runs only the sweep lane; `review` skips to Step 6 for
open PRs; a label filters.

**In-flight check (do it again right before starting each issue; other agents work this repo too).** Skip an issue
that has an open PR naming it (`Closes #N`, branch `…/N-…`), a remote branch for it, a "Claiming — …" comment newer
than its last "Releasing claim" comment, a `claude-fix` / `needs-operator` label, or an assignee note. A branch can
be pushed minutes after you looked: on 2026-10-27 three PRs appeared between one inventory and the next. Claim an
issue with a comment ("Claiming — <who> <UTC time>") before the first edit, and release it with the reason if you
stop.

## Step 2: Validate each issue (THE safety gate)

Re-read the body and comments; **re-run its "Verify it's still live" command** or reproduce on `main` (a failing
test, a read-only DB query, a journald line, a dashboard field). **Re-derive the scope** from how the consuming code
reads its inputs, not from the issue's count. **History check:** the issue's Prior art section, then
`gh issue list --state all --search`, `gh pr list --state all --search`, `git grep -n <component> -- 'PREREG_*.md'
records/`, `records/edge_graveyard.md`, and memory. Confirm a timing or absence symptom on a weekday RTH cycle.

| Outcome | Action |
|---|---|
| Reproduces, cause provable | → Step 3 |
| Gone (a recent commit closed it) | Close with evidence and the commit |
| Never matched the claim (holiday artifact, per-run counter misread) | Close with what you found |
| Duplicate | Close the newer, comment a pointer |
| Real, but every credible fix is more mechanism than its demonstrated cost | Close as complexity-cut, searchable comment |
| Would change a frozen number, floor, prompt, cap, cluster, the universe or a stamp's meaning | → **protocol lane**, never a direct fix |
| Has more than one credible fix and the choice changes behavior | Comment the options with a recommendation, label `needs-operator`, ask |
| Ambiguous | Comment findings, label `needs-triage`, move on |

Paste reproduction evidence verbatim in close comments.

## Step 3: Lane assignment

- **Full ceremony** — the safety-critical or PIT sets, `lane:profit`, any money-moving path, any migration. One
  worktree, one branch, one PR: `git worktree add -b fix/<issue#>-<slug> "$LIVE-claude-<issue#>" origin/main`
  (refuse to clobber an existing path); link the live venv (`ln -s "$LIVE/venv" <worktree>/venv`).
- **Protocol lane** — the fix is a record: draft the STANDING_STATE ruling entry and, where one governs, a dated
  PREREG amendment (what changes, why, the boundary run, the new stamp, what does not change). Present the options
  and get the operator's word **before** the code; the code PR then cites the dated entry.
- **Sweep** — `lane:sweep`: log or page noise, ops hygiene, docstrings, dashboard copy. Batched by topic (branch
  `sweep/<topic>-<date>`, one commit per issue), at most ~6 issues or ~400 lines per batch.
- **Simplify** — takes the lane its blast radius dictates, and carries deadness evidence: `git grep` proving no
  reader, 10 days of journald with zero hits, or the superseding mechanism.
- Cross-dependent issues run serially; the rest in parallel.

## Step 4: Fix at the root cause

Proximate symptom → upstream cause → fix at the cause. Refuse: a `try/except` that swallows a fail-closed path, a
retry around a non-transient failure, a threshold raised to silence a warning, a hardcode around config. **Sibling
callsites:** if the fix mirrors another path (the real book / shadow / 3A / 3B / shares, L1 / L2, DEV / PROD, every
caller of a shared selector), grep the whole scope; the same root cause reachable today is fixed in the same PR.
Where two code paths both claim to be "the gate", make one call the other, or pin them together with a test.

**Anti-complexity rules:** deletion beats guarding; any new state file, config key, guard layer or field needs a
one-sentence *bought outcome* in the PR body; fix the demonstrated failure, not three adjacent hypotheticals.

**Fail-soft is not fail-silent.** An adapter allowed to return nothing must say so: a log line with its hit count
(a WARNING at zero) and an honest "unknown" in anything the council or the dashboard reads, never a stand-in value
(the dead analyst meter showed the marker count as "articles" for three months).

**PIT and time rules:** every read is `as_of`-gated; nothing dated after the decision instant influences it
(lookahead probe: insert a future-dated row, assert no change). Compare schedule-anchored times as ET calendar dates
or trading days, never to the second or by the UTC date (the TTL bug). Use `nyse_calendar.py` for holidays.

**Test rules:** the regression test FAILS on `main` and encodes the mechanism; never stub the unit under test; no
date bombs or time-of-day-dependent tests (a test passed at 17:00 UTC and failed at 00:50 UTC); mock payloads use
the real upstream shape, captured, not invented; `dd.safe(f, g(x))` evaluates `g(x)` outside the guard, so pass a
lambda.

**Commits:** `git add <specific files>`, never `-A`. Message `<scope>: <summary> (#<issue#>)`, a paragraph of *why*,
`Closes #<issue#>`, and the attribution lines the system prompt specifies. One logical change per commit.

**PR body:** Summary · Root cause · What changed (file by file) · **Record** (the PREREG / STANDING_STATE entry
that governs it, the stamp if record-segmenting, or "no frozen thing touched") · Prior art · Conscious deferrals
(with follow-up issue numbers) · Verification stamp (Step 5).

## Step 5: Verify — mutation per fix, one batch suite

1. Merge current `origin/main` into every branch (or rebase a branch nobody else has pulled).
2. **Mutation-check every fix:** revert the fix body, keeping the test → the test must fail naming the defect →
   restore. Mutate behavior and keep the symbol; a collection error is not evidence.
3. Lint parity: `ruff check .` clean on every branch, and `gh pr checks <PR#>` green after the push.
4. **One batch merge-result suite** from the main session: a scratch worktree at `origin/main`, a `git merge-tree
   --write-tree` conflict pre-check, merge all candidates, run the suite (plus `dashboard_web/api` and the UI tests
   when touched). Check `/proc/loadavg` first; the box also runs Real Options and Alpha Options. Red → read the
   exception, bisect by halving, drop the offending branch.
5. **Stamp every PR body:**

```
## Verification stamp
- Suite: <N> passed / <M> skipped / <K> failed — batch run on the merge of [<branches>] with origin/main@<sha>
- Mutation: reverted <what> → <test> failed: "<assertion>"
- Lookahead probe: <test> (PIT-touching diffs only)
```

## Step 6: Adversarial review — fresh context, not the author

Every diff, ours or another agent's, gets a reviewer that did not write it (fable/xhigh for safety-critical, PIT or
frozen-adjacent diffs; else sonnet/medium), working **read-only** in a scratch worktree it removes afterwards. It
gets the diff, the issue, the governing record and this checklist:

- Correctness, regressions, fail-closed kept: the KILL switch checked first, the triple live gate, `DRY_RUN`, the
  never-broker null books, the restricted list, foreign-quantity and shared-account reserve checks.
- **The hard seam:** no LLM output sizes a position, overrides a veto, sets a cap, or picks a cluster.
- **Lookahead** and **evidence honesty:** can a new read see the future, or show the council a value that isn't what
  its label says?
- **Frozen audit:** diff every literal against the governing record; a changed literal without a dated entry fails.
- **Root cause vs symptom**, in one sentence. **Anti-complexity:** net LOC, new config/state, the bought-outcome line.
- **Sibling paths and scope:** does the diff leave a mirror path inconsistent, or touch files its issue didn't name
  (a "display-only" PR editing `orchestrator.py` gets the safety-critical review)?
- **Acceptance criteria:** check each criterion in the issue against the diff (a backend-only PR does not close a
  UI issue).
- **Conflicts:** `gh pr view --json mergeStateStatus` and a scratch merge with main and the other open PRs.

**Verify every reviewer finding yourself before posting it** (read the code at the cited line). Reviewers have
swapped unit names and overstated severities. Post the verified review as a PR comment; findings go back to the
author (us, or the other agent through that comment). Re-review the new head when fixes land: each previously
flagged item resolved, CI green, nothing new slipped in (diff the new commits only).

## Step 7: Merge plan — the operator's explicit word

Present one table and STOP:

```
| PR | Issues | Lane | Safety/PIT? | Record entry | Reviewer verdict (verified) | Suite / CI | Recommendation |
```

plus one line each for issues closed at validation, complexity-cuts, protocol items awaiting the word, drafts, and
skipped / in-flight items. **Merging needs the operator's explicit word ("merge", or "merge once green and
validated").** "Sure" to a review question is not a merge word, and the auto-mode classifier enforces this. A
scheduled or unattended run never merges.

On the word, for each PR in dependency order:

1. **Only inside a merge window:** UTC minutes 02–26 or 32–56 (clear of the :00/:30 L2 fires and the deploy
   fetch). Wait with `until m=$(date -u +%M); [ "$m" -ge 2 ] && [ "$m" -le 26 ] || { [ "$m" -ge 32 ] && [ "$m"
   -le 56 ]; }; do sleep 10; done`.
2. `gh pr update-branch <N>`; if the head moved, wait for CI on the new head. **Exception:** a `main → production`
   promotion PR is never update-branched (that would write production's old promotion merges into `main`).
3. `gh pr merge <N> --merge --match-head-commit <sha>` (merge commits, never squash); confirm `state=MERGED`.
4. **Verify the deploy:** the `Deploy dramatic_options` run for the merge commit completes green, the live checkout's
   HEAD (`git -C "$LIVE" log -1`) and `/api/version` show it, `systemctl --failed` stays empty.
5. Update the next PR's branch (siblings often touch the same UI files) and repeat.

A draft is never merged; marking a PR ready is its author's signal. Remove only this run's merged worktrees and
branches. File reviewer follow-ups as issues with a lane label and a Payoff line.

**Promotion to PROD** happens only on the operator's personal go each time: a PR `production ← main`, CI green,
merge in a window, then read-only checks over `ssh console@all-options-prod`: HEAD = the merge, timers still
disabled, `LIVE_TRADING_ENABLED=false`, `DRY_RUN=true`, units on `-m orchestrator`, 0 failed units, Real Options'
`trading-bot` active, and `/api/version` `env: prod`. Then update STANDING_STATE's board in a records PR.

## Step 8: Summary

One table: Issue/PR · Title · Verdict · Action · Link. Include fixes shipped, issues closed by class, protocol items
awaiting the word, follow-ups filed, the batch stamp and the deploy result. Remind the operator that `/triage` Step 0
verifies these fixes in ~3 days.

**Skill-impact ledger:** if this run merged a change to any `.claude/skills/*/SKILL.md` rule, append a row to
`.claude/skills/skill-impact.md` in the same PR (date, skill/step, rule, motivating issue/PR, commit, recurrence check
due +14 days, outcome `pending`). Fill in due outcomes only inside a PR too.

## What NOT to do

- Never merge without the operator's explicit word, outside a window, on red CI, or a draft; never squash.
- Never change a frozen number, the floor, a prompt, a cap, a cluster or the universe without the operator's dated
  word recorded in the same PR; never `json.dump` `universe_register.json`.
- Never weaken the KILL check, the triple live gate, `DRY_RUN`, the never-broker null books, or a fail-closed path.
- Never start an issue without the in-flight check; never take over another agent's branch without the operator's
  say-so.
- Never post a reviewer's finding you haven't verified; never fabricate a stamp.
- Never write under `$LIVE`, edit `.env`, print a key, or run the loop by hand.
- **Never `gh pr edit --body` without a non-empty guard.**
