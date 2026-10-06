# The autonomous corpus-generator discovery path — CAPPED (the third clean negative)

**Date:** 2026-06-23 · **Status:** floored to curation; the autonomous LLM-generator-synthesis path is
retired as a quiet-name *discovery* mechanism. Closed on **measurement**, not argument (the discipline
that makes divergence v1 and FSSD v2 load-bearing — see `records/edge_graveyard.md`, `CLAUDE.md`).

## What it was meant to hit
The first council INCLUDE needs a candidate that is **`under_narrated ∧ at_inflection ∧ cheap`**
simultaneously; the binding leg is `under_narrated`. The Stage-1 theme generator (`generator/`, frozen
`PREREG_THEME_GENERATOR.md`) was the intended structural fix: synthesize falsifiable secular-theme
mechanism-claims from the §2-clean Stage-0 corpus (`corpus/`), citation-verified, so genuinely-quiet
themes clear the bar **without loosening it**.

## The finding (class-level, not a tuning failure)
**A §2-clean corpus is blind to *quietness*, and its structural inflection signals surface the *loud*
end by construction.** `under_narrated` is a news property and §2 forbids **prices, IV, momentum, and
news-sentiment** at the corpus input (AST guard `tests/test_corpus_stage0.py:111-124`), so no structural
proxy for quietness survived (cadence ⊥ quietness, *measured*, below). Inflection is different: the
corpus *can* express it structurally (award milestones, filing events, the fundamental-acceleration door
below) — but **every structural discovery source that *ranks* candidates ranks them by *event
magnitude*, and magnitude correlates with coverage**: biggest awards → primes, biggest/most-frequent
raises → Alphabet/sovereigns, buzziest S-1s → the SPAC firehose. The one source that worked —
`etf_constituents` → FRO/CDE — is the exception that proves it: it doesn't rank by magnitude, it's
seeded by a human sector choice, and the human supplies the one thing no magnitude-ranked scan can —
**decorrelation from the coverage axis**. So the irreducible human input is not "sector-level
under-narration" but specifically *the judgment that decouples a candidate set from the salience axis
the corpus is built on.*

This is stronger than "the residue was loud": it's a *structural* reason — magnitude-ranking rides the
coverage axis — not a member-by-member tally, which is why one more member test would add little (and
why the cheap closes below were sufficient).

## The evidence (cheapest-first; graded, not asserted)
1. **`gen_rescore` (prior session) — corroboration, not the proof:** the generator's *framing* did not
   move the council's `under_narrated` read (it re-derived NARRATED names, 8/9 already in-universe). On
   its own this only shows framing is inert; the floor's weight is carried by the corpus-reach evidence
   below + the structural argument that the generator can only propose *which* names, not change a name's
   coverage. gen_rescore corroborates.
