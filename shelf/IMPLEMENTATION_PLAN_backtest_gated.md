# Dramatic Options — Implementation Plan (SUPERSEDED — backtest-gated)

> **SUPERSEDED 2026-05-31.** This is the original backtest-gated build plan. Both
> deterministic edges it gated (divergence v1, FSSD v2) graded negative, so the system
> pivoted to a forward, discretionary thematic cheap-convexity strategy. The canonical
> plan is now the v2 `IMPLEMENTATION_PLAN.md` at repo root. Kept here for history.

---

## Phase 0 — Scaffolding ✅ COMPLETE

- [x] Repo, `.gitignore`, `pyproject.toml`, `requirements.txt` (pinned).
- [x] `config.json` + `config_loader.py` (schema-validated).
- [x] `clock.py` (injectable clock; no naked `datetime.now`).
- [x] `state.py` (SQLite state + journal).
- [x] `orchestrator.py` (cycle skeleton, kill-switch check, fail-closed).
- [x] CI (GitHub Actions: ruff, pytest).
- [x] Deploy scaffolding (inert until app exists).

## Phase 1 — Data + Divergence + Backtest ✅ COMPLETE (edge graded negative)

- [x] `data/alpaca_client.py` — Alpaca market data (bars, chains, IV).
- [x] `data/cache.py` — point-in-time disk cache.
- [x] `universe.py` — tradable-universe construction.
- [x] `narrative.py` — thesis representation.
- [x] `substance.py` — fundamentals/insider/revenue substance scoring.
- [x] `divergence.py` — the divergence signal.
- [x] `watchlist.py` — candidate ranking.
- [x] `backtest/engine.py` — walk-forward, no-lookahead backtest.
- [x] `backtest/metrics.py` — rank-IC, bootstrap CI, Bonferroni.
- [x] `backtest/run.py` — backtest entry point.
- [x] `friction.py`, `options_tradability.py`, `fssd_stage1.py` — FSSD edge (graded negative).
- [x] Edge gate run to completion: divergence UNPROVEN (k=4), FSSD FAILED (Stage-1 k=1).

## Phase 2 — Council + Execution (NOT STARTED under this plan)

- [ ] `council/` — analyst/critic/risk/arbiter agents.
- [ ] `compliance.py` — fail-closed compliance gate + conviction gate.
- [ ] `sizing.py` — fractional-Kelly sizing against risk budget.
- [ ] `execution/` — order manager, atomic combos, limit walking.
- [ ] `forensics.py` — full decision journal.
- [ ] Brier + contribution scoring (forward).

## Phase 3 — Forward-scoring + Calibration + Dashboard (NOT STARTED)

- [ ] Forward-scoring pipeline.
- [ ] Calibration reports.
- [ ] Streamlit dashboard.

## Phase 4 — Live gate (NOT STARTED)

- [ ] Paper→live promotion gate.
- [ ] Reconciliation hardening.
- [ ] Live-trading runbook.

---

*End of superseded plan. See repo-root `IMPLEMENTATION_PLAN.md` for the active v2.*
