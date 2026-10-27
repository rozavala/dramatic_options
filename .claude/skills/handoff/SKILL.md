---
name: handoff
description: End-of-session wrap-up for Dramatic Options. Flushes this session's durable learnings into the memory files (and names, never silently commits, any owed record or doc update), then writes a self-contained, ready-to-paste RESUME PROMPT for the next session (saved to .claude/HANDOFF.md and printed), then hands off the two manual steps to clear. Use when ending a session, when context is getting long, or when the user says "wrap up", "save and clear", "hand off", "close out the session", "checkpoint", or "prepare the next session".
argument-hint: [optional: anything to emphasize in the next steps, e.g. "lead with the 11-02 posture look"]
---

# Handoff Skill — Dramatic Options

End a working session so a fresh one resumes with zero loss of context: **(A)** persist durable learnings →
**(B)** write the resume prompt → **(C)** hand off the manual clear.

> `/clear` is a user-only command: no tool or hook can clear the conversation. This skill automates A and B and ends
> by telling the operator the two manual steps. Never claim the session was cleared.

**Paths are derived, never hardcoded.** The worktree is the cwd; the live checkout is the main worktree
(`LIVE=$(git worktree list --porcelain | awk '/^worktree/{print $2; exit}')`); the live DB is
`$LIVE/data/dramatic_options.db` (open it `?mode=ro`); the memory directory is the one the system prompt names.
**Re-derive every live fact** (HEADs, the board, timers, the book); never copy a number from memory into the handoff.

## Phase A — persist what's durable

The memory files are the wrap-time target (outside the repo, always safe to edit, never part of a PR). Committed
records (`records/STANDING_STATE.md`, `PREREG_*.md`, `CLAUDE.md`, `DEPLOYMENT.md`) should already be current from
this session's PRs; don't edit them at wrap time. If an update is owed, name it as a next step.

1. **Live state (read-only):**
   - `git -C "$LIVE" log -1 --oneline`; `git fetch -q origin && git log --oneline -1 origin/main origin/production`;
     `git log --oneline origin/production..origin/main | wc -l` (PROD's lag).
   - `systemctl --failed --no-legend | grep -i dramatic`; `systemctl list-timers 'dramatic-options-*'`.
   - `curl -sk https://all-options-dev.tail57521e.ts.net:8602/api/status` (level, beats, KILL, drawdown, last
     council) and PROD's `/api/version`.
   - `gh pr list --state open` and `gh issue list --state open` with labels (`needs-operator`, drafts, holds).
   - The last scheduled reviews: `tail -4 ~/.local/state/dramatic-options/cron.log`.
2. **Classify this session's durable items** (`user` / `feedback` / `project` / `reference`) and update in place,
   one fact per file, linking related memories with `[[name]]`. Delete a memory that proved wrong. The usual homes:
   - strategy state, L1 health, the record: `dramatic-options-thematic-convexity` (prepend a dated banner; the
     nightly grade reads the newest banner for its expectations, so keep stamps and tallies exact);
   - operator red-team and plan-review lessons: `dramatic-options-plan-review`;
   - council disciplines (the seam, parse health, grounding): `dramatic-options-council-build`;
   - deploy, topology and ops: `dramatic-options-deployment-topology`;
   - data feeds, OPRA, dual-read: `dramatic-options-data-feed-upgrade`;
   - edge vetting and validation: `dramatic-options-edge-toolkit` / `-validation-methodology`.
   A new file gets a one-line pointer in `MEMORY.md`.
3. **Nothing durable this session → say so and skip.** Don't manufacture memory edits.

## Phase B — the resume prompt

Write a self-contained prompt to `.claude/HANDOFF.md` in the worktree (git-ignored) **and** the final message:

- **Header:** `Resume Dramatic Options (worktree <cwd>, branch <b> @ <sha>; main <sha>, PROD <sha> = <n> behind).
  Live loop on DEV (<LIVE>); PROD inert. venv: venv/bin/python, venv/bin/ruff. Keys in <LIVE>/.env (names only).`
- **Read first:** `records/STANDING_STATE.md`, then the 3–5 most relevant memory files, each with a one-line hook.
- **What shipped this session:** merges and PRs with their SHAs, decisions with the operator's words, new stamps.
- **Dated obligations:** every dated item with its absolute date and trigger (posture looks, the model refresh,
  falsifier reads, pin expiries, DST).
- **The board:** open PRs (ready / draft / held, and who owns them) and open issues with the gating reason.
- **Routine watches:** what the pager and the nightly grade own, and what self-clears when.
- **⭐ Next:** derived from the board, the dated obligations and the frontier; "stay on watch" is valid.
- **Guardrails (unchanged):** read-only on `$LIVE`; never trigger a run; merges need the operator's explicit word,
  in a window (UTC minutes 02–26 / 32–56), after `gh pr update-branch` (except `main → production`), merge
  commits after green CI; PROD needs the operator's personal go each time; staged-class changes (frozen numbers,
  floor, prompts, caps, clusters, universe) wait for the dated word; the hard seam; never backtest the council; never
  print a key; never send the operator's email anywhere.
- **The grading recipe:** `con = sqlite3.connect("file:<LIVE>/data/dramatic_options.db?mode=ro", uri=True);
  con.row_factory = sqlite3.Row; council_health_report.council_l1_health(con)`.

Weave any `$ARGUMENTS` emphasis into Next and the dated section.

## Phase C — hand off

End with exactly:

```
1. /clear
2. paste the prompt above (also saved at .claude/HANDOFF.md; in the fresh session you can just say
   "read .claude/HANDOFF.md and resume")
```

Then stop.

## Guardrails for the wrap

- Memory files are safe to edit; committed records are not. Name an owed record update, don't make it here.
- Re-derive every live fact; derive next steps from the actual board, never invent them.
- This skill records and hands off. It never merges, promotes, or loosens a gate, cap or floor.
