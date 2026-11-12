# The criterion-(3) segment's first two weeks — the dated 11-04 look

**Date:** 2026-11-04 (the docketed look; formerly the F4 date, session 30, held early on 10-23 as §10.10).
**Scope:** the 9 L1 sessions since the §10.10 re-specification, L1 #1798 (2026-10-23) through #1935 (2026-11-04),
split at the §10.11 boundary (#1884, 2026-10-30). Read from the DB (read-only) and the nightly grades. No outcome
claim: the council is never backtested, and nothing here is scored against prices.

## The sessions

| Run | Date | Prompts | quote_filter | Deliberated | Raw ≥ MOD | Final ≥ MOD | at_inflection = T | under_narrated = T | tri-pass | include |
|---|---|---|---|---|---|---|---|---|---|---|
| #1798 | 10-23 | §10.10 `48f6d57f` | — | 10 | 1 | 0 | 7 | 7 | 5 | 5 |
| #1816 | 10-26 | §10.10 | musd_billions_v1 | 9 | 1 | 1 (HL) | 6 | 4 | 2 | 2 |
| #1833 | 10-27 | §10.10 | musd_billions_v1 | 9 | 0 | 0 | 2 | 4 | 0 | 0 |
| #1850 | 10-28 | §10.10 | musd_billions_v1 | 10 | 0 | 0 | 5 | 2 | 1 | 1 |
| #1867 | 10-29 | §10.10 | musd_billions_v1 | 10 | 1 | 1 (AG) | 6 | 4 | 3 | 3 |
| #1884 | 10-30 | §10.11 `cd34e754` | musd_billions_v1 | 12 | 0 | 0 | 2 | 4 | 1 | 1 |
| #1901 | 11-02 | §10.11 | + iso_dates_v1 | 11 | 0 | 0 | 4 | 3 | 1 | 1 |
| #1918 | 11-03 | §10.11 | + iso_dates_v1 | 12 | 1 | 1 (FLNC) | 5 | 2 | 2 | 2 |
| #1935 | 11-04 | §10.11 | + iso_dates_v1 | 11 | 0 | 0 | 2 | 4 | 0 | 0 |

(Counts are strategist judgments; tri-pass = structural ∧ under_narrated ∧ at_inflection, before the floor.)

## What the two re-specifications did
- **§10.10 (10-23) unblocked criterion (3), as intended.** `at_inflection` passed **26 of 48** §10.10 judgments
  (54%) and **13 of 46** under §10.11 (28%), against **4 of 176** from the direction-coherence boundary (#1437) to
  10-22. The binding criterion moved from (3) to (2), `under_narrated`, which failed most of the 94 judgments.
- **§10.10's tripwire never came close.** It was ≥ 6 of 12 at the floor on either of the first two sessions; the actual
  figure was 0 and 1 (raw and final alike), cleared on 10-26.
- **§10.11 (10-30) tightened as pinned.** The expectation was "fewer above-floor verdicts than 10-23 → 10-29 (2 in 5
  sessions)"; the actual figure is **1 in 4** (FLNC #1918). The basket-level passes it targeted stopped: the driver-scope
  count has stayed at 3 (HL, AG, PAAS) since. The floor-drought clock stands at 1 of 10 (the operator look is owed at
  10 of 10).
- **The filters:** `musd_billions_v1` (10-24) and `iso_dates_v1` (11-02) each removed their artefact: 0 date flags in
  3 nights. Every flag stored since #402 (11 outputs) is now another faithful restatement (decimal→%, 3-decimal $B, bps,
  rounding, a bare year), filed as **#421** (protocol, needs the operator's word).

## The money
- **Above-floor verdicts:** 3 in 9 sessions.
  - HL (#1816): ordered, cancelled unfilled.
  - AG (#1867): ordered, cancelled unfilled (before the carry-over switched on).
  - FLNC (#1918): ordered, carried, filled 11-04 at mid on the first rung: 10× `FLNC270521P00005000` @ 1.00, re-gated to P5 after spot +15%.
- **The first ranked-backfill entry:** TITN (#1918, LOW). Ordered at C25, 7% OTM: the nearest-eligible fallback, filed as **#416**. Carried, re-gated to C30 (27% OTM) and filled 11-04, 3× @ 2.60.
- **Real book 11-04:** 3 open, $2,470, unrealized −$750, drawdown 8%. No exit due.

## The finding this look adds: next-read persistence
Every above-floor (or backfilled) entry so far was **reversed at the same name's next read, on unchanged evidence:**

| Entry | Verdict | Next read |
|---|---|---|
| HL #1816 | MODERATE, inf = T | #1833: LOW, inf = F |
| FLNC #1918 | MODERATE, un = T, inf = T | #1935: LOW, un = F, inf = F (same filing, same 23 analysts; 1 of 11 reads on this filing above LOW) |
| TITN #1918 (backfill) | LOW, include = T | #1935: NEUTRAL, inf = F (after 5 straight inf = T) |
| AG #1867 | MODERATE | no next read (dormant 11-01) |

Randomized presentation order is ruled out for FLNC (both reads against_first) and TITN. The entries sit on the
noisiest criteria (`under_narrated`, `at_inflection`). Verdicts are not re-read after entry, so the positions stand;
no rule broke.

**Proposed watch (adopted with this record's merge; measurement only — no rule changes):** the nightly grade
reports, for every real entry, the strategist's verdict at the same name's next read ("persisted" = still ≥ the
floor, or for a backfill still `include = true` at ≥ LOW). **Pinned trigger:** if fewer than **half of the first 5**
real entries persist, a dated operator look at a confirmation-read rule is owed. That rule would have to settle
whether a carry waits for the next L1 re-read (a carry fills at 10:00 ET, before it). With 2 entries, no rule is
proposed.

## Decisions owed (the operator's)
- **#416:** the moneyness floor. CC's recommendation is a 15% minimum achieved OTM, fail-closed, on every book path. It needs a PREREG_THEMATIC_CONVEXITY amendment and moves `frame_version`.
- **#421:** the filter restatements. CC's recommendation is options A + B + C, landed on the ~11-12 model-refresh boundary, so the record breaks once.

## What does not change
The floor, the tri-criteria rule, the prompts (the §10.11 pins), the gate, sizing, the caps, the carry-over and the
backfill rules. This is a look, not an amendment.
