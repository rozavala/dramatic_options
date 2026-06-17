# PREREG — the narration probe (Stage-2 of the theme-generation layer): the calibration freeze

**Status: DRAFT for operator review (rev 2, 2026-06-17). Part A (the protocol) FREEZES ON MERGE —
nothing below is committed until then. Part B (the operating threshold NUMBER + the model roster) is a
SEPARATE dated blind run AFTER merge.** Companion to `PREREG_THEME_GENERATION_STUB`; the cold-critical
core of the generation layer's own pre-reg. Converged over two red-team rounds (rev 1 three MECE
passes; rev 2 a 12-item adoption-audit + new-seams pass — log §10). Cites only the committed record.

---

## 1. Cleared precondition + why this is the next pinned item (lead, per §10.8)

**The ordering condition is MET.** `PREREG_COUNCIL_GATE_SEPARATION` §10.8 (2026-06-10): **0/16 =
SCARCITY**, in-band for the 0/1 rule — verbatim, *"the theme-generation stub's ordering condition is
MET on the mandate side (0/1 achieved) — its remaining gates are its own pre-reg + the
generation-layer design constraints."* This is that pre-reg's cold core.

**Why the narration probe (§10.8's load-bearing finding):** the dominant abstention inside the 0/16
was that *marker-only grounding cannot support the hardened tri-criteria* — the council declines to
assert **under-narrated** from price/vol markers. §9 (`PREREG_EVIDENCE_GROUNDING`, FROZEN 2026-06-11)
added the **grounding** half (structural/at-inflection legs). The **under-narrated** leg has no
deterministic sensor yet; the narration probe IS it — measuring narration so a genuinely-quiet theme
clears the bar **without loosening the bar** (the HARK leash: measure the criterion, never relax it).

**Why COLD:** the operating threshold is a fitted parameter; set after seeing what the generator emits
or what the gate/council admit, it is HARKed. Stub constraint #2 binds the generator/probe **pair** to
one §10.4-style re-tightening, neither iterated against the other's outputs nor against admission/gate
outcomes. So the probe is calibrated on themes whose narration state is known **independently** of our
pipeline (cutoff-straddling, §5) and frozen before generation runs. Now is that window.

---

## 2. Two-part structure (mirrors §10.4 / §10.8: freeze-bands → run → record)

- **Part A — THIS freeze (spend-free, no LLM; FREEZES ON MERGE):** the register unit AND the concrete
  mechanism-claim **schema** (§3), the narration-diagnostic field set + the elicitation/scoring choice
  + the **mandatory** worked examples (§4), calibration-set construction + the reproducible onset
  procedure (§5), the overlap metric + **the validity-gate floor (blind numbers) + the
  operating-threshold rule** (§6), the carried postures + generator-yield bands (§7), and the
  must-land-before-merge numeric checklist (§9). Every decision rule is committed **with its
  pass/fail bar but without the calibration's output number in front of it.**
- **Part B — a SEPARATE dated run AFTER merge:**
  - (i) the **deterministic set-construction run** (GDELT only, no LLM) computes onset dates and
    assembles the cutoff-straddling set per §5;
  - (ii) the **LLM probe run** scores the set per §6, **records pass/fail against the §6 validity-gate
    floor**, and pins the **operating threshold** (stub Q4) per the §6 rule;
  - one pass; recorded as a dated appendix; **no §3–§7 text is re-touched after the number is seen**
    (§10.4). Part B probes the KNOWN calibration themes, never a generated candidate.

**The number split (rev-2 #1, the HARK fix):** the **validity-gate floor** (probe-is-fit pass/fail) is
frozen BLIND in Part A (§6); only the **operating threshold** (the permissive keep/reject cutoff) is a
Part-B output. A fitness bar set after the scores are visible is exactly the post-hoc move this
document exists to prevent.

---

## 3. Register unit (stub Q1) — mechanism-claim granularity + the FROZEN schema (PINNED, prescriptive)

The probed/scored/(eventually)demoted unit is a **mechanism claim**, NOT a theme label (*"a
theme-level threshold doesn't transfer"*). A mechanism claim names a **driver → effect** step, the
**entities** it runs through, and its **direction/sign**.

**The schema is FROZEN HERE as a concrete artifact, and it is FORWARD-BINDING on the Stage-1 generator
(rev-2 #2):** the future generator **MUST emit this exact schema** (prescriptive, not the descriptive
"emits claims in this unit"). This closes the one-way-door trap — §8 forbids re-touching §3 after Part
B, the generator is July-gated, and if its emitted format diverged the threshold would silently fail
to transfer with no recourse. The schema is the transfer anchor; the worked examples (§4.3) ARE the
schema and are therefore **mandatory in-band**, not optional.

```jsonc
{                                  // one mechanism claim
  "claim_id":   "str",
  "statement":  "one sentence: <driver> → <effect> → <entity class>",
  "named_entities": [              // §4 scoring leg 1 (deterministic, leans on EDGAR company_tickers)
    {"canonical": "GE Vernova", "ticker": "GEV", "aliases": ["GE Vernova", "Vernova"]}
  ],
  "mechanism_direction": {"vocab": "shortage|surplus|backlog_growth|capex_up|supply_cut|demand_surge|capacity_constraint|...",
                          "sign": "+|-"},     // §4 scoring leg 2 (controlled vocab; see the §4 fork)
  "headline_quantities": [         // §4 scoring leg 3 (deterministic numeric tolerance); NARRATION
    {"metric": "transformer lead time", "value": "~50→~120 weeks", "bucket": "weeks_x2plus"}
  ],                               // fingerprints (what circulates when narrated) — prefer STRUCTURAL
                                   // magnitudes (GW, Mlbs, capex %, lead-times), not prices (§2 optics)
  "provenance":  "calibration|generated",
  "onset_theme": "str",           // links the claim to its GDELT onset (§5.3)
  "in_live_book": true            // reflexivity flag (§5.1 / rev-2 #7)
}
```

---

## 4. The narration-diagnostic field set (stub Q2) + the elicitation/scoring choice (PINNED)

A model is asked about each mechanism (elicitation, see the fork) and its answer scored on
**accuracy-of-specifics overlap** against the three schema fields — the things that **circulate when a
theme is narrated**. **FORBIDDEN scoring targets (carried):** citation-verification-only identifiers
(docket / queue / filing IDs) — corpus-inaccessible, and scoring on them makes everything read quiet +
hands the generator a gaming channel. **Fluency is NOT a field** (models confabulate fluently about
quiet themes — a fluency probe false-rejects its own target class).

### 4.1 DECISION — elicitation × scoring relaxation (rev-2 #3; freezes at merge; **recommended: B**)

The triad **{free-text elicitation, fully-deterministic scoring, no LLM judge}** is over-determined —
`mechanism_direction` sign-extraction can't survive deterministically ("lead times are blowing out" =
backlog_growth with no "backlog" token → a lexicon under-credits paraphrase → margins become noise),
and the §5.4 responsiveness gate ("on-topic + fluent") needs that same judgment. At most two of the
three hold. The fork (pick one; it freezes at merge):

| | what relaxes | upside | downside |
|---|---|---|---|
| **A** structured elicitation | free-text → the model fills the fields | scoring stays fully deterministic | cueing the schema inflates overlap (cued vs free recall) — contaminates the very thing measured |
| **B (rec.)** ring-fenced narrow LLM | "no LLM judge" → a bounded classifier | free-text recall preserved; entity+quantity scoring stays deterministic (leans on EDGAR `company_tickers`, 10.4k names); LLM only labels sign ∈ controlled-vocab + responsiveness ∈ {engaged-nonspecific / empty / off-topic}, NEVER the overlap/verdict | one bounded LLM in the loop (mitigated: decorrelated ≥2-vendor majority, pinned model+prompt-sha, controlled-vocab output, auditable) |
| **C** deterministic lexicon | nothing | purest | the paraphrase noise above; must *prove* lexicon adequacy vs adversarial paraphrase in the worked examples |

**Recommendation B**, because free-text elicitation is the *right* task (natural recall is what
narration measurement requires; structured elicitation in A cues the answer — a worse contamination
than a bounded classifier), and entity+quantity scoring is solidly deterministic on existing infra
(EDGAR ticker↔name; numeric tolerance). The relaxation is narrow: **the overlap SCORE is deterministic
given (entity-match, sign-label, quantity-match); only the sign-label and responsiveness come from a
ring-fenced, pinned, decorrelated classifier that emits a controlled-vocab token and never decides
narrated/under-narrated.** §4.2/§5.4 below are written for B; if the operator picks A or C at merge,
those two subsections swap (and C makes the §4.3 adversarial-paraphrase demonstration load-bearing).

### 4.2 Scoring legs (written for B)
| field | match rule | determinism |
|---|---|---|
| `named_entities` | case-insensitive alias/ticker match (claim aliases ∪ EDGAR `company_tickers` title/ticker); score = fraction of the claim's entities correctly named | **fully deterministic** |
| `mechanism_direction` | the ring-fenced classifier maps the model's prose → a controlled-vocab (vocab, sign); match = exact (vocab, sign) | classifier-labeled, deterministic given the label |
| `headline_quantities` | numeric parse of the model's prose vs the claim's value within the pinned bucket tolerance (order-of-magnitude / ±1 bucket) | **fully deterministic** |

Per-field margins are reported and gated **independently** (rev-2 #6) — the combined scalar can pass
on a third-garbage construct if (say) sign is noise but entity-match separates; the gate (§6) sees
each leg so the brittle one is watched, not averaged away.

### 4.3 Worked examples — MANDATORY in-band (the schema + the scorer-adequacy demonstration)
Two book-theme claims + **one non-book claim** (rev-2 #7, reflexivity hygiene + matcher
generalization beyond energy vocabulary):

1. **`ai_power` (in_live_book=true).** statement: *"AI-datacenter buildout → transformer & MV-switchgear
   shortage → multi-year order backlog at grid-equipment OEMs."* entities: GE Vernova/GEV, Eaton/ETN,
   Vertiv/VRT. direction: `backlog_growth +`. quantities: transformer lead time `~50→~120 weeks`
   (`weeks_x2plus`). *Adversarial paraphrase a lexicon (C) would miss:* "OEM delivery windows have
   ballooned to over two years" — no "backlog" token; B's classifier maps it to `backlog_growth +`.
2. **`nuclear_fuel` (in_live_book=true).** statement: *"reactor restarts + SMR demand vs post-Fukushima
   underinvestment → structural uranium supply deficit."* entities: Cameco/CCJ, Kazatomprom, NexGen/NXE.
   direction: `supply_cut +` (deficit). quantities: annual deficit `~30–50 Mlbs` (`Mlbs_tens`) —
   structural magnitude, **not** spot price (§2 optics).
3. **`glp1_obesity` (in_live_book=FALSE — non-energy 2023 onset).** statement: *"GLP-1 efficacy readouts
   → obesity-drug demand surge → injectable fill-finish / CDMO capacity constraint."* entities: Eli
   Lilly/LLY, Novo Nordisk/NVO. direction: `capacity_constraint +`. quantities: trial weight-loss
   `~15–20%` (`pct_15_25`). Proves the entity/sign/quantity matcher generalizes past grid/uranium.

---

## 5. Calibration-set construction (stub Q5) — the load-bearing surface

### 5.1 Cutoff-straddling; the theme as its own control; ≥1 non-book theme
Each calibration mechanism comes from a theme with a **verifiable onset**, probed across models whose
cutoffs **bracket** it: a **pre-onset** reading = the quiet state (expected LOW overlap), a
**post-onset** reading = narrated (expected HIGH overlap). The same mechanism supplies both → **cross-
theme idiosyncrasy controlled by construction** (the stub's HARK-vector warning; **no hand-picked
current-quiet themes enter the set**). Seeds have verifiable onsets: uranium/nuclear (~2023),
AI-power/grid (~2024). **At least one seed must be OUTSIDE the live book** (rev-2 #7 — uranium/AI-power
ARE `nuclear_fuel`/`ai_capex_power`/`grid_equipment` in `universe_register.json`; calibrating the
under-narration sensor only on the book's own winning themes is a reflexivity surface and may tune the
scorer to energy vocabulary). The GLP-1/obesity onset (~2023, non-energy) is the seed non-book theme;
the final list is whatever §5.3 admits.

### 5.2 The core assumption, stated so it can be attacked
Validity rests on: *a current model's specific-overlap on a current under-narrated mechanism ≈ a
pre-onset model's overlap on a pre-onset mechanism.* An assumption, not a theorem — guarded by the §6
**ceiling AND basement** checks.

### 5.3 Onset verification — REPRODUCIBLE, GDELT (net-new, one-shot)
- **Source:** GDELT DOC 2.0 article-volume timeline (free, keyless, historical, deterministic
  query→series) for a **pinned per-theme query** (frozen in Part A). **GDELT is net-new** (verified:
  zero repo usage; `data/news.py` is per-symbol Alpaca/Benzinga and cannot supply theme-keyword
  historical volume — so it's justified). It is **one-shot** (Part B-(i) only), so the FERC-style
  scheduled-robustness bar does NOT apply (rev-2 #9).
- **Normalization (pinned, rev-2 #9):** volume as **% of total GDELT articles** (not raw counts), so a
  growing corpus doesn't masquerade as rising salience. **Source-composition discontinuities** (a
  sustained source-set change reads as a sustained onset) are a known GDELT artifact a crossing rule
  won't absorb → **each computed series is eyeballed for regime artifacts** before its onset is banked.
- **Onset rule (pinned form):** the first month where normalized volume exceeds **K×** the
  trailing-baseline median **and stays above ≥ M consecutive months** (sustained, not a spike). K, M,
  baseline window pinned in Part A (§9 checklist); onset *dates* computed by Part B-(i), never chosen.
- **Two proxy-hops, stated (rev-2 #10):** GDELT dates **media-narration** onset (hop 1), which precedes
  **training-corpus incorporation** (hop 2). The ≥6-month cutoff bracket (§5.5) is partly absorbing
  this lag — that is explicitly part of the bracket's job.

### 5.4 The #37 discipline — responsiveness gate (written for B)
§10.8: *"a 100%-NEUTRAL cycle must prove it isn't a parse bug in costume."* A quiet-state LOW overlap
is meaningless if the output was empty/refused/off-topic. The ring-fenced classifier (§4.1-B) triages
each reading → {engaged-nonspecific / empty / off-topic}; **only `engaged-nonspecific` counts as
under-narrated evidence.** empty/off-topic readings are dropped from the set (logged), never scored as
quiet. (Under fork A/C this triage is whatever that fork's relaxation allows.)

### 5.5 Model/cutoff matrix — feasibility-checked, asymmetric, exhaustive
- **Post-onset (narrated):** ≥2 **distinct-vendor** models, cutoff ≥6 months AFTER onset (decorrelation
  earns its keep here — confirming the narrated specifics are broadly in circulation, not one model's
  quirk).
- **Pre-onset (quiet):** ≥2 models, cutoff ≥6 months BEFORE onset; **distinct-vendor PREFERRED, NOT
  required (rev-2 #4)** — the pre-onset need is "didn't know it yet," not vendor diversity, and the
  roster is genuinely thin for a 2023 onset (e.g. xAI/Grok's earliest model post-dates the uranium
  onset entirely; old-cutoff models cluster at OpenAI/Meta/early-Anthropic/early-Gemini, several near
  the ≥6mo boundary). Same-vendor different-cutoff pre-onset readings are admissible.
- **Pre-merge FEASIBILITY CHECK (rev-2 #4):** before merge, a rough-onset check confirms a qualifying
  pre-onset roster can be assembled for the **oldest seed**; if not, the documented fallback is to drop
  distinct-vendor pre-onset (above) and, failing that, widen the seed set / relax the bracket — recorded.
- **Roster rule = EXHAUSTIVE over qualifying models (rev-2 #11):** Part B-(ii) uses **every** model
  meeting the bracket criteria, not a chosen subset — so the roster is not a post-onset tuning knob.
  The concrete roster (versions drift) is recorded in Part B, selected by this deterministic rule.

### 5.6 Carried caveat
**Knowledge-cutoff lag:** a theme narrated after a probe model's cutoff reads quiet to it — a real
deploy-time false-quiet source, backstopped by the council's live under-narrated test (funnel-not-
verdict, §7). Pinned, not "fixed."

---

## 6. Overlap metric, validity gate (blind floor), and operating-threshold rule

- **Overlap metric:** the §4.2 per-field scorer → per-field overlaps + a combined overlap ∈ [0,1] per
  (mechanism, model) reading (field weighting pinned in Part A, §9).
- **Separation statistic:** per-mechanism **margin** = narrated-overlap − quiet-overlap; aggregated as
  the median margin + the fraction of mechanisms with positive margin, **and per field** (rev-2 #6).
- **Validity gate — FROZEN BLIND in Part A (rev-2 #1), a pass/fail, distinct from the threshold.** The
  probe is **fit to deploy only if ALL hold** (numbers pinned blind at merge, §9 — conservative
  defaults shown):
  - **ceiling check:** narrated-state aggregate overlap ≥ **0.60** — the metric *can* capture a
    narrated mechanism's specifics (else the metric, not the theme, is broken);
  - **basement check (rev-2 #5):** quiet-state aggregate overlap ≤ **0.30** — the set is not
    contaminated by pre-onset leakage;
  - **separation:** narrated > quiet on ≥ **75%** of mechanisms AND median margin ≥ **0.25** AND a sign
    test p < 0.05;
  - **per-field floor:** the `named_entities` leg (the most reliable, fully-deterministic leg) clears
    margin ≥ **0.25 on its own** — a pass cannot rest on the paraphrase-noisy sign leg alone.
- **Three-way diagnosis (rev-2 #5 — contamination is distinguishable from non-separation, not collapsed
  into one fail):** ceiling-OK & basement-FAIL (quiet too high) → **set contamination** → re-pick the
  bracket / drop the offending theme (NOT a probe failure); basement-OK & ceiling-FAIL (narrated too
  low) → **metric broken** → probe unfit (do not loosen); both mid → **genuine non-separation** → unfit.
- **Operating-threshold RULE (committed now; the NUMBER is Part B):** given a passing gate, the
  keep/reject overlap threshold is set at the **permissive funnel point** — the value bounding the
  **false-narrated** rate (the invisible loss: rejecting a genuinely under-narrated mechanism) at a
  pinned-low level, accepting more **false-quiet** (which the council's live under-narrated test
  backstops). Controls false-narrated; not balanced. RULE frozen; number recorded in Part B.
- **Aggregation across models per state (carried + reconciled, rev-2 #3 / rev-1 pass-3):
  any-model-high-overlap = narrated → reject**, reconciled with "calibrate permissive" via the **bar
  for "high"**: a model counts as knowing the mechanism only on **strong** specific overlap (the
  permissive/high per-model bar), so a vaguely-fluent answer never triggers a reject; but if **any**
  qualifying model *demonstrably* knows the specifics, the mechanism is in circulation → narrated. Net:
  reject only when ≥1 model genuinely knows it — minimizing the false-narrated invisible loss.

---

## 7. Generator-yield freeze-gate bands (stub constraint #5, pinned cold) + carried postures

**The GENERATOR-yield gate** (fires on the generator's first run, Stage-1, July-gated; pinned blind
HERE per "pre-committed at ITS freeze" — earlier = more blind; **DISTINCT** from the §6 calibration
validity gate):
- **0 generated theses** → corpus too thin → **do NOT loosen the probe** (investigate the corpus);
- **small-n** → proceed;
- **large-n** (above the pinned expectation) → **selectivity-flag on the generator** → investigate,
  do not bank, do not proceed until understood.
Expected yield pinned **blind** at this freeze (§9 checklist); themes get a **graveyard**, like edges.

**Cross-reference (rev-2 #12):** this band lives here for maximal blindness, but the generator's own
pre-reg MUST cite it so stub constraint #2 ("one re-tightening per re-score") is not muddied by a band
spanning two documents — the band is pinned once, here, and referenced there.

**Carried postures (pinned, not re-decided):** the probe is a **funnel, not a verdict** (permissive;
the discovery-prescreen doctrine); the LLM is a **synthesis device over pinned inputs, never a memory
device** (free recall samples the narrated corpus — the worst-placed anti-quietness instance, which
this probe inverts into the sensor).

---

## 8. Out of scope / forbidden (the HARK leash) + deferred (named)

**Forbidden:** stating the operating-threshold number this week; iterating the probe / field set /
scorer / threshold against generated candidates or admission/gate/council outcomes (constraint #2);
re-touching §3–§7 after Part B's number (§10.4 one-pass); loosening any floor/criterion/threshold to
manufacture separation or yield.

**Deferred (named):** stub **Q3** (demote rule / N windows / dormancy write-path) — a Stage-3/ops
concern, its own later section; stub **Q4's number** → Part B; the **Stage-1 generator mechanics** +
**Stage-3 adversary/operator-veto** → their own pre-reg sections, July-gated.

---

## 9. Must-land-before-merge numeric checklist (rev-2 #8 — makes the freeze auditable)

These are asserted "pinned at this freeze" and MUST carry concrete values in the merged text (all
committed blind — no calibration scores exist yet):
- [ ] **§4.1 fork** resolved (A / B / C) and §4.2/§5.4 consistent with it.
- [ ] **§4.2 field weighting** + **§4.3 quantity buckets** (the controlled bucket set).
- [ ] **§5.3 GDELT**: per-theme query templates; K, M, baseline window; normalization (= %-of-total).
- [ ] **§5.5 feasibility check** run on the oldest seed; roster rule = exhaustive-over-qualifying.
- [ ] **§6 validity-gate floor**: ceiling, basement, separation %, median-margin, sign-test, per-field
  floor (defaults 0.60 / 0.30 / 75% / 0.25 / p<0.05 / 0.25 — confirm or adjust BLIND).
- [ ] **§7 generator-yield**: the expected-yield number + the small/large-n band edges.
- [ ] **§4.3 worked examples** present in-band (mandatory) and consistent with the fork.

---

## 10. Red-team log

**Rev 1 — three MECE passes (catches folded into §3–§6):** construct validity (generated-vs-calibration
format transfer → §3 schema; pre-onset≈under-narrated assumption → §5.2 + ceiling check); measurement
artifact/gaming (responsiveness gate §5.4; forbidden citation-IDs §4; cutoff-fuzz bracket §5.5); HARK/
ordering (any-model-high reconciled via per-model high bar §6; reproducible GDELT onsets §5.3).

**Rev 2 — adoption audit + 12 new seams (all folded; the design got specific enough that the next
layer of seams became visible):**
- **#1 (blocker)** §6/§10 contradiction put the validity-gate floor in Part B = a HARKed gate → SPLIT:
  gate floor blind in Part A (§6), only the operating threshold in Part B (§2).
- **#2 (blocker)** the transfer-anchor schema was unfrozen + optional behind a one-way door before a
  July-gated generator → §3 freezes it as a concrete, **prescriptive forward-binding** artifact;
  worked examples **mandatory** (§4.3).
- **#3** the {free-text, deterministic, no-LLM-judge} triad is over-determined → §4.1 fork, **rec. B**
  (ring-fenced narrow classifier for sign+responsiveness only; entity+quantity stay deterministic on
  EDGAR `company_tickers`).
- **#4** §5.5 matrix may be infeasible (no pre-2023 Grok; old models cluster) → relax distinct-vendor
  **pre-onset**, add a pre-merge feasibility check.
- **#5** quiet-side contamination had no detector → §6 **basement check** + the three-way diagnosis.
- **#6** scalar-only gate hides a garbage field → §4.2/§6 per-field margins gated independently.
- **#7** seeds ARE the book's themes → §5.1 requires ≥1 non-book seed (GLP-1) + a non-book worked
  example.
- **#8** scattered "pinned" assertions → §9 checklist.
- **#9** GDELT net-new (verified) + data-quality → §5.3 (justified, one-shot, %-of-total, regime eyeball).
- **#10** GDELT dates media-narration, 2 proxy-hops → §5.3 (the bracket absorbs the lag).
- **#11** roster chosen post-onset = a knob → §5.5 exhaustive-over-qualifying rule.
- **#12** band in two docs muddies constraint #2 → §7 cross-reference.

---

## 11. Open questions remaining (dated — answers belong to Part B or a later section, not improvisation)

1. The operating-threshold **number** — **Part B** (blind run on the known set).
2. The §4.1 fork is recommended-B but **the operator's pick freezes at merge** (the worked examples
   already demonstrate B; A/C swap §4.2/§5.4).
3. The §9 numeric pins (GDELT K/M/baseline + queries, field weights, gate-floor confirmations,
   generator-yield expectation) — land in the merged text, blind.
4. stub **Q3** (demote rule / dormancy write-path) — deferred (§8).
