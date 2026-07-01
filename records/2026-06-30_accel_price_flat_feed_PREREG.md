# PRE-REG (FROZEN-CANDIDATE v2 — for sign-off) — the fundamental-acceleration ∧ price-flat curation feed

**Date:** 2026-06-30 · **Status: FROZEN** — §10 decision RULES signed blind by the operator **2026-07-01,
before any probe ran** (§13). Freeze complete; the two distribution-derived checks (accel-floor
fallback-trigger; news degeneracy) are computed POST-freeze by applying the frozen rules (§12) —
mechanical, not new decisions. The GATE-1 diagnostic (§7) follows. All yield knobs BLIND, surfaced in
§10/§13. Scope: the universe-wide divergence feed only (within-sector
ranker + insider/13D family out of scope, §9). The diagnostic driver is ephemeral (outside the repo); the
`qtr_yoy_accel` surfacer + price-flat filter commit as tested infra **only on BUILD**.

Changes from v1: ① accel pin → existing `qtr_yoy_accel` (younger reach + earlier signal); ② coverage
degeneracy condition (quietness verification shifts to GATE 2 if news is degenerate); ③ over-filter →
shoulder-once then route through the main rule; ④ moved-on-thin-news cohort as the measured effect-size
ceiling (three-way composition); ⑥ GATE 2 = throughput-cost ceiling, GATE 3 = value; ⑦ vacuity → a
supply-vs-threshold-vs-quietness decomposition.

---

## §1 — Why this probe (the one door the funnel graveyard left open)

The five idea-supply negatives all tried to mechanize the **quietness/decorrelation** leg — proven
HUMAN-only for *ranking*. `records/2026-06-23_autonomous_corpus_generator_negative.md` (18-19, 84) leaves
ONE door open: fundamental acceleration from filed XBRL is *"the single §2-clean signal that targets
inflection directly."* Two of its three shelving caveats are obsolete (`fundamentals.py` computes
PIT-clean revenue accel; §9 wired the news axis); the third — **cleanest accel skews narrated** — is the
only live question, and this probe decides it.

**The seam (the load-bearing defense).** `discovery.py`'s two enforced leashes (module docstring) are **no
cheapness** (pre-selects the IV gate) and **no coverage** (pre-selects `under_narrated`, the §2 corollary).
This feed respects both: it raises the `under_narrated` **base rate** via `{accel ∧ price-flat}` — accel a
structural XBRL signal, price-flat a motion-lane filter, both seam-clean — and **never ranks on
quietness**. `PREREG_FRESH_INFLECTION_FUNNEL §12` (432-450) records that CGS §8's frontier sketch ("rank
on quietness + cheapness") was *itself* seam-violating; this feed threads that needle — the seam-clean way
to attack the quietness frontier §12 left open. (Grounded: §12; `structural_events.py:82` is form-based,
so revenue-accel is grounding-only, never a surfacer → genuinely **new reach**.)

**Not the FRO/CDE shape — bounded throughput, stated honestly.** There the human supplied the sector
thesis upfront; here the machine surfaces an obscure name and the human builds *both* the quietness read
and the thesis from scratch. The feed *shrinks* the binding constraint (curation throughput), it does not
dissolve it. Consequence: the eyeball tests thesis-ABILITY (§4); the warrant is conversion, not snapshot
population (§7).

## §2 — Hypothesis + the decisive distinction

**H:** there is a populated, judgeable, *novel* cohort in `{material revenue-acceleration ∧
price-not-re-rated ∧ optionable}` mid-caps — filed fundamental moved, stock did not — **denser in
quiet-∧-thesis-able-∧-novel names than each of its drop-one ablations** (§4): both conjuncts earn their
place and together beat the bare characteristic.

**Why not federal_awards' empty cell.** federal_awards self-emptied because the catalyst is
announcement-gated (the award IS the press release → re-rates → empties). Reported acceleration is
**coverage-gated**: filed-but-not-narrated. The price-not-re-rated conjunct makes coverage-gating
operational — it selects the subset where the filed accel has not yet moved the stock. No structural
antagonism forces the cell empty.

