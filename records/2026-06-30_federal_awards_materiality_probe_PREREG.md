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

---

# RESULT (post-run, dated 2026-06-30) — GRAVEYARD (dated negative). Source-negative, not market-empty.

The frozen blind body above is unedited; this is the dated addendum (the `§10-append` pattern). The
cheap leg ran; the chain screen was never reached (correctly — the population isn't real). **Verdict:
GRAVEYARD.** `federal_awards` joins `capital_raises`; the **EDGAR funnel as a *surfacing apparatus* is
settled** (both tractable sources ceilinged) — a clean dated negative consistent with the project's
epistemics (divergence / FSSD / seeded-generator). The resolver stays ephemeral (BUILD not earned).

## The finding (the durable output) — the size-cell is structurally near-empty, NOT "prime-dominated"
The material `≥10%` set was **2, both prime/large** (LMT 26%, SAIC 16%; **NON-OBVIOUS = 0**). But the
durable finding is **not** "the salient end won the material cell" — that framing is a **ceiling
artifact** (see caveat 1: LMT's "$30.1B" is a multi-year IDV *ceiling*, not a period obligation; under
a clean obligated-period measure the cell is ~empty for **everyone, primes included**). The real result:

> **The `material ∩ quiet ∩ optionable` cell is structurally near-empty because the three constraints
> are mutually antagonistic.** Optionable ⇒ cap not tiny (thin chains below ~$200–300M); material ⇒
> award ≥10% of a non-tiny cap ⇒ a *large* award; and a quiet small-cap winning a large *prime* award
> is both **rare** (small defense names mostly **subcontract** — their wins are recorded under the
> prime, invisible to a prime-award feed) and **self-limiting** — when one does win big, the public
> award **re-rates** it out of "small" and "quiet" (exactly what KTOS/AVAV did; the recall test caught
> them resolved-but-non-material). Prime awards are the wrong **locus**; the quiet operational signal
> lives in **subaward** flow this source doesn't capture.

**Transferable lesson (scoped correction to the materiality-enricher escape):** a **current-cap-
denominated materiality enricher self-defeats on visible catalysts** — the catalyst moves the
denominator — so it works as an under-narration proxy **only where the catalyst isn't visibly priced**,
which a *public award*, by construction, is.

**Source-negative, not market-empty:** near-empty *here* does **not** mean the market is dry on
inflections (not an earned World-2 on the market). It means **prime federal awards are the wrong
instrument** — the inflections may well exist; this feed can't see them. That distinction keeps the
negative from reading as defeatist and points back to where the signal does live (curation; subawards).

## The data (per the pinned distribution-read, not a bare count)
| read | result |
|---|---|
| enumeration (180d, ≥$10M, DoD A/B/C/D) | **core 2,152** + **flagged 2,106** = **4,258** awards; **BOTH EXHAUSTED** (`hasNext=False` at 22/60 pages; smallest award fetched = $10.0M = the floor) — see "Enumeration-exhaustiveness" below |
| name→ticker join | **26** unique public tickers; **75.9%** recipient-rows unmatched (private-awardee + *prime*-subsidiary majority — Accenture Federal, AAR Government Services; prime-biased, doesn't threaten "0 quiet") |
| market-cap join coverage | **23/26 = 88.5%** (per-symbol price; 3 no price/shares) |
| material **≥10%** | **2 — both prime/large**: LMT 26% (336411), SAIC 16% (541712). **NON-OBVIOUS = 0** |
| 5–10% shoulder | LDOS 6% (prime), **TLS 6%** (Telos — the *only* quiet small-cap anywhere near the line, **below** the pinned 10% threshold). Shoulder **not "populated"** → the AMBIGUOUS→revisit-threshold door (blind §"Decision rule") is **not** triggered; recorded as the lone hint, not a revisit. |
| shortlist recall | **AVAV, KTOS** resolved (the only shortlist names with a ≥$10M in-window DoD award); **both non-material** (caps re-rated past it). **Recall test SATISFIED** — the verdict is not a join leak. |

## Enumeration-exhaustiveness (the load-bearing check — stands in for both of option-(b)'s reruns)
The failure mode that bit this path twice is *top-by-amount enumeration not reaching the small awards*.
Re-verified post-`$10M`-floor: **both** NAICS-group fetches **EXHAUSTED** (`hasNext=False` at page 22 of
60; smallest award = exactly $10.0M, so the desc-sorted pull reached the floor — no material award hides
beyond a cap). With both groups exhausted, **"0 quiet" is airtight on the only dimension that can flip
it.** (Skipped, deliberately: the obligated-period de-confound and the parent/subsidiary recall pass —
option (b). The ceiling-confound cuts *toward* emptier, so the clean obligated number only tidies a
non-load-bearing figure; shortlist recall is clean and unmatched-leakage is prime-biased, so a sub
recall pass can't manufacture quiet names. Running them would be rigor-theater on a settled negative.)

## The `$10M` floor (disclosed as a tractability bound — added mid-run, so named)
A server-side `award_amounts.lower_bound = $10M` was added during the run to bound the enumeration
(the fix for the page-cap). **Justification:** a sub-$10M award is **<5%** of any optionable-sized
(≥$200M-cap) name — **below the 5% shoulder** — so nothing material to a *tradeable* name lives beneath
the floor. It is a tractability bound, not a yield knob (it cannot drop a material-to-optionable award).

## Auditability — three protocol-sanctioned plumbing fix-and-reruns; **none touched the frozen decision pin**
1. **enumeration page-cap** (top-by-amount missing small awards) → **core/flagged NAICS split + the $10M floor** (bounds each group; honors the blind NAICS-bucketing pin).
2. **price-batch bug** (one bad symbol zeroed the whole batched bars call) → **per-symbol price** fetch.
3. **`3M COMPANY` (≡ MMM) recall leak** ("COMPANY" ≠ EDGAR's "CO") → **suffix-strip** in `norm()` — this was the **frozen recall protocol firing *as designed*** (a demonstrated public-name leak ⇒ fix-and-rerun, never graveyard). Recall jumped 15→26 resolved.

Each was a deterministic plumbing fix under the pre-specified fix-and-rerun protocol; **none** touched
the frozen threshold (10%), window (180d), denominator, or decision rule → the negative is **not
HARK-tainted**.

## Two caveats (both cut *toward* the negative — they strengthen it)
1. **Ceiling-confound** — LMT's "$30.1B" is a multi-year IDV **ceiling**, not a period obligation. This
   **overstates** prime materiality, so the *true* (annual-obligated) material set is **even emptier**.
   The confound only **strengthens** the negative (it is why "prime-dominated" is the wrong framing).
2. **Name-join recall is decent-not-airtight** — 26 public cos from 4,258 awards; the shortlist recall
   **passes**, and the unmatched are dominated by private LLCs + *prime* subsidiaries, so a leak is
   **prime-biased** and can't manufacture quiet names. Not airtight, but it cannot flip "0 quiet."

## Footnote (where you'd look if you ever revisit — explicitly NOT now)
The size-cell finding *points* to **subawards** as the only place federal-contracting quiet signal could
live: small-caps **subcontract**, and subaward reporting carries a lag that *might* escape the visible-
catalyst defeat. But that's a **new source with its own completeness/lag wall** — flagged, not opened.

## Tie-back
This **reinforces** the standing conclusion rather than adding a new one: filing/enumeration sources
surface the **salient end** and structurally miss quiet under-narration — now shown **twice**
(`capital_raises` can't go quiet; `federal_awards`' target cell is empty). The EDGAR funnel as a
*surfacing apparatus* is **settled**, and the binding constraint returns to where it was: **manual
curation throughput** — the irreducible human judgment that decouples candidates from the salience axis.
There is no automated substitute on these sources; the human judgment **is** the input.
