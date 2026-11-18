# 2026-11-10 — Market-wide convexity regime series: definitions (DRAFT)

**Status: DRAFT for issue #462 (X2, step 1). Merging this file ratifies nothing; nothing here is in force.** It
proposes the definitions of a once-per-day, measurement-only record of how cheap long-dated wings are across the
universe. The definitions are fixed BLIND, before any aggregate has been computed, because a later pacing rule (step
2) would be pinned from this series. Proposed numbers are marked `[PIN]`. **The operator decides:** (1) the
population, fixed reference set R vs the live universe (§2); (2) whether the five sessions since the 11-04 frame
boundary may be rebuilt from existing rows (§5); (3) the percentile window and minimum history (§5); (4) whether the
weekly market cohort shows up at all, and only as share-cheap (§3); (5) whether an index-level input is added
(§8; recommended: no).

**Measurement only.** Nothing here changes an entry, a veto, a size, an exit, the backfill quota, the council's
pack or the council's verdict of record. The record is never rendered into a council prompt (guardrail 6 is
unaffected; no council output is involved).

## 1. What exists today (read from the code)

- **The per-name gate** is `convexity_gate.is_cheap_convexity`: `iv_rv = ATM IV / trailing RV`, where the ATM peer is
  taken at the wing's own expiry and kind (`atm_iv`), and `otm_skew = (wing IV − ATM IV) × 100`. It is cheap when
  `iv_rv ≤ 1.2` and skew ≤ 10 vol points, and fails closed on any missing input. It judges each name on its own.
- **`dashboard_data.market_context` does NOT compute a latest-run distribution, contrary to the issue.** It runs
  `SELECT iv_rv FROM convexity_eval WHERE iv_rv IS NOT NULL` (and the same for `otm_skew`) with no run filter.
  `convexity_eval` is the append-only survivorship log (`state.record_convexity_eval`; migration 0003). So the
  "universe" numbers are p50/p90/max (not quartiles) pooled over every real-book gate evaluation since June. That
  covers only names the council sent to the gates, not the universe. It is also read: `dashboard_web/api/snapshot.py`
  ships it as `market_ctx`, and `dashboard_web/ui/src/data/adapter.ts` displays `universe_iv_rv.p50` and
  `universe_otm_skew.p50`. This draft leaves it untouched. Re-labelling that card is a separate fix, which I flag here
  and do not propose.
- **The universe sweep** is `gate_dualread.sweep_universe`, called from `orchestrator.py` (the L1 path) after
  `run_paper_cycle`, only when not in demo. It sweeps every name in `config.universe.themes` (`_scan_universe`). The
  orchestrator passes no `skip`, so inline-evaluated names are swept too. Each name gets one OPRA row and one
  INDICATIVE row in `gate_dualread` (`state.record_gate_dualread`, append-only), with `structured`, `iv_rv`,
  `otm_skew`, `cheap`, `wing` and a classified error `note`.
  - **Wing side:** the sweep picks it from 12-1 momentum (`close[-22]/close[-253] − 1`, bullish if unknown), not from
    any thesis.
  - **"Nightly":** this is the L1 timer, Mon–Fri 15:45 ET (`scripts/systemd/dramatic-options-l1.timer`). The sweep is
    skipped when entries are not allowed, and when the market has closed by the time the council finishes. A weekday
    can therefore have no sweep.
- **Per-name history already exists.** `iv_history.py` calls the OPRA sweep arm "the IV baseline of record since
  2026-06-10" (`gate_history` takes the last OPRA read per name per date). Since 2026-11-03 the sweep's
  `chain_sink` has also written the compact `iv_term_snapshot` record (`iv_history.term_record`): for each expiry from
  30 to 550 days, the ATM call and put IV and the 25%-OTM call and put IV. Only one record per name per calendar day
  is kept, and a same-day re-run replaces it (`persist_term_record`). `term_slope_volpts` gives the far ATM minus the
  near ATM, in vol points. `MIN_PCTILE_SESSIONS = 120`. **What is missing is only the cross-sectional aggregate and
  its history.** No universe-level record is written anywhere.

## 2. Population and the membership-drift problem

