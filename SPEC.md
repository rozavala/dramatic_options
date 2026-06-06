# Dramatic Options — Architecture & Build Spec (v1)

> **For a fresh Claude Code session:** this is the north-star spec for a new, standalone
> equity-options trading system. Read it fully before starting. It is a sibling to an
> existing commodity-options system ("Real Options") but a **separate codebase** — reuse
> patterns, not a code dependency. This doc is the architecture and the *why*; the
> canonical, task-level build order lives in **IMPLEMENTATION_PLAN.md** (work it one phase
> per session, in plan mode). Paper-first. Live trades only after §13's gates are met.
>
> This is engineering scaffolding, not financial advice. The edge is a hypothesis to
> validate, not a given.

---

> **⚠ v2 PIVOT (2026-05-31) — read `PREREG_THEMATIC_CONVEXITY.md` + `IMPLEMENTATION_PLAN.md`
> first.** The strategy below (thesis-first narrative-vs-delivery *divergence*, validated on a
> backtest gate) was pre-registered, tested, and **graded negative** (divergence UNPROVEN;
> FSSD FAILED). The active strategy is now **forward, discretionary thematic cheap-convexity**:
> long-dated far-OTM defined-risk options on secular themes whose IV hasn't priced the move,
> sized small as a portfolio of convex bets. **The harness role flipped** from a pre-trade
> *validation gate* to an *execution + risk-control + forward-scoring* engine; the backtest
> machinery is parked in `shelf/`. Sections below are retained for architectural lineage
> (the council, risk model, execution funnel, reuse map all still apply) — but where this
> doc says "the edge is divergence" or "validate the edge in backtest before capital," read
> `PREREG_THEMATIC_CONVEXITY.md` instead. The non-negotiable guardrails (§13) are unchanged.
> **Build status** (canonical: `CLAUDE.md` / `IMPLEMENTATION_PLAN.md` / `DEPLOYMENT.md`) — as of
> 2026-06 the forward loop runs on systemd timers (L1 daily full cycle, L2 intraday monitor) and
> **T3 sentinel discovery** is operationalizing as a weekly **L0** scan (PR3; §C cold-cache timing
> verified, held unarmed until the live-loop §A check). The "discovery" section below describes the
> shelved *v1* narrative-clustering discovery — for T3's motion/structural funnel read
> `IMPLEMENTATION_PLAN.md` §T3 + `discovery.py`.

---

## 0. North star

A single, deliberately-aggressive, risk-managed, multi-agent system that trades **US
equity & ETF options** on a **thesis-first thematic** basis. It discovers themes and
mispricings from evidence, forms time-bounded theses via an adversarial AI council,
expresses them as **defined-risk option structures** on high-beta names, sizes them by
**fractional Kelly against a hard risk budget**, and manages them with fast, deterministic
exits. The brain is slow and deliberate; the reflexes are fast and dumb-by-design.

---

## 1. Converged design decisions (quick reference)

| Decision | Choice |
|---|---|
| System count | **One** system, standalone repo, isolated from Real Options |
| Broker | **Alpaca** (commission-free options, REST API, paper-first) |
| Asset scope | US equity & ETF options; defined-risk multi-leg (MLEG) |
| Shape | **Thesis-first thematic** (not bottom-up single-name screen) |
| Core edge | **Narrative-vs-delivery divergence** |
| Discovery | Two-layer, evidence-based; **deferred to a late phase** — start with a hand-seeded theme/basket list |
| Traceability | Causal driver graph (drivers → themes → companies); built late |
| Timing | Hybrid: slow brain (daily + event) / fast reflexes (intraday) |
| Lanes | L1 thesis engine · L2 position monitor · L3 opportunistic trigger (default = event-accelerated L1) |
| Risk posture | **Disciplined aggression**: high-beta universe, defined-risk, fractional Kelly, portfolio caps |
| Account size | $50–100k (above $25k → PDT not a constraint) |
| Sequencing | **Validate the edge in backtest/paper before scaling aggression or leverage** |

---

## 2. The edge (what the whole system serves)

