# 2026-11-03 — Calibration v2 finding (PREREG_CONVEXITY_CALIBRATION §4 amendment 2026-11-03)

**Run:** `python -m calibration.v2` at commit `8dd3548` (code) after the blind amendment at `51d9b7d`;
5,000 paths per cell, seed 7, run 2026-11-03 05:38 UTC. Payoff mechanics only: **no edge claim** (PREREG §1).
A CANDIDATE earns a DRAFT live amendment, never a change.

## Verdicts against the pre-stated rules
| Rule | Question | Verdict | One line |
|---|---|---|---|
| J | Does the June exit ranking survive jumps? | **CONFIRMED** | Hold still beats delta@0.5 under jumps (mean 1.16× vs 1.01×; p* 19% vs 63%). The GBM cells reproduce the June numbers exactly (1.22×, p99 14.4×, p* 19%), a reproducibility check on the reworked engine. |
| S | Falsifier salvage | **NOT A CANDIDATE** | It lowers p* in every corner cell, but at a = 0.7 with a strong thesis (μ_right = 80%) false alarms cost winners 17% (3.81 vs 4.59; the bar was ≤ 15%). It passes everywhere at a = 0.9. |
| R | House-money roll at 3× / 5× | **NOT A CANDIDATE** (both) | P(M ≥ 1) *falls* about 5 pp: about 7% of rolled paths end at 0.9–1.0×, the stake back minus costs. Mean ≤ live; p99 rises (10.7 → 12.6× at R5 under jumps). It trades middle outcomes for tail. |
| V | Wide vertical for over-cap names | **CANDIDATE** | Short +75% wing, s = 0, jumps: premium 0.71× naked, mean M 0.98× naked. Cost: p99 10.7× → 7.0×. With +5 vol pts of call skew on the short wing, the vertical beats naked on mean (1.30× vs 1.13×). |
| T | 540 d vs 365 d | **NOT A CANDIDATE** | Better at μ = 10% and 25%, worse at μ = 0 (0.81–0.85× vs 0.86–0.88×); premium is 1.38× the 365-d contract. |

## Readings (descriptive; none moves a verdict)
1. **The expectation in the amendment was wrong.** It said BS-at-σ_real would show a higher mean M under
   jumps. It is slightly *lower* (hold 1.16× vs 1.22×). At 25% OTM and 270 d the strike sits about half a
   standard deviation out, in the distribution's shoulder, where variance-matched fat tails thin the mass.
   Recorded as found.
2. **Salvage is a falsifier-quality question.** Every salvage cell improves p*; whether it is worth adopting
   depends on how often a fired falsifier is a false alarm on a winner. That accuracy is measurable forward:
   every registered thesis carries a dated falsifier. A forward falsifier-accuracy ledger is the honest
   next step; the rule is not re-run at a different bar.
3. **The later the falsifier read, the less salvage is worth** (d_f 150 is below d_f 90 throughout). Dated
   falsifiers should be early: the first quarterly print, not the annual.
4. **The salvage cells are an upper bound** (the falsified thesis is sold at its diffusion mark).
5. **Rule T asked "replace 365 with 540?" (no).** The draft D2 fallback asks something else: "540 or no bet,
   when [180, 365] is empty?" This run does not answer that. The 540-d contract's economics look like the
   365-d one's: mean M below 1 at μ = 0, above 1 with drift, similar p*. That is framing, not a pass. D2
   needs its own pre-stated rule if the operator wants it.
6. **Roll:** a post-hoc check at P(M ≥ 0.9) gives the roll +0.7 to +1.2 pp, still short of the 3 pp bar.

## Full tables

## Rule J (exit ranking under jumps): **CONFIRMED**

| path | rule | mean M | median | p99 | P(M≥1) | P(loss) | p* |
|---|---|---|---|---|---|---|---|
| gbm | hold | 1.22 | 0.00 | 14.4 | 23% | 71% | 0.1867 |
| gbm | live_10x | 1.14 | -0.04 | 10.6 | 24% | 58% | 0.2107 |
| gbm | delta_0.5 | 1.02 | 1.41 | 1.8 | 68% | 29% | 0.6701 |
| jumps | hold | 1.16 | 0.00 | 13.6 | 22% | 73% | 0.1895 |
| jumps | live_10x | 1.13 | -0.04 | 10.7 | 23% | 59% | 0.2051 |
| jumps | delta_0.5 | 1.01 | 1.37 | 3.4 | 63% | 33% | 0.6304 |

## Rule S (falsifier salvage): **NOT A CANDIDATE** (corner a=0.7, d_f=90: [True, False, True, False])

