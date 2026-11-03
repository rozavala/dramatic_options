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
  **Amendment 2026-06-01 — delta-trigger + reprice rules added** (for the venture→reprice-capture
  exit reframe; see `PREREG_THEMATIC_CONVEXITY` §6a). New cells: `delta` (close when `|delta| ≥
  θ_delta` — the far-OTM convexity has *converted into delta*, i.e. the anticipated spot move
  played out) and `reprice` (delta **OR** the 10× profit-take backstop **OR** time-stop@21DTE,
  else expiry — the candidate new OTM rule). Swept over **`θ_delta ∈ {0.4, 0.5, 0.6}`**, reported
  as an exit head-to-head at the live cell (25% OTM, 270d) vs hold-the-tail and live-10×. The
  delta exit is calibratable because delta moves with *spot* at constant σ_entry; an IV/skew
  *re-rating* ("gate-rerate") exit is **NOT** calibratable here (the harness re-prices at constant
  σ_entry — no vol path) and is excluded. **Read with the GBM-no-jumps caveat (carried from §3):**
  GBM understates the right tail, which in a head-to-head flatters *early* exits — so the delta
  cells are an upper bound on how good early-exit looks; weight the Mode-B (real-jump) overlay for
  the tail-dependent comparison and do not let the harness silently endorse earlier exits.
  **FINDING (2026-06-01, 5000 paths, 25% OTM/270d/σe=1.0×/μ=10%/σ_real=50%): the delta exit is
  EV-inferior on the OTM sleeve and was NOT adopted.** hold-the-tail: mean M=1.22×, p99=14.4×,
  break-even p*=**19%**. delta@0.5: mean M=1.02×, p99 capped at **1.8×**, p*=**67%** — it forfeits
  the fat tail and needs a ~60–68% hit-rate to beat holding; hold dominates on *both* mean and p*,
  and the GBM bias favored the early exit yet it still lost. → **OTM exits stay §6a (hold-the-tail);
  the delta/reprice rules are retained as a calibration capability for the future ITM sleeve** (where
  high-delta/no-tail makes reprice the right pairing), not used in the live OTM path.
- **σ_entry multiple:** `{0.8, 1.0, 1.2, 1.5}` (§3).
- **Mode-A path params:** `μ ∈ {0%, 10%, 25%}` annual drift, `σ_real ∈ {30%, 50%, 80%}`
  (spanning the high-beta thematic names), N paths per cell (config, default 5000, seeded).

**Amendment 2026-11-03 — calibration v2: jumps, thesis state, salvage, rolls, verticals, 540 d
(written BLIND, committed before any v2 code or number exists).** Motivation:
`records/2026-11-03_literature_review.md` and the operator's "small losses, big wins" question. Every
cell below answers a *structure* question; none is an edge claim, and none changes a live parameter. A
cell that meets its rule earns only the right to **draft** a live amendment
(`records/2026-11-03_profit_program_DRAFTS.md`), which still needs the operator's word.

*Common settings (frozen here):* call, 25% OTM, 270 d, σ_entry = 1.0 × σ_real, σ_real = 50%, the live exit
(10× profit-take backstop OR time-stop at 21 DTE, else expiry), round-trip cost 5% of premium, seed 7,
5,000 paths per cell. Paths are run **paired** (same seed ⇒ the same price paths and the same falsifier
draws across the cells being compared).

1. **Path model axis: GBM vs Merton jumps.** Jumps: Poisson intensity λ = 2/yr, log-jump size N(0, 0.20),
   the diffusion σ reduced so total variance still equals σ_real², drift compensated so E[S_T] = S₀e^{μT}.
   The June finding was GBM-only and flagged that GBM flatters early exits. **Rule J:** re-run hold vs
   live-10× vs delta@0.5 at μ = 10% under jumps. If delta@0.5 beats hold on mean M under jumps, the June
   ranking is reopened (reported, no draft). Otherwise the ranking is confirmed. Note: BS-at-σ_real
   under-prices a fat-tailed wing, so jump cells show a higher mean M mechanically. Compare cells *within*
   a path model, never across.
2. **Thesis-state paths + falsifier salvage.** Each path draws `right ~ Bernoulli(p)`; drift is
   μ_right if right, μ_wrong = −10%/yr if wrong. A falsifier is read on day d_f and fires with
   probability `a` when wrong and `1 − a` when right (false alarm). **Salvage** = the live exit plus
   "sell at the mark on d_f if the falsifier fires". Grid: μ_right ∈ {40%, 80%}, d_f ∈ {90, 150} days,
   a ∈ {0.7, 0.9}, both path models. Reported per state: E[M | right], E[M | wrong], p99 | right, and the
   exact break-even `p* = (1 − E_w)/(E_r − E_w)` (the mean is linear in p). **Rule S:** salvage is a
   drafting candidate iff, at the conservative corner (a = 0.7, d_f = 90), for **both** μ_right and
   **both** path models: p*(salvage) < p*(hold) **and** E[M | right](salvage) ≥ 0.85 × hold's (false
   alarms may not cost winners more than 15%).
3. **House-money roll.** When the mark first reaches R × entry (R ∈ {3, 5}), close; bank 1.0 × entry
   premium as cash; spend the rest (net of cost) on a new call 25% OTM from the current spot, same expiry;
   that leg then runs the live exit (10× is measured on the *total*, banked + leg, against the original
   entry). One roll per position. **Rule R:** a drafting candidate iff, under **both** path models at
   μ = 10%: mean M ≥ 0.95 × live's **and** P(M ≥ 1) ≥ live's + 3 pp.
4. **Wide call vertical** (for names over the per-name cap only). Long 25% OTM, short K₂ ∈ {+75%, +100%}
   OTM; the short leg priced at σ_entry + s, s ∈ {0, +5 vol pts}. The live exit runs on the spread's value.
   Reported: premium ratio (spread / naked), mean M, p99, P(M ≥ 1). **Rule V:** a drafting candidate iff,
   under jumps at μ = 10% and s = 0, some K₂ gives premium ≤ 0.75 × naked **and** mean M ≥ 0.85 × naked's.
5. **540-day tenor.** The live cell at 365 d and 540 d, both path models, μ ∈ {0%, 10%, 25%}. Reported:
   mean M, p*, premium ratio (540 / 365) and premium per day. **Rule T:** a drafting candidate iff,
   for **every** μ and both path models: mean M(540) ≥ mean M(365) **and** p*(540) ≤ p*(365).

Outputs go to `data/calibration/<ts>/` and the finding is appended below this amendment with the date,
the commit and the rule verdicts. Same caveats as §3: constant σ_entry through the life (no vol path), so
an IV re-rating is not modelled. In particular a falsified thesis is sold at its *diffusion* mark; a real
mark after bad news is probably lower, so salvage cells are an **upper bound** on salvage value.

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