**Narrative-vs-delivery divergence.** For each theme and name, measure two things
separately: how loud/confident the *story* is (breadth and rate-of-change of coverage,
analyst/retail intensity — from text) and what the *substance* is actually delivering
(guidance, contracts, shipments, margins — from filings). Trade the gap:

- substance quietly outrunning a quiet story → **long** (under-the-radar acceleration);
- story outrunning substance → **fade / short** (hype exceeding delivery).

This is causal and falsifiable, not vibes, and it is the system's mispricing detector.
It is **not arbitrage**: it is convergence risk (cheap can get cheaper), and the catalyst
that closes the gap runs on its own clock — so exits anchor to catalysts and falsifiers,
not to an assumption of speed.

**Mandate:** prove this signal predicts reversals/continuation on historical data before
any capital — let alone leverage — rides on it.

---

## 2a. Backtesting & validation

The system is split so it can be validated honestly:

- **The deterministic spine is backtestable** — divergence scoring, momentum/IV signals,
  structure selection, sizing, exits. This is the optimization surface: **walk-forward,
  out-of-sample, risk-adjusted** (never raw-profit maximization), on strictly
  **point-in-time** data (no restated fundamentals, no lookahead).
- **The LLM council is NOT backtested historically.** Training-data lookahead makes a
  historical "agent backtest" meaningless — the model already knows what happened next.
  Agents are validated **forward** on unseen, post-cutoff data via Brier + contribution
  scoring.
- **Surrogate distillation is deferred** (see §14) — overkill until there's a working
  backtest plus substantial forward council history to distill.

---

## 3. System shape & the three lanes

**L1 — Slow thesis engine (the brain).** Daily post-close scan + event-driven triggers.
Pipeline: discovery → divergence scoring → council debate → **thesis** (direction,
conviction, timeframe) + **playbook** (entry conditions, falsifiers, exit rules, and
pre-authorized intraday contingencies). All deliberation lives here. ≈ Real Options'
scheduled council cycles.

**L2 — Fast position monitor (the reflexes).** Tight intraday loop, deterministic, **no
LLM**. Watches open positions against the falsifiers / profit targets / stops L1 set, and
fires exits. Cheap, fast, robust to broker latency. ≈ Real Options' continuous
exit/drawdown monitoring. It does not think — the intelligence was front-loaded at entry.

**L3 — Opportunistic trigger (fast intake).** A material intraday event (8-K, sweep, gap)
on a *tracked* name fast-tracks L1 to an accelerated-but-still-vetted decision. This is
the **default (event-accelerated L1)** behavior. A genuine separate fast-alpha engine
(intraday flow/microstructure trading on its own logic) is **explicitly out of scope for
v1** — it is a different machine with real-time-data and risk requirements, to be
considered only as a later, separately-risk-budgeted subsystem.

**Principle:** open slow, close fast. Patient on entry (missing an entry is cheap),
reactive on exit (slow exits compound losses and bleed theta). Anything fast is
**pre-authorized, never improvised**.

---

## 4. Components / modules

