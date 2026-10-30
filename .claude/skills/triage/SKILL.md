---
name: triage
description: Money-and-record-first audit of the Dramatic Options system (real paper book + null books + council funnel) over a rolling 10-day window. Verifies recently closed issues stayed fixed, reconstructs every order, position and above-floor verdict against the change timeline, checks every systemd lane ran and every fail-soft adapter actually returned data, sweeps journald/the DB/the dashboard/the debug chain, and hunts for mechanism to delete. Classifies every finding as PROFIT, PROTOCOL, DEBUGGABILITY, SMOOTHNESS, SIMPLIFY or COMPLEXITY-BAIT before filing GitHub issues with operator approval. Use when the user asks to triage, review logs, audit recent activity, or check what's broken.
argument-hint: [optional: lookback override like "48h" / "since 2026-10-20", or a unit name like "l1"]
---

# Triage Skill — Dramatic Options

Run after the nightly L1 grade (weekdays, from ~20:45 UTC) or on demand. Audit from the money and the record, not
from the logs. Scan window: since the previous run (default 24h; `$ARGUMENTS` overrides). Context window: **10 days**
(the change timeline, lifecycles and baselines). Long-dated positions mean the system that entered a position is
often not the one now marking it.

Order: (0) verify recent fixes, (1) reconstruct lifecycles against the change timeline, (2) sweep lanes, journals,
adapters and the debug chain, (3) classify by what fixing it buys, (4) origin, prior art and dedup, (5) present for
approval, (6) file.

**Issues and PRs are the system's documentation.** Write every issue so a future agent can reconstruct the reasoning
without this conversation: a searchable title (component + symptom), a self-contained body, prior art, and a
"Verify it's still live" command.

**Two things are sacred.** (a) The money: paper today, ~$10k live at T4 arming. (b) The record: frozen protocols
(`PREREG_*.md` at the repo root, the rulings in `records/STANDING_STATE.md`) change only by a dated operator
amendment, and the council is never backtested (forward Brier only). A finding that would "fix" a result by
changing a frozen rule, the floor, the gate, a cap or a prompt is a PROTOCOL finding, never a code fix.

**Not the nightly grade.** `scripts/ops/prompts/nightly_grade.md` grades the L1 *record* (stamps, tallies, verdicts).
Triage hunts *defects*. Read the newest grade banner (memory file `dramatic-options-thematic-convexity.md`) and
don't re-derive what it already graded; do chase anything it flagged as a finding.

## Operating Constraints

- **Paths are derived, never hardcoded.** The worktree is the cwd; the live checkout is the main worktree
  (`LIVE=$(git worktree list --porcelain | awk '/^worktree/{print $2; exit}')`); the live DB is
  `$LIVE/data/dramatic_options.db`; the cache is `$LIVE/data/cache/`; the memory directory is the one the system
  prompt names (else `~/.claude/projects/-home-rozavala-dramatic-options-claude/memory/`).
- **Read-only everywhere.** Never write under `$LIVE` (no temp files, no markers), never trigger a run, never touch
  a timer or the crontab, never edit `.env`, never print a key value (names only). Open the DB only as
  `sqlite3.connect(f"file:{LIVE}/data/dramatic_options.db?mode=ro", uri=True)` from `venv/bin/python`, never the
  `sqlite3` CLI (read-write; it can checkpoint the WAL). Skill state (`last-run.md`) goes under
  `.claude/skills/triage/` in the worktree (git-ignored).
- **Two hosts.** DEV `all-options-dev` (this box): the paper loop on `main`. PROD `all-options-prod` (user
  `console`): branch `production`, **inert** (timers disabled, `LIVE_TRADING_ENABLED=false`, `DRY_RUN=true`). On
  PROD run only read-only commands over `ssh console@all-options-prod`: `git log -1`, `git --no-optional-locks
  status --porcelain`, `systemctl show|list-timers|--failed`, `journalctl`, and `curl` of its dashboard. No fetch,
  no restart, no deploy, no `.env` edits.
- **The dashboard is evidence.** `https://all-options-{dev,prod}.tail57521e.ts.net:8602/api/status` (light: level,
  heartbeats, KILL, drawdown tier, book open/max, last council, T4), `/api/snapshot` (every panel, including
  `why_no_entry` and the funnel), `/api/version` (`head`, `env`, `started_at`). Start there; grep journald second.
