# PREREG — Council/Gate cheapness-separation (FROZEN 2026-06-09)

**Status: FROZEN 2026-06-09** (committed before the re-score number is seen; the §5 decision rule + the
principle + the ~0-1 yield expectation are now IN FORCE). The sequence is: **operator red-team → FREEZE (commit) this pre-reg incl.
the §5 decision rule → run the thesis-only re-score → act per the frozen rule → OPRA precondition (§6) →
code.** The rule is frozen **before** the re-score number is seen — the anti-HARKing firewall (cf. the
divergence/FSSD graves).

## 1. The bug (corroboration, NOT the justification)

The council currently adjudicates **cheapness** itself, via an `rv_slope`/`momentum` **proxy**, and that
pre-empts the deterministic IV gate — so the frozen cheap-convexity edge (`PREREG_THEMATIC_CONVEXITY §4`)
**has never once run** (`convexity_eval` = 0 across 4 live L1s). The council rejects "vol rising → no longer
cheap" from the markers, before the real chain is ever measured.

**Divergence test (2026-06-09, read-only, real names):** the real-chain gate would pass **11/16** of the
universe as cheap right now (IV/RV <= 1.2, skew <= 10, INDICATIVE); **8/16 sit in the harm quadrant**
(gate-cheap but the proxy would reject). This corroborates that the seam **has bite** — it is **not** the
load-bearing number (see §3).

## 2. The honest yield (pre-committed BEFORE the re-score — inoculation against the "loosen the filter" slide)

The read-only classification of the 8 harm-quadrant names found only **2 (NEE, RKLB)** rejected on cheapness
**alone** — but that checked only the **structural** leg. The **full §4 thesis mandate** is structural **AND
under-narrated AND at-a-genuine-inflection**, and under it the ~2 is **optimistic**: RKLB (+194% momentum,
"extended") plausibly **fails** at-genuine-inflection (the inflection already happened) **and** under-narrated
(a name up 194% isn't unloved); NEE (momentum +0.40, "move starting") may pass inflection but is the
**OPRA-boundary-fragile** one (§6). The other 6: 4 carried a legitimate **thesis** objection (CCJ/KTOS/RTX
"already consensus"; SMCI "fad / mean-reverting / not a fresh inflection") that **survives** the
re-architecture, 1 grounding-drop (FCX "ungrounded"), 1 unaccounted (CEG, no council proposal).

**==> Pre-committed yield expectation under the FULL §4 mandate: ~0-1 names** from the current universe —
**NOT 8, and likely below the structural-only ~2.** A result of ~0-1, or even 0, is the **scarcity finding
arriving a step early** (§5 decision rule), **NOT** a failure. Loosening the conviction floor or the thesis
criteria to raise yield is explicitly **forbidden** (§7).

Mapped to the §5 freeze-gate (no silent disagreement): **0 = scarcity** (proceed on principle, no near-term
trade), **1 = confirms** (proceed) — both within this ~0-1 expectation; **>= 2 trips the selectivity flag**
(above expectation -> investigate, do not bank).

## 3. The justification (load-bearing — the PRINCIPLE, not the count)

**Separation of concerns.** The IV gate is the frozen, pre-registered **cheapness** edge (`§4`). The council's
mandate (hard seam) is to **propose themes** (thesis), and the deterministic gates **dispose**. The council
judging cheapness on a marker proxy is a **seam violation**: it does the gate's job, *worse* (a proxy, not the
real chain), and pre-empts the gate so the actual edge never runs. **Legitimacy test** (the advisor's firewall
— "would you make this even at ZERO extra trades?"): **YES** — correct separation of concerns regardless of
trade count. This passes; the change rests here, not on §1/§2's numbers.

## 4. The exact behavioral change

- **Council -> THESIS ONLY (ALL roles, not just the strategist).** Cheapness reasoning currently enters via
  (a) the shared `_COMMON` system prompt — "ONLY when implied vol has not yet priced the move" (`council/agents.py:25`),
  injected into ALL three roles — and (b) the **adversary**'s objection set — "already ... priced" / "the move is
  behind it" (`agents.py:42`). **Both are removed:** `_COMMON` keeps "the deterministic IV gate DISPOSES on
  cheapness" but drops the "implied vol not yet priced" criterion; the adversary objects on THESIS grounds only
  (already-consensus / fad / not-a-real-inflection), never on priced/vol. The proposer (Inflection Analyst) and
  strategist role keys are already thesis-shaped (inflection / structural / under-narrated) and come out clean once
  `_COMMON` + the adversary are fixed. Net: the council judges THESIS — real / structural / under-narrated (not
  consensus) / at-a-genuine-inflection / direction — NOT "is the convexity cheap / is vol rising."
