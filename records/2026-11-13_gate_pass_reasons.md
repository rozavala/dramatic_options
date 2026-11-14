# 2026-11-13 — Why the cheapness gate passes what it passes (#454; measurement only)

**What this is.** The dated record #454 asked for: the read-only pass-reason audit (`gate_audit.py`,
`scripts/probe_gate_pass_reasons.py`, merged in #474 as `8dde766`) run once over the DEV journal. **Nothing changes:**
no rule, no threshold, no config, no stamp. The decision this informs (S1, rank by own-history cheapness) is #457's
and needs the operator's dated word.

**Run.** 2026-11-13 ~05:20 UTC, `main`@`f2d86cd`, from a worktree. `gate_dualread` (OPRA arm, the gate of record)
opened `?mode=ro`; bars read from `data/cache` with `offline=True` and no client (a cache miss is counted as
unknown; nothing is ever fetched). All 108 nightly sweep dates, 2026-06-10 → 2026-11-12. Thresholds from
`config.json:convexity_gate`: `iv_rv` (IV_atm / RV252) ≤ 1.2, `otm_skew` ≤ 10 vol pts.

```bash
DRAMATIC_DB=$LIVE/data/dramatic_options.db DRAMATIC_CACHE_DIR=$LIVE/data/cache PYTHONPATH=. \
  venv/bin/python scripts/probe_gate_pass_reasons.py [--json] [--names]
```

**It reproduces the issue's counts** on the nightly sweeps next to each Sunday: 10-30 universe structured 39 → pass
37 (the 11-01 Sunday read 39 → 37); 11-06 structured 35 → pass 34 (the 11-08 Sunday read 35 → 34). The Sunday
*market* sample is not in `gate_dualread` (sealed in `records/miss_baserate/ledger.csv`), so this record explains the
universe's pass rate only.

## 1. The pass rate rose while the gate's ratio fell

Universe cohort, pooled name-days per month:

| Month | Sweep dates | Structured | Pass | Pass rate | Median `iv_rv` (pooled) |
|---|---|---|---|---|---|
| 2026-06 | 13 | 455 | 387 | 0.85 | 1.08 |
| 2026-07 | 22 | 757 | 675 | 0.89 | 1.03 |
| 2026-08 | 21 | 682 | 643 | 0.94 | 0.97 |
| 2026-09 | 21 | 809 | 780 | 0.96 | 0.94 |
| 2026-10 | 22 | 874 | 851 | 0.97 | 0.92 |
| 2026-11 (to 11-12) | 9 | 321 | 310 | 0.97 | 0.95 |

- **Headroom.** From 10-20 on, the median pass sits about **0.27** under the 1.2 ceiling on `iv_rv` (pooled; 0.24–0.30
  by night) and about **10 vol pts** under the skew ceiling. The median `otm_skew` is about 0, so the skew leg almost
  never binds.
- **What vetoes, all 108 dates.**
  - Not structured: 748 (no eligible contract in the tenor window 654, no OTM-eligible contract 72, none beyond the
    minimum moneyness 22).
  - `iv_rv`: 201. Fail-closed on a structured row: 42. Skew: 8. Both legs: 1.
- **Most refusals are contract existence, not the gate.** Since 10-20 the gate refuses 1–2 structured names a
  night, while 11–16 of the ~50 names have no structure at all.

## 2. How many passes rest on an elevated trailing 252-day RV

The question #454 asked. A name that recently made a big move carries an inflated RV252 and so a low `IV/RV252`. For
each gate pass, the audit recomputes RV as of the sweep date at 252, 63 and 21 sessions. It flags the pass as
**"depends on elevated RV252"** when `IV/RV63` is above the 1.2 ceiling: the name passes on the long window and would
fail on the 63-day one.

**Coverage window.** 2026-09-22 → 2026-11-06: 34 sweep dates where the bars cache covers at least 75% of structured
rows (in fact at least 95%: no cache misses; 7 dates have 1–2 structured rows with no `iv_rv`, `unknown_no_iv_rv`). The windows outside it are excluded rather than read:
- Before 09-22, most names have fewer than 253 closes (`unknown_short_history`). Every name does until 09-15, and
  about half of the structured rows read `ok` on 09-16 → 09-21 (79 `ok` rows in all before 09-22).
- From 11-09, non-sentinel names miss the cache (`unknown_cache_miss`; bars for those are refreshed by the Sunday
  L0 only). The known subset would be the motion-selected sentinels, the bias #474 warned about.