- **Calendar context (ET timers; DST moves them in UTC).** L0 discovery Sun 08:00 ET · reach digest + survivor
  cards Sun 09:40 ET · L1 council + entries Mon–Fri 15:45 ET · L2 monitor Mon–Fri 09:00–16:00 ET every 30 min
  (marks, exits, the 16:00 reconcile) · web always on. Scheduled reviews (DEV crontab, UTC; each waits for its run):
  grade weekdays 20:37, Sunday review 14:23. NYSE holidays and 13:00 ET half days come from `nyse_calendar.py`. A
  closed-market L1 short-circuits the council before any spend, so "council didn't fire", "0 entries" or "$0" on a
  weekend, holiday or after hours is expected. Confirm any absence or frequency signal on the most recent weekday
  RTH cycle before calling it a finding.
- **Don't duplicate the pager.** `notify.py` already pages: unit `OnFailure`, kill-rule trip, fail-closed council,
  cost-cap trip, the council parse-fail page, `REAL-BOOK ORDER SUBMITTED` / `NOT FILLED` / `FILL`, foreign quantity,
  OPRA entitlement lapse, dual-read degraded. Skip what those cover; hunt what fixed triggers miss.
- **Delegation.** Mechanical sweeps (counts, greps, timeline assembly) → parallel `Agent` subagents on `haiku`,
  given absolute paths and asked for the command plus one verbatim line per claim. Interpretation → `sonnet`.
  Lifecycles and classification stay in the main session. **No subagent claim is a finding until the main session
  re-runs its command.** Reviewers have mislabelled units (L1 vs L2) and miscounted before.

## Step 0: Verify recent fixes (closed loop)

```bash
gh issue list --state closed --limit 40 --json number,title,closedAt,body \
  --search "closed:>$(date -d '10 days ago' +%Y-%m-%d)"
```

For each closed issue whose fix merged ≥3 days ago and has a "Verify it's still live" command (skip ones
`last-run.md` already verified): re-run it.
- **Signal gone** → "N fixes verified dead".
- **Signal persists** → reopen with the re-run output and the PR that claimed the fix. First split the count at
  the fix's merge time and report only the post-fix side, and rule out a benign mechanism with the same signature.
- **Changed shape** → a new Step 2 finding, cross-linked.

Also read `.claude/skills/skill-impact.md`: for each `pending` row whose recurrence check is due, check whether the
motivating failure recurred and record the outcome **as a PR comment or in a PR**, never as an edit on `main`.

## Step 1: Lifecycles × the change timeline (the core)

**a. Change timeline** (haiku assembles; main session interprets):

```bash
git log --since='10 days ago' --oneline --first-parent origin/main
gh pr list --state merged --limit 60 --json number,title,mergedAt,files --search "merged:>=$(date -d '10 days ago' +%Y-%m-%d)"
git log --oneline origin/production..origin/main | wc -l          # PROD's lag behind main
curl -sk https://all-options-prod.tail57521e.ts.net:8602/api/version   # head must equal origin/production
```

Mark the commits that touched decision paths (`paper_loop.py`, `convexity_gate.py`, `convexity_sizing.py`,
`structure.py`, `monitor.py`, `broker.py`, `council/*`, `discovery.py`, `sentinels.py`, `marker_refresh.py`,
`data/*`, `config.json`) vs plumbing, and every **record-segmenting** change (a new `runs.model_mix` key or value,
a `frame_version` move, new prompt hashes) with the dated STANDING_STATE entry that explains it.

**b. The real book.** For every order and position in the window, plus a status pass over open ones:
- **The decision chain.** `council_proposals` (conviction, strategist reason, `at_inflection` / `under_narrated`) →
  `convexity_eval` (gate `iv_rv`, `otm_skew`, decision) → sizing reasons → `convexity_positions.rationale` (`quote`
  bid/ask/spread at submit, the `fill` note).
- **The order.** A DAY limit at mid from the 15:45 L1, reconciled by the 16:00 L2: `filled` → `open`, resting →
  `cancelled_unfilled`. A row still `pending` after a later L2 is a finding. A fill worse than the limit is PROFIT.
- **Caps.** Per name ≤ 1% of the frame, cluster ≤ 2% (counts `pending`), book ≤ 10%, ≤ 15 open, from `config.json`
  `convexity_book`. The dashboard `risk` panel must agree.
