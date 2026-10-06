# PREREG — the OPRA gate-of-record flip (accelerated, dual-read concurrent)

**Status: FROZEN by the merge of this PR (2026-06-10).** Cites the COMMITTED record only
(cite-before-record): `PREREG_COUNCIL_GATE_SEPARATION` §10.1–§10.8 (the §5-compliant 5/16
selectivity flag → the §10.7 re-tightened freeze → the §10.8 one-pass result **0/16 = SCARCITY**,
which unblocked this document per the frozen band action). Converged over the 2026-06-09 3-round
red-team (two relayed external-critique rounds + the cap check), then BLOCKED by the two honest
brakes, now unblocked with the brakes' findings folded in.

## 1. The decision and its honest yield

**Flip `config.data_feed.option_gate` INDICATIVE→OPRA now** (the companion build PR), with the
INDICATIVE dual-read running **concurrent** rather than gating. Honest near-term yield:
**ZERO, and validated** — the §10.5 cap-check showed every cap-fitting gate-cheap name on the old
16 was a thesis-reject (GEV $8,125/contract cap-blocked), and §10.8 showed the validated mandate
yields 0/16 on that population (grounding-limited, not mandate-broken). This flip is
**correctness + record hygiene**, not yield.

## 2. Justification — the principle (the snapshot is supporting evidence, never the load-bearer)

The IV/cheap-convexity gate is the frozen, pre-registered cheapness edge
(`PREREG_THEMATIC_CONVEXITY §4`). Alpaca's INDICATIVE feed is **OPRA-derived/modeled**; the gate
authorizing "cheap" off a modeled wing quote no market maker posts is the arbiter reading a model
of the market instead of the market. **The frozen arbiter must read the REAL chain** — a
correctness claim that survives the legitimacy test at zero extra trades (and zero is the honest
expectation). The earlier "OPRA can only tighten / zero veto→cheap" framing is **WITHDRAWN**: the
2026-06-09 dual-read showed GEV reading *cheaper* on OPRA (1.135 < 1.155) — deltas are
bidirectional, and trusting the real chain's reads in BOTH directions is the point. What IS
structurally guaranteed: fail-closed on missing input → veto (`convexity_gate.is_cheap_convexity`)
— the downside is bounded; the tripwires (§5) guard the bidirectionality.

**Two state facts sharpen the timing (2026-06-10):** (a) **record hygiene** — the shadow/3A/3B
null books began booking the NEW 33-name universe this week and accrue INDICATIVE-fed gate
records every cycle (the 06-10 sweep read 28/33 gate-cheap on the modeled feed); flipping while
those books are days old is the segment-while-young doctrine that drove the SIP flip. (b) **the
first-entry argument** — the new universe holds 8 cap-fittable active sentinels; whenever the
live council first includes one, the gate authorizes the book's FIRST real entry, and that
authorization should read the real chain.

## 3. Evidence (supporting), with feed provenance reconciled

- 2026-06-08 close probe: feeds agree closely; OPRA marginally better IV population.
- 2026-06-09 ~13:00 ET dual-read (`scripts/probe_opra_dualread.py`, committed): 12/16 IND vs
  10/16 OPRA gate-cheap, **0 coverage gaps**, |Δ iv/rv| median 0.014 / max 0.024; the 2 flips
  (LHX, RTX) both cheap→veto and both thesis-consensus names.
- **§6 (CGS) discharge by name** — IND/OPRA: NEE 1.105/1.088 · RTX 1.199/1.201 · LHX 1.194/1.209 ·
  GEV 1.155/1.135. Provenance reconciliation: CGS §6's original boundary reads (NEE 1.17, RTX
  1.14) were computed on **IEX-RV pre-data-feed-PR1**; the SIP-RV switch moved NEE ~0.08
  (3–4× the max IND→OPRA delta) — the feed change moved the boundary SET itself, hence the §6
  re-target NEE→GEV, now MOOT against §10.8 (no survivor). The §6 *spirit* — the gate's cheapness
  reads must be trustworthy on the real chain before the council defers to them — is discharged
  by this flip itself plus §5's measure-while-live tripwires.

## 4. The relaxation, named

This document **supersedes the documented "across-session dual-read first" evidence standard** in
three places: `PREREG_THEMATIC_CONVEXITY §4` (a dated supersession NOTE, original sentence left
visible), `IMPLEMENTATION_PLAN §5b` (in-place, living doc), and the `config.json data_feed`
`_comment` (in-place, with the flip). It is a RELAXATION of a standard, not merely an accelerated
schedule; the beneficiary is the re-architecture timeline — the CGS §7 HARK gradient, named. The
defense rests on §2's principle, not the calendar, and the dual-read does not disappear — it runs
concurrent with pinned tripwires and a fail-closed revert.

## 5. Tripwires — fully pinned (thresholds DISCLOSED as set after the 2026-06-09 calibrating snapshot)

