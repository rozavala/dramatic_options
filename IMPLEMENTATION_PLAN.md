# Dramatic Options — Implementation Plan (for Claude Code)

> **Companion to `SPEC.md`.** SPEC.md is the architecture and the *why*; this is the
> execution sequence and the *do-this-next*. Read SPEC.md first, then work this plan one
> phase at a time. Paper-first throughout; live only behind §0 gates after the edge
> validates.

---

## How to execute this plan (Claude Code protocol)

- **One phase per session.** Start each with plan mode: *"Read SPEC.md and
  IMPLEMENTATION_PLAN.md. We're doing Phase N. Show me the plan before executing."*
  Review the diff, run the tests, commit, then `/clear` before the next phase.
- **Each phase ends green:** all tests pass **and** the acceptance criteria are met before
  advancing. Don't start Phase N+1 with Phase N red.
- **Phase 1 is the edge-validation gate.** If the divergence signal doesn't show
  predictive value on point-in-time history, iterate the *signal*, not the plumbing.
  Do not build toward live-money behavior on an unvalidated edge.
- **Detail is front-loaded.** Phases 0–2 are specified at task level. Phases 3–8 are
  outlines — expand each into tasks in plan mode when you reach it. Don't over-build
  far-future phases now; the design will sharpen as the early phases land.
- **Keep `CLAUDE.md` lean** (created in Phase 0): project overview, stack, build/test
  commands, the §0 guardrails, and a pointer to SPEC.md + this plan. Detailed plan lives
  here, not in CLAUDE.md.

---

## 0. Global conventions & guardrails (Definition of Done)

- **Paper-first.** `PAPER=true`, `DRY_RUN=true` by default. Live requires three gates
  (`PAPER=false` + `LIVE_TRADING_ENABLED=true` + explicit `--live`).
- **Fail-closed.** Any error in a trade cycle blocks the trade.
- **Defined-risk by default.** Verticals/condors/defined structures; naked exposure behind
  a separate explicit gate. No "maximize leverage" path exists in the code.
- **Kill switch** (`KILL` file or env) checked every cycle.
- **Config over code.** Tunables in `config.json`; secrets in `.env` (never committed).
- **Every phase ships:** unit tests, a runnable entry point, and updated docs.
- **From Phase 2 on, log every decision** (full forensic record) for traceability.
- Python 3.11+, `asyncio`, type hints, small focused modules.

---

## Phase 0 — Scaffold & paper broker connection

**Goal:** a runnable skeleton that connects to Alpaca paper and respects the safety rails.

- **0.1** Repo init per SPEC §10. `pyproject.toml` / `requirements.txt`
  (`alpaca-py>=0.40`, `pandas`, `python-dotenv`, `chromadb` later). `.gitignore`
  (`data/`, `.env`, `*.db`, `logs/`). `.env.example`.
- **0.2** `config.py` / `config_loader.py`: `.env` overrides; the safety gates
  (`PAPER`, `LIVE_TRADING_ENABLED`, `DRY_RUN`, `DATA_FEED`); risk-budget placeholders.
- **0.3** `data/alpaca_client.py`: paper `TradingClient`; account/clock/positions; stock
  bars; option chain (`OptionChainRequest` with `feed`, `type`, strike/expiry filters,
  `OptionsFeed.INDICATIVE`); news; MLEG submit helper (`OrderClass.MLEG`, two
  `OptionLegRequest` legs). *Note: verify signatures against installed alpaca-py.*
- **0.4** `state.py`: SQLite store with atomic writes; tables `runs`, `signals`,
  `theses`, `orders`, `positions`.
- **0.5** `risk.py` (skeleton): kill switch, daily-loss halt, market-hours guard.
- **0.6** `CLAUDE.md` (lean) per the protocol above.
- **0.7** CI: GitHub Actions running lint + `pytest`; `tests/` skeleton.
- **0.8** `orchestrator.py` (skeleton): connects to Alpaca paper, logs account equity,
  honors the kill switch, exits cleanly.

**Acceptance:** `python orchestrator.py` connects to Alpaca paper, prints equity; `touch
KILL` halts the next run; CI is green.

---

