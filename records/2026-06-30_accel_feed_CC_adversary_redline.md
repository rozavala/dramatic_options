# CC ADVERSARY REDLINE (DELTA-ONLY — for the advisor's final review) — against the accel∧price-flat frozen-candidate

**Date:** 2026-06-30 · **Status:** adversary pass on the FROZEN-CANDIDATE (pre-freeze). Touches **§3, §4,
§5, §7, §10, §11 only**; everything else is conceded and unchanged. Two of the six are **freeze-blockers**
(① changes a pinned knob, ② adds a conditioning pin); the rest fold in. Grounded in the repo (citations
inline). Red-team **just these deltas**.

## The six deltas at a glance

| # | section | change | severity | grounded |
|---|---|---|---|---|
| ① | §3 accel row, §10.2 | swap pinned accel `TTM-YoY−TTM-YoY(−1yr)` → existing **`qtr_yoy_accel`** + `ttm_yoy>0` floor; report age dist | **freeze-blocker** (band-changer) | ✓ `fundamentals.py:504-513`, `:80-83` |
| ② | §3 coverage row, §7(ii), §10.4 | quiet-label **degeneracy fallback** + reach resolved + fetch-cost sized | **freeze-blocker** (conditioning pin) | ✓ `news.py:74-84` |
| ③ | §5 over-filter branch | "re-tune the ceiling" → **fall back to the pre-pinned shoulder once** (close the HARK hole) | freeze-blocker | logic |
| ④ | §4 mechanics, §11.1 | report the **moved-on-thin-news cohort** = price-flat's measurable effect-size ceiling (replaces guessing min-N) | folds in | — |
| ⑤ | — | moved-on-thin-news de-confounder **already in the doc** (§2/§4) — conceded, no edit | — | — |
| ⑥ | §7 GATE 2, §10.6 | novelty qualifier → **throughput opportunity-cost** (you over-corrected by dropping comparison) | folds in | — |
| ⑦ | §7 GATE 2, §11.4 | vacuity guard → **supply-vs-threshold decomposition** (elevate) | folds in | — |

---

## ① §3 acceleration row + §10.2 — the pinned accel regresses from existing code AND your own QoQ argument

**Grounding:** `data/fundamentals.py:80-83` — `revenue_yoy` returns `None` under **8 quarters**; the pinned
`TTM-YoY(as_of) − TTM-YoY(as_of−365d)` is two such readings a year apart ≈ **12 quarters (~3yr)**, which
silently excludes recently-public names (a chunk of the novelty target). `data/fundamentals.py:504-513`
already ships **`qtr_yoy_accel`** (qtr-YoY now − qtr-YoY two quarters back), code-commented *"earlier than
TTM-on-TTM"* — your round-2 QoQ argument, already built and tested.

**OLD (§3 acceleration row)**
> | **acceleration** (structural XBRL signal — §2-clean source) | `accel = TTM-rev-YoY(as_of) − TTM-rev-YoY(as_of − 365d)`, points **filed ≤ as_of** (reuse `revenue_yoy`); require **current TTM-YoY > 0**; **material floor ≥ +15pp**, report full distribution + a **+8pp shoulder**. | the second-derivative/inflection; revenue not earnings…; the floor defines the cell… Stays pure XBRL… |

**NEW**
> | **acceleration** (structural XBRL signal — §2-clean source) | **`qtr_yoy_accel`** = qtr-rev-YoY(latest) − qtr-rev-YoY(2 quarters back) — the **EXISTING tested metric** (`fundamentals.py:504-513`, commented *"earlier than TTM-on-TTM"*), points **filed ≤ as_of**; **robustness floor `ttm_yoy > 0`** (surface only when the trailing-twelve-month trend is also up — kills the single-quarter blip); **material floor re-pinned BLIND on the `qtr_yoy_accel` distribution** (the +15pp was TTM-Δ-scaled — do not carry it over), report distribution + shoulder; **report the per-cell revenue-history/age distribution + the count excluded for insufficient history**. | a FEED wants the EARLIER, younger-reaching signal — the eyeball/council filters the added single-quarter noise (feed-not-edge), and the 1yr-Δ-of-TTM needed ~3yr history → silently dropped the youngest, most-plausibly-quiet names. `qtr_yoy_accel` needs ~6 quarters; with the `ttm_yoy>0` floor ≈8 quarters (~2yr) — a full year younger, blip-robust, IS the round-2 QoQ insight, already built. The young-name exclusion is now **measured** (age dist), not silent. |

**OLD (§10.2)** → `accel definition (one-year two-point Δ of TTM-YoY) + the +15pp material floor (+8pp shoulder).`
**NEW (§10.2)** → `accel = the EXISTING qtr_yoy_accel (NOT the 1yr-Δ-of-TTM) + the ttm_yoy>0 robustness floor + the material floor re-pinned BLIND on the qtr_yoy_accel distribution + the per-cell history/age distribution reported.`

---

