# 2026-07-01 — Null-arm zero-booking diagnosis: shadow + 3A saturated at the sentinel slot reservation (DESIGNED behavior), invisible for three weeks (OBSERVABILITY defect)

**Status:** §1–§4 written + committed **BEFORE** the confirmatory probe ran (anti-HARK — the
outcome→interpretation map in §4 is pinned first). §5 appended after. **§6–§8 DECIDED +
APPLIED 2026-07-02 (operator directive, while blind — 0 resolutions anywhere):** §6 the
censored-not-dead annotation + §8(b) symmetric slot relief → `PREREG_FIXED_BASKET_NULL.md` §4
dated amendment + code; §7 the posture-review backstop → `PREREG_THEMATIC_CONVEXITY.md` §6
dated amendment (D=2027-03-02 + interim checkpoint 2026-11-02).

---

## §1 — The observation

The brain-off shadow book (`shadow_positions`) booked **0 new positions after run 130
(2026-06-10 19:45 UTC)** across 13 subsequent healthy L1s, with **no error, no page, and no log
line** — while its monitor kept printing (`marked=7`) and the cheapness-watch kept reading
`cheap=1` on the very names it wasn't booking. Discovered 2026-07-01 during the "shadow book as
branch-3 instrument" scoping. Run 130 is also the first OPRA-gate L1 (`option_gate`
indicative→opra flipped that day), which made feed breakage the natural first suspect.

## §2 — The hypotheses (pinned in-session before the fact sweep)

- **H_a (operator):** the IV gate fail-closes on missing/degenerate far-wing IV on the real
  OPRA chain, while the watch scores a nearer/proxy wing that quotes fine.
- **H_b (CC):** `contract_eligible` (spread >25% / OI) rejects real OPRA wings inside
  `select_structure` → "cheap-because-untradeable".
