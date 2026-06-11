# PREREG — the §9 evidence-grounding corpus (fundamental/numeric evidence for council judgment)

**Status: FROZEN by the merge of this PR (2026-06-11).** Converged over a three-round red-team
(2026-06-10/11). Cites only the committed record: `PREREG_COUNCIL_GATE_SEPARATION` §9 (the
evidence-grounding leg, named 2026-06-09) + §10.8 (the demonstrated binding constraint:
marker-only grounding cannot support the §10.7 tri-criteria — 0/16 SCARCITY, abstentions citing
the inability to assert under-narrated/at-inflection from price markers alone) + the Step-0
fill audit `records/2026-06-11_fundamentals_fill_audit.txt` (committed ahead of this text,
cite-before-record). The companion data layer (inert substrate the audit required — nothing in
the live loop reads it until the build PR) ships in this same PR; the judgment-layer
integration is the SEPARATE build PR, sequenced per §7.

## 1. Motivation and the legitimacy test

The council's §10.7 mandate (correctly) demands evidence for three hard assertions —
structural, under-narrated, at-a-genuine-inflection — and the pack carries only price/vol
markers, which cannot support them (§10.8's dominant abstention reason; live corroboration:
run #130's HBM rejection literally asks for fundamental data, UUUU cites "no fundamental
catalyst"). CGS §9 names the same defect from the hand-seed side: thin-news names drop
"ungrounded, no numeric evidence" (FCX, every run) — penalizing exactly the under-narrated
names the thesis targets. This corpus adds EVIDENCE, never permission: every §10.7 floor,
criterion, gate, and cap binds identically. It passes the zero-extra-trades legitimacy test —
a council that can finally *see* fundamentals and still abstains is working correctly. This is
the most throughput-increasing change available (it feeds the include-criteria directly), hence
this maximal-leash document.

## 2. The corpus — pinned inputs, pinned rendering (the input-layer prohibition)

**Enforced by what the builder can SEE (auditable at the call signature), not by prompt.**

(a) **Filed XBRL numbers** — five concepts, each an ORDERED fallback tag list (single tags
under-fill; the audit validated the lists):

| line | concept tags (ordered) | shape |
|---|---|---|
| `revenue ttm_yoy` | RevenueFromContractWithCustomerExcludingAssessedTax → …IncludingAssessedTax → Revenues → SalesRevenueNet | quarterly-income |
| `revenue qtr_yoy` + `qtr_yoy_accel` | same | quarterly-income |
| `gross_margin delta_pts` | revenue winner × (CostOfRevenue → CostOfGoodsAndServicesSold → CostOfGoodsSold) — the consistent pair | quarterly-income |
| `capex qtr_yoy` | PaymentsToAcquirePropertyPlantAndEquipment → PaymentsToAcquireProductiveAssets | ytd-cashflow |
| `rpo yoy` | RevenueRemainingPerformanceObligation | instant |

- **Three extraction shapes** (XBRL mechanics; each fixture-tested in
  `tests/test_fundamentals_corpus.py`): quarterly-income durations with
  **Q4-derivation-or-explicit-omission** (Q4 = FY − Q1..Q3 inside the same fiscal window, filed
  = max of inputs — PIT-correct; never a non-consecutive sum, guarded); **YTD-differencing**
  for cash-flow concepts (10-Q cash-flow facts are fiscal-YTD); **instant** for RPO (end-only
  balances; YoY = two instants 350–380d apart).
- **Year-ago matching, all YoY concepts:** period-end proximity ±45d around one year back —
  the OPERATIVE rule, because the `fy`/`fp` fields on companyfacts units describe the FILING,
  not the fact's period (the known XBRL gotcha), so fiscal-label matching is not reliably
  implementable from this payload. A 53-week/fiscal-shift mismatch fails closed (no match → no
  line).
- **PIT:** ALL (period, filed) variants kept; the read picks **max-filed ≤ as_of per period**
  (an amendment filed after as_of never erases the original from an earlier read — the
  pre-existing latest-filed-wins hole is fixed and tested). **Same-day boundary pinned:** filed
  dates compare at `T20:00:00Z` → a same-day filing is NOT visible to the 19:45 UTC L1;
  backtest and live cannot disagree.
- **Stable tag per name** (most deduped visible periods wins, never first-with-data per
  period — no mid-history tag-migration splices); the margin pair is tag-consistent.
- **Denominator floors** (TTM revenue $10M / quarterly revenue $2.5M / quarterly capex $1M /
  RPO $10M; sub-floor or sign-flipped base → the line is OMITTED — no "+4,300%" anchors), and
  every line renders the **underlying $M values alongside the percent**.
- **Every line carries BOTH `period_end` and `filed`** — staleness is self-describing.
- **Sparse-tolerant:** an unfiled concept is omitted, never fabricated, never zero.
- **IFRS/foreign filers are OUT OF SCOPE v1, visibly:** the audit shows 7/33 names render zero
  lines (CCJ, ERO, HBM, NNE, NXE, TGB, UROY — the Canadian cohort; concentrated in
  nuclear_fuel/copper_supply). Their packs honestly carry no FUNDAMENTALS lines. An
  `ifrs-full` extractor is a future dated amendment, not a quiet addition.

(b) **Filing events** — already in the markers (`has_event`/`event_kind`); unchanged here.

(c) **News coverage counts** — the only deterministic under-narrated input: **TWO raw counts,
trailing 7d and trailing 90d** of Alpaca `headlines_asof` items (level + recency; a raw 90d
count alone is mostly a market-cap proxy — the pair lets the model see attention and its
change; we compute NO verdict ratio — input, never an engineered feature). PIT parity to the
fundamentals standard: counts reconstruct from published-timestamp ≤ as_of (verified against
the news layer in the build, not assumed). Pinned caveat rendered IN the block: free-feed
coverage is sparse; low counts are weak supporting evidence. (The trailing-baseline
narration-change ratio = named v2; the theme-generation stub's narration probe = the future
stronger sensor.)

**Prohibited inputs:** prices/returns beyond the existing markers; IV/options data (the gate's
domain); analyst ratings/targets; sentiment scores; full-text news for sentinels.

**Pinned rendering (the evidence surface — an unpinned reorder is an unstamped corpus
change):** a `FUNDAMENTALS:` section after the headlines block; one line per metric, format
`- {concept} {metric} {value:+.1%} ({latest}M vs {base}M; period {period_end}, filed {filed})`
(gross margin in points; accel unitless); then `NEWS_COVERAGE: 7d={n7} 90d={n90} (free feed —
sparse; low counts are weak evidence)`. **Concept labels stay NEUTRAL** — never the criterion a
line was chosen to support (a label like "structural spend" is a leading question; the §10.7
role prompts own the mapping). Section order within the pack is part of this pin.

## 3. Origin policy — and the ONE behavior change, named

- **Sentinels:** markers (unchanged) + FUNDAMENTALS + coverage counts. The `grounded`
  definition is UNCHANGED (markers ⇔ grounded) — fundamentals enrich, never gate.
- **Hand-seeds:** news (unchanged) + FUNDAMENTALS. **`grounded` gains an OR-leg:
  fundamentals-present grounds a thin-news hand-seed** — the §9 FCX fix; hand-seeds stop
  $0-early-exiting and get deliberated (cost +~$0.03–0.06/cycle, inside the $5 cap).
  **"Fundamentals-present" is pinned: ≥1 revenue-family line OR ≥2 lines total.**
- **The hand-seed roster is pinned at this freeze: FCX, NVDA; max 2 seeds per cycle.** The
  OR-leg makes seeding cheap → hand-seeding becomes the one discretionary opening into the
  judgment layer and silently moves the §5 band denominator. Roster changes are dated operator
  edits in `themes.json` recorded like §11 register amendments — never quiet additions.
- `--demo`/`synthetic_context_pack`: untouched.

## 4. Freshness (and why it serves the thesis, not just hygiene)

`FundamentalsData.max_raw_age_days` (council path: 7; default None = the historical
never-refetch behavior — shelved callers byte-compatible) **plus refetch-on-filing-event**: a
fresh `has_event` marker forces a refetch regardless of age — the moment right after a filing
is exactly when inflection evidence matters most. The refetch validates before committing
(parse + a `facts` key; a 200-OK SEC error page must not pass) and writes temp-then-rename;
online-but-SEC-errors falls back to the stale disk raw (a stale line with visible dates beats
an empty section). All fixture-tested.

## 5. Validation — one pass, bands BEFORE numbers (the §10.4 pattern)

**(a) The gated re-score.** After the build PR is reviewed: ONE ephemeral re-score on the SAME
pinned 16 (`scripts/probe_rescore_thesis_only.py` extended to pass the corpus), §10.7 prompts
sha-matched, live router, tee committed to `records/`. **Band: 0–2 of 16 survivors** (the
criteria stay hard; the corpus lets assertions be MADE, not makes them true; NVDA stays
under-narrated-false). Actions: 0–2 → ship per §7; **>2 → exactly ONE identical repeat (both
tee'd + committed; the noise rule, pinned now — the router runs at nonzero temperature), and
the STOP stands if either run exceeds 2** — then investigate; no corpus iteration after seeing
the number (one corpus change per re-score). **Scope honesty:** n=16 with a 0–2 band is a
smoke test of plumbing + selectivity under the frozen mandate — it validates neither corpus
quality nor edge, and a pass must never be cited as if it did.

**(b) The fill diagnostic rides the re-score:** the tee records per-name rendered-line counts —
a 0-survivor result with median lines < 2 is a CORPUS failure (plumbing), not selectivity, and
fix-and-rerun is allowed for that case only (stated now so it isn't latitude later).

**(c) The OR-leg band (the named behavior change ships on a band, not vibes):** in the first
post-ship L1, **FCX (the thin-news seed) reaches full deliberation via the OR-leg** (vs the $0
ungrounded-drop baseline); **NVDA is expected to deliberate via the news leg regardless and is
NOT an OR-leg test** (the band tests the leg once, honestly). Over the first 5 post-ship L1s:
hand-seed includes ≤ 1 (≤10 deliberations at the pinned roster). Outside either bound → flag +
investigate before any further change.

**(d) Live fill telemetry:** per-pack line count + ok/partial/empty status ride the proposal
rationale; `council_l1_health` surfaces the per-run median (a SEC outage under fail-soft must
not masquerade as hard criteria — and an OR-leg band miss is uninterpretable without it).

## 5b. Outcome attribution (what already owns the profit question + the one added read)

The includes-make-money question is OWNED by the existing pre-registered instruments:
`PREREG_FIXED_BASKET_NULL`'s **council = real − shadow** (one variable: selection), the
never-traded reference sweep ({180,270,365}, terminal-event guard, controls cohort, tail not
mean), and Brier/agent-contribution. This pre-reg ADDS one read on that same machinery: the
**proposal-level contrast — include=true vs DELIBERATED-but-rejected vs controls** (the
judgment control finer than the book read; caps/affordability never touch it), same horizons,
same statistics, compute-when-mature. **Citation threshold pinned: not citable in EITHER
direction below 10 includes.** **The blindness window is a named cost:** ~180d+ of
corpus-influenced selections accrue before the first judgment-quality read matures
(Brier/agent-contribution resolve on the same horizon clock — there is no earlier-maturing
interim instrument); the interim record is throughput bands only, accepted because the right
statistic beats the fast one. A separate short-horizon (20d/60d) outcome ledger was considered
and DECLINED: horizon-mismatched to the ~250d hold, mean-vs-tail-mismatched to a convex book,
and a duplicate instrument is itself a HARK channel (post-hoc choice of which to cite).

## 6. HARK leash

Never loosened by this work: the discovery floors, the framer, the §10.7 prompts/criteria/
enforcement, the conviction floor, the IV gate, every cap, the kill rule. The corpus adds
evidence lines to packs and nothing else. If the §5 bands miss, the response is investigate —
never widen.

## 7. Sequencing + record segmentation

The judgment-layer integration (the build PR) merges only AFTER PR-B's first thesis-only L1
observation (Fri 2026-06-12 19:45 UTC) — the prompt change and the corpus change must be
separately attributable; earliest merge Fri evening, normal path Mon 2026-06-15 pre-L1. The
pack change stamps `"corpus": "fundamentals_v1"` into the runtime `runs.model_mix` JSON (the
prompt-sha pattern applied to the pack; zero migration). The dual-read soak, PR-B flow, and
Sun L0 run independently.

## 8. Out of scope (named so they don't vanish)

The narration probe (stub Stage-2) and theme generation; ANY funnel/surfacing change (judgment
INPUTS only — floors/TTL/slots untouched); IFRS extractors (dated future amendment, §2); the
coverage narration-change ratio (v2); IV-baseline graduation; the L2 monitor.
