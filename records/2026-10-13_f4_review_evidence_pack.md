# 2026-10-13 — F4 review evidence pack (interim, session 14 of 30)

**What this is:** the evidence for the dated operator review that PREREG_DIRECTION_COHERENCE §6 F4 owes at the
30th L1 session under the rule (≈ **2026-11-04**) if the council has still produced zero above-floor
convictions. It is prepared early so the review is a decision, not an analysis. **Descriptive only:
nothing here loosens, re-ranks or re-segments anything.** The review decides; any change to the floor or the
criteria is its own dated amendment. Refresh the tables at session 30 and decide on those numbers, not these.

The F4 question, verbatim: *can the §10.7 `under_narrated` criterion pass on names this system is able to
curate and express?*

Source: the live DB, read-only, L1 runs #1437 → #1661 (2026-09-24 → 2026-10-13), 14 sessions.

## 1. The funnel, stage by stage

| Stage | Reading | Binding? |
|---|---|---|
| Curated universe | 47 names in 16 baskets; the weekly discovery scan covers only these | **yes: it is the whole population** |
| Council slots | 12 per session (11 sentinel + 1 hand-seed) = 168 slots | |
| Distinct names given a slot | 34 of 47 | |
| Proposer abstained (NEUTRAL) | 50 of 168 | |
| Proposer HIGH / MODERATE | 40 / 57 | |
| Strategist above LOW | **0 of 111** | **yes: the blocker** |
| Cheapness gate (today) | 33 of 40 watched names pass (IV/RV ≤ 1.2, skew ≤ 10) | no |

The last above-floor conviction was run #508 (2026-07-10). The only real position is PL (opened
2026-07-01).

## 2. Why the strategist says no

Keyword classes over the 118 explained rejections (a rejection can carry more than one):

| Reason | Rejections |
|---|---|
| The move has already happened ("behind the name", "already realized/embedded", stale print) | 70 |
| Growth decelerating / no inflection in the filings | 50 |
| Already consensus / widely covered | 23 |
| Transient or tactical move | 17 |

The binding test in practice is **`at_inflection`**, more than `under_narrated`. That matters for the F4
question as worded: `under_narrated` is cited in 23 of 118, `at_inflection`-type reasons in 120 hits.

## 3. The names reaching the council have mostly already moved

12-month momentum on the sentinel marker the council saw (154 sentinel slots):
median **+35%**; 83 slots above +30%; 24 above +100%; 52 below zero (bear framings).

The proposer's favourites are the clearest case:

| Name | Slots | Proposer HIGH / MOD | 12m momentum | Strategist's reason (latest) |
|---|---|---|---|---|
| ERO | 14 | 9 / 4 | +122% | revenue surge is an 8-month-old annual print; move behind the name |
| HL | 14 | 7 / 5 | +86% | momentum embeds the surge; quarterly acceleration −0.84 |
| KKR | 14 | 1 / 12 | −24% | quarterly acceleration −0.64; tactical rotation |
| TITN | 8 | 2 / 5 | +46% | revenue still −10% TTM; no order normalization in filings |
| AG | 4 | 2 / 2 | +108% | inflection is the completed 2025 print |

This is the structural tension: discovery surfaces on **motion** (|12m momentum| ≥ 15% or a rising-vol slope,
or a structural filing), and the council's `at_inflection` rejects names whose move already happened. The
two stages select against each other.

## 4. The slate is the whole eligible pool, and it is small

- ERO, HL and KKR took a sentinel slot in **all 14** sessions; STUB 12, FRO 10, TITN 8. NVDA holds the
  hand-seed slot every session. The top four names took **56 of 168** slots (33%) and drew the same verdict
  each time.
