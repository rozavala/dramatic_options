# PREREG — Fresh-Inflection Funnel Re-Target (the discovery prescreen)

**STATUS: FROZEN 2026-06-22 — operator-authorized ("freeze + build"); §10 pins ratified as proposed.**
The freeze takes effect on merge of this PR (pre-reg → build merge order); the BUILD PR is held past the
2026-07-10 dual-read close-out (single-variable). Converged over two code-grounded red-team rounds (R1
v1→v2, R2 v2→v3). Anti-HARK: pinned **blind to forward outcomes** — the freshness parameters were informed
by a read-only cross-sectional probe of the *current* funnel state (§1), never a forward include/trade
result (there are none — the book is empty). Disclosed like the OPRA tripwires.

This amends the **funnel knobs** of `discovery.py` (the T3 prescreen, `PREREG_THEMATIC_CONVEXITY §2`). It
does **not** touch the IV gate, cluster cap, council prompts, risk frame, or any capital-authorizing layer.

**R1 disposition (v1→v2):** P1-1 (§7 → `_marker_evidence`; golden-breaking; segmentation broadened to
framer+council). P1-2 (staling confirmed; merge held past 7/10; OLD segmented-not-erased; comparison
tempered). P2-3 (dedicated `runs.discovery_funnel` column + migration). P2-4/5/6/7/8 + P3-9..13 folded.
**R2 disposition (v2→v3):** R2-1 (§7 horizon-LABELED render — the freeze-blocker); R2-2 (§8.1 softened —
within-basket z is *relative*, so the rank prefers freshness but can't guarantee a monster-free top-K on a
scarce universe); R2-3 (§10 yield band restated self-contained + split unit-invariant / live-descriptive);
R2-4 (`clears_gate` reordered so `fresh` is observable); R2-5 (`rv_slope`-only surfacers' limbo
acknowledged). Open dial → **decided: both** (§7).

---

## §1 — Motivation, the probe evidence, and the honest ceiling

Funnel surfaces candidates; council judges `under_narrated ∧ at_inflection ∧ structural ∧ ≥MODERATE`;
IV gate disposes on cheapness. The council's evidence-based `at_inflection` (the `_COMMON` system prompt,
sha-pinned CGS §10.7):

> "(3) AT A GENUINE INFLECTION — the change is happening NOW: if the large move has **already happened**,
> the inflection is BEHIND the name … unless the evidence shows a NEW, distinct inflection. **Reason only
> from the EVIDENCE provided.**"

The evidence a sentinel carries = its **markers** (rendered by `council/context.py:_marker_evidence`) +
§9 fundamentals + news counts. **Today the funnel feeds `at_inflection` the wrong names.** A read-only
NO-FETCH probe over the universe (warm PIT cache, as-of 2026-06-21; the 5 window-#2 admits aren't cached
yet — characterized from the handoff: already ran 90–190%, `rv_slope<0.25`):

- **Current funnel surfaces 28 of 33.** The `|mom_12-1| ≥ 0.15` leg fires for post-move monsters —
  **RKLB +382%, PL +715%, VRT +177%, LUNR +217%, UUUU +175%** — all `rv_slope` flat/negative (the move
  is behind them; `at_inflection=False` is the council's correct read).
- Only **`scan_top_k = 8`** become sentinels, and `inflection_score` is **|momentum|-magnitude-
  dominated** → the monsters consume the council's 8 slots and **crowd genuinely-fresh names out of view.**
- A leg keyed on **recent** momentum + **rising** vol catches names the trailing gate **misses**: e.g.
  **ATKR** (`mom_12-1` only +10% → unsurfaced, but `mom_3m +44%`, vol rising +33%) and **FLY**.

**So the funnel and the gate are mis-aligned, and the funnel is the fixable side** — rank-driven first
(the rank is explicitly "ordering only, never a signal", prescreen §2), surface-additive second.

**The honest ceiling — three things this pre-reg will NOT pretend away:**
1. **Motion-freshness only PROXIES the council's `at_inflection`** (a thesis judgment over fundamentals +
   narrative + markers). This raises the *conditional* probability a surfaced name clears `at_inflection`;
   it **cannot, and must not, manufacture includes**.
