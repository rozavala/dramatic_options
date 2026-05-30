# dramatic_options

Thesis-first thematic **equity & ETF options** trading system (Alpaca, paper-first).
A standalone sibling to the commodity-options "Real Options" system. **Paper-only; live
trading is multi-gated and not yet enabled.**

Read `SPEC.md` (architecture + the *why*) and `IMPLEMENTATION_PLAN.md` (build order) first.
`CLAUDE.md` is the lean working context.

## Setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env            # fill in Alpaca paper keys + EDGAR_USER_AGENT
python scripts/run_migrations.py   # SQLite schema (currently v2)
pytest                          # offline test suite (no network)
```

## Run

```bash
python orchestrator.py          # Phase 0: connect to Alpaca paper, print equity
python watchlist.py             # Phase 1: ranked divergence watchlist (seed universe), persisted to signals
touch KILL                      # halt everything (checked every cycle)
```

## The edge (Phase 1) and its gate

The core edge is **narrative-vs-delivery divergence**: measure how loud the *story* is
(news coverage intensity/acceleration/breadth) vs what the company is actually *delivering*
(EDGAR filing events — contracts, results, insider/activist activity, dilution), and trade
the gap. `divergence = z(narrative) − z(substance)`; the directional view is `s = −divergence`
(positive divergence = hype exceeding delivery → fade).

Phase 1 is the **edge-validation gate** — prove the signal predicts forward returns on
point-in-time history before any capital rides on it. The backtest is walk-forward,
out-of-sample, momentum/beta-neutral, and judged against **pre-registered** criteria.

```bash
# 1. ALWAYS the data-availability pre-flight first (coverage only — no IC):
python -m backtest.run --audit --start 2022-01-01 --end 2024-06-30
#    Review the eligible-N-over-time curve, then freeze the explore/lockbox boundary.

# 2. Explore-set gate run (scored against the bands below):
python -m backtest.run --start 2022-01-01 --end 2024-06-30 --k 1

# 3. ONLY if explore clears — look at the lockbox exactly once:
python -m backtest.run --unlock --k 1

# Reproduce offline from the warmed cache (deterministic, network-free):
python -m backtest.run --offline --start 2022-01-01 --end 2024-06-30
```

### Pre-registered pass/fail (frozen before the run; bands, not a line)

| Band | Pooled rank-IC (h=21td) | Meaning |
|---|---|---|
| **FAIL** | < 0.03 | no edge |
| **YELLOW** | 0.03 – ~0.06 | real-but-marginal — Phase 2 only at minimal risk |
| **GREEN** | ≳ 0.06 | edge |

All of these must also hold (and confirm once on the lockbox): block-bootstrap CI over the
**period** IC series excludes 0 at **Bonferroni α=0.05/k** (k = signal-iteration rounds);
sign-consistent in ≥60% of folds; positive/monotonic quintile spread; momentum + growth +
broad-beta-neutral residual IC retains ≥50%; and **substance non-zero density ≥20%** (else
divergence ≈ narrative and the result is *inconclusive for the thesis*, not a pass).

Caveats baked into the report: spot-edge ≠ options-edge (median move vs option costs); the
universe is hindsight-selected; substance v1 is tangible-event *presence*, not *good*
delivery; thin cross-sections (<8 names) are excluded. A modest IC near 0.03 on thin, late
data is the plausible realistic outcome — a disciplined modest-but-real edge is the thesis.

## Layout

Flat modules at repo root (`config_loader`, `clock`, `state`, `risk`, `universe`,
`narrative`, `substance`, `divergence`, `watchlist`, `orchestrator`) + `data/` adapters
(`alpaca_client`, `cache`, `market`, `news`, `filings`) + `backtest/` (`engine`, `metrics`,
`run`) + `scripts/` + `tests/`. Tunables in `config.json`; secrets in `.env` (never
committed). Point-in-time everything — all data flows through an injectable `Clock` and an
as-of cache; the backtest is strictly no-lookahead.
```
