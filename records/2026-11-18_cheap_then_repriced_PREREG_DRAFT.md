# PREREG DRAFT — Cheap-then-repriced ledger (#455), with the #453 layer scoreboard as its reporting layer

**Status: DRAFT — NOT FROZEN. Nothing here is in force.** Written 2026-11-18 on the operator's word of 2026-11-18
(STANDING_STATE, "Operator word 2026-11-18": "draft #455 (cheap-then-repriced, with #453's scoreboard folded in) …
now"). It revises `records/2026-11-10_cheap_then_repriced_PREREG_DRAFT.md` and folds in the shared-data part of
`records/2026-11-10_layer_scoreboard_PREREG_DRAFT.md` (both on draft PR #476). Every code claim was checked on `main`
at `f36f9b5`, and every count below was read from the live DB opened `?mode=ro` and the live cache read-only on
2026-11-18. **Numbers marked [PIN] are proposals.** The operator decides whether to freeze this text as
`PREREG_CHEAP_THEN_REPRICED.md`, and decides each [PIN]. Merging this file ratifies nothing.

**Measurement only.** No output reaches discovery, the council, the gate, sizing, an exit or a prompt. The report has no
write path into `config.convexity_gate`. A gate change on this evidence is #457's own pre-registration (S1).

## §0 What changed since the 11-10 draft

1. **The same-contract outcome cannot come from stored data, and now there is a measurement to show it.** The sweep
   re-selects its wing as spot moves. Where the name is structured on both nights, the same OCC contract is selected
   again on 38% of next sessions, on 6.5% 21 sessions later, and on 0.4% 63 sessions later (§3.3). So the outcome needs an explicit capture: the quotes of the
   contracts already selected.
2. **One capture serves #455, #453 and #462.** The nightly OPRA sweep already passes every universe name's full
   chain to `iv_history.term_record` (the `chain_sink`, from 2026-11-03). The proposal adds two fields to that record.
   No new API call, no migration, no new timer, and no change to the Sunday miss sweep (§4.1).
3. **Universe cohort only [PIN].** The 11-10 draft added the sealed weekly market sample. It brings its own
   Sunday-quote problem and its own capture, and on 11-15 it had 2 not-cheap rows of 30, so it does not fix the
   scarcity of not-cheap rows (§3.5).
4. **A pre-stated #454 split** (RV252-dependent passes vs the rest) joins the tercile contrast (§5).
5. **The mark multiple is the primary outcome, not the IV change.** The pooled `iv_rv` series mean-reverts strongly
   (lag-63 r = 0.19; §3.4). A cheapest-tercile rise in IV is expected from regression to the mean alone, so an IV
   contrast cannot show "repricing on a trend change". The mark multiple is what the book is paid on, and mean
   reversion pays the holder too (§6).
6. **No ledger file and no writer.** The unit rows are derived at read time from two persisted, append-by-date
   inputs (`gate_dualread` and the term record; §4.3).
7. **#453 folds in as the reporting layer, where its data is shared** (§8). The null-book gate read (shadow − 3A) has
   had no 3A-only position since 09-01 (§3.6), so at interim the ledger is the only gate-layer read that can fill.

## §1 The question

At a weekly unit date t, read the gate of record on every universe name. At t + h, read the same contract and the
same underlying. Are rows that read cheapest at t followed by a larger mark multiple on that contract than the other
rows? The operator's thesis (PREREG_THEMATIC_CONVEXITY §1, amendment 2026-06-01) is that the far wing is mispriced
"if an anticipated trend changes". This ledger tests the weaker, measurable part: does cheap-at-t predict that the
wing pays more over 21–63 sessions. It cannot attribute a payoff to a trend change (§10).

## §2 What is stored today (verified on `main` and the live DB)

| Needed | Where it is | Usable? |
|---|---|---|
| `structured`, `iv_rv`, `otm_skew`, `cheap`, wing OCC symbol, per universe name per L1 | `gate_dualread`, `feed='opra'`, `source='sweep'` (`gate_dualread.sweep_universe` → `record_arm`; migration 0014). Append-only, full float precision | Yes. 111 sweep dates, 2026-06-10 → 11-17 |
| Spot and the RV252 the gate used, per name per L1 | The term record `iv_term_snapshot` (`iv_history.term_record`): `spot` and `rv` are the sweep's own values (the sink closes over the same `rv`, `spot`) | Yes, from 2026-11-03 (11 sessions) |
| ATM IV and wing IV at t | Not stored, but exactly recoverable from 11-03: `atm_iv = iv_rv × rv` and `wing_iv = atm_iv + otm_skew/100` (`convexity_gate.is_cheap_convexity`) | Yes from 11-03; before that only with RV recomputed from bars (UNVERIFIED match) |
| RV63 and RV21 at t (the #454 split) | Not stored. `gate_audit` recomputes them from the bars cache, which misses non-sentinel names between Sunday L0 refreshes (#454 record, "From 11-09") | Needs capture (§4.1) |
| Bid / ask of the selected wing at t | Nowhere. `Contract.bid/ask` exist in the sweep's chain and are dropped. `option_chain_snapshot` is entry-path only (7 names, 10 records, the last 11-13) and stores IV, not quotes | Needs capture |
| The same contract's bid / ask / IV at t + h | Nowhere (§3.3) | Needs capture |
| Wing IV per active sentinel | `cheapness_watch` (`wing_iv`, `atm_iv`, `rv`, `contract_symbol`; 38–40 names a night). Its wing follows the sentinel's direction and matched the sweep's wing in 115 of the 241 same-run pairs since 11-05 where the watch selected a contract (`contract_symbol IS NOT NULL`, which is also every pair with a `wing_iv`); 115 of 340 pairs in all | Not the gate-of-record wing |
| A held real position's nightly mark | `held_reads.mark_multiple` (§10.13), from 11-16 (8 rows) | Real book only |
| Underlying closes | Alpaca bars and the PIT cache | Yes |

## §3 What was measured read-only on 2026-11-18

All from `gate_dualread` (the last OPRA sweep row per name per date), the term-record files and `ledger.csv`
(aggregate counts only). The queries are in §12.

### 3.1 Coverage
- 111 sweep dates from 06-10 to 11-17. One NYSE session has no sweep (06-22), and no date has two sweep runs.
- Term records: 11 sessions (11-03 → 11-17), 49–50 names each, `rv` present on all, 528 KB in all (≈ 48 KB a night).

### 3.2 Reads per night under the 15% floor (11-05 → 11-17, 9 sessions)

| | Per night |
|---|---|
| Names swept | 49–50 |
| Structured | 33–36 |
| Gate-cheap | 31–35 |
| Structured, not cheap | 1–2 (2 distinct names in 9 sessions: one on 9 nights, one on 2) |
| Structured with no `iv_rv` | 0 |

Since 10-01 (34 sessions): 39 not-cheap name-days from 5 names, one of them 25. **A gate-cheap vs not-cheap cell with
≥ 8 distinct names cannot fill under the current regime**, at any horizon.

### 3.3 Wing persistence (the same OCC contract re-selected; pooled, 06-10 → 11-17)

Primary: the name is structured at both t and t + lag. The note column keeps the looser denominator: structured at
t, any row at t + lag, where an unstructured t + lag counts as not the same wing.

| Lag (sessions) | Pairs, both structured | Same wing | Note: pairs, t structured only | Same wing |
|---|---|---|---|---|
| 1 | 3,872 | 38.2% | 3,965 | 37.3% |
| 5 | 3,601 | 22.0% | 3,830 | 20.7% |
| 21 | 2,583 | 6.5% | 3,232 | 5.2% |
| 42 | 1,899 | 1.8% | 2,356 | 1.4% |
| 63 | 1,443 | 0.4% | 1,614 | 0.4% |

`select_structure` takes the strike nearest `spot × (1 ± 0.25)`, so a few percent of spot moves the strike. The
VRT wing changed strike on 8 of 10 nights from 11-03 to 11-17. Distinct wings selected per name: median 7 (max 16)
over the last 21 sessions, and median 12 (max 32) over the last 63.

### 3.4 Persistence of `iv_rv` (pooled Pearson r between t and t + lag, same name)

| Lag | 1 | 5 | 21 | 42 | 63 |
|---|---|---|---|---|---|
| r | 0.89 | 0.73 | 0.47 | 0.31 | 0.19 |

These are pooled over all rows and were **not split by cheapness or by tercile** (§9). Two consequences:
- Weekly rows are still dependent (r = 0.73 at lag 5), so inference is name-blocked (§7).
- `iv_rv` mean-reverts strongly. Any low-`iv_rv` group will show a rise toward the mean.

### 3.5 The weekly market sample (aggregate counts from `records/miss_baserate/ledger.csv`)
On 11-15: market 150 names, 30 structured, 28 cheap; universe 49, 30 structured, 28 cheap. Earlier the market sample
had more not-cheap rows (10-04: 74 cheap of 99 structured), but the side guard (11-01) and the floor (11-08) cut its
structured count from 124 to 30.

### 3.6 Positions the capture would also mark
- Open on 11-17: real 4, shadow 45, 3A (`union_nogate`) 45, 3B (`basket_nogate`) 43. Every one is on a name the
  nightly sweep reads, except ATKR (delisted).
- New null-book entries by month (shadow, 3A, 3B):

  | Month | Shadow | 3A | 3B |
  |---|---|---|---|
  | Sep | 4 | 4 | 4 |
  | Oct | 2 | 2 | 2 |
  | Nov (to 11-17) | 1 | 1 | 3 |

- 3A positions opened since 09-01 with no shadow twin (same symbol and direction within 7 days): **0 of 7**.

## §4 Design [PIN throughout]

### 4.1 The capture (shared with #462 and the #453 rows)
In `gate_dualread.sweep_universe`, the term record gains two fields. It is written once per name per night by the
existing sink. The record is persisted after the OPRA arm's gate read, not before it, so that tonight's wing is
known:
- **`rv63`, `rv21`:** `realized_vol(closes, window=63/21)` on the same closes the sweep already holds
  (`provider.closes(s, window=300)`).
- **`quotes`:** `{occ_symbol: [bid, ask, iv]}` from tonight's chain for the **tracked set**:
  - tonight's selected wing;
  - every wing the sweep selected for this name on a unit date in the last 70 sessions **[PIN]**;
  - the contract of every open position on this name in the real, shadow, 3A and 3B books (both legs of a vertical).

  A tracked contract missing from the chain is stored as `null` (delisted, expired, or not returned), never dropped.
  - **Size:** at most 14 unit-date wings plus about 3 position contracts per name. About 49 × 17 ≈ 830 quotes a
    night, under 50 KB.

The capture is telemetry: no stamp moves, so it is exempt from boundary B and can land on any day. It is skipped in
demo. **Cost:** no extra chain or bar fetch, no LLM call, no migration. It needs one read of `gate_dualread` and the
four position tables per sweep, to build the tracked set.

**Build requirements (part of the pin):**
- **Fail-soft, including the tracked-set build.** The tracked-set read (`gate_dualread` and the four position
  tables, inside `sweep_universe`), the `rv63`/`rv21` computation and the record write all sit inside the same
  `try/except` as today's sink. A read error, an empty result or a malformed row is logged and leaves the record
  without the new fields. It can never change, delay or skip the gate read or the `gate_dualread` row.
- **Write order.** Today the sink persists the term record before `select_structure` runs; the proposal persists it
  after the OPRA arm's gate read. The build PR checks that no test or consumer depends on the old order (the
  `iv_history` panel, `persist_term_record`'s same-day replace, the sweep's `term_ok` count, the `gate_dualread`
  tests), and says so in its description.

### 4.2 Unit, cohort, first row
- **Unit:** one row per universe name per ISO week. The unit date is that week's first council-L1 sweep (usually
  Monday). Exposure comes from that run's OPRA sweep row and that night's term record.
- **Cohort:** `config.universe.themes` at the unit date (49 names today). The market sample stays the miss
  ledger's alone.
- **First row:** the first unit date after the capture is live **[PIN: as soon as it deploys]**.
  - The 40% maximum moneyness lands at 12-07 (#504). Rows whose wing is more than 40% OTM at t are excluded from every
    read, before and after 12-07, so the pooled rows match the post-12-07 frame. Each row also carries its run's
    `frame_version`.
  - Alternative: first row Mon 12-07, at the cost of 2–3 weeks (§11, decision 3).
- **Direction:** the sweep's own momentum side (sign of `close[-22]/close[-253] − 1`, bullish if unknown), as stored
  by the wing's kind.

### 4.3 No ledger file
Unit rows are a pure function of `gate_dualread` (append-only) and the term records (one per name per date; a same-day
re-run replaces that day's record, and the PIT write is atomic). The report derives them on each read. No row is
stored twice, so nothing can drift. Per-name values are never printed (§10), so no sealing is needed. This departs
from the issue's "sealed, append-only ledger", because the only sealed cohort, the market sample, is out (§0.3).

## §5 Exposure splits at t (stated before any row)

- **E1 (primary): the cheapest `iv_rv` tercile vs the rest.** Within each unit date, over structured rows with a
  non-null `iv_rv`. About 11 rows a tercile a week; a tercile fills by construction.
- **E2 (the #454 split): among gate-cheap rows, RV252-dependent vs the rest.**
  - "RV252-dependent" means `atm_iv / rv63 > iv_rv_max` (1.2): the row passes on the 252-day window and would fail on
    the 63-day one. This is the `gate_audit` definition.
  - #454 measured 15.7% of passes dependent (09-22 → 11-06), so about 5 rows a week.
  - The concentration is a known risk. The #454 dependent days clustered in six names (PL, NEE, MOS, FLNC, BWXT,
    AMSC), so the ≥ 8-name guard may hold this cell back longer than its row count suggests.
  - Rows with no `rv63` are counted and excluded.
- **E3: gate-cheap vs not-cheap.** Counts only. Expected never to fill (§3.2). It prints `never filled by <date>`,
  which is itself a finding: the gate seldom says no on this universe. It is never a reason to change `iv_rv_max`.

## §6 Outcomes at h ∈ {21, 42, 63} sweep sessions [PIN]

Each h counts sweep sessions after t, read off the nightly capture. h = 42 is added so the horizons match #453's
30/60/90 calendar days (≈ 21/42/63 sessions).

- **O1 (primary): the same contract's mid multiple,** `mid(t+h) / mid(t)`.
  - Mid = (bid + ask)/2, with both sides > 0.
  - Otherwise the row is `unquoted` at that h. Unquoted rows are counted, and the statistic is printed twice:
    unquoted excluded, and unquoted set to 0 (the worst case).
  - **Companion: the realizable multiple** `bid(t+h) / ask(t)`, printed beside O1, never instead of it.
- **O2: the same contract's IV change,** in vol points.
- **O3: the underlying's directional return** over h sessions, from the stored spots. It is raw for bullish rows and
  negated for bearish ones. A terminated series resolves at its last bar, as in
  `sentinel_scoring.reference_return_from_bars`.
- **O4: Δ`iv_rv`** of the name (whatever wing it then selects). Reported only. It moves with RV, so it is not a
  repricing measure.
- **Binary companions:** `paid` = O1 ≥ 2.0 **[PIN]**; `repriced` = O2 ≥ +3.0 vol points **[PIN]**.
- **Why O1 leads.**
  - §3.4's mean reversion means a cheapest-tercile rise in IV (O2, O4) is expected whatever the thesis.
  - O1 is what the book is paid on, and it already includes any IV reversion, the underlying's move and theta.
  - The read can say "the cheapest tercile's wings paid more (or less)". It cannot say why.
- **Survivorship:** a row is never dropped for lack of a later quote. A delisted or acquired name stays in its unit
  week; O3 resolves through the terminal guard; O1 and O2 are `unquoted (terminated)`, counted separately, and set to
  0 in the worst-case O1 column.

## §7 Contrasts, inference, minimum n [PIN]

- **Within cohort, per unit date, then pooled across dates.** E1 first, then E2, then the E3 counts.
- **Continuous outcomes:**
  - The statistic is the difference in medians, with a **name-blocked bootstrap** 95% CI: resample names with
    replacement, 2,000 iterations, seed 0.
  - The Mann–Whitney U is printed beside it, labelled "rows overlap; not independent".
- **Binary outcomes:**
  - The name-blocked CI on the difference in proportions.
  - The two-proportion z (`miss_baserate.two_proportion_z`) is printed with the same label.
- **Small-n guard:** a cell needs ≥ 20 matured rows and ≥ 8 distinct names. Below that it prints `n<20` (the miss
  ledger's `MIN_CELL_N` wording), with no median and no rate.
- **One first read per horizon, for every cell at once.**
  - The first read is set by the slowest cell expected to fill, E2: about 5 rows a week against the 20-row guard,
    so about four unit weeks. E1's cheapest tercile would pass the guard after about two weeks (≈ 11 rows a week),
    but it is **not** read earlier. Each horizon then has one pinned look, and no cell runs on a schedule of its own.
  - A cell still under the guard on that date prints `n<20`. Later prints add rows and are labelled re-prints of
    the same pinned look, never new looks.
- **Read dates.**
  - If rows start Mon 11-23: the fourth unit week (12-14) matures at h = 21 on 2027-01-14, at h = 42 on 02-16 and at
    h = 63 on 03-17 (NYSE calendar via `nyse_calendar`, assuming no skipped sweep).
  - The first reads are the Sundays after those dates **[PIN]**: 2027-01-17, 02-21 and 03-21.
  - If rows start 12-07, add two weeks.
  - **No outcome read is possible by the 12-18 §10.12 look**, whatever the start date. The roadmap says #457 is
    "decided after the §10.12 look (12-18) with #455 data". By 12-18, #455 can give only exposure-side counts (the E1
    cut points, the E2 share, E3's emptiness), not outcomes.

## §8 The #453 scoreboard, folded in as the reporting layer

One weekly page, report-not-gate, in the FBN §5 stance: no gap verdict, and `null_hierarchy` keeps computing none.
Each row is printed only where the data is shared with §4.1.

| Layer | Read | Shares the capture? | At interim |
|---|---|---|---|
| **Gate (universe scale)** | E1, E2 and E3 of this ledger at 21/42/63 | Yes; this ledger | The only gate read that fills |
| **Gate (null books)** | shadow − 3A, the matched / 3A-only strata (11-10 #453 draft §3.2) | Yes: position contracts are tracked | 3A-only is 0 of 7 since 09-01 (§3.6), so counts only, `read_layer.ACCRUING` below `FLOOR_N = 10` ∧ `FLOOR_CLUSTERS = 3` |
| **Instrument** | Each position's O1 within terciles of its own O3 (the linear twin, 11-10 #453 draft §3.4); descriptive only, never options vs shares | Yes: spot and quotes | Counts until the floor |
| **Council** (real − shadow) | — | Yes, but RATIFIED Pin 2 (2026-07-14) forbids an interim re-read of the small real-book sample | n and "accruing — Pin 2" only |
| **Entry path** (backfill vs above-floor) | — | Same as the council row | n only |
| **Universe vs market** | The miss ledger's interim horizons (11-10 #453 draft §3.1) | **No.** It is the miss ledger's own data, a PREREG_MISS_BASERATE amendment | Not in this prereg; stays with #453 ("later" in the 11-12 order) |

- **The position rows.** Interim marks exist only for positions opened after the capture starts, at about 1–3 a month
  per book (§3.6), so they will print counts for months. They are kept because they cost nothing once the contracts
  are tracked.
- **The book cut.** Rows are printed in-frame (`structure.OUTSIDE_FRAME_SQL` excluded) and with-legacy beside it.
- **Freezing them.** Freezing the null-book rows needs a dated cross-reference in PREREG_FIXED_BASKET_NULL §5,
  because it owns that layer. One sentence pointing here is enough; it changes no FBN read.

## §9 What was looked at before freezing (blindness)

- **Computed for this draft:**
  - per-night counts (§3.2);
  - wing persistence and `iv_rv` autocorrelation, pooled (§3.3–3.4);
  - term-record coverage;
  - aggregate miss-ledger counts;
  - position counts.
- **Not computed:** no outcome was split by exposure. No tercile, no E2 class and no cheap flag was joined to any later
  value.
- **Already public before this draft:** #454 published pooled monthly medians of `iv_rv` and the per-name RV252
  dependence. These are exposure-side only.
- **No pre-freeze row enters any read.** `gate_dualread` would allow a retro O3 and O4 from June, but those values are
  not blind.

## §10 Allowed and forbidden claims

- **Allowed:** "At h = 63, rows in the cheapest `iv_rv` tercile had a median same-contract mid multiple of X vs Y for
  the rest (name-blocked CI a–b; n rows, k names; unquoted excluded / as 0); report-not-gate."
- **Forbidden:**
  - that the gate works, or that it is empty;
  - that a payoff came from a trend change;
  - any change to `iv_rv_max`, `otm_skew_max_volpts`, the floors or the side guard on this evidence alone;
  - per-name values or narratives in any output;
  - using a row as a signal;
  - choosing rows, names or dates by outcome;
  - re-cutting terciles or E2 after the first row.

## §11 Decisions for the operator

| # | Decision | Recommendation |
|---|---|---|
| 1 | Capture: extend the nightly term record with `rv63`/`rv21` and the tracked-contract `quotes` (§4.1), versus a separate Sunday writer in the miss sweep (11-10 draft) | **Extend the term record.** No extra fetch, exact h, weekday quotes, and it serves #462 and the #453 rows |
| 2 | Cohort: universe only, versus adding the sealed market sample | **Universe only.** The market sample needs its own capture and Sunday quotes, and would not fill E3 (§3.5) |
| 3 | First row: as soon as the capture deploys, wings over 40% OTM excluded, versus Mon 12-07 | **As soon as it deploys.** About 2 weeks earlier on every read date |
| 4 | Primary outcome: the mid multiple O1 (realizable `bid/ask` beside it), with the IV change O2 secondary, given §3.4's mean reversion | **Adopt** |
| 5 | Exposure splits: E1 primary, E2 (RV63 > 1.2 among passes) secondary, E3 counts only | **Adopt.** E2 is the #454 question asked forward |
| 6 | Horizons 21/42/63 sessions; guard ≥ 20 rows ∧ ≥ 8 names; `paid` ≥ 2.0×, `repriced` ≥ +3.0 vp | **Adopt** as written |
| 7 | No ledger file: unit rows derived at read time, aggregate-only output, no sealing | **Adopt** |
| 8 | #453 fold: gate (both scales) and instrument rows on this capture; council and entry path as counts under Pin 2; universe vs market stays with #453 | **Adopt.** Add the one-line FBN §5 cross-reference at freeze |
| 9 | #457 timing: the roadmap reads #457 "with #455 data" after 12-18; no outcome exists by then | **Say so in the 12-18 look**: #455 then supplies exposure counts only. The first outcome read is 2027-01-17 at the earliest |

## §12 The read-only queries behind §3

Every query opened `sqlite3.connect('file:/home/rozavala/dramatic_options/data/dramatic_options.db?mode=ro', uri=True)`
from Python; the cache files were read with `json.load`.

- **Rows.** `SELECT substr(evaluated_at,1,10), upper(symbol), structured, iv_rv, otm_skew, cheap, wing, run_id FROM
  gate_dualread WHERE feed='opra' AND source='sweep' ORDER BY id`, keeping the last row per name per date. Per-night
  counts, wing persistence (same `wing` at date index i and i + lag; `structured = 1` at both, or at i only for the note column) and the pooled Pearson r of `iv_rv` at i and
  i + lag all come from these rows.
- **Missing sweeps.** `nyse_calendar.is_trading_day` over 06-10 → 11-17, against the distinct sweep dates.
- **The term records.** `data/cache/iv_term_snapshot/*.json`: records per date, `rv` present, bytes.
  `option_chain_snapshot/*.json`: files, records, last `ts`.
- **cheapness_watch.** `SELECT substr(as_of,1,10), count(*), sum(wing_iv IS NOT NULL) … GROUP BY 1`, and its join to
  the sweep on `run_id` and `symbol` (contract match).
- **Positions.** `SELECT symbol, count(*) FROM {convexity,shadow,fixed_basket}_positions WHERE status IN
  ('open','closing') GROUP BY symbol`, against the 11-17 swept names. Entries by month: `substr(opened_at,1,7)`.
  3A-only: same symbol and direction as a shadow position within 7 days.
- **The miss ledger.** `ledger.csv` grouped by (date, cohort, structured, gate_cheap). Counts only; no key was read
  or joined.

UNVERIFIED:
- The share of tracked far-OTM wings with both bid and ask > 0 at 15:45 ET. It is not stored anywhere today; the first
  week of capture measures it.
- That `atm_iv = iv_rv × rv` reproduces `is_cheap_convexity`'s ATM read to float precision. It is algebraically
  exact, but not checked against a stored `atm_iv`.
- The wing-strike moneyness at t for the 40% exclusion uses the term record's `spot`; the stored wing strike is in
  the OCC symbol.