2. **Expect the binding constraint to RELOCATE, not fall.** The re-target + §7 fix `at_inflection`'s feed,
   but `under_narrated` stays funnel-blind and evidence-thin (news counts + fundamentals only — the
   prescreen is forbidden from touching coverage, §2). Most likely forward outcome: fresh names reach the
   council, **clear `at_inflection`, then get rejected on `under_narrated`/thin-news grounding.** The wall
   moves from `at_inflection` to `under_narrated + grounding`. That relocation is the useful diagnostic —
   it isolates the true frontier (the quietness/corpus lever, §12).
3. **Freshness is scarce on this curated universe** (every name keys to a narrated, largely-moved secular
   theme). This reorders the council's view + catches a couple of missed quiet-movers; it is
   **complementary to the quieter-universe lever**, not a substitute.

---

## §2 — The hard-seam argument (endorsed R1, unchanged)

**Objection:** the plan-review rule forbids "a prescreen that ranks by the gate's own pass-criterion."

**Defense (rests on all four):**
1. **The forbidden alignment is with the CAPITAL-AUTHORIZING layer (the IV gate / cheapness).** The
   prescreen makes **no cheapness claim** — unchanged. The council is a *judgment overlay* (forward-scored,
   never authorizes capital, never overrides a veto). Aligning the funnel with it cannot defeat a capital
   veto; the IV gate disposes on cheapness independently.
2. **The prescreen stays in the MOTION lane** (deterministic price/vol). The council reasons over strictly
   more and **rejects independently** (0 includes even on today's surfaced fresh names).
3. **`under_narrated` (the OTHER ~1/8-pass binding leg) is left untouched + funnel-blind.** Coverage/
   narration stays **out of the prescreen entirely** (§7) → the council retains a fully-independent binding
   leg the funnel cannot pre-select. Structural proof the council still does real work.
4. **The seam — discovery proposes, council judges, gate disposes — is unchanged.**

**Corollary leash (structural):** coverage / news-count / any narration proxy is **forbidden** in the
surface gate AND rank (would pre-select `under_narrated`). The gate/rank functions take only price/vol/
event markers.

---

## §3 — The freshness markers (deterministic; blind-pinned §10)

Added to `MarkerSet` / `compute_markers`, all as-of, fail-soft, in the motion lane; ride the existing
`markers` JSON:

- **`mom_recent`** = `momentum(lookback=R, skip=0)` — recent-window return, **skip=0**. *Caveat (R1
  P3-10): `skip=0` re-admits the 21-day reversal window `mom_12-1`'s `skip=21` excludes — accepted
  because the 63-session window dilutes it and `fresh_mom_floor 0.20 > mom_floor 0.15` compensates; it
  also feeds §6 direction.*
- **`rv_rising`** = `(rv_21 − rv_M) / rv_M`, `rv_M = realized_vol(·, w=M)` — vol **accelerating, not
  rolling over**. (`rv_slope` = `(rv_21 − rv_252)/rv_252`, retained as a surface disjunct only, NOT the
  rank — §5.)

`mom_12-1` is **retained** (surface disjunct + still computed; removed only from the rank, §5).

---

## §4 — The surface gate (ADDITIVE freshness disjunct)

`clears_gate` stays a **disjunction on absolute floors** (never a blend — the FSSD lesson). **Add one
disjunct; remove none.** Surface iff:

> structural event OR **( `|mom_recent| ≥ fresh_mom_floor` AND `rv_rising ≥ fresh_rv_rising_floor` )**
> OR `|mom_12-1| ≥ mom_floor` OR `rv_slope ≥ rv_slope_floor`

**Disjunct ORDER (R2-4):** `clears_gate` returns the *first* matching reason, so the fresh conjunct is
checked **before** the `mom_12-1`/`rv_slope` legs (order: event → **fresh** → momentum → rv_slope). This
makes the `"fresh"` gate-reason **observable** for the whole fresh cohort (a name clearing both fresh and
momentum is labeled `fresh`, not `momentum`) — needed for §8.1's "fresh cohort enters" telemetry. (Events
keep priority; a structural filing is the highest-signal surfacer.)

