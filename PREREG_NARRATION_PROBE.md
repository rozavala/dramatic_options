# PREREG — the narration probe (Stage-2 of the theme-generation layer)

**Status: FROZEN by the merge of this PR (2026-06-17).** The operator set the two blind values to the
proposed: **§5 `high-overlap` cutoff = 0.80**; **§7 expected rejection ~15–35% with a ≥20-generated-claim
N-floor on "0% = inert".** rev-6 authored the two §6 smoke-test exemplars as concrete claim objects +
de-placeholdered §7 + folded two forward notes (the §4 classifier-bar pin-blind discipline, the §3
schema-contract scope); rev-5 landed the two P2 pins + P3 folds + the row-level PR-B verification.
rev-4 was the
**feasibility-check pivot**: the mandated pre-merge feasibility check (live model-availability + a
GDELT onset enumeration) found the cutoff-straddle calibration is **not constructible for the deploy
theme class**, so the probe ships **fiat-permissive** — the threshold is a deterministic RULE pinned
blind, its single cutoff value by fiat, with a falsifiable behavior band + a non-perishable scorer
smoke test. **Part B (the blind calibration run) collapses; the straddle / GDELT / cutoff-table
machinery moves to the §8 high-bar escalation spec.** This is the **correct design here (§2), not a
weak fallback.** Companion to `PREREG_THEME_GENERATION_STUB`. Converged over six red-team rounds
(log §9). Cites only the committed record.

---

## 1. Cleared precondition + what the probe is (and is not)

**Ordering MET.** `PREREG_COUNCIL_GATE_SEPARATION` §10.8 (2026-06-10): **0/16 = SCARCITY** — verbatim,
*"the theme-generation stub's ordering condition is MET on the mandate side."* This is the
generation-layer's own pre-reg.

The probe is the deterministic **under-narration funnel** on Stage-1 generator output — it measures
narration so a genuinely-quiet mechanism clears the council's `under_narrated` bar **without loosening
the bar** (the HARK leash: measure the criterion, never relax it).

**It is ADDITIVE, not a supersession (rev-4).** A fiat-permissive *uncalibrated* probe is too weak to
*replace* the working under-narration sensor — the evidence-grounding **coverage counts** (Alpaca 7d/
90d, `PREREG_EVIDENCE_GROUNDING` §2c), which STAY the live sensor. The probe rides **on top** as an
extra permissive funnel on generator output; supersession is deferred to the §8 escalation. So
shipping it is **not a regression** (no working sensor is swapped for an uncalibrated one), and it
keeps grounding-first correct.

---

## 2. Why fiat-permissive is the CORRECT design (the finding + two independent reasons)

**The feasibility finding (this revision, verified live):** the oldest model any provider still serves
has a cutoff ≈ **Oct-2023** (OpenAI `o1`; everything else 2024+), so straddle onsets must be ≥Apr-2024
(≥1 model) / ≥~Feb-2025 (≥2-vendor). More decisively, the 3×-spike onset rule cleanly separates only
**sharp fads** (genuine pre-onset silence → loud after); the deploy class is **slow secular ramps**
(uranium, copper, AI-power), which have **no clean quiet state** — the narrative thickens gradually,
so even a 2022-cutoff model carries partial narration of what we care about (the uranium squeeze was
2021, the copper-deficit thesis older). So the straddle won't separate the deploy class under **any**
model bracket; the open-model anchor (§8) fixes only the model *floor*, the lesser problem. The
straddle calibration is therefore not constructible for this theme class.

**That does not weaken the probe — fiat-permissive is correct on two independent grounds:**

- **(a) The loss asymmetry mandates a permissive bias regardless of calibration.** `false-narrated`
  (rejecting a genuinely under-narrated claim) is **invisible** by construction — rejected claims
  never reach the council, so you never learn the probe killed a good one. `false-quiet` is **caught**
  by the live council's under-narrated test. The only observable failure is the council catching
  narrated claims the probe *passed*; the costly direction is unobservable → you bias permissive. A
  perishable, fad-biased calibration would only have produced a threshold the loss structure says not
  to trust to reject much anyway.
- **(b) Dropping the straddle does NOT weaken anti-HARK.** Pre-registration requires the **threshold
  pinned before data**, not **calibration before data**. A fiat threshold pinned blind in frozen text,
  with a pre-committed expected-behavior band (§7), satisfies that. The HARK failure mode is shipping
  with *no* threshold, seeing generator output, then picking one that "looks right" —
  fiat-permissive-pinned-blind is the opposite of that.

