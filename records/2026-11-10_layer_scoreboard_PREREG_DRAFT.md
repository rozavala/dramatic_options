# PREREG DRAFT — Layer scoreboard: interim mark-based reads at 30/60/90 days (amends PREREG_FIXED_BASKET_NULL §5)

**Status: DRAFT — NOT FROZEN.** Issue #453 (M1). Written 2026-11-10. Nothing reads this file and no code exists
for it. The operator decides (a) whether interim mark reads are added to the null layer at all, (b) for which
layers, given the conflict with the RATIFIED min-N pins found in §1.3, and (c) every value marked **[PIN]**.
**Numbers marked [PIN] are proposals.** On the operator's word this text becomes a dated amendment appended to
`PREREG_FIXED_BASKET_NULL.md` §5; until then nothing changes. Report-not-gate throughout: no read below changes
an entry, a veto, a size or a prompt.

## §0 What this proposes, in one paragraph

Add an INTERIM read to the null layer: for each open or closed position in each book, its **mark multiple** at
30, 60 and 90 calendar days after entry, compared across books one layer at a time. It is a mark read, not a
resolution read. It never replaces the FBN §5 tail read (p95 of realized multiples), never feeds a verdict on
the edge, and cannot be computed today for any position already past 90 days, because the system keeps no mark
history (§1.1). The proposal therefore starts with a new capture.

## §1 What the code does today (verified)

### 1.1 Marks are overwritten; there is no mark history
- `state.mark_convexity_position`, `state.mark_shadow_position` and `state.mark_fixed_basket_position` each run
  `UPDATE … SET mark = ?, marked_at = ?`. One `mark` column per row (migrations 0003/0004, 0008, 0010); every L2
  monitor pass (`monitor.monitor_positions`, `shadow_book.mark_shadow_positions`,
  `fixed_basket.mark_fixed_basket_positions`) replaces the previous value.
- No table or cache stores a position's mark by date (searched: no `mark_history`/`position_marks` anywhere).
- Consequence: a 30/60/90-day mark exists only if someone records it on that day. Every position opened before
  the capture starts loses each horizon that has already passed. Per `records/2026-07-14_min_n_pins_RATIFIED.md`,
  shadow held 30 and 3A 31 positions on 2026-07-14; all of those are past 90 days and get no interim read.
- `shares_positions` (migration 0012) is an entry log: `symbol, direction, entry_spot, entry_at`. It has no
  mark; `shares_basket.shares_return_report` computes returns from bars at report time.

### 1.2 The books do not enter the same name on the same day
- `shadow_book.run_shadow_cycle` and `fixed_basket.run_fixed_basket_3a_cycle` run in the same L1, after the real
  entries (`orchestrator.py`, the calls after the dual-read sweep), over the same `candidate_union`. Each skips a
  name already open **in its own book** (`skip_open` via `state.shadow_open_symbols` /
  `state.fixed_basket_open_symbols`). So 3A opens a name at its first structured day; shadow opens it at its first
  *cheap* day, which may be the same L1 or weeks later. When both open the same day they call `select_structure`
  on separately fetched chains, so the contract is usually, not provably, the same.
- The real book opens a name only when the council selects it (`council.wiring.council_to_themes` →
  `paper_loop`), often long after shadow opened it. `opened_at` on the real book is the **fill** time
  (`state.confirm_convexity_fill` sets `opened_at` at the fill price); on the null books it is the L1 booking time.
- 3B (`run_fixed_basket_3b_cycle`) and shares (`run_shares_basket_cycle`) run weekly (L0) over the whole basket
  with the **motion-derived** direction (`discovery.direction_of`), not the thesis direction. Shares dedups a
  name for 365 days (`shares_recent_symbols`, `dedup_days = max(horizons)`).
- A precedent pairing rule exists: `read_layer.mandate_ledger._match` matches a proposal to a shadow position on
  **symbol AND direction, opened within ±5 weekdays** (`MATCH_TD = 5`).

**Implication.** "Paired" cannot mean "the same entry in two books". A name-matched real/shadow pair compares
entry timing and contract, not the council's selection, because the shadow book holds every cheap union name.
Each contrast in §3 therefore gets its own rule.

### 1.3 Two existing records constrain this amendment
- `dashboard_data.null_hierarchy` docstring: "No gap is computed." Its note: the verdict "belongs to the
  blind/mature null layer — this is plumbing". `performance_panel` likewise shows per-book p95 + CI side by side,
  "no gap verdict".
- `records/2026-07-14_min_n_pins_RATIFIED.md`: Pin 1 — "No interim tail claims from a smaller sample; the read
  waits for the count." Pin 2 — if the real-book admissions floor (N₂ = 10 by 2027-03-02) is unmet, the
  council-marginal read is UNDERPOWERED "and there is **no interim re-reading of the small sample** in either
  direction." An interim council read (§3.3) contradicts Pin 2 as written. This draft does not override a
  ratified pin; §3.3 proposes the council row prints counts only unless the operator amends Pin 2 by name.
