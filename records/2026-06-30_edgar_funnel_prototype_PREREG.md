# PRE-REG (frozen, BLIND, before the run) — the EDGAR-event funnel prototype

**Date:** 2026-06-30 · **Status: FROZEN before the prototype runs (anti-HARK).** The event-type
whitelist and the yield band are pinned here so the experiment is **decisive**, not another ambiguous
lead. A surprising yield is a *finding*, not a license to re-tune.

## Why this machine (and why the obscurity null does NOT foreclose it)
The obscurity prototype (2026-06-30, null) tested the WRONG machine: news-count quietness over an
*unfiltered* universe. It failed on the broad→quiet direction (78% funds, obscurity⊥liquidity, the
feasibility wall) and on a **salience-coupled proxy** (news-count). It conflated **company obscurity**
with **inflection under-narration** — and the first is anti-correlated with tradeability (quiet =
illiquid = no far-OTM chain).

This machine inverts it and separates them: **tradeable-set first**, **salience-blind event source**
(EDGAR is unranked — a tier-2 supplier's 8-K is the same form as a hot name's), and it is a **funnel,
not an oracle** — it mechanizes the *anti-salience surfacing* (what humans are bad at), NOT the
under-narration judgment (which stays the human/council's). The edge is **"this filed inflection is
unpriced on a name analysts already cover,"** never "the company is obscure" — so a liquid, covered
company is *expected* and fine.

## What the prototype IS (read-only; the experiment is World-1-vs-World-2 discrimination)
It surfaces a candidate set; it does NOT judge narration (step 3) or admit anything. Its purpose is to
tell us which world we're in:
- **World 1** — qualifying names exist now and we were *under-surfacing* (every prior machine was
  salience-coupled / wrong-population). → the funnel surfaces a judgeable set; one survives step-3.
- **World 2** — the market is genuinely dry on tradeable unpriced inflections right now. → the funnel
  runs clean over a real enriched set; **WATCH becomes earned, not anxious.**
"Empty" stops being a function of operator bandwidth and becomes trustworthy.

## The frozen design (pinned blind)
1. **Tradeable-set filter (step 1) — kills the obscurity null's three failure modes by construction:**
   - **operating companies** (exclude funds/ETPs by SIC / asset class — the 78%-funds artifact);
   - **chain-depth** sufficient to express a **15–35% OTM, 180–365d** structure;
   - **ADV ≥ $3M** and **cap-fit** (one contract ≤ $1,000) — the existing feasibility floors.
   Expected size: a few hundred to low-thousand names.
2. **Event-type whitelist (step 2) — Rule-0, design-time, salience-blind.** Surface a tradeable name
   iff it carries a recent whitelisted *inflection-bearing* event, using the EXISTING built adapters:
   - `capital_raises` (424B5 / S-1 shelfs/raises), `federal_awards` (USASpending/DoD), `nrc_dockets`
     (reactor pipeline) — trailing **90 days**;
   - `customer_concentration` (10-K >10%-customer second-order exposure) — most-recent filing.
   - **DROP the noise:** routine earnings-release 8-Ks, director/officer changes, routine shelf
     take-downs. (Selecting event *kinds* is the design-time funnel choice; it never ranks per-name.)
3. **Yield band (the read criterion — PINNED BLIND):** the step-2 output (tradeable ∩ whitelisted
   recent event), BEFORE any narration judgment, should fall in **[3, 20]**:
   - **< 3** → the tradeable∩inflection set is genuinely sparse → **World-2-leaning** (real-null
     evidence about the lever), OR the whitelist is too narrow (noted, not re-tuned mid-experiment).
   - **3–20** → a **judgeable enriched set** → proceed to step 3 (human/council judges *event*
     under-narration: "is THIS filed inflection unpriced given how the name trades") → premise-check
     (§11 Rule 5) → admit.
   - **> 20** → **not selective enough** → the human step would inherit the salience trap (attention
     re-sorts to the recognizable names = salient = wrong). Re-tighten the whitelist/recency and
     re-freeze for a NEXT run — do NOT judge a >20 set (that is where the back-door trap re-enters).

## Seam discipline (unchanged)
- **No cheapness / no motion at the input.** The funnel selects on tradeability + event-kind only;
  IV/cheapness stays the gate's exclusive job at decision time (§2 / CGS §7). Survivors are
  CANDIDATES for step-3 + the premise-currency check, **never admits**.
- The prototype is read-only: no `config.universe.themes` edit, no loop/council/gate change, no admit.
  It produces a candidate list + the yield-band read; step 3 (narration judgment) is the human's.

---

## v2 amendment — frozen BLIND before the v2 run (the §3 ">20 → re-tighten + re-freeze for a NEXT run" path)

**Date:** 2026-06-30 (later) · **Status: FROZEN before the v2 run.** v1 yielded **59 > 20** → not
selective enough → per §3 the v1 set is NOT judged; re-tighten on PRINCIPLE, re-freeze, re-run once.
Band `[3,20]` and the >20-recursion rule are **UNCHANGED**. This amendment is the *content* of the
re-freeze, not just prose — `is_atm_offering`'s behavior is the HARK-exposed surface, so it is pinned
by committed fixtures, not a tunable knob.

### What v1 actually was (and why "59→27→15" is discarded, not "soft")
v1 ran step-1 (tradeable) ∩ step-2 (whitelisted recent event) but **could not honor the frozen
step-2 "DROP… routine shelf take-downs"** — `corpus/capital_raises.py` emits structural metadata
only (`{ts,cik,company,accession,file,date_filed,form}`); no deal structure exists to filter on. So
v1's 59 is **routine-takedown-inflated**, and the modeled 59→27→15 is **discarded** (unverifiable —
the v1 driver was ephemeral and the adapter can't do the cut; and the "15" modeled an `ex-biotech`
*sector* cut now rejected as HARK-exposed). **The v2 run's yield is the only real read.**

