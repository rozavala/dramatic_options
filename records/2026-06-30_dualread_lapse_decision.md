# Decision (2026-06-30): LAPSE the `veto-dualread-disagree` at 2026-07-10 — do NOT extend

**Status: DECIDED — off the board.** The OPRA/indicative dual-read shadow's date-gated disagree-veto
(`config.data_feed.dualread_disagree_veto_until = "2026-07-10"`) will be allowed to **auto-lapse** on
its pre-committed date. We do **not** extend it.

## Rationale (the input is decisive)
The dual-read flip-wire analysis (`records/2026-06-29_dualread_flip_analysis.md`, PR #117) is
**lapse-defensible**:
- Where quotes are clean, OPRA and indicative agree to ≤0.03 iv/rv → **OPRA is validated as a
  standalone gate-of-record.**
- They disagree only where **both feeds are equally broken** (CDE-class thin deep-OTM wings) → the
  shadow is no cleaner an oracle there; it is **not accruing marginal safety value.**
- The **delta-wire** (the SOLE revert trigger) has stayed quiet across the entire soak.

So the shadow has done its validation job; keeping it as a veto over the gate-of-record buys nothing.

## Mechanics (no action needed now; honor the pre-committed date)
- **No config change.** Leaving `dualread_disagree_veto_until = "2026-07-10"` lets the veto lapse
  automatically when that date passes — honoring the deliberately pre-committed date rather than
  lapsing ~10 days early (the veto has been **inert** across the soak, so early-lapse would gain
  nothing). "Lapse" = do not renew.
- **What lapses:** only the indicative shadow's ability to *veto* OPRA. The dual-read **sweep +
  tripwires keep running** (observability is retained); the gate-of-record stays OPRA.
- **At 2026-07-10:** routine verify the auto-lapse fired (the veto stops; no page; OPRA stands
  alone). This is a calendar check, not a decision — the decision is made here.

Recorded so 2026-07-10 is not a revisit. (Companion: the §5 close-out artifacts were frozen
2026-06-17/22; this resolves the lapse-vs-extend call that was their remaining near-deadline item.)