---

## 3. Register unit (stub Q1) — mechanism-claim + the FROZEN generator schema

The scored unit is a **mechanism claim**, NOT a theme label. The schema is **frozen here, prescriptive
and forward-binding on the Stage-1 generator** (it MUST emit these fields):

```jsonc
{
  "claim_id":   "str",
  "statement":  "one sentence: <driver> → <effect> → <entity class>",   // GENERATOR-CORE
  "named_entities": [{"canonical": "GE Vernova", "ticker": "GEV", "aliases": ["Vernova"]}],  // §4 leg 1
  "mechanism_direction": {"vocab": "shortage|surplus|backlog_growth|capex_up|supply_cut|demand_surge|capacity_constraint|...",
                          "sign": "+|-"},                                // §4 leg 2
  "headline_quantities": [{"metric": "transformer lead time", "value": "~50->~120 weeks", "bucket": "weeks_x2plus"}],  // §4 leg 3
  "provenance": "generated"
}
```

(The rev-2/3 calibration-only fields `onset_theme` / `in_live_book` are **removed from v1** — they
served the cutoff-straddle set construction, which now lives in §8 escalation.)

**Scope note (what the freeze commits):** freezing this pre-reg locks the **generator↔probe schema
contract** — the §3 generator-core fields, the `mechanism_direction` vocab, and the `headline_quantities`
buckets — not just the probe's threshold; the July Stage-1 generator inherits it as a hard output
contract. The schema has been stable since rev-2, so this is intended (the probe defines the interface
it consumes) — but settle any doubt the generator can cleanly emit the quantity buckets / direction
vocab BEFORE freezing. The threshold itself is genuinely probe-only and lower-risk.

---

## 4. Field set + deterministic scorer (stub Q2) — survives the freeze

A model describes each mechanism (free-text); the description is scored on **accuracy-of-specifics
overlap** against three fields — the things that circulate when a theme is narrated. **Citation-only
IDs are forbidden as scoring targets** (corpus-inaccessible + a gaming channel); **fluency is not a
field** (models confabulate fluently about quiet themes).

| field | match rule | determinism |
|---|---|---|
| `named_entities` | alias/ticker match (claim aliases ∪ EDGAR `company_tickers`, 10.4k names) | **fully deterministic** |
| `mechanism_direction` | a ring-fenced, pinned, decorrelated classifier maps prose → (vocab, sign); match = exact | classifier-labeled |
| `headline_quantities` | numeric parse vs the claim value within the bucket tolerance (±1 bucket / same-OOM) | **fully deterministic** |

