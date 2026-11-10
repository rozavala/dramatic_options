# 2026-11-10 — Held-name thesis tracking: definitions (DRAFT)

**Status: DRAFT for issue #464 (P1). Merging this file ratifies nothing; nothing here is in force.** It proposes how
every open real position's (symbol, direction) would be re-read by the council after entry, how each read is stored
and shown, and how the reads are scored at close. It fixes, BLIND and before any read exists, what the reads may never
be used for. Proposed numbers are marked `[PIN]`. **The operator decides:** (1) Option A (a held slot class in the
council of record) or Option B (a separate post-entry pass), §3; recommended: B; (2) the per-pass cost cap and
whether to start after the ~11-12 model refresh (§4); (3) how dormant-lineage packs are labelled (§5); (4) the
scoring definitions (§7); (5) the pinned prohibition (§8), adopted as written or tightened.

**Measurement only.** No read may change an entry, a veto, a size, an exit, an add, a re-strike, a carry, the backfill
rank, or the council's verdict of record. Guardrail 6 holds: the reads are scored forward, at each position's close,
and are never backtested.

## 1. How a held name is (and is not) re-read today (read from the code)

- **The candidate set.** `orchestrator.py` (L1 path) builds `sentinels.union_candidates(active hand-seeds,
  sentinels.active_sentinel_candidates(conn))`.
  - **Order:** hand-seeds first, then live sentinels by `inflection_score` (`state.active_sentinel_rows`:
    `status='candidate'`), deduped on (symbol, direction), restricted list applied; then `direction_coherence`
    withholds some and `_refresh_council_markers` runs.
- **The slate.** `council/wiring.council_to_themes` builds it in three steps.
  - **Expressible-first:** `demote_unexpressible` holds sentinels with no eligible structure to the back.
  - **Composition:** `council/council.compose_judged_set` (with `max_candidates = 12`, `cheap_reserve_slots = 3`,
    `fairness_slots = 2`) takes hand-seeds, then the top motion-ranked sentinels, then 3 cheap-reserve slots (by
    least-recently-judged), then 2 fairness slots (fresh event first, then least-recently-judged), then a backfill
    in motion order.
  - **Cut:** `council.propose` slices the result to `[:max_candidates]`.
  - **No position check:** no step consults `convexity_positions`. A held name gets no priority, so being in the
    union (38 active per STANDING_STATE) does not mean it is judged that night.
