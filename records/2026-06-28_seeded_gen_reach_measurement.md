# Seeded-gen un-confounding REACH measurement — result (2026-06-28)

Executes `PREREG_SEEDED_GENERATOR_DIAGNOSTIC §12` (frozen BLIND 2026-06-28, commit `a1f79d2`, before
this run). Resolves §11's confounded zero: does `capital_raises` reach genuinely-quiet, optionable,
**basket-able quality** non-universe names that the theme ETFs miss — i.e. is SIC-scoped `capital_raises`
worth building as a §11 curation source? **Verdict: NO.** Reach is real but it is scattered financing-noise,
not a quiet sector-tailwind cluster. The seeded-generator / new-source phase closes on this measured finding.

Ephemeral keyed driver `~/seeded_reach_measure.py` (outside the repo, loads the box `.env`; read-only
Alpaca bars + news + OPRA — no scan, no universe edit, no §5 re-stale). Warm 180d cache; `Q` annualized ×2
(the operator-offered equivalent to §12's 365d — decisive either way, so the exact re-pull is unneeded).

## The funnel (180d)

| stage | count | filter |
|---|---|---|
| P_resolvable | 1071 | non-universe `capital_raises` CIKs → ticker (of 1260 non-univ; 189 don't ticker-map) |
| P_common | 1006 | drop `-`/`.` warrant/pfd/when-issued shapes (65) |
| **L** | **390** | price ≥ $3 ∧ ADV ≥ $3M (the cheap §11 floors; batched SIP bars) |
| **Qn** | **50** | raise-aware trailing-90d news ≤ 3 (the `no_fetch` un-confound) |
| **Q** | **5** | + full §11 admission: 25%-OTM 180–365d structure ∧ eligible ∧ fits 1 contract ≤ $1k (OPRA) |

**Stage 1: PASS.** Q = 5 / 180d ≈ **10/yr** ≥ the frozen `Q ≥ 6/yr` floor → the source is **not dry**;
the §11 "reaches only confounded-zero quiet" was wrong — un-confounded, it reaches ~10 quiet+optionable
non-universe names a year.

## Stage 2a (SIC sector geometry) — FAIL

The Q=5 are **5 distinct SIC codes**, max 1/sector (need ≥1 sector with ≥3):

| ticker | company | $/contract | achieved OTM | SIC |
|---|---|---|---|---|
| AADX | Applied Aerospace & Defense | $495 | −2.6% | 3728 aircraft parts |
| CTMX | CytomX Therapeutics | $118 | −11.8% | 2834 pharma (biotech) |
| FRVO | Fervo Energy | $835 | +7.8% | 4911 electric services |
| HAWK | HawkEye 360 | $775 | −17.6% | 7374 data processing |
| SATA | Strive | $855 | −8.8% | 6199 finance |

Not basket-able. (Note also: AADX/HAWK "25%-OTM" structures landed near-ATM — coarse low-priced chains, a
different payoff object, calibration finding #3.)

## Stage 2b (council quality) — MOOT for the decision

2a (free) already disqualifies the build, so per the two-stage spend gate the council batch was **not run**.
Quality is anyway clear by SIC + inspection — the Q and the wider Qn=50 are **financing-noise**, exactly P1's
prediction (`capital_raises` is a financing-event surface, not a tailwind surface; reach ≠ quality):
- **biotech binaries:** CTMX + (in Qn) Avalyn, Hemab, Forte, Odyssey, Parabilis, Seaport, SpyGlass, Zura.
- **banks / finance:** SATA, NBHC, SFST, Renasant, Isabella, National Bank Holdings.
- **closed-end funds:** BlackRock/PIMCO trusts (BIT, BST, HYT, PCN).
- **un-optionable miners (the latent quiet cluster that can't trade):** SSMR (silver), REA/USAU (gold/rare-earth) — 1000/1040 metal mining, all `no_structure` (illiquid far-OTM wings, the LTBR/IE/STNG class).

## Methodology finding — the raise-aware window has an IPO/new-listing confound

§12's raise-aware rule (read news over a pre-filing baseline so offering coverage can't mislabel a
thesis-quiet name) **over-corrects for IPOs**: a fresh S-1 filer has no pre-filing equity news because it
wasn't public — reading FALSE-quiet. FRVO (37 articles/90d), HAWK (17), Cerebras (80), SpaceX (384),
Quantinuum (19) all read raise-aware=0. So the un-confound **inflates** Qn; the true quiet count is lower.
IPO-corrected (reclassify by naive-90d), Q ≈ 3 (CTMX, SATA, AADX) ≈ 6/yr — right at the floor, still
scattered (pharma/finance/aero). **The verdict is robust to the confound — correcting it only strengthens
the negative.** A future re-run needs an "already-public-before-the-filing" guard on the baseline.

## Disposition

- **Do NOT build SIC-scoped `capital_raises` as a curation source.** Reach is real (~10/yr, ~6/yr
  IPO-corrected) but scattered across unrelated SICs and dominated by biotech-binary / SPAC / bank /
  IPO-buzz financing-noise. No quiet sector-tailwind cluster to scope a source around.
- **The §11 finding is now MEASURED, not confounded:** capital_raises reaches quiet+optionable non-universe
  names, but they do not form tradeable sector baskets and are not tailwind-quality → the honest answer to
  "can a grounded source out-quiet the human on this corpus" is **no**. The irreducible quiet-discovery input
  remains the HUMAN sector judgment that decorrelates from coverage (consistent with the 2026-06-23 autonomous
  floor). **Seeded-generator / new-source phase: CLOSED on measurement.**
- **Hand-curation residue (color, not admits):** AADX (aero-defense), FRVO/HAWK (geothermal / space-intel)
  are individually plausible quiet-ish names a HUMAN curator could look at at the next window — but each is
  caveated (FRVO/HAWK IPO-confounded on quietness; AADX/HAWK near-ATM achieved structure) and none justifies
  a deterministic source. Curation stays ETF-sourced; the window holds for the §5 read (~mid-July).

Raw: `~/seeded_reach_full180_2026-06-28.json`. Lineage: divergence v1 → FSSD v2 → autonomous-corpus
(`2026-06-23_autonomous_corpus_generator_negative.md`) → this (seeded source, measured).
