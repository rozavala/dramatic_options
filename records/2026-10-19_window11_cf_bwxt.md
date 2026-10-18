# 2026-10-19 — Window #11 (off-cycle): CF · BWXT

**Status: WORD GIVEN (2026-10-18 ~20:59 UTC); screen pending. Nothing is admitted until an in-band read and the
merge.** Admission needs, per name: an in-window read in band (achieved OTM 15–35%), under the $1,000 cap and with
≥ 200 days of runway (PREREG_UNIVERSE_CURATION §2, §11, §12). The theses are on the record already; CC re-drafted
them in true form from the filed corpus.

## Decision provenance (TRUE form)

**Operator word (2026-10-18 ~20:59 UTC):** *"I already rebooted PROD. And regarding CF and BWXT, yes let's admit
them"*, on CC's W42 recommendation (`records/2026-10-18_sunday_w42.md` §7): both names, BWXT routed to
`nuclear_fuel` (the 10-14 decision), CF to the existing `ag_cycle_trough` basket, and the `ag_cycle_trough`
council_thesis amendment below. Given before the reads, so the reads are the screen of record. Merging the PR
(after the 15:07 read) is the admission act and waits for the operator's merge go.

## Why now
From Monday 10-19 the April-2027 tenor cliff leaves about 35 of 48 universe names expressible (43 on 10-16).
Both names printed in band and under the cap on the W42 provisional Sunday read. The F4 caveat stands: an
admission adds names the council can judge, not names it will pass.

## Pre-declared reads (Mon 2026-10-19)
- **13:37 UTC**: admit any name that prints in band at this read.
- **15:07 UTC, the LAST read of the day**: governs only names out of band at 13:37. No re-reads after it.
- Tool: `scripts/probe_basket_feasibility.py CF BWXT`, read-only.

| read (UTC) | symbol | contract | spot | achieved OTM | dte | $/contract | verdict |
|---|---|---|---|---|---|---|---|
| 10-18 W42 (provisional, Sunday) | CF | CF270617C00145000 | $120.85 | 20.0% | 242 | $975 | provisional only |
| 10-18 W42 (provisional, Sunday) | BWXT | BWXT270521C00175000 | $137.01 | 27.7% | 215 | $790 | provisional only |
| 10-19 13:37 | | | | | | | |
| 10-19 15:07 (LAST) | | | | | | | |

## CF — CF Industries · basket `ag_cycle_trough` / cluster `ag_cycle` (existing, with TITN and MOS)

- **How it surfaced:** the window-5 ag slate (08-20). Flipped out in-window that day ($930 / 26.0% provisional →
  $1,240 / 18.4% at the read of record, on a spot pop $119 → $127); near-miss ledger; bench Tier A.
- **Thesis:** the basket thesis as adopted on 2026-08-20 — two years of farm-income recession cut nutrient
  application below agronomic norms, and those inventories must restock. CF is the **nitrogen** expression of the
  crop-nutrient leg, beside MOS (phosphate/potash). Filed record: quarterly revenue **$2,222M, +17.6% y/y**, TTM
  **+20.0%**, capex +10.6% (period 2026-06-30, filed 2026-08-06).
- **Proposed `council_thesis` amendment (basket line, dated operator amendment, applied only if CF is admitted):**
  "…lifting equipment dealers (TITN) and crop-nutrient producers (**MOS, CF**) when the cycle turns."
- **Falsifier:** the basket's (by ~Aug-2027: equipment orders / dealer inventories normalizing, or nutrient
  volume/price recovery in the quarterlies).
- **Pinned caveats (honest):** (1) CF's revenue is already up 20% — nitrogen pricing has recovered ahead of the
  basket's other legs, so `at_inflection` may well read CF's turn as already behind it (the basket's own
  turnaround-class warning: it self-falsifies by success). (2) Remaining performance obligations −34.8% y/y — fewer
  contracted volumes ahead. (3) The corpus's gross-margin line is a 2018 period. (4) A cap-line name: $930 →
  $1,240 → $975 across reads; the read of record governs.
- **Cluster:** `ag_cycle` with TITN and MOS — three names in one $2,000 cluster budget (the cluster cap, not the
  name count, binds).

## BWXT — BWX Technologies · basket/cluster `nuclear_fuel` (existing)

- **How it surfaced:** the window-1 longlist and window-5 slate; window #10 near-miss on 10-14 ($1,100 over the cap
  at both reads, 19.0–20.1% OTM). This is a fresh word on a fresh screen.
- **Thesis (as drafted 10-14, unchanged):** the reactor-technology and fuel-chain supply layer of the buildout the
  `nuclear_fuel` basket names. Remaining performance obligations **$8.40B, +39.6% y/y** against revenue **+18.0%**
  (quarter) / **+22.7%** (TTM), capex **+26.6%** (period 2026-06-30, filed 2026-08-05): demand contracted ahead
  of delivery. No newer filing since.
- **Falsifier:** in the 10-Q for the quarter ending 2026-09-30, remaining performance obligations grow slower than
  revenue y/y. The basket falsifier also stands.
- **Pinned caveats:** (1) nuclear demand is among the most covered energy stories (CEG drew "consensus" every
  session this week), so `under_narrated` may well fail. (2) Much of the backlog is naval/government work the RPO
  line doesn't split out. (3) Stale 2023 gross-margin line. (4) Cap-line: $1,120 (Aug) → $1,045 → $945 → $1,100 (10-14
  reads) → $790 (10-18 provisional).
- **Cluster:** `nuclear_fuel`, shared with CCJ · UEC · UUUU · NXE · UROY · SMR · NNE. **No council_thesis change.**

## What the merge changes (in band names only)
- `config.json` `universe.themes` + `convexity_book.clusters`: CF → `ag_cycle_trough` / `ag_cycle`; BWXT →
  `nuclear_fuel`. Universe 48 → up to 50; clusters stay 16 (both join existing clusters, so the frame stamp moves —
  the cluster map is in the hash — while every risk number stays unchanged).
- `universe_register.json`: `windows.11` with each screen of record; the `ag_cycle_trough` council_thesis
  amendment if CF is admitted.
- First council exposure: the Sun 10-25 L0 scan; earliest council read Mon 10-26.
