# PRE-REG (frozen, BLIND, before the probe runs) — the DoD-awards materiality probe

**Date:** 2026-06-30 (later) · **Status: FROZEN before the cheap leg runs (anti-HARK).** All
yield-determining knobs + the join-recall protocol are pinned here so the read is decisive. Converged
over a multi-round operator red-team; values are set on principle, before any probe yield is seen.

## Why this probe (lineage)
The EDGAR-event funnel (`2026-06-30_edgar_funnel_prototype_PREREG.md`) whitelisted four event sources;
run-1 was a **single-source degenerate run** (3 dark; only `capital_raises` wired) and settled
**capital_raises as a weak standalone source** — a *financing* event (fires on "raised money"), the
FSSD-null class, that **can't go quiet** (so can never earn World-2) and **can't reach the band without
thesis-violating tightening**. So the funnel has collapsed, for now, to **`federal_awards` alone = a
DoD defense/space/gov-tech *contractor* funnel** (not all-federal; the multi-source decorrelation
rationale is **deferred, not delivered** — it accrues only if `nrc_dockets` is later built; `nrc` is a
static fleet snapshot today, `customer_concentration` is §2-NER-blocked).

**Why federal_awards escapes the idea-supply graveyard (the nameable reason):** a contract win is a
genuine **forward-revenue inflection** (unlike a financing event), AND it carries a **salience-anti-
correlated separator** the seeded-generator lacked — **materiality = award / scale**. award↑ with
coverage, scale↑ with coverage, but the **ratio↓** → it selects the under-narrated end. Materiality is
to `federal_awards` exactly what the routine-takedown (ATM) drop is to `capital_raises`: the Rule-0
"what counts as an inflection-bearing event" separator within a whitelisted source.

