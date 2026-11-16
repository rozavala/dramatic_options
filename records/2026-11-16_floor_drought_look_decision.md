# 2026-11-16 — The §10.11 floor-drought look: evidence and the decision (option A, decided in advance)

**Status: DECIDED 2026-11-16 (operator word "Sure, let's keep moving with your recommendations"): option A**, decided in advance of the look. If the 11-16 and 11-17 L1s also have no verdict at the floor, the look owed after 11-17 is this decision: §10.11 is unchanged, the drought is recorded as upstream, and a second 10-session drought after 12-18 triggers another look. If either night reaches the floor, the clock resets and the decision stands for the next drought. PREREG_COUNCIL_GATE_SEPARATION §10.11 pinned: *"If zero names reach the
floor for 10 consecutive sessions, an operator look is owed (the wording may be too tight; nothing reverts
automatically)."* The clock was **8 of 10 at L1 #2055 (11-13)**; the last above-floor verdict was #1918 (FLNC,
11-03). If the Mon 11-16 and Tue 11-17 L1s also have none, the look is owed after 11-17. This draft prepares it so
the decision is not made cold. If either night reaches the floor, the clock resets and this draft waits.

## 1. What the record shows (read-only, `council_agent_outputs` strategist rows, 2026-11-03 → 11-13, 95 reads)

| structural_vs_fad | under_narrated | at_inflection | Reads |
|---|---|---|---|
| structural | false | false | 43 |
| structural | false | **true** | 20 |
| structural | **true** | false | 17 |
| structural | true | true | **9** |
| fad | false | false | 4 |
| fad | true | false | 2 |

- **Criterion (3) alone blocks 17 of 95 reads** (structural and under-narrated, not at inflection). **13 of those 17
  are bearish** theses on names whose own latest filing still grows: RDW ×5 (RPO +90.6%, margins +16 pts), HL ×2
  (TTM +84.1%), BWXT ×2 (RPO +15.8%), UEC ×2, FIG, CDE. The other 4 are TITN bullish (revenue still −10.7% TTM).
- **Criterion (2), under-narrated, fails 67 of 95** (every row with under_narrated=false). That is the biggest
  single blocker, and it is the coverage count, not §10.11's wording.
- **The 9 reads that pass all three are 2 names:** FLNC bearish ×4 and TITN bullish ×5, re-read nightly. Every one
  but #1918 (FLNC 11-03, MODERATE) came back **LOW**. Conviction, not the criteria, keeps them under the floor.
- **Before vs after §10.11** (strategist reads; the sentence took effect 10-30):
  - 10-23 → 10-29: 38 reads, at_inflection true 20 (53%), under_narrated true 17, ≥ MODERATE 2.
  - 10-30 → 11-13: 118 reads, at_inflection true 35 (30%), under_narrated true 35 (30%), ≥ MODERATE 1.
  - Both criteria's pass rates fell, not only (3). The slate also changed: the 11-08 L0 surfaced 8 bears out of 8,
    and bears on still-growing names fail (3) for a stated reason.
- **The slate is narrow:** rank held NVDA/RDW/FLNC/TITN every night of W46. The same few names fail the same way
  nightly.

## 2. Options

**A — no change to §10.11; record that the drought is upstream (recommended).**
- The rejections that (3) alone causes cite the name's own growing figures. That is what §10.11 asked for, and the
  basket-level passes it was written to stop (HL 10-26, AG 10-29) have not recurred (the driver-scope count stays 3).
- The supply problem is the slate (few names, mostly bears on growing companies), under-narrated, and LOW
  conviction on the names that pass. None of these is §10.11's wording.
- Pair with what is already moving: #456's probe (12-07 → 12-18) measures whether LOW vs MODERATE at the margin is
  noise; #505 (slate slots); the 11-23 expiry cliff.
- **Pinned for next time:** a second 10-session drought after 12-18 triggers another look, with the §10.12 reads in
  hand.

**B — revert the §10.11 sentence at the 12-07 boundary.**
- The upper bound on what it buys: 17 reads in 2 weeks would face (3) under the §10.10 wording, mostly the bear
  reads above. They still need a MODERATE conviction to reach the floor. Expected effect: small, and it re-opens the
  basket-level reads §10.11 was written to stop.
- A prompt change: a new record segment (new prompt shas) on boundary B.

**C — defer the decision to the §10.12 look (after 12-18).**
- Keep §10.11, and read the drought with the probe's Read 1 (is the floor verdict stable?). If the floor verdict is
  a coin at the margin, a k-read entry rule matters more than criterion wording.
- Differs from A only in not recording the "upstream" diagnosis now.

## 3. What does not change under any option

The floor (MODERATE), criteria (1)–(2), the tri-criteria `include` rule, the gates, sizing, the risk frame. Nothing
reverts automatically (§10.11).

## 4. Decision

**A**, with the second-drought pin (operator word 2026-11-16). Recorded as a dated note under §10.11 and a STANDING_STATE entry. No code change.