## ② §3 coverage row + §7(ii) + §10.4 — the quiet-flip loads the BUILD metric onto a possibly-degenerate signal

**Grounding:** `data/news.py:74-84` — `NewsData._ensure(symbol)` fetches **per-symbol on-demand**
(Alpaca/Benzinga), so reach for arbitrary frame tickers is **resolved (favorably)**. But under the flip
(adopted — coverage as a measured label, not a filter, is correct), **quiet-density IS the BUILD metric**,
and Alpaca/Benzinga coverage of obscure $300M mid-caps is plausibly **degenerate** (mostly near-zero 90d
counts → the bottom-tercile boundary is meaningless → quiet-density can't discriminate the 2×2 cells).

**OLD (§3 coverage row, rationale cell tail)**
> …(c) keeps news-count unambiguously an instrument — it never gates, so the §2 corollary is honored with zero gray area. |

**NEW (append to the rationale cell)**
> …(c) keeps news-count unambiguously an instrument. **BUT the flip makes quiet-density the BUILD metric, so its informativeness is a freeze-condition:** (i) reach is resolved — per-symbol on-demand fetch — but it is a **~N-symbol fetch leg** (size it alongside companyfacts; not free); (ii) **pre-run probe** the 90d-count distribution on ~50 random frame names; (iii) **degeneracy fallback (blind-pinned):** if > **X%** of the frame sits at 90d-count ≤ **K**, **DROP the news quiet-label** and make the blinded eyeball the **SOLE** quiet arbiter — never fake-precision a degenerate tercile. |

**OLD (§7 GATE 1 risk ii)**
> (ii) the **news-count source must fetch for arbitrary frame tickers** (not just in-pipeline names) — the one open plumbing unknown, gates the quiet-label measurement, verify before freeze;

**NEW (§7 GATE 1 risk ii)**
> (ii) **news-count REACH is RESOLVED** (`news.py:74-84` `_ensure` fetches per-symbol on-demand) — but it is a **~N-symbol fetch leg** (size it) and the **distribution may be DEGENERATE** over obscure mid-caps; the **degeneracy fallback** (pre-run 50-name probe → if >X% at ≤K, eyeball-only quiet) is a **conditioning pin**, set blind before the run;

**OLD (§10.4)** → `coverage "quiet" = bottom tercile of 90d news-count, used as a measured label not a filter.`
**NEW (§10.4)** → `coverage "quiet" = bottom tercile of 90d news-count, a measured label — PLUS the degeneracy threshold (X%, ≤K) and the eyeball-only fallback (the conditioning pin).`

---

## ③ §5 PRICE-FLAT OVER-FILTERS branch — close the HARK escape hatch

Re-tuning a blind-pinned threshold *because* the cell came back thin is the post-hoc tuning the freeze
exists to block (you could loosen until cell 11 populates). The pre-pinned **shoulder** (§3) is the
sanctioned second rung.

**OLD (§5)**
> - **PRICE-FLAT OVER-FILTERS (plumbing, not a verdict):** cell 11 thin but cell 10 populated → the price ceiling is too tight → re-tune the ceiling and rerun (pre-named, §7) — NOT graveyard.

**NEW (§5)**
> - **PRICE-FLAT OVER-FILTERS (plumbing, not a verdict):** cell 11 thin but cell 10 populated → fall back to the **PRE-PINNED shoulder** (`momentum_12m ≤ +40%` AND `momentum_recent_3m ≤ +25%`, §3) **ONCE, dated** — NOT a free re-tune (re-tuning a blind-pinned threshold because the cell came back thin is post-hoc HARK). If the shoulder also over-filters → a **price-leg negative** (→ ship accel-only), not another loosening.

---

## ④ §4 mechanics + §11.1 — measure the effect-size ceiling instead of guessing a min-N

Price-flat's entire lift is stripping the **moved-on-thin-news** cohort from cell-10's quiet subset. That
cohort is itself a cell — directly measurable — and its size IS price-flat's maximum concentration effect.
This dissolves the abort-then-rescue trap (§11.1): you don't pin a min-N a priori, you read the ceiling.

**NEW — add a §4 "Mechanics" bullet**
> - **Effect-size ceiling (first-class report — operationalizes the §11.1 min-N concern).** Report the **moved-on-thin-news cohort** = `{accel ∧ quiet ∧ moved}` = cell-10's quiet members that FAIL price-flat. **Its size = price-flat's maximum possible concentration effect.** If it is < a blind-pinned **K**, price-flat can move at most K names out of cell-10's quiet subset → the 11-vs-10 density comparison is uninterpretable **by construction**, and the read **auto-resolves** to "price-flat directionally-valid but immaterial → ship accel-only" (§5) — NOT an underpowered abort. Measure the ceiling, don't guess the floor.

**OLD (§11.1, tail)**
> …The cells are small; pre-name the **minimum judgeable N per cell** or the comparison is decorative (the abort-then-rescue trap in a new costume)…

**NEW (§11.1, tail)**
> …The cells are small — but **don't pre-name a min-N blind**: the **moved-on-thin-news cohort** `{accel ∧ quiet ∧ moved}` is directly measurable (§4) and IS price-flat's effect-size ceiling; if it is < K the comparison is uninterpretable by construction and the read auto-resolves to accel-only. Measure the ceiling, not the floor. The de-confounding story stays falsifiable: if cell-10's eyeball-fails are NOT disproportionately ran-up-quietly, price-flat is decoration.

---

## ⑥ §7 GATE 2 + §10.6 — you killed the wrong comparison (rate), then dropped comparison entirely

Conceded: conversion-rate-vs-etf_constituents compares across name-difficulty and penalizes the feed for
surfacing the harder/novel names that are its point — kill it. But the binding constraint is **throughput**,
and the feed **consumes** it (each surfaced obscure name costs a human thesis-attempt). A novel admit at a
ruinous effort-per-admit is throughput-**negative** despite clearing an absolute novelty floor. So keep a
comparison — make it opportunity-cost, not rate.

**OLD (§7 GATE 2, novelty bullet)**
> - a **novelty qualifier** (the admits must be *novel* — unreachable by etf_constituents or the motion funnel); the feed's value is **reach**, not rate, so do NOT require it to beat etf_constituents' conversion *rate*…;

**NEW (§7 GATE 2, replace that bullet)**
> - a **throughput opportunity-cost qualifier:** the binding constraint is throughput, which the feed consumes — so the test is **"are the feed's NOVEL admits (unreachable by etf_constituents / the motion funnel) worth the throughput diverted from the proven lever?"** Novelty is necessary (the feed's value is reach, not rate — do NOT compare conversion *rate* across name-difficulty, that penalizes reach) but **not sufficient**: a novel admit at a ruinous effort-per-admit is throughput-negative. Novelty-adjusted **opportunity cost**, never absolute novelty, never rate;

**OLD (§10.6)** → `GATE 2: the conversion floor, the trial length N, the novelty qualifier, the vacuity condition…`
**NEW (§10.6)** → `GATE 2: the conversion floor, N, the throughput-OPPORTUNITY-COST qualifier (novel admits worth the diverted throughput — not absolute novelty, not rate), the vacuity/decomposition condition (non-zero global include rate).`

---

## ⑦ §7 GATE 2 vacuity + §11.4 — elevate the vacuity guard to a supply-vs-threshold DECOMPOSITION

The vacuity guard is bigger than "the trial might be unreadable" — the gate sequence *diagnoses* whether the
binding constraint is supply or the council threshold, and pre-answers "is supply even binding given the
empty book?"

**OLD (§7 GATE 2, vacuity bullet)**
> - a **vacuity guard**: admits are ~0 globally (empty book). If the council includes *nothing from any source*… The trial is readable **only conditional on a non-zero global include rate**; otherwise it correctly redirects to the council threshold.

**NEW (§7 GATE 2, vacuity bullet)**
> - a **vacuity guard, as a DECOMPOSITION:** **GATE-1 BUILD** = a quiet-∧-thesis-able cohort EXISTS = **supply was the binding constraint** (this IS the test of "is supply even binding given the empty book?"). **GATE-2 vacuity** (empty book despite BUILD) = the cohort exists but the council still won't include it = the residual constraint is the **council threshold/judgment, not supply** — an actionable redirect to the council, not a dead trial. Readable only conditional on a non-zero global include rate.

**OLD (§11.4)**
> 4. **The conversion trial is unreadable on an empty book** — GATE 2 only fires if GATE 1 = BUILD *and* the global include rate is non-zero; if the book stays empty, the honest conclusion is "the constraint is the council threshold, not supply," and this feed is not the lever.

**NEW (§11.4)**
> 4. **The gate sequence DECOMPOSES supply-vs-threshold** (not merely "unreadable on an empty book"): GATE-2 fires only if GATE-1 = BUILD AND the global include rate is non-zero; an empty book *despite* BUILD is itself the actionable finding — "the binding constraint is the council threshold, not supply" — which redirects to the council, a result, not a dead trial.

---

## Conceded & unchanged (scope discipline)

- **⑤ moved-on-thin-news de-confounder** — already in the candidate (§2 + §4 cell-10 prediction); conceded,
  no edit. ④ operationalizes its test.
- The **quiet-as-measured-outcome flip** (adopted, ②), the **2×2-with-prediction** (§4), the **corpse guards**
  (§6), the **seam/§12 lineage** (§1/§6), the **three dated gates** (§7), the **out-of-scope fence** (§9) —
  all unchanged.

## What still gates the freeze (operator + advisor)

1. Apply ①/②/③ (the freeze-blockers); fold ④/⑥/⑦.
2. **Run the ② pre-freeze news-distribution probe** (~50 names) — its result sets the degeneracy fallback
   threshold and confirms whether the quiet-label survives.
3. Re-pin the §10.2 material floor on the `qtr_yoy_accel` distribution (the +15pp was TTM-Δ-scaled).
4. Then freeze §10 + sign-off.
