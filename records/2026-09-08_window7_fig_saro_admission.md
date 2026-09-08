# 2026-09-08 — Window #7 (off-cycle): FIG admitted, SARO near-miss — the Sept tenor recheck's first admission; universe 45, cluster #13

**Rule:** PREREG_UNIVERSE_CURATION §11 off-cycle admission. **Merging this PR is the admission act.**
Both names came off the September tenor recheck (parked at windows #3/#5 for having no
180–365-day contracts; both are young IPOs whose long-dated listings only matured this month).

## Decision provenance (TRUE form)

The 2026-09-06 Sunday review reported the tenor-recheck survivors on **provisional** quotes
(FIG $470 / 24.4% / 257d · SARO $142 / 20.9% / 222d) and presented a CC-drafted thesis for
FIG (none was on file — FIG entered via the window-3 `orphan_new_listings` watch) alongside
SARO's aviation_mro thesis (operator-adopted 2026-08-20). The operator answered **"let's admit
those FIG and SARO"** (2026-09-06). Execution was queued behind the in-window read of record
(Sunday quotes are provisional; Mon 09-07 was Labor Day). Theses AI-drafted / operator-adopted
per the 2026-07-14 convention — never presented as blind pins. Draft on file:
`records/2026-09-06_window7_fig_saro_theses_DRAFT.md`.

## The screen — three in-window reads (the pre-declared LAST read governs)

| read | FIG | SARO |
|---|---|---|
| 09-06 provisional (Sunday, marks) | FIG270521C00030000 · **$470 · 24.4% · 257d** ✓ | SARO270416C00030000 · **$142 · 20.9% · 222d** ✓ |
| 09-08 13:38 UTC | FIG270521C00025000 · $575 · **8.4%** ✗ band | SARO270416C00022500 · $470 · **−9.0% ITM** ✗ band |
| 09-08 13:41 UTC (diagnostic) | same wing · $575 · 8.0% ✗ | same wing · $470 · −8.5% ✗ |
| **09-08 15:07 UTC (governs)** | **FIG270416C00030000 · $375 · 28.7% · 220d · spread 8% · ADV $382.6M → ADMITTED** | SARO270416C00022500 · $455 · **−8.5% ITM** · spread 7% → **NEAR-MISS** |

**Why the opening reads flipped out.** `structure.select_structure` picks the *eligible*
contract nearest the 25% OTM target, and eligibility requires a live two-sided quote with
spread ≤ 25%. In the first minutes after the open the in-band long-dated strikes (FIG C30
Apr/May-2027, SARO C25/C30 Apr-2027) carried no eligible quote, so the selector fell back to
the nearest quoted strike — out of band for both. Sunday's off-hours read used marks, which is
why it found the in-band wings. By 15:07 FIG's C30 Apr-2027 quoted (8% spread) and the
in-band expression re-emerged; SARO's never did — a 2024-IPO chain still too thin at the
long tenor (calibration finding #3: a far-from-25% structure is a different payoff object).

**Method note pinned for future windows:** the *first* in-window read is not automatically the
read of record for thin long-dated chains; a pre-declared last read of the day governs, and
no re-reads follow it (the anti-camping rule from the BNTX hold).

## FIG — admitted (basket/cluster `design_software_ai`, NEW, #13)

Thesis as adopted (register `themes.design_software_ai`): an AI-native design/collaboration
platform whose fundamentals are re-accelerating while the stock has round-tripped its IPO
froth (2025 IPO $33 → >$120 → ~$23). Q2-2026 revenue $370.1M **+48% y/y**, the third straight
quarter of accelerating growth, NDR 136%, FY-2026 guide raised to +39%. **Falsifier:** Q3-2026
revenue growth < 30% or NDR < 120%. **Pinned caveat, stated plainly:** FIG is the least
copper-not-rockets name in the universe — heavily narrated, AI-credit growth of unproven
durability, SBC-heavy, lock-up supply. The council's `under_narrated` leg is expected to veto
it; that outcome is a datum about the seam, not a failure of the admission. Admission is
feasibility-only — cheapness and momentum are forbidden criteria; the council judges.

## SARO — near-miss (recorded, not admitted — the CF/AIR precedent)

Band fail on all three in-window reads (ITM fallback). `aviation_mro` stays an adopted thesis
without an expression (the window-5 convention: no empty baskets, no register theme until a
name can express it). **Recheck door:** the Sun 2026-09-13 provisional read + a Mon 2026-09-14
in-window read; the operator's 09-06 word stands for SARO through that recheck.

## Changes in this PR (additive-only)

1. `config.universe.themes` += `design_software_ai: ["FIG"]` (universe 44→45; first scan =
   the 2026-09-13 L0; funnel/council judge, gates/caps dispose).
2. `config.convexity_book.clusters` += cluster #13 `design_software_ai` (a software-platform
   driver shared with no existing cluster; book still fills ≤5; `cluster_fraction` 0.02 unchanged).
3. `universe_register.json` += `themes.design_software_ai` + `windows.7` (with the SARO
   near-miss ledger entry).
4. This record + the 09-06 theses draft (committed as the provenance trail).
