# 2026-11-09 — Persistence watch: count the next 3 reads, not the next one

**Status: measurement only. The nightly grade's count changes; no rule, floor, prompt or gate changes, and no stamp
moves.**

## Decision provenance

**Operator word (2026-11-09):** *"Sure, let's do the three items"*. The third item was CC's recommendation after the
W45 Sunday review: *"decide whether to count persistence as the majority of the next 3 reads instead of a single next
read."*

The watch it amends is from `records/2026-11-04_council_two_week_look.md` ("The finding this look adds: next-read
persistence"), adopted with that record's merge.

## Why

The single next read proved too noisy to measure persistence.
- **FLNC** has 17 council reads since 08-05, and 4 of them had all three criteria true.
- **The flip-back:** FLNC and TITN both read all-true again at #1969 (11-06), on the same filings that "reversed"
  them at #1935.
- **Presentation order is ruled out:** the 11-06 grade did this for FLNC, which read both false/false and true/true
  under `against_first`.

A count built on one read mostly measures that noise.

## The amended watch

For each real entry, the grade reads the strategist's verdicts at the same name's **next 3 reads**.
- **Persisted:** at least 2 of the 3 are still at or above the floor. For a backfill entry, persisted means
  `include = true` at LOW or higher.
- **Decided early:** an entry is settled as soon as 2 reads agree.
- **Unchanged:** the pinned trigger. If fewer than half of the first 5 real entries persist, a dated operator look at
  a confirmation-read rule is owed, and that rule must settle whether a carry waits for the next L1.

## Recount under the amended rule (`council_proposals` conviction; TITN's `include` from `council_agent_outputs.raw`; read-only)

| Entry | Next reads | Result |
|---|---|---|
| HL #1816 (MODERATE) | #1833 LOW · #1850 LOW · #1867 LOW | reversed (0 of 3 at the floor) |
| FLNC #1918 (MODERATE) | #1935 LOW · #1952 LOW · #1969 LOW | reversed (0 of 3) |
| TITN #1918 (backfill, LOW `include = true`) | #1935 NEUTRAL · #1952 LOW `include = false` | reversed, decided at #1952 |
| AG #1867 (MODERATE) | no read since (dormant 11-01) | not measurable |

The count is unchanged at 0 of 2 measurable real entries persisting, plus TITN's backfill reversed.

**A correction to the framing that led here.** CC's 11-08 note said FLNC and TITN "came back" at #1969. That is true
of the *criteria*, which were all true. But FLNC's *conviction* stayed LOW, below the floor, on every re-read. For a
real entry, persistence is measured against the floor, so FLNC never came back under either rule. The amendment
still stands on the noise argument; it simply doesn't change today's count.

## What does not change

The council, its prompts, the floor, the gates, the carry-over and the backfill all stay as they are. Positions
stand; verdicts are not re-read after entry for any trading purpose. Only the grade's measurement is redefined.