- **Why a lineage cannot outlive its TTL while held (sharper than the issue).** `run_discover` passes
  `exclude = state.open_position_symbols(conn) | state.active_sentinel_symbols(conn) | hand-seeds` to
  `discovery.scan_baskets`, so a held name can never re-surface. Its `last_seen_at` stays frozen at its last surfacing,
  which predates the entry (`state.fresh_event_symbols`' docstring records this freeze for active lineages).
  `state.expire_stale_sentinels` (weekly, `ttl_days = 35`, compared as ET dates) then flips it to `dormant`.
  `active_sentinel_rows` drops it, and while the position is open it cannot come back. The result: a sentinel-origin
  position is re-read at most until about 35 days after the lineage last surfaced, then never again until it closes.
  For example, the entry AG #1867 shows "no read since (dormant 11-01)" in `records/2026-11-09_persistence_watch_amendment.md`.
- **Hand-seeds differ.** An active `themes.json` entry is always first and protected (only NVDA is active today; FCX
  is `active: false`). A held hand-seed name is therefore re-read every L1, with the news-based pack.
- **The council does spend on an open name.** The skip in `paper_loop.run_paper_cycle` comes after the council. Only
  themes that survive (above the floor, or a backfill pick) reach `if theme.symbol in open_syms` (from
  `state.entry_blocked_symbols`), which records `skip-already-open` in `convexity_eval`. A below-floor re-read of a
  held name is simply a `dropped` row in `council_proposals`.
  - **So re-reads of held names are already in the forward record,** in proposal Brier and in the persistence
    watch's substrate, whenever the slate happens to seat them.
  - **And in the backfill pool:** `backfill.rank` and `backfill.select` do not exclude held names, so a held name's
    structural LOW re-read can take one of the 3 backfill candidate places and then be skipped at the gate.
- **The persistence watch** (STANDING_STATE; the 11-09 amendment) reads the strategist at the same name's next 3 reads
  in `council_proposals`. It is the only post-entry read that is reported. UNVERIFIED: no code implements it (a grep
  for it finds nothing); it is computed in the nightly grade.
- **The falsifier ledger** (`falsifier_ledger.py`, D3b) appends one numeric read per spec × name and never sells,
  gates or vetoes. Rule S (`records/2026-11-03_calibration_v2_finding.md`) is NOT A CANDIDATE at a = 0.7: salvage
  hinges on false-alarm accuracy. A council re-read is another "thesis broken" signal of unknown accuracy (§7).

## 2. Who is tracked

Every real position with status `open` or `closing` (`state._EXPOSURE_STATES`) and a non-null `proposal_id`. The key
is the position's (symbol, direction); the source is its own proposal (any origin: above-floor, backfill, carry). One
without a `proposal_id` (pre-council T1) is listed `no_lineage`, not read. The book on 11-08: FLNC, TITN, PL
(`records/2026-11-08_sunday_w45.md` §8); at most 15 open (`max_open_positions`).

## 3. Options

**A — a reserved "held" slot class in the council of record.**
- **Slate:** after `compose_judged_set`, every tracked (symbol, direction) is appended in its own class
  (`selection = "held"`). `propose`'s slice becomes `max_candidates + H` (H = tracked count, ≤ 15), so no candidate
  is displaced. A tracked name already seated competitively keeps its seat and adds no held slot `[PIN]`.
- **Stamp:** `runs.model_mix.union_rank` gains `+held_v1` (a new record segment).
- **Cost:** ≈ $0.023 per proposal (W45: $1.37 for five L1s at 12 seats; ATKR's one seat $0.024), so ≈ $0.07 a night
  at 3 positions, ≈ $0.35 at 15, all under the per-cycle `cost_cap_usd = 5.0`, where `BudgetExceeded` inside
  `propose` fails the whole cycle closed (no entries).
- **Side effects:**
  - Held reads enter `council_proposals`, proposal Brier, the §10.10/§10.11 counts and the backfill pool.
  - An above-floor held read becomes a theme and logs `skip-already-open`.
  - The persistence watch would resolve within 3 L1s for every entry. That changes the watch's substrate, which the
    11-09 amendment did not contemplate.

**B — a separate post-entry pass (recommended).**
- **When:** after `run_paper_cycle` and the dual-read sweep, when entries are done (the slot #456 proposes for its
  probe), skipped in demo and under kill.
- **How:** for each tracked position it builds the pack with the same `council/context.build_context_pack` and the
  same council config, runs `council/debate.run_candidate`, and writes the result to its own table `held_reads`
  `[PIN]`, never to `council_proposals`.
- **What stays untouched:** the judged set, `union_rank`, proposal Brier, the §10.x reads, the backfill pool, the
  persistence watch and the forward record.
- **Cost:** the same ≈ $0.023 per name, on its own `CostLedger` with a cap of $1.00 per pass `[PIN]`. Because the pass
  runs after entries, a cap hit or a provider error loses only that night's held reads.

**Why B keeps the verdict of record cleaner.** Under A, membership of the council of record depends on what the book
holds, so the slate and the record become partly a function of past entries. Held reads would mix with candidate
reads in every proposal-level statistic, and they would reach the backfill rank, the floor survivors and the
`skip-already-open` log. B adds no row to any table a rule reads. Its only shared resource is the router. B leaves
today's incidental seatings unchanged; they keep landing in `council_proposals`, as they do now.

## 4. What is stored per read (`held_reads`, append-only)

- **Position and lineage:** `position_id`, `run_id`, `as_of`, symbol, direction, `origin`, `sentinel_id`, lineage
  status (`candidate`/`dormant`), `markers_asof`.
- **The verdict:** the three criteria; conviction raw and final; `include`; `structural_vs_fad`; `weakest_point`.
- **Provenance:** per-role provider and model; the three prompt shas; the `quote_filter`, `corpus` and `markers`
  stamps; `flagged_details`; cost.
- **Duplicate flag:** `of_record_same_night` → that night's of-record `proposal_id` for the same (symbol, direction).
- **Kept out of the pack:** the position's mark multiple and live DTE at read time are stored for the timeline
  only. **Pinned:** the pack never says the name is held, nor its entry, mark or P&L. `ContextPack` has no such
  field today, and a test asserts it stays that way.
- **Start** after the ~11-12 model refresh, so the reads are one model segment from day 1.

## 5. The dormant-lineage pack

- **Building the pack:** a pack can be built for a name with no live sentinel. `sentinels.discovered_to_theme(row)`
  projects any `sentinel_candidates` row without checking status, giving `source='sentinel'`, `sentinel_id`, the
  persisted markers, `basket` and `seed_thesis`. `build_context_pack` then takes the sentinel branch
  (`sentinel_context_pack`) with fresh fundamentals, the analyst count, the register thesis and the catalysts.
- **Markers:** `marker_refresh.refresh_candidates` (`council.marker_refresh = "both"`) recomputes the price markers
  with no status check. The pack shows `markers_computed <date>` and the at-surfacing markers dated at `last_seen_at`.
  It carries `has_event` / `event_kind` over from the persisted (surfacing-time) markers, because the L0 owns that
  leg.
- **Proposal:** render as-is. Store the lineage status and the event leg's age. Do not alter the pack to say
  "dormant", since that would break same-pack comparability with the of-record reads.
- **Other origins:** a hand-seed position uses its `themes.json` entry, news branch. UNVERIFIED: the path for a
  hand-seed later set `active: false`, since `active_themes` would drop it; the proposal is to load it by
  (symbol, direction) from `load_themes`. A backfill or carry position follows its proposal's `sentinel_id`.

## 6. Display

A per-position timeline under Positions. It shows the entry verdict (the of-record proposal), each later read (A: the
held-class proposals; B: `held_reads`, with of-record seatings drawn alongside and labelled by source), D3b
falsifier reads for that symbol, and the L2 mark multiple. A read is drawn as its three criteria and its conviction.
There is no trend line, no "thesis broken" badge and no colour keyed to exit.

## 7. Later scoring (counts only, at close)

When a position closes (any `exit_reason`), take the last 3 reads before `closed_at` `[PIN]`. Their majority is
"intact" if at least 2 are at or above the floor (for a backfill origin, `include = true` at LOW or higher, the
persistence-watch convention), otherwise "broken". The outcome is the realized multiple
(`(total_premium + realized_pnl) / total_premium`), classed as ≥ 1.0 vs < 1.0 `[PIN]`, with ≥ 10× (the profit-take)
reported alongside. The report is a 2 × 2 table of counts, with closes that had fewer than 3 reads counted separately.
No rate prints until at least 20 closed positions with 3 reads `[PIN]`. The quantity the counts feed is the false-alarm
rate P(broken | outcome ≥ 1.0), which is the number Rule S says salvage depends on.

## 8. The pinned prohibition

Until a separately pre-registered rule exists, written after C1 and after the §7 counts reach their minimum, no held
read (under either option) may:
- trigger or delay an exit, an add, a re-strike or a carry;
- veto or size anything;
- be rendered into any council prompt;
- feed the backfill rank, the gates or the persistence watch.

`monitor.py`, `paper_loop.py`, `backfill.py` and `carry.py` never import the writer or read `held_reads`, which an
import-graph test asserts. Under A the held-class proposals are excluded from `select_for_trade` survivors and from
the backfill pool, a change that is itself a ruling.

## 9. Interactions and stamps

- **#456 (same-night repeat probe):** B never re-reads a name the council of record judged that night by default
  `[PIN]`. It sets `of_record_same_night` and stores no duplicate read, so #456's population and its kappa stay its
  own. If the operator prefers B to read every held name every night, the duplicates are flagged and excluded from
  #456 unless #456's prereg says otherwise.
- **The persistence watch:** unchanged under B; it keeps counting `council_proposals` only. Under A its definition
  would need a dated amendment.
- **Stamps and segments:**
  - A moves `union_rank` (new segment for every proposal-level read) and makes `max_candidates` a floor rather than a
    total.
  - B moves no `runs.model_mix` stamp and no `frame_version` (`config_loader.frame_version` hashes only
    `convexity_book`, `convexity_gate`, `convexity_exits` and `kill_rule`). Each `held_reads` row carries its own
    stamps, and the run note carries the counts `held_reads n/m, cost $x`.

UNVERIFIED: PL's lineage and last council read (no production DB here); per-proposal cost is from W45's weekly spend.