### Run-1 = CONFORMANCE to the frozen design (no new tightening; no knob; can't be count-targeted)
1. **Enforce step-1's achieved-OTM band against the REAL chain** — a 15–35% OTM, 180–365d structure
   must be *buildable on live strikes* (not merely "options exist"), with ADV ≥ $3M and one
   contract ≤ $1,000. (This is the existing §11 feasibility floor, now actually enforced.)
2. **Drop routine shelf take-downs = clean ATM / continuous offerings**, via
   `data.prospectus.is_atm_offering` / `classify_offering` (built here; FSSD §3 specced this
   primary/secondary/**ATM-shelf-refresh** split as a v1.1 knob that died unbuilt).

### The separator (the HARK-exposed line — pinned)
- **DROP iff** `classify_offering(prospectus).kind == "atm"` — a clean, **conflict-free** cover ATM
  signal. **KEEP-BIASED:** any conflicting structural signal (a firm-commitment underwriting table,
  a notes offering, a selling-holder/forward), or an absent/ambiguous signal → **KEEP** (→ step-3).
  The discrimination is **cover-localized** (the offering *description*), never document-wide keyword
  presence (grounded on real 424B5 covers 2026-06: risk-factor "from time to time", a passing mention
  of an *existing* ATM program, and "at-the-market offerings" in a notes risk-factor list all
  false-fire a lone-keyword OR).
- **Firm-commitment underwritten = a CANDIDATE inflection → KEPT** ("is this raise funding the
  inflection?" is the step-3 question; over-excluding biases toward a false World-2 — the same
  asymmetry that fixes recency below).
- **Fetch/parse failure → KEEP (step-3) + flag; NEVER drop.** Report **parse-coverage** alongside the
  yield: a low yield driven by unparsed prospectuses is *plumbing*, not a dry market (the
  fill-diagnostic rule, `PREREG_EVIDENCE_GROUNDING`). Re-fetching failures is the sanctioned remedy,
  NOT a HARK re-roll.
- **Behavior is pinned by committed fixtures** (`tests/test_prospectus.py`, real-grounded): precision
  is pinned (**zero false ATM-drops** on the labeled non-ATM set — the keep-bias property); recall is
  reported (clean-ATM 3/3 on the labeled set). A later silent re-tune of the keyword list is a count
  channel → the fixtures freeze with this spec.

### Run-1 is DIAGNOSTIC
Report the yield **broken down by triggering source / offering kind** (clean-ATM dropped · firm_commitment
· convertible_notes · debt_notes · registered_direct · selling_holder · unknown · S-1; and by event
source for the non-capital_raises whitelist) + parse-coverage — so a >20 outcome points straight at the
run-2 lever instead of needing another investigation.

### Held for run-2 (NOT bundled into the discriminating run — clean one-variable)
- **Recency stays 90d.** Under-narrated ⇒ slowly diffused ⇒ a *wider* filing-recency window is
  thesis-coherent; 30d assumes the fast pricing whose absence *is* the edge. 45d is the run-2 lever if
  conformance is still >20 (never 30d).
- **S-1 stays whitelisted** (it is *not* in the noise list) but its survivors carry the IPO-false-quiet
  confound (no pre-filing baseline; the seeded-source negative) → **flag at step-3**; drop S-1 as a
  *run-2 whitelist* tightening only if it is a >20 driver.
- **Straight debt-notes stay KEPT-flagged in run-1** (the drop pile = clean-ATM only, as settled).
  Adding straight-notes to the drop is the obvious run-2 lever and is keep-bias-safe (a notes
  takedown can never be an equity-inflection candidate). **Convertible** notes stay kept-flagged
  (could fund an inflection).

### FSSD backbone
FSSD graded 424B5s directly: top-friction-decile CAR −1.91% vs random-in-name null −1.78% → conditioning
on the 424B5 adds ~nothing over the small-cap friction characteristic → **424B5 raises as a class carry
no event-specific signal**. So the routine-takedown drop is *essential* (the source is mostly noise),
and the funnel's edge rides on step-3 judging the *non-routine* survivors' event under-narration.

### Seam / safety (unchanged)
Read-only: no `config.universe.themes` edit, no loop/council/gate change, no admit. No cheapness/motion
at the input. The ephemeral driver lives outside the repo; only the reusable `classify_offering` parser
+ fixtures are committed (additive/INERT — nothing in the live loop calls it).
