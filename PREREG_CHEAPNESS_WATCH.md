# PREREG — Cheapness-Watch (finding #1's gating instrument)

**Status: DRAFT for operator sign-off (2026-06-26).** Pins the cheap-window / break-trigger / `cheap`
threshold **BLIND, before either arm runs** (anti-HARK). The definitions are mostly **INHERITED** (the
live gate's `cheap` boolean, the funnel's fresh floor) — not invented — so the only real pin is the
**counting methodology**, frozen here so the historical data cannot shape it. The historical arm is an
advance read *against* these frozen definitions, never an input to them.

## §1 — Purpose

The gating instrument for finding #1's `PREREG_FRESH_INFLECTION_FUNNEL §7.1` re-open trigger: when a
staged name **breaks**, measure whether there is a cheap-entry window and **how wide**. That width vs the
**staleness lag** (the next-L0 + top-K re-surface latency — measured live at **16.7d median / 23.7d max**
on run #337, 2026-06-26) decides whether the marker-refresh ("persist") fix is worth building. A wide
cheap-window ⇒ the trigger does **not** fire ⇒ the persist fix is low-value.

**Standalone, read-only measurement.** Never wired into `at_inflection` (the hard seam — cheapness is the
deterministic gate's job, not the council's); never trades; fail-soft; its own table + a dashboard panel.
Diagnostic only (like `marker_staleness`).

## §2 — Blind pins (frozen before any arm runs)

1. **`cheap` threshold — INHERITED:** the live gate's `cheap` boolean (`convexity_gate`: `IV/RV ≤ 1.2`
   ∧ `OTM_wing − ATM skew ≤ 10` vol pts). No new threshold is introduced.
2. **The priced structure — INHERITED:** the live `structure`/`convexity_gate` selection (15–35% OTM,
   180–365d, defined-risk, `target_moneyness 0.25`). The watch prices the **same wing a real entry would
   pick** — the real-extractor discipline, never a proxy wing.
3. **break trigger — INHERITED:** the funnel's fresh leg, `|mom_recent| ≥ 0.20 ∧ rv_rising ≥ 0.10`
   ("a fresh inflection just started").
4. **cheap-window + §7.1 trigger — SUPERSEDED by §2.1 (single source of truth).** The original
   first-cross→first-flip window and the cheap-window-`<`-lag trigger are replaced by §2.1's debounced
   break-onset, **sustained** (2-consecutive) close, the three `cheap_window`/`never_cheap` states, the
   `marker_age_at_break` selection dimension, and the **JOINT** trigger. Read §2.1, not this item.

## §2.1 — Live-arm state-machine pins (amendment 2026-06-26, BLIND, before the build exists)

"Days the gate stays cheap after a break" hides definitions the secular-ramp cohort makes non-trivial
(no clean onset — the cutoff-straddle problem the narration probe dropped). Pinned blind, before the
module is written, so the deciding measurement isn't defined after seeing data:

1. **break-onset (clock START):** the FIRST session the funnel's fresh leg crosses UP —
   `rv_rising ≥ fresh_rv_rising_floor (0.10) ∧ |mom_recent| ≥ fresh_mom_floor (0.20)` — **after ≥1 prior
   session BELOW** the fresh leg (a fresh, debounced crossing; a continuation that never dipped below
   does not re-trigger).
2. **window-close (clock STOP):** the first session of **sustained** not-cheap = **2 consecutive**
   not-cheap sessions (a 1-session IV blip does NOT close it). Window length = sessions from onset to the
   first of those 2.
3. **`never_cheap` — a DISTINCT state.** If the gate is **not cheap at the break-onset session** → state
   `never_cheap` (IV already popped — the *modal* narrated-breaker outcome); otherwise the break is
   `cheap_window_days = N`. **Under inclusive cheap-day counting the onset itself is ≥1 enterable day, so
   `cheap_window_days = 0` is UNREACHABLE — `never_cheap` (0 enterable days) IS the 0-state.** Two states:
   `never_cheap` / `cheap_window_days = N≥1` (the original "=0" wording dropped — implementation reconcile
   2026-06-27; the distinct-state intent, "never catchable" vs "caught cheap", preserved).
