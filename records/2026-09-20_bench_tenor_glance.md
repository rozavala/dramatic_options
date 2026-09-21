# 2026-09-20 — Bench tenor glance #1 (PROVISIONAL Sunday quotes; admission needs an in-window read + the operator's word)

Trigger: the September long-dated listing cycle landed 09-16→09-18 (dual-read coverage 36→46/46). Screened the
bench's Tier A/B names (SARO excluded — the 09-06 word lapsed 09-14; no re-read without a fresh word).
`scripts/probe_basket_feasibility.py` from the live checkout, 14:5x UTC Sunday. Cheapness deliberately not read.

| symbol | tier | contract | dte | $/contract | achieved OTM | read |
|---|---|---|---|---|---|---|
| **CNH** | C→? | CNH270319C00017500 | 180 | **$50** | **30.1%** | IN BAND, under cap — first time ever (was tenor-flicker/ATM); dte exactly 180 → the Mar-2027 expiry falls below the floor on Monday; the read of record would be the Apr-2027 chain |
| **CF** | A | CF270319C00160000 | 180 | **$670** | **25.3%** | IN BAND, under cap — flipped back IN (08-20 in-window $1,240/18.4%); same dte-180 caveat |
| **BNTX** | A | BNTX270319C00120000 | 180 | **$635** | **24.9%** | IN BAND, under cap — CLEAN again after four over-cap reads; the 08-23 word LAPSED 09-13 → needs a FRESH word; same dte-180 caveat |
| BWXT | A | BWXT270521C00185000 | 243 | $1,045 | 25.4% | near-miss (cap) again |
| TEM | A | TEM270416C00095000 | 208 | $1,292 | 22.0% | over cap |
| IOVA | A | IOVA270319C00010000 | 180 | $272 | −2.4% | ATM fallback (was 13.8%) |
| MWA | A | MWA270521C00017500 | 243 | $530 | −20.1% | ITM fallback |
| HLIT | B | HLIT270416C00002500 | 208 | $885 | −77.5% | tenor now EXISTS (Apr-2027) but only a deep-ITM 2.5 strike quotes → still no expression |
| TWI | B | TWI270416C00002500 | 208 | $480 | −64.3% | same — coarse grid |
| KMT | B | KMT270416C00022500 | 208 | $860 | −24.4% | tenor exists, ITM fallback (thesis leg falsified 09-13 anyway) |
| ADTN | B | ADTN270521C00003000 | 243 | $445 | −58.3% | ITM fallback |
| CLFD | B | CLFD270319C00020000 | 180 | $1,215 | −33.7% | ITM + over cap |
| GBX | B2 (the July "September window" watch) | GBX270416C00040000 | 208 | $590 | −4.4% | ATM — watch discharged for now: chain exists, band not |
| TRN | B2 | TRN270416C00023000 | 208 | $625 | −17.9% | ITM fallback — same |
| STNG | B | STNG270416C00095000 | 208 | $745 | 9.0% | band-broken (was band-excluded 06-22) |
| SBLK | B | SBLK270617C00026000 | 270 | $705 | −20.0% | ITM fallback |
| VSEC | B | VSEC270416C00200000 | 208 | $1,895 | 14.4% | over cap + under band |
| ASPI · PSNL · TROX | B | — | — | — | — | still no eligible contract in the tenor window |

**To the operator (no action taken; nothing auto-admitted):** three bench names print in band and under cap
provisionally — **CNH** (ag equipment; a thesis would need drafting — the July slate carried it only as an
AGCO/TITN neighbour), **CF** (nitrogen; the window-5 thesis stands in the record) and **BNTX** (the rival
INT program; thesis on file in probe_themes, word lapsed 09-13). Any of the three needs a fresh word and an
in-window read on the Apr-2027 chain (the Mar-2027 expiry drops below 180d on Monday). GBX/TRN's July
watch is discharged: contracts exist now, the band does not.