2. **Phase-0 corpus-reach diagnostic** (`scripts/corpus_reach_diagnostic.py` →
   `records/2026-06-23_corpus_reach_diagnostic.json`; NO-FETCH/NO-LLM over the warm cache). The
   entity-surfacing sources select for the **wrong populations**:
   - `customer_concentration`: **20/20 in-universe, 0 non-universe** — an entire source = the curated
     leak (`@all_basket_symbols`, `corpus/content.py:70`).
   - `federal_awards`: prime-amplifier — **Raytheon 391 / Lockheed 354 / Boeing 189 / Northrop 64**.
   - `capital_raises`: 1,273 issuers, 1,260 non-universe — but the population is volume-skewed to the
     **loudest** names (top non-universe by filing-count: Jefferies 87×, Alphabet 13×, Amazon, NextEra,
     CIBC, BBVA, Republic of Turkey).
   - `etf_constituents`: the **themed ETFs we already chose** + their holdings.
   - (The curated→CIK map resolved **38/38** — lever #1's keystone validated, but mooted by the floor.)
3. **Cadence eyeball (free, no-fetch):** filing-cadence is **orthogonal** to quietness. Quiet dilutive
   micro-caps file 424B5s *constantly* (Trio Petroleum 11×, Tamboran 6×, AIM ImmunoTech 6×); the
   `count==1` slice is **large infrequent issuers** (Abbott, AT&T, American Tower, Ameriprise) +
   the **SPAC/shell/crypto-ETF S-1 firehose** (…Acquisition Corp / AI-named shells / ARK CoinDesk).
   So a §2-clean cadence filter does **not** de-louden capital_raises into a quiet tradeable slice.
4. **SBIR strong-version leg — CLOSED ON MEASUREMENT.** SBIR.gov 403s the bot UA (like FERC) and
   USASpending `spending_by_award` has no SBIR-program filter, so the faithful cheap measurement is the
   **small-business set-aside superset** (SBIR ⊂ it) via USASpending. Of the **88** largest small-biz
   set-aside DoD awardees, **0 are public-optionable** (the lone name-match, "Tapestry Technologies" →
   ticker TPR, is a collision with the *luxury retailer* Tapestry Inc, not the defense small-biz). The
   rest are LLCs / employee-owned / private contractors. SBIR-eligibility (SBA size standards) and
   options-liquidity are **near-disjoint by legislative design** — measured, not argued. The top-by-$
   slice is the subsample *most likely* to be public (biggest revenue), so **0/88 optionable there is a
   fortiori** for the smaller, earlier-stage SBIR awards. (Query: DoD, award types A–D,
   `set_aside_type_codes` = SBA/SBP/8A/HZ/SDVOSB/WOSB/EDWOSB, 2024-06→2026-06, top-100 by $; matched
   against `data/cache/edgar/company_tickers.json`, normalized-core.)

## What works instead (the redeployment — the actual win)
**Human-named quiet sector → `etf_constituents` → council** (the SIL/SLVP/BOAT → **FRO/CDE** path that
produced the window-#2 silver/freight admits). The human supplies the **irreducible** part — the sector
judgment that **decorrelates the candidate set from the coverage axis** (a quiet, under-covered sector,
chosen *despite* low salience); the corpus infra mechanizes the **deterministic sector→constituent
expansion** + structural enrichment. The LLM **synthesis** ambition is retired
(`gen_rescore`: it adds an expensive, decorrelation-questionable step that doesn't touch the binding
axis). Consequences:
- **Lever #1** shrinks to its cheap **symbol-leg dedup** (don't re-propose a quiet-sector holding
  already in-universe) — hygiene, build at the curation window, not on the critical path.
- The **CIK-map apparatus is shelved** (correct fix for the cik-bearing sources `capital_raises`/
  `customer_concentration` — exactly the sources the floor retires from discovery; not wrong, just
  scoped out).
- The Phase-0 diagnostic (`scripts/corpus_reach_diagnostic.py`) is a **reusable corpus-reach
  measurement**.

## The one untested §2-clean door (future; OUT OF SCOPE now)
**Fundamental acceleration** (revenue/earnings YoY accel from filed XBRL) is the single §2-clean signal
that targets *inflection* directly without price/IV/momentum/sentiment. It is **not** a rescue of the
generator path — it's a **different project**: a new deterministic discovery source feeding *curation*.
Caveats that keep it out of scope: a from-scratch broad-universe build; the **same volume-skew risk**
(cleanest acceleration skews already-narrated); it still needs the news axis bolted on for the quietness
leg. Logged here as the one door the mismatch finding does not close.

## The reusable lesson (pre-answers the next autonomous-discovery proposal)
**Structural breadth ≠ news-quietness.** Every "this source/slice is structurally quiet" ("broad",
"small-biz", "infrequent-filer") is a *hypothesis about news-quietness* that must be tested against the
news axis — cheapest-first, free eyeball before any spend, with the decision rule pre-committed (anti-
HARK). And the deeper invariant: **structural salience correlates with coverage — every magnitude-ranked
§2-clean scan rides the coverage axis — so the human's irreducible contribution is *decorrelation from
that axis* (the sector judgment that decouples the candidate set from salience), which autonomous
structural discovery cannot manufacture.**
