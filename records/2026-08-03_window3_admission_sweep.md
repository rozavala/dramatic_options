# Window-#3 mechanical admission sweep — 2026-08-03 (in-window)

**Authorization:** operator, 2026-08-03 ("run sweep, then I veto" — sweep-then-veto form).
**Unlock:** the §5 four-scan read closed after the 2026-08-02 L0 (scans 07-12 · 07-19 · 07-26 · 08-02).
**Method:** the §11 rule — sources ∩ feasibility ∩ 15–35% achieved-OTM, additive-only, operator veto-only.
Production screen path (`survivor_cards.run_screen`: price/ADV/optionable/band_fit with
`select_structure` + `contract_eligible` + the frozen $1,000 per-name cap), live OPRA quotes,
in-window (13:47 UTC), read-only ephemeral probe from the live checkout. Raw output:
`2026-08-03_window3_admission_sweep_raw.txt`. Mirrors `2026-07-10_window3_prep.md`.

## Result table (optionable column CORRECTED — see the bug finding below)

| name | theme | price | ADV | optionable† | band_fit | class |
|---|---|---|---|---|---|---|
| ADTN | bead_fiber | PASS $8.52 | PASS $21.3M | PASS† | FAIL −53.1% ITM-fallback, $485 | ITM-fallback |
| CLFD | bead_fiber | PASS $30.63 | PASS $5.9M | PASS† | FAIL −42.9% ITM + $1,495 over cap | ITM + over-cap |
| CALX | bead_fiber | PASS $37.18 | PASS $53.0M | PASS† | FAIL 0.9% (ATM), $570 | band-broken (ATM) |
| HLIT | bead_fiber | PASS $11.56 | PASS $16.7M | PASS† | FAIL no contract in 6–12mo window | **tenor-floor** (max exp 2027-01-15) |
| TROX | tio2 | PASS $5.85 | PASS $13.3M | PASS† | FAIL −82.9% deep-ITM (coarse grid) | strike-grid |
| KRO | tio2 | PASS $6.04 | **FAIL $2.4M** | PASS† | FAIL no eligible contract | **ADV-dead** |
| TITN | ag_equipment | PASS $17.48 | PASS $3.2M | PASS† | FAIL 14.4% — 0.6pt BELOW the 15% floor, $215 | near-miss (reported, not admitted) |
| LNN | ag_equipment | PASS $114.68 | PASS $13.9M | PASS† | FAIL −12.8% ITM + $2,085 over cap | ITM + over-cap |
| AGCO | ag_equipment | PASS $105.31 | PASS $92.6M | PASS† | FAIL 4.5% (ATM) + $1,155 over cap | ATM + over-cap |
| TWI | ag_equipment | PASS $7.38 | PASS $3.2M | PASS† | FAIL no contract in 6–12mo window | **tenor-floor** (max exp 2027-01-15) |
| KMT | carbide | PASS $34.44 | PASS $28.5M | PASS† | FAIL no contract in 6–12mo window | **tenor-floor** (max exp 2027-01-15) |
| **VIAV** | neighbor | PASS $36.11 | PASS $175.5M | PASS† | **PASS — VIAV270416C00045000, dte 256, 24.6% OTM, $915 ≤ $1,000** | **IN-BAND** |

† The probe's raw `optionable` column read FAIL for all 12 — a **false negative** (bug finding
below). All 12 names hold listed options classes, verified per-name via an explicit-window
`GetOptionContractsRequest` (e.g. HLIT 86 contracts, KRO 40, TWI 52, KMT 86).

## THE MECHANICAL ADMISSION SET = { VIAV }

One name. Presented to the operator for veto (additive-only; nothing enters
`universe_register.json` / `config.universe.themes` until the operator approves).
VIAV reproduces its 07-10 read (28.2% then, 24.6% now — stable in-band, unlike ADTN's
documented expression instability). Theme/sources for the register entry: VIAV was surfaced in
the 07-10 window-#3 prep as a cap-door population member (optical/network test & measurement —
bead_fiber-adjacent); the register entry drafting happens only on operator approval.

## Honest notes

- **KMT fails, as pre-announced** — but the fail CLASS changed since 07-10: then it was
  band-broken (40% ITM, coarse strike grid); today its Jan-2027 expirations sit under the 6-mo
  tenor floor entirely (same class as the 9-name tenor-floor cohort of 07-21). The KMT class-(d)
  pin + M-ledger probes are unaffected (they are council-evidence instruments, not admissions).
- **TITN near-miss (14.4% vs the 15% band floor):** reported for the record; the mechanical rule
  is the rule — no HARK loosening to manufacture an admission.
- **HLIT/TWI/KMT tenor-floor fails carry a re-open trigger:** when Jun-2027/Jan-2028 expirations
  list (~Sept-Oct per the 07-26 probe), the band_fit axis becomes computable again. Fold into the
  ~Sept tenor-floor recheck.

## ⚠ Bug finding (found live, mid-sweep): `digest.options_class_exists` false-negatives

`GetOptionContractsRequest(underlying_symbols=[sym], limit=1)` with NO explicit expiration
window relies on Alpaca's default, which only covers near-dated expirations — a monthly-cycle
name queried early in its cycle returns 0 contracts (verified live: KMT/VIAV → 0 by default,
non-zero with `expiration_date_gte/lte` explicit; FIG/NVDA → 1 because they carry weeklies).
**Blast radius:** (1) the survivor-cards `optionable` axis (this sweep's raw column; historic
cards W29–W31 audited — every screened-out name also failed ≥1 other axis, so NO wrong disposal
shipped); (2) **`orphan_new_listings`** uses the same helper → a monthly-only new class could be
detected LATE or missed (FIG was caught day-one because big-IPO classes list weeklies
immediately — luck, not design). Fix: explicit ~1-year expiration window in
`options_class_exists` (code PR alongside this record).

## Sentinel-expansion note (operator-approved shape, 2026-08-03)

Names surviving the operator's veto join `universe.themes` scan baskets (the weekly L0 judges
them from the next scan). **Dated follow-up on the record:** the IRDM ranked-union starvation
datum — a first-ever re-surfaced lineage (surface_count=2, 07-26) went 0-for-7 nightly unions
because the 12-slot ranked union caps it out (the LUNR detect-but-never-judge class in a second
costume). Revisit the union-cap/rank question after ~a week of expanded scans (≥2026-08-10),
as its own operator-gated discussion — NOT folded silently into this admission.
