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
| **Kill rule, dry leg:** clock A (first real fill, 2026-07-01), payoff P1 (a real close with `realized_pnl > 0`); binds 2027-04-01 absent a payoff | PREREG_THEMATIC_CONVEXITY §6, conformance notes (2026-11-12) | implementing PR, on the 12-07 boundary (before 12-25) |
| **Kill rule, drawdown leg:** option 1, cumulative net loss since 2026-07-01 (realized + unrealized) ÷ $10,000 | same | same PR |
| **R2:** the 10% book is premium committed at any moment | PREREG_THEMATIC_CONVEXITY §5, reading note (2026-11-12) | none (sizing already does this) |
| **A trip halts the real book and the council; the null books keep booking.** The manual KILL still halts everything | §6 conformance notes | same PR |
| **Scheduled boundary B:** record-segmenting changes land on the first Monday L1 of each month, deployed the weekend before; next **Mon 2026-12-07**. The model refresh rides it only if its PR and the Gemini/xAI price checks are ready | STANDING_STATE ruling | none |
| **T4 conditions:** (2) = 2B, (4) = 4A | IMPLEMENTATION_PLAN, T4 conditions (dated note) | the scoreboard reading them: a follow-up |
| **PROD promotion** of main, inert (`FORWARD_ENABLED=false`), **after** the PROD `.env` PAPER contradiction is resolved | STANDING_STATE docket | the `production ← main` PR, when resolved |
| **Inert arming PR**, a draft only; **1-week paper rehearsal on a separate paper account** | STANDING_STATE docket | draft PR; the rehearsal is an operator `.env` act |
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