4. **`marker_age_at_break` — the SELECTION dimension (recorded per break).** = the name's marker-age at
   the onset session (`as_of − markers_asof`, the migration-0016 stamp). The watch only sees breaks in
   names that are **active sentinels when they break**, and a break on a **fresh-marker** name is the case
   finding #1 does **not** bite (at_inflection already sees it). So `marker_age_at_break` partitions
   **benign** (fresh → seen in time) from **harmful** (stale → at_inflection blind) breaks. Without it the
   watch could record wide `cheap_window_days` on freshly-surfaced names and conclude "don't fire" while
   the harm case (break + stale markers + missed re-judge) goes **unmeasured** — the selection trap.
5. **§7.1 trigger — the JOINT condition (restated).** Fires (build the persist) IFF, across breaks where
   **`marker_age_at_break` was STALE** (≥ ~the staleness lag, so at_inflection was blind at the break), the
   `cheap_window_days` distribution (excluding `never_cheap`) sits **below** the lag (~16–23d). Breaks on
   **fresh-marker** names are benign-by-construction (recorded, NOT counted toward the harm — the persist
   wouldn't have helped them). `never_cheap` breaks reported **separately** (catchability-at-all, not the
   staleness race). **The persist's value = breaks that are BOTH catchable-cheap AND missed-due-to-staleness;
   the watch measures that intersection, not the cheap-window alone.**
6. **N-floor (pinned — no verdict off noise).** The trigger reads **`insufficient_N`** until **≥
   `n_qualify_floor` (default 5, configurable)** *qualifying* breaks (stale ∧ catchable) have been observed
   — never a fire/don't-fire off 1–2 events (the generator's N-floor discipline; close negatives on
   measurement, not argument). The panel shows the **qualifying-break count** beside any window stat.
   **The conjunctive filters (active sentinel ∧ caught-at-onset ∧ stale markers ∧ cheap) make qualifying
   breaks RARE** (plausibly 1–2/yr on a ~5–10-name cohort), so **`insufficient_N` is the EXPECTED
   long-term state — and a sustained one is itself the finding:** the harm is too infrequent to spend on,
   the persist stays gated, a clean negative — not a stall. Read it lightly; let it take the time it takes.
7. **Rate-based close (the symmetric partner to the N-floor; pinned BLIND).** The decision-relevant
   signal is the qualifying-break **RATE**, not the window distribution (N≥5 windows is *years*; the rate
   reads in ~one quarter). The persist's value = rate × value-per-catch, so a near-zero qualifying rate
   de-prioritizes finding #1 **on the rate alone** — no window distribution needed; the years-long N≥5
   path binds ONLY in the surprising high-rate world (itself the thesis-relevant signal that the persist
   matters). **Pinned:** if after **T = 90 days** the `qualifying_per_quarter` rate is **< 2** (the
   materiality floor), **close finding #1 as a RARE-HARM negative — de-prioritize the persist** (a dated
   clean negative, not an open loop). The N-floor guards against firing on noise; the rate-close guards
   against `insufficient_N` forever.
   **PRECONDITION — curation feeds the watch:** the rate is interpretable ONLY once the cohort holds
   **break-CAPABLE** (fresh-ish quiet, curation-fed) names — a watch over post-move run-out names sees
   zero breaks because they already moved, **NOT** because the harm is rare. Until the cohort is
   curation-widened, a zero rate is **uninterpretable** (no break-capable names), not a clean negative —
   **the T-clock starts when the cohort is break-capable**, not at first observation.

## §2.1.8 — the `degenerate_iv` + `unmeasurable` states (in force; amendment 2026-06-30)

