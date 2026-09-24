# PREREG DRAFT — Direction coherence: a recent-move bear framing must not contradict the filed fundamentals

**Status: DRAFT — NOT FROZEN.** Written 2026-09-24 for the operator's 2026-09-30 review. Nothing reads this
file. On the operator's word it is frozen by moving it to the repo root as `PREREG_DIRECTION_COHERENCE.md`,
where it amends `PREREG_FRESH_INFLECTION_FUNNEL.md` §6 (it adds a condition to that rule; it does not repeal
it). Until then the live loop behaves exactly as today. Build follows the freeze, never the reverse.

## §0 Why — measured, disclosed as motivation, not as evidence of efficacy

The operator asked (2026-09-23) how to get "more top funnel". The funnel is not short of names: the council
judges twelve every session. It is short of names the council can pass. Read-only counts over the current
record segment (since the 2026-08-27 boundary; 19 L1 sessions, 228 proposals, **zero** above the MODERATE
floor):

| framing | proposals | reached the strategist | rejected with the filed fundamentals cited against the framing |
|---|---|---|---|
| bearish | 121 | 83 | 44 (53%), across 19 distinct names |
| bullish | 107 | 75 | 15 (20%), across 9 distinct names |

Two facts stand out. First, **more than half the council's intake is framed as puts**, on a universe curated
from bullish structural theses (AI power, nuclear fuel, copper, space, grid). Second, bear framings are
rejected on contradicting fundamentals at more than two and a half times the bull rate. The nightly count
committed to the operator on 2026-09-22 shows the same thing in miniature: 2026-09-21 → 09-23, fourteen
bear framings reached the strategist and all fourteen were rejected, most in words like "the bearish decay
thesis is directly contradicted by +30% quarterly revenue with positive acceleration" (AMSC) or "record
revenue acceleration, +304% y/y" (LUNR).

**These numbers are the motivation, and they are in-sample.** They are not evidence the rule below will
help, and no parameter below is fitted to them. The rule's in-sample hit rate was deliberately **not**
computed: doing so would invite tuning the thresholds until the motivating data looked best. §6 scores the
rule forward only, from the freeze.

## §1 What `PREREG_FRESH_INFLECTION_FUNNEL` §6 intended, and why it stands

§6 made direction follow the **recent** move (`sign(mom_recent)` when `|mom_recent| ≥ dir_recent_epsilon`),
so that a fresh rollover surfaces as a put — its worked example was NOC at `mom_3m −0.27`. That intent is
sound and this draft keeps it: a name whose price is rolling over **and** whose fundamentals are rolling over
is exactly the fresh bearish inflection §6 was written to catch.

What §6 could not see at the time is the other case, now the common one on this universe: a three-month
pullback in a name whose **filed** fundamentals are growing and accelerating. Motion reads that as a
rollover; the evidence reads it as a pullback in a compounding business. The council has sided with the
evidence every time it has been asked. Proposing those puts spends council capacity on a framing the
council's own criteria cannot pass (`at_inflection` needs the inflection to be real, and the corpus says
the opposite).

## §2 The rule (exact)

At council-union assembly, a candidate whose proposed direction is **bearish** because of the §6 recent-move
rule is **withheld from the union** when its latest filed fundamentals, point-in-time as of the run, show
**both**:

- `revenue.qtr_yoy > 0` — the latest filed quarter's revenue grew year on year, **and**
- `revenue.qtr_yoy_accel > 0` — that growth is faster than two quarters earlier.

Both conditions use the natural zero. There is no tuned threshold, deliberately: a number chosen on the
motivating data would be HARK by construction.

A withheld candidate's slot passes to the next candidate by the existing rank/reserve/fairness order, so the
council still judges twelve names. The withheld candidate is **not deleted**: its sentinel lineage, direction
and markers persist unchanged, and the existing reference-return sweep keeps scoring it forward (that is
what makes the harm falsifier in §6 possible).

**Scope limits, stated plainly:**

- **Bear side only.** The bull-side mirror (a bullish framing contradicted by deteriorating fundamentals,
  20% in §0) is out of scope. It is a smaller effect, and adding it would make the rule a fundamentals-picks-
  direction rule, which is a different claim needing its own measurement (§7).
- **The rule fires only where an acceleration is filed.** `qtr_yoy_accel` needs three filed quarters.
  Annual-only filers (IFRS issuers with an annual line only) and the newest listings (KLAR, STUB, NTSK carry
  one line) are untouched: with no filed acceleration the rule cannot fire, and §6's behavior applies as
  today. KLAR's 2026-09-21 bearish first read, rejected by the strategist on an annual +24.8% line, would
  **not** have been withheld. That is correct: the rule needs filed evidence to act.

## §3 Where it lives, and what it does not touch (the hard seam)

- **Lives at union assembly** (`council.wiring.council_to_themes`), which already receives the fundamentals
  corpus for the context pack. It is composition-only, in the same class as the frozen gate-cheap reserve
  and the fairness slots: it changes which names the council is shown, never how the council judges them.