**The rationale is mutual de-confounding, NOT "inflection + novelty."** Each conjunct removes a *different*
failure mode of the others (the §4 predictions make this falsifiable): `price-flat ∧ quiet` is confounded
(early vs dead value-trap) → **accel removes the dead**; `accel ∧ quiet` is confounded (early vs
already-moved) → **price-flat removes the moved**, including the *moved-on-thin-news* subset the coverage
label cannot see (coverage and motion are different axes).

## §3 — The pinned design (BLIND; §10 is the red-team surface)

| knob | proposed BLIND value | rationale / anti-HARK |
|---|---|---|
| **frame** | US **common stock** (exclude ETFs/CEFs/SPACs/funds — the obscurity-null funds trap; exclude no-clean-XBRL-revenue), **cap ∈ [$300M, $15B]** as-of, **optionable**. Run the **FULL frame** (not an 800 sample). | the feasible mid-cap zone. companyfacts for novel names are **NOT cached** — size the one-time SEC-rate-limited fetch (~minutes at 10 req/s), tractable not free. |
| **acceleration** (structural XBRL — §2-clean source) | **`qtr_yoy_accel`** = qtr-rev-YoY(latest) − qtr-rev-YoY(2 quarters back) — the **EXISTING tested metric** (`fundamentals.py:504-513`, commented *"earlier than TTM-on-TTM"*), points **filed ≤ as_of**; **robustness floor `ttm_yoy > 0`** (surface only when the TTM trend is also up — kills the single-quarter blip QoQ noise admits); **material floor re-pinned BLIND on the `qtr_yoy_accel` distribution** (do NOT carry the v1 +15pp — it was TTM-Δ-scaled); report distribution + shoulder; **report per-cell revenue-history/age distribution + the count excluded for insufficient history**. | a FEED wants the EARLIER, younger-reaching signal — the eyeball/council filters the added noise (feed-not-edge); the v1 1yr-Δ-of-TTM needed `revenue_yoy` × 2 ≈ **12 quarters (~3yr)** → silently dropped the youngest, most-plausibly-quiet names. `qtr_yoy_accel` needs ~6q; with `ttm_yoy>0` ≈ **8q (~2yr)** — a full year younger, blip-robust, the round-2 QoQ insight, already built. The ~2yr floor is inherent to a second-derivative signal and now **measured** (age dist); a younger inflection metric (sequential-growth-accel) is a future extension iff the age dist shows young-name exclusion bites. |
| **price-not-re-rated** (motion-lane filter on the structural source — NOT a corpus signal) | move neither *behind* nor *underway*: **`momentum_12m ≤ +25%` AND `momentum_recent_3m ≤ +15%`** (reuse existing markers, **no new computation**; symbol-agnostic — verified `compute_markers`/`market.momentum`). **Pure ceiling, NO downside floor** (a name down on accelerating fundamentals is the strongest divergence; the falling-knife is dispositioned by the §4 eyeball, not pre-excluded). **Absolute** return; `rel_strength_12m` SECONDARY; report distributions + a **+40% / +25%** shoulder (the §5 over-filter fallback rung). | the Leg-3 timing discriminator; two windows = the renderer's existing "already happened" vs "happening now" pair (recent spike = strongest too-late signal → tighter ceiling). It cannot ride the salience axis — it is an *anti*-motion filter. |
| **coverage** (DIAGNOSTIC INSTRUMENT — a MEASURED LABEL, never a filter) | trailing **90d news count** (`coverage_by_year`/the §9 proxy; reach RESOLVED — `news.py:74-84` `_ensure` fetches per-symbol on-demand, but a **~N-symbol fetch leg** — size it); **"quiet" = bottom tercile** of the frame's count, used to MEASURE each §4 cell's quiet density. **Never filters the production feed** (`{accel ∧ price-flat}`; quietness judged downstream). **DEGENERACY condition (blind-pinned):** pre-run probe the 90d-count distribution on **~50 random frame names**; if **> X%** sit at count **≤ K**, the tercile is meaningless → **DROP the quiet label from the GATE-1 density read** (read thesis-able-∧-novel only, quietness UNVERIFIED) and **shift quietness verification to GATE 2's council `under_narrated` judgment** (the real arbiter; §7). Do NOT make the eyeball the quiet arbiter — "is this obscure name's story widely-told" is not eyeball-judgeable, and degenerate-low news may be feed-blindness, not quiet. | flipping coverage to a measured outcome keeps it unambiguously an instrument (never gates → §2 corollary honored with zero gray area). The degeneracy switch refuses to fake-precision a saturated signal and relocates — not fakes — the quietness read. |
| **optionability** | the existing §11 Rule-1 feasibility screen (chain, 15–35% OTM band, price ≥ $3, ADV ≥ $3M, fits one ≤ $1k contract). | reuse; the live tradeability bar. |

