# PREREG_THEMATIC_CONVEXITY.md — Thematic Cheap-Convexity Inflection Trading

> **Pre-registration.** This document is the operating contract for the thematic
> cheap-convexity strategy. It is frozen **before any signal/gate code is written**
> (T0). The risk frame, the eligibility gate, and the IV / cheap-convexity gate — with
> their thresholds — are fixed here. Code reads these parameters from `config.json`; the
> *structure* of the gates is fixed by this doc.
>
> **This is NOT a backtest pass/fail gate.** A 6–12-month hold cannot reach statistical
> significance in tolerable time, and the LLM council can never be backtested (guardrail
> §6). So the discipline shifts: we **pre-register the risk frame and the gates, then
> calibrate forward** — we do not "prove" an edge. The protection is bounded premium, hard
> deterministic vetoes, and a kill rule — not a backtest. See
> `dramatic-options-validation-methodology` (memory) §"How to apply".
>
> **Status: T0 — frozen. T1 (minimal paper loop) implements against this contract.**

---

## 1. Strategy (frozen definition)

> **Amendment 2026-06-01 — thesis framing clarified (no rule change to this sleeve).** The
> operator clarified the intent: buy the **mispriced far extreme** of an option (long-dated, far
> strike) whose price is wrong **if an anticipated trend changes**, and the long tenor is
> **runway** for that thesis, not a 6–12-month holding *commitment*. The natural reading is "exit
> when the mispricing corrects." For the **far-OTM sleeve this resolves to: keep holding the
> tail.** A calibration head-to-head (`PREREG_CONVEXITY_CALIBRATION` §4 amendment) tested a
> delta-trigger "exit-when-the-move-played-out" rule against hold-the-tail and graded it
> **EV-inferior on OTM**: it caps the convex tail you paid for (p99 ~14× → ~1.8× at δ=0.5) and
> raises the break-even hit-rate from **19% → ~50–68%** — and the GBM-no-jumps bias *favored* the
> early exit, yet it still lost. So the OTM book's edge **is** the fat tail; §6a exits below are
> **unchanged** (this is the hold-the-tail venture sleeve). The **reprice-capture** behavior the
> operator wants is a genuinely *different edge* (high-delta, no tail to forfeit) and is **deferred
> to a separately-pre-registered ITM sleeve** — its own financing/extrinsic gate (a skew test would
> mis-fire on ITM by put-call parity), its own reprice + invalidation exits — to be built once
> forward evidence warrants it (not on the GBM harness alone). See the v2 `IMPLEMENTATION_PLAN`.

1. Identify a secular theme at **inflection** — a real tailwind the market hasn't narrated
   yet, or a real headwind/rollover before consensus turns.
2. Express it with **long-dated (6–12 month), far-OTM, defined-risk** options (calls for
   tailwinds, put/bear structures for rollovers). Long options are inherently
   defined-risk: max loss = premium paid.
3. **The edge is the gate:** trade only when the option's implied vol is **NOT already
   pricing the theme** — the convexity is *cheap* ("copper-not-rockets"). A beloved,
   richly-priced theme is a pass however right the narrative.
4. Run a **portfolio of small convex bets**: most expire worthless, a few pay many-fold
   (venture-style payoff).
5. Discipline lives in **sizing and risk control**, not validation.

## 2. The hard seam — deterministic gates dispose; judgment only proposes

Code-enforced, non-overridable (Layer 1): the **IV / cheap-convexity gate** (§4),
**eligibility** (§3), **sizing / caps / book budget** (§5), the **kill rule** (§6).
Judgment (the council, T2+; hand-seeded in T1): *which* theme is at inflection, structural
vs. fad, the cleanest name, narrative ahead-of vs. behind fundamentals. Judgment is *input*
to a proposal that must still pass every deterministic gate. The council can be wrong; it
**cannot** buy expensive convexity, breach a cap, or defeat the kill rule.

## 3. Eligibility gate (frozen) — is the contract tradable for us?

Reuses `options_tradability.py`. A candidate contract must satisfy all of:
- Relative bid/ask spread `(ask−bid)/mid ≤ 0.25`.
- Open interest `≥ 50`.
- Per-contract price within `[0.10, 100.0]`.
- Underlying passes the `universe.py` filter (min price, min avg dollar volume,
  no leveraged ETFs).