- **The IV gate is the SOLE cheapness arbiter** — unchanged, frozen (`§4`), on the **real chain** (OPRA, §6).
- **Both must agree** (the hard seam, intact): council includes on thesis >= MODERATE **AND** the gate passes
  on cheapness -> the deterministic sizing/caps/structure then dispose. Conviction still never sizes.
- Forensics: the council's `structural_vs_fad` / under-narrated / inflection judgments are recorded +
  forward-scored (Brier), exactly as today, minus the cheapness leg.

## 5. The freeze-gate — a pre-committed decision rule (FROZEN before the re-score)

The thesis-only re-score is the freeze-gate, and its number must be read against a rule committed **without
having seen it** — otherwise the latitude this pre-reg exists to close reopens at the worst point.

**The re-score:** re-run the council on the 8 harm-quadrant names **and the full universe**, under the **FULL
§4 thesis mandate** — structural **AND** under-narrated **AND** at-a-genuine-inflection (NOT just "is the theme
structural"; the §2 classification checked only structural and is therefore optimistic). Ephemeral DB, **no
live-record touch**; count how many reach >= MODERATE on thesis grounds. (This also confirms the council *can*
express >= MODERATE at all.) **The re-score MUST preview the EXACT config production will ship** (the edited
`_COMMON` + adversary from §4, applied to all roles) — if it previews thesis-only-strategist while production
drops cheapness from all roles (or vice versa), the freeze-gate validates the wrong configuration.

**Decision rule (pre-committed, all three outcomes — bands NON-OVERLAPPING, consistent with §2's ~0-1):**
- **exactly 1** (~ the expected NEE flip) -> CONFIRMS; proceed to the OPRA precondition (§6), then code.
- **0** -> the council's **floor**, not the cheapness seam, is the binding constraint on the current loud
  universe — it holds no genuine under-narrated-at-inflection cheap name right now. This is the **scarcity
  finding, NOT a failure**: **proceed on the principle** (the gate should be the sole cheapness arbiter
  regardless), **expect no near-term trade**, do **NOT** loosen the floor or criteria (§7), and treat it as
  **elevating the funnel re-targeting (§8) to the next frontier.**
- **>= 2** (above the ~0-1 expectation) -> **SELECTIVITY FLAG**: the thesis-only council is *less* selective
  than the classification predicted (e.g. it included RKLB despite +194%) -> investigate the discrepancy (is the
  thesis-only mandate under-specified / too permissive?); do **NOT** bank it as upside; do **NOT** proceed until
  understood + the mandate re-tightened.

## 6. OPRA confirmation (a hard precondition — and it re-checks the BOUNDARY names)

The re-architecture relies on the gate's cheapness reads being trustworthy. They are currently INDICATIVE.
Before the council defers cheapness to the gate, **PR3 (OPRA) must confirm the gate-cheap reads on the real
chain — specifically the boundary names**: **NEE (IV/RV 1.17)** is the headline flip *and* closest to the 1.2
line; a 1-vol-pt INDICATIVE->OPRA difference (inside the probe's observed 0.3-1.4 range) can flip it to
gate-**expensive**, erasing the flip. (RTX 1.14 was a thesis-reject regardless.) So OPRA / PR2-PR3 move from
"readiness, off the trading path" to an explicit **precondition** of this change. The seam fix does **not**
ship on INDICATIVE.

## 7. Out of scope / explicitly forbidden (the HARKing leash)

Every change here increases throughput toward entries — the gradient the manufacturing-trades HARKing rides.
Forbidden in this pre-reg: **loosening the conviction floor**; **loosening the IV-gate thresholds**;
**re-curating baskets so the council/gate will pass them** (reverse-selection); **raising yield by relaxing
the thesis criteria**. The risk frame (book 10% / name 1% / cluster 2% / <= 15) bounds the 0->some-entries
regime change and is unchanged.

## 8. What this does NOT fix (kept honest, front and centre)

The genuine **quiet-cheap** thematic profile (e.g. NNE: IV/RV 0.94, momentum +0.06, flat rv_slope) is **rare**,
**not in the universe**, and **invisible to a motion funnel** (it's quiet by construction). The seam fix runs
on whatever discovery surfaces — currently **loud, consensus** names — so it will not reach the NNEs. **The
seam fix is correct-but-modest, not the unlock.** Even executed perfectly it likely lands ~0-2 trades; its
value beyond the count is that **the frozen IV-gate edge finally runs at all.** Re-targeting the discovery
funnel (rank thematic candidates on **quietness + cheapness**, not motion) is a **separate, larger,
separately-pre-registered** design question, and the real next frontier (and only *there* does the LLM
theme-expander become the right source rather than a demoted one). Do **not** bundle it into this pre-reg.

## 9. Known-open items (out of scope here, named so they don't vanish)

- **The third anti-quietness leg — evidence-grounding.** Hand-seeds / thin-news names drop "ungrounded, no
  numeric evidence" (FCX, every run), which penalizes exactly the under-narrated names the thesis wants (quiet
  names have thin news). Like the funnel (§8), this is a real leg of the anti-quietness bias, **NOT fixed
  here** — deferred to its own consideration, named so it isn't lost.
- **CEG pipeline gap.** CEG is gate-cheap (IV/RV 1.09) yet has **no council proposal** — a gate-cheap name that
  never reached the council. One-line check: discovery gap (never surfaced) vs timing (surfaced on a scan whose
  L1 we haven't read). A small pipeline hole worth confirming, not a blocker.

## 10. POST-FREEZE RECORD (appended 2026-06-09) — the §5 freeze-gate FIRED: ≥2 → SELECTIVITY FLAG

*Append-only. §§1–9 above are the frozen body (PR #43) and are unchanged. This section records the
freeze-gate's outcome and its pre-committed consequences; it closes latitude, it adds none.*

### 10.1 Two runs — population reconciliation

- **Run 1 (superseded — NOT §5-compliant).** 2026-06-09, earlier session; ephemeral, live router, ~$0.13.
  Population = the **11 then-active sentinels** (the 2026-06-03 scan's RKLB/VRT/PWR/KTOS/GEV/ETN/CCJ/SMCI
  + the 2026-06-07 scan's RTX/NEE/LHX) — a motion-filtered subset, NOT §5's "the 8 harm-quadrant names
  and the full universe." Result **1 of 11 ≥ MODERATE (GEV, structural)**, read at the time as "1 =
  CONFIRMS"; per-name verdicts / config text / cost were not fully captured. Superseded for population
  non-compliance + capture gaps (flagged in red-team review before any doc cited it).
- **Run 2 — the §5-COMPLIANT RUN OF RECORD.** **2026-06-09 21:52 UTC**, operator-approved, ephemeral
  (in-memory candidates, NO live-record touch), live router, cost **$0.22**. Population = the **full
  16-name universe** (⊇ the 8 harm-quadrant names): NVDA, SMCI, VRT, ETN, GEV, CEG, CCJ, FCX, NEE, PWR,
  RKLB, LMT, NOC, LHX, RTX, KTOS — every name marker-grounded (origin-aware sentinel context), direction
  = the motion-derived `discovery.direction_of`, forced past the motion floor (§5 scores the full
  universe), `council.max_candidates` 12→20 so nothing truncates. Models (config-pinned): proposer
  `gemini/gemini-3.5-flash` (thinking_level=minimal, json_mode), adversary `xai/grok-4.3`, strategist
  `anthropic/claude-opus-4-8`. Conviction floor: MODERATE. Harness:
  `scripts/probe_rescore_thesis_only.py` (committed with this append; prints the previewed prompts and
  all per-name verdicts on every run).

**Result: 5 of 16 reached ≥ MODERATE — NVDA, VRT, CCJ, FCX, KTOS (all MODERATE, structural). GEV = LOW
/ fad ("already-consensus, heavily-narrated, crowded momentum") — run 1's sole survivor did NOT survive
the run of record. → the frozen §5 band: ≥2 = SELECTIVITY FLAG.**

### 10.2 The previewed config (and the named capture gap)

The run previewed the exact §4 all-roles edit against `council/agents.py`: (a) `_COMMON` dropped the
cheapness criterion "ONLY when implied vol has not yet priced the move" (keeping "a deterministic
IV/cheap-convexity gate DISPOSES and can veto you"); (b) `ADVERSARY_SYSTEM` dropped the priced /
move-is-behind-it objections, keeping thesis grounds (already-consensus / fad / not-a-real-inflection).
Proposer/strategist role keys unchanged (already thesis-shaped). **Capture gap, named:** the edited
prompt strings were applied ephemerally and reverted, and run 2's stdout (which printed them plus all 16
per-name verdicts) was not tee'd to a file — so the verbatim previewed prompt text and the 11
non-survivors' individual verdicts are not retained; the count, band, survivors, GEV verdict, cost,
time, population, and models above are the operator-witnessed record. The committed harness reprints
prompts + all verdicts on every run, so the next gate run is fully captured by construction.

### 10.3 Reading per the frozen rule

≥2 = the thesis-only council is LESS selective than §2 predicted (~0-1): the survivors include names the
full §4 mandate (structural AND under-narrated AND at-a-genuine-inflection) should reject — NVDA
(already-consensus AI), VRT (momentum +1.95 / rel +1.71, extended), CCJ (extended). Diagnosis: the
previewed prompts enforce "structural" but do NOT enforce "under-narrated" / "at-a-genuine-inflection"
as hard criteria. **Per the pre-committed rule: investigate + re-tighten the mandate; do NOT bank; do
NOT proceed** to §6/OPRA or code until re-tightened and re-scored. GEV's run-1→run-2 flip
(MODERATE→LOW) is population difference + run-to-run LLM variance on a borderline name — itself the
demonstration that an uncommitted 1-of-11 could not carry a freeze (cite-before-record, vindicated).

### 10.4 Pre-committed next gate (recorded BEFORE that re-score runs)

The re-tightening session edits the thesis-only mandate so under-narrated + at-a-genuine-inflection are
HARD veto criteria (tighten-only; §7 still forbids loosening floor/gate/criteria/baskets), then re-runs
this same harness **on this same 16-name population** (pinned here for before/after comparability,
regardless of any later universe curation), read against the same §5 bands: **0 = scarcity / 1 =
confirms → unblocks §6; ≥2 again = investigate again — prompts are NOT iterated until the number fits.**
One re-tightening pass per re-score; every run is appended here.

### 10.5 Stale-premise retirement + companion findings

- §1's "the frozen edge has never once run (`convexity_eval` = 0)" is now historical: at L1 **#111**
  (2026-06-09 19:45 UTC) the live (old-config) council included RKLB MODERATE → the IV gate RAN and
  PASSED (iv/rv 1.066, skew 0.08) → the **cluster cap vetoed** the entry (space_defense $2,000 < one
  RKLB contract $2,866). The same run live-corroborated §1's suppression mechanism: GEV was rated LOW
  on the cheapness proxy ("momentum already reflected, negative rv_slope").
- Companion read-only cap check (`scripts/probe_gev_cap_check.py`, 2026-06-09): one GEV 25%-OTM
  180–365d call ≈ **$8,125/contract** vs the $1,000 per-name cap (and 4× the $2,000 cluster cap) →
  `convexity_position_size` = 0, un-enterable. Every gate-cheap name whose single contract fits $1,000
  is a thesis-reject (FCX $772 / NEE $162 / KTOS $990). **Near-term yield of the re-architecture on the
  current universe = ZERO, independent of this selectivity flag.** The cap-vs-contract-granularity
  mismatch and the universe/funnel re-target (§8) are known-opens, each its own future pre-registered
  session; per §7 the caps are NOT raised to force entries.
- §9's CEG pipeline gap is RESOLVED-BENIGN: CEG is a random CONTROL (deliberately never proposed) and
  its markers (momentum +0.14 < the 0.15 floor; rv_slope 0.157 < 0.25) would not have surfaced it —
  another quiet-cheap name the motion floor excludes (reinforces §8), not a pipeline bug.
- Layer distinction, kept explicit: council-≥MODERATE (this re-score) ≠ gate-cheap (the chain probes,
  `scripts/probe_opra_dualread.py`). The five survivors are a council-selectivity reading, not a
  tradeability reading.

### 10.6 Expected-vs-actual identity + §6 status

§2/§6 expected the single flip to be **NEE**; run 1's actual was **GEV** (the §6 boundary re-target
NEE→GEV, after PR1's IEX→SIP RV change took NEE off the boundary, 1.17 IEX-RV → ~1.09 SIP-RV); run 2
has **no GEV** and five different survivors. GEV's OPRA reads were gathered en route (gate-cheap on
both feeds: 1.155 IND / 1.135 OPRA mid-day; 1.138/1.140 at the close) but are now moot for §6. **The §6
boundary-name discharge is OPEN** — to be re-discharged by name against whatever survives the
re-tightened mandate. The drafted OPRA-sequencing pre-reg ("ACCELERATE") is **not frozen**; any future
freeze must cite THIS committed record, not run 1.