## §4 — The 2×2 ablation with a committed prediction (the decisive leg)

Production feed = `{accel ∧ price-flat ∧ optionable}`. Ablation = the **drop-one 2×2** over the two
production conjuncts within `{optionable}`, read on **quality-density (quiet-∧-novel-∧-thesis-able RATE,
never count;** under degeneracy, **thesis-able-∧-novel** rate, quietness deferred to GATE 2):

| | **price-flat OUT** | **price-flat IN** |
|---|---|---|
| **accel OUT** | cell 00 = `{optionable}` (base rate) | cell 01 = `{price-flat ∧ optionable}` |
| **accel IN** | cell 10 = `{accel ∧ optionable}` | **cell 11 = the feed** |

**Predicted compositions (pinned BLIND — the falsifiable anti-HARK commitment):**
- **cell 01** value-trap-heavy (accel de-confounds → 11 cleaner than 01).
- **cell 10** moved-heavy; the high-news-moved (SMCI/GEV-type) read NON-quiet so the density already
  catches them — the residual contaminant is the **moved-on-thin-news** subset (re-rated while coverage
  stayed low), which the coverage label can't see and price-flat strips.
- **cell 11** cleanest.

**The decision is the INTERACTION:** does adding price-flat to 10 raise quiet-∧-thesis-able density
(**11 > 10**)? Does adding accel to 01 (**11 > 01**)? Both beat the base (**11 > 00**)?

**Mechanics:**
- **Effect-size ceiling (first-class — operationalizes the min-N concern, §11.1).** Report the
  **moved-on-thin-news cohort** = `{accel ∧ quiet ∧ moved}` = cell-10's quiet members that FAIL price-flat.
  **Its size = price-flat's maximum possible concentration effect.** If < a blind-pinned **K**, the
  11-vs-10 comparison is uninterpretable **by construction** → the read **auto-resolves to "price-flat
  directionally-valid but immaterial → ship accel-only"** (§5), not an underpowered abort. Measure the
  ceiling, don't guess the floor. **Eyeball-tag this cohort itself** — its composition is three-way:
  **mostly-junk** (ran-up-quietly-and-done) → price-flat HELPS; **small** → immaterial → accel-only;
  **mostly good-early-movers** (ran up but the thesis is still live) → **price-flat HURTS** (it strips live
  theses) → reject the price leg as harmful, not merely demote it. The no-downside ceiling makes the
  harmful case a real risk.
- **Blinded eyeball** over all cells **shuffled, label-hidden**; per name a **junk-type tag** {value-trap,
  already-moved, one-off/accounting/M&A, other} + thesis-ability Y/N. Cells over the eyeball budget are
  **random-sampled to a fixed N** (NEVER ranked — ranking by accel re-imports the salience axis).
- **Thesis-ability rubric (pinned BEFORE names):** PASS iff the accel traces to an **identifiable secular
  driver** (product cycle, regulatory shift, supply change), NOT a one-off.
- **Production precision:** report cell-11's **quiet-hit-rate** (its quiet density) = the pre-enrichment
  the feed buys (the throughput value).
