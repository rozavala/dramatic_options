# PRE-REG (DRAFT — for RED-TEAM; NOT frozen, nothing builds or runs) — the gate-cheap RESERVE in the council's judged set

**Date:** 2026-07-02 · **Status: DRAFT.** All yield-determining knobs are proposed BLIND in §9
(the red-team surface). Freeze = pin §9 + operator sign-off, BEFORE any code. Motivated by a
MEASURED finding (§1), not a brainstorm — the first yield-side lead since the idea-supply line
closed 2026-07-01.

---

## §1 — Why (the measured finding)

Across all 14 L1s since the OPRA flip (runs 130→389), **~16–23 gate-cheap union names are
rank-truncated out of council judgment EVERY cycle — roughly two-thirds of the gate-cheap
union is never judged.** 25 distinct names; **13 truncated on 14/14 L1s** (CCJ, SMR, NNE, NEE,
GEV, KTOS, AMSC, RDW, FLY, SMCI, LUNR, ATKR, LMT); the admitted quiet cohort — PAAS, HL, FRO —
on 7 L1s each. PAAS has **never** appeared in `council_proposals` while reading gate-cheap on
the real OPRA chain since 06-23. (Query: 2026-07-02, `gate_dualread` opra-arm `cheap=1` ∩
ever-surfaced sentinels − `council_proposals` per run.)

**Mechanism:** `council.propose` truncates the union at `[:max_candidates]` (=12,
`council/council.py:67`); the union is ordered hand-seed-first then sentinels by
`inflection_score DESC` (`sentinels.py:95-102`, `state.py:1093-1096`). `inflection_score` is
the MOTION/salience rank — so the documented anti-quietness bias operates at a fourth point
(after motion-surfacing, rv_slope, thin-news): **for gate-cheap quiet names, the binding
constraint is that judgment never occurs.** The 2026-06-25 catch-problem arc found the same
truncation (~23-25/35) but before cheapness was measurable per name; the cheapness-watch +
dual-read now make the starved subset visible and specific.

## §2 — The change (ONE, composition-only)

Replace the plain `[:12]` slice with a reserved composition, same total (zero marginal LLM
cost):

> hand-seeds (unchanged, protected, first) + top-(N−K) sentinels by `inflection_score`
> (unchanged rank) + **K RESERVE slots** = gate-cheap union sentinels not already selected,
> ranked by the §4 rule.

The reserve changes **WHO is judged, never HOW**: prompts byte-identical (sha-pinned),
tri-criteria unchanged, framer unchanged, IV gate / caps / sizing / kill untouched, no
admission path, no sizing input. The hard seam holds: discovery proposes, council judges,
deterministic gates dispose.

## §3 — The cheap signal (data contract; fail-closed)

Reserve eligibility = the most recent **gate-of-record** cheap read for the name, aged ≤ S
trading days: primary `cheapness_watch` (`cheap=1`, the real tradeable structure); fallback
`gate_dualread` `feed='opra'` `cheap=1`. Both are written AFTER the council in each cycle
(`orchestrator.py:827` vs `:685`), so the read is **necessarily prior-cycle — staleness ≥ 1
trading day, pinned honestly.** A name with no qualifying read within S is NOT
reserve-eligible (fail-closed to the motion rank — the reserve never infers or models
cheapness, it only re-uses the recorded gate read).

## §4 — Within-reserve ranking (deterministic, salience-free)

**Least-recently-council-judged first** (never-judged = oldest), tie → lowest `iv_rv`, tie →
symbol asc. This is a COVERAGE rotation: with C ≈ 20 persistently-cheap names and K slots,
every gate-cheap union name is judged at least every ⌈C/K⌉ L1s (~7 at K=3) instead of never.
Rejected alternatives: cheapest-first (sticky — the same names daily, coverage never widens);
random (non-reproducible).

## §5 — Anti-manufacture guards (pinned BLIND, before any outcome)

- **The success metric is COVERAGE, not includes:** rolling-7-L1 fraction of gate-cheap union
  names judged ≥1× (current ~⅓ → target ~1.0). **Pinned expectation: most reserve names read
  `at_inflection=False` (post-move or catalyst-absent) → 0 includes remains the likely
  outcome.** The value claimed is that the record can say "judged and rejected on leg X"
  instead of "never judged," and that the first-entry channel is no longer starved by the
  salience rank.
- An include arriving via the reserve is the COUNCIL's include, forward-scored (Brier) like
  any other — it does not validate the reserve, and the reserve is never tuned toward it.
- Displaced names (the bottom-K motion-ranked sentinels that yield their slots) are logged
  per cycle — the displacement is observable, not silent.

## §6 — Attribution / record segmentation (zero migration)

- `union_rank:cheap_reserve_v1` merged into `runs.model_mix` (the established stamp idiom) —
  record-segmenting from the deploy.
- Per-proposal provenance: `selection: "reserve" | "rank"` riding the `council_proposals.rationale`
  JSON (the telemetry channel §9-integration established) — council-marginal and Brier reads
  can decompose reserve-judged vs rank-judged.

## §7 — Known interactions (flagged for red-team)

- **Marker staleness (finding #1):** reserve names may be judged on TTL-stale markers
  (refresh only on L0 top-K re-entry; ages 15–22d typical). Default = ACCEPT + observe via the
  `markers_asof` stamp (merged PR #95); inline marker refresh for K names is scope creep,
  rejected by default (red-team may overrule).
- **Independent of the 2026-07-02 null-book slot relief** (that changed the null books'
  BOOKING; this changes the council's JUDGED SET). The real book's `sentinel_max_slots`
  reservation still binds any resulting real trade at the trade path — unchanged.
- **Direction:** the reserve uses the sentinel's persisted direction (the same one the watch
  structured); no re-derivation.

## §8 — Review (dated, blind)

After **4 weeks** of L1s from deploy: (a) coverage metric vs target; (b) council health
unchanged (parse rate, cost/cycle — expected flat: same 12 calls); (c) the displaced-names log
reviewed for any systematic harm (a motion-ranked name that would have been judged and
included — assessable because displaced names remain in the union and rotate back). No include
expectation is part of the review (§5).

## §9 — The BLIND values to red-team (freeze = pin these + sign-off)

| # | knob | proposed | note |
|---|---|---|---|
| 1 | K (reserve slots) | **3** of the 10 sentinel slots (12 total − 2 hand-seeds) | ⌈20/3⌉ ≈ 7-L1 full rotation |
| 2 | S (cheap-read staleness) | **5 trading days** | prior-cycle by construction; fail-closed past S |
| 3 | within-reserve rank | least-recently-judged → lowest iv_rv → symbol | coverage rotation, §4 |
| 4 | coverage target | rolling-7-L1 judged-fraction ≈ 1.0 | the success metric, §5 |
| 5 | review horizon | 4 weeks | §8 |
| 6 | stamps | `union_rank:cheap_reserve_v1` + `selection` field | §6 |

## §10 — Status / what commits

DRAFT for red-team. **Nothing builds until: red-team convergence → §9 pinned → operator
sign-off (the freeze).** Expected build after freeze: one PR (the `council/council.py`
selection + the wiring stamp + tests incl. a seam-guard: reserve can alter only membership of
the judged set, never a prompt byte, a gate value, or a sizing input). Kill-before-spend,
fail-closed, and the cost ledger unchanged.
