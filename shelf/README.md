# shelf/ — parked backtest-gate machinery (NOT deleted)

This directory holds the **backtest-gated edge machinery** from the prior strategy
generation. It is **parked, not abandoned**: two pre-registered deterministic edges were
graded negative (see `CLAUDE.md` and `PREREG_FSSD.md`), so the system pivoted to a
**forward, discretionary thematic cheap-convexity** strategy
(`PREREG_THEMATIC_CONVEXITY.md`, `IMPLEMENTATION_PLAN.md`).

The harness here is the **durable asset** — a survivorship-clean, point-in-time,
pre-registration-disciplined event-study/IC toolkit. Keep it for any *future deterministic
edge hypothesis*. It does **not** gate the current forward strategy.

## What's here

| Path | What it is | Grade |
|---|---|---|
| `backtest/` | walk-forward engine + metrics (rank-IC, block-bootstrap CI, Bonferroni) + `run` CLI | harness (reusable) |
| `divergence.py`, `narrative.py`, `substance.py`, `watchlist.py` | v1 narrative-vs-delivery divergence signal | UNPROVEN (k=4) |
| `friction.py`, `fssd_stage1.py` | v2 forced-supply secondary drift (424B5 × short-sale friction) | FAILED (Stage-1 k=1, null≈signal) |
| `scripts/fssd_stage1_run.py`, `scripts/fssd_audit.py` | FSSD Stage-1 runner + §8 corner audit | harness (reusable) |
| `tests/` | the parked modules' unit tests (`test_divergence`, `test_substance`, `test_watchlist`, `test_fssd_stage1`, `test_backtest`, `test_narrative`, `test_friction`) | — |
| `config.shelved.json` | the `divergence` / `fssd` config blocks lifted out of the active `config.json` | — |
| `IMPLEMENTATION_PLAN_backtest_gated.md` | the superseded backtest-gated build plan | — |

## What deliberately stays at repo root (the reusable point-in-time DATA layer)

The shelved code imports `from data.X import ...`, so the **point-in-time data adapters stay
under `data/`** (they depend only on `data/cache.py` and are a genuine reusable asset — the
edge-toolkit memory lists `edgar_index`/`finra_si`/`shares_out`/`prospectus` as reusable
harness modules):

- `data/cache.py` — point-in-time as-of cache (also used by the *forward* strategy).
- `data/market.py`, `data/news.py`, `data/filings.py`, `data/insider.py`,
  `data/fundamentals.py` — EDGAR / news / XBRL / bars PIT adapters.
- `data/edgar_index.py`, `data/finra_si.py`, `data/prospectus.py`, `data/shares_out.py` —
  FSSD-specific fetchers.

Their unit tests remain in `tests/` (they pass standalone — their modules are present).
Collected datasets stay under the gitignored `data/` (`edgar_index`, `finra_si`,
`prospectus`, `shares_out`, `backtest`, `cache`). `options_tradability.py` and `universe.py`
also stay at root — they are **reused** by the forward strategy's eligibility gate.

## Reviving it

The parked modules use flat imports (`from divergence import ...`, `from backtest.metrics
import ...`) plus `data.*` / `universe` from repo root. They are **excluded from default
CI** (`testpaths=["tests"]` doesn't reach `shelf/tests`; ruff `exclude` includes `shelf`).
To run them, from the repo root (so both `shelf/` and root are importable):

```bash
cd /home/rodrigo/dramatic_options-claude
PYTHONPATH=shelf venv/bin/python -m pytest shelf/tests -q
```

Reviving an edge means a *new* `PREREG_*.md` contract first — the validation bar
(pre-registration, lockbox, Bonferroni-k, null+positive controls, stopping rule) still
applies. See `dramatic-options-validation-methodology` in memory.
