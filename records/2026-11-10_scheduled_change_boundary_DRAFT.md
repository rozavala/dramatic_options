# 2026-11-10 — A scheduled boundary for record-segmenting changes (#470, G1)

> **Status: DRAFT for issue #470. Nothing here is in force.** This is a process ruling. It would change how
> every later ruling is scheduled, so it is the operator's to accept, change or strike, by dated word. Merging
> this file ratifies nothing: merge-as-ratification is a named failure mode in this project
> (PREREG_THEMATIC_CONVEXITY §6 ownership addendum). The STANDING_STATE text in §7 would be recorded on the word.

## 1. Where the stamps are written (verified)
- `runs.frame_version` (migration 0009) is written by `state.record_run` on **every** run, from
  `config_loader.frame_version`. That function hashes the comment-free `convexity_book` (with the clusters),
  `convexity_gate`, `convexity_exits` and `kill_rule` config blocks.
- `runs.model_mix` (migration 0011) is written on **council L1 runs only**, by `orchestrator._stamp_council_health`
  through `state.update_run_council_health`. Its keys:
  - per role, `provider/model` (the "models" stamp);
  - `prompts`: sha256[:16] of `council.agents._COMMON`, `ADVERSARY_SYSTEM` and `STRATEGIST_SYSTEM`, at runtime;
  - **hard-coded constants:** `corpus_refresh = filing_date_v1`, `corpus = fundamentals_v2`,
    `coverage_meter = analyst_v2` and `quote_filter = musd_billions_v1+iso_dates_v1`;
  - **config-derived:** `union_rank` (cheap reserve, fairness, `direction_coherence.STAMP = dircoherence_v1`,
    `expressible_v1`), `markers` (`marker_refresh.stamp`), `pack_provenance`, `forward_catalysts` and
    `roles_fallback`.
- `runs.data_feed` (migration 0013) and `runs.discovery_funnel` (migration 0015) are also per run. Neither moved in
  this window.
- **Consequence for staging:** the constant and prompt stamps move only by a code change. The config-derived
  stamps and `frame_version` move by a config edit. §4 relies on this split.

## 2. Evidence: every change since 2026-10-15
From STANDING_STATE "Rulings in force" and the records cited there. "Record-segmenting" means a `runs` stamp
moved. "Sweep" means a weekly sweep's dated segment moved (PREREG_MISS_BASERATE / PREREG_UNIVERSE_CURATION), with
no `runs` stamp.