- **⊥ cheapness check (§2 completeness — the alignment risk lives in the price filter):** report
  **gate-pass rate of cell 11 vs cell 10**. If price-flat *raises* gate-pass, "hasn't moved" tracks
  "low RV → cheap IV/RV" → IV-gate alignment, a problem. Similar → clean (flat ≠ low-RV; cheapness is a ratio).

## §5 — Decision rule (banded, BLIND; the 2×2 selects WHICH feed, if any)

- **BUILD — `{accel ∧ price-flat}`:** (a) cell 11 ≥ a **blind-pinned minimum novel-pass count** (label-
  hidden, thesis-able, novel); (b) cell-11 eyeball pass-rate highest of the four AND ≥ a pinned floor;
  (c) cell-11 quiet-∧-thesis-able density **> 10 AND > 01 AND > 00** (qualitative side-by-side on
  label-hidden lists; §10 multipliers are *guides*, not gates — cells too small to power a ratio).
- **BUILD — accel-only instead (validates the v1 draft over the price leg):** `11 ≈ 10` density (or the
  moved-on-thin-news cohort < K) but 10 beats 00/01 → ship accel-only, drop the price leg, dated.
- **REVISIT — the lever is the characteristic:** `11 ≈ 00` → "quiet optionable mid-caps" is the finding →
  build the curation triage surface (§9-tooling), not a feed.
- **PRICE-FLAT OVER-FILTERS (plumbing, not a verdict):** cell 11 thin but cell 10 populated → fall back to
  the **PRE-PINNED shoulder** (`momentum_12m ≤ +40%` AND `momentum_recent_3m ≤ +25%`, §3) **ONCE, dated**
  — NOT a free re-tune (re-tuning a blind threshold *because* the cell came back thin is post-hoc HARK).
  Then **re-apply this rule from the top** with the shoulder cell: BUILD if cell 11 now populates clean;
  accel-only iff cell-10 is **high-quality**; **GRAVEYARD if cell-10 is mostly-moved/low-quality** (accel
  cannot escape the skew → accel-only would ship a narrated feed). Do NOT auto-ship accel-only.
- **GRAVEYARD:** cell 11 thin AND cell 10 thin AND nothing concentrates → dated negative; the last
  §2-clean inflection door surfaces only the narrated end or nothing tradeable-and-quiet.

## §6 — Guards (the lines off the divergence corpse + the seam)

- **FEED, NEVER A SCORED EDGE.** `fundamentals.py` IS the divergence-edge module; revenue-YoY as a ranked
  predictor is PROVEN DEAD (k=4 rank-IC −0.057, CI spans 0). The diagnostic **NEVER computes accel's
  forward-return IC**. Forward validation is at the **convexity** level only (GATE 3).
- **The price leg is a MEMBERSHIP FILTER, never a divergence SCORE.** Accel floor + price ceiling are each
  binary in/out. **NEVER compute `(accel − price_move)`, NEVER rank by it, NEVER IC it.** *The moment we
  compute `corr(accel − price_move, fwd_ret)` or rank by a divergence quantity, we've re-run the corpse.*
  Use-specific lesson → binds despite different inputs.
