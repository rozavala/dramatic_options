# dramatic_options

Thematic **equity & ETF options** trading system (Alpaca, paper-first). A standalone
sibling to the commodity-options "Real Options" system. **Paper-only; live trading is
multi-gated and not yet enabled.**

**Active strategy — thematic cheap-convexity (v2, forward/discretionary).** Long-dated
(6–12mo) far-OTM **defined-risk** options on secular themes whose **implied vol hasn't
priced the move yet** ("copper-not-rockets"), run as a portfolio of small convex bets. The
earlier backtest-gated edges (divergence, FSSD) were graded negative and are parked in
`shelf/`; the harness role flipped from a validation gate to **execution + risk-control +
forward-scoring**.

Read `PREREG_THEMATIC_CONVEXITY.md` (the frozen risk frame + IV gate), then
`IMPLEMENTATION_PLAN.md` (build order) and `SPEC.md` (architecture + the *why*).

## Setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env                # fill in Alpaca paper keys
python scripts/run_migrations.py    # SQLite schema (currently v3: runs, signals, convexity_*)
pytest                              # offline test suite (no network)
```

## Run

```bash
python -m dramatic_options.orchestrator --demo   # one paper cycle on deterministic synthetic data (no creds)
python -m dramatic_options.orchestrator          # one paper cycle on themes.json (needs Alpaca paper creds)
touch KILL                                       # halt everything (checked every cycle)
```

`--demo` is the offline acceptance path: it logs a paper position for a *cheap* seeded theme
and vetoes a *rich* one, printing the survivorship log. Seed your own conviction themes by
editing **`themes.json`** (name · symbol · direction · thesis · active).

## The edge — the IV / cheap-convexity gate

The edge IS a hard deterministic gate (`convexity_gate.py`): trade only when the option's
convexity is *cheap*. With **no historical IV** (forward-only chains), "cheap" is measured
from one current chain snapshot + the underlying's trailing realized vol:

- **IV/RV ratio** `IV_atm / RV ≤ 1.2` — ATM vol isn't richly bid over what the name realizes.
- **OTM skew** `IV(wing) − IV_atm ≤ 10` vol pts — the wing we're buying isn't already bid up.

Pass ⇔ both hold; **fail-closed** on any missing input. The council (T2, `council/`) only
*proposes* themes from the `themes.json` candidate watchlist — it can never override this veto,
breach a cap, change sizing, or defeat the kill rule (conviction is recorded + forward-scored
only). Risk frame
(frozen, `config.json`): book = 10% of account, per-name ≤ 1%, ≤ 15 open, flat-by-slots
sizing, kill at 20% book DD or 9mo dry. Forward measurement is **calibrate-not-prove**:
6–12mo holds can't reach significance fast (`PREREG_THEMATIC_CONVEXITY §7`).

## Layout

The core lives in the **`dramatic_options/`** package (SPEC §10), run as a module
(`python -m dramatic_options.orchestrator`). Inside it: plumbing (`config_loader`, `clock`,
`state`, `risk`, `orchestrator`, `universe`, `options_tradability`) + the T1 strategy
(`themes`, `convexity_gate`, `structure`, `convexity_sizing`, `broker`, `convexity_data`,
`paper_loop`, `monitor`) + the T2 **`council/`** subpackage (heterogeneous `router` +
`FakeRouter`, `context`, `agents`, `filters`, `debate`, `proposal`, `scoring`, `wiring`) +
the **`data/`** subpackage (`alpaca_client`, `cache`, `news`, and the reusable point-in-time
adapters) + the **`calibration/`** Monte-Carlo engine. At the **repo root** sit the Streamlit
`dashboard.py`, `scripts/` (deploy, migrations, systemd templates), `tests/`, and the runtime
files `config.json` / `themes.json` / `.env`. Parked backtest-gate machinery lives in
**`shelf/`** (not deleted — see `shelf/README.md`). Tunables in `config.json`; secrets in
`.env` (never committed). Point-in-time everything — all "now"/market-state flows through an
injectable `Clock`.
```
