# PREREG — the narration probe (Stage-2 of the theme-generation layer): the calibration freeze

**Status: DRAFT for operator review (2026-06-17). Part A (the protocol) FREEZES ON MERGE — nothing
below is committed until then. Part B (the operating threshold NUMBER) is a SEPARATE dated blind run
AFTER merge.** Companion to `PREREG_THEME_GENERATION_STUB` (the dated EXISTENCE/ORDERING/CONSTRAINTS
commitment, 2026-06-10); this is the **cold-critical core** of the generation layer's own pre-reg —
the one piece whose validity depends on being frozen before any generated candidate exists.
Self-red-teamed across three MECE passes (logged §9). Cites only the committed record.

---

## 1. Cleared precondition + why this is the next pinned item (lead, per §10.8)

**The ordering condition is MET.** `PREREG_COUNCIL_GATE_SEPARATION` §10.8 (re-tightened re-score,
2026-06-10): **0/16 = SCARCITY**, in-band for the 0/1 rule, and verbatim — *"the theme-generation
stub's ordering condition is MET on the mandate side (0/1 achieved) — its remaining gates are its own
pre-reg + the generation-layer design constraints."* This document is that pre-reg's cold core.

**Why the narration probe, and why now (§10.8's load-bearing finding):** the dominant abstention
reason inside the 0/16 was that *marker-only grounding cannot support the hardened tri-criteria* — the
council declines to assert **under-narrated** / at-a-genuine-inflection from price/vol markers, and the
mandate (correctly) demands evidence. §9 (`PREREG_EVIDENCE_GROUNDING`, FROZEN 2026-06-11) added the
**grounding** half (filed fundamentals for the structural/at-inflection legs). The **under-narrated**
leg has no deterministic sensor yet: today it is whatever the council can (not) infer. The narration
probe IS that sensor — it measures narration so a genuinely-quiet theme can clear the bar **without
loosening the bar** (the HARK leash holds: measure the criterion, never relax it).

**Why COLD (the imperative the two-part structure exists to honour):** the probe's operating threshold
is a fitted parameter. A threshold set after seeing what the generator emits — or after seeing which
candidates the gate/council admit — is HARKed. `PREREG_THEME_GENERATION_STUB` constraint #2 binds the
generator/probe **pair** jointly to one §10.4-style re-tightening, *neither component iterated against
the other's outputs, nor against admission or gate outcomes*. The probe must therefore be calibrated
on themes whose narration state is known **independently** of our pipeline (cutoff-straddling, §5),
and frozen before generation runs. Now is that window.

---

## 2. Two-part structure (mirrors §10.4 / §10.8: freeze-bands → run → record)

- **Part A — THIS freeze (spend-free, no LLM):** the protocol — register unit (§3), narration-diagnostic
  field set (§4), calibration-set construction + the reproducible onset procedure (§5), the overlap
  metric + separation criterion + the blind validity gate + the operating-threshold *rule* (§6), and
  the carried postures + freeze-gate bands (§7). Every decision rule is committed **without a number
  in front of it.**
- **Part B — a SEPARATE dated run AFTER merge (the §10.8 cite-before-record pattern):**
  - (i) the **deterministic set-construction run** (GDELT only, no LLM) computes the verified onset
    dates and assembles the cutoff-straddling set per §5;
  - (ii) the **LLM probe run** scores the set per §6 and pins the **operating threshold** (the stub's
    open Q4 number);
  - one pass; recorded as a dated appendix here; **no §3–§7 text is re-touched after the number is
    seen** (§10.4). Part B is STILL blind: it probes the KNOWN calibration themes, never a generated
    candidate.

This separation is the whole point: "no LLM spend this week" and "pin Q4" are in tension only if they
collapse into one step. They do not — the protocol freezes now; the number is recorded later, still
blind.

---

## 3. Register unit (stub Q1) — mechanism-claim granularity (PINNED)

The probed / scored / (eventually) demoted unit is a **mechanism claim**, NOT a theme label. The stub
is explicit that *"a theme-level threshold doesn't transfer"*, so the calibration set is built at this
same granularity.

A **mechanism claim** names: a **driver → effect** causal step, the **entities** it runs through, and
its **direction/sign**. Worked contrast:

- ✅ mechanism claim: *"AI-datacenter buildout → transformer & medium-voltage switchgear shortage →
  multi-year order backlog at the grid-equipment OEMs."* (driver, effect, direction, entity class)
- ❌ theme label: *"AI power."* (a sector tag — narrated-macro by construction; the un-narrated
  expression lives at the mechanism level inside it, the copper-not-rockets distinction.)

The generator (Stage 1, later) emits claims in this unit; the calibration claims (§5) are authored in
the **identical schema and format** the generator will emit (the transfer requirement — see the §9
red-team pass 1). The schema's narration-diagnostic fields are §4.

---

## 4. The narration-diagnostic field set (stub Q2) — what overlap is scored over (PINNED)

A no-documents model is asked to describe each mechanism claim; its description is scored on
**accuracy-of-specifics overlap** against three schema fields — the things that **circulate when a
theme is narrated**:

| field | what it captures | deterministic match rule |
|---|---|---|
| `named_entities` | the specific companies / actors / inputs central to the mechanism (stored with aliases + tickers) | case-insensitive alias/ticker match; score = fraction of the claim's entities the description correctly names |
| `mechanism_direction` | the causal direction + **sign** from a small controlled vocabulary (shortage/surplus, backlog-growth, capex-up, supply-cut, …) | the description must reproduce the sign; binary per claim |
| `headline_quantities` | the magnitudes in circulation (e.g. "lead times ~50→~120 weeks", "+30% capex") | match if within a pinned tolerance (same order of magnitude / ±1 controlled bucket) |

**Scoring is DETERMINISTIC** (entity/sign/quantity matching) — **no LLM judge in the measurement
loop** (an LLM-judge is itself a HARK + drift surface; a deterministic scorer is reproducible and
auditable). The overlap score ∈ [0,1] combines the three fields by a pinned weighting (Part A fixes
the form; the weights are pinned here, not tuned in Part B).

**FORBIDDEN scoring targets (the gaming channel, carried from the stub):** citation-verification-only
identifiers — docket numbers, FERC queue IDs, filing accession numbers. They are corpus-inaccessible
by construction, so scoring on them makes *everything* read quiet AND hands the future generator a
gaming channel (cite obscure IDs → read quiet). **Fluency is NOT a field** — models confabulate
fluently about quiet themes, so a fluency probe false-rejects its own target class (the stub's warning).

---

## 5. Calibration-set construction (stub Q5) — the load-bearing surface

### 5.1 Cutoff-straddling, the theme as its own control
Each calibration mechanism comes from a theme with a **verifiable narration onset**, probed across
models whose knowledge cutoffs **bracket** that onset:
- a **pre-onset** reading (model cutoff before onset) is the theme's **quiet state** → expected LOW
  overlap (the model cannot know specifics that weren't yet in circulation);
- a **post-onset** reading (model cutoff after onset) is the **narrated state** → expected HIGH overlap.

The same mechanism supplies both states, so **cross-theme idiosyncrasy is controlled by construction**
— directly answering the stub's warning that *hand-picked contemporary "known-quiet" exemplars would
resemble our holdings = a HARK vector*. **No current/hand-picked quiet themes enter the set.** Seed
themes (verifiable onsets): uranium/nuclear (~2023), AI-power/grid (~2024), plus ≥1 more per onset era
to avoid single-theme dependence; the FINAL list is whatever the §5.3 procedure admits, not this prose.

### 5.2 The core assumption, stated so it can be attacked
The calibration's validity rests on: *a current model's specific-overlap on a current under-narrated
mechanism ≈ a pre-onset model's overlap on a pre-onset mechanism.* This is an assumption, not a
theorem. Its **ceiling check** (committed blind, §6): the **narrated-state** readings MUST show high
overlap — if a post-onset model cannot reproduce a narrated mechanism's specifics, the *metric* is
broken, not the theme, and the probe is unfit (do not deploy; do not loosen).

### 5.3 Onset verification — REPRODUCIBLE, not eyeballed (the red-team's main earn)
"Verifiable onset" must be a computed date, or "verifiable" does no work and the idiosyncrasy control
can't be audited.
- **Source:** the GDELT DOC 2.0 article-volume timeline (free, keyless, historical, deterministic
  query→series) for a **pinned per-theme query** (the mechanism's keyword set, frozen in Part A).
- **Onset rule (pinned form):** the onset is the first month in which normalized article volume
  exceeds **K×** the trailing-baseline median **and stays above for ≥ M consecutive months** (a
  *sustained* crossing, not a one-month spike). K, M, the baseline window, and the normalization are
  pinned here; the onset *dates* are computed by Part B-(i), not chosen.
- This is a deterministic news-volume computation (no LLM), so it does not need the blind-LLM-run
  treatment — but it MUST be run per the pinned procedure (auditable), never hand-set.

### 5.4 The #37 discipline applied to the calibration set itself
§10.8: *"a 100%-NEUTRAL cycle must prove it isn't a parse bug in costume."* The quiet-state's LOW
overlap is meaningless if it's an empty/refused/errored output rather than genuine non-knowledge.
**Responsiveness gate (pinned):** a quiet-state reading counts as "under-narrated evidence" only if it
is non-empty, on-topic, and fluent (the model *engaged* and was *non-specific*) — distinguishing
"genuinely lacks the specifics" from "the probe failed." A reading that fails responsiveness is
dropped from the set (logged), never scored as quiet.

### 5.5 Model/cutoff matrix
Heterogeneous, decorrelated providers (the council's multi-provider principle — training-data leakage
decorrelated across vendors). **Per onset: ≥2 distinct-vendor models with cutoff ≥6 months BEFORE the
onset, and ≥2 with cutoff ≥6 months AFTER** (the ≥6mo bracket guards against cutoff fuzz + partial
leakage near the boundary). The exact model/version matrix is recorded in Part B (model versions
drift; the RULE is pinned here, the roster in the run).

### 5.6 Carried caveat
**Knowledge-cutoff lag (stub):** a theme narrated *after* a probe model's cutoff reads quiet to that
model. At DEPLOY this is a real false-quiet source — backstopped by the council's live under-narrated
test (the funnel-not-verdict posture, §7). Pinned, not "fixed."

---

## 6. The overlap metric, separation criterion, and the operating-threshold rule (committed before scoring)

- **Overlap metric:** the §4 deterministic per-field scorer → a combined overlap ∈ [0,1] per
  (mechanism, model) reading. Definition + field weighting pinned in Part A.
- **Separation statistic:** over the set, the per-mechanism **margin** = narrated-state overlap −
  quiet-state overlap, aggregated (median margin + the fraction of mechanisms with positive margin).
- **Blind validity gate (committed now, pass/fail before any operating number):** the probe is **fit
  to deploy only if** (a) the **ceiling check** (§5.2) holds — narrated-state overlap is high in
  aggregate — AND (b) narrated exceeds quiet on a pinned super-majority of mechanisms with the
  aggregate margin distinguishable from zero by a pinned test. If the gate FAILS, the probe is unfit:
  **do not deploy it, and do NOT loosen it to manufacture separation** (§7). The gate's *structure*
  and a conservative floor are frozen here; it is a pass/fail, not the operating threshold.
- **Operating-threshold RULE (committed now; the number is Part B):** given a passing validity gate,
  the keep/reject overlap threshold is set at the **permissive funnel point** — the value that bounds
  the **false-narrated** rate (the invisible loss: rejecting a genuinely under-narrated mechanism) at a
  pinned-low level, *accepting* more **false-quiet** (which the council's live under-narrated test
  backstops). The threshold controls false-narrated, it is not balanced. The RULE is frozen; the
  resulting number is recorded in Part B.
- **Aggregation across the ≥2 models per state (carried + reconciled): any-model-high-overlap =
  narrated → reject.** This reconciles with "calibrate permissive" via the *bar* for "high": a model
  counts as knowing the mechanism only on **strong** specific overlap (the permissive/high per-model
  bar), so a vaguely-fluent description never triggers a reject; but if **any** decent model
  *demonstrably* knows the specifics, the mechanism is in circulation → narrated. Net: we reject only
  when at least one model genuinely knows it — minimizing false-narrated — while the any-model rule
  still catches genuinely-circulating themes. (Surfaced in red-team pass 3; the two stub phrases pull
  opposite ways and the reconciliation is the per-model high bar.)

---

## 7. Freeze-gate bands (stub constraint #5, pinned cold) + carried postures

**The GENERATOR-yield freeze-gate (pinned blind here per "pre-committed at ITS freeze"; distinct from
the §6 calibration validity gate):** on the generator's first real run (Stage 1, July-gated) —
- **0 generated theses** → sources/corpus too thin → **do NOT loosen the probe** (investigate the
  corpus, not the threshold);
- **small-n** → proceed;
- **large-n** (above the pinned expectation) → **selectivity-flag on the generator** — it is less
  selective than expected → investigate, do **not** bank as upside, do not proceed until understood.

Expected yield is pinned **blind** before the run; themes get a **graveyard**, like edges. (The exact
expectation and bands are committed at this freeze; the read happens at the generator's first run.)

**Carried postures (from the stub — pinned, not re-decided here):** the probe is a **funnel, not a
verdict** (calibrated permissive; the discovery-prescreen doctrine); the LLM is a **synthesis device
over pinned inputs, never a memory device** (free recall samples the narrated corpus — the worst-placed
anti-quietness instance, which this probe inverts into the sensor).

---

## 8. Out of scope / forbidden (the HARK leash) + deferred (named so they don't vanish)

**Forbidden (the leash):**
- stating the operating threshold **number** this week (it is Part B, blind);
- iterating the probe, the field set, the overlap scorer, or the threshold **against generated
  candidates** or against admission / gate / council outcomes (constraint #2 — the generator/probe
  pair is one §10.4-bound re-tightening);
- re-touching §3–§7 after Part B's number is seen (§10.4 one-pass discipline);
- loosening any floor / criterion / threshold to manufacture separation or yield (the §7 analog).

**Deferred (out of this cold payload, named):**
- **stub Q3** — the demote rule (N windows, the aggregate keyed on, the dormancy-flag write path):
  a Stage-3/operations concern, not cold-critical, its own later section;
- **stub Q4's NUMBER** — the operating threshold value → **Part B**;
- the **Stage-1 generator mechanics** (prompt, model versions, citation-verification wiring) and the
  **Stage-3 adversary/operator-veto** — their own pre-reg sections, July-gated per the stub ordering.

---

## 9. Red-team log (three MECE passes; catches folded into the text above)

**Pass 1 — construct validity (does the calibration measure what deploys?).**
- *Catch:* the calibration straddles KNOWN themes but DEPLOY scores GENERATED claims; if the generator's
  claim format differs from the calibration claims', the threshold doesn't transfer. → *Fix:* §3 pins
  the calibration claims to the generator's **identical schema/format**; this is why Q1+Q2 are in the
  cold payload, not just Q5.
- *Catch:* "pre-onset model doesn't know it" ≈ "under-narrated" is an **assumption**, not given. →
  *Fix:* §5.2 states it explicitly + the §6 **ceiling check** (narrated-state must read high, else the
  metric — not the theme — is broken).

**Pass 2 — measurement artifact / gaming (the #37 + the stub's gaming channel).**
- *Catch:* quiet-state LOW overlap could be an empty/errored output, not non-knowledge. → *Fix:* §5.4
  responsiveness gate (engaged + non-specific, else dropped).
- *Catch:* scoring on obscure citation IDs makes everything read quiet + is gameable. → *Fix:* §4
  forbids citation-only IDs as scoring targets (carried); fluency is not a field.
- *Catch:* cutoff fuzz / training-data leakage near the boundary contaminates the "pre" state. → *Fix:*
  §5.5 ≥6-month bracket + heterogeneous decorrelated vendors.

**Pass 3 — HARK / ordering cleanliness.**
- *Catch:* the two stub phrases "any-model-high = narrated" (aggressive reject) and "calibrate
  permissive" (lenient keep) pull opposite ways — left unreconciled, an implementer picks whichever
  fits the number. → *Fix:* §6 reconciles them via the **per-model high bar** (reject only on strong
  per-model overlap; any such model ⇒ narrated), and §2/§8 forbid setting the number against generated
  candidates and re-touching after the run.
- *Catch:* eyeballed onset dates would let the straddle be tuned to "work." → *Fix:* §5.3 GDELT
  sustained-crossing procedure computes onsets reproducibly; dates are computed in Part B-(i), not
  chosen.

---

## 10. Open questions remaining (dated — answers belong to Part B or a later section, not improvisation)

1. The operating-threshold **number** and the validity-gate's exact numeric floor — **Part B** (blind
   run on the known set).
2. The §4 field **weighting** form is pinned, but its exact weights + the quantity-tolerance buckets
   want a worked schema with 2–3 fully-populated example claims (authored at §3 granularity) — to be
   attached to Part A before the operator merges, if the operator wants the examples in-band.
3. The GDELT query templates per seed theme + K/M/baseline values — pinned numerically in Part A's
   final (this draft pins the *form*); recommend fixing them in the same review that merges this.
4. stub Q3 (demote rule / dormancy write-path) — deferred (§8).