- This is not slot starvation. 40 sentinels are active; the 10 that never got a slot are all bear framings
  that the direction rule withholds by design (AMSC, GEV, IRDM, KTOS, LHX, LUNR, … in run #1661's note).
  The ~30 eligible sentinels plus the hand-seed are the pool, and the fairness reserve already rotates it.
  A cool-down on repeat names would only reshuffle the same pool, so it is not proposed.
- Sentinel markers refresh only when the weekly scan resurfaces the name: ERO's marker is from 2026-09-13
  (30 days old on 10-13), KKR's from 2026-09-06.
- The pool is about to shrink: from ~2026-10-19, AMSC, ATKR, CC, HBM, NNE, STUB and UUUU lose a contract in
  the tenor window (PL's open position is unaffected).

## 5. What was already tried to widen the top of the funnel

The operator asked for more top-of-funnel once before (2026-09-23); the answer then was the direction rule,
the x_lists cut and this review (`records/2026-09-24_operator_decisions.md`).

| Attempt | Date | Result |
|---|---|---|
| Fresh-inflection re-target of discovery | 06-22 | scoped; its own ceiling predicted the constraint would relocate, "freshness is scarce on this curated universe" (PREREG_FRESH_INFLECTION_FUNNEL §1) |
| Autonomous corpus generator | 06-23 | negative: ranking by event size rides the coverage axis |
| Seeded capital-raises source | 06-28 | negative: ~10 quiet names/yr, scattered financing noise |
| Obscurity gate over 6,134 optionable names | 06-30 | null: quiet ∧ feasible ∧ fresh is "structurally near-empty" |
| EDGAR-event funnel / federal-awards materiality | 06-30 | weak standalone source / graveyard |
| Revenue-acceleration ∧ price-flat feed | 07-01 | closed (§21): acceleration fires on cyclical troughs and M&A base effects |
| Reach channels (operator admits) | since 07-16 | open; orphan_watch is the one channel that yields (KKR, FIG, KLAR, STUB). W40: 3 survivors, none admitted; W41: 1, a homonym |

**Closed, and how it reopens:** the idea-supply automation line "do not revive without a standalone
thesis" (STANDING_STATE). The §21 close names two untested doors: small sub-optionable names, and
XBRL-free inflection estimators (margin, guidance changes, estimate-revision breadth), open "only if the
standalone thesis can be stated with conviction, not as a reflexive next hop".

## 6. Options (for the operator; nothing here is adopted)

**A. Widen the pool through the ratified path: an admission window now.** The last admission was 2026-09-21
(STUB); nothing has been admitted since. Every window since #3 has been off-cycle, so one now is in pattern.
The bench draft (`records/2026-09-16_bench.md`) and the window-7/9 near-misses (SARO, NTSK) are the
starting slate; the mechanical sweep and the §12 ≥ 200-days-to-expiry read apply unchanged. The lesson of §3
and the fresh funnel's ceiling: **more names on stories that are already the consensus one will meet the same
wall.** The useful admissions are theses the operator holds where the story is not yet the consensus one.
Price history stays out of curation (§2 forbids momentum and cheapness as criteria); the judgment is the
operator's.

*Provisional feasibility read (off-hours, 2026-10-14 00:02 UTC; quotes stale, not an admission read).*
`scripts/probe_basket_feasibility.py` over 17 bench names. Fit one contract under the $1,000 cap, in the
OTM band, with ≥ 200 days of runway:

| Name | Bench tier / basket | $/contract | Achieved OTM | DTE |
|---|---|---|---|---|
| BNTX | A · mrna_oncology_platform (08-23 word lapsed by drift) | 915 | 29.2% | 311 |
| BWXT | A · radiopharma / nuclear components (cluster routing open) | 950 | 22.4% | 220 |
| NTSK | window-9 near-miss | 520 | 18.2% | 339 |

Fit the cap but fail the band or runway: SARO (0.6% OTM, 185d), STNG (7.0%, 185d), HLIT (ITM, 185d), MWA and
SBLK (ITM). Over the cap: TEM $1,270, CF $1,040, VSEC $1,310, AIR $1,140, HEI $1,185. No contract in the
tenor window: IOVA, TWI, HII; ASPI is under the $3 price floor. An admission still needs two in-window reads,
a register thesis and the operator's word.

**B. Ask F4 about both criteria.** The question as frozen names `under_narrated`. On this evidence
`at_inflection` binds harder (§2). The review can answer the frozen question and also note whether
`at_inflection` can pass on names that discovery surfaces on motion. Any change to either criterion is its
own dated amendment and re-segments the record.

**C. A standalone thesis for one of the §21 doors.** Not proposed now. CC's read: estimate-revision breadth
is analyst attention by definition, which works against `under_narrated`; guidance changes on low-coverage
optionable names run into the obscurity null (quiet ∧ feasible ∧ fresh is near-empty). Neither can be stated
with conviction today. It reopens if the operator holds one.

**Not options:** loosening the floor or the strategist to get a fill; a slot cool-down (§4); reviving any
closed feed without a standalone thesis.

## 7. At session 30

Re-run §1–§4 on runs #1437 → the 30th session, add any admissions from option A and their first verdicts,
and hold the review on that read.