The new leg is a **conjunction inside one disjunct** (recent move *and* vol rising = a fresh start),
surfacing quiet-but-just-moving names the trailing legs miss (ATKR, FLY). **Additive:** nothing surfacing
today stops; monsters still surface via `mom_12-1` but are *demoted by the rank* (§5).

Probe sanity-check (a check of the §10 pins against the current cross-section, not a fit): the new leg
fires for ATKR (`mom_3m 0.44`, `rv_rising 0.33`) and FLY, **not** the monsters (RKLB `rv_rising −0.04`,
VRT `−0.12`, PL `mom_3m 0.05` — each fails a conjunct).

**Control-population note (R1 P3-9):** the additive leg moves ATKR/FLY from `eligible_unsurfaced` into
`cleared`, shrinking the control pool — handled by the per-run funnel stamp (§8), identical-arms.

---

## §5 — The rank re-target (the core change)

`rank_basket`'s `inflection_score` currently = within-basket `z(|momentum|) + z(rv_slope) +
z(|rel_strength|) + event_bonus`. The `z(|momentum|)` term crowds the monsters into the top-K.

**Replace with a clean two-term freshness composite (R1 P2-5):**

> `inflection_score` = within-basket `z(rv_rising) + z(|mom_recent|) + event_bonus`

- `z(|momentum|)` (trailing 12-1) and `z(|rel_strength|)` (a 12-1-derived magnitude proxy) **removed.**
- **`z(rv_slope)` removed from the rank:** `rv_slope` and `rv_rising` share the `rv21` numerator →
  double-weight vol; worse, `rv_slope` stays *high* for a recently-spiked monster whose vol is still above
  its annual base → re-imports the magnitude signal this swap removes. The single acceleration term
  `rv_rising` is the clean freshness vol-signal. (`rv_slope` keeps its surface-disjunct job, §4.)

**Control-arm integrity (verified):** the control pool = eligible names that **did not clear the gate**
(`scan_baskets`: `m.eligible and m.symbol not in cleared_syms`). Cleared-but-not-top-K names fall out of
*both* surfaced and control → the re-rank cannot contaminate the control arm.

**Limbo acknowledgment (R2-5):** a name clearing **only** via `mom_12-1` (monster) **or only via
`rv_slope`** (re-expanding vs 1-yr, but no recent move and no rising-vs-quarter vol) clears the gate but
gets a low freshness-rank z → lands in cleared-but-not-top-K limbo, contributing only to `n_cleared` /
`by_basket` (curation-health). This is the **accepted tradeoff**: the rank dimension is freshness, so the
two non-freshness surface disjuncts are now *surfacing-only* (curation visibility), not rank-bearing — by
design, stated so they aren't quietly decorative.

---

## §6 — Direction under freshness

A fresh inflection's tradeable direction is the **recent** move. `direction_of` currently keys on
`mom_12-1`. **New rule:** direction = `sign(mom_recent)` when `|mom_recent| ≥ dir_recent_epsilon` (pinned
§10), else `sign(mom_12-1)`, else `sign(rel_strength)`, else bullish. A fresh rollover then surfaces
**bearish/puts** (NOC `mom_3m −0.27`). A behavior change where recent/trailing disagree; intended.

---

## §7 — Council + framer grounding via `_marker_evidence` (R1 P1-1 target; R2-1 render)

**The grounding the council reasons over is `council/context.py:_marker_evidence`** (it builds
`RECENT_HEADLINES` from a fixed key list) — **NOT** `sentinels.py:marker_summary` (that feeds
`operator_thesis`, "NOT counted as grounding evidence", context.py:38). Change:

- **Add `mom_recent` + `rv_rising`** to `_marker_evidence` (so `at_inflection` reasons over freshness — the
  §9 evidence-never-permission pattern) **and to `markers_dict`** (persistence).
- **R2-1 — HORIZON-LABELED render (the freeze-blocker).** Today `_marker_evidence` renders bare keys
  (`f"{key} {v:+.3f}"` → `momentum +3.820`), so the council can't tell trailing from recent — defeating
  §7's purpose. Render each marker with an explicit horizon label so the recent-vs-trailing contrast is
  legible (the **display labels** carry horizons; the underlying `markers` dict keys are unchanged):

  | dict key | display label | meaning |
  |---|---|---|
  | `momentum` | `momentum_12m` | trailing 12-1 (252d, skip 21) |
  | `mom_recent` | `momentum_recent_3m` | recent 63d, no skip |
  | `rel_strength` | `rel_strength_12m` | 12-1 vs benchmark |
  | `rv_slope` | `rv_reexpansion_1y` | rv21 vs rv252 |
  | `rv_rising` | `rv_accel_3m` | rv21 vs rv63 |
  | `rv` | `rv_annualized` | trailing realized vol |

  Order them so the contrasting pairs are adjacent (`momentum_12m` then `momentum_recent_3m`;
  `rv_reexpansion_1y` then `rv_accel_3m`).
- **This is a deliberate, golden-breaking change** (R1 P1-1): `RECENT_HEADLINES` is **not** in the
  conditional render block (context.py:73-88), and relabeling changes the existing markers' bytes too →
  **update `test_evidence_grounding.py::test_framer_sentinel_pack_byte_identical`** to the labeled form, as
  a pre-registered dated change.
- **Both packs (framer + council) are enriched — DECIDED (R2 dial).** Both call `_marker_evidence`. The
  framer was **already** grounded on these surface markers (it rendered `momentum`/`rv_slope` pre-§7), so
  enriching it adds **no new circularity** between "what surfaced the name" and "what the skeptic judges" —
  that coupling pre-exists; and the segmentation cost is **theoretical** (empty book, no framer forward-
  scores resolved). The coherence gain (the upstream skeptic judging on the same evidence as the council)
  is real. *Documented fallback (not taken): council-only via conditional render — buys only one untouched
  golden, at the cost of the framer judging on a poorer marker set than the council.*
- **§6 corpus-leash NOT violated:** the leash (context.py:19-21) forbids moving NEWS_COVERAGE / leaking the
  §9 fundamentals corpus — markers are the framer's native food. **Verify the leash scope at build.**
- **Segmentation broadened (§8):** the §7 enrichment makes the **framer's** forward-score AND the
  **council's** Brier substrate record-segmenting under the funnel stamp, alongside the discovery null.

**Coverage stays OUT** (§2 corollary). The council already gets coverage via §9 news counts.

---

## §8 — Forward measurement, segmentation, the regime boundary (anti-HARK)

1. **What "the re-target worked" means (R2-2 — corrected, not over-claimed).** The re-rank makes
   **magnitude no longer the rank dimension**; the **relatively-freshest** names in each basket surface.
   But within-basket z is *relative* — on an **all-monster basket** (a fully run-out theme), the
   *least-stale* monster still gets a positive within-basket z and competes across baskets for a top-K
   slot. So the rank **prefers** freshness but **does not guarantee** a monster-free top-K on a
   freshness-scarce universe (the one §1.3 admits this is); it surfaces the *relatively* freshest, which on
   a run-out basket is "least stale," not "fresh." The rank can't manufacture freshness that isn't there.
   *Documented-not-taken alternative: an absolute `mom_recent`/`rv_rising` rank-eligibility floor would
   force a fresh-only top-K (at <8 names some weeks), at the cost of the clean surface-gate/ordering-rank
   separation — declined to keep the architecture clean; §1.3 sets the scarcity expectation.*
2. **Segmented-then-restarted, NOT erased (R1 P1-2).** The four-scan **discovery sizing-clock read**
   (`PREREG_THEMATIC_CONVEXITY §5`) is **already staled** by window #2 — verified live: scans 1 (run #167,
   6/14) + 2 (run #253, 6/21) ran on the 33-name universe; window #2 landed 6/22; scan 3+ runs on the
   38-name universe. So the new funnel aborts no clean measurement. OLD records stay **stamped + auditable**
   via the funnel version; a future tail read **never pools** OLD and NEW. **HONEST LIMIT:** empty book +
   3-then-0 surfaced sentinels = the OLD arm is **immature** — the stamp buys no-pooling honesty, NOT a
   powered comparison. *Side benefit of the merge-hold (R2): the OLD funnel keeps accruing (stamped
   legacy/NULL) through scans 3–4 on the 38-name universe until merge, marginally maturing the OLD arm
   before the switch — costs nothing.*
3. **Segmentation covers THREE forward-scored layers** under the funnel stamp (R1 P1-1): the discovery
   null (`sentinel_scoring` surfaced-vs-control TAIL), the **framer** score, the **council** Brier — all
   join the single `run_id`→`runs.discovery_funnel` stamp.
4. **`at_inflection` pass-rate on surfaced sentinels is a MEASURE, not a TARGET** — expected to rise vs the
   pre-re-target ~1/8, but **no include count is a success gate** (the HARK leash). The expected
   *relocation* of the wall to `under_narrated` (§1.2) is the read to watch.
5. **Disclosed:** the §10 floors were set against the 2026-06-21 cross-section (blind to forward outcomes).
   Re-tuning against a forward result is HARK — itself a dated, segmented regime change.

---

## §9 — Implementation surface + segmentation substrate

- **`discovery.py`:** `MarkerParams` (+ `mom_recent_lookback`, `rv_mid_window`, `fresh_mom_floor`,
  `fresh_rv_rising_floor`, `dir_recent_epsilon`); `MarkerSet` (+ `mom_recent`, `rv_rising`);
  `compute_markers`; `clears_gate` (+ §4 disjunct, **fresh checked before momentum**, `"fresh"` reason);
  `rank_basket` (§5); `direction_of` (§6); `synthetic_market`/demo (a fresh-mover ramp + a post-spike
  monster).
- **`council/context.py` (R1 P1-1):** `_marker_evidence` += `mom_recent`/`rv_rising` keys, **horizon-
  labeled render** (§7 table).
- **`sentinels.py`:** `markers_dict` += the two values. `marker_summary` is NOT the grounding — default
  leave. `revalidate_active` semantics unchanged (§11-Q2).
- **`config.json` `discovery.markers`:** the new params.
- **Segmentation stamp — DEDICATED column (R1 P2-3):** `frame_version` hashes only `{convexity_book,
  convexity_gate,convexity_exits,kill_rule}` (config_loader.py:169-172) → won't move on a `discovery.markers`
  change. Add **`runs.discovery_funnel`** via an idempotent `ADD COLUMN` migration (0009/0011/0013
  precedent), written each run (`"fresh_v1"`; legacy/NULL = pre-re-target). One column suffices — discovery
  null, framer, council all carry `run_id` and join to it.
- **Tests:** new-marker computation; the fresh disjunct (fires on a fresh ramp, not a post-spike synthetic);
  **the freshness-rank UNIT INVARIANT (§10)**; `clears_gate` labels `fresh` when the fresh conjunct clears
  even alongside momentum; direction under recent-vs-trailing disagreement; `_marker_evidence` enrichment +
  the **updated** byte-pinned golden (labeled form); an anti-HARK value test pinning the §10 floors;
  migration idempotency.
- **One migration** (`runs.discovery_funnel`). First paper entry stays market-gated.

---

## §10 — The blind pins + the yield band

| knob | proposed | rationale |
|---|---|---|
| `mom_recent_lookback` (R) | **63** (~3mo), skip 0 | standard "recent" horizon; 21 is reversal-noise, ≥126 re-admits the already-run |
| `rv_mid_window` (M) | **63** | `rv_21 > rv_63` = short vol above quarter vol = accelerating, not post-spike fade |
| `fresh_mom_floor` | **0.20** | a real recent move, above `mom_floor` 0.15 (recent windows noisier) |
| `fresh_rv_rising_floor` | **0.10** | vol meaningfully rising, below `rv_slope_floor` 0.25 (a *rising* not *re-expansion* bar) |
| rank terms | **`z(rv_rising) + z(\|mom_recent\|) + event_bonus`** | clean 2-term freshness composite (R1 P2-5) |
| `dir_recent_epsilon` | **0.02** | a 2% recent move sets direction; below it, trail (R1 P2-6) |
| `runs.discovery_funnel` | **`"fresh_v1"`** | the §8 regime boundary |

**Yield band (R2-3 — split, self-contained):**
- **Deterministic UNIT INVARIANT (universe-independent, a test):** in a synthetic basket containing a
  fresh-ramp name and a post-spike monster (`mom_12-1 ≥ 1.0 ∧ rv_slope < 0.25`), the fresh name **out-ranks**
  the monster. Proves the rank prefers freshness; always holds.
- **Live first-scan DESCRIPTIVE read (universe-dependent, investigate-not-bank):** report the new top-K;
  **expected** = no name with `mom_12-1 ≥ 1.0 ∧ rv_slope < 0.25` in the top-K AND ≥1 fresh-leg name present.
  This is self-contained (no need to re-run the old rank — R2-3). **Failure is a real signal, not
  necessarily a bug:** either mis-pinned floors OR a genuinely freshness-scarce week (§1.3, §8.1) →
  investigate, don't bank. **NOT a hard gate** (the universe can be picked-over). **No include-count
  target** (§8.4).

---

## §11 — Self-red-team + the resolved dials

Passes pre-empted: seam (§2, load-bearing = untouched `under_narrated`); HARK (§8.5 + §10 principled pins);
regime/null integrity (§5 + §8 dedicated stamp); additive-not-destructive (§4); direction (§6); wiring
(R1 P1-1, verified file:line); segmentation home (R1 P2-3, verified); render legibility (R2-1, verified);
rank over-claim (R2-2, corrected).

**Resolved dials:**
1. **R/M = 63/63 — yes.** Collinearity handled by dropping `rv_slope` from the rank (R1 P2-5).
2. **`revalidate_active` force-dormant on freshness decay — NO.** ANY-leg semantics already handle it.
3. **Keep `mom_12-1` — KEEP**, for the minimal-`clears_gate`-change + curation-health reason (R1 P2-4);
   the v1 "preserves the forward cohort" claim was wrong. DROP (→ monsters control-eligible) is a larger
   change, deferred.
4. **Restart the four-scan read now — staling CONFIRMED** (§8.2); **but hold the MERGE behind 2026-07-10**
   (single-variable) and segment-not-erase. Build + freeze now; merge after.
5. **§7 framer+council enrichment — BOTH** (R2 dial; no new circularity, theoretical cost, coherence gain;
   council-only documented as the un-taken fallback).
6. **Absolute rank-eligibility floor (R2-2) — NOT TAKEN** (documented in §8.1); state the scarcity
   limitation honestly rather than complicate the gate/rank separation.

---

## §12 — Lineage reconciliation (CGS §8) + scope fence

**Reconciliation with `PREREG_COUNCIL_GATE_SEPARATION §8` (R1 P2-7).** CGS §8 names the funnel frontier as
*"rank thematic candidates on **quietness + cheapness**, not motion"* and flags a quiet name as *"invisible
to a motion funnel."* **This pre-reg deliberately DIVERGES**, and the divergence is the *correct* one:
ranking on **cheapness** pre-selects the IV gate (forbidden, §2), ranking on **coverage** pre-selects
`under_narrated` (§2 corollary). CGS §8's sketch was itself seam-violating; this pivots to a **seam-clean
motion-freshness** refinement. **Therefore this is NOT "the §8 funnel item" — it is a narrower
motion-profile refinement that does NOT address §8's quietness blindness.** A genuinely-quiet flat name
(NNE/CEG: `mom +0.06`, flat `rv_slope`, low `mom_recent`, low `rv_rising`) **still won't surface** under
the fresh leg. The quietness frontier stays **OPEN** = the quieter-universe / corpus-generator lever — and
§1.2's expected wall-relocation to `under_narrated` is why that lever is the real fix. This re-target is
**complementary**: it cleans the `at_inflection` feed so the relocation is visible and measurable.

**Scope fence:**
- Does **not** touch the IV/cheap-convexity gate, cluster cap, council prompts (§10.7), risk frame,
  sizing, or any capital-authorizing path. First paper entry stays market-gated.
- Does **not** add coverage/narration to the prescreen (§2 corollary).
- Does **not** claim to produce includes (§1.1) or to fix quietness (§12).
- Does **not** resurrect a graded-negative edge — `mom_recent`/`rv_rising` are funnel markers ("something
  fresh is happening"), never a tradeable/alpha claim (the FSSD/divergence graves).
