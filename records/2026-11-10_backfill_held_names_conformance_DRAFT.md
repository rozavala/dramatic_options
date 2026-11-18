# 2026-11-10 — Backfill candidates and names the book already holds: a conformance draft (#471)

> **Status: DRAFT for issue #471. Nothing here is in force.** The ranked backfill's pool is frozen text
> (PREREG_THEMATIC_CONVEXITY §5 amendment 2026-11-03). Which names reach the gates changes only by the operator's
> dated word. Merging this file ratifies nothing: merge-as-ratification is a named failure mode in this project
> (§6 ownership addendum). The entry texts in §6 would be recorded on the word.

## 1. The frozen text (quoted exactly)
From PREREG_THEMATIC_CONVEXITY §5, "Amendment 2026-11-03 — ranked backfill for an idle book":
> - **Pool:** this L1's council proposals that did **not** clear the floor and tri-criteria, with
>   `structural_vs_fad = structural` and conviction ≥ LOW (NEUTRAL = abstain or parse failure, never
>   eligible). Direction coherence has already been applied upstream.

And the next bullet:
> … The top `candidates` (3) go to the gates **after** every above-floor name; the first to clear every gate is the
> week's entry.

The amendment's stated purpose: "one labelled entry path that fills idle slots from the council's own ranking,
inside the unchanged gates". The pool sentence does not exclude held names. The purpose sentence and "the first to
clear every gate is the week's entry" both presuppose that a candidate *can* become an entry.

## 2. The code (verified on `origin/main` d2971be)
- `backfill.rank` (`backfill.py:109`) keeps `eligible(p)` (structural, and conviction ≥ LOW by `_RANK`) and sorts by
  the frozen key: criteria true ↓, conviction ↓, fresh cheap IV/RV ↑ (none last), symbol ↑. `backfill.select` takes
  `rank(...)[: cfg.candidates]` (`candidates = 3` in `config.json:convexity_book.backfill`).
- `council/wiring.py:153-161` passes every dropped proposal of the run to `backfill.select`. It stamps each pick
  `backfill.rank` on the proposal (`backfill.stamp_proposal`) and appends it as a theme with
  `entry_origin = "backfill"`. Nothing removes held names.
- `paper_loop.run_paper_cycle` computes `open_syms = state.entry_blocked_symbols(conn)` once (`paper_loop.py:153`).
  For each theme it first checks the weekly quota (`skip-backfill-quota`), then `if theme.symbol in open_syms`
  records `skip-already-open` (`paper_loop.py:196`) and `continue`s, before any gate runs.
