# PREREG — Seeded-Generator Diagnostic (the human-seed → second-order-source reach test)

**Status: FROZEN 2026-06-27** (operator sign-off after a 2-round advisor red-team). Pins the criterion
**BLIND before any bounded-live run.** Read **separately** from `PREREG_THEME_GENERATOR §10` — the §10 yield
band was pinned for the *full-corpus* run; a seeded slice has a different denominator, so scoring against
§10 would HARK. The red-team caught the original criterion measuring *"narrow input → different output"*
(near-tautological) instead of the hypothesis; this is the corrected pin.

> **⚠ §9 (dated 2026-06-27) amends this BEFORE the first run — read it WITH §3/§4.** A second pre-spend
> red-team found `nuclear_fuel`'s non-ETF sources are entity-FREE (leg (c) unsatisfiable → a structural zero).
> §9 supersedes the **first theme** (§3: `nuclear_fuel` → **`space_smallcap`**) and **refines leg (c)** (§4:
> "non-ETF source" → "non-ETF **entity-resolvable** source"). Where §3/§4 say `nuclear_fuel`/`nrc`/`eia`, §9 governs.

## §1 — Hypothesis
The **autonomous** generator is measured-dead (`records/2026-06-23_…negative.md`: it re-derives
narrated/in-universe names — `gen_rescore` 0/17 on `under_narrated`, 8/9 already in-universe — because a
§2-clean corpus is blind to quietness and magnitude-ranking rides coverage). Its **surviving** role: a
HUMAN names a quiet sector (the decorrelating judgment the machine cannot supply); the generator,
**restricted to that sector's corpus slice**, synthesizes a falsifiable mechanism-claim tracing to a
**second-order source** — the supplier-of-the-supplier OUTSIDE the human's named ETF. **Tested: does a
seeded run reach a genuinely-quiet name the human's own ETF (via §11 source∩screen∩OTM) would NOT already
surface?**

## §2 — Firewall (INERT)
Operator-chosen seed → restrict `assemble_corpus` to that theme's slice → synthesize → `verify.py` DROPs
any claim not tracing to a cited dated record → derived **sources** enter admission via
source∩screen∩OTM∩gate; **the LLM never selects a ticker.** Writes only `records/generator/`
(`GENERATOR_RECORDS_DIR`) — no register write, no live scan, no book. Fully parallel to #72 and the §5 read.

## §3 — Method
- **Bounded-LIVE synthesis** — real router, single cheap model, `generator.cost_cap_usd`, fail-closed
  `BudgetExceeded`. **NOT `--demo`** (FakeRouter = canned ⇒ cannot measure emission content; the `--demo`
  run is a **step-0 plumbing smoke ONLY**).
- **First theme: `nuclear_fuel`** (routes `etfs`+`nrc`+`eia` — multi-source; `nrc`/`eia` are the non-ETF
  second-order sources the mechanism needs). `copper_supply` (etfs-only) and `humanoid_supply` (unrouted)
  are corpus-thin → would false-negative; `humanoid_supply` only AFTER it is routed to multi-source pulls.
- **k = 5 runs per arm**, fresh at the **current** model/prompt/corpus-date (matched conditions — model
  versions are record-segmenting). The 2026-06-22 autonomous artifact counts as one run IFF version-matched,
  else a non-load-bearing reference.

## §4 — The single quality bar (scored on BOTH arms; yields compared)
An emission **QUALIFIES** iff ALL of:
- **(a)** not in `universe_register.json` / `themes.json` (genuinely new); AND
- **(c)** traces (via `verify.py` citations) to a **second-order source** — a cited source OTHER than the
  seed theme's ETF (for `nuclear_fuel`: `nrc` / `eia`) — **AND the name is NOT a member of the seed theme's
  ETF/constituent holdings** (a name in the seed's own ETF is already caught by §11 on the human's ETF — no
  added reach); AND
- **(Stage-2)** a council re-score reads `under_narrated = True`.

**Frequency-aware (k=5):** a name is a **stable** emission for an arm iff it appears in **≥ 3 / 5** runs
(factors out LLM sampling variance — the underpowered-N trap the abort discipline guards). **YIELD(arm)** =
count of stable names meeting (a)+(c)+Stage-2. Score BOTH arms; the autonomous arm is the comparator
(06-23 read ≈ 0).

