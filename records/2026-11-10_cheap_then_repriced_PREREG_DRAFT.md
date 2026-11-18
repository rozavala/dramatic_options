# PREREG DRAFT — Cheap-then-repriced ledger: is a gate-cheap read followed by repricing?

**Status: DRAFT — NOT FROZEN.** Issue #455 (M3). Written 2026-11-10, before any row exists. Nothing reads this
file and no code exists for it. The operator decides whether to freeze it (as `PREREG_CHEAP_THEN_REPRICED.md`
at the repo root), whether its writer rides the Sunday miss-ledger sweep, and every value marked **[PIN]**.
**Numbers marked [PIN] are proposals.** Report-not-gate: no output reaches discovery, the council, the gate,
sizing or a prompt, and the ledger has no write path into `config.convexity_gate`.

## §1 The question, stated forward

Each week at sweep time t, read the production gate on every name in two cohorts. At t + h, read what happened
to the same contract and the same underlying. The question is whether rows that read cheap at t are followed
by repricing more often, or by more, than rows that did not. The operator's thesis (PREREG_THEMATIC_CONVEXITY,
the 2026-06-01 thesis-framing amendment) is that the far wing is mispriced when an anticipated trend changes; this ledger tests the
weaker, measurable part: does cheap-at-t predict a rise in the wing's IV or mid within 21–63 trading days.

## §2 What is stored today, and what is not (verified)

| Needed at t or t + h | Where it exists today | Usable here? |
|---|---|---|
| `iv_rv`, `otm_skew`, `cheap`, wing OCC symbol, per name per night | `gate_dualread` (migration 0014), OPRA arm, `source='sweep'`, written by `gate_dualread.sweep_universe` at every L1 | Universe names only (the sweep walks `config.universe.themes`) |
| The same for the frozen market sample | Nowhere. The miss ledger stores `date, key, cohort, direction, structured, gate_cheap, entry_close, feed` (`miss_baserate.LEDGER_COLUMNS`) | No |
| The selected wing's IV | Not in `gate_dualread`. `GateVerdict.wing_iv` is computed in `convexity_gate.is_cheap_convexity` and discarded by `shadow_gate_eval`. `cheapness_watch.wing_iv` stores it daily, but only for active sentinels | Partial (sentinels) |
| The selected wing's bid / ask / mid | Nowhere. `Contract` carries `bid`/`ask` (`convexity_gate.Contract`); no sweep persists them | No |
| A 25%-OTM IV per expiry | `iv_term_snapshot` (`iv_history.term_record`, from 2026-11-03): ATM and the strike nearest spot × 1.25 per expiry, universe only | A constant-moneyness proxy, not the same contract |
| Full per-contract IV surface | `option_chain_snapshot` (`convexity_data.snapshot_record`), entry-path names only; silent since 2026-07-01 per `dashboard_data.data_gathered_panel` | No |
| Underlying bars | The point-in-time cache / Alpaca bars | Yes |

Three consequences:
- **Outcome (2), the mid multiple, cannot be computed from any existing table.** The writer must record the mid at t.
- **Outcome (1), the same contract's IV change, cannot be computed from `gate_dualread`.** `iv_rv` is
  `atm_iv / rv` at the wing's expiry (`is_cheap_convexity`); the wing IV is `atm_iv + otm_skew/100`, and `rv` is
  not stored, so recovering it needs RV recomputed from bars. UNVERIFIED that a recomputation matches the value
  used that night. The writer must record `wing_iv` and `rv` at t.
- **`Δiv_rv` moves when RV moves, with no change in IV.** It is reported, but it is not a repricing measure.

The issue's statement that the outcomes come "all from data we already store" holds only for the underlying's
return and for `Δiv_rv` on universe names.

## §3 Design [PIN throughout]

- **Writer.** A sibling output of `scripts/probe_miss_baserate.py sweep`. That loop already holds, per name,
  the selected structure `s` (with `s.contract` bid/ask/iv/strike/expiry) and the verdict `v` (`iv_rv_ratio`,
  `otm_skew_volpts`, `atm_iv`, `wing_iv`, `rv`) from the gate-of-record feed (`config.data_feed.option_gate`),
  and today keeps only `cheap`. It appends to a new file, `records/cheap_repriced/ledger.csv`; the miss ledger's
  own file, columns and reads are untouched. No loop module changes; no LLM calls; no extra chain pulls at t.
