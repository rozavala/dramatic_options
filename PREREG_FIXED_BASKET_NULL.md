# PREREG_FIXED_BASKET_NULL.md — The No-Gate / Fixed-Basket Null Hierarchy

> **Pre-registration, written BEFORE any harness code.** This document fixes *what the nulls
> measure, on what data, and — critically — what they are NOT allowed to claim.* It is the
> disciplined companion to `PREREG_THEMATIC_CONVEXITY.md` (the frozen live strategy) and
> `PREREG_CONVEXITY_CALIBRATION.md` (payoff mechanics). **Frozen 2026-06-03, before any forward
> result exists.**
>
> **This is NOT a backtest and produces NO edge claim.** It is a **forward** null hierarchy — the
> forward analog of the FSSD null≈signal control (`PREREG_FSSD.md`), applied to the part of the
> strategy that *is* the claimed edge: the IV / cheap-convexity **gate**. Like the calibration, it is
> a **measurement tool**, read as calibration, **never a pass-gate and never an auto-trade trigger**
> (guardrail §6: validated forward, never backtested).

---

## 1. Why — the hole in the current null hierarchy

The forward record already runs two books: the **real** book (gate-ON + council selection) and the
brain-off **shadow** book (`shadow_positions`, PR3b: gate-ON, no council). Their gap isolates the
**council** (the LLM layer). But **both keep the IV gate** — so **nothing tests the gate**, and the
gate *is* the claimed edge ("trade only when convexity is *cheap*"). This is exactly the structure
that honestly killed FSSD: the null control (random in-name dates) ≈ the signal, so conditioning on
the event added nothing over the base characteristic. The analog here: if a book that trades the
**same names with the gate OFF** earns the same realized-multiple tail as the gate-ON book, then
"cheapness" is **not** an edge — it is a characteristic the gate is not adding value over.

This doc pre-registers the books, universes, metric, and read **blind**, so a later "the gate works"
or "the gate is empty" conclusion cannot be a post-hoc choice (the HARKing failure mode that this
project is scarred by — divergence, FSSD).

## 2. The null hierarchy (forward, simulated-only, never-broker, tail-scored)

| Book | Gate | Selection | Universe | Caps | Isolates |
|---|---|---|---|---|---|
| **Real** (`convexity_positions`) | ON | council | union | cap-ON | the strategy |
| **Shadow** (`shadow_positions`, PR3b) | ON | none | union | cap-ON | the **LLM layer** |
| **3A — gate-off union** (new, headline) | **OFF** | none | union | cap-ON | the **IV GATE** |
| **3B — fixed basket** (new) | **OFF** | none | **whole basket** | equal-weight | the **apparatus** (bundled) |
| **Shares basket** (new, secondary) | n/a | none | whole basket | equal-weight | **convexity vs linear** |

All non-real books are **simulated fills only and NEVER reach the broker** (their own table, no broker
import, a merge-blocker test — the PR3b invariant), and run **fail-soft** (a null bug logs/pages but
never halts the real trade cycle).

**The inferential chain — name the CLEAN contrasts vs the BUNDLED one.** The decomposable spine is two
**clean one-variable steps**:
- **council = real − shadow** (both gate-ON, union, cap-ON — only selection differs);
- **gate = shadow − 3A** (both no-selection, union, cap-ON — only the gate differs). **This is the
  doc's strongest claim and the reason the whole exercise exists.**

**3B is bundled, not an isolation.** 3B differs from 3A in **both** universe (union → whole basket)
**and** caps (cap-ON → equal-weight), so `real − 3B` is the **end-to-end** read
{discovery-narrowing + gate + council + caps} — useful as "is the machine worth running vs. naively
buying convexity on the whole basket," but **not** attributable to any single part. A positive
`real − 3B` could merely mean *the surfaced/curated union beats the whole basket*, independent of the
gate or the council. It is pre-registered as the **bundled headline**; the two clean steps above are
the attribution.

**Gate-marginal caveat.** All books keep the **eligibility** filter (spread / OI / price); 3A skips
**only** the IV gate. To the extent eligibility correlates with what the gate rejects (rich-IV names
that are also wide-spread / thin), eligibility already pre-screens some of it — so **`shadow − 3A` is a
conservative LOWER BOUND on the gate's standalone value.** Read "shadow ≈ 3A" as "the gate adds little
**over and above eligibility**," **not** "cheapness is worthless in isolation."

