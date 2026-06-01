# Dramatic Options — Implementation Plan
## v2: Thematic Cheap-Convexity Inflection Trading

> **Companion to `SPEC.md` and `PREREG_THEMATIC_CONVEXITY.md`.** This supersedes the
> backtest-gated plan (divergence / FSSD), preserved at
> `shelf/IMPLEMENTATION_PLAN_backtest_gated.md`. Those edges were pre-registered, tested,
> and graded negative — this is a deliberate pivot to a **forward, discretionary** strategy,
> not a patch. Work one phase per session, in plan mode; each phase ends green.
>
> **Status: T0 · T1 · T1.5 · calibration harness COMPLETE · T2 (the council) IN PROGRESS.**
> (Sentinels T3 not started.) T1.5 added the L2 monitor (mark-to-market + deterministic
> profit-take/time-stop/expiry exits) and the real DRY_RUN-gated Alpaca paper-submit path; the
> calibration harness (`PREREG_CONVEXITY_CALIBRATION.md`) graded the exit structure (→ 4×→10×
> profit-take). T2 adds `council/` — the three-role LLM judgment layer that proposes themes.

---

## 0. What changed, and why

The prior plan demanded a *pre-validated, backtested* edge before deploying capital. Two
such edges (narrative-vs-delivery divergence; forced-supply secondary drift) graded
negative — and the analysis showed *why*: clean, backtestable, uncrowded edges in liquid
equity options barely exist for a small player. The durable edges are judgment-based, and
judgment edges cannot be backtested (training-data lookahead — guardrail §6).

- **From** "prove an edge on the harness, then trade it" **to** "deploy a conviction thesis
  forward, small and bounded, and let live results + risk control do the work."
- The thesis: **long-dated (6–12mo) far-OTM convex options on secular themes at an
  inflection point** — long the un-priced tailwinds, bearish the un-priced rollovers.
- **The harness's role flips:** no longer a pre-trade *validation gate*; now an
  *execution + risk-control + forward-scoring* engine.
- A forward-only strategy needs only **current** option data (which we have) → the "no
  historical options data" wall that blocked backtesting is irrelevant here.

## 1. The strategy (frozen — see PREREG_THEMATIC_CONVEXITY §1)

1. Identify a secular theme at **inflection**.
2. Express it with **long-dated, far-OTM, defined-risk** options.
3. **The gate — the edge:** trade only when implied vol is **not** already pricing the theme
   (convexity is *cheap* — "copper-not-rockets").
4. Run a **portfolio of small convex bets** (venture-style payoff).
5. Discipline lives in **sizing and risk control**, not validation.

## 2. The hard seam — deterministic gates vs. council judgment

The council **proposes**; deterministic, code-enforced rules **dispose**.
**Deterministic (hard):** the IV/cheap-convexity gate, eligibility, sizing / caps / book
budget, the kill rule. **Judgment (council, forward-scored, never sole authority):** which
themes are at inflection, structural vs. fad, the cleanest name, narrative ahead-of vs.
behind fundamentals. The council can be wrong; it cannot buy expensive convexity, breach a
cap, or defeat the kill rule. (PREREG §2.)

## 3. Reuse map (as built)

**Reuse (plumbing, kept at repo root):** `clock.py`, `state.py`, `config_loader.py` +
`config.json`, `orchestrator.py`, `risk.py`, `universe.py`, `options_tradability.py`
(→ eligibility), `data/alpaca_client.py` (chain + IV/greeks/bid-ask), `data/cache.py`
(point-in-time cache, also used to accrue an IV baseline going forward). The wider
point-in-time data adapters (`data/market,news,filings,insider,fundamentals,edgar_index,
finra_si,prospectus,shares_out`) stay at `data/` as the reusable PIT data layer.

**Shelve (parked, not deleted — `shelf/`):** the backtest harness (`backtest/`),
divergence signal (`divergence,narrative,substance,watchlist`), FSSD modules
(`friction,fssd_stage1` + runners), their tests, and the `divergence`/`fssd` config blocks.
A real asset for any future deterministic idea; does not gate this strategy. See
`shelf/README.md`.