- **Exits.** Time stop and expiry per `convexity_exits`. Marks fresh vs the L2 cadence. **A mark is unrealized;
  never call a mark a loss.**

**c. The council funnel.** Every above-floor verdict in the window: did it reach the gate, what did the gate say,
did an order follow, did it fill? Every name that flipped verdict on unchanged figures (quote both reasons). The
driver-scope count and the other running tallies belong to the nightly grade. Read them, don't recount.

**d. The null books.** Shadow, 3A, 3B and shares: booked when the real loop evaluated, never-broker, outside-frame
positions tagged. A null book that stops booking while the real loop runs is a fail-soft swallowing every cycle.

**e. Overlay the timeline.** A position entered under rule set A and marked or exited under rule set B is a
first-class finding whether it won or lost. A frozen number, floor, prompt or gate that changed in code without a
dated STANDING_STATE / PREREG entry is PROTOCOL, highest severity.

## Step 2: Lane, journal, adapter and debug-chain sweep

Fan out haiku subagents (one per category) over journald (`journalctl -u dramatic-options-{l0,l1,l2,reach,web}
--since …`), the DB, the dashboard payloads, and one read-only PROD ssh sweep.

- **A. Lane health.** Each scheduled fire has a `runs` row (L1 weekdays; L2 every 30 min in RTH; L0 and reach on
  Sunday); `systemctl --failed` empty on both hosts; every unit's `ExecStart` is `python -u -m orchestrator` (a
  `pkill -f orchestrator.py` from a sibling project once SIGKILLed our L2); no `status=9/KILL`; the scheduled-review
  log `~/.local/state/dramatic-options/cron.log` shows each grade/Sunday run with `rc=0` (or a deliberate "NOT RUN").
- **B. Fail-soft adapters returning nothing** (the coverage-meter class: a dead endpoint looks like a quiet one).
  `Coverage meter: analyst counts n/m` (0/m is a WARNING), `Corpus refetch on filing: n`, `Marker refresh:
  refreshed=…`, `fundamentals-staleness: lagging=[…]`, the `Quote …` lines (a missing bid/ask), dual-read
  `record_ok`. For each adapter that is fail-soft by design, confirm it returned real data on the latest weekday
  RTH run, and check its cache's newest write date (`ls -t data/cache/<source> | head`).
- **C. Warning storms and retries.** The same WARNING repeated; `call failed (attempt` counts; provider fallbacks
  (the strategist understudy firing is loud).
- **D. Cost creep.** Per-provider council cost vs the cap; month-to-date spend (`dashboard_data.spend_panel`).
- **E. State inconsistencies.** Orders without positions, positions without proposals, a sentinel linked to a
  proposal that never traded, `client_order_id` duplicates, a migration not applied on PROD.
- **F. Measurement drift.** Every caller that claims to measure "the gate" uses the gate's own path (the side-guard
  AST test in `tests/test_otm_side_guard.py` guards `select_structure`; look for the next such seam). Time logic
  decided to the second or by the UTC date where the timer is ET (the TTL bug).
- **G. Debuggability.** Dashboard reachable on both hosts with `/api/version` = the deployed head; the newest Deploy
  run for `main` and `production` green with its head; journald retention covers the 10-day window; "Verify it's
  still live" commands in OPEN issues still execute; STANDING_STATE's "Open issues" and board lines match `gh`.
- **H. Simplification hotspots.** Config keys nothing reads (`git grep -n "<key>" -- '*.py'`), switches left on
  after their study closed, duplicate guards. Flag removal only when the guarded state is provably unreachable.

Per candidate: most recent occurrence (verbatim line + timestamp + unit, or the DB row), first appearance in the
window (weekday-RTH vs off-RTH), frequency/trend, affected module, and a copy-pasteable verification command.
**Take the scan scope from the consuming code** (e.g. which `runs` rows the funnel reads), not from a pattern.

## Step 3: Classify every finding