## §5 — Verdicts (Stage-1 = escalation; Stage-2 = confirmation)
- **Stage-1 (NECESSARY, not sufficient):** ≥1 stable seeded emission meeting (a)+(c) → escalate to Stage-2.
  **Plumbing-negative:** if the seeded stable set is a **subset** of the autonomous set, the slice isn't
  biting (training recall, not the corpus) → stop.
- **Stage-2 (CONFIRMATION):** `YIELD(seeded) > YIELD(autonomous)` on the full bar (a)+(c)+`under_narrated`.
  The re-score is a **fixed-entity-list** invocation (the `gen_rescore` pattern), **not a discovery scan** →
  it does not touch the §5 count.
- **Demoted leg (b):** "different from the autonomous set" is **NOT** a success leg — near-tautological (a
  narrower input yields different output by construction; a different name can still be narrated). It
  survives ONLY as the subset plumbing-check above.

## §6 — Reads + framing
- **DROP split** (`dropped_entity_unresolved` / `dropped_fact_untraced`) reported per seeded run — a high
  untraced rate = the slice is too thin to synthesize (a richness diagnostic, distinct from confabulation).
- **A clean Stage-2 pass on `nuclear_fuel` is an EXISTENCE PROOF for ONE theme, not a validated accelerant**
  (nuclear may carry a richer second-order supply chain than most). It licenses "promising — test more
  themes," NOT "ship the seeded generator."
- **Cost:** Stage-1 (bounded-live synthesis ×k) and Stage-2 (the council re-score) BOTH cost a little; only
  the step-0 `--demo` smoke is free.

## §7 — Sequence
0. *(free)* `--demo` slice-assembly plumbing smoke (this PR). 1. freeze (this doc). 2. the `--seed-theme`
   extension (this PR). 3. build the k=5 matched autonomous baseline. 4. bounded-live Stage-1 ×5 on
   `nuclear_fuel`. 5. Stage-2 council re-score on divergence. Steps 3–5 are the only spend, all INERT.

## §8 — Scorer operationalization (dated appendix 2026-06-27, BLIND before any run)

The §4–§5 legs stay frozen; this pins **how** the scorer (`generator/score.py`) computes them, fixed
before emissions exist (so no operationalization choice is made to taste later). It does NOT re-pin the legs.

1. **In-register (leg a)** reads the FULL register — `config.universe.themes` baskets + `themes.json` — so
   a **source-departed-but-retained** name counts as in-register (it IS in the universe → not novel).
2. **ETF-membership (leg c2)** reads the seed theme's ETF constituents **point-in-time as-of the run date**
   (the caller supplies that set); a name in the seed's own ETF is disqualified.
3. **c2 dominates c1:** a claim citing BOTH the ETF and a second-order source still requires the *entity*
   ∉ the seed's ETF — an ETF co-citation never rescues an in-ETF name.
4. **Name matching** is EXACT — ticker, else canonical, normalized via `generator.entity._norm`; **no fuzzy
   string matching** (so a borderline alias can't be resolved to taste).
5. **Matched-version is an ASSERTION** (`assert_matched_version`): every artifact must carry `model` +
   `prompt_sha` and all must be equal, else the set is refused — a pre-stamp run (e.g. the 2026-06-22
   autonomous artifact) is a non-load-bearing reference, never counted toward the k=5.
6. **The scorer computes Stage-1 fully offline** (legs a+c, ≥3/5 stability, the subset plumbing-check, the
   DROP split) and emits the Stage-2 candidate list; **Stage-2 needs the ONE live council `under_narrated`
   re-score** on that list — the scorer then computes `YIELD(seeded) > YIELD(autonomous)` from the labels.

## §9 — Pre-spend correction (dated amendment 2026-06-27, BLIND — no emission exists, so anti-HARK-clean)

A pre-spend red-team caught a **structural** flaw seeded by the original `nuclear_fuel` recommendation
("multi-source"), which propagated into §3/§4 and was sealed by the #108 universe-drop. Corrected before
the first run.

- **The error:** "multi-source" is NOT the property that matters; **"has a non-ETF *entity-resolvable*
  source"** is. `nuclear_fuel`'s non-ETF sources `nrc`/`eia` are `ENTITY_FREE_MACRO` (§3 verify-class:
  structural/series, no resolvable company), so leg (c) is **unsatisfiable** there — every surviving entity
  is in the ETF (c2 fails), every non-ETF entity is DROPped pre-scoring (`dropped_entity_unresolved`). The
  seeded yield is **zero by construction**, and `stage1` would misread empty-⊆-autonomous as a
  plumbing-negative — filing a **false negative against the whole seeded-generator idea**.
