# CLAUDE.md — Dramatic Options

## What this is

Dramatic Options is an event-driven, multi-agent AI system that trades **US equity & ETF
options** on a **thesis-first thematic** basis. It is a standalone sibling to the "Real
Options" commodity-options system — same architectural lineage, but a **separate codebase
with no shared dependency**. It will eventually trade real money via **Alpaca**; treat
every change with that care.

**Status: paper-only. Live trading is gated and not yet enabled.**
**Current build phase: v2 thematic cheap-convexity (forward/discretionary) — T0 · T1 · T1.5 · calibration · T2 (the LLM council) · T2.5 (run-it-forward) COMPLETE; T3 sentinel discovery IN PROGRESS — PR1 (deterministic core) + PR2 (LLM framer + origin-aware grounding + cost/kill gates + the slot reservation) landed & green; PR3-core (weekly L0 systemd/deploy + §C cold-cache timing) BUILT & green and held UNARMED until §A, PR3b (the brain-off null shadow book) BUILT & green; the pre-T4 **per-theme/cluster exposure cap** BUILT & green (PREREG §5 amendment, branch `pre-t4-cluster-cap`); then T4 graduation.** **T3** adds the DISCOVERY layer upstream of the council: a weekly scan that PROPOSES new candidates into the set the council judges (the hard seam holds — discovery proposes, council judges, deterministic gates dispose; both judgment layers forward-scored, never backtested §6). The prescreen is a MOTION/STRUCTURAL **funnel** (a disjunctive ABSOLUTE-floor gate — `|momentum|≥floor` OR `rv_slope≥floor` OR a structural filing — within-basket z only ranks the survivors; NO cheapness/alpha claim — cheapness stays the IV gate's job, and prescreen rank is a funnel never a tradeable signal). **PR1 (landed, offline):** `discovery.py` (prescreen) + `sentinels.py` (lineage identity/TTL, ranked union into the council, persist) + `sentinel_scoring.py` (forward-scoring: traded→outcome+Brier+realized-multiple; never-traded + a random CONTROL cohort → label-only reference forward-return with a survivorship/terminal-event guard, compared on the TAIL not the mean) + migration 0007 (`sentinel_candidates`) + `orchestrator.py --discover` (FakeRouter, kill-before-spend) + the ranked union into L1; `config.discovery` + curated `config.universe.themes` scan baskets (incl. the `ai_compute` second-order worked example). **PR2 (landed):** the bounded LLM framer (a skeptic that adjudicates real-inflection/artifact/mean-reversion, model-decorrelated, fail-closed-to-zero) + **origin-aware grounding** (sentinel candidates ground the framer AND the council on their MARKERS, not news — else a pre-news discovery is NEUTRAL-dropped) + the provenance chain (sentinel→proposal→position; traded sentinels resolve at close with outcome+Brier+realized-multiple, never-traded via the reference sweep) + the `sentinel_max_slots` reservation (`veto-sentinel-slots` when discovery's slice is full) + hard-seam guard tests. **PR3-core (BUILT & green):** weekly L0 systemd timer + deploy wiring + docs; `TimeoutStartSec=900` DERIVED from the §C cold-cache run (exit-0 in 11s, $0.0019 over 8 gemini-flash-lite framer calls — the first live LLM round-trip, which §A could not exercise). Held UNARMED until §A re-verifies the live loop (merging auto-arms L0 = the go-live act + first real council spend on the live book). **PR3b (BUILT & green):** the **brain-off null shadow book** (`shadow_book.py` + migration 0008 `shadow_positions` + the fail-soft L1/L2 wiring) — a parallel book that runs the deterministic pipeline (IV gate→structure→sizing→exits) over the SAME candidate union the council sees but brain-OFF (every gate-passer, no council include/exclude, no framer drop), **simulated fills only — NEVER the broker** (its own table + a never-broker merge-blocker test), origin-tagged (hand-seed vs sentinel), scored on the per-position realized-multiple TAIL; the gap to the real book = the LLM layer's marginal contribution (fail-soft: a shadow bug never halts the real cycle). **Pre-T4:** the per-theme/cluster exposure cap **BUILT & green 2026-06-03** (PREREG §5 amendment, operator-authorized via the R2/R3/R4 plan red-team — `cluster_fraction=0.02` over a deterministic by-driver `symbol→cluster` map `ai_capex_power`=VRT/PWR/GEV/ETN/CCJ/CEG/NEE + `space_defense`=RKLB/KTOS, NEVER an LLM label; **entry-premium** basis counting committed-incl-**pending** so a `DRY_RUN=false` same-cycle leak can't over-admit a tight cluster; direction-agnostic/no-netting; applies identically to the brain-off shadow book; per-run `frame_version` stamp + per-decision breach-audit substrate; migration 0009; `clusters.py`; 326 tests green, branch `pre-t4-cluster-cap`) — it fixes the false diversification the very first §C scan exposed (7 correlated AI-capex names across two baskets). **REMAINING pre-T4:** a basket-quality report + the **fixed-basket null** — **PR1 pre-registration FROZEN 2026-06-03** (`PREREG_FIXED_BASKET_NULL.md`, written BLIND via the R2/R3 red-team): the no-IV-gate book is the **headline gate test** (`shadow−3A` = FSSD null≈signal on the edge), `real−3B` the **bundled** beat-the-basket read; **p95**-tail + **bootstrap CIs** + **with/without-top-k** on the event-enriched gate-rejected cohort; shares = descriptive secondary; **live basket → `real−3B` clean**; the never-broker books mirror `shadow_positions` field-for-field. **PR2a (book 3A) BUILT & green 2026-06-03** (`fixed_basket.py` + migration 0010 `fixed_basket_positions` mirroring `shadow_positions`; gate-OFF over the SAME union, cap-ON, fail-soft + never-broker merge-blocker test, `--demo`: shadow books 1 vs no-gate-3A books 2 — the gate rejected NVDA, 3A kept it; 335 tests, branch `fixed-basket-pr2a`). **PR2b (book 3B) BUILT & green 2026-06-03** (`run_fixed_basket_3b_cycle` + `equal_weight_contracts`; gate-OFF + EQUAL-WEIGHT over the WHOLE basket with the MOTION-derived direction `discovery.direction_of`, NO book/cluster truncation; weekly L0 in `--discover`; `--discover --demo` books all 16; 340 tests, branch `fixed-basket-pr2b`) — `real−3B` the bundled apparatus-vs-basket read is now live. **BUILD next:** PR2c (the shares descriptive null) + a fast-follow trailing-return-correlation **diagnostic** (report-not-gate; before next Sunday L0 scan). T2.5 operationalized the forward loop: PR1 added two-sided close-side execution (broker-aware monitor, real DRY_RUN-gated SELL_TO_CLOSE, idempotent client_order_id, migration 0006); PR2 added the systemd run model — `Type=oneshot` `orchestrator.py` on timers (L1 daily 15:45 ET pre-close = full cycle; L2 ~30min intraday `--monitor`, no council/LLM), a fail-closed `is_market_open()` gate + a `FORWARD_ENABLED` flag checked BEFORE the council build (no entries/LLM-spend on a closed market or inert env; the monitor runs mark-only when closed so a post-close/catch-up run never submits into a closed book), a `deploy.sh` that renders+installs units on both envs but arms timers only where `FORWARD_ENABLED=true` (PROD=real-money stays installed-but-inert until T4; rollback re-syncs units), a verify gate asserting the live-checkout `.env`, and `notify.py` Pushover paging (systemd `OnFailure` for non-zero exits + in-app pages for the soft exit-0 trips: kill-rule / fail-closed council / cost-cap). DEV=paper runs it with `DRY_RUN=false`; see `DEPLOYMENT.md`. T2 added `council/` — a minimal-but-real three-role council (Proposer → direction-relative Adversary → Master Strategist) over the `themes.json` candidate watchlist, on a heterogeneous LLM router with a first-class cost ledger. It only PROPOSES; the deterministic gates still DISPOSE (the hard seam, PREREG §2). Conviction is recorded + forward-scored (Brier + contribution, guardrail §6) ONLY — it never sizes a position and never overrides a veto; kill checks precede any LLM spend; over-budget/failure fails closed to zero entries. `--demo`/tests use a deterministic FakeRouter (no keys/SDKs). **Thesis framing clarified 2026-06-01 (reprice-capture):** the long tenor is *runway* for an anticipated trend-change, not a holding commitment. For the **far-OTM sleeve this stays hold-the-tail** — a calibration head-to-head graded a delta-trigger "exit-on-playout" rule **EV-inferior** (caps the ~14× tail at ~1.8×, break-even hit-rate 19%→~67%; the GBM-no-jumps bias favored it yet it lost), so OTM exits are unchanged. The reprice-capture behavior is a distinct edge **deferred to a future, separately-pre-registered ITM sleeve** (its own financing/extrinsic gate + reprice/invalidation exits). The delta/reprice calibration rules are retained as a tool for that sleeve, not used in the live OTM path. Two deterministic backtest-gated edges were graded negative (divergence v1 UNPROVEN, FSSD v2 FAILED at Stage-1 k=1); rather than a 3rd backtest edge, the system pivoted to a **forward, discretionary** strategy and the **harness role flipped from validation-gate to execution + risk-control + forward-scoring**. The backtest machinery is parked in `shelf/` (not deleted). See **`PREREG_THEMATIC_CONVEXITY.md`** (the frozen risk frame + IV/cheap-convexity gate) and the v2 **`IMPLEMENTATION_PLAN.md`**.
**v2 strategy (active):** long-dated (6–12mo) far-OTM **defined-risk** options on secular themes whose **IV hasn't priced the move yet** ("copper-not-rockets"), run as a portfolio of small convex bets (most expire worthless, a few pay many-fold). The edge IS a hard deterministic gate: trade only when convexity is *cheap*. With no historical IV (forward-only chains), "cheap" is measured vs the underlying's **trailing realized vol** (`IV_atm/RV ≤ 1.2`) + the **live skew** (`OTM_wing − ATM ≤ 10` vol pts), fail-closed; we also start persisting chain snapshots to accrue our own IV baseline. Risk frame (frozen, operator-set): book = **10%** of acct (total premium-at-risk), per-name ≤ **1%**, **per-cluster ≤ 2%** (correlation budget — 2026-06-03 amendment), ≤ **15** open, sizing flat-by-slots (NOT Kelly), kill at **20% book DD or 9mo** dry. Validation discipline shifts to **calibrate-not-prove** (6–12mo holds can't reach significance fast). The two graded-negative edges below are retained as **lineage/history**.
**FSSD (Forced-Supply Secondary Drift, 424B5 × short-sale friction) — see `PREREG_FSSD.md`:** the §8 eligible-N audit PASSED (friction∩optionable∩tradable corner 28≥24 months) but the Stage-1 gross-CAR gate FAILED at k=1 (explore 2019–22, h=10td): top-friction-decile mean CAR −1.91%, Bonferroni CI [−4.64%, +0.67%] spans 0, and — decisively — the **null control (random in-name dates) −1.78% ≈ the signal −1.91%**, so conditioning on the 424B5 event adds ~nothing over the friction characteristic (the drift belongs to high-SI/low-float small-caps generally, not the supply event). STOPPED per the pre-registered rule (no k=2, no Stage-2 options-data spend). The §8b corner also showed a ~52% median put bid/ask spread (borrow-in-the-puts), which would have sunk Stage-2 net-of-borrow regardless. Harness extended & reusable: `data/edgar_index` · `data/finra_si` · `data/shares_out` · `data/prospectus` · `friction` · `options_tradability` · `fssd_stage1` (survivorship-clean event-study CAR with trailing-decile, period-bootstrap, null+positive controls). **Two graded negatives confirm the harness is the durable asset; the fork is unchanged — a *new* edge hypothesis, OR forward-test divergence via the Phase-3 council, OR reconsider greenfield.**
**Divergence (v1) history:** The point-in-time data layer (Alpaca + EDGAR + bulk insider + XBRL fundamentals), divergence signal, and walk-forward backtest harness are built, tested, and green. **The edge gate FAILED across four Bonferroni-penalized iterations** (substance: event-presence → signed insider net-buy → reported revenue YoY) on a properly-powered, multi-regime, momentum-neutral test (44–47 periods, 61 names, 2020–24): primary-horizon (h=21) rank-IC stayed ≈0, every Bonferroni CI spans 0. An early +0.075 on a narrow 30-period window did not survive added power/regimes — fragile. Verified the null is real (substance density 96–100%; real-data momentum positive control IC ≈ +0.10), not a measurement artifact. Per the pre-committed stopping rule the deterministic divergence approach is set aside (no k=5); per guardrail §5 **no live-shaped behavior is built on the unvalidated edge**; the lockbox was never opened. See the §"Phase 1 gate result" below. The fork now is: a *new* edge hypothesis on the (working) harness, OR forward-test divergence via the un-backtestable Phase-3 council, OR reconsider the greenfield system. ← update this line as phases complete.

### Phase 1 gate result (2026-05-30) — v1 divergence edge UNPROVEN

Pre-registered, banded, multiple-testing-aware gate (SPEC §2a). Primary horizon h=21td.

| Run | periods | h=21 rank-IC | Bonferroni CI | verdict |
|---|---|---|---|---|
| 34 names, 2022–24 (k=1) | 30 | +0.075 | spans 0 | fragile (didn't replicate) |
| 61 names, 2020–24 (k=2) | 47 | +0.023 | spans 0 | FAIL |
| + insider net-buy substance (k=3) | 47 | −0.048 | spans 0 | FAIL |
| + revenue-YoY substance (k=4) | 44 | −0.057 | spans 0 | FAIL |

Four iterations (k=1→4), each Bonferroni-penalized; substance evolved event-presence → signed
insider net-buy → reported revenue YoY (the strongest deterministic "delivery" proxy). The
h=21 IC never escaped 0; the only positive (+0.075) was the narrow-window artifact that didn't
replicate. Per the pre-committed stopping rule the **deterministic divergence approach is set
aside** (no k=5); the lockbox was never opened. Diagnostics holding across all four runs:
substance density 96–100% (not thin), real-data positive control alive (momentum→fwd IC
≈ +0.10), divergence decorrelated from momentum — so the null is real, not a plumbing artifact.
The harness (point-in-time, no-lookahead, pre-registration, period-bootstrap, momentum-
neutralization, null + real-data positive controls) is the durable deliverable — reusable for
a *new* edge hypothesis, or for forward-testing divergence via the Phase-3 council.

## Read these first

- **`SPEC.md`** — the architecture and the *why* (system shape, the three lanes, the agent
  tiers, the edge, the risk model). Read before any non-trivial work.
- **`IMPLEMENTATION_PLAN.md`** — the canonical, task-level build order. Work it **one
  phase per session, in plan mode**. A phase ends green (tests pass + acceptance criteria
  met) before the next begins.

## Non-negotiable guardrails

These hold in every session; a violation should block a merge.

1. **Paper-first.** Live requires all three: `PAPER=false` **and**
   `LIVE_TRADING_ENABLED=true` **and** explicit `--live`. Default is paper + `DRY_RUN`.
2. **Fail-closed.** Any error in a trade cycle blocks the trade.
3. **Defined-risk by default.** Verticals / condors / defined structures only; naked
   exposure sits behind a separate explicit gate. **There is no "maximize leverage" path
   in the code** — sizing is fractional Kelly against a risk budget; leverage is an
   *output* of sizing, never a target.
4. **Kill switch** (`KILL` file or env) is checked every cycle.
5. **Edge before capital.** The Phase-1 divergence signal must validate on point-in-time
   history before any live-shaped behavior is built. Backtests are **walk-forward,
   out-of-sample, risk-adjusted** — never raw-profit maximization, never lookahead.
6. **Never backtest the LLM council historically** — training-data lookahead makes it
   meaningless. Agents are validated **forward** (Brier + contribution scoring).
7. **Log every decision** (forensic record) from Phase 2 on.

## Stack

Python 3.11+, `asyncio` · Alpaca (`alpaca-py`) · ChromaDB · multi-LLM router
(Gemini / OpenAI / Anthropic / xAI / Perplexity) · SQLite (state/journal) ·
Streamlit (dashboard) · systemd on a Digital Ocean droplet · GitHub Actions CI.

## Commands

(Stubs until Phase 0 lands them.)

```bash
pip install -r requirements.txt   # install
python orchestrator.py            # run (paper, default)
pytest                            # tests
streamlit run dashboard.py        # dashboard
touch KILL                        # halt everything
```

## Conventions

- **Config over code** — tunables in `config.json`; secrets in `.env` (never committed).
- **Point-in-time data** — backtest/replay use as-of data only (no restated fundamentals,
  no future leakage).
- **Every phase ships** unit tests and a runnable entry point.
- Small, focused modules; type hints throughout.
- **Confidence vocabulary is strict:** `LOW` / `MODERATE` / `HIGH` / `EXTREME`.
- **Isolation from Real Options is mandatory** — separate runtime, data dir, and keys.

## Reuse from Real Options (patterns, re-implemented — not imported)

Debate engine + hallucination/quote-authenticity filtering · compliance fail-closed +
conviction gate · full-revaluation HS VaR · drawdown circuit breaker · position sizer ·
TMS · semantic cache · heterogeneous router · Brier + contribution scoring + DSPy ·
execution funnel / forensics · reconciliation discipline · order-manager safety (atomic
combos, adaptive limit walking, missed-order persistence).