- **Exposure source.** Both cohorts take exposure from this same read at t (symmetric). For universe names, the
  most recent L1 `gate_dualread` OPRA sweep row is recorded beside it as a cross-check, and a disagreement on
  `cheap` is counted. This departs from the issue's wording ("from the gate of record" nightly row) because the
  market cohort has no such row.
- **Cohorts.** `universe` = `config.universe.themes` at sweep time; `market` = the frozen 150-name denominator
  (`records/miss_baserate/denominator.txt`), never re-drawn.
- **Unit: one row per name per week.** Justification: `iv_rv`'s denominator is a 252-day realized vol and ATM IV
  is persistent, so consecutive nights carry nearly the same exposure; and a 21-bar outcome window from
  consecutive nights overlaps by 20 of 21 bars. Nightly rows would multiply n about five-fold with almost no new
  information. Weekly rows still overlap (16 of 21 bars at h = 21, 58 of 63 at h = 63), so inference is
  name-blocked (§5). UNVERIFIED: the measured lag-1 autocorrelation of `iv_rv` in `gate_dualread` (no DB here).
- **Row at t:** date, sealed key, cohort, direction, structured, gate_cheap, `iv_rv`, `otm_skew`, `atm_iv`,
  `wing_iv`, `rv`, wing kind/strike/expiry (no ticker), wing bid/ask, spot, feed, and the cross-check flag.
- **Direction.** The miss ledger's and `gate_dualread.sweep_universe`'s convention: sign of
  `close[-22]/close[-253] − 1`, bullish if unknown. Directional return = raw for bullish rows, negated for bearish.
  IV changes are not sign-adjusted: the wing is already on the thesis side (call for bullish, put for bearish).
- **Gate parameters.** Read from `config.convexity_gate` at t and stored with the row, including the 15% floor
  and the side guard (`min_otm_moneyness`, `otm_side_guard`). Rows begin after the freeze, so every row is in the
  post-2026-11-08 regime.

## §4 Outcomes

Read at the first Sunday sweep on or after t + 4 weeks and t + 13 weeks (≈ 20 and ≈ 65 trading bars) **[PIN]**,
so the same chain pull serves new rows and maturing rows. The exact elapsed bar count is stored with each read.
- **O1a — same-contract IV change:** IV of the stored wing (same kind/strike/expiry) at the maturity read minus
  `wing_iv` at t, in vol points. Missing if the contract is absent from the chain or has no IV.
- **O1b — `Δiv_rv`:** the name's `iv_rv` at the maturity read (whatever wing it then selects) minus at t.
  Reported; not a repricing measure (§2).
- **O2 — mid multiple:** mid at maturity ÷ mid at t, where mid = (bid + ask)/2 and both sides are > 0. "Still
  quoted" = both sides > 0. Otherwise `unquoted`, counted, and the statistic is printed twice: unquoted excluded,
  and unquoted set to 0 (the worst case) **[PIN]**.
- **O3 — directional underlying return:** exactly 21 and 63 trading bars from the spot at t, through
  `sentinel_scoring.reference_return_from_bars` so a terminated series resolves to its last bar.
- **Binary companions [PIN]:** `repriced` = O1a ≥ +3.0 vol points; `paid` = O2 ≥ 2.0. Neither is tuned after
  the first row.

**Survivorship.** A name that delists or is acquired stays in its cohort and its week: O3 resolves through the
terminal guard; O1a and O2 are `unquoted (terminated)`, counted separately and included as 0 in the worst-case
O2 column. A row is never dropped for lack of a later quote.

## §5 Contrasts, tests, minimum n

- **Primary contrast: the cheapest tercile vs the rest**, within cohort × sweep date, over structured rows with a
  non-null `iv_rv`; "cheapest" = the lowest third of `iv_rv`. A tercile fills by construction, which is why it is
  primary.
- **Secondary: `gate_cheap = 1` vs `gate_cheap = 0`.** Not-cheap rows are scarce. The 2026-11-08 miss-ledger
  sweep: universe 34 of 35 structured names cheap (1 not cheap); market 30 of 34 (4 not cheap). The earlier
  regime was less extreme (11-01: market 38 of 54; 10-04: 74 of 99).
