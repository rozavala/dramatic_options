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
