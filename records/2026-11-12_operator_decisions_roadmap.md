# 2026-11-12 — The operator's decisions on the roadmap drafts (#476)

**What this is:** the dated record of the operator's word of 2026-11-12 on the protocol drafts in PR #476
(`records/2026-11-10_*_DRAFT.md`, written by a session the operator has since stopped). Only what was worded is in
force. Everything else in those drafts stays a draft.

## The word (verbatim)
> Kill rule: clock A (from 2026-07-01), payoff P1, drawdown option 1 (cumulative), R2, null books keep booking. Land
> before 12-25. Boundary B, first Monday L1, starting 12-07; models ride it only if the PR and price checks are ready.
> T4: 2B + 4A. OK to promote main to production inert (FORWARD_ENABLED=false), but first resolve the PROD .env
> PAPER=true/false contradiction. OK to draft the inert arming PR and a 1-week paper rehearsal on a separate paper
> account. No live arming. Defer #469.

Before giving it, the operator received CC's concerns (in-session, 2026-11-12):
- the cumulative drawdown leg will plausibly trip within months on a venture book;
- "null books keep booking" starves if the L0 scan halts on a trip;
- several sub-decisions were still open.

The operator then answered "please go ahead". The open sub-decisions are listed at the end, and none is assumed.

## What is now in force, and where it is recorded

| Decision | Recorded in | Code |
|---|---|---|
| **Kill rule, dry leg:** clock A (first real fill, 2026-07-01), payoff P1 (a real close with `realized_pnl > 0`); binds 2027-04-01 absent a payoff | PREREG_THEMATIC_CONVEXITY §6, conformance notes (2026-11-12) | implementing PR, before 12-25 (CC recommends the 12-07 boundary weekend) |
| **Kill rule, drawdown leg:** option 1, cumulative net loss since 2026-07-01 (realized + unrealized) ÷ $10,000 | same | same PR |
| **R2:** the 10% book is premium committed at any moment | PREREG_THEMATIC_CONVEXITY §5, reading note (2026-11-12) | none (sizing already does this) |
| **A trip halts the real book and the council; the null books keep booking.** The manual KILL still halts everything | §6 conformance notes | same PR |
| **Scheduled boundary B:** record-segmenting changes land on the first Monday L1 of each month, deployed the weekend before; next **Mon 2026-12-07**. The model refresh rides it only if its PR and the Gemini/xAI price checks are ready | STANDING_STATE ruling | none |
| **T4 conditions:** (2) = 2B, (4) = 4A | IMPLEMENTATION_PLAN, T4 conditions (dated note) | the scoreboard reading them: a follow-up |
| **PROD promotion** of main, inert (`FORWARD_ENABLED=false`), **after** the PROD `.env` PAPER contradiction is resolved | STANDING_STATE ruling ("authorized but not done") | the `production ← main` PR, when resolved |
| **Inert arming PR**, a draft only; **1-week paper rehearsal on a separate paper account** | STANDING_STATE ruling ("authorized but not done") | draft PR; the rehearsal is an operator `.env` act |
| **No live arming.** **#469 (capital ladder) deferred** | STANDING_STATE | — |

## Still open, not assumed

- **L0 on a kill-rule trip.** Today a trip also skips the L0 scan, so the null books would book only from the remaining
  active sentinels and the hand seed until those lapse. CC recommends that L0 keep scanning, since it places no orders
  and costs about $0.002 a week. Until then the implementing PR leaves L0's behaviour as it is.
- **Re-anchor after a review** (`kill_rule.dry_clock_reanchored_on` / `drawdown_reanchored_on`, each a `frame_version`
  boundary). Not built. A trip clears only by a payoff or a mark recovery until that is worded.
- **Boundary details:**
  - whether a frame-conformance defect may land off-cycle;
  - the exempt list as drafted;
  - the staging rule;
  - the segment register and CI fingerprint tooling.

  B itself is in force, with the draft's money-safety and fail-closed-outage off-cycle classes as the working default.
- **T4 checklist decisions 2, 3 and 6:**
  - the §3 mechanics rows;
  - the order ceiling versus closes (#473);
  - the live smoke (#467).
- **The rehearsal's details:** a separate Pushover token and LLM keys as well as the separate paper account, and the
  starting DB: (i) a quiet-moment copy of DEV's, or (ii) empty.
- **The other drafts in #476** (calibration v3, the repeat-read probe, the layer scoreboard, cheap-then-repriced, the
  convexity regime, held-name tracking): no word yet.

## Second word, the same day: "accept all"

After the first word, CC put a table of suggestions for the open items to the operator. The operator answered "accept
all, and then let's get a new /ship cycle going". The accepted rows:

| Item | Ruling | Recorded in |
|---|---|---|
| L0 on a kill-rule trip | **The scan keeps running, framer included**; the council and the real book stay halted | PREREG_THEMATIC_CONVEXITY §6 addendum |
| Re-anchor after a review | **Build** `kill_rule.dry_clock_reanchored_on` and `drawdown_reanchored_on`: dated keys written only on the word, each a `frame_version` boundary | same |
| Boundary off-cycle classes | Money-safety defect, fail-closed outage, **and frame-conformance** (the #276 class) | STANDING_STATE |
| Boundary exempt list and staging | As drafted: config-gated changes default-off; prompt and constant-stamp changes as draft PRs | STANDING_STATE |
| Boundary tooling | **The segment register only**; no CI fingerprint check | STANDING_STATE |
| T4 decision 2 | The mechanics rows are adopted | IMPLEMENTATION_PLAN |
| T4 decision 3 | **(a)** the ceiling bounds opening orders only | PREREG_REAL_MONEY_BROKER §3b |
| T4 decision 6 | The live smoke is deferred until arming is on the table | IMPLEMENTATION_PLAN |
| Rehearsal | A separate paper account, a separate Pushover app token, shared LLM keys, and starting DB (i) | IMPLEMENTATION_PLAN |
| Backfill and `include=false` (RDW) | Decided at #456's look | STANDING_STATE |
| The remaining #476 drafts, in priority order | (1) #456, the cheaper arm; (2) #455 and #462; (3) #464, option B; later #453, #460, #457, #459 and #461 | STANDING_STATE |

**PROD's `.env`, verified read-only by the operator on 2026-11-12** (names and flags only):
- the flags: `PAPER=false`, `LIVE_TRADING_ENABLED=false`, `DRY_RUN=true`, `FORWARD_ENABLED=false`;
- the keys: only the live pair, no paper pair and no legacy names;
- the code: `a7548e8`.

STANDING_STATE was right, and DEPLOYMENT.md was stale (it said `PAPER=true` and legacy names); it is corrected in the
same PR. With `FORWARD_ENABLED=false` the inert promotion is safe: the deploy's key check is skipped on an inert env,
no timer arms, and the web dashboard builds no Alpaca client.

**Still open after this word:** the companion quantity guard on closes (#473's draft); the CI fingerprint check (by
choice, not built); and the #476 drafts beyond the priority order above, which have not yet had their details
worded.

