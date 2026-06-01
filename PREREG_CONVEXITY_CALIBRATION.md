# PREREG_CONVEXITY_CALIBRATION.md — Far-OTM Convexity Payoff-Mechanics Calibration

> **Pre-registration, written BEFORE any harness code.** This document fixes *what the
> calibration measures, on what data, and — critically — what it is NOT allowed to claim*.
> It is the disciplined companion to `PREREG_THEMATIC_CONVEXITY.md`: that doc froze the
> live strategy; this one frames a **calibration tool** for tuning its structure parameters
> (moneyness, tenor, exit rules) and informing **sizing**. Frozen 2026-05-31.
>
> **This is NOT a strategy backtest and produces NO edge claim.** See §1 (the three walls).

---

## 1. The three walls — why "backtest the strategy" is not what this is

The thematic cheap-convexity strategy has three parts; they are not equally testable, and
conflating them is exactly the false-positive this project killed twice (divergence, FSSD):

| Part | Testable on history? | Why / why not |
|---|---|---|
| **Theme-pick at inflection** (the alpha) | **No** | Judgment. Replaying "buy copper calls in 2021" *because we know it rose* is survivorship + lookahead — forbidden by guardrail §6 and the validation-methodology memory. |
| **The IV / cheap-convexity gate** | **No (today)** | Needs historical options IV. We have none (forward-only chains; the paid-vendor wall). Cannot replay the gate's as-of decisions. |
| **The option payoff *mechanics*** | **Yes** | Given an entry and a price path, a far-OTM long-dated option's value is Black-Scholes + arithmetic. This is the **only** part this harness touches. |

**What this harness computes:** the *payoff transfer function* of the structure — given a
realized underlying move, what multiple does the far-OTM defined-risk option return (net of
premium, after the §6a exits)? That is a deterministic property of Black-Scholes and the
path; it does **not** depend on whether a theme was well-chosen. It answers: *how do
moneyness / tenor / exit rules shape the venture payoff, and what hit-rate × payoff makes
the book EV-positive* — i.e., it informs **sizing and structure**, not edge.

**Forbidden outputs (HARKing tripwires):** no "this strategy returned X%"; no Sharpe/CAGR of
a theme-picked book; no selecting entry names/dates by their outcome; no tuning a parameter
to maximize a historical return number. A good payoff shape here is **not** evidence the
strategy makes money — only that *if* the operator's judgment has edge, this structure
expresses it efficiently.

## 2. Two modes (primary parametric; historical is a thin caveated overlay)

**The data wall (live-smoked 2026-05-31):** the free Alpaca **IEX** feed returns only
**~1,465 daily bars back to 2020-07-27** (~5.8 years). For 6–12-month holds that is ≤ ~6–10
non-overlapping holds per name — still far too thin to characterize a payoff *distribution*
(and it is a single late-cycle regime). So:

- **Mode A — PARAMETRIC Monte-Carlo (PRIMARY).** Simulate underlying paths under a **stated,
  swept** annualized drift `μ` and realized vol `σ_real` (geometric Brownian motion, fixed
  seed → reproducible). This is pure mechanics: no historical data, no lookahead, no
  survivorship, unlimited independent samples, entries 100% parametric. It is the honest way
  to map the payoff transfer function and the EV-vs-hit-rate surface.
- **Mode B — HISTORICAL reality-check (OVERLAY, heavily caveated).** A **mechanical** entry
  schedule (every calendar month-start, a fixed pre-listed name set, one entry per name per
  date — NO outcome selection) over the available 2022-06→2025-12 window. Entries are
  **overlapping** → samples are NOT independent and the window is **one regime**; reported as
  an illustrative overlay only, never a distribution to trust or to tune against. Its purpose
  is a sanity check that the parametric model isn't wildly off real far-OTM behavior.

## 3. Pricing assumptions (frozen, and SWEPT where we're blind)

- **Model:** Black-Scholes, European, **no dividends**, risk-free `r` from config
  (default 4%). Far-OTM long-dated calls/puts; defined-risk (max loss = premium).