## 3. Universes

- **Union** (3A) = `shadow_book.candidate_union` (hand-seed ∪ active sentinels) — the **same** names
  the gate and the shadow book operated on this cycle.
- **Basket** (3B, shares) = flatten `config.universe.themes` (the curated thematic baskets that
  `orchestrator._scan_universe` / the weekly L0 scan already read), **eligibility-filtered**. A ⊂ B is
  conceptual (sentinels are drawn from the basket; hand-seeds may sit outside it).

**The basket is LIVE, not frozen.** `config.universe.themes` is the operator-edited curated list. A
frozen snapshot would go stale vs. the universe the real book actually trades; so the basket stays
**live**, and we pre-register that **3B-absolute is curation-contaminated** (it inherits whatever
curation drift the sibling *basket-quality report* exists to surface) while **`real − 3B` is the clean
read** — both books see the **same** evolving basket each period, so the *relative* comparison survives
drift. (Alternative considered and rejected as less representative: freeze membership as-of this
pre-reg date for a literally-fixed 3B-absolute.)

## 4. Cap inheritance (per-universe — deliberate)

- **3A inherits the full frozen frame, cap-ON** (per-name / book / cluster / slots — `PREREG §5` incl.
  the 2026-06-03 cluster amendment). This keeps it a **clean one-variable step from the shadow book**
  (same union, same caps, gate on-vs-off). The union is small (≤ ~12) and fits the caps.
- **3B equal-weights the WHOLE eligible basket at per-name size, with NO book/cluster truncation.** A
  cap-ON 3B would book only the ~10 names that fit a 10% book — which is **not** "the basket"; and the
  apparatus's caps *are* part of the apparatus, which is precisely **why `real − 3B` is bundled** (§2).
- **Shares** equal-weights the basket linearly (one unit per eligible name).

The per-position-multiple metric (§5) neutralizes the resulting book-size difference, so the tail
comparison stays valid across books of very different N.

**§4 amendment — sentinel-slot relief for the null books (dated 2026-07-02, operator-authorized;
pinned BLIND — 0 positions resolved in ANY book at pin time).**

*What happened:* both cap-ON arms (shadow + 3A) saturated their `sentinel_max_slots=6`
reservations at run 130 (2026-06-10) and booked nothing for three weeks — **CENSORED, not
dead**: the bookers ran healthily every cycle, applied the frozen frame correctly, and vetoed
on slots by design; the monitors marked correctly throughout. The defect was *invisibility*
(fixed, PR #137), not function. **The first-6 cohort (booked 06-03→06-10) is a VALID sample of
week-one gate-passers — its rows are not suspect** and stay in every read as the first vintage.
Full diagnosis (hypotheses pinned before the confirmatory probe; every pin held):
`records/2026-07-01_shadow_null_arm_saturation_DIAGNOSIS.md`.

*Why relief rather than parity:* cap-parity was frozen so `real − shadow` isolates the council
("only the selection differs") — but parity-of-caps does not produce parity-of-OBSERVATION.
Because shadow lacks the council's veto it fills its six slots in week one and goes blind,
while the (empty) real book keeps free slots and keeps judging every cycle. The arms do not
face the same opportunity set; the null sample censors to whatever was cheap in week one — a
selection bias in the control, not a controlled comparison. The capital-risk rationale for the
slot reservation does not bind a simulated book that deploys nothing. **Relief RESTORES the
isolation parity was meant to buy.** (Probe quantification: 16/29 slot-vetoed sentinels would
book; 25/29 sentinel vetoes were cap vetoes, not market vetoes.)

*Scope (tight):*
- **Slots only, symmetric across shadow AND 3A** (the `shadow − 3A` contrast stays clean —
  both arms change identically). The null books no longer apply the real book's
  `discovery.sentinel_max_slots`; an explicit `discovery.null_sentinel_max_slots` re-enables a
  null-book-only reservation if ever needed.
- **Everything else byte-unchanged:** cluster caps, per-name, book fraction, `max_open`, and
  the eligibility/gate pipeline stay as frozen (the book cap still bounds total simulated
  exposure); the REAL book's reservation (`paper_loop.py`) is untouched; 3B (already
  uncensored, no caps) is untouched — it remains the whole-basket read on concentrated cohorts.