| path | μ_right | d_f | a | hold E_r | hold E_w | hold p* | salv E_r | salv E_w | salv p* | p99_r hold→salv |
|---|---|---|---|---|---|---|---|---|---|---|
| gbm | 40% | 90 | 0.7 | 2.32 | 0.634 | 0.2166 | 2.05 | 0.765 | 0.1835 | 10.8→10.7 |
| gbm | 40% | 90 | 0.9 | 2.32 | 0.634 | 0.2166 | 2.24 | 0.788 | 0.1452 | 10.8→10.8 |
| gbm | 40% | 150 | 0.7 | 2.32 | 0.634 | 0.2166 | 2.15 | 0.706 | 0.2039 | 10.8→10.8 |
| gbm | 40% | 150 | 0.9 | 2.32 | 0.634 | 0.2166 | 2.28 | 0.716 | 0.1822 | 10.8→10.8 |
| gbm | 80% | 90 | 0.7 | 4.59 | 0.634 | 0.0927 | 3.81 | 0.765 | 0.0774 | 11.2→11.1 |
| gbm | 80% | 90 | 0.9 | 4.59 | 0.634 | 0.0927 | 4.35 | 0.788 | 0.0594 | 11.2→11.1 |
| gbm | 80% | 150 | 0.7 | 4.59 | 0.634 | 0.0927 | 4.09 | 0.706 | 0.0869 | 11.2→11.1 |
| gbm | 80% | 150 | 0.9 | 4.59 | 0.634 | 0.0927 | 4.44 | 0.716 | 0.0764 | 11.2→11.1 |
| jumps | 40% | 90 | 0.7 | 2.24 | 0.650 | 0.2205 | 1.98 | 0.749 | 0.2033 | 12.2→11.3 |
| jumps | 40% | 90 | 0.9 | 2.24 | 0.650 | 0.2205 | 2.16 | 0.799 | 0.1478 | 12.2→11.7 |
| jumps | 40% | 150 | 0.7 | 2.24 | 0.650 | 0.2205 | 2.07 | 0.678 | 0.2315 | 12.2→11.4 |
| jumps | 40% | 150 | 0.9 | 2.24 | 0.650 | 0.2205 | 2.19 | 0.702 | 0.2008 | 12.2→11.8 |
| jumps | 80% | 90 | 0.7 | 4.52 | 0.650 | 0.0904 | 3.78 | 0.749 | 0.0828 | 13.7→12.8 |
| jumps | 80% | 90 | 0.9 | 4.52 | 0.650 | 0.0904 | 4.28 | 0.799 | 0.0578 | 13.7→13.4 |
| jumps | 80% | 150 | 0.7 | 4.52 | 0.650 | 0.0904 | 4.05 | 0.678 | 0.0957 | 13.7→12.9 |
| jumps | 80% | 150 | 0.9 | 4.52 | 0.650 | 0.0904 | 4.37 | 0.702 | 0.0813 | 13.7→13.4 |

## Rule R (house-money roll): **{'R3': 'NOT A CANDIDATE', 'R5': 'NOT A CANDIDATE'}**

| cell | live mean M | roll mean M | live P(M≥1) | roll P(M≥1) | live p99 | roll p99 | pass |
|---|---|---|---|---|---|---|---|
| R3_gbm | 1.14 | 1.07 | 24.1% | 18.5% | 10.6 | 11.5 | False |
| R3_jumps | 1.13 | 1.08 | 23.4% | 18.3% | 10.7 | 12.1 | False |
| R5_gbm | 1.14 | 1.10 | 24.1% | 19.1% | 10.6 | 11.9 | False |
| R5_jumps | 1.13 | 1.13 | 23.4% | 19.6% | 10.7 | 12.6 | False |

## Rule V (wide vertical): **CANDIDATE**

| cell | premium ratio | mean M | mean ratio | p99 | P(M≥1) |
|---|---|---|---|---|---|
| naked_gbm | 1.0 | 1.14 | 1.0 | 10.6 | 24.1% |
| K0.75_s0_gbm | 0.7107 | 1.12 | 0.986 | 7.0 | 27.2% |
| K0.75_s5_gbm | 0.6014 | 1.32 | 1.1593 | 8.2 | 28.4% |
| K1_s0_gbm | 0.8437 | 1.12 | 0.9859 | 8.8 | 25.8% |
| K1_s5_gbm | 0.7646 | 1.24 | 1.085 | 9.7 | 26.6% |
| naked_jumps | 1.0 | 1.13 | 1.0 | 10.7 | 23.4% |
| K0.75_s0_jumps | 0.7107 | 1.11 | 0.9771 | 7.0 | 25.8% |
| K0.75_s5_jumps | 0.6014 | 1.30 | 1.1484 | 8.2 | 27.6% |
| K1_s0_jumps | 0.8437 | 1.11 | 0.9794 | 8.8 | 24.7% |
| K1_s5_jumps | 0.7646 | 1.22 | 1.0775 | 9.7 | 25.3% |

## Rule T (540 d vs 365 d): **NOT A CANDIDATE**

| cell | 365 mean M | 540 mean M | 365 p* | 540 p* | premium ratio | pass |
|---|---|---|---|---|---|---|
| mu0_gbm | 0.88 | 0.85 | 0.2174 | 0.2158 | 1.3776 | False |
| mu0.1_gbm | 1.20 | 1.27 | 0.2033 | 0.1985 | 1.3776 | True |
| mu0.25_gbm | 1.82 | 2.10 | 0.1816 | 0.1754 | 1.3776 | True |
| mu0_jumps | 0.86 | 0.81 | 0.2164 | 0.2239 | 1.3776 | False |
| mu0.1_jumps | 1.18 | 1.23 | 0.2023 | 0.201 | 1.3776 | True |
| mu0.25_jumps | 1.82 | 2.04 | 0.1844 | 0.1803 | 1.3776 | True |