## Phase 1 — Data + divergence signal (seeded universe) + backtest harness  **[EDGE GATE]**

**Goal:** compute the core edge on a hand-seeded universe and prove it predicts something
on point-in-time history. No LLM discovery yet — discovery comes in Phase 7.

- **1.1** Seed config: themes + baskets (e.g. `evtol → JOBY, ACHR`; `space → RKLB, LUNR,
  ASTS`; extend as desired) and the eligibility floor (price, ADV, option OI/spread).
- **1.2** Data adapters under `data/`, **all point-in-time / as-of aware** (timestamp
  everything; never use restated/revised data):
  - `market.py` — bars/snapshots; momentum & relative-strength inputs.
  - `filings.py` — EDGAR 8-K, Form 4, 13D/G, S-1; full-text; SHA-256 diff on 10-K/10-Q so
    only year-over-year changes are processed.
  - `news.py` — Alpaca news headlines with timestamps.
  - `earnings.py` — earnings calendar.
  - `macro.py` — DXY/rates/VIX/sector ETFs (optional in P1).
- **1.3** `substance.py` — extract delivery signals from filings/earnings (guidance,
  contracts, revenue/margin deltas) into a numeric *delivery* series per name.
- **1.4** `narrative.py` — text-intensity signals (coverage breadth, rate-of-change of
  mentions, sentiment intensity) into a numeric *story* series per name. Deterministic/NLP
  and cheap — **not** the full council.
- **1.5** `divergence.py` — combine story vs delivery into a signed divergence score per
  name/theme, with rationale fields. This is the core edge.
- **1.6** `backtest/` — replay point-in-time data, compute the divergence signal
  historically, and evaluate predictive value (does divergence predict forward returns?).
  **Walk-forward, out-of-sample, risk-adjusted metrics** (hit-rate, Sharpe, max drawdown)
  — never raw-profit maximization. Strict no-lookahead.
- **1.7** Watchlist output: ranked theme/basket list with divergence scores, persisted to
  the journal.

**Acceptance:** produces a ranked watchlist with divergence scores on the seed universe;
the backtest scores the signal on point-in-time history and reports risk-adjusted
predictive metrics. **Review these results before Phase 2** — this is the gate.

---

## Phase 2 — Deterministic paper loop (structure → minimal risk → execute → track)

**Goal:** a full end-to-end loop on paper, no LLM yet. Signal in, defined-risk paper trade
out, positions tracked and exited by rules.

- **2.1** `options_selector.py` — pull the chain for shortlist names; pick a defined-risk
  structure per signal (verticals first), ~45–90 DTE; liquidity gate (OI + bid/ask);
  compute net debit, max loss/gain, reward:risk.
- **2.2** Minimal risk gate in `risk.py` — per-trade max-loss budget, basic
  concurrent/per-name caps, kill switch, daily-loss halt. (Full model in Phase 4.)
- **2.3** Minimal sizer in `sizing.py` — `contracts = floor(budget / max_loss)`.
  (Fractional Kelly in Phase 4.)
- **2.4** `execution.py` — build + submit MLEG paper order; `DRY_RUN` logs instead of
  sending; persist any missed orders for review.
- **2.5** Thesis/position store — group legs into a thesis; record entry rationale and exit
  rules (profit target, stop, time-stop, falsifier placeholders).
- **2.6** `monitor.py` (Lane 2) — intraday loop checking open positions against
  targets/stops/time-stops; fires paper exits. Deterministic, **no LLM**.
- **2.7** Wire `orchestrator.py`: daily scan → shortlist → select → risk gate → size →
  execute(paper) → journal; run the monitor loop intraday.

**Acceptance:** end-to-end on paper — the signal produces defined-risk paper spreads,
positions are tracked at thesis level, and the monitor fires exits on the rules.
Everything logged.

---

## Phase 3 — The Council (LLM judgment)  *(outline — expand in plan mode)*

**Goal:** insert the deliberative LLM layer between the signal and structure selection.

- Heterogeneous router (multi-provider + fallbacks).
- Tier-2 specialists (config-driven personas, routed per role): fundamental/filings,
  catalyst, vol/options, technical, macro/sector, sentiment, smart-money. Early-exit to
  NEUTRAL/LOW on non-numeric grounding.
