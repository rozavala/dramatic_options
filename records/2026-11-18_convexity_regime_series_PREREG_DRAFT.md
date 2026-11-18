# PREREG DRAFT — Market-wide convexity regime series: definitions (#462, X2 step 1)

**Status: DRAFT — NOT FROZEN. Nothing here is in force.** Written 2026-11-18 on the operator's word of 2026-11-18
(STANDING_STATE, "Operator word 2026-11-18": "draft … #462 (the regime series) now"). It revises
`records/2026-11-10_convexity_regime_series_DRAFT.md` (draft PR #476). Every code claim was checked on `main` at
`f36f9b5`, and every count was read from the live DB (`?mode=ro`) and the live cache, read-only, on 2026-11-18.
**Numbers marked [PIN] are proposals.** Merging this file ratifies nothing.

**Measurement only.** Step 1 is a series and a dashboard card. Nothing here changes an entry, a veto, a size, an exit,
the backfill quota or a council input. Nothing is rendered into a prompt. Step 2 (a pacing rule on the backfill quota)
is a separate pre-registration, pinned from this series and never from outcomes (§9).

## §0 What changed since the 11-10 draft

1. **The series of record moves off the gate's own rows,** to a constant-maturity read of the nightly term record.
   - The 11-10 draft built the series from `gate_dualread`: the selected wing's `iv_rv`, skew and share cheap. Those
     depend on the gate frame, and the 11-10 draft restarted the percentile history at each frame boundary.
   - Under boundary B the gate frame can move monthly. The next move is 12-07, the 40% maximum moneyness (#504). A
     series that restarts monthly never reaches the 120 sessions a percentile needs.
   - The term record (`iv_history.term_record`, nightly from 2026-11-03) is independent of the gate frame: per expiry,
     the ATM and 25%-OTM IVs, plus spot and the gate's RV252. A 270-day constant-maturity read from it moves only
     with the market (§4).
2. **Coverage survives the tenor cliffs.**
   - A 270-day bracket exists for 48 of 49 names on every night so far. The gate is structured on only 33–36 names
     (§2.2).
   - The 11-23 cliff takes the gate to about 28 structured names, but those names keep an expiry on each side of 270
     days (§2.3).
3. **No nightly writer.** The series is derived at read time from inputs that are already persisted nightly (§6).
4. **One capture with #455.** Both read the same nightly sink. #455 adds two fields to it (`rv63`/`rv21`, and the
   tracked-contract quotes); #462 reads the existing fields plus `rv63` (§7).
5. **The weekly market leg is dropped [PIN].** It is sealed (PREREG_MISS_BASERATE §3, §5) and run on Friday-close
   chains on Sundays.
6. **Blindness has to be restated.**
   - #454 (`records/2026-11-13_gate_pass_reasons.md` §1) published the pooled monthly median of the gate's `iv_rv`
     (1.08 in June → 0.92 in October), so a gate-derived series is no longer blind.
   - The constant-maturity statistics below have not been aggregated by anyone. This draft computed coverage only
     (§2), no level.

## §1 What exists today (verified)

- **The nightly sweep.** `gate_dualread.sweep_universe` runs on every universe name after the L1 entries
  (`orchestrator.py`; not in demo).
  - Per name it fetches the OPRA chain once. It passes the chain to the `chain_sink`, which writes
    `iv_history.term_record` through `persist_term_record` (one record per name per day; a same-day re-run replaces
    it; the PIT cache write is atomic, `tmp.replace`).
  - It then records the gate read in `gate_dualread`.
- **The term record.** `{ts, symbol, spot, rv, expiries: [{expiry, dte, atm_c, atm_p, otm_c, otm_p}]}` for expiries
  of 30–550 days.
  - `atm_*` is the IV at the strike nearest spot; `otm_c`/`otm_p` are at the strike nearest `spot × 1.25` and
    `spot × 0.75`.
  - `rv` is the sweep's own RV252 (the sink closes over it).
  - `iv_history.term_slope_volpts` gives the far ATM minus the near ATM; `MIN_PCTILE_SESSIONS = 120`;
    `pct_rank` exists.
- **`dashboard_data.market_context` still mislabels its numbers, as the 11-10 draft found.** Its "universe" numbers
  are p50/p90/max pooled over every `convexity_eval` row since June. Those are real-book gate evaluations, not the
  universe, and not a single night. The card reads `universe_iv_rv.p50`. This draft does not change it. The
  relabelling is a separate small fix (decision 7).
- **No index-level vol input.** No `VIX`/`VXX`/`VIXY` anywhere in `*.py` or `*.json`. SPY is only
  `universe.benchmarks.broad`, and the sweep never reads its chain.

## §2 What was measured read-only on 2026-11-18

### 2.1 The sweep
111 sweep dates from 06-10 to 11-17. One NYSE session has no sweep (06-22), and no date has two sweep runs.

### 2.2 Term-record coverage, by night (11-03 → 11-17)

| | Every night |
|---|---|
| Names with a record | 49–50 (50 until ATKR's removal on 11-09) |
| `rv` present | all |
| An ATM IV on both sides of 270 days (the interpolation bracket) | 48 |
| An ATM IV at an expiry of 180–365 days | 40 |
| Both 25%-OTM IVs at an expiry of 180–365 days | 40 |
| Storage | 528 KB for 11 nights (≈ 48 KB a night) |

For comparison, the gate was structured on 33–36 names a night over the same nights. Structured names never fell below
60% of those swept on any of the 111 sweep dates, so the 11-10 draft's coverage guard would not have tripped yet.

### 2.3 The 11-23 cliff
STANDING_STATE expects about 28 structured names after Mon 11-23, which is 57% of 49. A gate-based coverage guard at
60% would trip.
- The seven names losing gate structure (BWXT, FLNC, FLY, KTOS, RDW, SMR, UEC) each list May-2027 and Jan-2028 on
  their 11-17 records (KTOS also Dec-2027). After 11-23, May-2027 is about 179 days out and Jan-2028 about 424, so
  the pair still brackets 270 days and the names stay in S1.
- The cost: those seven are then interpolated across a wide gap (≈ 179 → 424 days), a noisier read than a near
  bracket.
- This holds only if no listing changes: UNVERIFIED until the 11-23 record exists.

## §3 Population [PIN]

- **R:** the universe names (`config.universe.themes`) on the adoption date (49 today), frozen.
  - A name that dies stays in R and stops counting.
  - R is never topped up.
  - A re-pin is a dated amendment and starts a new segment.
- **Live companion:** the same statistics over the current universe, display-only.
- **Coverage guard:** a night's R statistics count only if at least 70% of R **[PIN]** (35 of 49) has a usable
  270-day bracket. Below that, the night is `coverage_low`: shown greyed and excluded from percentile history.
  - The 70% here is higher than the 11-10 draft's 60%, because this coverage is higher (48 of 49) and does not swing
    with listing cycles.
- **Rows:** the term record that belongs to the night's council-L1 sweep run (the record whose date is that run's ET
  date).

## §4 The statistics, per L1 night, over R [PIN]

### S1, the series of record: constant-maturity 270-day ATM IV ÷ RV252
- **Per name:**
  - ATM IV per expiry = the mean of `atm_c` and `atm_p` (whichever exist).
  - Interpolate **total variance** (σ²·T) linearly in days between the two expiries bracketing 270 days. Take
    σ₂₇₀ = √(var₂₇₀ / 270d).
  - Divide by the record's `rv`. A name with no bracket is missing that night.
- **Across R:** p25, p50 and p75, with n.
- **Why 270 days:** the middle of the gate's 180–365 tenor window.
- **What it shares with the gate:** the cheapness concept (IV vs trailing RV252) and the RV. What it does not share is
  the wing selection, so a gate frame move does not move it.

### Companions: display, and candidates for step 2
- **S2: the term slope,** `iv_history.term_slope_volpts`. p25/p50/p75 over R.
- **S3: the 270-day 25%-OTM skew,** calls and puts separately: `otm_c − atm_c` and `otm_p − atm_p` in vol points, at
  the expiry in 180–365 days nearest 270. p50 and n per side, and the share of R whose sweep side is the put.
  - It is per side because in a sell-off names flip to puts and put wings carry structural skew. A pooled skew would
    move on composition alone.
- **S4: the constant-maturity IV level** (σ₂₇₀ itself) and **σ₂₇₀ ÷ RV63** (needs #455's `rv63`).
  - Both are here because #454 found the RV252 denominator carries an old move for about one pass in six.
  - S1 inherits that lag: after a vol spike, S1 reads "cheap" for up to a year while IV normalises.
- **S5: the gate's own share cheap and median `iv_rv`** over R, from `gate_dualread`. Display only, segmented by
  `frame_version`, and already partly unblinded (§0.6).
- **Quantiles:** `numpy.percentile` (linear), rounded to 4 decimals. Each night also carries `frame_version`, n and
  `coverage_low`.

## §5 Percentiles

- Each statistic is ranked in its own in-segment history with `iv_history.pct_rank`. `coverage_low` nights are
  excluded.
- The history expands until 250 nights, then trails 250 **[PIN]**.
- **Minimum:** nothing prints before 120 in-segment nights (`MIN_PCTILE_SESSIONS`); until then it reads "accruing k of
  120".
- **What segments S1–S4:**
  - a re-pin of R;
  - a change to `convexity_gate.rv_window_days`;
  - a change to the term record's definition. The build adds a `TERM_VERSION` constant stamped into each record for
    this, so the boundary can be read from the record itself.
  - A `frame_version` move does **not** segment them; it segments S5 only.
- **History available:** the term record starts 2026-11-03. Rebuilding S1–S4 from 11-03 is mechanical: the
  definitions are applied as pinned, and nobody inspects the output before the pins merge.
  - Nothing older exists to rebuild.
  - The 120th session from 11-03 is **2027-04-28** (NYSE calendar via `nyse_calendar`, assuming no skipped sweep;
    one skip in 111 so far).

## §6 Storage: derived at read time, no writer [PIN]

- A pure function (proposed: `iv_history.regime_series(cache, R, …)`) reads the term records and returns one row per
  night.
- The inputs are already persisted:
  - one term record per name per date;
  - an atomic write;
  - `gate_dualread` append-only, for S5.
- So the series is reproducible from them, and a second store would only be able to drift from them.
- **The known weakness:** a manual same-day sweep re-run replaces that day's term record. That night's point can then
  move, but only within the same session.
- **Alternative (the 11-10 draft's):** a nightly writer to a `convexity_regime` PIT source, where the first complete
  record of the day wins. Choose it if the operator wants the series of record frozen at write time.

## §7 Relation to #455 (one capture)

Both read the nightly OPRA sweep's chain sink and the term record it writes. The capture (described in
`records/2026-11-18_cheap_then_repriced_PREREG_DRAFT.md` §4.1) adds two fields:
- `rv63`/`rv21`, used here by S4;
- `quotes` for the tracked contracts, used by #455 only.

#462 needs none of it except `rv63`, for S4. One build PR can carry the sink change, `regime_series`, the #455
report and their tests. It is telemetry with no stamp moved, so boundary B does not hold it.

## §8 Display

- One card under Edge → Telemetry, showing:
  - tonight's S1 p25/p50/p75 with n, and its percentile or "accruing k of 120";
  - a sparkline of S1's median;
  - S2–S4 medians;
  - S5 and the live companion, greyed and labelled display-only.
- The card has no colour scale and no words like "cheap regime", "deploy" or "buy".
- An import-graph test asserts that nothing in the gates, the backfill rank, sizing or the council imports
  `regime_series`, as for `iv_history`.

## §9 Out of scope: step 2

A pacing rule on the backfill quota (PREREG_THEMATIC_CONVEXITY §5 amendment 2026-11-03: `per_week = 1`, the top 3,
the stop rule) needs its own dated pre-registration, written before any look at outcomes. It must settle:
- the one statistic it reads (one, not a menu);
- the threshold, as a percentile of this series;
- hysteresis or a minimum dwell;
- fail-closed to today's quota on `coverage_low` or when no percentile exists;
- ≥ 120 in-segment nights before it binds;
- reading only the prior L1's value.

It would be a `convexity_book.backfill` edit, so a `frame_version` move landing on a boundary-B Monday. Step 1 adds
no key to a frame-hashed block and moves no stamp.

## §10 What the series cannot tell us

- **It is narrow.** 49 correlated thematic names, not the market.
- **It is not index vol.** An index input was considered and not recommended (decision 6).
- **It is a 15:45 ET snapshot.** It says nothing about payoffs. Whether cheap-everywhere months pay is #455's kind of
  question and must not tune this series.
- **The RV252 lag** (S1). S4 is there to show it.
- **25% OTM is approximate.** The term record's "25% OTM" is the listed strike nearest 25% OTM; on sparse far
  expiries it can be several points away.

## §11 Decisions for the operator

| # | Decision | Recommendation |
|---|---|---|
| 1 | Series of record: S1, constant-maturity 270-day IV ÷ RV252 from the term record, versus the gate's own `iv_rv`/share cheap (the 11-10 draft) | **S1.** It is frame-independent, so boundary B does not reset it; it covers 48 of 49 names against the gate's 33–36; and it is still blind |
| 2 | Population: R frozen at adoption (49 names), live universe display-only; coverage guard 70% of R | **Adopt** |
| 3 | Percentiles: in-segment, expanding to 250 then trailing; minimum 120 nights; segments only on R, `rv_window_days` or `TERM_VERSION` | **Adopt.** First percentile about 2027-04-28 |
| 4 | Rebuild from the 11-03 term records, mechanically, before anyone reads a level | **Adopt.** Nothing older exists |
| 5 | Storage: derived at read time with no writer, versus a nightly first-record-wins writer | **Read time.** One store fewer; the inputs are already persisted and atomic |
| 6 | Index input (SPY's chain through the same `term_record`) | **No.** It is a new input, and index vol prices correlation, not single-name wings |
| 7 | The `market_context` mislabel (pooled `convexity_eval`, shown as "universe") | **A separate small fix**, relabelled, not removed; not part of this prereg |
| 8 | Market leg | **Drop it.** It is sealed and Sunday-only |
| 9 | Build together with #455's capture as one telemetry PR | **Yes** |

UNVERIFIED:
- That the 11-23 cliff names keep their 270-day bracket (§2.3: true on the 11-17 listings, unless a listing changes).
- That the 120th session lands on 2027-04-28: it assumes no further skipped sweep.
- How often a manual same-day sweep re-run happens. None is visible in `gate_dualread`: no date has two sweep runs.

**Read-only queries used:**
- `SELECT substr(evaluated_at,1,10), count(DISTINCT symbol), sum(structured) FROM gate_dualread WHERE feed='opra' AND
  source='sweep' GROUP BY 1` (coverage and the 60% check).
- `SELECT substr(evaluated_at,1,10) d, count(DISTINCT run_id) FROM gate_dualread WHERE source='sweep' GROUP BY d
  HAVING count(DISTINCT run_id) > 1` (re-runs: none).
- `nyse_calendar.is_trading_day` for the missing sessions and the 120-session date.
- The term-record files read with `json.load`. Per date it counted records, `rv` present, the 270-day bracket, an
  expiry in 180–365 days, and both 25%-OTM IVs there. No IV value was aggregated.
- The seven cliff names' latest term records: their listed expiries of 150 days or more (expiry dates only).
