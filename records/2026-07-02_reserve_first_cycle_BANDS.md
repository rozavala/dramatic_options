# 2026-07-02 — BLIND bands for the gate-cheap reserve's FIRST live cycle (Mon 2026-07-06 19:45 UTC L1)

**Status: PINNED BEFORE OBSERVATION** (the reserve deployed 2026-07-02 ~23:47 UTC, box
`48df998`; Fri 07-03 is a market holiday → the first live council cycle with the reserve is
**Mon 2026-07-06**; the Sun 07-05 L0 runs in between — see the caveat). Written the night of
the deploy, before any reserve cycle has run. Grade Monday alongside the vintage-2b null-book
burst (`records/2026-07-02_vintage2b_holiday_redating.md` — a separate grade, same night).

## The correction this record makes before observation

Earlier tonight (the operator report accompanying the #139 freeze) I wrote that the reserve
would put "PAAS in front of the council" on its first cycle. **The frozen §4 rank says
otherwise, and the frozen rank decides:** among never-judged gate-cheap names the tie-break is
*lowest iv_rv*, and three never-judged names are cheaper than PAAS (iv_rv 0.985) on the
gate-of-record reads. Running the deployed `compose_judged_set` against the live DB as of
tonight (33 cheap-eligible ∩ fresh, 17 of them never council-judged, 19 symbols judged-ever):

| reserve cycle (L1) | expected cohort (frozen rank: never-judged → lowest iv_rv → symbol) |
|---|---|
| 1 — Mon 07-06 | **IRDM (0.589) · FRO (0.790) · RDW (0.917)** |
| 2 — Tue 07-07 | HL (0.943) · ATKR (0.946) · **PAAS (0.985)** |
| 3 — Wed 07-08 | SMR · FLY · NNE |
| 4–6 | LUNR/CEG/AMSC → LMT/LHX/ERO → UROY/TGB |

**PAAS's first-ever council judgment is expected cycle 2 (~Tue 07-07), not Monday.** The full
17-name never-judged cheap cohort sweeps in ~6 reserve cycles (~6 trading days) — after which
the reserve rotates by least-recently-judged, the §4 steady state.

## HARD falsifiers (mechanism level — a miss here reopens the build, record don't explain)

1. The `Cheap-reserve: k=3 …` wiring log line appears on Monday's L1 with `filled ≥ 1`
   (eligible ≈ 30+ names exist; filled=0 with a populated cheap read = a data-contract bug).
2. The judged set stays **12 total** (the reserve never grows the council's cost surface —
   ledger calls comparable to tonight's ~30).
3. `runs.model_mix` carries **`union_rank: cheap_reserve_v1`** AND the three prompt-shas
   **unchanged** (d96f18ebc865a384 / dc3d21ca8f6444cb / ecbf363c9802289d — a drifted byte is a
   seam violation, not a tuning event).
4. Every persisted proposal's rationale carries `selection: "reserve" | "rank"`; the reserve
   names' proposals exist (i.e., they were actually judged, not silently dropped pre-council).

## Expected bands (name-level — modal, NOT falsifiers)

- **Reserve cohort = IRDM / FRO / RDW** (the table above). *Caveat that makes this modal
  rather than hard:* the **Sun 07-05 L0** re-scans (markers refresh, TTL expiries, possible new
  sentinels) and Monday's motion-8 line moves with `inflection_score` — a name crossing into or
  out of the top-8, a TTL expiry, or a fresh discovery legitimately reshuffles the cohort. The
  grade is "3 never-judged gate-cheap names from the pinned pool were reserve-judged," with the
  exact trio as the modal expectation.
- **Displaced (logged, not silent): the bottom-3 motion names** — on tonight's state AG / UEC /
  HL. They lose *judgment* only; the (now uncapped) null books still book every gate-passer, so
  nothing is lost from the control arms.
- **Includes: 0–1.** The §5 pinned expectation stands — most reserve names should read
  `at_inflection = False` (quiet-cheap often means the move hasn't started *or* the market
  disagrees; that is the point of judging them). 0 includes Monday is HEALTHY. An include, if
  one arrives, is the council's own (forward-scored like any other) and does not validate the
  reserve.
- **Cost: flat** (~$0.20/cycle class; same 12 candidates, same 3 roles).
- IRDM's 0.589 iv_rv is the cheapest gate-of-record read in the pool — if the council reads it
  `structural=False` or grounding-starved, that is the §5 "judged and rejected on leg X"
  outcome working as designed; record the leg.

## What Monday night's grade covers (two layers, one run)

1. **Vintage 2b** (null books, re-dated from Fri): the remaining cheap union names book
   (~11 incl. PAAS — PAAS *books* Monday even though it isn't *judged* until ~Tuesday; booking
   and judgment are different channels by design).
2. **The reserve's first cycle** (this record): HARD falsifiers + the modal cohort above.