**The universe changes.** ATKR was removed on 2026-11-09 (`records/2026-11-09_atkr_removal.md`); it returned
`structured = 0` on both feeds from run 1730 (10-19) onward. Windows add names: window #11 took the universe from 48
to 50 (`records/2026-10-19_window11_cf_bwxt.md`). Admission requires an in-band structure read
(PREREG_UNIVERSE_CURATION §2, §11, §12), so additions are selected partly on option state. How many names are
structured also swings with listing cycles (STANDING_STATE: "the 11-23 cliff now costs 7 names (→ ~27)"). So a median
over "whoever is structured tonight" moves with membership, not only with prices.

**Proposal (recommended): a fixed reference set R plus a live companion.**
- **R:** R is the 49 names in `config.universe.themes` on the adoption date `[PIN]`. A name that dies stays in R and
  simply stops counting. R is never topped up. Re-pinning R takes a dated amendment, and a re-pin starts a new
  segment whose percentile history restarts.
- **The R statistics** are the series of record, and the only ones a step-2 rule could later be pinned from.
- **Coverage guard:** a night's R statistics print only if at least 60% of R `[PIN]` (30 of 49) has a structured OPRA
  sweep read that night. Below that the record is written with `coverage_low = true`, displayed greyed, and excluded
  from percentile histories. The 11-23 cliff (~27 structured) would trip this guard, by design: a listing cycle is
  not a regime.
- **Live companion:** the same statistics over the current universe, with `n` and `n_structured`; display-only.

**Considered and not recommended: a matched-names delta** (each night's change in the median over names read on
both nights, chained). It handles additions and deaths cleanly. But a chained level accumulates noise without
limit, a percentile of a chained index has no fixed reference, and the result is harder to state than "R's median".
R loses breadth as names die, which the coverage guard makes visible; the delta hides its own drift.

**Rows:** `gate_dualread` with `feed = 'opra'`, `source = 'sweep'` and `run_id` = that L1. Inline rows are excluded:
they carry the council's direction, not the sweep's momentum side.

## 3. The weekly market cohort (PREREG_MISS_BASERATE)

- **What it is:** a manual Sunday probe (`scripts/probe_miss_baserate.py sweep`, "run from the WORKTREE on Sundays").
  No systemd unit runs it (grep of `scripts/systemd/` finds none). It reads Friday-close chains, while the L1 reads at
  15:45 ET, so it never shares a sweep day with the L1.
- **What it keeps:** its ledger has only `date, key, cohort, direction, structured, gate_cheap, entry_close, feed`
  (`miss_baserate.LEDGER_COLUMNS`). No `iv_rv` or skew is stored.
- **What binds it:** §3 seals each per-name verdict, and §5 says no output of that sweep "enters discovery, the
  framer, the council, the gate, or sizing".

**Proposal:** at display time, compute per sweep date and per cohort the share structured and the share gate-cheap
among structured rows, from `ledger.csv` directly. This uses aggregates only: no key is joined to the denominator and
no per-row value is printed, so the seal holds. The probe and its ledger columns stay unchanged (no iv_rv
medians), because adding a column would amend a frozen pre-reg for a display. **Pinned:** the market leg is
display-only, permanently. Under §5 it can never feed a step-2 rule without a dated amendment to PREREG_MISS_BASERATE
itself. The operator may instead drop the market leg entirely.

## 4. The statistics (per L1 date, over R)

- **iv_rv:** the median and quartiles (p25, p50, p75) of the sweep's `iv_rv` over structured names in R.
- **Wing skew:** the median and quartiles of the sweep's `otm_skew`, reported **separately for call wings and put
  wings** `[PIN]`, each with its own `n`. The sweep chooses the side by momentum, so in a broad sell-off many names
  flip to puts, and put wings carry structural skew. A pooled skew median would then move on composition alone. The
  share of R on the put side is recorded alongside.
- **Term slope:** the median and quartiles of `iv_history.term_slope_volpts` over the names in R with an
  `iv_term_snapshot` record for that ET date.
- **Share gate-cheap:** `cheap = 1` divided by `structured = 1` among R, with both counts. "Cheap" is the gate of
  record's verdict under the then-live `convexity_gate` (15% floor, side guard). Each record stamps `frame_version`,
  and a frame boundary starts a new segment.
- Quantiles by `numpy.percentile` (linear interpolation), rounded to 4 decimals.

## 5. Percentiles: history and minimum