- The same record dates the first natural resolutions at ≈ 2026-12-25 and the expiry wall at 2027-01-15, which
  "resolves the majority of currently-open null positions by mid-January 2027". The issue's premise that the
  first resolutions land "around mid-2027" does not match the record for the null books. For the real book
  (3 open on 11-04 per the two-week look; that they are PL, FLNC and TITN is inferred from the records) it is closer to true. UNVERIFIED: the live `read_layer.resolution_calendar`
  output today (no DB in this worktree).

## §2 The new capture (a precondition, not a read)

- **[PIN] A daily mark snapshot**, append-only: one row per open position per book per trading day —
  `book, position_id, as_of (date), mark, underlying_spot, marked_at, status`. Written once a day after the last
  L2 pass (proposed: a `scripts/` probe on its own timer that reads the DB read-only and appends to its own
  table or CSV, so no loop module changes). Fail-soft: a missed day is a gap, never an imputed value.
- `underlying_spot` is recorded beside the mark because the instrument read (§3.4) needs it on the same day.
- Positions closed before a horizon need no snapshot: their realized multiple is stored at close
  (`realized_multiple` on the null books; `(total_premium + realized_pnl) / total_premium` on the real book, as
  `state.convexity_realized_multiples`).
- Reads apply only to positions whose entry date is on or after the first snapshot day **[PIN: positions opened
  ≥ the capture start; older positions are excluded from every interim read, not partially included]**.

## §3 The reads

### 3.0 Common definitions
- **Entry date d:** `opened_at` (date, ET). **Horizons:** h ∈ {30, 60, 90} calendar days; the mark used is the
  snapshot on the first trading day ≥ d + h.
- **Mark multiple:** `M_h = mark × 100 × contracts ÷ total_premium`. For a vertical the stored mark is the net
  mid (`verticals.position_mid`), so the same formula applies.
- **Closed before d + h:** `M_h` = the realized multiple, frozen at close (profit-take, time-stop, expiry).
- **Unmarked at d + h** (no quote): use the latest snapshot in the prior 5 trading days **[PIN]**; if none, the
  position is `unmarked` for that horizon — counted and printed, excluded from the statistic, never set to 0 or 1.
- **Fill realism:** print both columns of `read_layer.band` (frictionless mid; conservative at h = 0.125) since a
  mark is a mid, not an exit.
- **Statistic [PIN]:** per arm, n, median and mean `M_h`, p90, and the share with `M_h ≥ 1`. The CI is on the
  **median**, from `read_layer.cluster_blocked_ci(q = 0.5)` (cluster blocks, 2000 iterations, seed 0; 95%).
  p95 is not used at interim; it stays the resolution read's primary (FBN §5).
- **Minimum n [PIN]:** the `read_layer` floor — n ≥ 10 marked positions in each compared arm ∧ ≥ 3 clusters
  (`directional_floor`, `FLOOR_N`, `FLOOR_CLUSTERS`). Below it the cell prints `read_layer.ACCRUING` verbatim and
  no median. CI `unstable` at n_blocks < 5 is printed as such.
- **Legacy positions:** every cell is printed in-frame first (excluding `structure.OUTSIDE_FRAME_SQL` rows, the
  six tagged wrong-side positions) and with-legacy beside it, as `performance_panel` does. Rows are also split by
  `runs.frame_version` at the 15% floor boundary (`frame-880e893e1660`), because positions opened before it may be
  7–15% OTM and `OUTSIDE_FRAME_SQL` does not tag them **[PIN: split, not pooled]**.

### 3.1 Universe (curated universe vs the frozen market sample, gate-cheap rows)
There are no option positions for market names, so this read is on the **underlying's directional return** from
the miss ledger, not on marks.
- **What must be added:** `miss_baserate.HORIZONS = (63, 126, 250)` gains interim horizons **[PIN: 21 and 42
  trading bars ≈ 30 and 60 calendar days; 63 already exists ≈ 90]**, and `render` prints them. `aggregate` keys
  cells by `(cohort, h)`, so new horizons add cells and leave the existing ones unchanged.
- **Does it touch the miss ledger's frozen §4?** No. R1 is read at h = 250 and R2 is descriptive; neither cell
  changes. It does amend §3's frozen outcome list, so it is a dated append to `PREREG_MISS_BASERATE` as well,
  and that ledger's own rule ("the pinned reads (§4) are not edited after the first row") is respected.
- **Blindness problem:** rows from 2026-09-20 already have matured 21- and 42-bar outcomes; they have not been
  printed, but they exist. **[PIN] Interim horizons apply only to rows dated after the amendment's freeze.**
- **Statistic:** the +0.50 big-move threshold almost never fires at 21 bars, so the interim cell reports the
  directional-return distribution (p50, p90) per cohort among `gate_cheap = 1` rows, counts first, under the
  ledger's `MIN_CELL_N = 20` guard and its never-a-symbol rule. The regime splits at 11-01 and 11-08 (§7, §8)
  hold. Pairing: none (cohorts are disjoint by construction); unpaired, same sweep dates.