- **Deterministic.** Filed XBRL lines only. Never an LLM label, never the framer's verdict, never price.
- **The brain-off shadow book is affected identically**, because it runs over the same union. The
  real-versus-shadow contrast therefore stays paired: both arms see the same candidates.
- **Untouched:** the L0 surface gate and ranking; `discovery.direction_of` itself (the rule reads its output
  and withholds; it does not re-compute direction); the 3B whole-basket book and the shares log (they use the
  trailing-momentum direction over the whole basket and never see the union); the IV gate and every
  threshold; sizing; the cluster cap; the council prompts (sha-pinned, unchanged); the miss base-rate ledger.

## §4 Data discipline

- **Point-in-time.** The corpus is read as of the run (`corpus_asof`), exactly as the context pack reads it.
  A quarter filed after the run date cannot fire the rule.
- **Missing or partial data never fires the rule.** The rule removes a candidate, so it acts only on filed
  evidence. No revenue line, no `qtr_yoy_accel`, or a corpus read error ⇒ the candidate is kept and §6
  applies unchanged. This is the conservative direction for a withholding rule: absence of data must not
  manufacture a veto.
- A corpus read error is counted, never raised: a bug here must not halt the council cycle (fail-soft for
  composition, as the reserve is).

## §5 Telemetry and record segmentation

- One journal line per L1: `direction-coherence: withheld=[...] kept_no_accel=[...] errors=N`, and the
  same counters appended to `runs.note` (journald rotates; the runs row does not — the anti-silent-dormancy
  convention).
- Per-proposal provenance: withheld candidates are recorded with `selection="withheld_dircoherence"` so
  the funnel and dashboards can count them.
- **Record-segmenting.** The union composition changes, so the `runs.model_mix` `union_rank` stamp gains a
  suffix (`cheap_reserve_v1+fairness_v1.1+dircoherence_v1`). The first run under the rule is a segment
  boundary: never pool Brier or council-marginal across it.

## §6 Forward scoring and falsifiers (never backtested)

All reads are forward from the freeze.

- **F1 — harm (the load-bearing falsifier).** The withheld cohort is scored forward by the existing
  reference-return sweep. At **h = 126 trading bars**, compare the withheld cohort's *bearish-directional*
  return tail (p90) with the tail of the bear framings that were **kept** (the coherent ones). If the
  withheld cohort's downside tail is as heavy or heavier, the rule is throwing away real bear setups and is
  **reverted**. Small-n guard: no verdict below 10 matured withheld names; below that the read is
  "accruing".
- **F2 — mechanical.** Within the first five sessions, no withheld-class candidate (bearish, growing,
  accelerating) reaches the council. This checks the wiring, not a hypothesis.
- **F3 — capacity, descriptive only.** The share of council slots spent on bear framings rejected with the
  fundamentals cited against them should fall, and the freed slots' deliberated (non-abstained) rate is
  reported beside the pre-freeze baseline. The pre-freeze above-floor rate is zero, so no benefit claim is
  pinned: F3 describes, F1 decides.
- **Read dates.** F2 at five sessions after deploy; F1 first readable around h = 126 after the tenth
  withheld name, and re-read at every quarterly curation review.

## §7 Explicitly out of scope

- The **bull-side mirror** (§2). If wanted, it gets its own draft after F1 has read.
- **Letting fundamentals choose direction** (flipping a withheld bear into a bull). That would make the
  funnel propose a "buy the pullback in a grower" trade, a signal claim the prescreen is forbidden to make
  (prescreen rank is a funnel, never a tradeable signal).
- **Lowering the MODERATE floor or relaxing the §10.7 criteria.** That is the one lever guaranteed to
  produce entries, and this draft does not touch it.
- **Any tuning** of the two zero thresholds after the freeze, except by a dated amendment that re-segments
  the record.

## §8 Alternatives considered, and why not

- **Re-frame the withheld name by trailing momentum instead of withholding it.** Rejected: on these names
  trailing momentum is usually up, so the name comes back as a bullish momentum candidate and meets the 43%
  "the move already happened" rejection instead. The slot would still be spent.
- **Withhold at L0 (never surface the name).** Rejected: the sentinel would never exist, so the reference
  sweep could not score it and F1 would be impossible. Withholding at the union keeps the lineage and its
  forward score.
- **Require bear framings to agree with the register's thesis direction.** Rejected: every register thesis
  is bullish, so this would make the book single-sided and forbid a genuine broken-thesis put, which the
  two-sided mandate must keep proposable.

## §9 Open numbers the operator sets at freeze

- F1's horizon (proposed h = 126 bars) and small-n guard (proposed 10 matured names).
- Whether F3's descriptive read also reports the withheld cohort's shadow-book outcome.
- The freeze date, which fixes the segment boundary.