- **`discovery`** — two-layer, evidence-based. Layer 1: cluster co-moving language across
  filings, transcripts, patents, regulatory dockets, job postings to surface emergent
  themes (pre-consensus). Layer 2: assign basket membership by *evidence of exposure*, not
  sector label, surfacing non-obvious names. (Generalizes Real Options' `TopicDiscoveryAgent`.)
- **`divergence`** — the core scorer (§2): story-intensity vs substance-delivery, per
  theme and name; outputs the signed divergence and a rationale.
- **`themes`** — theme/thesis store: each theme's thesis, basket, signals, lifecycle state.
- **`graph`** — causal driver graph (drivers → themes → companies, timestamped,
  evidence-weighted) for traceability and second-order discovery. **Built late** (Phase 6+).
- **`council/`** — Tier-2 specialists + Tier-3 debate (see §5).
- **`risk`** / **`sizing`** — fractional-Kelly sizing, risk budget, portfolio caps,
  drawdown breaker, compliance gate (§6).
- **`execution`** — Alpaca MLEG order construction/submission (defined-risk structures),
  adaptive limit walking, liquidity gate, missed-order persistence.
- **`monitor`** — the L2 fast loop (intraday exits, falsifier checks).
- **`observability`** — funnel diagnostics, debate forensics, abstention monitor, **cost
  ledger per stage** (first-class — the whole design is a cost argument). _BUILT 2026-06-05
  (§5b PR-A): `dashboard.py` + `dashboard_data.py` + `breach_audit.py` — a read-only Streamlit
  surface (`?mode=ro` / NO-FETCH / fail-soft) with a T4-readiness scoreboard spine._
- **`data/`** — adapters (§8).

---

## 5. The Council (runs on the shortlist only)

> **T2 minimal council (built 2026-06-01) — a deliberate consolidation, not a subset.** The full
> bench below (seven Tier-2 specialists + Tier-3) is the destination. T2 ships a minimal-but-real
> **three-role** council — **Proposer** (Inflection Analyst, argues FOR the candidate's direction)
> → **Adversary** (Devil's Advocate, **direction-relative** — argues AGAINST the proposed
> direction, the bull case on a bearish name) → **Master Strategist** (synthesis + conviction in
> `LOW/MODERATE/HIGH/EXTREME`) — over the operator's `themes.json` **candidate watchlist** (it
> judges, it does not discover; discovery is T3). Roles run across distinct providers via the
> heterogeneous router (`council/`); the quote-authenticity filter + early-exit-to-NEUTRAL apply;
> proposals are forward-scored only (Brier + contribution, guardrail §6). The Tier-2 specialist
> bench is an additive expansion behind the same router/seam. See `PREREG_THEMATIC_CONVEXITY` §2
> (the hard seam: the council proposes, the deterministic gates dispose) and `IMPLEMENTATION_PLAN` T2.

**Tier-2 specialists** (LLM, routed per role via the heterogeneous router):
- Fundamental / Filings (10-K/Q, 8-K, guidance; long context → Gemini)
- Catalyst / Event (earnings, FDA, M&A, product)
- Volatility / Options (IV term structure, skew, flow; code-tool-augmented for greeks)
- Technical (chart structure, momentum, levels)
- Macro / Sector (rates, dollar, sector tailwind/headwind, relative value)
- Sentiment (retail/social crowd psychology → Grok)
- Smart-Money / Insider (Form 4 clusters, 13F, 13D activists)

**Tier-3 decision & risk** (reuse Real Options designs, re-ground prompts):
- Permabull / Permabear adversarial debate — symmetric evidence, explicit `weakest_point`,
  randomized order/model, quote-authenticity + hallucination filtering.
- Master Strategist — synthesizes into a verdict; regime-aware; conviction dampener at extremes.
- Devil's Advocate — pre-mortem.
- AI Risk Agent — narrative VaR + stress scenarios.

Data-dependent agents follow the early-exit rule: return NEUTRAL/LOW if grounded data
lacks numeric content.

---

## 6. Risk & sizing (non-negotiable, explicit)

- **Defined-risk structures only by default** (verticals, condors, defined straddles/
  calendars). Naked long options behind a separate, explicit gate.
- **Per-trade max loss budget:** config (start ~1–2% of equity).
- **Fractional Kelly sizing** (≤ half-Kelly) against the estimated edge. **Leverage is an
  output of sizing, never a target.** Do not implement any "maximize leverage" path —
  overbetting a positive-edge game still leads to ruin.
- **Portfolio caps:** max concurrent positions; max per name; max per theme/sector; max
  aggregate premium-at-risk (gross). *(The per-theme/**cluster** cap landed 2026-06-03 — PREREG §5
  amendment, `clusters.py` + `convexity_book.cluster_fraction`: a deterministic operator-curated
  `symbol→cluster` correlation budget so a correlated basket can't pose as diversified.)*
- **Drawdown circuit breaker:** warn / halt / panic thresholds (config).
- **Daily-loss halt.** **Kill switch** (file or env) checked every cycle.
- **Broker treated as unreliable:** fail-closed on ambiguity, aggressive reconciliation,
  persist missed orders for manual review.

---

## 7. Strategy templates (signal → structure)

| Signal / regime | Structure |
|---|---|
| Bullish directional, moderate IV | Bull call (debit) spread |
| Bearish directional, moderate IV | Bear put (debit) spread; bear call (credit) spread if IV high |
| Range-bound, elevated IV | Iron condor / credit spreads |
| Pre-catalyst vol-expansion thesis | Long straddle/strangle or calendar (vol-aware) |
| Post-catalyst IV crush, directional | Debit spread (avoids vega bleed) |

Option selection for slow-lane theses: ~45–90 DTE entries; close or roll near 21 DTE to
avoid the gamma/theta endgame. Hard liquidity gate (OI + bid/ask spread) at selection and
execution — the aggressive small-caps often have untradable options.

---

## 8. Data sources

- **Alpaca** — market data (bulk bars/snapshots), options chains + greeks/IV/OI (shortlist
  only), news. Feed: `indicative` (free) for build/paper, `opra` (paid real-time) for live.
- **SEC EDGAR** — 8-K (material events), Form 4 (insider), 13D/G (activists), S-1/424B
  (dilution). Use SHA-256 diffing on 10-K/10-Q so only year-over-year changes are embedded.
- **Earnings calendar** — pre/post-earnings tagging.
- **Macro** — DXY, rates, VIX, credit, sector-ETF breadth.
- **Social** — Reddit/StockTwits/X sentiment level and velocity (provider TBD — see §14).

---

## 9. Tech stack & where it runs

- **Language/runtime:** Python 3.11+, `asyncio`.
- **Broker SDK:** `alpaca-py` (trading + data; MLEG options confirmed supported).
- **Vector store:** ChromaDB (TMS + discovery embeddings).
- **LLMs:** heterogeneous router across Gemini / OpenAI / Anthropic / xAI / Perplexity.
- **State/journal:** SQLite (file-based, simple; matches Real Options) — Postgres optional later.
- **Dashboard:** Streamlit.
- **Process model:** one long-running `asyncio` orchestrator under **systemd** that
  internally schedules the daily L1 cycle and runs the intraday L2 loop — mirrors Real
  Options' `orchestrator.py`. Event triggers (L3) interrupt the schedule.
- **Hosting:** a **dedicated small Digital Ocean droplet** (≈2–4 GB RAM) is recommended
  for blast-radius isolation from the live commodity book. Cheaper fallback: the **same
  droplet as a fully isolated service** (own system user, venv, `.env`, data dir,
  systemd unit). Either way, isolation from Real Options is mandatory.
- **CI/CD:** GitHub + Actions, push-to-deploy to the droplet (mirror Real Options;
  `main` → DEV, a `production` branch → PROD).
- **Secrets** in `.env` (never committed): Alpaca keys, LLM provider keys, EDGAR/news
  keys, Pushover.

---

## 10. Repo structure

The core is the importable **`dramatic_options/`** package; the Streamlit dashboard,
`scripts/`, `tests/`, and the runtime config files sit at the repo root. Run as a module
(`python -m dramatic_options.orchestrator`) or `pip install -e .`. Tests resolve the package
via the repo-root `conftest.py` without an install.

```
dramatic_options/                # the package (importable as `dramatic_options`)
  __init__.py
  orchestrator.py        # single-cycle loop: reconcile → monitor/exits → council → entries
  config_loader.py       # config.json + .env overrides; the live-trading gates
  clock.py               # injectable Clock (point-in-time everything)
  themes.py              # conviction theme watchlist (themes.json) store + lifecycle
  discovery.py           # evidence-based theme/basket discovery (L0)
  convexity_data.py      # option-chain / quote providers (Alpaca + synthetic)
  convexity_gate.py      # the edge: IV/RV + OTM-skew cheap-convexity gate (fail-closed)
  convexity_sizing.py    # flat-by-slots position sizing
  structure.py           # defined-risk structure selection
  broker.py              # Alpaca paper/real broker + client-order-id helpers
  paper_loop.py          # the per-cycle entry loop
  monitor.py             # mark positions + fire deterministic exits (L2)
  risk.py                # kill switch / kill-rule, caps
  sentinels.py           # event sentinels; sentinel_scoring.py forward-scores them
  universe.py            # eligibility floor
  options_tradability.py # OSI parse + spread/tradability checks
  notify.py              # Pushover paging (systemd OnFailure + in-app)
  state.py               # atomic SQLite state/journal
  council/               # T2 LLM council: router, agents, debate, proposal, scoring, wiring
  data/                  # alpaca_client, cache, news + reusable point-in-time adapters
  calibration/           # parametric Monte-Carlo convexity calibration (calibrate-not-prove)
config.json              # thresholds, risk budget, council/model config  (repo root)
themes.json              # conviction theme candidate watchlist            (repo root)
dashboard.py             # Streamlit dashboard (streamlit run dashboard.py)
scripts/                 # deploy, migrations, systemd unit templates, readiness check
tests/
shelf/                   # parked backtest-gate machinery (graded-negative edges; kept)
conftest.py · pyproject.toml · SPEC.md · CLAUDE.md · .env.example
```

---

## 11. Reuse from Real Options (patterns, re-implemented for Alpaca)

Debate engine + hallucination/quote-authenticity filtering · Master Strategist /
Devil's Advocate / AI Risk Agent · compliance fail-closed posture + conviction gate ·
full-revaluation HS VaR (add beta-weighted delta + correlation) · drawdown circuit
breaker · position sizer · TMS · semantic cache · heterogeneous router · Brier +
contribution scoring + DSPy · execution funnel / debate forensics / abstention monitor ·
reconciliation discipline (aggregate matching, idempotent phantom cleanup) · order-manager
safety (atomic combos, adaptive walking, missed-order persistence). Copy the design;
re-target the broker.

---

## 12. Build phases

`IMPLEMENTATION_PLAN.md` is the canonical, task-level build order — work it one phase per
session in plan mode. At a high level the phases progress (detail front-loaded on the
early ones):

- **Phase 0 — Scaffold & paper broker connection.** Repo, config, Alpaca paper client,
  SQLite state/journal, kill switch, `CLAUDE.md`, CI.
- **Phase 1 — Data + divergence signal (seeded universe) + backtest harness.** The
  **edge-validation gate**: hand-seed the theme/basket list, build the data adapters and
  the divergence scorer, and prove the signal on point-in-time history. No LLM discovery yet.
- **Phase 2 — Deterministic paper loop.** Structure selection + minimal risk gate + MLEG
  paper execution + thesis-level tracking + the L2 exit monitor. No council yet.
- **Phase 3 — The Council.** Tier-2 specialists + Tier-3 debate on the shortlist → thesis
  + playbook (with falsifiers); forward agent scoring.
- **Phase 4 — Full risk & portfolio.** Fractional-Kelly sizing, portfolio caps, VaR,
  drawdown breaker, compliance gate.
- **Phase 5 — Opportunistic lane (L3) + event triggers.** Event-accelerated L1,
  pre-authorized contingencies, periodic thesis re-check.
- **Phase 6 — Learning & observability.** TMS, scoring, journal post-mortems, DSPy,
  funnel/forensics, cost ledger, dashboard.
- **Phase 7 — Advanced discovery & traceability.** Two-layer LLM discovery (replaces the
  seed list) + causal driver graph.
- **Phase 8 — Harden & go-live.** Reconciliation, outage handling, go-live checklist,
  dedicated droplet.

Each phase is independently testable and ends green (tests pass + acceptance met) before
the next.

---

## 13. Non-negotiable guardrails

- **Fail-closed** everywhere; on any error in a trade cycle, the trade is blocked.
- **Paper-first**; live requires explicit, multi-gate opt-in + a validated edge.
- **Defined-risk by default**; naked exposure separately gated.
- **Kill switch** honored every cycle.
- **Edge validated before leverage**; no "maximize leverage" path exists in the code.
- **Every decision logged** (full forensic record) for traceability.

---

## 14. Open items to confirm

1. **L3 scope** — default is (b) event-accelerated L1. Confirm (a) stays out of v1.
2. **Risk numbers** — per-trade budget %, fractional-Kelly fraction, profit-target /
   stop / time-stop parameters.
3. **Universe seed** — starting theme list + basket mappings (e.g., the current eVTOL/
   space book) and the eligibility floor (liquidity, optionability).
4. **Social data provider** and **EDGAR access method** (full-text search API vs a library).
5. **Data feed** — `indicative` for build, switch to `opra` before live.