**Fail-closed:** missing quote/OI/price → ineligible → no trade.

## 4. IV / cheap-convexity gate (frozen) — the edge, as a hard veto

**The problem (flagged at pre-registration):** "cheap" normally means low IV-rank /
IV-percentile versus the name's *own IV history*. **We have no historical options IV** —
chains are forward-only (see `dramatic-options-edge-toolkit` memory, "harness can't"
walls). So IV-rank is not computable today. We resolve this two ways:

**(a) Substitute the underlying's realized-vol history as the baseline.** Realized vol IS
computable — from the daily bars cache we already hold (point-in-time, no options history
needed). The variance-risk-premium framing answers "is vol expensive?" without an IV time
series.

**(b) Read the convexity price directly off the live snapshot** via the skew shape — the
specific wing we are buying.

The gate, computed from **one current chain snapshot + trailing realized vol**:

| Metric | Definition | Frozen threshold | Meaning |
|---|---|---|---|
| **IV/RV ratio** | `IV_atm / RV_h`, where `RV_h` = annualized realized vol over the trailing window (`rv_window_days`, matched toward tenor) | `≤ τ_ivrv = 1.2` | ATM vol isn't richly bid over what the name actually realizes |
| **OTM skew premium** | `IV(target wing strike) − IV_atm`, in vol points | `≤ τ_skew = 10.0` | the *wing we are buying* isn't already bid up, even if ATM looks calm |

**Pass ⇔ both hold.** Either rich → **veto** (defined-risk default; the council cannot
override).

**Fail-closed:** missing IV, ATM reference, wing IV, or insufficient bars for `RV_h`
→ treat as **NOT cheap** → veto. A gate that cannot be evaluated does not pass.

**Thresholds are frozen for the current forward cohort.** They live in
`config.json:convexity_gate` and are changed **only** by an explicit, documented operator
edit — **never** moved to justify a specific trade (no post-hoc gate moving).

**Accrue our own IV baseline going forward.** The point-in-time cache (`data/cache.py`,
immutable entries) is the mechanism: persisting each cycle's chain snapshot into it builds a
real IV history over months, after which the gate can **graduate** from the RV proxy to a
true IV-rank / IV-percentile. (T1 establishes the loop and the cache; wiring the per-cycle
snapshot write is the immediate next step. The graduation itself is a future,
separately-pre-registered change.)

Frozen values (T0): `τ_ivrv = 1.2`, `τ_skew = 10.0` vol pts, `rv_window_days = 252`,
tenor window `[180, 365]` days, `target_moneyness = 0.25` (≈25% OTM).

