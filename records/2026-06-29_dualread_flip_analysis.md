# Dual-read flip-wire analysis → 7/10 lapse/extend input (corrected)

**Date:** 2026-06-29 · **Status:** durable input for the 2026-07-10 `veto-dualread-disagree`
lapse-vs-extend decision. This is the **corrected** read, not the first pass.

## Context

Dual-read soak = 11 sessions (runs 147–337), OPRA (gate-of-record) vs indicative (shadow).
At run #337 the rolling-5 tripwire profile was:

- **delta-wire (|Δiv/rv|, the SOLE revert trigger): NOT tripped** — median Δ 0.004–0.009, max
  0.05 (ex-CDE). Nothing pages/reverts. Correct.
- **flip-wire: TRIPPED** — 3 of the last 5 sessions had a material cheap/not-cheap flip:
  **CDE (#303), NXE (#320), TGB (#337)**.
- gap-wire: quiet (UROY recovered); entitlement: never lapsed; coverage ~100% both arms.

## Per-name diagnosis (gate cutoff = iv_rv ≤ 1.20 ∧ skew ≤ 10 vp)

| Flip | OPRA iv_rv / skew | IND iv_rv / skew | Δiv_rv | Diagnosis |
|---|---|---|---|---|
| **NXE** #320 | 1.178 / +0.33 → cheap | 1.210 / −0.14 → not | 0.032 | **1.20-cutoff bisection** |
| **TGB** #337 | 1.185 / −2.77 → cheap | 1.205 / −4.10 → not | 0.020 | **1.20-cutoff bisection** |
| **CDE** #303 | 3.744 / **−201.9** → not | 0.945 / +1.26 → cheap | 2.80 | **degenerate gate IV** |

- **NXE / TGB — pure cutoff bisection (feed-agnostic).** True iv_rv parks at ~1.18–1.21,
  right on the line; across all 11 sessions the two feeds agree to within **0.02–0.03** with
  clean sane skews. Any single feed bisects the same name on its own jitter — the shadow adds
  no arbitration value.
- **CDE — NOT a feed disagreement.** The degenerate leg is the **ATM-IV reference**
  (`atm_iv(chain,…)` ≈ 200%, poisoning both iv_rv=3.7 and skew=−202 vp); the wing IV stayed
  positive (else `no_wing_iv` fail-close would have fired). **Both** feeds are garbage most
  sessions (#285 OPRA 3.38/IND 3.42; #320 OPRA 3.34/IND 3.35); #303 = indicative happened to
  land a clean pull that session. The gate-of-record (OPRA) **correctly fail-closed** not-cheap
  on its garbage quote.

## Conclusion — lapse is supported

The feeds **agree tightly where quotes are clean** (NXE/TGB ≤0.03 iv_rv → validates OPRA as a
standalone gate), and **disagree only where both are equally broken** (CDE → the shadow is no
cleaner an oracle). The dual-read is **not accruing marginal safety value** → **lapse is
supported at 7/10.** The flip-wire trip is a *curation/threshold + thin-wing-quote artifact*,
not an OPRA-vs-indicative reliability signal. Per design (shadow *tightens, never authorizes*),
the veto's only live effect right now is blocking near-cutoff thin-name entries on ≤0.03 iv_rv
noise. (Operator's call at the date; this is the input.)

## Spin-off finding (separate workstream)

CDE's degenerate gate IV is a **measurement-integrity** issue in the cheapness-watch instrument
(an un-priceable IV is silently bucketed `never_cheap` = "the move got priced before we could
catch it"). Tracked as a `PREREG_CHEAPNESS_WATCH §2.1` amendment (report-time un-priceable
state; **no migration** — the raw IV columns already persist). See that draft.
