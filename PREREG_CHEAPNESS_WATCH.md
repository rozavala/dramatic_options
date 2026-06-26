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
4. **cheap-window (the deciding number) — counting methodology pinned:** the count of trading days the
   gate stays `cheap` from the break trigger (first-cross) until it **first** flips to not-cheap. Daily
   resolution; the gate's own `cheap` boolean; first-cross→first-flip (no post-hoc re-choice of window).
5. **§7.1 re-open trigger:** re-open finding #1 (build the persist) **IFF** the measured cheap-window
   `<` the staleness lag (~16–23d). Equality/wider ⇒ do not fire.

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