| Class | Test | Outcome |
|---|---|---|
| **PROFIT** | Fixing it changes a verdict reaching the gate, a gate verdict, a fill, an exit, a cap, or the data feeding them. Step 1 findings land here by construction. | Label `lane:profit`. Full ceremony in `/ship`. |
| **PROTOCOL** | It touches a frozen number, the floor, a council prompt, the gate, a cap, a cluster, the universe, a stamp's meaning, or a PREREG / STANDING_STATE ruling. The fix is a **dated operator amendment**, never a quiet code change. | Label `lane:protocol`, `needs-operator`. `/ship` drafts the record; code follows the word. |
| **DEBUGGABILITY** | Restores our ability to see the system: a fail-soft adapter that hides an outage, journal integrity, dashboard truth, lane observability, verification-command health. | `lane:profit` unless trivial, then `lane:sweep`. |
| **SMOOTHNESS** | Same trades, less drama: log noise, page noise, ops hygiene. | `lane:sweep`. Batched in `/ship`. |
| **SIMPLIFY** | Removing mechanism (dead config, superseded switches, duplicate guards) makes the next change easier. | `lane:simplify`. Ceremony by blast radius. |
| **COMPLEXITY-BAIT** | The fix adds a state file, config key, guard tier or retry for a state with no demonstrated cost. | Propose **won't-fix**; on approval close with a searchable comment. |

Calibration from this repo: the analyst-coverage endpoint 404ing for three months behind a fail-soft adapter =
DEBUGGABILITY with PROFIT impact (#337). The feasibility probe selecting a wrong-side contract the gate refuses =
PROFIT for admissions (#343). The TTL decided by start-second jitter = PROTOCOL (membership; it took the operator's
word, #342). A prompt re-wording to make a verdict pass = PROTOCOL, never a fix. A retry tier around a one-off 502 =
COMPLEXITY-BAIT.

**Deletion first:** if a defect exists because two mechanisms overlap (two places computing "the gate", two clocks
for one schedule), the fix removes one path rather than synchronizing them.

## Step 4: Origin, prior art and dedup

- **Origin:** tie each finding to a commit from the Step 1a timeline, or say "no clear origin within the window".
- **Prior art (mandatory):** `gh issue list --state all --search "<component>"`, `gh pr list --state all --search
  "…"`, `git grep -n "<component>" -- 'PREREG_*.md' records/`, `records/edge_graveyard.md` (divergence v1, FSSD,
  the delta-exit are closed), and memory. Re-proposing a closed approach needs new evidence and a dated protocol.
- **Dedup and in-flight work:** an exact-topic open issue → comment; related → comment there; a recently closed same
  fingerprint → reopen; truly new → new issue. Check claims too: an issue with a recent "Claiming — …" comment or an
  open PR naming it is someone else's.

## Step 5: Present for approval — STOP HERE

No `gh` writes until the operator approves. Lead with the Step 1 narrative (what the book and the funnel did and
why), then the Step 0 results, then one table:

```
| # | Class | Sev | Finding | Affected | $ / record impact | First seen (UTC / ET) | Count | Off-RTH only? | Origin | Proposed action |
```

Order: PROFIT → PROTOCOL → DEBUGGABILITY → SMOOTHNESS → SIMPLIFY → COMPLEXITY-BAIT. Per finding: a verbatim excerpt
(≤ 8 lines) and the exact issue body to file. Ask: "File all, a subset, or none? Won't-fix proposals need explicit
approval too."

## Step 6: File after approval

Template (HEREDOC): Summary · Most recent occurrence · First appearance · Frequency · **Payoff** (one sentence, in
class terms) · Likely origin · **Prior art** (with one-line outcomes, or "none found") · **Verify it's still live**
(an exact, date-scoped command) · Impact tier · Proposed next step · for PROTOCOL, the PREREG / STANDING_STATE
section the amendment must cite. Apply the lane label. Footer: `*Filed by /triage on <date>.*` Then update
`last-run.md` (date, fixes verified, issues filed).

## What NOT to do

- Don't skip Step 0 or Step 1 to get to log-grepping.
- Don't file without a verbatim excerpt, a verification command and a Payoff line.
- Don't propose changing a frozen number, the floor, a prompt, a cap or the universe in code. It is an operator
  amendment.
- Don't write under `$LIVE`, trigger a run, touch a timer, edit `.env`, or print a key. On PROD, read only.
- Don't call a never-firing guard dead without proving the guarded state unreachable.
- Don't treat weekend / holiday / after-hours absence as a finding without weekday-RTH confirmation.
- Don't trust a subagent's claim you haven't re-run.
