# PREREG — Miss base-rate ledger (does the curated universe catch cheap-then-moved names at a better rate than the market?)

**Status: FROZEN at merge (staged-class — merged only on the operator's explicit word).** Written BLIND
2026-09-14, before the first ledger row exists. Amendments are dated appends; the pinned reads (§4) are
not edited after the first row.

## 1. Motivation (the hole the null books don't cover)

The five parallel books (real / shadow / 3A / 3B / shares) and the §6 reference-return sweep over
council-dropped and gate-vetoed names already measure every miss **among names the system saw**. Nothing
measures the names it never saw: the ~6,300 options-enabled US equities outside `config.universe.themes`.
That is the input the quarterly curation refresh (`PREREG_UNIVERSE_CURATION` §3) has no number for.

The naive instrument — a list of big movers assembled after the fact, then asked "what would have caught
this?" — is hindsight selection on the outcome (the anti-HARK rule, `PREREG_CONVEXITY_CALIBRATION` §6)
and is momentum-as-sourcing by construction (forbidden as a curation criterion, `PREREG_UNIVERSE_CURATION`
§2). This ledger is the form that survives that discipline: **forward, base-rated, sealed per name,
counts-only, report-not-gate.**

## 2. The question, stated forward

Each week, at sweep time t, the production gate is read over two cohorts. Later, at horizon h, the
underlying's realized move is read. The pinned contrast is:

    P(big directional move at h | gate-cheap at t, cohort=universe)
  vs
    P(big directional move at h | gate-cheap at t, cohort=market)

and the unconditional companion P(big move at h | cohort) for both. "Cheap-then-moved" is the only miss
that was ever our trade: a name that ran but was never gate-cheap was never a candidate under the frozen
mandate, and its absence from the universe is not a miss.

## 3. Design (frozen)

- **Cohorts.** `universe` = the union of `config.universe.themes` members at sweep time (the register
  is additive-only, so this only grows). `market` = a **fixed random sample, drawn ONCE and frozen** in
  `records/miss_baserate/denominator.txt`: from Alpaca's ACTIVE / tradable / `has_options` US equities on
  NASDAQ, NYSE or AMEX, excluding fund-type names (ETF/ETN/Fund/Trust/Preferred/Warrant/Right/Unit in the
  asset name) and excluding the universe as of the draw; `random.Random(20260914).sample(sorted(pool), 300)`,
  then the first **150** in that order passing the feasibility floors (price ≥ $3, 20-day ADV ≥ $3M —
  the existing `eligibility.live` floors, no new thresholds). The draw is never re-drawn; a name that
  dies stays in the denominator (survivorship guard, §6 `reference_return_from_bars` semantics).
- **Sweep (weekly, Sundays beside the L0 review).** For every name in both cohorts: direction from
  trailing momentum (the 3B/shares convention: close[-22]/close[-253] − 1 sign, bullish if unknown),
  the production `select_structure` at the frozen 25%-OTM 180–365d target on the gate-of-record feed,
  then `is_cheap_convexity` at the frozen `iv_rv_max` / `otm_skew_max_volpts`. One row per name per
  sweep: date, **sealed key**, cohort, direction, structured (0/1), gate_cheap (0/1/blank),
  entry_close, feed. **The per-name gate verdict never carries the symbol**: the key is
  `sha256("miss_baserate_v1:" + SYMBOL)[:12]`. The seal is a discipline boundary on the recorded
  artifact (as `PREREG_UNIVERSE_CURATION` §6), not cryptography: the denominator file is plain, the
  ledger is sealed, and no report joins the two into a printable name.
- **Outcome.** Directional forward return from `entry_close` over **h ∈ {63, 126, 250} trading bars**
  (~3/6/12 months; 250 ≈ the option lifecycle), read through `sentinel_scoring.reference_return_from_bars`
  so a delisted/terminated series resolves to its last bar rather than vanishing. Directional return =
  raw return for bullish rows, negated for bearish rows. **Big move = directional return ≥ +0.50.**
  (A second, descriptive threshold of +1.00 is reported alongside; neither is tuned after the first row.)
- **Maturity gate.** A row counts at horizon h only once h bars have elapsed or the series terminated.
  Rows still inside the window are "accruing", shown as a count and never a rate.
- **Report = counts only.** Per cohort × horizon: n_matured, n_cheap, n_big, n_cheap∧big, the two
  conditional rates, and a two-proportion z with its small-n guard (each cell needs ≥ 20 matured rows
  before a rate is printed; below that the cell prints `n<20`). **No symbol, sealed key, or per-row
  verdict is ever printed by the report** (asserted by test).

## 4. Pinned reads (BLIND)

- **R1 (curation quality).** If, at h=250 with ≥ 20 matured cheap rows in each cohort,
  P(big | cheap, universe) is NOT greater than P(big | cheap, market) at z ≥ 1.64 (one-sided), the
  curated universe is not selecting cheap-then-moved names better than a random optionable slice, and
  the quarterly refresh should weight structural sourcing (§4 of the curation pre-reg) over thesis
  reading. This is a curation-quality finding, never a gate or council finding.
- **R2 (gate relevance, descriptive).** P(big | cheap) vs P(big | not-cheap) within the market cohort
  is reported alongside as a descriptive companion to the OPRA soak tripwires. It does not change the
  gate: the gate's thresholds are frozen elsewhere and this ledger has no write path into them.
- **Read dates.** First provisional read at the first quarterly review after the earliest rows reach
  h=63 (≈ 2026-12-13); R1 is readable at h=250 (≈ 2027-09).

## 5. What this ledger is NOT (named so it can't drift)

- **Not a signal.** No output of the sweep or the report enters discovery, the framer, the council, the
  gate, or sizing. The probe is never imported by the loop (asserted by the existing import-graph test
  class: it lives in `scripts/`).
- **Not a name source.** Names from the market cohort are never surfaced to the operator as candidates,
  in any form — not as "movers", not as "cheap-then-moved". If a market-cohort name later enters the
  universe by the ordinary thesis-first door, it is admitted on its thesis and feasibility exactly as
  any other, and its market-cohort rows stay in the market cohort (cohort is stamped at sweep time).
  This supersedes the 2026-09-14 conversational suggestion of "thesis prompts by name": that would have
  been momentum-as-sourcing.
- **Not per-name.** No per-name narratives, no "why did we miss it". The only deliverable is the rate
  contrast.
- **Not a cost line.** The sweep adds ~150 chain pulls per week on the existing read-only feed;
  no LLM calls.

## 6. Artifacts

`miss_baserate.py` (pure, tested: sealing, the frozen draw, the maturity-gated aggregation, the
never-a-symbol report) · `scripts/probe_miss_baserate.py` (`init` — draws and freezes the denominator,
refuses to overwrite; `sweep` — appends rows; `report` — counts only) ·
`records/miss_baserate/denominator.txt` (plain symbols, written once) ·
`records/miss_baserate/ledger.csv` (sealed rows, append-only) · `tests/test_miss_baserate.py`.
