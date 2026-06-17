# PREREG — the narration probe (Stage-2 of the theme-generation layer)

**Status: DRAFT for operator review (rev 4, 2026-06-17). FREEZES ON MERGE.** rev-4 is the
**feasibility-check pivot**: the mandated pre-merge feasibility check (live model-availability + a
GDELT onset enumeration) found the cutoff-straddle calibration is **not constructible for the deploy
theme class**, so the probe ships **fiat-permissive** — the threshold is a deterministic RULE pinned
blind, its single cutoff value by fiat, with a falsifiable behavior band + a non-perishable scorer
smoke test. **Part B (the blind calibration run) collapses; the straddle / GDELT / cutoff-table
machinery moves to the §8 high-bar escalation spec.** This is the **correct design here (§2), not a
weak fallback.** Companion to `PREREG_THEME_GENERATION_STUB`. Converged over four red-team rounds
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
agreement bar before the probe is wired live.

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
- **The only fiat number (pinned BLIND, §10):** `high-overlap` = per-field overlap ≥ **0.80**;
  `concur` = **≥2** of the deploy roster each clear the all-three bar.
- **Deploy roster:** the live council models, **exact-version-pinned via the `runs.model_mix` stamp**
  (PR-B) — not drift-prone aliases (current: gemini / xai / anthropic proposer/adversary/strategist).

This keeps the scorer discipline (which the straddle was never the source of) fully intact; only the
cutoff *value* is asserted rather than calibrated.

---

## 6. Non-perishable scorer smoke test (a unit test, NOT a calibration)

Verifies the **scorer functions** — the one thing the straddle would have incidentally confirmed —
with no perishable machinery:
- a **blatantly-narrated** exemplar ("NVDA — AI-accelerator dominance") MUST score high-overlap on all
  three fields;
- a **deliberately-obscure invented** mechanism MUST score low-overlap.

Pinned exemplars; a CI unit test, re-runnable forever (no model-vintage dependence beyond the deploy
roster). If it fails, the scorer — not a theme — is broken.

---

## 7. Falsifiable rejection-rate band (the §-yield pattern, one floor down — keeps "uncalibrated" honest)

Pinned **BLIND** before the generator runs (you can't calibrate the value, but you pre-commit what its
behavior must look like + flag degeneracy):
- **expected ~[X%]** of generated claims rejected by the probe;
- **0% rejected = the probe is INERT** (threshold too permissive / a no-op) → investigate, do NOT bank
  it as doing work;
- **very-high %** (mis-set tight) → investigate.

---

## 8. Escalation — the high-bar future (#2 AND #3 together, never either alone)

**Trigger (the one observable signal):** the live council backstop **repeatedly catching obvious-
narrated claims the probe passed** ⇒ too permissive ⇒ escalate. (The costly direction, false-narrated,
stays unobservable — so escalation is keyed on the *observable* failure.)

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

---

## 10. Must-land-before-merge (the SHRUNK confirm-set; all pinned BLIND)

- [ ] **§4** field weights (0.40/0.30/0.30) + quantity buckets.
- [ ] **§5** the fiat threshold: the RULE (all-three-high ∧ ≥2-concur) + the `high-overlap` cutoff
  value (**0.80** proposed — **operator's blind call**).
- [ ] **§6** the smoke-test exemplars (the narrated + the obscure-invented).
- [ ] **§7** the rejection-rate band (**expected ~[X%]; 0% = inert** — **operator's blind call**).
- [ ] **§5** deploy roster = the live council via the `model_mix` stamp (exact-version).
- [x] **§4** elicitation fork — FROZEN B.

**Dropped (→ §8 escalation):** GDELT K/M/baseline + queries, per-model cutoff table, separation-criterion
floor, p<.05 (these were Part-B / straddle pins; moot once Part B collapses).

---

## 11. Sequencing + open

- **Ordering MET** (§10.8, 0/16). The freeze sits behind PR-B window #1 verifying clean + the grounding
  leg landing (`PREREG_EVIDENCE_GROUNDING` §7) — **both DONE** (PR #58, 2026-06-15; L1 #182/#199 both
  grounded `ROUNDTRIP_CONFIRMED`). So the freeze is sequencing-unblocked.
- **Build order inside the pipeline:** generator-first (Stage-1, July-gated), **probe-second** (it acts
  on generator output). The probe is additive (§1).
- **Open (operator's blind calls at merge):** the §5 `high-overlap` cutoff value + the §7 rejection-rate
  band.
- stub **Q3** (demote rule / dormancy write-path) — still deferred.
