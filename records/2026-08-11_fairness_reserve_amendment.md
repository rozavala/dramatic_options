# Fairness reserve — amendment to the gate_cheap_reserve composition (2026-08-11)

**Operator decision (TRUE form):** asked "what needs to be done regarding the starvation?",
presented four options with evidence, chose **"2 reserved slots"** (2026-08-11, structured ask;
recommended option). Build STAGED for explicit operator merge per the 2026-06-26 discipline
(judged-set composition = forward-scoring-adjacent change class; never auto-merged).

## The evidence (why)

- 34 active sentinel candidates compete for 12 nightly union slots → 23 unjudged per night.
- The rank is salience+cheap-reserve, so starvation is *persistent*, not rotating: **IRDM
  0-for-14** since its 2026-07-26 re-surface (the first-ever surface_count=2 lineage) — and it
  now carries a **fresh structural filing** (2026-08-09 `fresh_on_active_lineage`) decaying
  unjudged inside its event window (the LUNR-gap class, recurring). **VIAV 0-for-2** — admitted
  2026-08-03 (window #3), surfaced on its first scan 08-09, never judged: **the admission act
  does not convert into judgment.**
- Concrete harms: (1) a starved name can never earn the council-confirmed
  `under_narrated=TRUE` that the §10 off-cycle admission warrant runs on (the CC precedent);
  (2) fresh filings lapse unjudged; (3) no Brier accrual (the label-only reference sweep still
  covers forward outcomes, so scoring is degraded, not blind).

## The design (what)

`compose_judged_set` gains a second reserve class beside the frozen gate_cheap_reserve
(2026-07-02, K=3): **M=2 fairness slots** from the post-motion remainder.

- **Eligibility:** any remaining sentinel — deliberately NO cheapness gate (cheapness stays the
  cheap-reserve's job; this class exists precisely for names cheapness can't rescue).
- **Rank:** fresh-event-on-active-lineage FIRST (`state.fresh_event_symbols`: active lineage,
  `has_event` markers, seen ≤7 days — a new filing is judged the *next* L1) → least-recently-
  judged (never-judged sorts first, reusing the frozen §4 `council_last_judged` input) → symbol.
- **Fail-closed:** unfilled slots backfill to motion order; `fairness_slots=0` is byte-identical
  to the pre-amendment composition (pinned by test).
- **Composition-only:** prompts, gates, sizing, candidate objects untouched (the §10 seam);
  hand-seeds stay protected-first; total stays 12 (zero marginal LLM cost beyond the roundtrips
  the rescued names themselves generate).
- **Observable:** per-proposal selection provenance `"fairness"`; the cheap-reserve log line
  extended with `fairness: m/filled/fresh_event/fairness` + displacement, every cycle.
- **Record-segmenting:** `runs.model_mix.union_rank` → `cheap_reserve_v1+fairness_v1` from the
  deploy (self-describing stamp, zero migration). Never pool council-marginal/Brier reads
  across the boundary.

## Coverage arithmetic (expectation, not a promise)

~22 non-selected actives rotating through 2 LRJ slots ≈ every active judged at least once per
~2 weeks (fresh-event arrivals preempt; TTL dormancy shrinks the pool). IRDM and VIAV are the
first two rescues by construction (never-judged sorts first).

## Status

- BUILT + tested (22 reserve-suite tests incl. 6 new: off=byte-identical, starved-rescue,
  fresh-event-beats-LRJ, no-overlap with cheap reserve, hand-seed protection, the
  `fresh_event_symbols` state read). Full suite green.
- **STAGED — merges only on the operator's explicit word.** Merging = the amendment's dated
  activation; the first post-deploy L1 opens the `fairness_v1` record segment.