- **H_c:** per-candidate exceptions (format/parse) swallowed at `log.debug`.
- **H_d (raised from the code read; the operator's discriminator-(ii) "cap-saturation,
  designed behavior" one level up):** the `discovery.sentinel_max_slots` reservation saturated
  at run 130 and vetoes every sentinel-origin candidate before eval.
- **H_e (low prior):** the candidate union itself broke/emptied.

## §3 — Static evidence chain (settles the verdict WITHOUT the probe)

**Verdict: H_d CONFIRMED; H_a, H_b, H_c, H_e falsified.** Six read-only fact agents over the
code, box config, live DB, and frozen docs (2026-07-01 ~20:30–20:45 UTC):

1. **3A stalled at the same instant, 3B did not.** 3A (`book='union_nogate'`) booked at exactly
   the same runs with exactly the same 7 symbols as the shadow book (37 / 92 / 130) and nothing
   after, across the same 13 healthy L1s. 3B (`book='basket_nogate'`) kept booking at every
   weekly L0 (runs 167, 253, 288 — 06-14/06-21/06-24) **through the same `select_structure` +
   byte-identical `contract_eligible` eligibility on the same OPRA gate feed**
   (`fixed_basket.py:242-246, 279-283`; the L0 3B provider is built with `option_feed=gate_feed`,
   `orchestrator.py:439-441`). The structure/eligibility path is alive on OPRA → **H_b and H_e
   dead** for the books' silence.
2. **One provider object, shared.** `orchestrator.py:580` builds ONE `AlpacaChainProvider`
   (OPRA post-flip) passed to the real cycle, the shadow booker, 3A, the dual-read record arm,
   AND `record_cheapness`. The watch — same object, same eligibility, same gate — reads
   structurable + `cheap=1` on 89/105 all-time observations; the dual-read OPRA arm structured
   38/39 names on 2026-07-01 (sole failure: UROY `no_eligible_contract_in_tenor_window`, a
   known thin-tenor case). **H_a dead** (no feed divergence to hide behind — the booker and the
   instruments see the same chain, and it structures).
3. **Nothing threw.** `errors=0` on every relevant result; no fail-soft pages ever fired for
   the booking passes. **H_c dead** (the DEBUG-level concern was real as an observability hole,
   but nothing was being thrown through it).
4. **The saturation arithmetic closes exactly.** Live `discovery.sentinel_max_slots = 6`.
   The shadow book holds exactly **6 open sentinel-origin** positions since run 130 (SMCI@37,
   RTX/NEE/LHX@92, PL/FLNC@130); 3A independently holds 6 sentinel-origin + 1 hand-seed of the
   same symbols (each book counts its OWN open sentinel rows — `shadow_book.py:136-139`,
   `fixed_basket.py:130-132`). The hand-seed side of the union is **only the two EXAMPLE
   placeholder themes** (`themes.json`: FCX — already open since run 37 → dedup-skip; NVDA —
   gate-rich → not_cheap). With 0 resolutions ever (long-dated book, ~1 mo old), the slots can
   never free. **Every candidate of every L1 since 06-10 is accounted for: skip (FCX), not_cheap
   (NVDA), or slot-veto (every sentinel). booked=0, errors=0 — silent by the log guard.**
5. **The 06-10 dating was a confound, not a cause.** Run 130 was BOTH the first OPRA L1 AND the
   run that filled sentinel slots 5–6 in both books. The flip-day correlation that motivated
   H_a/H_b is fully explained by H_d.
6. **The pre-flip counterfactual ("they would have booked before the flip") was false for most
   of the missing cohort:** AG/PAAS first surfaced as sentinels 2026-06-24; HBM/UEC/UUUU the
   morning OF 06-10; only RKLB/VRT predate the flip (surfaced 06-03). PAAS has **never** reached
   `council_proposals` at all (union rank-truncation at `council.max_candidates=12` — the known
   2026-06-25 F3 finding) while reading `cheap=1` in the dual-read since 06-23.

**Character of the finding:** the zero-booking is the frozen design working
(PREREG_FIXED_BASKET_NULL §4 pins cap-inheritance deliberately: "the apparatus's caps *are*
part of the apparatus"). The **defect** is observability: `orchestrator.py` logged the booking
result only behind `if booked or halted`, `vetoed` was reason-blind, and per-candidate
exceptions logged at DEBUG → a veto-saturated arm was indistinguishable from a dead one for
three weeks. Fixed bug-agnostically in **PR #137** (per-reason veto counters + always-log +
errors at WARNING + non-fatal error page), shipped independent of this diagnosis.

## §4 — THE PINS (pre-probe; committed before the probe runs)

The mechanism is settled by §3; the probe is **CONFIRMATORY + CAPACITY-QUANTIFYING**, not
discriminating. Design: stepwise replicate `run_shadow_cycle` per union candidate on the live
OPRA provider — union → active/dedup/origin → slot state → `select_structure` (+ reasons) →
`is_cheap_convexity` → cluster headroom → sizing — **read-only** (ro DB, no booking, no writes,
no broker import). Caveat pinned: it runs post-close (~21:00 UTC); quotes are the closing
snapshot. In-window corroboration exists independently (the 19:47/19:48 UTC #389 watch +
dual-read rows).

**Pinned expectations, and what REOPENS the diagnosis:**

- **P1:** every active sentinel candidate not already open is vetoed at the slot step, before
  eval. **REOPEN if any sentinel-origin candidate reaches eval.**
- **P2:** hand-seed FCX → dedup skip; NVDA → structure FOUND (OPRA), then gate `not_cheap`.
  **REOPEN (H_b revives for hand-seeds) if NVDA fails at `select_structure`.**
- **P3 (capacity counterfactual — slots hypothetically freed):** expected from cluster
  arithmetic (cluster budget = 2% × $100k = $2,000 entry-premium): silver (AG/PAAS — cluster
  empty) and nuclear (UEC/UUUU — cluster empty) book if structurable + cheap + sized; **VRT
  likely `cluster_cap`** (ai_capex_power headroom $2,000 − NEE $984 − FLNC $705 = **$311**);
  HBM books if its wing ≤ $1,138 (copper headroom after FCX $862); RKLB books if ≤ $1,170
  (space_smallcap after PL $830). Falsifiable by the probe's live premiums.
- **Pinned interpretation regardless of the counterfactual count:** it MEASURES the capacity
  cost of cap-parity in the control arm. It does **NOT** authorize a cap change — any change to
  the null books' caps is a PREREG_FIXED_BASKET_NULL §4 amendment, operator-gated (§8).

## §5 — Probe result (appended post-run; ran 2026-07-01 22:46 UTC, post-close)

Driver: `~/probe_shadow_stepwise.py` (ephemeral, read-only; one probe-side attribute typo —
`GateVerdict.iv_rv` vs the real `iv_rv_ratio` — errored the first pass and was fixed before any
result was read; the pins were untouched). Union = 37 (2 hand-seed + 35 sentinels); 7 open →
skip; live OPRA gate provider.

**Every pin held; the diagnosis is CONFIRMED, nothing reopens:**

- **P1 ✅** — all **29** non-open sentinel candidates vetoed at the slot step
  (`open_sentinels=6 ≥ max_slots=6`); **zero** sentinels reached eval.
- **P2 ✅** — FCX `skip_open`; NVDA reached eval, `select_structure` **found** its OPRA wing
  ($1,455) and the gate vetoed `not_cheap` at iv_rv **1.211** (> 1.2; the dual-read's 19:47
  in-window read was 1.2075 — same verdict, post-close drift only).
- **P3 ✅ (capacity counterfactual, slots hypothetically freed):**
  **16 / 29 WOULD BOOK** — AG($158×6) PAAS($315×3) HL($113×8) [silver, headroom $2,000] ·
  UUUU UEC NXE NNE CCJ SMR [nuclear, $2,000] · HBM($470×2) ERO TGB [copper, $1,138] ·
  FLY RDW LUNR [space_smallcap, $1,170] · FRO($228×4) [freight, $2,000].
  **9 cluster_cap** — VRT/AMSC/ATKR/GEV/ETN on ai_capex_power's **$311** headroom (pinned
  arithmetic exact); RKLB($2,440)/IRDM($1,265) > space_smallcap's $1,170; LMT/KTOS >
  space_defense's $442. **4 not_cheap** — NVDA, PWR(1.323), NOC(1.251) rich; CDE iv_rv 0.318
  but **skew-vetoed** (the known 45-volpt wing). **1 no_structure** — UROY (the known
  thin-tenor case; matches the dual-read's sole OPRA failure).

**The capacity finding, quantified:** the control arm is structurally excluding 16 current
gate-passers (incl. the entire silver/nuclear cheap cohort) via the slot reservation, plus 9
more via cluster caps — 25 of 29 sentinel vetoes are CAP vetoes, not market vetoes. Per the §4
pin this measures the cost of cap-parity; it authorizes nothing (§8 remains the operator's
design decision). Also confirmed in passing: PAAS — never council-judged (rank truncation) —
is a live WOULD_BOOK in the gate-only arm; the shadow book was precisely the instrument meant
to catch names like it, and the slot cap is why it hasn't.

## §6 — Dated annotation for PREREG_FIXED_BASKET_NULL — **APPLIED 2026-07-02 (operator-authorized)**

Applied inside the §4 amendment in `PREREG_FIXED_BASKET_NULL.md` (this PR — the final text
lives there). **Framing corrected before freezing (operator's P2, 2026-07-02): the arm was
CENSORED, not dead.** The bookers ran healthily every cycle, applied the frozen frame
correctly, and vetoed on slots by design; the monitors marked correctly throughout. The defect
was *invisibility* (fixed, PR #137), not function. **The first-6 cohort (booked 06-03→06-10)
is a VALID sample of week-one gate-passers — its rows are not suspect** and stay in every read
as vintage 1. The session language that escalated to "dead control arm" is retracted on the
record here.

## §7 — Posture-review backstop — **PINNED 2026-07-02 (operator-authorized, blind)**

**Applied as a dated amendment to `PREREG_THEMATIC_CONVEXITY.md` §6 (this PR — final text
there).** Pinned: entries-clock anchored at go-live **2026-06-02**; **interim checkpoint
2026-11-02** (added per the advisor's reachability point — placed at the opening of the first
structural resolution window, so a censored-but-healthy-looking state cannot accumulate unseen
for the full window: the exact lesson of this diagnosis); **review trigger D = 2027-03-02**;
review-not-kill; both legs' reachability pinned honestly. The original motivation text follows
for lineage:

**The gap, per the frozen letter:** PREREG_THEMATIC_CONVEXITY §6 halts on "the book **bleeds 9
months** with zero payoff." *Bleeding presupposes premium at risk* — an EMPTY book never starts
the clock. No other frozen text supplies a substitute trigger (grep-verified). The T4 conds
(2)/(4) require resolved positions, so an indefinitely-empty book indefinitely blocks
graduation **without violating anything**. The waiting posture is currently unfalsifiable — the
operator's P1 (2026-07-01), confirmed at the letter of the frozen text.

**Proposed dated amendment to PREREG_THEMATIC_CONVEXITY §6 (review-not-kill; values are
PROPOSALS for the operator's blind pin):**

> **Posture-review trigger (added 2026-07-01, before any outcome is visible; the null books are
> blind — 0 resolved):** the entries-side clock anchors at **forward-loop go-live (2026-06-02)**,
> not at first entry. If by **D = 2027-03-02** (9 months from go-live — symmetric with the
> frozen 9-month bleed constant) the real book has had **zero entries ever**, a mandatory
> operator **posture review** triggers: hold-with-re-dated-trigger, open the criteria-
> reconsideration branch (IMPLEMENTATION_PLAN §T4 fork 3), or stand down. The review is a
> decision point, NOT an automatic kill and NOT evidence the edge is absent (§7 discipline
> unchanged). Optional soft checkpoint **2026-10-01** (dashboard/heartbeat line only, no
> action).
>
> **Reachability honesty (pinned):** any conjunctive "0 resolved null positions" leg is
> **vacuously true before ~Nov–Dec 2026** (earliest structural resolutions: 21-DTE time-stop on
> Dec-2026–Jun-2027 expiries). Before that date the zero-entries leg ALONE carries the trigger;
> a reader must not mistake the resolved-leg's silence for evidence.

## §8 — Control-arm capacity — **DECIDED 2026-07-02: option (b), symmetric slot relief (operator-authorized, blind)**

**Decision + rationale (the operator's, recorded):** cap parity was frozen so `real − shadow`
isolates the council, but **parity-of-caps does not produce parity-of-OBSERVATION** — because
shadow lacks the council's veto it saturates its six slots in week one and goes blind, while
the (empty) real book keeps free slots and keeps judging every cycle. The arms do not face the
same opportunity set; the null sample censors to week-one cheapness — a selection bias in the
control, not a controlled comparison. The capital-risk rationale for slot caps does not bind a
simulated book that deploys nothing. **Relief RESTORES the isolation parity was meant to buy.**
Decided while blind (0 resolutions anywhere — the anti-HARK property expires at the first
resolution, ~Nov 2026; hence decided now). Scope: **slots only, symmetric shadow+3A** (the
`shadow − 3A` contrast stays clean), cluster/book/per-name caps and the REAL book
byte-unchanged, 3B untouched (already the uncensored whole-basket read). Applied in this PR:
the `PREREG_FIXED_BASKET_NULL.md` §4 dated amendment + code (`discovery.null_sentinel_max_slots`
explicit re-enable knob; the null books no longer read the real book's `sentinel_max_slots`;
`paper_loop.py` untouched) + tests both ways. **The relief deploy = vintage boundary 2.**

Original options for lineage — (a) keep parity (leaves the branch-3 measurement channel
censored ~5 months for no capital-safety benefit); **(b) slot relief — SELECTED**; (c)
observability only (PR #137, shipped, kept regardless).
