# PREREG — Held-name thesis tracking, Option B (#464; PREREG_COUNCIL_GATE_SEPARATION §10.13)

**Status: FROZEN 2026-11-16 (operator word "Sure, let's keep moving with your recommendations").** Every [PIN] takes the §8 recommendation: run Option B; start with the first L1 after the code merges; a separate post-L1 unit (shared with the §10.12 probe: `dramatic-options-post-l1`); cap $1.00 per pass with spend counted in MTD; dormant packs rendered as-is with the lineage status stored; scoring §4 as drafted; the prohibition §5 as written. It narrows the 2026-11-10 draft (`records/2026-11-10_held_name_thesis_tracking_DRAFT.md`, draft PR #476) to Option B, as the operator's 2026-11-12 word ranked it. §10.13 indexes this file.

**Measurement only.** No held read may change an entry, a veto, a size, an exit, an add, a re-strike, a carry, the
backfill rank, the persistence watch or any verdict of record. Guardrail 6 holds: reads are scored forward at each
position's close and never backtested.

## 1. Why now (read-only, 2026-11-16)

A held name is re-read only while its sentinel lineage stays active, and a held name can never re-surface:
`run_discover` excludes `state.open_position_symbols` from the scan (`orchestrator.py:606`). Its lineage then goes
dormant at `sentinel_ttl_days = 35` and the council never reads it again while the position is open.

| Position | Held since | Lineage | Last seen by L0 | Last council read |
|---|---|---|---|---|
| PL #1 bullish | 2026-07-01 | dormant | 2026-06-10 | **2026-07-17** (4 months unread) |
| TITN #7 bullish | 2026-11-04 | **dormant 11-15** | 2026-10-04 | 2026-11-13 (last read) |
| FLNC #6 bearish | 2026-11-04 | active | 2026-11-01 | 2026-11-13; dormant ~12-06 |
| RDW #13 bearish | 2026-11-13 | active | 2026-11-08 | 2026-11-13; dormant ~12-13 |

By mid-December no held position would be re-read, for the rest of 6–12-month holds. A post-entry read is the input
every position-management rule (salvage exit, add-to-winners, re-strike; C1) needs and nobody is measuring.

## 2. The pass [PIN throughout]

- **Who:** every real position with status `open` or `closing` and a non-null `proposal_id`, keyed by its
  (symbol, direction). A position without one is listed `no_lineage`, not read.
- **When:** after the L1, as a separate process, on the same pattern as the §10.12 probe: its own unit after the
  L1, refusing until the L1 has finished, skipped under KILL. It never runs inside the L1 and never touches the
  council of record.
- **How:** for each tracked position, build the pack exactly as the L1 would (`build_context_pack` on the
  position's own lineage row via `sentinels.discovered_to_theme`, active or dormant; a hand-seed by its
  `themes.json` entry), refresh its markers as the L1 does, and run the full `council/debate.run_candidate` once,
  with the council of record's config and models.
- **The pack never says the name is held**, nor its entry, mark or P&L (`ContextPack` has no such field; a test
  asserts it stays that way). A dormant lineage's pack is rendered as-is, without a "dormant" label, so held reads
  stay comparable with of-record reads.
- **Storage:** its own append-only table `held_reads` (position id, run id, as_of, lineage status, the three
  criteria, conviction raw and final, `include`, `structural_vs_fad`, `weakest_point`, per-role provider/model, the
  `model_mix` stamp, cost; the mark multiple and DTE at read time for the timeline only). **Never
  `council_proposals` or `council_agent_outputs`**, so Brier, the §10.x counts, the backfill pool and the
  persistence watch are untouched.
- **Cost:** a full debate costs about $0.024 per name (11-13: $0.2854 for 12 names). Four held names ≈ $0.10 a night,
  fifteen ≈ $0.36. Own `CostLedger`, cap **$1.00 per pass**; a cap hit or provider error loses only that night's
  held reads. Spend counts in the monthly page's MTD, as §10.12's probe does.
- **Start:** default-off until the word, then switched on with the first L1 after its merge. It changes nothing the
  council of record sees, so it is not a boundary-B change. Its own segment: if `runs.model_mix` changes, the reads
  before and after are reported separately.

## 3. Display

A per-position timeline under Positions: the entry verdict (the of-record proposal), each held read (three criteria
and conviction), of-record seatings of the same name labelled by source, the falsifier-ledger reads for that
symbol, and the L2 mark multiple. **No trend line, no "thesis broken" badge, no colour keyed to exit.**

## 4. Scoring (counts only, at close)

When a position closes, take its last 3 held reads before `closed_at`. "Intact" if at least 2 are at or above the
floor (for a backfill origin: `include = true` at LOW or higher, the persistence-watch convention), else "broken".
Outcome: realized multiple ≥ 1.0 vs < 1.0, with ≥ 10× reported alongside. A 2 × 2 table of counts; closes with
fewer than 3 reads counted apart. **No rate prints until 20 closed positions with 3 reads.** The quantity it feeds
is the false-alarm rate P(broken | outcome ≥ 1.0), the number a salvage exit depends on (Rule S,
`records/2026-11-03_calibration_v2_finding.md`).

## 5. The pinned prohibition

Until a separately pre-registered rule exists (after C1, and after §4's counts reach their minimum), no held read may
trigger or delay an exit, an add, a re-strike or a carry; veto or size anything; be rendered into any council
prompt; or feed the backfill rank, the gates or the persistence watch.

## 6. Relation to §10.12 and the open questions

- §10.12's probe re-reads the same night's of-record verdict k times (stability). This pass reads held names once a
  night, every night (drift over the hold). Different units, different tables; both measurement-only.
- The RDW `include=false` question and carry confirmation stay with the §10.12 look; held reads do not enter the
  persistence count (§5).

## 7. What changed from the 11-10 draft

Option A is dropped (operator: option B). The "start after the ~11-12 refresh" is replaced by "first L1 after merge,
own segment" (the refresh now rides 12-07 at the earliest, and held names are going unread now). Cost re-measured.
The process follows §10.12's separate-unit pattern instead of running inside the L1.

## 8. Decisions (adopted 2026-11-16: every recommendation)

| # | Decision | Recommendation |
|---|---|---|
| 1 | Run the held pass (Option B) | Yes |
| 2 | Start: the first L1 after merge, default-off until then | Yes |
| 3 | Separate unit after the L1 (the §10.12 pattern) | Yes |
| 4 | Cap $1.00 per pass; spend counted in MTD | Yes |
| 5 | Dormant packs rendered as-is (no label); lineage status stored | Yes |
| 6 | Scoring §4 (last 3 reads, ≥ 20 closes before any rate) | As drafted |
| 7 | The prohibition §5 | As written |