### 3.2 Gate (shadow − 3A)
- **Pairing [PIN]:** match each 3A position to a shadow position on symbol ∧ direction, opened within ±5
  weekdays (the `mandate_ledger` rule). Three strata follow:
  - **matched** — cheap at entry in both books. The paired difference should be near 0 (same name, same day,
    usually the same contract). It is printed as a **plumbing check**, not as the gate read.
  - **3A-only** — structured but not cheap at entry (the gate rejected it). This is where the gate acts.
  - **shadow-only** — booked by shadow with no 3A twin in the window (3A already held the name). Printed as a count.
- **The gate read:** `M_h` of 3A-only vs `M_h` of matched, same entry weeks, unpaired, cluster-blocked CIs side by
  side. Both arms run with the same relieved caps (FBN §4 activation addendum: `null_book_fraction = 1.0`,
  `null_cluster_fraction = 0`, `null_max_open_positions = 100`), so caps do not differ between them.
- Not censored for parse_fail (FBN §5: brain-off books never invoke the council).

### 3.3 Council (real − shadow)
- A name-matched real/shadow pair measures timing, not selection (§1.2), so it is printed only as a diagnostic.
- **Proposed comparator [PIN]:** for a real entry at d, the shadow positions open on d, each measured over the
  same window: `W_h = mark(d + h) ÷ mark(d)`. The real entry's `M_h` is ranked within that day's `W_h`
  distribution; the read is the distribution of those percentile ranks across real entries (centred near 0.5 if
  selection adds nothing over the window). Needs the snapshot of §2 on both d and d + h.
- Runs stamped `parse_fail` (and **[PIN] `provider_fail`**) in `runs.council_health` are excluded, per FBN §5.
- **Conflict:** RATIFIED Pin 2 forbids an interim re-read of the small council sample. **[PIN] Default: the
  council row prints n and "accruing — Pin 2 (2026-07-14) forbids an interim council read" and no number,** unless
  the operator amends Pin 2 by name. Real-book n is 3 positions today, so the floor is far off in any case.

### 3.4 Instrument (option books vs linear)
- `shares_positions` cannot be paired with option entries: it enters weekly, once per 365 days, on the motion
  direction. **[PIN] Linear twin instead:** for each option position, the directional underlying return over the
  same window, from its own stored `entry_spot` to the snapshot `underlying_spot` at d + h (raw for bullish,
  negated for bearish; the `sentinel_scoring.reference_return_from_bars` terminal guard if the series ends).
- FBN §5 forbids scoring an option multiple against a share return. The read is therefore descriptive only:
  median `M_h` within terciles of the linear return (how much the marks responded to the underlying's move).
  No "options beat shares" or the reverse.
- The shares book itself can get interim horizons with no capture: `shares_return_report(horizons=…)` already
  takes the horizon set in trading bars. Printed alongside, never against.

### 3.5 Entry path (origin = backfill vs above-floor, real book)
- Origin per `dashboard_data._real_multiples_by_origin`: `'"origin": "backfill"'` in `rationale`, else sentinel
  or hand_seed. Unpaired. Today: one backfill entry (TITN) and one filled above-floor entry (FLNC).
- The backfill's own stop rule (`convexity_book.backfill.stop_*`, `records/2026-11-03_backfill_enabling.md`) is
  the only thing that acts on backfill performance. This read must not become a second stop rule. Pin 2's
  restriction (§3.3) applies equally, since these are real-book positions **[PIN]**.

## §4 What each read may and may not claim

- **May:** "At h = 30, the 3A-only stratum's median mark multiple was X (CI a–b, n, k clusters), the matched
  stratum's Y; INTERIM, unresolved positions, mid marks." Counts of unmarked and excluded rows, always.
- **May not:** that the gate, council, universe or instrument works or fails; any significance test; any change to
  an entry, veto, size, prompt, basket or threshold; any outcome-selected name list. A gap between arms at
  interim is not a gap verdict. The null_hierarchy stance holds: this layer is a separate INTERIM panel, and
  `null_hierarchy` keeps computing no gap.
- **Relation to FBN §5:** the resolution read (p95 of realized multiples, bootstrap CI, with/without top-k) is
  unchanged and remains the only read that bears on the edge.

## §5 Open decisions for the operator

1. Adopt the daily mark snapshot (§2), and where it lives (a `scripts/` probe and its own table vs a write inside
   the L2 monitor).
2. Pin 2 conflict: keep the council and entry-path rows as counts-only (default), or amend Pin 2 by name.
3. Universe interim horizons 21/42 bars, forward-only from the freeze, as an amendment to PREREG_MISS_BASERATE §3.
4. The statistic (median + CI on the median, not p95) and the floor (n ≥ 10 ∧ ≥ 3 clusters per arm).
5. Whether the gate read's value justifies the build, given that the expiry wall resolves most null positions by
   mid-January 2027 and only positions opened after the capture start get interim reads.