- **Per-cohort reads first.** Within-universe and within-market tercile contrasts; universe vs market among
  cheap rows is a descriptive companion only (PREREG_MISS_BASERATE owns the cohort contrast).
- **Small-n guard:** a cell needs ≥ 20 matured rows ∧ ≥ 8 distinct sealed keys; below that it prints `n<20`
  (the miss ledger's `MIN_CELL_N` string) and no rate or median.
- **Tests.** Continuous outcomes (O1a, O2, O3): the difference in medians with a **name-blocked bootstrap** 95% CI
  (resample sealed keys with replacement, 2000 iterations, seed 0). The Mann–Whitney U is printed beside it,
  labelled "rows overlap; not independent". Binary companions: two-proportion z (as
  `miss_baserate.two_proportion_z`, one-sided, 1.64) under the same guard, printed with the same label; the
  name-blocked CI on the difference in proportions is the figure quoted.
- **If a cell never fills.** If the `gate_cheap = 0` cell has < 20 matured rows at a read date, it prints
  `never filled by <date>`. That is itself reported as a finding about the gate on this universe (it rarely
  says no), never as a reason to change `iv_rv_max` or the skew threshold. If a tercile cell fails the guard
  (a cohort with < 60 structured rows matured), it prints `n<20` and the read waits.

## §6 Sealing and the market sample

- Per PREREG_MISS_BASERATE §3, per-name verdicts are sealed. This ledger seals with its own salt:
  `sha256("cheap_repriced_v1:" + SYMBOL)[:12]`, so its keys cannot be joined to the miss ledger's by eye.
- The OCC symbol contains the ticker, so the row stores only kind/strike/expiry. At maturity the writer
  reconstructs the symbol from the plain denominator and universe lists, as the miss ledger's `report` does
  (`key_to_sym`). The report prints no symbol, key or per-row value (asserted by test, as the miss ledger).
- PREREG_MISS_BASERATE §5 applies unchanged: market names are never surfaced as candidates, in any form.

## §7 Read dates [PIN]

- First rows: the first Sunday sweep after the freeze (earliest 2026-11-15).
- h = 21 read: Sunday 2027-01-10 (21 bars from 11-15 ends 2026-12-15 by the NYSE calendar; two more weeks of
  rows fill the guard). h = 63 read: Sunday 2027-03-07 (63 bars from 11-15 ends ≈ 2027-02-17). Both are reads
  that may be stated; neither is a gate decision.

## §8 Allowed and forbidden claims

- **Allowed:** "Rows in the cheapest `iv_rv` tercile were followed at h = 63 by a median same-contract IV change of
  X vol points vs Y for the rest (name-blocked CI a–b; n, names); report-not-gate."
- **Forbidden:** that the gate works or is empty; any change to `iv_rv_max`, `otm_skew_max_volpts`, the floor or
  the side guard on this evidence alone (a gate change is S1's own pre-registration); per-name narratives; using
  the ledger as a signal; selecting rows, names or dates by outcome; re-cutting terciles after the first row.

## §9 What existing data is NOT used, and why

`gate_dualread` holds `iv_rv` per universe name per night since 2026-06-10, so O1b and O3 could be computed
backwards from June. Those outcomes already exist and the record has been read for other purposes, so they are
not blind. **[PIN] No pre-freeze row enters any read.** The retro series may be used once, before the freeze, only
to measure the autocorrelation that justifies the weekly unit, and that number is recorded in the frozen text.

## §10 Open decisions for the operator

1. Writer placement: inside the Sunday miss sweep script (proposed) vs a Monday post-L1 run. UNVERIFIED: what
   bid/ask Alpaca's chain returns on a Sunday (Friday's last quotes or empty); if empty, mids need the Monday run.
2. Symmetric exposure from the writer's own read (proposed) vs the L1 `gate_dualread` row for universe names.
3. Horizons as 4 and 13 weekly sweeps for O1/O2 (proposed) vs exact 21/63 bars (which needs extra chain pulls).
4. The binary thresholds (+3.0 vol points; 2.0×) and the guard (≥ 20 rows ∧ ≥ 8 names).
5. Whether to measure the `iv_rv` autocorrelation from the retro series before freezing (§9).
