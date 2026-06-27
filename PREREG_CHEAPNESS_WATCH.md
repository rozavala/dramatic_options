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
3. **`never_cheap` — a DISTINCT state, never merged with `cheap_window_days = 0`.** If the gate is **not
   cheap at the break-onset session** and does not turn cheap before close → state `never_cheap` (IV
   already popped — the *modal* outcome for a narrated breaker). `cheap_window_days = 0` means the opposite
   ("cheap at onset, flipped immediately"). For the §7.1 trigger these are **opposite** findings
   ("never catchable" vs "caught cheap, briefly") — the schema records three states: `never_cheap` /
   `cheap_window_days = 0` / `cheap_window_days = N≥1`.
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
