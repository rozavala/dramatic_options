# 2026-07-04 — ERRATUM: the real book's FIRST entry happened 2026-07-01 (L1 #389, PL) and went unrecorded for three days

**Status: correction of record, written 2026-07-04 on discovery** (found while grading the
2026-07-03 holiday L1 — the "Book: 1 open · $690" line in an otherwise-expected no-op run).
Every element below verified against the DB, the run-389 journal, and the persisted agent
outputs before writing.

## 1. What actually happened (the event)

**2026-07-01, L1 #389 (19:45 UTC): the system's first-ever real-book trade — the full
apparatus chain executed end-to-end, legitimately, on a discovery-origin name:**

- **Sentinel #21** (T3 discovery, `space_infrastructure_scaling`) surfaced **PL** →
- the **council** (first cycle with the analyst meter + restored news live) produced a
  tri-criteria-complete **include at MODERATE**: `structural_vs_fad="structural"` ∧
  `under_narrated=True` (the meter's "11 analysts" — the §19 instrument working as designed) ∧
  `at_inflection=True` (RPO +80.6% YoY, quarterly revenue +42.1%, capex +113%; the strategist's
  honest `weakest_point`: the +5.685 12-mo momentum means the inflection may be partly behind) →
- the **IV gate** passed PL cheap on OPRA: `iv/rv=1.08, skew=−6.2vp` (inside the frozen
  1.2 / 10vp) →
- **caps** fit ($690 ≤ $1k per-name; `space_smallcap` cluster $690/$2,000) → sized 1 contract
  (`PL270115C00040000`, Jan-2027 $40C, 198 DTE) →
- **submitted** to the paper broker (`submit-pending`, journal 19:48:10), **filled**, and
  **reconciled to open** by the 20:00:04 L2 — PR #44's pending→fill→open machinery working
  live on its first real use. Order `3292f59e-…`; `proposal_id=216 status="traded"
  position_id=1`. The L2 has marked it every cycle since (2026-07-03 20:30 mark: $665.50/ct,
  −3.6%). Exits armed: 10× profit-take / 21-DTE time-stop (~2026-12-25) / expiry.

This is also the **first live traversal of the T3 provenance chain**
(sentinel → proposal → position): proposal 216 resolves at close → the first council Brier
observation; sentinel 21 resolves as traded.

## 2. The error (what the record said instead)

- The 2026-07-01 (LATER-3) session **graded L1 #389 as "…0 includes"** and described PL as
  "the two-of-three exemplar" with **at_inflection ❌**. Both claims are contradicted by the
  persisted record (`council_l1_health(389).proposer.above_floor_proposals = 1`; the
  strategist's raw output: `at_inflection=True`, include, MODERATE, all three criteria
  present). The journal line `Cycle #389: evaluated=1 opened=1` was printed at grade time.
- The error then **propagated by inheritance**: the 2026-07-02 sessions repeated "the real
  book has NEVER traded (0/406)" in operator reports, and
  `records/2026-07-02_burst_prediction_PINNED.md`'s ACTUAL section wrote "the real book stays
  (correctly) empty" — **factually wrong at write time** (PL had been open ~24h). A dated
  correction bracket is added there with this PR.
- Nothing in the alerting fired, correctly per its own (too-narrow) spec: the pager covers
  failures, kill-rule, cost-cap, parse-fail — **there is no page for an include or a first
  entry**. The single most consequential healthy event the system can produce was silent.

## 3. Why it was missed (mechanisms, each with a fix)

1. **Grading error at the source** (human/session): the #389 grade recorded the roundtrip
   fields and missed `above_floor_proposals=1` and the cycle line. FIX (process): an L1 grade
   MUST quote the cycle line (`evaluated/opened`) and `above_floor_proposals` verbatim.
2. **No event page** for include / entry-submit / fill-reconcile on the REAL book. FIX
   (shipped with this PR's sibling): page on any real-book above-floor include and on any real
   entry submit + fill — these are rare-by-design; the page cost is ~zero.
3. **State inherited from memory instead of re-queried**: three sessions repeated
   "empty book" without a `convexity_positions` count — the cheapest possible query. FIX
   (process): any statement about book state in a record must be from a same-day query.

## 4. Corrected implications (each previously stated wrong or now stale)

- **T4 unlock conds 2/3/4 are ACCRUING, no longer vacuous** — 1 real trade open; they still
  need RESOLUTIONS (PL resolves by ~Dec-2026 time-stop / earlier on 10× / expiry Jan-2027).
  Cond-3's breach-audit is no longer auditing an empty table.
- **The §6 posture-review backstop's zero-entries leg is DEAD** (entries ≥ 1 as of
  2026-07-01); the original kill-rule clocks (20% book drawdown / 9-month bleed) are now LIVE
  on a real position — the falsifier-leg-reachability concern the backstop existed to patch
  has resolved itself in the healthy direction. The 2026-11-02 checkpoint and D=2027-03-02
  review stand unchanged (review-not-kill; D's trigger condition "zero entries ever by D" can
  no longer fire — the review at D, if reached, is now about resolution evidence, not empty
  posture).
- **The "empty-book fork" (apparatus-ready vs yield-block vs criteria-reconsideration) is
  MOOT** — the market answered it: the validated mandate CAN produce an include when the
  evidence-grounding is sufficient. Causal note, stated carefully: the include arrived on the
  FIRST L1 after the analyst meter + news restore went live, with the meter's output quoted in
  the surviving thesis (`11 analysts`) — consistent with (not proof of) the §10.8 finding that
  grounding, not the criteria, was the binding constraint.
- **The council-selectivity picture updates**: the mandate is not 0-yield; it is
  ~1-include-per-3-weeks-of-L1s on current evidence (1/407 runs, but 1/3 post-meter L1s).
  No re-tightening or relaxation is licensed by n=1; the Brier resolution is the evidence.
- The **null-book contrasts are unaffected** (their books never read the real book), but
  `real − shadow` now has a real-side leg accruing — the reads stay resolution-gated
  (~Nov 2026+) and the vintage segmentation stands.

## 5. What does NOT change

The frozen frame (caps byte-identical — the entry fit them), the exits (§6a deterministic),
the reserve (PL is judged-recently and open — it never enters the reserve pool), Monday's
vintage-2b and reserve bands (pinned blind; the includes band 0–1 already anticipated a
possible include), and the smoke plan. No pre-registration pin was violated by the trade
itself — the apparatus did exactly what its frozen documents say it should; the failure was
purely in the OBSERVING layer.