Per L1 session, over the option-eligible universe (the swept population) + the evaluated names
(inline): **OPRA coverage gaps** (INDICATIVE structures a name OPRA cannot), **|Δ iv/rv|**
(ratio units) median and max vs the INDICATIVE shadow, and **any cheap-flip in either direction**.

- **Thresholds:** |Δ iv/rv| median > 0.05 OR max > 0.10, sustained in ≥3 of a rolling 5 sessions;
  an OPRA coverage gap or a cheap-flip recurring on ≥2 distinct sessions in the rolling 5.
- **Amendment 2026-06-12 (operator-authorized — merging this edit is the authorization act): a
  cheap-flip COUNTS toward the tripwire only when the flipped name's same-session |Δ iv/rv| ≥ 0.02**
  (the flip-materiality floor). Sub-floor flips are still REPORTED per session (`flips` vs
  `material_flips` in `gate_dualread_report` — the close-out review sees every flip; they just
  don't trip the wire); a flip whose delta is UNCOMPUTABLE (either arm's iv_rv missing) counts
  fail-closed. *Rationale (instrument correctness, never throughput):* the counter as originally
  pinned thresholded a continuous agreement — a name PARKED at the 1.20 line flips arms on noise
  indefinitely (NOC across soak sessions #130/#147: all four reads within 1.1915–1.2021,
  |Δ| ≤ 0.0091, flip direction REVERSED between sessions — a biased feed flips one way; IRDM left
  the boundary and stopped flipping), so the wire measured "the universe contains a boundary-parked
  name," not feed divergence — and once tripped it SATURATES (under coin-flip recurrence, 2-of-5
  stays tripped indefinitely), carrying zero further information for the close-out review it
  feeds. The 0.02 floor restores the wire to its purpose: it fires only when the feeds MATERIALLY
  disagree on the flipped name (0.02 = the GEV-scale genuine read gap from the 2026-06-09 probe;
  well under the 0.05/0.10 distribution thresholds, which are UNCHANGED — as are the coverage-gap
  wire, `veto-feed-entitlement`, and the inline `veto-dualread-disagree`, so entry-time protection
  on ANY arm-disagreeing evaluated name is untouched and capital never rides this noise).
  **DISCLOSURE:** this floor was set AFTER the flip wire fired (two sessions of data) and
  RECLASSIFIES soak sessions #130/#147 to clean (observed flips NOC×2 / IRDM×1, all |Δ| ≤ 0.0132 —
  all sub-floor), un-blocking the PR-B sequencing (CGS §6) — the named beneficiary. The defense
  rests on the instrument-correctness rationale above. Future changes to this floor are again
  dated operator edits.
- **Fail-closed responses (pre-committed):**
  1. An arm-disagreeing EVALUATED name (the two feeds disagree on `cheap` at decision time) →
     **`veto-dualread-disagree`** — no entry on that name pending investigation. This rule
     **auto-lapses** at the dated close-out `config.data_feed.dualread_disagree_veto_until`
     (set ~+30 days at the flip); renewal is a deliberate dated edit — the INDICATIVE shadow
     never holds indefinite veto power over the gate-of-record. The rule can only VETO
     (tighten); the shadow arm never authorizes.
  2. A recurring threshold breach per above → **revert `option_gate`→indicative** — itself a
     record-segmenting provenance event (`runs.data_feed`) — plus a page. **[Superseded 2026-06-22
     by the per-class split amendment below — the |Δ iv/rv| wire is the SOLE revert trigger;
     gap / flip / entitlement route to feasibility / investigate / feed-wide-hold.]**
- **Duration:** ≥10 L1 sessions of dual-read before the dated close-out review; weekly review
  cadence; **one named reporting surface** = `gate_dualread_report` (tested, value-pinned) + its
  dashboard panel; the close-out decision (drop the shadow arm / renew the veto rule / revert) is
  a dated, documented operator decision.
