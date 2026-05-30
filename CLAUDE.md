# CLAUDE.md — Dramatic Options

## What this is

Dramatic Options is an event-driven, multi-agent AI system that trades **US equity & ETF
options** on a **thesis-first thematic** basis. It is a standalone sibling to the "Real
Options" commodity-options system — same architectural lineage, but a **separate codebase
with no shared dependency**. It will eventually trade real money via **Alpaca**; treat
every change with that care.

**Status: paper-only. Live trading is gated and not yet enabled.**
**Current build phase: Phase 1 infrastructure COMPLETE; v1 edge UNPROVEN (deterministic approach set aside) — Phase 2 NOT started.** The point-in-time data layer (Alpaca + EDGAR + bulk insider + XBRL fundamentals), divergence signal, and walk-forward backtest harness are built, tested, and green. **The edge gate FAILED across four Bonferroni-penalized iterations** (substance: event-presence → signed insider net-buy → reported revenue YoY) on a properly-powered, multi-regime, momentum-neutral test (44–47 periods, 61 names, 2020–24): primary-horizon (h=21) rank-IC stayed ≈0, every Bonferroni CI spans 0. An early +0.075 on a narrow 30-period window did not survive added power/regimes — fragile. Verified the null is real (substance density 96–100%; real-data momentum positive control IC ≈ +0.10), not a measurement artifact. Per the pre-committed stopping rule the deterministic divergence approach is set aside (no k=5); per guardrail §5 **no live-shaped behavior is built on the unvalidated edge**; the lockbox was never opened. See the §"Phase 1 gate result" below. The fork now is: a *new* edge hypothesis on the (working) harness, OR forward-test divergence via the un-backtestable Phase-3 council, OR reconsider the greenfield system. ← update this line as phases complete.

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