- **What is ranked:** each statistic is ranked within its own history, using `iv_history.pct_rank` (share of the
  history at or below tonight's value).
- **History:** in-segment, `coverage_low` records excluded, expanding until 250 records and then trailing 250 `[PIN]`.
- **Minimum:** none prints before 120 in-segment records `[PIN]` (`MIN_PCTILE_SESSIONS`); else "accruing k of 120".
- **Backfill (operator decision):** the OPRA sweep rows let the series be rebuilt back to June. **Recommended: do not
  rebuild across a frame boundary.** The side guard (09-30) and the 15% floor (11-04) both changed which wing is
  selected, so pre-11-04 skew and share-cheap are another regime. If the operator agrees, the writer may rebuild only
  the in-segment L1 dates since the 11-04 boundary (`frame-880e893e1660`), at most about five records. It applies
  these pinned definitions mechanically and no one inspects the output before the pins merge. Anything older may be
  shown as a separately labelled "reconstructed" line that never counts toward 120. With term slope accruing only
  from 11-03, the first percentiles are about 24 weeks of L1s away (≈ late April 2027; arithmetic, not verified
  against holidays).

## 6. Storage and the once-per-day rule

- **Where/when:** one record per ET date in the PointInTimeCache, source `convexity_regime`, key `universe` `[PIN]`,
  as in `capex_cycle.record_daily`; written after `sweep_universe` returns, in its fail-soft `try`, skipped in demo.
- **Same-day rule:** the existing writers differ. `capex_cycle.record_daily` keeps the first record (a same-day
  re-run is skipped); `attention.record_daily` merges; `iv_history.persist_term_record` replaces. **Proposal:** the
  first record with `coverage_low = false` wins. A `coverage_low` record may be replaced by a later complete one the
  same day, and a complete record is never replaced. A manual re-run therefore cannot overwrite the record of the
  timer run.
- **Fields:** `ts`, `run_id`, `frame_version`, `R_id` (hash of sorted R), the §4 statistics, counts, `coverage_low`.

## 7. Display

One small card under Edge → Telemetry. It shows tonight's R medians and quartiles with `n`; the share gate-cheap;
each percentile, or "accruing k of 120"; a sparkline of each median; and the live-universe companion and the weekly
market leg, greyed and labelled display-only. It carries no colour scale or words like "cheap regime", "deploy" or
"buy". It is never rendered into a council prompt, the gates, the backfill rank or any sizing input (to be asserted by
an import-graph test, as for `iv_history`).

## 8. What the series cannot tell us

- **No index-level vol is ingested.** A grep for VIX, VIXY, VXX and VVIX in `*.py` and `*.json` finds nothing. SPY is
  configured only as `universe.benchmarks.broad` (relative strength in discovery) and is not in the themes, so the
  sweep never reads its chain.
- **Narrow:** a 49-name correlated thematic universe, not the market.
- **The denominator lags:** RV is a trailing 252-day window, so after a vol spike RV stays high for a year and `iv_rv`
  reads "cheap" mechanically while IV normalises.
- **It is a snapshot** (one 15:45 ET read) and says nothing about payoffs: whether cheap-everywhere months pay is
  an outcome question this record must not be tuned to.
- **Index input — recommended: do not add.** The one free, reachable input is SPY's OPRA chain via the same provider
  and `term_record`; but index vol is mostly a correlation price, not single-name wing cost, and is a new input.

## 9. Step 2 is out of scope

A pacing rule on the backfill quota (PREREG_THEMATIC_CONVEXITY §5, amendment 2026-11-03: `per_week = 1`, top 3
candidates, stop rule) would need its own dated pre-registration, written before any look at outcomes. It would have
to settle the following:
- **The rule itself:** which single R statistic (one, not a menu); the threshold as a percentile of this series
  (e.g. the lowest tercile), fixed from the series' own distribution; hysteresis or minimum dwell; behaviour when
  `coverage_low` or no percentile exists (fail closed to today's quota).
- **History and timing:** ≥ 120 in-segment records before it binds; written after entries, so only the prior L1's
  record could be read.
- **Frame:** a dated `convexity_book.backfill` edit, which moves `frame_version` (`config_loader.frame_version` hashes
  `convexity_book`).
- **Interactions:** with the stop rule and the 1% / 2% / 10% caps, which keep disposing.

Step 1 adds no key inside the four frame-hashed blocks: no `frame_version` or `model_mix` stamp moves.

UNVERIFIED: how many weekdays since 06-10 lack a sweep (no production DB here); that the live `config.universe`
equals this checkout's 49 names on the adoption date.
