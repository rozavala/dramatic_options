# CLAUDE.md — Dramatic Options

## What this is

Dramatic Options is an event-driven, multi-agent AI system that trades **US equity & ETF
options** on a **thesis-first thematic** basis. It is a standalone sibling to the "Real
Options" commodity-options system — same architectural lineage, but a **separate codebase
with no shared dependency**. It will eventually trade real money via **Alpaca**; treat
every change with that care.

**Status: paper-only. Live trading is gated and not yet enabled.**
**Current state:** what is in force right now (rulings, open clocks, staged PRs) is in `records/STANDING_STATE.md`, refreshed weekly — read it before acting on a strategy question. Build-phase detail is in `IMPLEMENTATION_PLAN.md`; the June 2026 build log that used to sit here is in `records/2026-06-19_claude_md_status_line_archive.md`.
**v2 strategy (active):** long-dated (6–12mo) far-OTM **defined-risk** options on secular themes whose **IV hasn't priced the move yet** ("copper-not-rockets"), run as a portfolio of small convex bets (most expire worthless, a few pay many-fold). The edge IS a hard deterministic gate: trade only when convexity is *cheap*. With no historical IV (forward-only chains), "cheap" is measured vs the underlying's **trailing realized vol** (`IV_atm/RV ≤ 1.2`) + the **live skew** (`OTM_wing − ATM ≤ 10` vol pts), fail-closed; we also start persisting chain snapshots to accrue our own IV baseline. Risk frame (frozen, operator-set): book = **10%** of acct (total premium-at-risk), per-name ≤ **1%**, **per-cluster ≤ 2%** (correlation budget — 2026-06-03 amendment), ≤ **15** open, sizing flat-by-slots (NOT Kelly), kill at **20% book DD or 9mo** dry. Validation discipline shifts to **calibrate-not-prove** (6–12mo holds can't reach significance fast). The two graded-negative edges below are retained as **lineage/history**.
**Graded-negative edges (do not resurrect):** divergence v1 (UNPROVEN) and FSSD v2 (null≈signal). Results, and the later dead hypotheses, are in `records/edge_graveyard.md`.

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
3. **Defined-risk only.** Positions are long premium (max loss = premium paid); verticals /
   condors are the other defined structures, and naked exposure sits behind a separate
   explicit gate. **There is no "maximize leverage" path in the code** — sizing is
   flat-by-slots against the risk budget (not Kelly; `PREREG_THEMATIC_CONVEXITY.md`);
   leverage is an *output* of sizing, never a target.
4. **Kill switch** (`KILL` file or env) is checked every cycle.
5. **Edge before capital.** The Phase-1 divergence signal must validate on point-in-time
   history before any live-shaped behavior is built. Backtests are **walk-forward,
   out-of-sample, risk-adjusted** — never raw-profit maximization, never lookahead.
6. **Never backtest the LLM council historically** — training-data lookahead makes it
   meaningless. Agents are validated **forward** (Brier + contribution scoring).
7. **Log every decision** (forensic record) from Phase 2 on.

## Stack

Python 3.11+, `asyncio` · Alpaca (`alpaca-py`) · multi-LLM router
(Gemini / OpenAI / Anthropic / xAI / Perplexity) · SQLite (state/journal) ·
FastAPI + React web dashboard (`dashboard_web/`) · systemd timers on the DEV and PROD
hosts (`DEPLOYMENT.md`) · GitHub Actions CI.

## Commands

```bash
pip install -r requirements.txt   # install
python orchestrator.py            # run (paper, default)
pytest                            # tests
# dashboard: dramatic-options-web.service (scripts/dashboard_web_run.sh)
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