| In force | What changed | Stamp that moved | Class |
|---|---|---|---|
| 10-15 (#1681) | window #10: NTSK, new `cyber_sase` cluster | `frame_version` → `a80e6abea2b9` | segmenting |
| 10-16 (#1712) | L1 marker refresh ON | `markers = l1_refresh_both_v1` | segmenting |
| 10-19 (after #325) | window #11: CF/BWXT added to the cluster map | `frame_version` → `3a810daad056` | segmenting |
| 10-21 | expressible-first slate (#329) | `union_rank +expressible_v1` | segmenting |
| 10-23 (#1798) | criterion (3) re-specified, §10.10 | `prompts` → `48f6d57f…` | segmenting |
| 10-26 (#1816) | $B restatements pooled (#336; word 10-24) | `quote_filter = musd_billions_v1` | segmenting |
| 10-26 (planned) | analyst meter restored (#337/#338; word 10-24) | `coverage_meter = analyst_v2` | segmenting |
| first L1 after deploy | corpus refetch on filing (#340; word 10-25) | `corpus_refresh = filing_date_v1` | segmenting |
| 11-01 sweep | OTM side guard in the probe and survivor cards (#343/#345) | sweep segment | sweep |
| 11-01 L0 | sentinel TTL by ET date (#342) | none (membership; no retroactive change) | membership |
| 10-29 | carry-over ON (#386/#387) | none: "Execution only; `frame_version` unchanged" | execution-only |
| 10-30 (#1884) | criterion (3) name-level, §10.11 | `prompts` → `cd34e754…` | segmenting |
| 11-02 (#1901) | rendered ISO dates accepted (#403) | `quote_filter +iso_dates_v1` | segmenting |
| 11-03 (#1918) | ranked backfill enabled (#415) | `frame_version` → `f86f37a0bd4f` | segmenting |
| 11-03 | D0 execution ledger, D4 IV history, D3b falsifier ledger | none | telemetry |
| 11-05 (run #1938) | 15% moneyness floor (#416 → #425; word 11-04) | `frame_version` → `880e893e1660` | segmenting |
| 11-08 sweep | the 15% floor in both weekly sweeps (#427) | sweep segment | sweep |
| 11-09 | ATKR removed, universe 49 | none ("`frame_version` is unchanged … no `model_mix` stamp changes") | membership |
| 11-09 | persistence watch amended | none (measurement) | telemetry |
| ~11-12 (staged) | model refresh, all roles; `restate_v1` (#426, a draft PR) | models; `quote_filter` | segmenting |

**Count:** 12 `runs`-stamp moves in 22 days (10-15 → 11-05). Four were `frame_version` moves: two curation windows
and two frame amendments. They fall on about 10 distinct L1 boundaries, if `coverage_meter` and `corpus_refresh`
both started at #1816 as planned. There are also two sweep boundaries, and two more moves are staged. Issue
#470's table lists 8 of the 12, plus the staged row. It omits the two window frame moves, `markers` and `expressible_v1`. It also
dates `quote_filter` at 10-24, the word, where the first stamped L1 is 10-26 (#1816).
**UNVERIFIED:** the first run of `coverage_meter = analyst_v2` and of `corpus_refresh` (the records say "planned
10-26" and "first L1 after deploy"). `frame-a80e6abea2b9`'s session and entry counts are not stated in any record.

**Sessions and real entries per segment** (`records/2026-11-04_council_two_week_look.md`;
`records/2026-11-08_sunday_w45.md`):
- **Prompts.** §10.10: 5 L1 sessions (#1798–#1867), 2 above-floor (HL, AG), 0 fills (both cancelled unfilled).
  §10.11: 6 sessions through 11-06 (#1884–#1969), 1 above-floor (FLNC).
- **quote_filter.** None: 1 session (#1798). `musd_billions_v1`: 5 (#1816–#1884). `+iso_dates_v1`: 5 through 11-06
  ("nights 1–5").
- **frame_version.** `3a810daad056`: 0 real fills. `f86f37a0bd4f`: 2 sessions (#1918, #1935), **2 real entries**
  (FLNC #6 and TITN #7, ordered #1918, filled 11-04 via carry). `880e893e1660`: 0 entries through 11-08 ("No real
  entry has been made under the floor yet").
- **All stamps at once.** The longest completed run of L1 sessions with every stamp unchanged is 4 (#1816 → #1867,
  10-26 → 10-29). The others since 10-23 hold 1–2 sessions each. The current one (from 11-05) reaches 5 if the
  refresh lands on 11-12.
- **The two-week look** had to split 9 sessions into two prompt segments and three filter states. Its own table
  shows this.

## 3. The ruling — options
**When the boundary falls**
- **A: the first NYSE trading day of each month.** Simple. It can fall on a Friday, so the week's L0 slate was
  built under the old rules.
- **B (recommended): the first Monday L1 of each month, deployed the weekend before the Sunday L0.** Merges happen
  on Saturday, off the L1/L2 grids (L2 runs Mon–Fri). The Sunday 08:00 ET L0 and every L1 that week then run under
  one rule set. If that Monday is an NYSE holiday (e.g. Labor Day), the boundary is the next trading day.
  **Expiry weeks:** the monthly expiry is the third Friday (the 15th–21st), so a first Monday (the 1st–7th) never
  falls in an expiry week. It also stays clear of the Monday after expiry, where the 180-day tenor cliffs land
  (STANDING_STATE docket: Mon 11-23 after Fri 11-20). An expressibility cliff and a rule change never share a day.
- **C: every second Monday.** Segments half as long, about 10 L1 sessions. Twice the operator decisions.

Under B, the next boundaries would be Mon **2026-12-07** (L0 Sun 12-06), Mon 2027-01-04, then Mon 2027-02-01.
**The staged ~11-12 refresh** (models plus #426) is already worded (11-01 and 11-04). Recommendation: let it land
as the last unscheduled boundary, and start the schedule at 12-07.

**What may land off-cycle** (recorded as an off-cycle boundary with its reason, the same day):
- a **money-safety defect**: a wrong order, a wrong size, a position left at the venue, an exit that does not exit
  (#444 and #451 are this class);
- a **fail-closed outage**: an input or path dead in a way that blocks entries or fails every cycle;
- a **frame-conformance defect**: an entry path admitting positions outside what the frozen frame says. This is the
  #276 side-guard class. It is a judgement call, and §5 gives the honest example.

**Not** off-cycle: a silently degraded pack input, such as the dead analyst meter fixed 10-24. It degraded verdicts
without failing anything. Fixing it starts a better segment, but the old one can be read with the caveat for up to
a month. Recommendation: it waits, unless the operator classes it as an outage.

**Exempt** (lands any day): telemetry (ledgers, the falsifier ledger, logs, pages), execution-only changes that move
no stamp (the carry-over precedent), records, dashboard and copy, the removal of a delisted name with no stamp moving
(the ATKR precedent), and money-safety fixes outside the decision path. **Not exempt:** curation windows that move
the cluster map. They move `frame_version` (10-15, 10-19), so they land on a boundary.

**How staged changes are held**
- **Config-gated changes merge early behind a default-off switch.** These are the stamps derived from config and
  `frame_version` moves: the backfill (`convexity_book.backfill`) and over-cap verticals
  (`vertical_for_over_cap`) precedents. The code is inert until a dated enabling edit, and that edit is what lands
  on the boundary.
- **Prompt and constant-stamp changes stay draft PRs.** Prompts, `quote_filter`, `coverage_meter`,
  `corpus_refresh`: their stamp moves with the code, so no switch can hold them. They follow the #426 precedent: a
  GitHub draft PR titled "— DRAFT, merge at the <date> boundary", rebased onto the boundary.
- **Merge-day load.** `/ship` Step 7 allows at most 4 merges per 15 minutes (`dramatic-options-web`
  `StartLimitBurst=5`). A boundary with more than 4 PRs is spread over windows that Saturday, or folded into one
  boundary PR.

## 4. Tooling
**A generated segment register.** `scripts/segment_register.py` (read-only, `?mode=ro`):
- **It reads** `runs` (id, started_at, mode, frame_version, model_mix, data_feed, discovery_funnel), keyed on
  council L1 runs (those with non-null `model_mix`), plus `convexity_positions` (by `run_id`, excluding
  `cancelled`).
- **It prints one row per maximal run of L1s with the same stamp tuple:** segment #, first and last run and date,
  L1 sessions, which keys changed against the previous segment (old → new), above-floor verdicts and real entries
  (filled), with `origin` split.
- **Optionally,** a `--boundaries` file of dated boundaries. A segment start not on a scheduled date, and not
  listed as off-cycle, is flagged.
- **Tests:** a hand-built fixture DB with known segments.
- Reviews and the nightly grade read it instead of rebuilding the table by hand.

**A CI check.** A small refactor first: lift the `model_mix` assembly out of `_stamp_council_health` into a pure
`model_mix_stamp(config, roles)`. Then `scripts/stamp_fingerprint.py` prints `frame_version(config)`, the three
prompt hashes and `model_mix_stamp`. A `ci.yml` job runs it on the base and head of each PR. If the two differ, the
PR body must contain `Boundary: YYYY-MM-DD` (a scheduled date) or `Off-cycle: <reason>`; otherwise the job fails.
The body comes from `github.event.pull_request.body`. A config-gated feature merged default-off leaves the
fingerprint unchanged and passes.

**Skill steps that would change**
- `.claude/skills/ship/SKILL.md` **Step 3 (Lane assignment):** a record-segmenting change is opened as a draft PR,
  or merged default-off, and named for its boundary.
- **Step 4 (PR body)** "Record" field: add "the boundary date or the off-cycle reason".
- **Step 7 (Merge plan):** a record-segmenting PR appears in the plan only on its boundary date, unless it is
  off-cycle.
- The Operating Constraints line on record-segmenting changes ("adds a `runs.model_mix` stamp and a STANDING_STATE
  entry") gains "on a scheduled boundary".
- `.claude/skills/triage/SKILL.md` **Step 1a (Change timeline):** read the segment register for the stamp
  boundaries. **Step 1e:** a stamp move that is on no scheduled date and not recorded off-cycle is PROTOCOL.

## 5. The costs, stated honestly
- **A fix waits up to a month.** Under B, a defect found the Tuesday after a boundary waits about 4 weeks. For the
  council-input fixes in §2 (the quote filters, the meter, the refetch), waiting means a month of verdicts read
  with a known caveat. The filter cost was real: FRO on 11-04 and CEG on 11-05 and 11-06 were removed from
  deliberation by the #421 class (W45), and #426 waits for ~11-12 anyway.
- **The 15% floor (#416).** It was found at L1 #1918 (11-03), worded 11-04, merged 11-05 and in force at #1938. Under
  B, unless it counted as a frame-conformance defect, it would have landed on Mon 12-07, about 4.5 weeks later.
  Meanwhile the gate-of-record wings below 15% on 11-04 (5–7 of 38, all cheap; the §4 amendment) could have
  re-selected near-money contracts. TITN's 7%-OTM C25 order is the shape. The backfill quota (1 per 7 days) bounds
  that path to about 4 backfill entries; above-floor entries are unbounded by quota. **UNVERIFIED:** how many of
  those would actually have entered. I would class #416 as off-cycle (a frame-conformance defect), and §3's
  exception exists for it. A strict reading that refuses this would have cost up to a month of possible near-money
  entries.
- **What it buys:** segments of about 20 L1 sessions instead of about 4, one operator decision day a month instead
  of about one every two days, and a reviewer who reads one register.
- **What it does not buy:** entries. At about one real entry a week, a month-long segment still holds about 4
  entries. Calibrate-not-prove stays slow; this only stops it getting slower.

## 6. Decisions for the operator
1. Adopt a scheduled boundary: **B** (first Monday L1, weekend deploy), A or C.
2. The off-cycle classes: money-safety, fail-closed outage, frame-conformance (and whether #416-class counts).
3. The exempt list as in §3, including that curation windows that move the cluster map are **not** exempt.
4. Staging: config-gated changes default-off; prompt and constant changes as draft PRs.
5. Build the segment register and the CI fingerprint check (telemetry and CI; both exempt).
6. The ~11-12 refresh lands as planned, and the schedule starts Mon 2026-12-07.

## 7. STANDING_STATE entry, to be recorded on the word
> - **Scheduled record boundary (2026-[MM-DD], operator word "[quote]"; #470;
>   `records/2026-11-10_scheduled_change_boundary_DRAFT.md`):** record-segmenting changes (any move of
>   `frame_version`, the prompt hashes, a model, or a `runs.model_mix` key or value) land together on **the first
>   Monday L1 of each month** [| option], deployed the weekend before its Sunday L0 (next: **Mon 2026-12-07**).
>   Between boundaries they are staged default-off (config-gated) or as draft PRs (the #426 form). **Off-cycle,
>   recorded here with the reason the same day:** a money-safety defect, a fail-closed outage [, a
>   frame-conformance defect]. **Exempt:** telemetry, execution-only changes that move no stamp, records, the
>   dashboard, delisted-name removals with no stamp moving. Curation windows that move the cluster map are not
>   exempt. `scripts/segment_register.py` is the segment table of record; CI fails a PR that moves the stamp
>   fingerprint without `Boundary:` or `Off-cycle:` in its body. The ~11-12 model refresh plus `restate_v1` is the
>   last unscheduled boundary.