Report-time reclassification over the **already-persisted** raw IV columns (`atm_iv`, `wing_iv`, `iv_rv`,
`otm_skew` — migration 0017). **No migration, no record-segmentation, no schema change** — the raw inputs
are unchanged; only the interpretation changes, applied uniformly across all history (segmentation here
would be *incorrect* — splitting a homogeneous dataset on a non-event). This is the instrument *under* the
read, not a lever gated *on* it → **holds at zero additional trades**. (The companion live-gate fail-close
on degenerate IV — which *changes what trades* — is the separate §2.4 stub, its own pre-registration, a
precondition landing before the funnel first produces a council include.)

**The finding.** The gate fails closed **only** on a *missing* IV. Two failure classes both launder into
`never_cheap` ("IV already popped before we could catch it") when the truth is "we couldn't read it":
(1) **present-but-degenerate IV** (e.g. CDE: `atm_iv ≈ 200%` → `iv_rv 3.7`, `skew −202vp`; the wing stayed
positive so no fail-close fired → a confident false `cheap=0`); (2) the **missing-input fail-close** (a
wing that passed eligibility but lacks an IV → `GateVerdict(False, None, …)` → `cheap=0, iv_rv=NULL`). The
break is **never hidden, only reclassified** — onset detection is marker-based (`rv_rising`/`mom_recent`,
independent of the gate IV), so a degenerate/missing session cannot suppress a break; `n_breaks` is
invariant, only the attribution is corrected.

**The `(cheap, iv_rv)` partition.** `(None, —)` = `no_structure`; **`(0, NULL)` = `unmeasurable`** (the
missing-input fail-close); `(0, present-and-sane)` = `never_cheap`; **`(0/1, present-and-degenerate)` =
`degenerate_iv`**; `(1, present-and-sane)` = `cheap_window`. `(1, NULL)` is impossible (a passing gate
always computed `iv_rv`). The two NEW states sit **out of BOTH `qualifying` and `never_cheap`** (parallel to
`no_structure`). (Doc-fix note: migration-0017's NULL is `no_structure` only — a fail-closed gate *with a
structure present* writes `0`, not NULL.)

**The verdict-corruption seam (the one that matters).** The gate's skew check is **one-sided** (it vetoes
only a wing *richer* than ATM). So the dangerous case is the **clean-ATM / garbage-wing** name: ATM ~50%,
rv ~45% → `iv_rv 1.11` (passes); a stale wing → large *negative* skew (passes the one-sided gate) → a
false **`cheap=1`** into `qualifying`, the verdict-bearing set. (CDE only escaped into `never_cheap` because
its *second* leg, the ~200% ATM, tripped `iv_rv`; a clean-ATM/garbage-wing name has no such backstop.)

**A. The disjunction (per-leg, None-safe; any → `degenerate_iv`):**

| Disjunct | Failure it guards | Note |
|---|---|---|
| `\|otm_skew\| > skew_abs_max` | a leg diverges hard (CDE-high −202; the garbage-low wing) | **absolute** → catches both tails; its NEGATIVE tail is on the clip axis |
| `iv_rv > iv_rv_sanity_max` | ATM ≫ trailing RV (both-legs-high; skew small) | must be **≫ 1.2**; the **only** clip-free disjunct |
| `atm_iv < iv_floor` **OR** `wing_iv < iv_floor` | **either leg** implausibly low (absolute) | **per-leg / disjunctive** — the single-low-WING seam, not "both low together" |
| `wing_iv < k · atm_iv` | wing implausibly low **relative** to ATM (the *moderate* seam) | scales with ATM; the load-bearing catch for clean-ATM / garbage-wing |