**Elicitation × scoring = FROZEN B** (rev-3 #4): free-text elicitation + a ring-fenced narrow
classifier for `mechanism_direction` sign + responsiveness triage **only** (controlled-vocab output,
decorrelated ≥2-vendor, pinned model+prompt-sha, never the verdict); entity + quantity scoring stay
fully deterministic. Field weights **0.40 / 0.30 / 0.30** (favoring the deterministic legs). Per-field
overlaps are reported independently. `mechanism_direction` is the softest leg → a **two-scorer
agreement check** on its labels (rev-3). **Classifier validation is a pre-deploy precondition**: a
small hand-labeled set must validate sign + responsiveness (incl. adjacent-vocab cases) to a pinned
agreement bar before the probe is wired live. **That agreement bar must itself be pinned BLIND in the
July probe-build spec — before the hand-labeled validation runs, not after seeing the classifier's
agreement number** (same HARK discipline; flagged here so it isn't a post-hoc build-time pick).

Worked examples (mandatory, in the frozen schema) — `ai_power`, `nuclear_fuel`, and a non-energy
`glp1_obesity` claim — are retained from rev-3 as the schema demonstration + the adversarial-paraphrase
case a deterministic-only lexicon would miss.

---

## 5. The fiat-permissive threshold — a deterministic RULE, value by fiat (replaces the calibration)

The threshold is a **deterministic rule**; only its single cutoff value is by fiat.

- **RULE (deterministic, unit-tested):** a claim is **NARRATED → rejected** iff **high-overlap on ALL
  THREE fields simultaneously AND ≥2 deploy-roster models concur.** Permissive *by construction* —
  requiring all-three-fields AND ≥2-model concurrence to reject biases strongly toward keep /
  funnel-forward, exactly as the §2 loss asymmetry demands.
- **Why the conjunction (the design point, not just "permissive"):** it makes `headline_quantities`
  the load-bearing protector of under-narrated *specifics* — the stub's "narrated-macro /
  un-narrated-expression" case. A claim on a well-known entity inside a narrated macro theme (GEV's
  transformer backlog inside the everywhere-narrated AI-power story) reads entity-high and
  direction-high; the ONLY thing stopping a wrong reject is the *quantity* leg — if the specific figure
  (lead times ~50→~120 weeks) isn't in free recall, quantity-overlap is low, the conjunction fails,
  the claim passes to the council. The rule is permissive **in the direction the stub cares about**.
- **The only fiat number (pinned BLIND, §10):** `high-overlap` = per-LIST-field overlap ≥ **0.80**
  (`named_entities`, `headline_quantities`). `mechanism_direction` is a single `(vocab, sign)` with
  EXACT match, so "high-overlap" on it = exact match (the 0.80 fraction does not apply to a
  single-valued field). `concur` = **≥2** of the deploy roster each clear the all-three bar.
- **Empty/absent field ⇒ NOT high-overlap ⇒ no rejection (permissive-correct; REQUIRED unit test).**
  `headline_quantities` may legitimately be `[]` (a structural NRC-docket / FERC-queue mechanism with
  no clean headline number). An absent/empty field CANNOT be high-overlap, so the all-three conjunction
  is unsatisfiable and the claim passes to the council. Matches the codebase's sparse-tolerant
  precedent (an unfiled value is omitted, never fabricated, never zeroed — `PREREG_EVIDENCE_GROUNDING`).
  This is the **load-bearing** case: the alternative ("evaluate present fields only, reject on two")
  would silently reject exactly the quantity-less structural claims the quantity leg exists to protect
  — a failure in the invisible false-narrated direction.
- **Deploy roster:** the live council models, **exact-version-pinned via the `runs.model_mix` stamp**
  (PR-B) — not drift-prone aliases (current: gemini / xai / anthropic proposer/adversary/strategist).

This keeps the scorer discipline (which the straddle was never the source of) fully intact; only the
cutoff *value* is asserted rather than calibrated.

---

## 6. Non-perishable scorer smoke test (a unit test, NOT a calibration)

Verifies the **scorer functions** — the one thing the straddle would have incidentally confirmed —
with no perishable machinery. **Two exemplars, pinned here as concrete claim objects** (a CI unit test,
re-runnable forever; no model-vintage dependence beyond the deploy roster). If it fails, the scorer —
not a theme — is broken.

**(A) Blatantly-narrated → MUST score high-overlap on all three fields.** Its `headline_quantities` is a
genuinely-circulated figure, so an all-three-high pass is the scorer working, not a quantity-leg
artifact:
```jsonc
{ "claim_id": "smoke_narrated_nvda",
  "statement": "Hyperscaler AI-training capex -> NVIDIA data-center GPU dominance -> sustained accelerator demand + pricing power.",
  "named_entities": [{"canonical": "NVIDIA", "ticker": "NVDA", "aliases": ["Nvidia"]}],
  "mechanism_direction": {"vocab": "demand_surge", "sign": "+"},
  "headline_quantities": [{"metric": "data-center segment quarterly revenue", "value": "~$30B", "bucket": "usd_tens_of_billions"}],
  "provenance": "generated" }
```

**(B) Deliberately-obscure INVENTED → MUST score low-overlap** (FICTIONAL — `ALDP` is not a real
issuer; no deploy model can surface fabricated entities/figures, so all three legs read low):
```jsonc
{ "claim_id": "smoke_obscure_invented",
  "statement": "Aldermarsh Photonics' sub-threshold GaN lattice-anneal step collapses LED-driver-IC defect rates, forcing multi-quarter backlogs at boutique driver foundries.",
  "named_entities": [{"canonical": "Aldermarsh Photonics", "ticker": "ALDP", "aliases": ["Aldermarsh"]}],
  "mechanism_direction": {"vocab": "backlog_growth", "sign": "+"},
  "headline_quantities": [{"metric": "driver-IC defect-rate reduction", "value": "~40%", "bucket": "pct_25_50"}],
  "provenance": "generated" }
```

---

## 7. Falsifiable rejection-rate band (the §-yield pattern, one floor down — keeps "uncalibrated" honest)

Pinned **BLIND** before the generator runs (you can't calibrate the value, but you pre-commit what its
behavior must look like + flag degeneracy):
- **expected ~[15–35%]** of generated claims rejected by the probe (proposed — **operator's blind
  call**; the structural corpus skews under-narrated, but recall bias means a meaningful minority reads
  narrated, so the rate is low-to-moderate, not near-zero);
- **0% rejected = the probe is INERT** (threshold too permissive / a no-op) → investigate, do NOT bank
  it as doing work;
- **very-high %** (mis-set tight) → investigate.

**Read over a CUMULATIVE window with an N-floor before "0% = inert" is actionable** — proposed
**≥20 generated claims** (**operator's blind call**; the value that *matters* in §7, per the review).
At the stub's low per-run yield (~1–5 claims) that is a few weeks of running, not months: high enough
that 0% isn't noise, low enough that the inert-flag can fire in usable time. This is the same
N-sensitivity that retired the straddle's `p<.05` — it did not vanish when calibration was dropped, it
migrated to the surviving band.

---

## 8. Escalation — the high-bar future (#2 AND #3 together, never either alone)

**Trigger (the one observable signal):** the live council backstop **repeatedly catching obvious-
narrated claims the probe passed** ⇒ too permissive ⇒ escalate. (The costly direction, false-narrated,
stays unobservable — so escalation is keyed on the *observable* failure.)

**Sensitivity caveat (named, not oversold):** the deploy roster IS the council (§5), so the probe is
partly a cheaper early pass of the council's own `under_narrated` criterion — probe and council errors
are **positively correlated** (the same models that pass a claim through the probe are likelier to wave
it through the council). So this trigger is **less sensitive** than independence would give. It is
bounded (council judgment is holistic; the probe's is specifics-overlap, so some independence
survives), and the roster is unchanged on purpose — narration-maximal describers are the right scorer
choice. Named here so the trigger's reach isn't overstated.

**Escalation = #2 + #3 TOGETHER** (neither alone reaches the representativeness mismatch):
- **#2 self-hosted open old-cutoff model** (Llama-2-class ~2022 + a 2nd distinct open model) — restores
  the model floor + ≥2-vendor on the quiet side; a one-time GPU-day run pointed at a local endpoint;
  the within-model cutoff-vs-capability contrast (same model articulates pre-cutoff specifics, fails
  post-cutoff) isolates cutoff-effect from capability-effect more cleanly than the cross-model
  straddle. **Unvalidated; capability confound remains.**
- **#3 a level-shift / trend-change onset detector** (the 3×-spike rule CANNOT label slow secular
  onsets) **+ mechanism-level secular onset labels matched to the generator's emitted granularity**
  (which does not exist until Stage-1 is built).

**Why both:** #2 fixes only the floor (the lesser problem); the binding problem is the representativeness
mismatch (secular ramps have no clean quiet state), which needs #3's detector + generator-matched
labels. High bar **by design** — fiat-permissive is very likely sufficient.

**Dropped from v1 into this spec:** the cutoff-straddle; the **GDELT onset pull** (it was scoped to
calibration-set construction ONLY — the live under-narration input is coverage-counts, not GDELT, so
nothing is orphaned); the per-model cutoff table; the separation criterion + validity gate + Part B.

---

## 9. Red-team log

- **Rev 1** — three MECE passes (construct validity / measurement-artifact / HARK-ordering).
- **Rev 2** — a 12-item adoption-audit + new-seams pass (gate-floor split, prescriptive schema, the
  elicitation fork, basement check, per-field gating, non-book seed, GDELT data-quality, …).
- **Rev 3** — three structural seams the rev-2 choices created: capability drift (current-model quiet
  control), classifier validation as a precondition, the B-(i) onset-vs-feasibility recourse; + polish
  (fork→B, schema field-scoping, cutoff table).
- **Rev 4 — the mandated feasibility check ran and pivoted the design.** Live model-availability
  (oldest cutoff ≈ Oct-2023 / o1) + a GDELT onset enumeration showed the cutoff-straddle separates only
  sharp fads, not the slow secular **deploy class** (representativeness mismatch — **not** thin-N). →
  pivot to **fiat-permissive** (correct per the §2 loss asymmetry + anti-HARK-intact); **#2 pulled back**
  from "do-if-N-thin" to escalation-only-paired-with-#3; the broad-query re-run **skipped** (it resolves
  the wrong uncertainty — the floor is model-availability and the gradual-ramp failure is
  detector×theme-shape, both query-independent). Part B + the straddle machinery → §8.
