# CLAUDE.md — Dramatic Options

## What this is

Dramatic Options is an event-driven, multi-agent AI system that trades **US equity & ETF
options** on a **thesis-first thematic** basis. It is a standalone sibling to the "Real
Options" commodity-options system — same architectural lineage, but a **separate codebase
with no shared dependency**. It will eventually trade real money via **Alpaca**; treat
every change with that care.

**Status: paper-only. Live trading is gated and not yet enabled.**
**Current build phase: Phase 0 complete (scaffold + Alpaca paper connection). Next: Phase 1 (data + divergence signal + backtest — the edge-validation gate).** ← update this line as phases complete.

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