| Read (09-22 → 11-06, universe) | Count | Share of passes with known bars |
|---|---|---|
| Gate passes with known bars (name-days) | 1,314 | — |
| … pass on RV252 but `IV/RV63 > 1.2` (**depend on elevated RV252**) | **206** | **15.7%** |
| … pass on RV252 but `IV/RV21 > 1.2` | 663 | 50.5% |
| `iv_rv` vetoes that would pass on RV63 (the reverse case) | 0 | — |

- **By name.** 49 distinct names passed at least once. 22 had at least one RV252-dependent day, and 6 were dependent
  on most of their pass days:
  - PL 19/19, NEE 16/16, MOS 20/23, FLNC 25/32, BWXT 9/14, AMSC 11/19.
  - Next: NXE 15/31, LUNR 8/17, FLY 16/34, KTOS 15/33.
- **The real book's entries, as read by that date's nightly sweep** (~20:49 UTC, after the entry). The entry-time
  inline read differs slightly: on 11-04, FLNC was 0.88 inline vs 0.90 in the sweep, and TITN 1.08 vs 1.08. Every
  verdict is the same.

| # | Name | Entry | `iv_rv` (RV252) | `IV/RV63` | `IV/RV21` | Depends on RV252? |
|---|---|---|---|---|---|---|
| 1 | PL C | 07-01 | 1.08 | — | — | unknown (short history) |
| 2 | HL C (cancelled) | 10-26 | 0.83 | 0.93 | 1.16 | no |
| 3 | AG C (cancelled) | 10-29 | 0.77 | 0.95 | 1.12 | no |
| 4 | FLNC P (cancelled) | 11-03 | 0.92 | **1.44** | 1.29 | **yes** |
| 5 | TITN C (cancelled) | 11-03 | 0.96 | 0.85 | 1.52 | no |
| 6 | **FLNC P (open)** | 11-04 | 0.90 | **1.38** | 1.18 | **yes** |
| 7 | TITN C (open) | 11-04 | 1.08 | 0.96 | 1.66 | no |
| 8 | RDW P (cancelled) | 11-11 | 0.76 | 1.03 | 0.70 | no |
| 9 | RDW P (carried) | 11-12 | 0.80 | — | — | unknown (cache miss) |

The open FLNC put is the case #454 predicted: it passed on a 252-day RV inflated by FLNC's earlier moves, and on a
63-day window it reads 1.38, well over the ceiling.

## 3. A tighter cut-off, as a table only (not a rule)

From 09-22 on, the cheapest 25/50/75% of structured names by `iv_rv` would admit 9–11 / 17–22 / 25–33 names per
date. The 50% cut falls at `iv_rv` ≈ 0.93–0.96 from 10-19 on. On every date since 09-22, every name inside the
cheapest 75% also passes the gate of record, so a rank cut-off is a pure tightening. The gate's 1.2
ceiling removes 0–2 names a night.

## 4. What this says, and what it does not

- **Says.** On the record, the gate as frozen is close to a pass-through for anything that has a contract. Since
  September, ~97% of structured universe names pass. About one pass in six (15.7%) depends on the 252-day window
  carrying an old move. On a 21-day window half the passes would fail. The window choice looks to move the verdict
  more than the threshold does (an inference: no threshold sweep was run).
- **Does not say.** Whether those passes are wrong. "Cheap vs trailing realized" is the frozen definition
  (`PREREG_THEMATIC_CONVEXITY` §1), and whether a gate-cheap read leads to repricing is M3's forward test (#455), not
  this audit. RV63 and RV21 are a sensitivity read, not a proposed rule.
- **Bias notes.**
  - Name-days pool repeated reads of the same names: a persistent name counts every night. The per-name table
    above is the unpooled view.
  - The 09-22 → 11-06 window is a single regime of 6–7 weeks.
  - The per-name "most of their pass days" figures rest on different n per name (IRDM has 6 days), so small-n
    names are noisy.
  - Bar D's final close postdates the 15:45 ET evaluation (≤0.2% RV difference for a ≤5% late move; #474).

## 5. Feeds

- **#457 (S1, gate graduation: rank by own-history cheapness):** the evidence that the pass/fail gate barely
  filters, and that the trailing window carries much of the verdict. The frame change is the operator's.
- **#455 (M3, cheap-then-repriced ledger):** a natural split to carry forward is RV252-dependent passes vs the rest.
- **#453 (M1, layer scoreboard):** the gate layer's interim read starts from this pass rate.

**Re-run** right after a Sunday L0, when every universe name's bars are fresh, to extend the coverage window past
11-06.
