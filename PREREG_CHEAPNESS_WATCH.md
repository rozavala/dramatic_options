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
  the move takes to cover the OTM distance the structure sits at). A move unfolding over **months** (long
  duration, no sharp sub-leg, early-leg ≫ 23d) ⇒ a **wide** cheap-window ⇒ §7.1 trigger likely **does not
  fire** ⇒ finding #1's persist is likely **low-value**.
  **Caveat (pinned):** this is *underlying* move-speed, **not** IV reprice-speed — IV can pop ahead of the
  underlying, narrowing the true cheap-window. So the historical arm shifts the **prior** hard; it can
  **provisionally de-prioritize** finding #1, but only the live arm **confirms** — it never closes it.

## §4 — Refinements adopted (operator, 2026-06-26)

Blind-pin first (§2); dynamic cohort (§3); run the historical arm first (§3) — it may settle finding #1's
fix priority *before* the live arm ever sees a break. Build the live arm only after sign-off of this shape.