- **Leg (c) redefined** (§4): "non-ETF source" → "non-ETF **entity-resolvable** source" = §3 verify-class
  `ENTITY_BEARING` or `FREE_TEXT_RECIPIENT`, NEVER `ENTITY_FREE_MACRO`. The scorer reuses
  `generator.verify.SOURCE_CLASS` (single source of truth): `second_order_sources(nuclear_fuel)=∅`,
  `(space_smallcap)={federal_awards}`.
- **First theme → `space_smallcap`** (§3): it routes an ETF (UFO/ARKX, for the c2 exclusion) AND a
  theme-scoped entity-resolvable source (`federal_awards` NAICS 336414, recipient-name = `FREE_TEXT_RECIPIENT`)
  — the only currently-routed theme with both. (More narrated than nuclear ⇒ a harder, more-meaningful
  Stage-2 bar.) `nuclear_fuel` is deferred to **option (b)**: theme-scope `customer_concentration` into its
  slice (the 10-K supplier-of-the-supplier linkage) — the fidelity upgrade after an existence proof.
- **Feasibility guard** (P1, the cluster-cap-guard pattern): `slice_feasible` asserts ≥1 non-ETF
  entity-resolvable source; `run_generate` **fails closed (`seed_slice_infeasible`) before any router
  build/spend** on a dead slice — never a misattributed negative.
- **§6 DROP-split read corrected:** the dead-slice / entity-free signal is a high
  **`dropped_entity_unresolved`**, NOT `dropped_fact_untraced`.
- **#108 kept, not reverted:** the universe-drop is correct for a theme with a **theme-scoped**
  entity-resolvable source (`space_smallcap`'s `federal_awards` survives it — verified); only option-(b)
  themes that depend on universe-wide entity-bearing pulls need it refined, which option (b) does explicitly.

## §10 — The candidate-universe ceiling gate + the space_smallcap result → pivot to option (b) (2026-06-27)

The §9 `slice_feasible` guard checks source-class **existence** (necessary). It does NOT check
candidate-universe **non-emptiness** or **mechanism-alignment** (sufficient). Added as a standing **free,
offline pre-spend gate** (`python -m generator.ceiling`; lives inside `generator/` per the §6.4 firewall):
list the entity-resolvable second-order source's
recipients MINUS the theme's ETF; if the residual is all narrated primes + private entities (no quiet,
**public, ticker-mappable** name), a bounded-live spend returns a structural negative — learnable for $0.
**Required before any bounded-live spend** (the pre-check that would have killed `nuclear_fuel` pre-freeze).