- **NO catch-up claim (the corpse's falsified *premise*).** Price-flat's ONLY job is an anti-salience
  **novelty locator** (un-noticed accel → higher `under_narrated` base rate → more novel candidates). It
  is **never** a bet the price will catch up (IC≈0 across four iterations falsified that). The edge stays
  **entirely** the human thesis + the IV gate.
- **The seam (supersedes any placement argument).** The two enforced discovery leashes are coverage and
  cheapness; this feed touches neither and never ranks on quietness — the seam-clean way to raise the
  `under_narrated` base rate (§1/§12/CGS-§8 lineage).
- **§2-clean.** Acceleration is filed-XBRL revenue, unchanged. Price appears ONLY as an anti-motion filter
  (the permitted motion lane). News-count never filters. IV is the GATE's sole domain (`{price-flat ∧
  IV-rich}` caught downstream by the gate — the sole cheapness arbiter).
- **PIT.** Accel from points filed ≤ as_of. Snapshot current-as-of; any look-back aligns the price window
  to the FILING date (no restatement / no price look-ahead).
- **Anti-HARK.** §10 frozen before the run; the §4 predicted compositions are the falsifiable
  pre-commitment; the §7 plumbing fix-and-reruns are pre-named.

## §7 — Staged probe + the three dated gates (each falsifiable at its own horizon)

1. **GATE 1 — snapshot diagnostic (this pre-reg) → "worth a trial".** Full frame → §4 2×2 + eyeball +
   ⊥cheapness check → §5 read. **No build.** Pre-named fix-and-rerun risks (plumbing, NOT verdicts):
   (i) **companyfacts coverage** < 70% → widen/clean; (ii) **news degeneracy** — reach is resolved, but
   the distribution may be saturated-low over obscure mid-caps; the **degeneracy switch** (§3: pre-run
   50-name probe → if >X% at ≤K, drop the quiet label, shift quietness to GATE 2) is a **conditioning
   pin**, set blind; (iii) **inorganic/base-effect contamination** → an "already-public ≥ N quarters" +
   organic guard surfaced in the eyeball tags. (Market-data-marker reach is **resolved** — symbol-agnostic.)
2. **GATE 2 — conversion trial (iff GATE 1 = BUILD; N weeks) → "worth keeping as a curation input".**
   Commit `qtr_yoy_accel` surfacer + price-flat filter; wire the feed into the curation candidate path (it
   PROPOSES; human + council + §11 dispose). Gated by:
   - a **throughput-COST ceiling** (measurable in N weeks): the feed's **attempts-per-novel-admit** ≤ a
     blind-pinned multiple of the proven lever's **admits-per-attempt** (etf_constituents / motion funnel).
     The feed's value is **reach**, not rate — do NOT compare conversion *rate* across name-difficulty
     (that penalizes reach). Value/novelty-premium is **NOT assessed here** (not observable at this
     horizon — deferred to GATE 3);
   - a **vacuity / supply-vs-threshold-vs-quietness DECOMPOSITION:** admits are ~0 globally (empty book).
     **GATE-1 BUILD = a quiet-∧-thesis-able cohort EXISTS = supply was the binding constraint** (this IS
     the test of "is supply even binding given the empty book?"). **GATE-2 vacuum despite BUILD** is
     ambiguous and routes on the **council's rejection reasons:** rejects *everything* → the residual
     constraint is the **council threshold** (redirect to the threshold); rejects the **feed's names
     specifically on `under_narrated`** → the **feed's quietness premise failed** (operator eyeball
     disagreed with the council — and under news-degeneracy, GATE-2's `under_narrated` IS the quietness
     verification, so this is the quietness-premise-failure signal). Either is an actionable result, not a
     dead trial. Readable only conditional on a non-zero global include rate.
3. **GATE 3 — convexity Brier (6–12mo) → "did the novel admits PAY".** The existing convexity-level
   forward scoring. This carries the **value** that justifies GATE-2's throughput cost: a feed that
   cleared GATE 2 (acceptable cost) but whose admits don't pay → retire. Keep-the-feed needs **both**
   acceptable cost (GATE 2) AND positive value (GATE 3). (calibrate-not-prove: a clean snapshot is not a
   validated feed.)

## §8 — HARK structure / what commits

Nameable population (accelerating, price-flat mid-caps) = acceptable Rule-0 category design. Guards
against category→answer-fitting: the **§4 predicted compositions pinned blind**; the **blinded
junk-tagged eyeball**; the **2×2 interaction-as-decision**; the **effect-size-ceiling auto-resolve**
(no guessed min-N); **novelty-vs-in-universe**; **feed-not-edge** (no IC); **bands pinned-no-retune** (the
over-filter fallback is the pre-pinned shoulder, once, dated — not a re-tune). Decisive either way — even
GRAVEYARD settles the last §2-clean inflection door. The driver is ephemeral; the surfacer + filter commit
**only on BUILD**.

## §9 — Explicitly OUT OF SCOPE

- **The within-sector accel ranker** — no gate (human supplies the decorrelation); forward-proven-only
  (accel-as-predictor is IC-dead). Low-risk enhancement to the etf_constituents lever.
- **Other §2-clean inflection feeds** (insider-cluster Form-4 net-buy, 13D/activist — coverage-
  decorrelated by construction; same feed-not-edge guard). A family; accel is the best-instrumented member.

## §10 — The BLIND values to red-team

1. **frame** cap band [$300M, $15B] + common-stock-only.
2. **accel** = the EXISTING `qtr_yoy_accel` (NOT the v1 1yr-Δ-of-TTM) + the `ttm_yoy>0` robustness floor +
   the **material floor re-pinned BLIND on the `qtr_yoy_accel` distribution** + the per-cell history/age
   distribution reported.
3. **price-flat** `momentum_12m ≤ +25%` AND `momentum_recent_3m ≤ +15%`; pure ceiling (no downside floor);
   absolute, `rel_strength` reported-not-filtered; the +40%/+25% shoulder is the §5 fallback rung. *(Most
   arbitrary numbers here — the distribution-read drives the freeze; watch cell-11 drawdown composition.)*
4. **coverage** "quiet" = bottom tercile of 90d news-count, a measured label — PLUS the **degeneracy
   threshold (X%, ≤K)** and the **shift-to-GATE-2 fallback** (not eyeball-only quiet). The conditioning pin.
5. **the §4 read:** the **minimum novel-pass count** (cell-11 BUILD bar), the **effect-size-ceiling K**
   (moved-on-thin-news cohort floor), the junk-type taxonomy + thesis-ability rubric, the density-
   comparison guides.
6. **GATE 2:** the **throughput-cost ceiling multiple**, the trial length N, the vacuity/decomposition
   condition (non-zero global include rate + the rejection-reason routing).
7. **the ⊥cheapness check** threshold (gate-pass-rate gap between cell 11 and cell 10 that counts as
   "price-flat is tracking cheapness").

## §11 — Self-red-team (the adversary's standing concerns, resolved or live)

1. **The 2×2 interaction (11 vs 10) is the whole delta** — **don't pre-name a min-N blind:** the
   moved-on-thin-news cohort `{accel ∧ quiet ∧ moved}` is directly measurable (§4) and IS price-flat's
   effect-size ceiling; if < K the comparison is uninterpretable by construction and auto-resolves to
   accel-only. Measure the ceiling, not the floor. Falsifiable: if cell-10's eyeball-fails are NOT
   disproportionately ran-up-quietly, price-flat is decoration — and if the cohort is mostly *good*
   early-movers, price-flat is **harmful** (it strips live theses), not just decorative.
2. **Price-flat thresholds are the most arbitrary numbers** — more than the accel floor.
3. **No-downside-floor admits falling knives** — watch cell-11's drawdown composition; a deep-drawdown-
   heavy cell reads junk for a price-leg reason, contaminating the accel read.
4. **The trial DECOMPOSES the binding constraint** (not merely "unreadable on an empty book"): GATE-2
   fires only if GATE-1 = BUILD AND the global include rate is non-zero; vacuum *despite* BUILD routes on
   the council's rejection reasons — threshold-too-strict (rejects all) vs quietness-premise-failed
   (rejects the feed on `under_narrated`). Each is a result, not a dead trial.

## §12 — What still gates the freeze (operator + advisor)

1. Apply this v2 (CC's ①/②/③ + the folded ④/⑥/⑦ + the refinements).
2. **Run the §3 news-distribution probe** (`coverage_by_year` on ~50 random frame names) — its result sets
   the degeneracy threshold (X%, ≤K) and decides whether the quiet label survives or quietness shifts to
   GATE 2.
3. **Re-pin the §10.2 material floor** on the `qtr_yoy_accel` distribution (the v1 +15pp was TTM-Δ-scaled —
   do not carry it).
4. Then freeze §10 + sign-off. Nothing else is open.

---

## §13 — The proposed BLIND pins (CC, awaiting operator sign-off — filled AFTER sign-off, BEFORE the probes)

**Signed on principle, before any yield is seen.** §10's distribution-derived values are computed by
applying these pre-committed RULES to the probe output (never look-then-choose). Status: **SIGNED & FROZEN
— operator sign-off 2026-07-01, before the probes ran.** (The accel material-floor value is already
concrete = +10pp absolute; the probe only checks the fallback trigger and the degeneracy verdict.)

| §10 item | status | proposed pin (blind) | rationale |
|---|---|---|---|
| 1 frame | confirm | US common stock, cap **[$300M, $15B]** as-of, optionable (§11 Rule-1: px ≥ $3, ADV ≥ $3M, chain, 15–35% OTM, ≤ $1k/contract); FULL frame | the feasible mid-cap zone (already in §3) |
| 2 accel metric | confirm | `qtr_yoy_accel` + `ttm_yoy > 0` | existing tested metric; younger reach + earlier signal (§3/§10.2) |
| 2 accel **material-floor RULE** | **PROPOSE** | `qtr_yoy_accel ≥ +0.10` (10pp) absolute; **shoulder +0.05** (5pp); **fallback (once, dated):** if fewer than **20** frame names clear +10pp, re-pin to the **top quintile of positive `qtr_yoy_accel`** | absolute-on-principle ("growth rate accelerating ≥10pp is materially inflecting") avoids the always-populates trap; the pre-committed fallback handles mis-scale without free re-tuning (my flag #2) |
| 3 price-flat | confirm | `momentum_12m ≤ +0.25` AND `momentum_recent_3m ≤ +0.15`; no downside floor; absolute; shoulder **+0.40 / +0.25** | already in §3 |
| 4 **degeneracy RULE** | **PROPOSE** | **degenerate iff > 50%** of the ~50-name probe sample has **90d news-count ≤ 2**; on degeneracy → drop the quiet-label from GATE-1, shift quietness to GATE-2 | a bottom tercile needs spread; >50% clustered at ≤2 headlines/90d ⇒ the tercile boundary is within the noise |
| 5 **min novel-pass count** (cell-11 BUILD bar) | **PROPOSE** | **≥ 6** novel, thesis-able names in cell 11 | the [3,20]-judgeable sense, mid-low; ≥6 novel quiet inflections = worth a trial, < ~4 too thin |
| 5 **effect-size-ceiling K** (moved-on-thin-news cohort floor) | **PROPOSE** | **K = 5** — if the cohort `{accel ∧ quiet ∧ moved}` < 5, price-flat is immaterial → accel-only | below 5 names, price-flat can concentrate at most 5 → the 11-vs-10 read is noise (§4/§11.1) |
| 5 junk taxonomy + thesis rubric + density guides | confirm | as §4 (junk {value-trap, already-moved, one-off/accounting/M&A, other}; thesis = identifiable secular driver; 11 > 10/01/00 qualitative) | already in §4 |
| 6 **throughput-cost multiple** | **PROPOSE** | feed **attempts-per-novel-admit ≤ 3×** the proven lever's (etf_constituents / motion funnel) attempts-per-admit | the reach premium justifies up to ~3× the effort-per-admit; beyond that the throughput cost outweighs the novelty |
| 6 **trial length N** | **PROPOSE** | **N = 8 weeks** | enough council passes to read conversion without stalling the loop |
| 6 vacuity condition | confirm | readable iff ≥ 1 global include in the window; else route on rejection reasons (§7 GATE-2) | already in §7 |
| 7 **⊥cheapness gap** | **PROPOSE** | flag alignment iff cell-11 gate-pass-rate exceeds cell-10's by **> 10 percentage points** | a small gap is noise; a >10pp systematic elevation suggests price-flat is tracking cheap IV/RV |

**Two pre-freeze notes (CC):**
- **§12.2 is a FORK, not just a knob.** A *degenerate* probe result means GATE-1 stops verifying the feed's
  core premise (quietness) and defers it to a paid GATE-2 trial. Read it as a decision — proceed to the
  paid trial premise-unverified, OR add a non-news coverage proxy (analyst count / 13F breadth) at GATE-1
  first — not merely a threshold-setting.
- **§12.3 must be a RULE, not look-then-choose** — the material-floor pin above is a pre-committed rule
  (absolute + fallback), applied to the distribution; the same discipline governs every §10 value derived
  from a probe.

---

## §14 — Post-freeze §10 completion (2026-07-01) — the two distribution-derived checks

The frozen §13 rules (committed `4bebd2d` **before** this probe ran) applied to the pre-freeze probe
(`~/accel_prefreeze_probe.py`, ephemeral, outside the repo; out `~/accel_prefreeze_out.json`). **Mechanical
rule-application, NOT new decisions** — the GATE-1 2×2 / blinded-eyeball read is separate and unrun. The
probe calls the SHIPPED `qtr_yoy_accel` (`fundamentals.corpus_asof`), not a re-implementation (the point of ①).

**Frame (representative sample, not the full frame — the full frame is GATE-1's run):** 837 SEC filers
probed (deterministic stride) → 562 priceable → **236 in-cap-band [$300M,$15B]** → **150 with
`qtr_yoy_accel`**; **86 (36% of in-band) excluded for insufficient history** (the ~2yr / ≥6-quarter
requirement — the young-name exclusion §3/§10.2 flagged; material — see the note). *Caveat: the sample is
the tradable-in-band common-stock superset; OPTIONABILITY (chain existence) is applied downstream at GATE-1
(it only removes names, so it does not affect the floor or degeneracy checks).*

**(P1) accel material-floor — fallback does NOT trigger; the floor stands at +10pp.** `qtr_yoy_accel`
distribution (n=150): p10 −0.163 · p25 −0.078 · **p50 +0.007** · p75 +0.081 · p90 +0.293 (min −2.38, max
+2.80). **Clear +10pp: 32; + `ttm_yoy>0` robustness: 25** (16.7% of the with-accel sample). 25 ≥ 20 on the
sample alone; frame-wide (thousands of in-band names) the clearers ≫ 20 → **the top-quintile fallback does
NOT fire → the frozen material floor is `qtr_yoy_accel ≥ +0.10 ∧ ttm_yoy > 0`.** (Note: +10pp lands ≈ the
empirical top-quintile boundary here — the absolute floor and the fallback would select nearly the same
names, so the floor is not mis-scaled; the two blind rules happen to agree on this data.)

**(P2) news degeneracy — does NOT fire; the quiet-label SURVIVES at GATE-1.** 90d news-count (n=50): min 0
· **median 9** · max 56; **≤2 headlines: 9/50 = 18%** (well under the 50% degeneracy threshold). → **NOT
degenerate → the bottom-tercile quiet-label is meaningful; quietness is VERIFIED at GATE-1 (does NOT shift
to GATE-2).** The §12.2 fork resolves to the normal path — GATE-1 tests the feed's quietness premise directly.

**⇒ §10 is now fully concrete; the pre-reg is FROZEN and COMPLETE.** The next step is the **GATE-1
diagnostic** (§7): the full-frame 2×2 (`accel × price-flat`) + the blinded junk-tagged eyeball + the
effect-size-ceiling + the ⊥cheapness check → the §5 BUILD/accel-only/REVISIT/GRAVEYARD read. A separate run.

**One GATE-1-relevant flag (NOT a re-pin — the metric is frozen):** the **36% young-name exclusion is
material.** The frozen `qtr_yoy_accel` reaches ~64% of in-band names; ~1/3 are too young / annual-only for a
≥6-quarter second-derivative. If GATE-1's cell-11 comes back thin, the pre-reg's already-named future
extension (a younger sequential-growth-accel metric, §3) is the indicated fix — the age distribution now
*evidences* that the exclusion bites (it was a hypothetical at freeze).