- **Vintage boundary:** the relief deploy (the merge of PR #138, 2026-07-02) is a SECOND
  vintage boundary; per-position `opened_at`/`run_id` make the vintages separable in every
  read. Vintage 1 = the first-6 week-one cohort (06-03→06-10); vintage 2 = post-relief.
- **Anti-HARK property:** decided with 0 resolutions anywhere — provably not outcome-motivated;
  this property expires at the first resolution (~Nov 2026), which is why it is decided now.

> **Ownership addendum (2026-07-02, after the merge — provenance made explicit).** Option (b)
> was recommended by the advisor and transmitted by the operator as a merge directive ("take
> option (b), symmetric slot relief, decided now while the books are still blind"); the merge
> executed that directive. To close the gap between merge-as-ratification and explicit
> ownership: **RATIFIED 2026-07-02 by the operator's explicit instruction** ("go ahead …
> let's merge", given after the selection and its scope were laid out line-item) — ownership
> of the §8(b) selection and its scope (slots-only, symmetric shadow+3A, real book and all
> other caps byte-unchanged, vintage boundary 2 at the relief deploy) is the operator's,
> exercised on that date.

**§4 activation addendum — (iii)-COMPLETE cap relief for the null books (dated 2026-07-02,
activated by this merge).**

*Why the slot relief was not enough:* the first post-relief L1 (#406, 2026-07-02 19:45 UTC)
booked 5 in each cap-ON arm and landed the shadow book at **$9,951 of its $10,000 cap** — the
arm RE-CENSORS one mechanism up (book cap), exactly as pinned pre-run and graded CONFIRMED
(modal hit) in `records/2026-07-02_burst_prediction_PINNED.md`. The censoring recurses through
the cap stack: slots → book → count (`max_open_positions=15`, found during the fork pick) →
cluster. Partial relief provably strands the quietest cheap names (PAAS misses under book-only
AND book+cluster relief — the addendum's sequential arithmetic).

*The pick (made PRE-BURST, composition-blind; operator-delegated 2026-07-02):*
**(iii)-COMPLETE — book + cluster + count relief for shadow AND 3A, symmetric; the per-name
$1k cap RETAINED** (it is the per-position sizing normalizer the §5 per-position-multiple
metric needs for comparability). Config (this merge): `discovery.null_book_fraction = 1.0`,
`discovery.null_cluster_fraction = 0` (cluster caps OFF in the null books),
`discovery.null_max_open_positions = 100`.

*Scope:* the two SIMULATED cap-ON arms only. The REAL book's frozen frame (PREREG §5 incl.
the cluster amendment) is byte-untouched; 3B and shares (uncensored by construction) are
untouched. For the null books only, this is a dated supersession of the 2026-07-02 scope line
above ("cluster caps, per-name, book fraction, `max_open` … stay as frozen") — per-name stays.
The §2 reads segment accordingly: `shadow − 3A` stays a clean one-variable gate contrast (both
arms change identically); `real − shadow` becomes cap-regime-bundled from vintage 2b onward
(the real book keeps the frozen caps, the shadow book does not) — a known, dated property of
the read, carried alongside the vintage split rather than discovered later.

*Vintage boundary:* **vintage 2a** = the 2026-07-02 burst cohort (L1 #406, cap-ON, 5 names,
salience-skewed by the pinned composition-bias note); **vintage 2b** opens at the first
post-activation L1 (Fri 2026-07-03) — separable by `opened_at`/`run_id`. Pinned expectation
(pre-activation): the remaining cheap union names book at that L1 (~11, incl. PAAS), after
which the arm's binding constraint is the market (cheapness itself) — the intended steady
state for a control arm. *[Dated correction, 2026-07-02 pre-observation: Fri 2026-07-03 is a
full market holiday (July 4 observed — verified live on the broker calendar; Juneteenth run
250 = the precedent for tomorrow's expected no-op L1) — the first post-activation L1 on an
OPEN market is **Mon 2026-07-06 19:45 UTC**; expectation content unchanged, only the date.
See `records/2026-07-02_vintage2b_holiday_redating.md`.]*

*Anti-HARK:* the pick predates the burst (composition-blind at pick time); **0 positions are
resolved in ANY book at activation** (outcome-blind; earliest resolutions ~Nov 2026).

## 5. The metric + the read (the HARKing surface — pinned now, blind)

> *[Dated pointer, 2026-07-06: the frozen READ-LAYER pins
> (`records/2026-07-04_read_layer_pins_PREREG_DRAFT.md`, FROZEN 2026-07-04 v3, implemented in
> `read_layer.py`) COMPOSE with this section: the §1 leg-aware fill-realism band, the §2
> cluster-blocked bootstrap CIs, the §3 resolution calendar + minimum-n floor, and the §4
> counterfactual-mandate ledger. Nothing below is edited.]*

**Unit of comparison: the per-position realized-multiple TAIL** (reuse `shadow_book.tail_summary` /
`tail_report`), per book and per origin (hand_seed / sentinel). The **tail**, not the mean — a convex
book's value is in the tail; the mean reads negative while the book works (most expire worthless).

- **Quantiles (frozen list, from the calibration precedent):** p50 / p75 / p90 / p95 / p99 +
  **P(total loss)**. **PRIMARY = p95** (the convex tail, still estimable at forward N). No post-hoc
  choice of *which* quantile "shows" the gate working — p95 is the pre-committed primary.
- **The lens is DESCRIPTIVE, never a threshold:** "the gate-ON tail quantiles sit above / below the
  gate-OFF **bootstrap CI**." This preserves "no pass-gate, no auto-trade" while still preventing a
  post-hoc read.
- **Bootstrap CIs, not point estimates.** Compare tail quantiles via **bootstrap confidence intervals**
  (resample positions; reuse the FSSD/calibration block-bootstrap machinery), because the books have
  very different N (3B / shares, cap-OFF, book far more positions than the capped real / shadow / 3A) —
  a larger-N book has a naturally wider observed range and would look "fatter-tailed" on point
  estimates alone. The CI carries the small-N uncertainty honestly (wide early, narrowing as N grows).
- **Pool across the whole forward window — NOT a date-matched paired comparison.** Per-position
  multiples are pooled over the entire window, so the **cadence mismatch** (weekly 3B vs. daily real)
  washes out by construction — immaterial at a 6–12-month hold.
- **Report with AND without the top-k outliers** (a robust tail measure) — see §6: the gate-OFF cohort
  is event-enriched, and a single buyout can dominate its tail.
- **The shares null is a DESCRIPTIVE shape / risk-adjusted read, NOT a tail-quantile contest.** You
  cannot tail-compare an option *multiple* to a share *return*. Its return distribution is shown
  *alongside* as context for whether the convex book's bounded-downside / fat-upside is worth the
  premium bleed — explicitly **not** scored against the options tails.
- **Censor council-bug-contaminated runs from the council-marginal read (added 2026-06-03, council
  parse-fix; pinned blind before the window matures).** The `real − shadow` gap (the council's marginal
  contribution) and the proposer Brier are read ONLY over runs stamped `runs.council_health = 'ok'`
  (migration 0011). A run whose proposer LLM calls majority-`parse_error` (the Gemini-3.x
  thinking-starvation that silently inerted L1 #37) is stamped `parse_fail` and **excluded** — the
  council did not deliberate, so "council added nothing" there is a BUG artifact, not evidence. This
  censor scopes to the **council-marginal attribution ONLY**: the brain-off shadow / 3A / 3B / shares
  book tails are gate/cap reads that never invoke the council, so they stay VALID for those runs and are
  NOT censored.

## 6. Survivorship — load-bearing here (the gate-rejected cohort is event-enriched)

This is the subtle, test-specific guard. **Gate-rejected names are, by construction, rich-IV** —
disproportionately **pre-event or distressed** (rich vol often correctly prices an impending big move).
So the **gate-OFF population carries structurally more delist / M&A / squeeze exposure than
gate-passers** — in the very arm that decides the verdict.

- The **terminal-event guard is LOAD-BEARING, not hygiene.** A gate-OFF book name that delists or is
  acquired resolves to its **return to the last available bar** (the `terminal` tag of
  `sentinel_scoring.reference_return_from_bars`), **never a silent drop to None** — else the upper-tail
  test is structurally blind to the fattest part of the tail, biasing the deciding arm. The guard
  covers the **shares arm** too.
- Even with the guard, **one buyout / squeeze can dominate the gate-OFF tail** and read as "the gate is
  empty." The read is therefore reported **with and without the top-k outliers** so the gate-vs-no-gate
  conclusion **cannot hinge on a single event-driven name**.
- **This cuts both ways and IS the crux.** If rich-IV names genuinely carry the fatter convex tail (a
  *population* effect, not one print), then "the gate rejects the best payoffs" is a **real and
  important finding** — exactly the kind of result this null exists to surface honestly.

## 7. Forbidden outputs (HARKing tripwires)

- No selecting names or dates by their outcome.
- No tuning any parameter (k, the quantile, the basket) to a gap number.
- No post-hoc choice of which quantile "shows" the gate working — **p95 is the pinned primary**.
- No "the null **proves** / **disproves** the edge." It informs the **T4 decision** and **calibration**
  only; it never authorizes capital and never trades.
- **Forward, years to significance.** A favorable gap is not validation; an unfavorable one is not
  disproof until the kill rule actually trips. (`PREREG_THEMATIC_CONVEXITY §7`.)

## 8. Scope — what builds, in order

- **PR1 = this document, frozen BLIND** (now), before any harness code or forward result.
- **PR2a = book 3A** (gate-off over the union, cap-ON) — every L1, cheap (the names the cycle already
  processes); the headline gate test (`shadow − 3A`).
- **PR2b = book 3B (gate-off, whole basket, equal-weight) + the shares basket** — weekly (L0 cadence),
  the fetch bounded by the cost ledger. *(BUILT: 3B landed 2026-06-03; the **shares basket split out as
  PR2c**, BUILT 2026-06-04 — `shares_basket.py` + migration 0012 `shares_positions`. Design refined from
  "resolve-and-store one return" to an **append-only entry log + report-time, multi-horizon {180,270,365}
  returns**: the convex book holds ~250d median, not 180d, so a single fixed horizon would mismeasure and —
  load-bearing per §6 — would miss an event landing between 180d and the option's resolution; computing per
  horizon at report time (the §6 `reference_return_from_bars` terminal guard reused per horizon) fixes both.
  Two pinned caveats emitted: descriptive/not-a-contest, and the signed short is FRICTIONLESS → a
  deliberately conservative benchmark.)*

Each new book is a **new never-broker module + table** mirroring `shadow_positions` field-for-field
(so the eventual null-book unification is a mechanical union, `IMPLEMENTATION_PLAN §5b`), reuses the
pure decision functions (`structure.select_structure` — confirmed gate-independent —
`convexity_sizing.convexity_position_size`, the survivorship guard), and is wired **fail-soft**. The
gate-off ⊇ gate-on **superset invariant is asserted at the pre-cap candidate/eligibility stage**
(turning the gate off can only *add* candidates); the *booked* superset holds only where the cluster
cap doesn't bind (the cap + first-come ordering can let a gate-reject displace a gate-passer).

## 9. The basket-quality report — curation-drift sibling (pinned BLIND, dated edit 2026-06-04)

`3B-absolute` is **curation-contaminated** (§3 — it runs over the live basket). The **basket-quality report**
(`basket_quality.py`, report-not-gate; `IMPLEMENTATION_PLAN.md:171`) is the sibling that makes that
contamination auditable: heavy curation drift there → discount `3B-absolute`; **`real − 3B` stays the clean
read**. To keep it honest, its forward *contrast* is pinned here **blind, before any forward result exists**:

- **The decisive surfaced-vs-control null belongs to the sentinel-scoring layer** (the FSSD-style null≈signal
  test, tail not mean). The basket-quality report **surfaces** that contrast — it does not re-own or re-derive it.
- **Pooled, not per-basket** (option ii — a single global control baseline). Per-basket control N is ~1–2/scan,
  too thin to slice; per-basket forward cells are **descriptive surfaced tails only**, never a per-basket contest.
- **Statistic pinned:** the **p95** tail gap (surfaced − control) with a **bootstrap CI**, over the
  report-time multi-horizon **{180, 270, 365}** reference returns (the §6 `reference_return_from_bars` terminal
  guard reused per horizon — NOT the stored 180d). No post-hoc choice of quantile or horizon.
- **Computed-when-mature:** the contrast is emitted only once each arm clears `min_resolved_references_for_flag`;
  before that it reads `insufficient_evidence`, never a point estimate on a thin set.
- **The maturity gate is load-bearing for THIS null's integrity:** because 3B-absolute runs over the live basket,
  outcome-conditioned pruning of basket names on a thin record would make the curation contamination
  **adaptive and outcome-correlated**. So outcome/prune flags are maturity-gated, default KEEP; relaxing the gate
  later is a frozen-frame-grade change. Only data-dead + degenerate-basket flags are evidence-independent.

---

*Frozen 2026-06-03, before any forward results exist. Changes are documented, dated edits to this
doc — never retroactive. — Dramatic Options*