- **Rev 5 — freeze-prep pins (post-convergence; one-liners).** P2: (i) §5 the empty/absent-field rule
  (`headline_quantities=[]` ⇒ not-high ⇒ no reject — the load-bearing protector of quantity-less
  structural claims, a required unit test); (ii) §7 a cumulative N-floor on "0% = inert" (the straddle's
  p<.05 N-sensitivity migrated to the surviving band). P3: §5 the conjunction-protects-specifics
  rationale + `mechanism_direction` is exact-match-not-a-fraction; §6 the narrated exemplar must carry a
  circulated headline quantity; §8 the probe↔council positive-error-correlation caveat (the deploy
  roster IS the council → the trigger is less sensitive than independence). + §11 PR-B verified at the
  ROW level (booleans parsed typed on real data #182/#199; the §10.9 include-edge stays unexercised at
  0 includes).
- **Rev 6 — freeze-prep authoring (from the §10-precision review).** The "only two open items" preamble
  undersold the confirm-set: the §6 exemplars were unauthored (a category, not a value; the obscure one
  absent) and a CI fixture can't ship as a placeholder → **authored both as concrete claim objects**
  (`smoke_narrated_nvda` with a circulated quantity; the fictional `smoke_obscure_invented`).
  De-placeholdered §7 (~15–35% + a ≥20-claim N-floor, the value that matters). Folded two
  forward-discipline notes: the §4 classifier-agreement bar must be pinned BLIND in the July
  probe-build spec (not a post-hoc pick); §3 the freeze locks the generator↔probe schema CONTRACT (vocab
  + buckets), not just the threshold. No design change — closing the confirm-set.

