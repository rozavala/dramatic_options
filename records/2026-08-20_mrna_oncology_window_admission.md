# 2026-08-20 — Window #4 (off-cycle): mrna_oncology admitted {MRK}; universe 40→41, cluster #10

**Rule:** PREREG_UNIVERSE_CURATION §11 off-cycle admission — event-opened window (MRNA +177%
on the intismeran/Keytruda Phase 3 melanoma readout, 2026-08-19). Sweep-then-adopt form.
**Merging this PR is the admission act.**

## Decision provenance (TRUE form)

The operator asked (2026-08-20 ~00:05 UTC, after the MRNA print): *"do we have anything
around medical stuff and drugs?"* — the answer was no (zero medical exposure anywhere;
the only medical-adjacent ticker is restricted R-001). The operator then asked for help
drafting a thesis and candidate list. CC drafted the `mrna_oncology_platform` thesis and a
13-name slate (marked AI-drafted throughout), ran the provisional off-hours feasibility
sweep, and presented a 4-way fork. The operator answered **"I would do both"** (~00:20 UTC)
= adopt the thesis + admit the screen's clean fit (MRK) + park the blocked names
(BNTX/TEM → probe-themes; PSNL/NTRA/IOVA → the ~Sept tenor recheck). Informed adoption of
an AI-drafted thesis under the anti-anchoring provenance convention (2026-07-14): never
presented as a blind operator pin. The register entry carries provenance `operator` per
§11 (the adoption act is the operator's; the drafting assistance is disclosed here).

## The thesis (as adopted — register `themes.mrna_oncology`)

INT (individualized neoantigen therapy) platform validation → the commercialization
economics + picks-and-shovels layer re-rate; MRK admitted (~50/50 intismeran economics +
the Keytruda-LOE franchise-extension angle); **MRNA itself excluded as already-priced**
(premise-currency Rule 5 — the +177% day IS the reprice). Falsifier ~Aug-2027: regulatory
milestone AND supply-layer revenue acceleration, neither = dead.

## The sweep (both reads — provisional 00:17 UTC · in-window 13:41 UTC 2026-08-20)

| sym | provisional | in-window | verdict |
|---|---|---|---|
| **MRK** | $725 · 24.8% · 302dte | **$890 · 20.5% · 301dte · ADV $1.25B** | **ADMITTED** (stable expression, both reads in-band under cap) |
| BNTX | $1,195 near-miss · 23.8% | **$945 · 29.3% = CLEAN FIT** | **HELD** — flipped clean in-window, but the decision word covered MRK-only → parked in probe_themes; **admission awaits the operator's word (upgrade flagged)** |
| TEM | $1,035 near-miss · 22.4% | $1,038 near-miss · 23.8% | parked (probe_themes; near-miss both reads — the TITN-14.4% precedent: the rule is the rule) |
| MRVI | $305 but −30.7% ITM | $550 · −69.2% ITM | band-broken BOTH reads (coarse sub-$10 chain — confirmed not an off-hours artifact) |
| AVTR | $675 · −49.9% ITM | $450 · −29.1% ITM | band-broken both reads |
| PSNL | tenor-fail | $1,480 · −84.9% ITM | chain unusable → ~Sept tenor/chain recheck |
| NTRA, IOVA | tenor-fail | (not re-screened) | ~Sept tenor recheck (join HLIT/TWI/KMT/FIG) |
| RGEN/ILMN/GH/TWST | $1.6k–$3.1k over cap | — | honest fails |
| TLX | ADV $1.0M < $3M floor | — | honest fail |
| ABUS | tenor-fail | — | honest fail (LNP-royalty angle noted for a future window) |

Screen = the frozen §2 floors only (1 contract ≤ $1,000 · tenor 180–365d · spread ≤ 25% ·
OI ≥ 50 when present · price ≥ $3 · ADV ≥ $3M · achieved-OTM 15–35%). Cheapness and
momentum deliberately absent (forbidden curation criteria — the IV gate disposes at
decision time).

## Changes in this PR (additive-only)

1. `config.universe.themes` += `mrna_oncology: ["MRK"]` (scan universe 40→41; first scan =
   the 2026-08-23 L0; funnel/council judge, gates/caps dispose — the hard seam unchanged).
2. `config.convexity_book.clusters` += cluster #10 `mrna_oncology: ["MRK"]` (the
   INT-platform driver, shared with no existing cluster; the book still fills at most 5
   clusters — more selectivity, never more exposure; `cluster_fraction` stays 0.02).
3. `universe_register.json` += `themes.mrna_oncology` + `windows.4` (surgical splice,
   parsed-validation per the #122 minimal-diff gate).
4. `probe_themes.json` += BNTX + TEM staged theses (judgment-layer fuel, the KMT pattern;
   presence there is NOT admission).

## Standing follow-ups

- **BNTX**: a clean in-window fit awaiting the operator's admission word (or veto).
- ~Sept tenor/chain recheck list grows: PSNL, NTRA, IOVA (join HLIT/TWI/KMT/FIG).
- Premise-currency: any future admission from this slate re-checks the sympathy-pop
  question at its own window.
- Window #5 (the five-sector batch) runs the same day — its own record.