- **Amendment — the dual-read close-out (drafted BLIND 2026-06-17/18 as
  `records/2026-07-10_closeout_s5_amendment_DRAFT.md`; FROZEN 2026-06-22, brought forward from the
  planned 2026-07-10 close-out — operator-authorized via this merge):** response (2)'s single
  "recurring threshold breach → revert" is SUPERSEDED by a response SPLIT by breach mechanism. One
  response was bound to three structurally different breaches — coherent for a feed-*trust* breach
  (OPRA noisy → fall back to the validated prior feed), **incoherent for a coverage gap** (OPRA has
  no tradeable wing; reverting would restore the phantom coverage the gate correctly refuses).

  | Wire | Trip | Response |
  |---|---|---|
  | **\|Δ iv/rv\|** | med>0.05 ∨ max>0.10, ≥3/5 | `revert option_gate→indicative` + page. **The SOLE revert trigger.** |
  | **cheap-flip (material, \|Δ\|≥0.02)** | ≥2/5 | investigate + page; **no revert** (magnitude is the Δ wire's job). Rising-edge, debounced. |
  | **coverage-gap** | per class ↓ | OPRA can't structure — the `note` reason decides the class ↓ |

  **Coverage-gap partition** (reason in the dual-read `note`): **structural-absence**
  (`select_structure` reasons; ≥2/5) → feasibility page, **no revert**, the name stays in the basket
  (the gate fail-closes it; the sweep's `structured=0 + note` row IS the feasibility record — no
  separate §2.3 re-run); **entitlement** (a `feeds.classify_feed_error` entitlement class;
  per-session, feed-wide) → the §7 feed-wide hold + one page/session, **no revert** (never the silent
  downgrade §7 forbids); **transient** (≤1/5 log; escalates to a per-name page at ≥2/5). Heterogeneous
  reasons do NOT aggregate (1 structural + 1 transient + 1 entitlement trips none of absence/transient).
  **One name's flaky chain NEVER raises the feed-wide entitlement state** (only a
  `classify_feed_error`-entitlement arm raises it).

  **Debounce:** the structural-absence and material-flip pages are rising-edge, suppressed until
  **≥4 consecutive** clear sessions (the concrete count — derived from the rolling-5 so a single lift
  can't immediately re-trip a flickering name) or a disposition; the entitlement state is **never**
  debounced (one page/session while down — an outage is ongoing-actionable).

  **Carve-out ledger** (what the *revert trigger* reserves; the other wires still fire, they just don't
  revert): 2026-06-12 flip-materiality floor (\|Δ\|≥0.02, sub-floor not counted) · 2026-07-10
  coverage-gap split (structural→feasibility, entitlement→feed-wide hold, transient→log/escalate; none
  revert) · 2026-07-10 cheap-flip demotion (revert is the \|Δ iv/rv\| wire's exclusive job).
  **Reserved revert-trigger space: the \|Δ iv/rv\| wire ALONE.**

  **Anti-HARK:** the amendment text was committed BLIND weeks before the close-out, so the close-out's
  Δ / material-flip population cannot reshape the response table after the fact; UROY's then-tripped
  `gap_tripped` reclassifies to coverage-feasibility and exits the revert-trigger population. The
  runtime mechanism that EXECUTES this table is **#72** (`dualread_executor.py`, Phases 1–2 active; the
  Δ-wire revert latch behind `config.data_feed.dualread_revert_enabled`, default false until the OPRA
  deploy-gates clear).

## 6. Storage + the coverage guard

The dual-read lands in its own table (**migration 0014 `gate_dualread`**: run_id, evaluated_at,
symbol, feed, structured, iv_rv, otm_skew, cheap, wing, note) — the gate-of-record rows (OPRA)
come from the actual verdicts; the INDICATIVE shadow rows are additive fetches, **fail-soft**
(a shadow failure writes a structured=0 row with the error note — never blocks the cycle, never
silently vanishes). **The coverage guard reports BOTH arms' success rates** — a silently-empty
shadow arm must not masquerade as agreement (the free feed is now the shadow; the lesson cuts
both ways). `runs.data_feed` keeps per-run gate provenance unambiguous; the shadow never appears
there.

## 7. Entitlement-lapse = a HARD merge-blocker in the build PR

An OPRA fetch failure classified `entitlement` by `feeds.classify_feed_error` →
**`veto-feed-entitlement`** on that candidate + ONE in-app page per run (the soft-trip
precedent) — **never a silent INDICATIVE downgrade** (single-name downgrade is impossible by
construction: a failed premium fetch DROPS the candidate; the gate is fail-closed). A `transient`
classification → the existing veto-data path + a log line. The L2 monitor stays pinned to the
free feed (risk marking degrades-and-continues; never blinded).

## 8. HARK leash + interim acceptance + out of scope

- **Never** raise `account_equity`, the per-name 1%, the cluster 2%, the position limit, or
  contract-affordability mechanics to manufacture the first trade — the cap is the demonstrated
  blocker (GEV $8,125; RKLB $2,866 at L1 #111) and the cap-vs-contract-granularity question
  remains a named, separately-pre-registered known-open (`PREREG_UNIVERSE_CURATION §9`).
- **Interim-window acceptance (updated 2026-06-10):** the OLD cheapness-aware council runs live
  every L1 until PR-B ships the CGS §10.7 config (post-soak, CGS §6 sequencing: ≥2 clean OPRA
  L1s first). Any pre-PR-B entry is an old-config record — accepted and bounded (paper, frozen
  caps, per-run `runs.data_feed` + `model_mix` segmentation).
- **Out of scope:** thin-name OPRA coverage characterization (the §5 tripwires surface it
  empirically); IV-baseline graduation (stays shadow-only, PREREG §4b); PROD entitlement
  verification (T4 checklist); `equity_bars` (done, SIP); the L1-timing question (separately
  deferred).