<!-- #276 option-1 conformance amendment -->
**Conformance amendment (2026-09-29, approved by Rodrigo via Marcus; PR #277).** The structure selector now
reads `config.json:convexity_gate.otm_side_guard = true`: it admits only strictly out-of-the-money contracts
for the thesis direction and fails closed with no structure when no eligible OTM contract exists. This is the
minimal option-1 side guard, not the separately-scoped 15–35% admission band (option 2). Enabling the switch
changes `frame_version` and therefore starts a new recorded segment. The six pre-existing wrong-side null-book
positions are retained and tagged outside-frame; tail reports show both with and without those positions.
Confirmed directly by the operator in session on 2026-09-30 ("Go ahead"). Follow-up PR: tests for the tagging, and the dashboard performance panel lists the tagged positions (`outside_frame`).

<!-- #416 minimum-moneyness amendment -->
**Minimum-moneyness amendment (2026-11-04, operator word: "Adopt both the 15% floor and A+B+C at the 11-12
boundary"; #416).** The selector also reads `config.json:convexity_gate.min_otm_moneyness = 0.15`: it admits only
contracts at least **15% out of the money** (achieved, on the thesis side: `(strike − spot)/spot` for a call,
`(spot − strike)/spot` for a put) and fails closed with no structure (`no_eligible_contract_beyond_min_moneyness`)
when none is eligible. It runs after the side guard; the target stays `target_moneyness = 0.25` and the choice
among admitted contracts stays nearest-to-target.
- **Why:** on L1 #1918 (2026-11-03) the first ranked-backfill entry, TITN, had its ~28%-OTM wing refused by
  eligibility, and the nearest-eligible fallback bought C25 at **7% OTM** (17.8% of spot), a different payoff shape
  from the far-OTM frame. Its cheapness verdict passed only because the strike moved (C30 iv/rv 1.086 on 11-02, C25
  0.96). It was the only entry below 15% on any book since the side guard (2026-09-30). This is option 2 of #276
  in its floor-only form; no 35% ceiling (nothing has entered above 35%).
- **Scope:** every book and gate path that already reads the side guard: real (`paper_loop`), shadow, 3A and 3B
  (`fixed_basket`), shares, the gate dual-read record and the cheapness watch, so the nulls stay comparable. Out of
  scope: the survivor cards (their admission band already requires an achieved 15–35%) and the weekly sweeps
  (PREREG_MISS_BASERATE and the basket gate base-rate; their frozen definitions change only by their own dated note).
- **Boundary:** `frame-f86f37a0bd4f` → `frame-880e893e1660` from the first L1 after deploy. Positions already open
  are retained in their own frame segment (none on the real book is below 15%; the null books' 8 near-money
  positions are untouched, and the six #276 wrong-side positions keep their outside-frame tag).
- **Consequence for the slate, stated:** the gate-of-record reads apply the floor too. On L1 #1935 (11-04), 5–7 of
  38 structured names' gate-of-record wings were below 15% OTM, all of them cheap (FIG, KLAR, LHX, NOC, NTSK; LUNR
  and VRT on the day's closes). Each either re-selects a farther eligible strike or becomes unexpressible, which
  demotes it in the council slate and removes it from the cheap reserve. The two weekly sweeps keep their frozen
  definitions until their own dated notes (#427).
- **Unchanged:** `target_moneyness`, the tenor window, eligibility thresholds, the IV gate, sizing, the caps, the
  carry-over and the backfill rules.


**Data-provenance amendment (2026-06-08) — `equity_bars` IEX→SIP (the data-feed upgrade, PR1).** The
gate's `RV_h` is computed from daily closes; PR1 moves those closes from the free **IEX** feed (~2–3% of
consolidated volume; its last print ≠ the official close) to the paid **SIP** consolidated feed (Algo
Trader Plus, confirmed live on the paper key). This is a **gate-INPUT change**, not a non-event: `IV_atm/RV`
shifts, so a candidate near `τ_ivrv = 1.2` can flip — the SIP close is the *more-correct* input, so such a
flip is the **expected effect, not a regression**. The same `equity_bars` switch also feeds the **discovery
prescreen markers** (`data/market.py`), so the surfaced candidate funnel can shift too (the volume/ADV
markers were most undercounted on IEX). The **option** feeds are unchanged in PR1: `option_gate` stays
**INDICATIVE** (L1 entry authorization) and `option_monitor` stays free — `option_gate` flips
INDICATIVE→**OPRA** in a later, separately-noted amendment (PR3) once the PR2 dual-read confirms
across-session agreement. Stamped per-run via `runs.data_feed` (migration 0013). The frozen thresholds
(`τ_ivrv`, `τ_skew`, …) are **UNCHANGED** — this changes the *data source*, not the gate.

> **SUPERSESSION NOTE (2026-06-10, dated — the original sentence above is left visible per the
> never-rewrite-frozen-text rule):** the "once the PR2 dual-read confirms across-session agreement"
> precondition is RELAXED by `PREREG_DATA_FEED_OPRA_SEQUENCING.md` (frozen 2026-06-10): the
> `option_gate` flips INDICATIVE→OPRA NOW, with the dual-read running CONCURRENT
> (measure-while-live, pinned tripwires + a fail-closed revert path) instead of gating. This is a
> named relaxation of a documented evidence standard — the beneficiary is the re-architecture
> timeline (the HARK gradient, named) — defended on the principle that the frozen cheapness
> arbiter must read the REAL chain, which survives the legitimacy test at zero extra trades
> (yield is zero-and-validated: CGS §10.8). The frozen thresholds remain UNCHANGED.

## 5. Risk frame (frozen) — FIRST-CLASS; the discipline

Operator decisions, set 2026-05-31, in `config.json:convexity_book`:

- **Convexity book = 10% of account** — the total premium-at-risk. The **only** money the
  strategy can lose; the other 90% is untouched.
- **Per-name cap ≤ 1% of account.** Per-theme cap = per-name for T1 (one name per theme).
- **Max concurrent positions = 15.**
- **Sizing = flat-by-slots, capped — NOT Kelly.** A far-OTM lotto Kelly-sizes to ~0 (low
  win probability); that is the wrong instrument here. Each shot gets a small, roughly
  equal slice of the book, capped at the per-name limit and never exceeding the book
  remaining. Aggression comes from convex *structure* and the *number* of small shots —
  never from size on an unproven view. No naked, no uncapped, no leverage-on-conviction.
- **Survivorship log.** Record **every** evaluated bet — eligible or vetoed, winner or
  zero — append-only. This is the only honest basis for ever judging edge vs. luck, and it
  counters the bias toward remembering the winners.

**Amendment 2026-06-03 — per-theme/cluster exposure cap (operator-authorized, §C-instance-cited).**
The per-name 1% cap treats every underlying as independent, so a basket of *correlated* names reads as
"diversified" when it is one bet. The first live discovery scan (2026-06-03) made this concrete: 7 of 8
surfaced sentinels were a single AI-capex-into-power bet (VRT/PWR/GEV/ETN datacenter power + CCJ uranium
+ RKLB/KTOS space-defense) spanning **two** scan baskets — at 1%/name they would have loaded **7% of the
10% book** into one trade the log would record as "7 diversified positions." This adds a **cluster-level
entry-premium cap**:

- **Cluster cap.** Aggregate **entry** premium-at-risk across a *correlation cluster* ≤
  `cluster_fraction` × account equity (`config.json:convexity_book.cluster_fraction = 0.02` = **2 full
  names** = 20% of book). It composes with the existing caps:
  `alloc = min(per_name_cap, book_remaining, cluster_remaining)`. Graduate to 0.03 only once **≥4
  clusters** are curated (two clusters at 0.03 = 60% of book in two correlated bets) — itself a dated
  re-amendment.
- **Cluster = an operator-curated, DETERMINISTIC `symbol → cluster` partition** (a name in **≤1**
  cluster), documented **by driver** so future names route correctly. It is **never** keyed on a
  theme/basket *label* (a sentinel's label can be set by the LLM framer; letting that move a risk cap
  would breach the §2 hard seam). Shipped: `ai_capex_power` (AI-datacenter power demand) =
  VRT/PWR/GEV/ETN/CCJ/CEG/NEE (CEG/NEE folded in, CCJ kept, **FCX dropped** — copper variance is
  diluted; a power/uranium ETF like URA would co-cluster); `space_defense` (defense/space budgets) =
  RKLB/KTOS/LMT/NOC/LHX/RTX (**extended 2026-06-04** — the trailing-return correlation diagnostic
  `cluster_diagnostic.py` surfaced the defense primes LMT/NOC/LHX/RTX as a 0.50–0.68 SHARED-driver cluster
  the scan basket already held but the cluster didn't; RKLB the loosest member = future-split-on-evidence,
  the FCX pattern). The diagnostic is the ongoing **report-not-gate curation backstop** (it never edits the
  map — hard seam). Overlap / `cluster_fraction < per_name_fraction` / a malformed map **fail closed** (raise
  at load); an **absent** map is inert (every name a singleton) — an optional additive control must not
  fail-closed-to-zero-trades on absence.
- **Direction-agnostic, no netting.** The cap sums premium-at-risk regardless of direction (defined
  risk: you can lose all of it); it does **not** net long/short — a netting model would need clean beta
  the free feed can't give. Clusters are curated to be directionally coherent; a mixed-direction cluster
  logs a non-fatal warning.
- **Committed basis (incl. pending).** The cluster cap counts `status IN (open, closing, pending)` —
  unlike the book cap's open/closing basis — so a same-cycle just-submitted (`DRY_RUN=false` resting
  limit, reconciled only in the monitor pass) mate is counted and a tight cluster cannot over-admit on
  its next mate the same cycle. The ~10-slot book absorbs that window; a 2-slot cluster cannot.
- **Gates new entries, never force-closes** a pre-cap over-budget cluster (mirrors §6). Applies
  **identically to the brain-off shadow book** (a deterministic cap; only the council selection differs).
  **Breach = an entry admitted in violation of the THEN-LIVE frame**, not "book currently within caps":
  each run stamps its frame version (`runs.frame_version`, migration 0009) and each cluster decision
  stamps the per-decision occupancy/cap/equity into the survivorship log, so the T4 breach audit
  recomputes within-cap-ness at the admission rather than trusting the enforcement code.

This only **tightens** the frame (the lowest-risk §5 edit) and makes no edge claim — pure concentration
risk-control. Converged over the operator's R2/R3/R4 plan red-team. *(Operator-authorized 2026-06-03.)*

**Amendment 2026-11-03 — ranked backfill for an idle book (operator word 2026-11-03, "follow your suggested
steps"; draft D1 in `records/2026-11-03_profit_program_DRAFTS.md`).** *Written before the code.* The book
held 1 of 15 slots for months; three above-floor verdicts since July. With a skewed payoff the number of
independent shots sets the odds of a large winner (Bessembinder 2018), and the council's value over
brain-off is not yet measured (the null hierarchy's "council (real − shadow)" step has no matured data).
This adds one labelled entry path that fills idle slots from the council's own ranking, inside the
unchanged gates:

- **Inert until switched on.** Active only when `convexity_book.backfill` exists with `enabled: true`.
  An absent block is off, so merging the code changes nothing. The dated config edit that adds the block
  is the single `frame_version` boundary (the hash covers `convexity_book`).
- **Trigger (deterministic, from state):** committed slots now (open + closing + pending + carried) ≤
  `max_open_positions − empty_slots_min` (10 ⇒ ≤ 5 committed), **and** the most committed slots on any
  day of the trailing `lookback_days` (28) was also ≤ that.
- **Quota:** at most `per_week` (1) backfill entry per trailing 7 days, counting every backfill order that
  holds or held exposure or a working order. A carry attempt of an approved backfill is the same entry,
  never a second one.
- **Pool:** this L1's council proposals that did **not** clear the floor and tri-criteria, with
  `structural_vs_fad = structural` and conviction ≥ LOW (NEUTRAL = abstain or parse failure, never
  eligible). Direction coherence has already been applied upstream.
- **Rank (deterministic):** number of the three criteria the strategist asserted true (desc), then
  conviction (desc), then the latest fresh gate-of-record IV/RV (asc; a name without a fresh cheap read
  ranks after every name with one), then symbol. The top `candidates` (3) go to the gates **after** every
  above-floor name; the first to clear every gate is the week's entry.
- **Everything else is unchanged:** §3 eligibility, the §4 gate, side guard, dual-read veto, cluster and
  per-name caps, flat-by-slots sizing, the book cap, the §6 kill rule, the restricted list and the
  foreign-quantity check. Conviction still never sizes.
- **Labelled and scored apart:** the position's rationale carries `origin = backfill`, the proposal's
  rationale carries `backfill.rank`, and the dashboard's `real_by_origin` reports `backfill` as its own
  origin.
- **Stop rule (pre-stated):** backfill suspends itself (logged and paged once per run) when ≥ 8 backfill
  entries are ≥ 90 days old **and** their running premium-bled fraction exceeds the comparator's by more
  than 25 percentage points. The comparator is above-floor entries aged ≥ 90 days if there are ≥ 3 of
  them, else the brain-off shadow book's entries aged ≥ 90 days. A suspension is lifted only by a dated
  operator edit.

This **widens** entries (more shots), so it is a riskier §5 edit than the cluster cap; the protection is
that every frozen gate and cap still disposes, the path is capped at one per week, and it has a pre-stated
stop. No edge claim.

**Amendment 2026-11-03b — wide debit call verticals for over-cap names (operator word 2026-11-03; draft D3;
calibration v2 Rule V: CANDIDATE, `records/2026-11-03_calibration_v2_finding.md`).** *Written before the
order-path code.* Nine names (NVDA, LHX, LMT, CEG, NOC, ETN, VRT, PWR, GEV on the 11-01 read) cannot take one
naked contract under the $1,000 per-name cap, so the book can never express them. Rule V found a long
≈25%-OTM / short ≈+75%-OTM call vertical keeps ≈0.98× the naked mean multiple at ≈0.71× the premium, at the
cost of the tail (p99 ≈10.7× → ≈7×).

- **Inert until switched on:** active only when `convexity_gate.vertical_for_over_cap` exists with
  `enabled: true`. An absent block is off. The dated enabling edit is the `frame_version` boundary (the hash
  covers `convexity_gate`).
- **When:** a **bullish** theme whose gate-of-record naked contract passed eligibility, the side guard and
  the frozen §4 gate, but whose **one-contract premium exceeds the per-name cap**. No other veto falls back
  to a vertical: book, cluster, slots and gate vetoes stand as written. Bearish theses are out of scope
  (put verticals were not calibrated).
- **Structure:** long = the gate-of-record wing, unchanged. Short = the call at the same expiry and OCC class
  nearest +75% OTM (`short_moneyness`, default 0.75), eligible under §3, strictly above the long strike, and
  no nearer than +50% (`min_short_moneyness`): a narrower spread is a different payoff object. Net debit =
  long mid − short mid, > 0 and < the width; else no structure (fail-closed). The short leg is not
  cheapness-gated (selling a rich wing only lowers the debit).
- **Sizing and caps:** the **net debit** is the premium-at-risk (the defined max loss). Per-name, cluster
  and book caps and flat-by-slots sizing apply to it unchanged.
- **Orders:** one atomic multi-leg limit order (buy-to-open long, sell-to-open short, 1:1), never legged. The
  L1 limit is the mid debit; a carry walks it toward the natural debit (long ask − short bid) as #386 walks a
  single leg. The shared-account guards (reserved roots, restricted list) apply to **both** legs; the
  foreign-quantity check reads **both** contracts; the live per-order notional ceiling and the reserve check
  apply to the net debit. A venue that refuses multi-leg orders (options approval level) is a rejected
  order, fail-closed and paged.
- **Exits (§6a, on the spread's value):** the mark is long mid − short mid. Profit-take at 10× the net debit,
  time-stop at 21 DTE, expiry at intrinsic(long) − intrinsic(short). A close is one atomic multi-leg order
  at the mid credit. When the long leg's bid is under `min_close_bid`, the close books in-DB at mark, as for
  a single leg.
- **Null books stay paired:** the shadow book and 3A apply the same over-cap rule, so the council and gate
  contrasts still differ in one variable. 3B already skips names it cannot size; it gets the same rule.
- **Recorded:** the row carries the short leg's symbol and strike (`short_contract_symbol`, `short_strike`;
  migration 0021). `structure_kind` stays `C`, so a vertical is the row with a short leg.

> **Dated note 2026-11-03c (independent review of the order-path diff, before any merge; the bullet above is left
> as written):** a close priced at the **mid** credit can rest unfilled day after day on wide far-OTM quotes and
> reach expiry, where an in-the-money long is exercised or the short assigned (outside the defined-risk frame). The
> close is therefore priced at the **natural credit** (long bid − short ask), the two-leg equivalent of a single
> leg selling at the bid; the mid is used only when the natural credit is not positive, and a spread with no
> positive credit is booked at mark like an unsellable single leg. A refused multi-leg open or close pages (a
> close at most once per position per day), and a broker without a multi-leg path leaves the spread open, never
> booked closed. The short leg is chosen as stated: among eligible calls ≥ +50% OTM, the one nearest +75%.

> **Reading note (2026-11-12, operator word: "Kill rule: clock A (from 2026-07-01), payoff P1, drawdown option 1 (cumulative), R2, null books keep booking. Land before 12-25."; #472).** "Convexity book = 10% of account — the total premium-at-risk" means **10% committed at any moment (R2)**: a closed position frees its premium budget, which is what sizing already does (`book_remaining = book_budget − committed premium`). The lifetime loss before review is bounded by the §6 drawdown leg (cumulative since 2026-07-01, see §6's conformance notes): roughly 1.2 books at most, absent a gap between L2 ticks or an in-flight entry. No frozen number changes.

## 6. Kill rule (frozen)

Halt **new entries** for human review if **either**:
- the book draws down **≥ 20%** of its premium budget, **or**
- the book **bleeds 9 months** with zero payoff.

Plus the always-on `KILL` file / env switch, checked every cycle (fail-closed). Open
positions are not force-closed by the kill rule; it stops *new* risk pending review.
Thresholds in `config.json:kill_rule`.

**Posture-review trigger (dated amendment 2026-07-02, operator-authorized; pinned BLIND — 0
positions resolved anywhere at pin time).** The two clauses above both presuppose premium at
risk ("draws down", "bleeds") — on a book with **zero entries ever**, neither clock starts, so
the waiting posture itself had no pre-registered falsifier (found 2026-07-01,
`records/2026-07-01_shadow_null_arm_saturation_DIAGNOSIS.md` §7). Amendment:

- **The entries-side clock anchors at forward-loop go-live (2026-06-02)**, not at first entry.
- **Interim checkpoint — 2026-11-02** (the opening of the first structural resolution window
  for the June-2026 null vintage): a scheduled posture LOOK (dashboard/record note, no
  automatic action) — placed so a censored-but-healthy-looking state cannot accumulate unseen
  for the full window (the 2026-06/07 lesson).
- **Review trigger — D = 2027-03-02** (9 months from go-live, symmetric with the frozen
  9-month bleed constant): if the real book has had **zero entries ever** by D, a mandatory
  operator **posture review** triggers — hold-with-re-dated-trigger, open the
  criteria-reconsideration branch (IMPLEMENTATION_PLAN §T4 fork 3), or stand down.
- **Review-not-kill:** the trigger is a decision point, NOT an automatic halt and NOT evidence
  the edge is absent (§7 discipline unchanged). **Reachability pinned honestly:** any
  "0 resolved null positions" reading is vacuously true before ~Nov–Dec 2026; before then the
  zero-entries leg alone carries the trigger.

> **Ownership addendum (2026-07-02, after the merge — provenance made explicit).** The merge of
> the amendment above was executed on the operator's transmitted directive, but the line-item
> values were not each explicitly operator-pinned at merge time: **D = 2027-03-02** was proposed
> by CC (2026-07-01) and endorsed by the advisor; the **interim checkpoint 2026-11-02** was
> proposed by the advisor with the choice explicitly left to the operator ("your pin either
> way") and was included by CC's judgment, flagged in-session but not operator-worded.
> Merge-as-ratification is a named failure mode in this project, distinct from explicit
> operator ownership. **RATIFIED 2026-07-02 by the operator's explicit instruction** — the
> operator was presented all three values with keep-or-strike offered on the checkpoint, and
> answered "go ahead with whatever you feel is correct, so let's merge": explicit,
> informed authorization with the keep/strike choice DELEGATED to CC, which retained the
> **2026-11-02 interim checkpoint** per its standing recommendation. Ownership of
> **D = 2027-03-02**, the checkpoint, and the go-live clock anchor is the operator's,
> exercised in that delegated form on that date.

> <!-- #465 / #472 kill-rule conformance notes -->
> **Conformance notes (2026-11-12, operator word: "Kill rule: clock A (from 2026-07-01), payoff P1, drawdown option 1 (cumulative), R2, null books keep booking. Land before 12-25."; #465, #472; drafts `records/2026-11-10_kill_rule_dry_leg_conformance_DRAFT.md` in PR #476).**
> Both legs above were frozen here and in `config.json:kill_rule` (`book_drawdown_halt: 0.20`, `dry_months_halt: 9`). Only the drawdown leg was in code, and it measured the open book only. From the merge commit of the implementing PR (before 2026-12-25 as worded; CC recommends the 2026-12-07 boundary weekend), they are computed as follows.
> - **Dry leg ("bleeds 9 months with zero payoff"):** the clock starts at the first real fill's `opened_at` (2026-07-01, PL) and restarts at the `closed_at` of each real-book close with `realized_pnl > 0` (payoff P1, under any exit reason). Backfill positions count; cancelled or never-filled orders do not; null books never feed it; "months" are calendar months on the US-Eastern date. (These four sub-rules are the draft's §3 reading of clock A and P1, recorded as CC's reading. The operator worded the letters.) On today's book it binds on **2027-04-01** unless a real position closes above cost first.
> - **Drawdown leg ("draws down ≥ 20% of its premium budget"):** the book's net loss since the first real fill, i.e. realized P&L of real-book closes (partial closes included) plus unrealized P&L of open and closing positions at their marks, divided by the premium budget (`account_equity × book_fraction`, $10,000). A closed loss no longer leaves the figure. Until the first real close (none yet; PL's time-stop is first possible on 2026-12-28) the two readings never differed, so no past admission or halt would have been decided differently.
> - **Effect of a trip (either leg):** it halts NEW real-book entries and the council, exactly as before, and **the null books keep booking** (the brain-off controls keep running while the real book is halted). The manual `KILL` switch still halts everything. The L0 scan's behaviour on a trip is unchanged by this note: it is an open question whether L0 keeps scanning so the null books do not run out of sentinels.
> - **Release:** a trip clears through a payoff close or a mark recovery. A dated operator re-anchor is not built; it needs its own word.
> - **Unchanged:** the 20% and 9-month thresholds, §5's numbers, flat-by-slots sizing, §6a exits, "open positions are not force-closed", the posture review (D = 2027-03-02), and `frame_version` (the hashed `kill_rule` block already contained both legs; the implementing PR changes code only).

## 6a. Exit rules (frozen) — the L2 reflex, deterministic, no LLM

Open positions are marked to the current option mid each cycle and exited by **deterministic,
code-enforced** rules (`monitor.py`; SPEC §3 "open slow, close fast"). The intelligence is
front-loaded at entry; this loop only watches and fires. Rules (`config.json:convexity_exits`):

- **Profit-take:** close when the mark reaches **≥ 10× the entry premium** (a convex winner is
  realized rather than round-tripped).
- **Time-stop:** close when **≤ 21 calendar days to expiry** (avoid the gamma/theta endgame).
- **Expiry:** close at intrinsic; a far-OTM option that never came in → **−premium**, the
  expected zero (the venture payoff shape).

Realized P&L is recorded per close (the calibration substrate, §7). These thresholds are
frozen for the current cohort; changed only by a documented operator edit, never to rescue a
specific position. *(Added 2026-05-31, before live forward results exist.)*

**Amendment 2026-06-01 — profit-take raised 4× → 10× (operator-authorized, calibration-cited).**
The payoff-mechanics calibration (`PREREG_CONVEXITY_CALIBRATION.md`) showed the **4× cap clips
the convex right tail that is the entire point of the book**: at the live cell (25% OTM, 270d,
σ_entry = 1.2× realized) the capped p99 was ~4.5× vs ~10× uncapped, while the **mean barely
moved** (≈0.86–0.88× across drift scenarios — tail events are rare, so capping them costs almost
nothing on average but forfeits the many-fold winners the strategy is sized for). Above ~12× the
profit-take rarely fires (the 21-DTE time-stop takes over) and metrics converge. **10× sits just
before that plateau** — it still imposes profit discipline (realize a spectacular winner before
it round-trips, and before a far-OTM option that has gone ~10× has become a spent-convexity delta
bet) while recovering most of the tail. The protective **time-stop stays 21 DTE** (the
calibration showed it cuts P(total loss) ~72%→56% vs hold, by salvaging theta on losers).
*Caveat acknowledged:* GBM has no jumps, so the real catalyst-driven tail is fatter than modeled
— which only strengthens the case against an eager cap. This is a calibration of **structure**,
not an edge claim (the §1 walls hold). `config.json:convexity_exits.profit_take_multiple = 10.0`.

## 7. Forward measurement — calibration, not a pass-gate

Per bet, logged: theme, inflection thesis, IV-gate verdict + metrics, structure, size,
rationale, outcome, P&L. Tracked: hit rate, payoff distribution, premium-bled-vs-paid
(Brier + council contribution arrive with the council, T2+). **6–12-month holds mean
*years* to significance.** Forward data informs calibration, sizing, and the kill
decision — it does **not** prove an edge. A good run is not validation; a bad run is not
disproof until the kill rule actually trips.

## 8. Scope of this contract

T0 freezes §§1–7. **T1** implements the minimal paper loop against this contract
(hand-seeded themes → both gates → defined-risk structure → flat-by-slots sizing → logged
paper position + survivorship log). The council (T2) is built; **sentinels (T3) are in build —
PR1 (the deterministic discovery core) has landed.** T3 adds a discovery layer **upstream** of the
council and **changes no frozen gate**: it only widens the *candidate set*, and every discovered
candidate still faces the unchanged §3 eligibility + §4 IV gate + §5 sizing/caps + §6 kill. Its
prescreen thresholds are a candidate **funnel** (like eligibility), config-tunable, NOT
pre-registered frozen gates; **prescreen rank is a funnel, never a tradeable signal** (the reused
divergence plumbing is not a revived edge). *(The per-theme/cluster exposure cap foreseen here LANDED
2026-06-03 as the §5 amendment above — the `ai_compute`-style cluster made the per-name cap false
diversification on the very first live scan.)* Any change to a frozen
threshold or gate structure is a documented edit to this doc + `config.json`, dated, never retroactive.

---

*Frozen 2026-05-31, before signal/gate code (T0). — Dramatic Options*