- **Entry premium:** `BS(spot, strike, T, r, σ_entry)`. **We do not know historical IV**, so
  `σ_entry` is a **swept assumption** expressed as a multiple of `σ_real`:
  `σ_entry ∈ {0.8, 1.0, 1.2, 1.5} × σ_real`. The IV/RV-ratio of the live gate (≤1.2) maps
  directly onto this axis — so the sweep also shows *how much the entry-IV assumption moves
  the payoff*, the very uncertainty the missing-IV wall creates. **Reported as a sensitivity,
  never hidden behind a single number.**
- **Mid-life re-pricing (for non-expiry exits):** profit-take / time-stop close by
  re-pricing with BS at the same `σ_entry` held constant (a stated simplification — a vol
  path is out of scope; flagged in the report). **Expiry** needs no vol: payoff = intrinsic.
- **Costs:** an explicit per-contract round-trip cost stub (bid/ask + fees) in config
  (default modeled as a % of entry premium), applied to every close. Reported with and
  without, so the convexity isn't flattered by ignoring frictions.

## 4. The swept grid (frozen axes)

- **Moneyness** (OTM): `{15%, 25%, 40%}` (`target_moneyness` is 25% live).
- **Tenor:** `{180, 270, 365}` days (live window 180–365).
- **Exit rule:** `{hold-to-expiry, time-stop@21DTE, profit-take@4×}` and the live combined
  rule (profit-take 4× OR time-stop 21DTE) — so the §6a live exits are one cell of the grid.
- **σ_entry multiple:** `{0.8, 1.0, 1.2, 1.5}` (§3).
- **Mode-A path params:** `μ ∈ {0%, 10%, 25%}` annual drift, `σ_real ∈ {30%, 50%, 80%}`
  (spanning the high-beta thematic names), N paths per cell (config, default 5000, seeded).

## 5. Reported metrics (calibration, not a gate)

Per grid cell, over its sample of option-return multiples (multiple = exit value / entry
premium, so −100% = total loss of premium, the floor):

- **Payoff distribution:** mean, median, the venture quantiles (p50/p75/p90/p95/p99), and
  P(total loss) — the "most expire worthless" rate.
- **Premium-bled-vs-paid:** total premium lost / total premium deployed.
- **Convexity ratio:** mean upside multiple in the right tail vs the bounded −1 downside —
  the "small bounded loss, large unbounded gain" shape, quantified.
- **Payoff transfer curve:** underlying-return bucket → mean/median option multiple
  (the pure mechanics — what a +X% move in the name turns into).
- **EV vs assumed hit-rate:** since theme-pick edge is unknowable, treat hit-rate `p` (P the
  thesis direction is right by ≥ some move) as a **free swept parameter** and report the
  break-even `p*` per cell — directly: *how often must your judgment be right for this
  structure to be EV-positive.* This is the sizing-relevant output.

**Hold honestly (carried from PREREG_THEMATIC_CONVEXITY §7):** none of this proves an edge.
It tunes *structure* and *sizing* conditional on a judgment edge that only forward results
can confirm. A good calibration is a reason to prefer one structure over another, not to
deploy capital.

## 6. Scope & build

- New package `calibration/` (parallels the shelved `backtest/`; the *active* harness is the
  paper loop, so calibration is a separate, clearly-labeled analysis tool — not in the trade
  path). Modules: `pricing.py` (BS + GBM path sim, pure), `engine.py` (the sweep), `metrics.py`
  (the §5 stats), `run.py` (CLI → JSON + text report under `data/calibration/`).
- Reuses `data/market.py` bars (the PIT layer at root) for Mode B; **offline by default**
  (Mode A needs no network; Mode B reads the warm bars cache).
- Unit-tested offline: BS sanity (put-call parity, monotonicity, known values), GBM
  reproducibility (seed), exit logic on deterministic paths, metric correctness on a tiny
  hand-checkable sample. **Not run in CI** for the network Mode-B path; Mode A + all unit
  tests are offline and CI-safe.
- **No change to the live trade path, the gate, or the risk frame.** This doc governs only
  the calibration tool. Any later use of its output to *change* a frozen live parameter is a
  documented edit to `PREREG_THEMATIC_CONVEXITY.md`, dated, with the calibration cited.

---

*Frozen 2026-05-31, before calibration code. — Dramatic Options*
