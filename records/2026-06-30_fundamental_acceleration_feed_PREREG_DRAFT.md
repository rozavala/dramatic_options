# PRE-REG (DRAFT — pre-freeze, for RED-TEAM; NOT frozen, nothing runs yet) — the fundamental-acceleration candidate feed

**Date:** 2026-06-30 · **Status: DRAFT for red-team.** All yield-determining knobs are proposed BLIND
below and flagged in §10 as the red-team surface. Freeze (pin §10 + sign-off) happens AFTER convergence,
BEFORE the diagnostic runs (anti-HARK). The diagnostic driver is ephemeral (outside the repo); the
`fundamentals.py` acceleration extension is committed as tested infra **only if** the read says BUILD.

## §1 — Why this probe (the one door the funnel graveyard left open)
The four idea-supply negatives (divergence/FSSD, autonomous-generator, seeded-source, obscurity,
federal_awards) all tried to mechanize the **quietness / decorrelation** leg — proven HUMAN-only. The
06-23 record (`2026-06-23_autonomous_corpus_generator_negative.md`, lines 18-19, 84) explicitly leaves
ONE door open: *"Inflection is different: the corpus can express it structurally… Fundamental
acceleration (revenue/earnings YoY accel from filed XBRL) is the single §2-clean signal that targets
inflection directly."* It shelved it for three caveats — **two now obsolete:**
1. *"a from-scratch broad-universe build"* → **largely dissolved.** `data/fundamentals.py` already
   computes PIT-clean `revenue_yoy` (TTM, points filed ≤ as_of, `min_base` floor handling the
   pre-revenue explosion). Acceleration is the slope of that series — a small extension, a *run* not a build.
2. *"needs the news axis bolted on for quietness"* → **dissolved.** The §9 evidence-grounding pack already
   wired the trailing 7d/90d news-count coverage proxy into the council.
3. *"the same volume-skew risk (cleanest acceleration skews narrated)"* → **LIVE — the only real
   question, and what this probe decides.**

