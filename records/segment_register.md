# Segment register — every record-segmenting stamp move, dated (#470)

**What this is.** The register boundary B asked for (STANDING_STATE, operator decisions 2026-11-12: "the segment register
only, with no CI fingerprint check"; built on the operator's word of 2026-11-18). One row per stamp move recorded in
`runs`, with the first run that carries it, its cause, and what it segments. Reviews and records cite segments from
here instead of rebuilding the table by hand. **Append-only:** a row is never edited after it lands, except to fill
in a cause marked UNVERIFIED. A correction is a new dated note under the table.

**The machine half.** `scripts/ops/segment_register.py` reads `runs` (`?mode=ro`) and prints every stamp move and the
council-L1 segments those moves cut, with L1 sessions and real entries per segment. With `--check` it exits 1 if a move
has no row here. A row matches when one line holds `run #<first run id>` and the stamp name in backticks. Session and
entry counts live in the script's output, not in this file, because the current segment keeps growing.

```bash
PYTHONPATH=. venv/bin/python scripts/ops/segment_register.py \
  --db /home/rozavala/dramatic_options/data/dramatic_options.db --check [--since 1900]
```

**When a row is added.** Add it in the PR that moves a stamp. Under boundary B that is the boundary's merge set, or
the off-cycle fix with its reason. If the PR did not add it, the Sunday review's `--check` adds it in that week's
records PR.

**Which stamps are read.**
- `frame_version` and `data_feed` are stamped on every run.
- `discovery_funnel` is stamped on L0 (DISCOVERY) runs.
- Each `model_mix` key is stamped on council L1 runs only, so a `model_mix` move is dated at the first L1 that
  carries it.

A `frame_version` move is dated at the first run of any kind that carries it, which is often an L2 the same day. Its
**first council L1** is the one a council read segments on. Both are given.

**How the back-fill was verified (2026-11-18, read-only).**
- Every row comes from the live DB's `runs` (2,092 runs to #2092, 2026-11-17).
- All 18 `frame_version` values were re-derived from `config.json` at each commit on `main`, using today's
  `config_loader.frame_version`. Each matched exactly one commit, which gives the cause.
- All 3 `prompts` values were re-derived from `council/agents.py` at each commit on `main` and matched the same way.
- Other causes come from the commit that introduced or switched on the stamp, mapped to its PR through GitHub, and
  are cross-checked against STANDING_STATE where it names a boundary run (#1437, #1558, #1575, #1644, #1712, #1938).
- This settles two items the #470 draft (2026-11-10, §2) left UNVERIFIED: `coverage_meter = analyst_v2` and
  `corpus_refresh = filing_date_v1` both start at run #1816 (2026-10-26).

## The register

| First run | Date (UTC) | First council L1 | Stamp | Old → new | Cause | What it segments |
|---|---|---|---|---|---|---|
| run #21 | 06-03 | #55 (06-04) | `frame_version` | (none) → `a4b0c2df8345` | PR #27, the pre-T4 cluster cap (PREREG_THEMATIC_CONVEXITY §5 amendment 2026-06-03). The stamp starts here (migration 0009) | risk frame (cluster cap) |
| run #55 | 06-04 | #55 | `proposer` | (none) → gemini/gemini-3.5-flash | PR #32, the model_mix stamp (migration 0011). The stamp starts here | council verdicts (models) |
| run #55 | 06-04 | #55 | `adversary` | (none) → xai/grok-4.3 | PR #32, as above | council verdicts (models) |
| run #55 | 06-04 | #55 | `strategist` | (none) → anthropic/claude-opus-4-8 | PR #32, as above | council verdicts (models) |
| run #75 | 06-05 | #92 (06-08) | `frame_version` | → `cf66bc5a28b7` | PR #35: the defense primes added to the `space_defense` cluster | risk frame (cluster map) |
| run #96 | 06-08 | #111 (06-09) | `data_feed` | (none) → SIP equity bars, INDICATIVE gate | PR #42, data-feed PR1. The stamp starts here (migration 0013) | gate inputs (feeds) |
| run #114 | 06-10 | #130 (06-10) | `frame_version` | → `c2e5db5cfdfa` | PR #48, universe window #1 (17 names, 4 baskets) | risk frame (cluster map) |
| run #116 | 06-10 | #130 (06-10) | `data_feed` | → OPRA gate of record, dual-read concurrent | PR #53, the OPRA flip (PREREG_DATA_FEED_OPRA_SEQUENCING) | gate inputs (feeds) |
| run #164 | 06-12 | #164 | `prompts` | (unstamped `b644b20d…`) → `d96f18eb…/dc3d21ca…/ecbf363c…` | PR #54, the §10.7 thesis-only prompts (PREREG_COUNCIL_GATE_SEPARATION). A real prompt change; the stamp starts here | council verdicts (prompts) |
| run #182 | 06-15 | #182 | `corpus` | (none) → fundamentals_v1 | PR #58, the §9 fundamentals corpus wired into the pack (PREREG_EVIDENCE_GROUNDING) | council pack |
| run #254 | 06-22 | #285 (06-23) | `data_feed` | + `dualread_revert_enabled: false` | PR #80, the dual-read tripwire runtime (#72), phase 3 off | gate inputs (revert latch) |
| run #270 | 06-22 | #285 (06-23) | `frame_version` | → `9b6b6f9710fa` | PR #86, window #2 off-cycle (silver_deficit, seaborne_freight) | risk frame (cluster map) |
| run #288 | 06-24 | #303 (06-24) | `data_feed` | `dualread_revert_enabled` → true | PR #90, the phase-3 revert latch armed (#72) | gate inputs (revert latch) |
| run #288 | 06-24 | (L0) | `discovery_funnel` | (none) → fresh_v1 | PR #88, the fresh-inflection funnel (PREREG_FRESH_INFLECTION_FUNNEL) | L0 surfacing |
| run #320 | 06-25 | #320 | `corpus` | → fundamentals_v2 | PR #91, fundamentals freshness v2 (IFRS taxonomy, tag recency, annual fallback) | council pack |
| run #340 | 06-28 | (L0) | `discovery_funnel` | → fresh_v2 | PR #93, the lone-basket rank fix | L0 surfacing |
| run #358 | 06-30 | #372 (06-30) | `frame_version` | → `839859b74bd0` | PR #126, cheapness-watch §2.1.8 degenerate-IV bounds (keys added to `convexity_gate`) | risk frame (gate block; no live-gate change) |
| run #372 | 06-30 | #372 | `clock_basis` | (none) → council_confirmed_under_narrated_v1 | PR #129, the cheapness-watch clock-start gate (PREREG_CHEAPNESS_WATCH §2.1.7) | cheapness-watch rates |
| run #389 | 07-01 | #389 | `coverage_meter` | (none) → analyst_v1 | PR #132, the analyst-coverage meter | council pack |
| run #441 | 07-06 | #441 | `union_rank` | (none) → cheap_reserve_v1 | PR #149, the gate-cheap reserve (frozen 2026-07-02) | council slate composition |
| run #502 | 07-10 | #508 (07-10) | `frame_version` | → `d1f23fc12e81` | PR #181, CC's off-cycle admission (window #3's first act) | risk frame (cluster map) |
| run #508 | 07-10 | #508 | `forward_catalysts` | (none) → forward_catalyst_v1 | PR #170, the forward-catalyst channel PR1 (PREREG_FORWARD_CATALYST_GROUNDING) | council pack |
| run #663 | 07-23 | #663 | `proposer` | → gemini/gemini-3.6-flash | PR #213 (`records/2026-07-22_proposer_model_upgrade_gemini36.md`) | council verdicts (models) |
| run #787 | 08-04 | #801 (08-04) | `frame_version` | → `77f43a5558d5` | PR #222, window #3: VIAV (`fiber_capex` cluster) | risk frame (cluster map) |
| run #921 | 08-13 | #921 | `union_rank` | + fairness_v1 | PR #226 (`records/2026-08-11_fairness_reserve_amendment.md`) | council slate composition |
| run #990 | 08-19 | #990 | `union_rank` | fairness_v1 → fairness_v1.1 | PR #231 (`records/2026-08-19_fairness_fresh_event_v1p1_amendment.md`) | council slate composition |
| run #995 | 08-20 | none (one run) | `frame_version` | → `cbebcced2288` | PR #232, window #4: MRK (`mrna_oncology`) | risk frame (cluster map); superseded 30 min later |
| run #996 | 08-20 | #1007 (08-20) | `frame_version` | → `3b795b13bfcf` | PR #233, window #5: TITN, MOS (`ag_cycle_trough`) | risk frame (cluster map) |
| run #1093 | 08-27 | #1093 | `roles_fallback` | (none) → strategist:openai/gpt-5.2-2025-12-11 | PR #239, the strategist understudy | council verdicts (fallback nights) |
| run #1116 | 08-31 | #1128 (08-31) | `frame_version` | → `e853fa5cd2a4` | PR #241, window #6: KKR | risk frame (cluster map) |
| run #1222 | 09-08 | #1231 (09-08) | `frame_version` | → `8442a5e77cf3` | PR #246, window #7: FIG | risk frame (cluster map) |
| run #1322 | 09-16 | #1334 (09-16) | `frame_version` | → `82ac320a0497` | PR #255, window #8: KLAR | risk frame (cluster map) |
| run #1377 | 09-21 | #1386 (09-21) | `frame_version` | → `5a2055fea182` | PR #259, window #9: STUB | risk frame (cluster map) |
| run #1437 | 09-24 | #1437 | `union_rank` | + dircoherence_v1 | PR #261, PREREG_DIRECTION_COHERENCE (segment boundary #1437) | council slate composition |
| run #1492 | 09-30 | #1506 (09-30) | `frame_version` | → `a6da3dee9171` | PR #277, the OTM side guard (#276 option 1; STANDING_STATE "ITM side guard") | gate (wing selection) |
| run #1558 | 10-05 | #1558 | `forward_catalysts` | + sentinel_v1 | PR #280, the forward-catalyst sentinel scope (operator word 10-02) | council pack (sentinels) |
| run #1558 | 10-05 | #1558 | `pack_provenance` | (none) → provenance_v1 | PR #280, amendment A1 (boundary L1 #1558) | council pack |
| run #1575 | 10-06 | #1575 | `pack_provenance` | + register_thesis_v1 | PR #292, amendment A2 (boundary L1 #1575) | council pack |
| run #1644 | 10-12 | #1644 | `pack_provenance` | register_thesis_v1 → v1.1 | PR #301, amendment A2.1 (boundary L1 #1644) | council pack |
| run #1681 | 10-15 | #1695 (10-15) | `frame_version` | → `a80e6abea2b9` | PR #309, window #10: NTSK (`cyber_sase`) | risk frame (cluster map) |
| run #1712 | 10-16 | #1712 | `markers` | (none) → l1_refresh_both_v1 | PR #320, the L1 marker refresh (PREREG_FRESH_INFLECTION_FUNNEL §7.1a) | council pack |
| run #1732 | 10-19 | #1747 (10-20) | `frame_version` | → `3a810daad056` | PR #325, window #11: CF, BWXT | risk frame (cluster map) |
| run #1764 | 10-21 | #1764 | `union_rank` | + expressible_v1 | PR #329 (built default-off) and PR #330 (switched on, operator word 10-21) | council slate composition |
| run #1798 | 10-23 | #1798 | `prompts` | → `48f6d57f…/8a4d3291…/6cb63ff7…` | PR #335, criterion (3) re-specified (§10.10) | council verdicts (prompts) |
| run #1816 | 10-26 | #1816 | `corpus_refresh` | (none) → filing_date_v1 | PR #347 (#340), the corpus refetch on filing | council pack |
| run #1816 | 10-26 | #1816 | `coverage_meter` | analyst_v1 → analyst_v2 | PR #338 (#337), the analyst meter restored | council pack |
| run #1816 | 10-26 | #1816 | `quote_filter` | (none) → musd_billions_v1 | PR #336, $B restatements pooled | council final convictions |
| run #1884 | 10-30 | #1884 | `prompts` | → `cd34e754…/98f11177…/bc33c3e2…` | PR #388, criterion (3) name-level (§10.11) | council verdicts (prompts) |
| run #1901 | 11-02 | #1901 | `quote_filter` | + iso_dates_v1 | PR #405 (#403), rendered ISO dates accepted (PREREG_FORWARD_CATALYST_GROUNDING §12) | council final convictions |
| run #1914 | 11-03 | #1918 (11-03) | `frame_version` | → `f86f37a0bd4f` | PR #415, ranked backfill enabled (`records/2026-11-03_backfill_enabling.md`) | risk frame (entry path) |
| run #1938 | 11-05 | #1952 (11-05) | `frame_version` | → `880e893e1660` | PR #425 (#416), the 15% minimum moneyness (operator word 11-04) | gate (wing selection) |
| run #2038 | 11-12 | #2038 | `quote_filter` | + restate_v1 | PR #426 (#421), restate_v1 (PREREG_FORWARD_CATALYST_GROUNDING §13). The last unscheduled boundary | council final convictions |

**Not stamped, so not in the table.**
- Universe membership with no cluster-map change (ATKR removed 2026-11-09; `records/2026-11-09_atkr_removal.md`).
- Execution-only changes (carry-over, 10-29).
- Telemetry.

## Boundaries outside `runs`

These segment a weekly sweep's own ledger, not `runs`. The script cannot see them.

| Sweep date | Ledger | Change | Cause |
|---|---|---|---|
| 2026-11-01 | PREREG_MISS_BASERATE §7; PREREG_UNIVERSE_CURATION §6 | the OTM side guard in both weekly sweeps | #343/#345, operator word 10-25 |
| 2026-11-08 | PREREG_MISS_BASERATE §8; PREREG_UNIVERSE_CURATION §6 | the 15% floor in both weekly sweeps | #427, operator word 11-05 |

`held_reads` (§10.13) and `council_repeat_sessions` (§10.12) carry their own `model_mix` per row and key to the L1's
`run_id`, so they inherit that L1's segment.

## Staged for boundary B, Mon 2026-12-07 (not yet in `runs`)

Rows move into the table above, with their run ids, once the first run carrying them exists. Source: STANDING_STATE
and #515, as of 2026-11-18.
- `frame_version`: the 40% maximum moneyness (#504).
- A `model_mix` key: the null books skip closed-market exits (#477).
- The held-names-out-of-backfill change (#471). Whether it moves a stamp is UNVERIFIED until its PR exists.
- The orphaned-position path (#444; PREREG_REAL_MONEY_BROKER §3c). It is execution only; no stamp move is expected.
- `council.repeat_probe` switched on (§10.12). It is a post-L1 unit with its own segment, 12-07 → 12-18.
- The model refresh, only if its PR and the price checks are ready.