- Tier-3 debate: Permabull/bear (symmetric evidence, `weakest_point`, randomized
  order/model), hallucination + quote-authenticity filtering, Master Strategist verdict,
  Devil's Advocate, AI Risk agent.
- Output: **thesis** (direction, conviction, timeframe) + **playbook** (entry, falsifiers,
  exits, pre-authorized contingencies). Council runs on the **shortlist only**.
- Forward agent scoring: Brier + contribution scoring on **forward** outcomes.

**Acceptance:** council vets the shortlist and emits theses with explicit falsifiers;
agent decisions logged and forward-scored.
**Do not** attempt to backtest the council historically — lookahead contamination makes it
meaningless. Surrogate distillation is deferred (see §Deferred).

---

## Phase 4 — Full risk & portfolio  *(outline)*

- Fractional-Kelly sizing (≤ half-Kelly); leverage as an *output* of sizing.
- Portfolio caps: per-theme/sector, gross premium-at-risk.
- VaR (full-revaluation HS, beta-weighted delta, correlation).
- Drawdown circuit breaker (warn/halt/panic).
- Compliance gate (conviction gate, defined-risk enforcement, fail-closed).
- Replaces the Phase-2 minimal risk/sizer.

**Acceptance:** every order is risk-checked and Kelly-sized; caps enforced; breaker halts
on thresholds.

---

## Phase 5 — Opportunistic lane (L3) + event triggers  *(outline)*

- Sentinels for event detection (8-K / Form 4 firehose, unusual options flow, gaps).
- Event → fast-track Lane 1 (accelerated but still vetted) — the (b) reading.
- Pre-authorized contingency execution for held theses ("if event X, do Y up to size Z").
- Periodic / event-triggered thesis re-check during tracking (light council subset).

**Acceptance:** a simulated event fast-tracks a thesis; a held-name event triggers its
pre-authorized contingency; a thesis re-check can flip hold → exit.

---

## Phase 6 — Learning & observability  *(outline)*

- TMS (ChromaDB) for institutional memory + reflexion.
- Trade-journal LLM post-mortems → TMS.
- DSPy prompt optimization (offline, on forward-scored data).
- Funnel diagnostics + debate forensics + abstention monitor.
- **Cost ledger per stage** (first-class — the design is a cost argument).
- Streamlit dashboard: watchlist, theses, positions, portfolio greeks/VaR, P&L, agent
  scorecards, cost.

**Acceptance:** agent scores and cost-per-stage are visible; dashboard live; post-mortems
feeding TMS.

---

## Phase 7 — Advanced discovery & traceability  *(outline — "make it yours")*

- Two-layer evidence-based LLM discovery replacing the seed list: themes from language
  clusters across filings/transcripts/patents; basket membership by *exposure evidence*,
  surfacing non-obvious names.
- Causal driver graph (drivers → themes → companies, timestamped, evidence-weighted) for
  traceability and second-order discovery.

**Acceptance:** the system surfaces emergent themes and non-obvious basket members, and
positions trace through the driver graph.

---

## Phase 8 — Harden & go-live  *(outline)*

- Full Alpaca reconciliation (aggregate matching, idempotent phantom cleanup).
- Outage handling (retries/backoff, missed-order persistence).
- Readiness/pre-flight check script + go-live checklist + the multi-gate opt-in.
- Split to a dedicated droplet for isolation.

**Acceptance:** full reconciliation; live only after paper validates across **dozens** of
trades and the gates are met; start at the smallest viable risk budget.

---

## Deferred / explicitly NOT in scope (yet)

- **Surrogate models** for backtesting the council — overkill now; revisit only if/when
  there's a working backtest plus substantial forward council history to distill.
- Generative simulacra; temporal-GraphRAG-as-retrieval; a separate fast intraday
  flow-alpha engine (the (a) reading of Lane 3).

---

## First move

Point Claude Code at this repo with `SPEC.md` and this file present, and say:
*"Read SPEC.md and IMPLEMENTATION_PLAN.md. Do Phase 0 in plan mode — show me the plan
before executing."*
