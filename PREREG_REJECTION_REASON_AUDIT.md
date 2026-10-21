# PREREG — Rejection-reason audit: does the council's timing test filter losers?

**Status: FROZEN 2026-10-21 (operator's word: "Sure", to "Shall I freeze #327 …?").** Freezing commits the definitions and the decision rule
**before any 126-trading-bar (~6-month) outcome of a council judgment exists** (the earliest judgment,
2026-06-02, matures in early December 2026). Nothing here changes the council, the gate, sizing or the risk frame. It is a measurement, and it
decides nothing automatically: its verdict goes to an operator review.

## §1 — Why

- Since the direction-coherence boundary, the strategist has failed `at_inflection` on essentially every
  deliberated name. On L1 #1747 (2026-10-20) it passed `under_narrated` on 6 of 10 and failed `at_inflection` on
  all 10. Since June, of ~700 flagged judgments (~270 timing-only), ~20 passed `at_inflection`. The criterion is the system's only
  binding filter (`records/2026-10-13_f4_review_evidence_pack.md` §2).
- The pre-registered `real − shadow` contrast (PREREG_FIXED_BASKET_NULL §2) measures the council as a whole. It
  cannot say **which** criterion is right. With the real book empty, it reads as "was saying no to everything
  right?", not "is the timing test right?".
- For a 6–12-month far-OTM call the economic question is whether a further large move is plausible within the
  option's life and not yet priced. "The move has already happened" is a judgment about that, and it is testable
  forward on the underlying's subsequent move.

## §2 — Disclosures (anti-HARK, what CC had seen at drafting)

- **No 126-bar outcome of any council judgment has matured;** no class-split outcome has been computed.
- Seen: the shadow book's aggregate mark (43 open, −32% mid-life), its best mark (FRO, 4.1×; FRO was rejected 10
  times as "the move has already happened" / revenue −8.8%), and current prices / momentum for ERO, HL, KKR, FIG,
  TITN, CEG (the marker-refresh work, 10-16). These motivated the audit; they are not inputs to it.
- Class counts only (no marks) for the shadow book: timing-only 4, both-failed 8, abstained 6, unjudged 20,
  flags missing/unparsed 5.

## §3 — Primary read: every strategist judgment, scored on the underlying (higher n, resolves first)

- **Unit:** the **first** strategist judgment of each lineage `(symbol, direction)` in each calendar month (one
  per lineage-month — ERO was judged 14 times in a row; repeats are not independent). Hand-seeds excluded.
- **Classes (from the strategist's own JSON flags, no regex):**
  - **T — timing-only:** `under_narrated = true ∧ at_inflection = false`.
  - **N — narration-failed:** `under_narrated = false` (either `at_inflection`).
  - **P — passed both:** `under_narrated = true ∧ at_inflection = true` (rare; reported, not compared).
  - Judgments without both flags (June's pre-flag outputs, parse failures) are excluded and counted.
- **Outcome (the miss-base-rate ledger's own definitions, so B is directly comparable):** the directional return
  of the underlying from the judgment day's close over **h = 126 trading bars** (~6 months), via
  `sentinel_scoring.reference_return_from_bars` (survivorship guard unchanged; a terminated series resolves to its
  last bar). Directional = raw for bullish, negated for bearish. **Hit = directional return ≥ +0.50** (the ledger's
  "big move"; for the ~25%-OTM structure, the move that pays several-fold). Reported beside it, not decided on:
  ≥ +0.25 (the strike reached) and ≥ +1.00 (the ledger's second threshold). A judgment counts only once 126 bars
  have elapsed or the series terminated.
- **Base rate B:** the ledger's reported P(big move at h = 126 | gate-cheap, cohort = universe) for the same weeks
  (PREREG_MISS_BASERATE; sealed, already accruing). It is printed only once its cell has ≥ 20 matured rows; until
  then B is "not yet readable" and only the T-vs-N half of the rule applies.

## §4 — Decision rule (frozen before outcomes)

Read when **n_T ≥ 30** matured lineage-months (expected ~February 2027), then monthly. With Wilson 90%
intervals, no significance claim (calibrate-not-prove):

- **"The timing test is not filtering losers"** iff hit(T) ≥ hit(N) **and** hit(T) ≥ B (B once readable). → An operator review of
  `at_inflection` is owed (candidate: re-specify it to the option's horizon — "a further large move is plausible
  within the tenor and not yet priced"). Any change is its own dated amendment and re-segments the record.
- **"The timing test earns its keep"** iff hit(T) ≤ hit(N) − 5 pts **and** hit(T) < B (B once readable). → Recorded; no change.
- **Otherwise inconclusive**: re-read monthly to n_T ≥ 60; if still inconclusive, recorded as such.
- Segmentation is reported, never pooled across: the marker-refresh boundary (L1 #1712, 2026-10-16) and the
  direction-coherence boundary (#1437) split the T judgments; the decision uses the pooled count only if both
  segments point the same way.

## §5 — Secondary read: the shadow book's options (the economic measure, small n)

Each shadow position is classed by the strategist's judgment of the same `(symbol, direction)` in the **nearest
L1 session within ±10 sessions of entry** (before entry preferred), else "unjudged". At each position's
resolution (expiry / profit-take / time-stop), its realized multiple is recorded by class. Reported beside §3 at
every read: mean multiple, share ≥ 1×, share ≥ 3×, per class. **Descriptive only** (n is ~4–12 per class).

## §6 — Out of scope

Changing any criterion, prompt, floor or gate; the council's Brier scoring (unchanged); the null books
themselves (unchanged). A read script (`scripts/probe_rejection_audit.py`, read-only, counts and rates only) is
built after the freeze and before the first resolution.