- **Held names are on the slate.** The council union does not exclude open positions. Only the L0 scan does
  (`orchestrator.py`, `exclude = open_position_symbols | sentinel_syms`), which stops a held lineage from being
  re-surfaced. A traded sentinel stays `status = 'candidate'` until it goes dormant
  (`state.expire_stale_sentinels`, 35 days on the ET date). The persistence watch reads exactly these post-entry
  verdicts (STANDING_STATE: FLNC was LOW on all 3 reads after #1918).

**The issue's premise is correct, with three refinements:**
1. **`entry_blocked_symbols` covers open, closing and pending, not "carried".** It reads `_COMMITTED_STATES =
   ('open', 'closing', 'pending')` (`state.py`). The issue's "(open, closing, pending, carried)" is not what the
   code does. It does not matter in practice: a carry intent's attempts are `pending` rows, and the intent ends by
   15:30 ET on its window day (`carry.py` docstring), before the 15:45 ET L1. The fix should reuse
   `entry_blocked_symbols` exactly, so that the backfill's exclusion and the ordinary path's `skip-already-open`
   are one set by construction.
2. **The exposure is bounded per name.** A held name can take a candidate slot only while its lineage is still
   `candidate`, i.e. until about 5 missed weekly L0 scans after it was last surfaced. L0 cannot re-surface a held
   name. So it does not "grow with the number of held names" without limit: each held name bites for at most about
   five weeks after entry. If FLNC and TITN were last surfaced at the 11-01 L0, they stay on the slate until the
   12-13 L0. PL (held since 07-01) is very likely dormant. **UNVERIFIED:** their `last_seen_at` on DEV.
3. **It cannot have bitten before ~11-11.** The quota counted TITN #7 (opened 11-04) through its trailing-7-day
   window, so `backfill.select` returned "weekly quota used" and sent no candidates. STANDING_STATE dates the
   quota's freeing "~11-10".

## 3. The options
- **A (recommended): a conformance note. Names in `state.entry_blocked_symbols(conn)` at selection time leave the
  pool before ranking; the top 3 of the rest go to the gates.** The amendment's purpose is to fill idle slots, and
  its rank sentence names the entry as "the first to clear every gate". A held name can be neither, because the
  per-name dedup that every entry passes (`skip-already-open`) is unchanged. This reads the pool as its purpose
  states, and changes no ranked order among the names that remain. The log line gains the count removed:
  `Backfill: … excluded n held: [...]`.
- **B: keep as is, and say so in §5.** A held name may take a candidate slot and is then skipped. In a week where
  all 3 slots go to held names, the backfill does not happen. Cost: the week's one shot, silently.
- **C: rank everything, then walk the ranked list past held names until 3 unheld names are sent.** This sends the
  same names as A and is A's implementation in other words. It is listed only because the issue's fix filters
  before `select`, while this would filter inside `select`. Recommendation: filter in `council/wiring.py` before
  `backfill.select`, as the issue proposes, so that `backfill.rank` stays the pure frozen key.

Under every option, the held name's own proposal is still recorded (`status = 'dropped'`) with its verdict, which
the persistence watch reads. A only stops it from being *sent to the gates as backfill*.

## 4. frame_version, segments and the boundary run
- **`frame_version` does not move.** `config_loader.frame_version` hashes the comment-free `convexity_book`
  (including `backfill`), `convexity_gate`, `convexity_exits` and `kill_rule` config blocks, and no code. A filter
  in `council/wiring.py` changes no config value, so the stamp is unchanged by construction.
- **It should not move on the merits either.**
  - The amendment's single frame boundary was the enabling edit (`frame-3a810daad056` → `frame-f86f37a0bd4f`). The
    15% floor's later boundary (`frame-880e893e1660`) is the frame today.
  - Under either reading, every backfill entry is the highest-ranked eligible proposal that clears every gate. A
    held name can never be the entry under either. The two readings differ only on nights where a held name sat in
    the top 3 and an unheld eligible name ranked below it.
  - The stop rule (`backfill.stop_status`) and `real_by_origin` read backfill *entries*, and no backfill entry yet
    made could have been different unless §5's query below finds such a night.
  - The #276 precedent (a conformance change moving the stamp through a config switch) fits a change that admits
    a different population. This one only stops wasting slots.
- **Not record-segmenting.** No `runs` stamp moves (no `model_mix` key carries backfill). If the operator prefers
  a visible segment, the alternative is a config key, e.g. `convexity_book.backfill.exclude_held: true`. Written on
  the word, it would move `frame_version` and make the enabling edit the boundary. Not recommended: it adds a
  switch for a rule that should not be optional.
- **The boundary run** is the first L1 after the deploy, named by run id in the conformance note (as the carry-over
  and the sentinel TTL were recorded). Under the #470 draft (not in force), this moves no stamp. It is closest to
  that draft's "frame-conformance defect" class, which may land off-cycle. Recommendation: land it off-cycle, before
  FLNC's and TITN's lineages go dormant (~12-13). After that, nothing is left for it to fix until the next entry.

## 5. The DEV read-only SQL that would show it has bitten
Every backfill candidate since the feature went live, with its outcome (a held candidate shows `skip-already-open`;
`CASE … json_valid` keeps an old non-JSON rationale from raising):
```sql
SELECT p.run_id, e.evaluated_at, e.symbol, e.decision,
       CASE WHEN json_valid(p.rationale) THEN json_extract(p.rationale, '$.backfill.rank') END AS bf_rank
FROM convexity_eval e JOIN council_proposals p ON p.id = e.proposal_id
WHERE e.evaluated_at >= '2026-11-03'
  AND CASE WHEN json_valid(p.rationale) THEN json_extract(p.rationale, '$.backfill.rank') END IS NOT NULL
ORDER BY e.id;
```
It has **bitten** on a run where a candidate was `skip-already-open` **and** an unpicked eligible proposal (dropped,
structural, conviction ≥ LOW, not held) existed that would have moved up into the top 3:
```sql
WITH bf AS (
  SELECT p.id, p.run_id, p.symbol FROM council_proposals p
  WHERE p.as_of >= '2026-11-03'
    AND CASE WHEN json_valid(p.rationale) THEN json_extract(p.rationale, '$.backfill.rank') END IS NOT NULL),
held_runs AS (
  SELECT DISTINCT bf.run_id FROM bf JOIN convexity_eval e ON e.proposal_id = bf.id
  WHERE e.decision = 'skip-already-open'),
spare AS (
  SELECT p.run_id, p.symbol, p.conviction FROM council_proposals p
  WHERE p.run_id IN (SELECT run_id FROM held_runs) AND p.status = 'dropped'
    AND p.structural_vs_fad = 'structural' AND upper(p.conviction) IN ('LOW', 'MODERATE', 'HIGH', 'EXTREME')
    AND p.id NOT IN (SELECT id FROM bf)
    AND p.symbol NOT IN (SELECT symbol FROM convexity_positions c
                         WHERE c.status IN ('open', 'closing', 'closed') AND c.opened_at <= p.as_of
                           AND (c.closed_at IS NULL OR c.closed_at > p.as_of)))
SELECT h.run_id, group_concat(s.symbol || ':' || s.conviction) AS would_have_moved_up
FROM held_runs h LEFT JOIN spare s ON s.run_id = h.run_id GROUP BY h.run_id ORDER BY h.run_id;
```
A row with a non-empty `would_have_moved_up` is a night it bit. A row with it empty is a held slot that cost nothing.
Cross-check against the L1 journal's `Backfill: … candidate(s): [...]` line for that run. The held test
approximates `entry_blocked_symbols` (a `pending` row at that moment can't be reconstructed). Expected today: no rows,
because the quota was used until ~11-11 (§2.3).

## 6. Entry texts, to be applied on the word
**PREREG_THEMATIC_CONVEXITY §5, appended after the 2026-11-03 amendment's bullets (option A):**
> <!-- #471 backfill held-names conformance note -->
> **Conformance note ([date], operator word: "[quote]"; #471).** The Pool excludes names the real book already
> holds or has a working order in (`state.entry_blocked_symbols`: open, closing, pending) at the moment the
> candidates are selected, before ranking. Such a name could never be the week's entry (the per-name dedup every
> entry passes skips it before any gate), so it only took a candidate slot from a name that could. The ranking key,
> `candidates = 3`, the quota, the trigger, the stop rule and every gate are unchanged. The held name's proposal is
> still recorded with its verdict. In force from run [#N], the first L1 after commit [sha]. `frame_version` does not
> move (no config value changes). DEV showed [no night | n nights ([runs])] where a held name took a slot that an
> eligible unheld name would have filled.

**STANDING_STATE "Rulings in force", appended to the "Ranked backfill ENABLED" entry:**
> - **Held names leave the backfill pool ([date], operator word "[quote]"; #471; §5 conformance note):** names in
>   `entry_blocked_symbols` are dropped before ranking, from run [#N]. Frame unchanged (`frame-880e893e1660`);
>   not record-segmenting.

**What does NOT change:** the ranking key; `candidates`, `per_week`, `lookback_days`, `empty_slots_min` and the stop
rule's values; the gates and caps; the ordinary above-floor path and its `skip-already-open`;
`backfill.used_this_week`; held names' verdicts and the persistence watch; `frame_version`.

## 7. The code that follows the word
- `council/wiring.py`, before `backfill.select`: `blocked = state.entry_blocked_symbols(conn)`; drop proposals whose
  `symbol.upper()` is in it; pass the excluded symbols into the `Backfill:` log line. A failing state read falls
  into the existing `except` (no backfill this cycle, fail-closed; the ordinary path untouched).
- Tests in `tests/test_backfill.py`:
  1. **Regression, fails on main:** three held names rank above one unheld eligible name; the unheld name is the
     only candidate and becomes the entry.
  2. A `pending` (working-order) name is excluded too; a `cancelled` one is not.
  3. The ranked order among the remaining names is unchanged.
  4. The quota and `used_this_week` are unaffected; a held name's proposal is still recorded `dropped`.
  5. The `Backfill:` log line names the excluded symbols.
  6. `frame_version(config)` is identical before and after.

## 8. Decisions for the operator
- **D1** Option A (recommended), B or C.
- **D2** `frame_version` unchanged and no new switch (recommended), or a `backfill.exclude_held` key as a frame
  boundary.
- **D3** Land off-cycle, before ~12-13 (recommended), or at the next scheduled boundary if #470 is adopted.
- **D4** Run §5's two queries on DEV first, and record the result in the note.