---

## 10. Confirm-set — ALL FROZEN at merge (was: must-land-before-merge)

- [x] **§4** field weights **0.40/0.30/0.30** + quantity buckets — FROZEN.
- [x] **§5** the fiat threshold: the RULE (all-three-high ∧ ≥2-concur) + the `high-overlap` cutoff
  value **0.80** + the empty/absent-field ⇒ no-reject unit test — FROZEN (operator set 0.80).
- [x] **§6** the smoke-test exemplars — AUTHORED as concrete claim objects (`smoke_narrated_nvda` +
  the fictional `smoke_obscure_invented`); the required CI unit test asserts A→high / B→low.
- [x] **§7** the rejection-rate band — **~15–35% expected; 0% = inert only past the ≥20-claim N-floor**
  — FROZEN (operator set the proposed).
- [x] **§5** deploy roster = the live council via the `model_mix` stamp (exact-version).
- [x] **§4** elicitation fork — FROZEN B.

**Dropped (→ §8 escalation):** GDELT K/M/baseline + queries, per-model cutoff table, separation-criterion
floor, p<.05 (these were Part-B / straddle pins; moot once Part B collapses).

---

## 11. Sequencing + open

- **Ordering MET** (§10.8, 0/16). The freeze sits behind PR-B window #1 verifying clean + the grounding
  leg landing (`PREREG_EVIDENCE_GROUNDING` §7) — **both DONE** (grounding: PR #58, 2026-06-15).
  PR-B verified at the ROW level (not just the `ROUNDTRIP_CONFIRMED` grade): the §10.7 strategist
  tri-criteria booleans **parsed as typed bools on real data** — L1 #182 (8 names: NVDA/RKLB/PL/VRT/
  RTX/FLNC/UUUU/PWR carry `{under_narrated, at_inflection, include}`) and #199 (7 names, incl. VRT
  `at_inflection=True`), per `council_proposals.rationale.strategist`. **Nuance:** both runs had 0
  includes, so the §10.9 *include-edge* classification (absent booleans **on an include** = parse_error)
  remains live-unexercised — a fail-closed guard awaiting its first include, not a gap; the boolean
  parse itself is confirmed clean. So the freeze is sequencing-unblocked.
- **Build order inside the pipeline:** generator-first (Stage-1, July-gated), **probe-second** (it acts
  on generator output). The probe is additive (§1).
- **SET at freeze (the two blind calls):** §5 `high-overlap` cutoff = **0.80**; §7 expected rejection
  **~15–35%** with a **≥20-generated-claim N-floor** on "0% = inert".
- stub **Q3** (demote rule / dormancy write-path) — still deferred (a Stage-3/ops concern, §8).