- **`space_smallcap` ceiling result (2026-06-27):** the 336414 residual (minus UFO/ARKX) is **31 names, all
  narrated primes** (Raytheon/RTX, BAE, Aerojet→L3Harris, Textron/TXT, General Dynamics/GD, Kratos/**KTOS
  already in-universe**) **or private** (United Launch, Blue Origin, Astranis, Castelion, Corvid, Intelsat,
  Dynetics, MBDA). **No quiet public ticker-mappable residual.** `federal_awards` (336414 *manufacturing*
  prime awards) structurally surfaces the **integrator/up-chain** end, not the down-chain quiet supplier — a
  mechanism inversion. A `space_smallcap` spend returns the **up-chain negative** (the corpus source's skew,
  not the generator's ceiling). **Do not spend on it as the positive-shot.**
- **Pivot → option (b) is the REAL test.** Theme-scope `customer_concentration` (an `ENTITY_BEARING`
  down-chain source: a 10-K disclosing a quiet component maker sells >10% to a space prime is *exactly* the
  supplier-of-the-supplier, pointing the right direction). `space_smallcap`-via-`federal_awards` is at most a
  "does the plumbing produce an interpretable end-to-end read" run; option (b) is the "does seeded-gen
  out-quiet the human" run. **Build option (b) next** (theme-scope `customer_concentration` + the criterion
  amendment), then re-run the ceiling gate on its slice before spending.
- **Deferred until option (b) spends:** wiring the generator's live roster (harmless, theme-independent), and
  the c2 name-leak edge (pass BOTH ETF symbols AND normalized names into `etf_holdings`) — more live for a
  `FREE_TEXT_RECIPIENT` theme than for `customer_concentration` (`ENTITY_BEARING`, symbol-resolved).

## §11 — Reach-diagnostic adjudication: option (b) is DEAD; the theme-scoping-vs-reach conflict (2026-06-28)

A red-team flagged a **measure-first violation**: §10 proposed option (b) on mechanistic plausibility
without consulting `records/2026-06-23_corpus_reach_diagnostic.json`, which already scores every source's
non-universe + quiet reach. Read now (per-source `n_nonuniverse` / `nonuniverse_with_news` /
`nonuniverse_quiet`):

| source | class | n_entities | in-univ | **non-univ** | with-news | **quiet** |
|---|---|---|---|---|---|---|
| customer_concentration | symbol_keyed | 20 | 20 | **0** | 0 | 0 |
| federal_awards | free_text_recipient | 157 | 0 | 0 | 0 | 0 *(157 unknown — recipients don't ticker-map)* |
| etf_constituents | symbol_keyed | 129 | 26 | 102 | 0 | 0 |
| capital_raises | cik_bearing | 1273 | 13 | **1260** | **0** | **0** |
| nrc / eia / bls | entity_free | — | — | — | — | — |

- **Option (b) is DEAD — confirmed structural.** `customer_concentration` reaches **0** non-universe names
  (`n_nonuniverse=0`): it's `@all_basket_symbols`-scoped (the filers ARE the basket) and never extracts the
  *named customer* (`{percentage, n_customers, snippet}` only — the customer NER is a deliberate §2 no-LLM
  punt). So leg (a) excludes every entity by construction; it cannot deliver the down-chain supplier. **Do
  not build it.**
- **CORRECTION to "no source reaches quiet":** the diagnostic does NOT show that. `capital_raises` reaches
  **1260 non-universe** names (and `etf_constituents` 102). Their `nonuniverse_quiet=0` is **confounded by
  `no_fetch`**: `nonuniverse_with_news=0` (no cached news for non-universe names) → quiet is *unclassifiable*,
  not measured-zero. So quiet-reach is **UNMEASURED for the sources that do reach non-universe.**
- **The real structural blocker — theme-scoping vs reach conflict.** The only non-universe-reaching source
  (`capital_raises`) is **universe-wide** (by form, not theme). The seeded slice (`restrict_to_theme`) DROPS
  the universe block → discards `capital_raises` → the slice keeps only theme-scoped sources
  (etf=in-universe, nrc/eia=entity-free, federal_awards=up-chain/unresolvable), none of which reach
  non-universe. So **theme-scoping (to remove the LLM's salience bias) also removes the non-universe reach** —
  the two goals conflict on the current corpus. This is the 06-23 "magnitude rides coverage" finding one
  level down: the human seed decorrelates the *sector*, not the *source's* coverage skew.
- **Next (measure-first, NOT a build):** (1) un-confound — re-run the reach diagnostic **with news** on
  `capital_raises`/`etf` non-universe sets to measure whether any are genuinely quiet (a keyed box step);
  (2) if quiet reach exists there, the real work is a **theme-scoped non-universe-reaching source** (a corpus
  build), NOT re-slicing; if none, the seeded-generator phase **pauses** on that finding (the honest answer
  to "can a grounded generator out-quiet the human" on this corpus). Either way: **don't build option (b),
  and don't conclude "dead" from the confounded zero** — measure the quiet-reach first.
