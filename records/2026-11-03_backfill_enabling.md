# 2026-11-03 — Enabling the ranked backfill (D1): the dated config edit

**What:** `config.json` gains `convexity_book.backfill = {"enabled": true, …}` with the amendment's values
(`empty_slots_min` 10, `lookback_days` 28, `per_week` 1, `candidates` 3; stop rule 8 entries / 90 days / +25 pp).
Spec: `PREREG_THEMATIC_CONVEXITY` §5 amendment 2026-11-03 (merged in rozavala/dramatic_options#411). Operator
word: "Draft the backfill enabling PR" (2026-11-03); **in force from the first L1 after this PR is merged and
deployed** (DEV; PROD stays inert).

**Frame boundary:** `frame_version` moves **`frame-3a810daad056` → `frame-f86f37a0bd4f`** (the hash covers
`convexity_book`). Every frozen risk number is unchanged; the new segment is "ITM side guard + ranked backfill".
Entries before the boundary stay in the old segment.

## What it will do (expected, not promised)
- **The trigger is already met.** The real book has held 1 committed slot (PL) for months; HL's and AG's October
  orders were cancelled unfilled, and cancelled rows hold no slot. So the first L1 after deploy is expected to
  read `Backfill: book idle: peak 1 committed in 28d ≤ 5; N candidate(s): […]`.
- **Candidates:** that L1's council proposals that missed the floor or the tri-criteria, but were judged
  `structural` at conviction ≥ LOW. Ranked by criteria asserted true, conviction, then fresh gate-of-record IV/RV.
  Up to 3 go to the gates after every above-floor name.
- **At most one entry per trailing 7 days.** It must clear every unchanged gate: eligibility, the side guard, the
  §4 IV/skew gate, the dual-read veto, the cluster, per-name and book caps, flat-by-slots sizing, the
  foreign-quantity check and the restricted list. A night where no candidate is cheap enters nothing.
- **Orders follow the ordinary path:** submitted at the L1 mid and carried to the next session if unfilled
  (#386). The usual REAL-BOOK ORDER SUBMITTED / FILL / NOT FILLED pages fire.

## What to watch
- **The L1 log line** `Backfill: …` every night: the trigger, the quota, or the candidates.
- **The execution ledger** (dashboard Edge → Telemetry): backfill approvals are council proposals with
  `rationale.backfill.rank`, and the positions carry `origin = backfill`.
- **`real_by_origin`** (performance panel): `backfill` is scored apart from above-floor entries.
- **The stop rule** pages "Backfill suspended (stop rule)" if it ever fires. It needs ≥ 8 backfill entries that
  are ≥ 90 days old, so it cannot fire before about February 2027 at one entry per week.

## Pre-stated reads (written before any backfill entry exists)
- **First week:** report the trigger line and the candidates each night; flag anything unexpected (a quota
  breach, an entry that skipped a gate, a backfill on a name with a working order).
- **After 4 backfill entries or 6 weeks, whichever comes first:** a dated look at fill rate (D0), cheapness at
  entry vs above-floor entries, and cluster spread. No outcome claim; the 6–12-month holds can't resolve that soon.

## How to turn it off
Set `enabled` to `false` (or remove the block) by a dated edit. That moves `frame_version` again. Open
backfill positions are not closed; they run their §6a exits.