## The pinned design (BLIND)
| knob | pinned value | rationale / anti-HARK |
|---|---|---|
| **window** | **180d** | composition is staleness-invariant (a 5-mo-old material award is still a "quiet contractor, material award" data point); longer improves the quiet:prime ratio (primes saturate every window; small-caps accumulate) + cuts the false-empty-from-sparsity risk (the probe's one uninterpretable failure). The production build may drop to 90d for fresher step-3. |
| **denominator** | **award_obligated / market-cap**, market-cap = shares-out (XBRL) × price, **as-of window-end** | chosen for the **pre-revenue reason** (revenue is undefined/explosive for pre-revenue targets — RKLB-early/BBAI/ASTS, the population we want), **NOT** for price-neutrality. **DISCLOSED COUPLING:** market-cap embeds price → a negative-momentum tilt near the cutoff (fallen → lower cap → higher materiality → likelier to pass). Second-order away from the cutoff, weakly thesis-aligned ("fallen-then-catalyzed"), but NAMED so a fallen-heavy set reads as the artifact, not signal. As-of is **window-end** because the endpoint carries **no per-award date** (the parsed record has no date field). |
| **threshold** | **≥10%** | a **Schelling anchor** to prevent tuning to the known names (NOT an accounting derivation — award/market-cap is not a SAB-99 concept); more thesis-coherent than 5% (a 5% award is a weaker re-rating) and more robust against admitting large names. **Read the distribution, not the count** (below). |
| **NAICS** | aerospace/defense mfg (3364), nav/guidance instruments (334511), computers/comms/semis (3341–3344), shipbuilding (3366); **5415/5417 (IT/scientific-R&D) FLAGGED + bucketed separately** | sectors where a contract win is a genuine forward-revenue inflection for a public co (vs services/staffing/construction = routine churn). 5415/5417 carry staff-aug churn → kept but **bucketed** so a quiet count that's mostly-5415/5417 is discounted, mostly-3364/334511 is strong. DoD agency set (toptier 097) as-is; NASA/Space-Force are extensions iff DoD clears. |
| **"obvious" shortlist (FLOOR + recall test)** | RKLB · KTOS · RCAT · AVAV · PL · LUNR · BBAI · ACHR · RDW · DRS · KULR · SIDU · BKSY · SPIR · MNTS · ASTS · ONDS · UMAC · ARQQ (extensible) | the known quiet-defense/space names a desk already tracks. Used as a **FLOOR** (surfacing *only* these = salience-check failure), **not the win gate** → its incompleteness can't manufacture a false win. Also the **recall-test set** (below). |

## The match (name → ticker) — the join the graveyard verdict is conditioned on
`federal_awards` carries no CIK/ticker — only a free-text `recipient` name. The join is **net-new**
(capital_raises resolved via filer CIK). **A leaky join silently drops subsidiary/DBA/renamed quiet
filers → a thin quiet set reads as a FALSE GRAVEYARD.** Grounded 2026-06-30: normalized-exact already
leaks **RKLB** (renamed to "Rocket Lab Corporation"; USASpending carries "Rocket Lab USA, Inc.").
- **Method:** normalized-exact (upper, strip punctuation + corporate suffixes, collapse whitespace)
  against `company_tickers.json` `title`, **+ a curated overrides map** seeded from shortlist misses
  (RKLB→"Rocket Lab Corporation", …). **No fuzzy/token pass** — a false match corrupts the materiality
  denominator; exact+overrides is precise-and-auditable.
- **Report:** matched count, **unmatched rate**, and a **sample of unmatched names** (to eyeball whether
  *public* names are leaking, vs the expected private-awardee majority).
- **RECALL TEST (conditions the graveyard verdict):** every shortlist name with a material award in the
  window MUST resolve. If one doesn't → the join is leaking → **fix-and-rerun, never graveyard.**

## Decision rule — read the DISTRIBUTION + COMPOSITION, not a bare count
Only after the recall test passes AND the unmatched-sample shows no obvious public-name leakage:
- **BUILD / World-1:** the material set is majority **non-prime**, of **plausibly-quiet genuine-
  contractor character** (a step-3 read — character, not list-membership), and includes names **beyond
  the floor**. Judgeable size for a human (the [3,20] *sense*, distribution-read).
- **GRAVEYARD (decisive negative):** prime-dominated, OR empty including a thin 5–10% shoulder, OR only
  floor names. → dated negative; the EDGAR funnel as a *surfacing apparatus* is settled (both tractable
  sources ceilinged: capital_raises noise-only, federal_awards skew-only).
- **AMBIGUOUS → revisit-threshold:** sparse ≥10% **with a populated 5–10% shoulder** → NOT dead; the
  threshold is a touch tight, a future build adjusts. Threshold is pinned → **no mid-probe re-tune**;
  this is a recorded "revisit", not a re-roll.

## Staged probe (cheap leg first = the early-out before the chain spend)
1. **Cheap leg:** NAICS-bounded 180d enumeration → name-intersect (**+ shortlist recall test**) →
   market-cap join → materiality filter → **count + characterize**, sliced by **NAICS bucket × market-
   cap tier × {5%, 10%}**, **deduped per recipient** (largest material award per recipient — task
   orders/mods ≠ separate inflections), + **enumeration cost** + **both join-coverage numbers**
   (name-join unmatched rate; market-cap-join coverage). Prime-dominated/empty **and recall-verified**
   → dated negative **before any chain fetch**.
2. **Chain screen iff** the quiet-contractor population is real → the existing feasibility/OPRA screen
   on those survivors → tradeability → read against the rule.

## HARK structure (made visible / auditable)
The apparatus is shaped around a nameable population (defense small-caps) = acceptable Rule-0 *category*
design. The guards against category-shaping → answer-fitting: the **non-obvious-character win**, the
**blind-pinned floor**, the **distribution-read** (not a count), **threshold-pinned-no-re-tune**, and
the **recall-test conditioning the graveyard**. The probe is decisive **either way** — even the negative
settles the EDGAR-funnel-as-surfacing question, a clean dated negative consistent with the project's
epistemics (divergence / FSSD / seeded-generator).

## Seam / safety (unchanged)
Read-only: no `config.universe.themes` edit, no loop/council/gate change, no admit. No cheapness/motion
at the input (materiality is scale, not motion; the price-coupling is disclosed above). The ephemeral
probe driver lives outside the repo; the name→ticker resolver is committed as tested infrastructure
**only if** the probe says BUILD.