**⚠️ Three disjuncts share ONE clip axis — `skew_abs_max`, `iv_floor`, `k` are a single
cheap-wing-clip budget.** The edge *is* a cheap wing, so low-wing-IV-relative-to-ATM is the **signal**;
three disjuncts (including `|otm_skew|`'s NEGATIVE tail) fire on that same low-wing direction and can clip
genuine signal. They are not independent defense-in-depth — the effective clip is whichever is tightest.
Pin all three to fire **only** on near-zero/stale quotes (a wing at a few % annualized while ATM/RV run
tens of %), never on a real low-IV wing. Only `iv_rv` (high-side) is genuinely clip-free.

**B. The SCOPED invariance claim.** §2.1.8 reclassifies **bound-detectable** degeneracy out of
`qualifying`/`never_cheap`. It does **not** protect the verdict against *all* degenerate-low input: the
**moderate thin-wing band** (ATM 50%, wing 8–20% → skew −42…−30, above a generous ceiling, above a low
floor) is an acknowledged residual (the common case on the anti-quietness cohort, not just CDE's −202
extreme). The relative disjunct shrinks this band; it does not close it. "Protects the verdict against
degenerate-low" unqualified is an overclaim, explicitly retracted.

**The two consumption sites (both report-time; one shared `_classify(row, bounds)`, None-safe, never
raises).** Both consume the rows from the **`by_sym` query** at the top of `cheapness_report` (the four IV
columns added **there**, not a separate SELECT). **Site 1 — onset (`_detect_breaks`):** the onset session
is classified; an `unmeasurable`/`degenerate_iv` onset gets that state (excluded from both `qualifying` and
`never_cheap`); `_window_len` is not called for it. **Site 2 — mid-window (`_window_len`):** it reads
`cheap` directly, so an onset-only fix leaves `cheap_window_days` (the verdict-bearing quantity) corrupted
by mid-window degenerate sessions. It becomes a **three-input** machine; `degenerate_iv` and `unmeasurable`
collapse to one **`unreadable`** input class (`no_structure` stays the `not_cheap` column, as in the
original 2-state debounce):

| macro-state ↓ \ session → | `cheap` | `not_cheap` | `unreadable` (degenerate ∨ missing) |
|---|---|---|---|
| **IN_WINDOW** (`notcheap_run=0`) | `window++`; `degen_run:=0`; stay | `notcheap_run:=1`; `degen_run:=0`; → CLOSING | `degen_run++`; if `≥2` → **TRUNCATE**; else stay (window & run unchanged) |
| **CLOSING** (`notcheap_run=1`) | `window++`; `notcheap_run:=0`; `degen_run:=0`; → IN_WINDOW | `notcheap_run:=2`; → **CLOSED** (finalize) | `degen_run++`; if `≥2` → **TRUNCATE**; else stay CLOSING (run **transparent**) |

`degen_run` resets on any `cheap`/`not_cheap`. **An isolated `unreadable` blip is transparent** (neither
advances nor resets the close-run); **a sustained `unreadable` run (≥2, mirroring the §2.1.2 close
threshold) TRUNCATES** at the last clean cheap. `_window_len` returns a per-window **end-reason**
(`closed` / `truncated` / `open_at_end`).

**Right-censoring (windows that don't feed the verdict at face value).** A window **CLOSED** by 2 genuine
not-cheap sessions has an *exact* length. A window that ends `truncated` (lost visibility) or `open_at_end`
(still cheap at the last observation — the COMMON recent-break case) is **right-censored** (true length ≥
observed `V`). The verdict medians `cheap_window_days` and fires if median `< staleness_lag`, so a
censored-*short* window read at face value biases toward **FIRE** — worst on the target cohort (thin
under-narrated wings are where unreadable/recent breaks cluster). Rule:

- censored at **`V ≥ lag`** → true length ≥ V ≥ lag → a **definitive HOLD vote** (kept; informative).
- censored at **`V < lag`** → uninformative for median-vs-lag → **EXCLUDE from the decision set** (the
  verdict median *and* the N-floor), reported separately as **`censored_short`**.

This keeps `insufficient_N` longer when wings are flaky / breaks are fresh — the **honest** outcome (can't
measure the window ⇒ can't decide), not a regression. (The `qualifying_per_quarter` RATE still counts all
qualifying breaks — the harm *occurred* even where the window is censored-short.)

**Make the blindness visible.** The report adds `n_degenerate_iv`, `n_unmeasurable`, `n_censored_short`,
and a **reclassified-rows list** (`symbol / as_of / iv_rv / otm_skew / atm_iv / wing_iv / which-bound +
offending value` — load-bearing: a future false-positive must be **diagnosable**, not just countable). The
dashboard per-name panel surfaces the per-name **state** beside `iv_rv` so the row and the verdict agree.

**Pin-once / apply-once.** Bounds pinned **once** from physics + the live gate-pass distribution, applied
to history **once**, recorded **as-is**. A surprising reclassification is a **finding**, not a license to
re-tune; the *build* iterates against synthetic fixtures with known answers, never the live verdict.

**Bounds (pinned BLIND, in force) — `config.convexity_gate`:**

```
skew_abs_max_volpts  = 100    # vp a real far-OTM smile can sit from ATM; NEGATIVE tail is clip-axis
iv_rv_sanity_max     = 5.0    # ATM-IV ÷ trailing-RV multiple certainly degenerate (>> 1.2); clip-free
iv_floor_annualized  = 0.03   # per-leg annualized IV floor; clip-axis — fire only on near-zero
wing_atm_ratio_min_k = 0.15   # wing/atm ratio floor; clip-axis, the delicate one
```

## §3 — Two arms

- **Live arm (market-gated):** the cohort's *actual* cheap-window on a real break. **Expect a long quiet
  wait** — no break may come for months; that quiet is the expected state, not a stall. **Daily** cadence,
  **cost-capped** (≈ the dual-read sweep), over the **DYNAMIC active-sentinel cohort** (so newly-curated
  quiet-sector names are watched and break-chances rise) — not a snapshot.

- **Historical-proxy arm (available NOW, no break needed):** the cohort's own trailing-year up-legs — the
  **underlying move-speed** as a coarse upper-bound on the cheap-window timescale. **Methodology pinned:**
  over each cohort name's cached bars, report (a) trough→peak up-leg **duration** (trading days), (b) the
  fastest **20-day** return, (c) trough→**+25%** **early-leg duration** (the cheap-window proxy — how long
  the move takes to cover the OTM distance the structure sits at). See **§3.1** for the result.
  **Caveat (pinned, LOAD-BEARING):** this is *underlying* move-speed (moneyness), **NOT** the gate's IV/RV
  `cheap` — they coincide only if IV tracks RV, which it does **not** for an under-narrated breaker (IV lags
  RV → IV/RV *falls*/stays cheap through the early break; the window is then the **narration lag**). So the
  proxy systematically **understates** the cheap-window for the target cohort; it shifts a PRIOR at most and
  can never de-prioritize finding #1 on its own — only the live arm measures the IV/RV window.

### §3.1 — Historical-arm RESULT + pinned interpretation (run 2026-06-26 against the frozen §3 methodology)

`trough→+25%` (the cheap-window proxy): **CDE 4d · PAAS 15d · AG 17d · HL 21d · FRO 25d** — comparable to /
below the live staleness lag (16.7d median / 23.7d max). **It does NOT resolve finding #1, in either
direction:**
- **Pin 1 — name it for what it is.** An underlying-move-speed proxy on a **NARRATED** cohort (silver/
  freight rallies get press → their historical IV popped early → a short proxy window *because* narrated —
  anti-representative of the under-narrated *target*). A weak PRIOR, **not** the cheap-window; do not read
  4–25d as "fire" (it overstates the case as much as the discarded "slow-ramp ⇒ wide" overstated "park").
- **Pin 2 — interpretation governs the live read.** The live IV/RV arm **decides** (days-gate-stays-`cheap`-
  after-break = the IV/RV window, measured directly). A live window **WIDER** than this proxy is the
  **EXPECTED under-narration signature** (IV lagging RV — the thesis *working*), not an anomaly to explain
  away. This pre-commits against anchoring on 4–25d when the live data lands.
- Finding #1's persist is therefore **genuinely undetermined**; the live arm is the **decider**, not a
  confirmer. **Re-run the proxy on the quiet-sector names once curated** (a less anti-representative
  cohort) — it remains a move-speed proxy, never the IV/RV window.

## §4 — Refinements adopted (operator, 2026-06-26)

Blind-pin first (§2); dynamic cohort (§3); run the historical arm first (§3) — it may settle finding #1's
fix priority *before* the live arm ever sees a break. Build the live arm only after sign-off of this shape.