## 4. Risk frame — FIRST-CLASS, pre-registered (PREREG §5)

Frozen in `config.json:convexity_book` / `kill_rule` (operator decisions, 2026-05-31):
- **Convexity book = 10%** of account (total premium-at-risk; the only money that can be
  lost — long options are inherently defined-risk).
- **Per-name cap ≤ 1%** of account; per-theme = per-name for T1.
- **Max concurrent positions = 15.**
- **Sizing = flat-by-slots, capped — NOT Kelly** (a far-OTM lotto Kelly-sizes to ~0).
- **Kill rule:** halt new entries at **20% book drawdown OR 9 months** zero payoff; plus the
  always-on `KILL` switch.
- **Survivorship log:** every evaluated bet recorded, winners and zeros.

## 5. Phased build

**T0 — Repurpose & freeze ✅ COMPLETE.**
Stripped to reusable plumbing; shelved the backtest machinery; wrote
`PREREG_THEMATIC_CONVEXITY.md` (risk frame + IV gate, frozen *before* signal code); installed
this plan; updated `SPEC.md` / `CLAUDE.md`. No alpha logic.

**T1 — Minimal paper loop ✅ COMPLETE (+ T1.5).**
Smallest thing that can actually trade on paper:
hand-seeded theme+name → pull current chain + trailing realized vol → eligibility gate →
IV/cheap-convexity gate → propose a defined-risk long-dated structure → size per §4 → log a
paper position with a structured rationale + survivorship-log every evaluation →
forward-track P&L. Seeded from `themes.json`. **T1.5** added the L2 monitor (mark-to-market +
deterministic exits) and the real DRY_RUN-gated Alpaca paper-submit + reconciliation path.

**T2 — Council does the theme work �doing.** A minimal-but-real **three-role** council
(Proposer → direction-relative Adversary → Master Strategist) over the `themes.json` **candidate
watchlist** — it judges (inflection, structural-vs-fad, cleanest name, bull/bear), it does NOT
discover (that's T3). Roles run across distinct providers via a heterogeneous router (`council/`)
with a first-class cost ledger; SDKs are lazy-imported and `--demo`/tests use a deterministic
FakeRouter. The deterministic gates still dispose — **conviction is recorded + forward-scored
(Brier + contribution) ONLY; it never sizes a position and never overrides a veto** (the hard
seam). Kill checks precede any LLM spend; over-budget/failure fail closed to zero entries.

**T3 — Sentinel inflection discovery.** Always-on scan for pre-consensus tailwinds and
early rollovers — finds the *next* copper before it's narrated.

**T4 — Graduate to tiny real money.** On a pre-committed rule (N paper trades logged, payoff
distribution sane, risk frame held with no breaches) → tiny real capital under the identical
risk frame, behind the existing three live gates.

**T5 — Calibrate & scale.** Refine forward scoring, calibrate sizing to the observed payoff
shape, build a theme library, broaden the universe; consider graduating the IV gate from the
RV proxy to a true IV-rank once enough chain snapshots have accrued (PREREG §4b).

## 6. Forward measurement — calibration, not a pass-gate (PREREG §7)

Per bet: theme, inflection thesis, IV-gate verdict, structure, size, rationale, outcome,
P&L. Metrics: hit rate, payoff distribution, premium-bled-vs-paid; Brier + council
contribution arrive with T2. **6–12mo holds mean *years* to significance.** Forward data
informs calibration, sizing, and the kill decision — it does **not** prove an edge. A good
run is not validation; a bad run is not disproof until the kill rule trips.

## 7. Standing guardrails

- Paper-first; real money only via the T4 rule + the three live gates (`PAPER=false` AND
  `LIVE_TRADING_ENABLED=true` AND `--live`).
- Fail-closed; kill switch always live; defined-risk default; log every decision.
- The IV gate is a hard veto — a beloved theme with rich convexity is still a pass.
- The operator builds tooling; a human authorizes any capital. Not investment advice; the
  forward results decide.