**The seam (why this is the project's working shape, not a generator rescue):** mechanize the
deterministic **inflection** leg (the record concedes the corpus *can* express it), leave the
**quietness** judgment to the human/council. Structurally the etf_constituents → FRO/CDE lever that
produced admits — sourced from acceleration instead of a sector hunch. It is **not** a return-predictor
(that's the corpse — see §6); it is a candidate **feed**.

## §2 — The hypothesis + the decisive distinction
**H:** there exists a populated, judgeable, *novel* cell of `{material revenue-acceleration ∧ low-coverage
∧ optionable}` mid-caps — the quiet-inflection cell the prime-award/financing feeds could not populate —
AND conditioning on acceleration beats conditioning on coverage+optionability ALONE (the §4 null).

**Why this isn't obviously federal_awards' empty cell.** federal_awards self-emptied because the
catalyst is **announcement-gated** (a public award IS a press release → re-rates → moves the
denominator). Reported revenue acceleration is **coverage-gated**: filed-but-not-necessarily-narrated;
for a low-coverage mid-cap a strong 10-Q can sit unread for quarters. So filtering for low coverage does
NOT fight the catalyst's visibility — it *selects* names where the filed catalyst hasn't re-rated. There
is no structural antagonism forcing the cell empty (unlike federal_awards' size-cell). Whether it is
*actually* populated is the empirical question.

## §3 — The pinned design (BLIND; §10 is the red-team surface)
| knob | proposed BLIND value | rationale / anti-HARK |
|---|---|---|
| **frame** | US **common stock** (exclude ETFs/CEFs/SPACs/funds — the obscurity-null's 78%-funds trap; exclude names with no clean us-gaap XBRL revenue), **cap ∈ [$300M, $15B]** as-of run date, **optionable** (listed chain). | the mid-cap zone where the thesis is FEASIBLE: mega-caps are narrated-by-construction (cell empty by coverage), micro-caps have no chains (empty by optionability). The live zone is optionable mid-caps. |
| **sample** | the whole frame if ≤ **~800** names post-filter, else a deterministically-seeded random **800** (vary the seed by label, never `Math.random`). Report **companyfacts coverage rate** (valid-accel-read / sampled); **<70% = fix-and-rerun**, not a verdict. | a few hundred names is ample to read cell-population + run the null; fetches are cached (≈free, like the federal_awards probe's 100+). |
| **acceleration** (primary) | `accel = TTM-rev-YoY(as_of) − TTM-rev-YoY(as_of − 365d)`, points **filed ≤ as_of** (reuse `revenue_yoy`); require **current TTM-YoY > 0** (genuine growth-acceleration, not less-bad decline). **Material floor: accel ≥ +15 pp**; report the full distribution + a **+8 pp shoulder**. | the second-derivative/inflection; revenue (not earnings — earnings explode on sign-flips) is the robust leg `fundamentals.py` already grounds with a min-base floor. The +15pp floor defines "the cell"; the distribution-read (not a top-k) is what answers "populated". |
| **coverage proxy** (diagnostic instrument ONLY) | trailing **90d news count** (the §9 proxy); **"quiet" = bottom tercile** of the frame's 90d-count, reported with an absolute. | LOCATES the cell cheaply. **The PRODUCTION feed is accel-ONLY** (no news at the feed layer); quietness is applied DOWNSTREAM by the human/council exactly as today — keeps the §2 seam clean (news-count is a measurement instrument here, not a corpus input signal). |
| **optionability** | the existing §11 feasibility screen (chain exists, achievable 15–35% OTM band) on the cell survivors. | reuse; the same tradeability bar the live loop uses. |

## §4 — The null≈signal control (the FSSD/divergence discipline — the decisive leg)
The FSSD kill was *"null control ≈ signal → conditioning on the event adds ~nothing over the
characteristic."* The analog:
- **Control A (coverage-only null, PRIMARY):** `{quiet-tercile ∧ optionable}` WITHOUT the accel floor —
  a same-size random draw. **Does the accel-cell beat it?** If the quiet-optionable set is just as good
  *without* accel, the lever is "look at quiet optionable mid-caps" and accel is decoration.
- **Novelty:** fraction of the accel-cell **NOT already in-universe** and **not on the operator's
  exhausted thesis-lists** (the generator's death was re-deriving in-universe narrated names). A feed
  that surfaces only names you already have adds zero throughput.
- **BLINDED eyeball (kills judge-bias):** the operator scores cell + Control-A names **shuffled and
  label-hidden** ("genuine secular-inflection candidate to express as cheap convexity? Y/N"), THEN
  unblind and compare pass-rates + novelty. Council is a paid second pass only if the eyeball is ambiguous.

## §5 — Decision rule (banded, BLIND; read the distribution + composition, not a bare count)
- **BUILD (the accel feed as a curation candidate-source — feed-not-edge):** all three —
  (a) **populated**: ≥ **10** names in `{accel-floor ∧ quiet-tercile ∧ optionable}` (≈≥1.5% of an 800
  sample); (b) **non-junk**: blinded eyeball pass-rate ≥ **50%** (genuine inflections, not one-off blips /
  M&A-driven jumps / post-IPO base-effects / cyclical-trough bounces); (c) **beats the null**: accel-cell
  pass-rate ≥ **2×** Control-A's **AND** novelty ≥ **50%**.
- **GRAVEYARD (the door closes):** cell thin (< ~5), OR junk-dominated (pass-rate < ~25%), OR accel ≈
  Control-A. → dated negative; fundamental-acceleration was the last §2-clean inflection door, and it too
  surfaces only the narrated end (or nothing tradeable-and-quiet).
- **REVISIT / re-scope (a different, still-useful finding):** populated + non-junk but accel ≈ Control-A
  → the working lever is **"quiet optionable mid-caps"** (a curation-*tooling* finding — build the triage
  surface, §9), NOT acceleration specifically. Not a graveyard, a redirect.

## §6 — Guards (the line that keeps this off the divergence corpse)
- **FEED, NEVER A SCORED EDGE.** `data/fundamentals.py` IS the divergence-edge module; revenue-YoY as a
  ranked predictor is PROVEN DEAD (k=4 rank-IC **−0.057**, Bonferroni CI spans 0; insider net-buy k=3
  −0.048). **The diagnostic NEVER computes accel's forward-return IC** — that re-runs the graveyard. The
  output is cell-population + blinded-eyeball + null, judged qualitatively. Any forward validation is at
  the **convexity** level (council Brier, post-build), exactly like etf_constituents (nobody asks if
  "being in SIL" has IC). Accel is a funnel rank, never a tradeable signal (the existing discovery-layer
  discipline).
- **§2-clean.** Acceleration is filed-XBRL **revenue** (a fundamental) — not price/IV/momentum/sentiment.
  A name can accelerate with flat/falling price (the ideal target: fundamental inflection not yet in IV).
  News-count is the diagnostic's measurement instrument + the council's existing downstream quietness
  judge — never a feed-layer signal.
- **PIT.** Acceleration from points **filed ≤ as_of** (`revenue_yoy` enforces it). The diagnostic snapshot
  is current-as-of; any look-back uses as-of discipline (no restatement leakage).
- **Anti-HARK.** §10 frozen before the run; the three fix-and-rerun plumbing risks (§7) are pre-named so a
  mid-run fix can't be mistaken for tuning.

## §7 — Staged probe (cheap leg first; pre-named plumbing fix-and-reruns)
1. **Diagnostic (this pre-reg):** reuse `fundamentals.py` + the wired news axis over the §3 sample →
   the §4 null + §5 read. **No build.** Pre-named fix-and-rerun risks (plumbing, NOT verdicts): (i)
   **companyfacts coverage** < 70% (foreign/MJDS/financials filers) → widen/clean, not graveyard; (ii)
   the **news-count source must fetch for arbitrary frame tickers** (not just in-pipeline names) —
   pre-run verification; (iii) **inorganic/base-effect contamination** in the cell (M&A jumps,
   post-IPO base) → an "already-public ≥ N quarters" + organic guard, surfaced in the eyeball.
2. **Build iff §5 = BUILD:** commit the `fundamentals.py` acceleration extension as tested infra + wire
   the feed into the curation candidate path (NOT the live universe directly; it proposes, the human +
   council + §11 dispose — the hard seam holds).

## §8 — HARK structure (auditable) / what gets committed
The apparatus targets a nameable population (accelerating mid-caps) = acceptable Rule-0 category design.
The guards against category→answer-fitting: the **blinded eyeball**, the **coverage-only null**, the
**novelty-vs-in-universe** test, **feed-not-edge** (no IC scoring), the **band pinned-no-retune**. Decisive
either way — even GRAVEYARD settles the last §2-clean inflection door (consistent with the project's
epistemics). The ephemeral driver lives outside the repo; the resolver/extension commits **only on BUILD**.

## §9 — Explicitly OUT OF SCOPE (this gate is only for the universe-wide feed)
- **The within-sector accel ranker** (human names a quiet sector → expand constituents → rank by accel)
  does **NOT** need this gate — the human already supplied the decorrelation, so there's no
  "can-automation-surface-quiet" claim to falsify. It's a low-risk enhancement to the proven
  etf_constituents lever, buildable whenever; its *lift* is forward-proven-only (accel-as-predictor is
  IC-dead, so it can't be backtested — it's an extra signal in the human's view, not a scored gate).
- **Other §2-clean inflection feeds of the same shape** (insider-cluster Form-4 net-buy, 13D/activist
  entries — coverage-decorrelated by construction, same feed-not-edge guard) — a *family*; accel is the
  best-instrumented member, tested first. The others follow iff the shape validates.

## §10 — The BLIND values to red-team (the load-bearing decisions)
Pin/contest before freeze: **(1)** frame cap band [$300M,$15B] + common-stock-only; **(2)** accel
definition (one-year two-point Δ of TTM-YoY) + the **+15pp** material floor (+8pp shoulder); **(3)**
"quiet" = bottom **tercile** of 90d news-count (vs an absolute); **(4)** the §5 band — populated **≥10**,
non-junk **≥50%**, beats-null **≥2×** + novelty **≥50%**; **(5)** the blinded-eyeball protocol as the
judge (operator-first, council-second-if-ambiguous). Everything here is a proposal, set on principle,
before any yield is seen.
