# 2026-11-09 — ATKR removed from the scan universe (delisted: Atkore taken private)

**Status: ATKR leaves `config.universe.themes.grid_equipment` on merge. The universe goes from 50 names to 49,
and `grid_equipment` becomes AMSC and FLNC. `frame_version` is unchanged (`frame-880e893e1660`), and no
`model_mix` stamp changes.**

## Decision provenance

**Operator word (2026-11-09):** *"Sure, let's do the three items"*. This was the reply to CC's list after the W45
Sunday review (`records/2026-11-08_sunday_w45.md` §0), whose first item was *"Draft ATKR's removal: a dated
curation record, plus removing it from `grid_equipment`, the `ai_capex_power` cluster and
`universe_register.json`."* While drafting, CC found two parts of that list that should not be done. Both are
narrowed below, with the reasons, for the operator to see on the PR.

PREREG_UNIVERSE_CURATION §3: *"Removals stay frozen-frame-grade (an operator-authorized dated amendment, never
routine)."* This is that amendment.

## The facts

| Date | Filing (our cache, `data/cache/filings/ATKR.json`, CIK 0001666138) |
|---|---|
| 2026-09-09 | DEFM14A (merger proxy) |
| 2026-10-19 | 8-K (items 1.02, 2.01, 3.01, 5.01) and 25-NSE (delisting) |
| 2026-10-29 | 15-12G (deregistration) |

Since 10-19, ATKR's `iv_term_snapshot` has shown a frozen `spot: 94.96` with `expiries: []`. Both dual-read feeds
report it as `no_eligible_contract_in_tenor_window`; that mislabel is filed as #437. It has been in every L1
`Expressible-first: held …` list since then. **Cost so far: about zero.** Held names go to the back of the slate,
and an empty chain fails closed, so no council seat, gate verdict or order rode on it. It did inflate the
universe count and the expressible denominator.

## What changes

- `config.universe.themes.grid_equipment`: `["ATKR", "AMSC", "FLNC"]` becomes `["AMSC", "FLNC"]`, with a per-name
  `_comment_removal_atkr` tag (`delisted-removed`), following the §3 exception-tag pattern.
- **Effect:** ATKR leaves every consumer of the scan basket.
  - **Discovery and sentinel scans:** they stop scanning it.
  - **Slates:** it no longer takes a held slot.
  - **Dual-read sweep:** it drops out of the sweep, so the sweep has 49 names.
  - **3B / shares universe:** new-entry evaluation stops; no new entry was possible anyway with no chain.

## What does NOT change, and why

1. **`convexity_book.clusters.ai_capex_power` keeps ATKR.** The cluster map is part of the frozen frame, so
   editing it would move `frame_version`. More importantly, three null books hold **open ATKR positions**:
   - shadow #18 and 3B `basket_nogate` #17 / `union_nogate` #47, all `ATKR270115C00100000`, last marked 0.015 on 10-19;
   - shares #23.

   Those positions count against the cluster budget through `clusters.members_of`. Taking ATKR out of the cluster
   would quietly free that budget in the null books.
2. **`universe_register.json` is untouched.** `windows.1.admitted.ATKR` is the record of what happened at window #1.
   History isn't rewritten; the removal is recorded here and in the config tag.
   - The `grid_equipment` thesis mentions conduit, which was ATKR's product. Its `council_thesis` is what the
     council sees, so editing it would segment the record. It stays as it is; the thesis still reads true for AMSC
     and FLNC.
3. **The open null positions stay on the record. There is no pruning.**
   - **No outcome-correlated removal:** PREREG_UNIVERSE_CURATION §3 and the fixed-basket integrity rule forbid it.
     A take-private is exactly the kind of outcome the nulls exist to record.
   - **Shares:** the shares report reads `shares_positions` directly, not the universe. Once ATKR's bars stop,
     the §6 terminal guard counts #23 as a *terminated* entry at its last close, which is the guard this case is
     built for.
   - **Option nulls:** they keep their positions. A cash-out option settles at intrinsic against the deal
     consideration. Against the frozen 94.96 spot the C100s are worth nothing, and they close by their existing
     expiry path (2027-01-15) at intrinsic 0. The realized value matches an early cash-out; only the close date
     differs.
4. **No other universe name, basket, cluster, cap or prompt changes.** No stamp changes.

## Reading the record across the boundary

From the first L0 or L1 after merge, the universe has 49 names. Counts that use the universe as a denominator step
down by one at that boundary: the expressible count, the dual-read `swept` figure and the discovery `scanned`
figure. Earlier rows are left as written.

## Verify after merge

```
journalctl -u dramatic-options-l1 --since today -o cat | grep -E "Expressible-first|Gate dual-read sweep"   # no ATKR; swept 49
```
