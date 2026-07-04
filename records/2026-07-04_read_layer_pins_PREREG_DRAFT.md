# 2026-07-04 — READ-LAYER pre-registration: four blind pins before the first resolution exists

**Status: DRAFT — values proposed by CC; each pin requires the operator's EXPLICIT per-value
ratification (never merge-inheritance). Freeze = the operator's word on each of §1–§4 → dated
FROZEN stamp → then the (small, report-time-only) build.**

**Why now, with a clock:** the real book's first position (PL, 2026-07-01) and the null books'
June–July vintages start resolving ~Nov–Dec 2026 (21-DTE time-stops on Dec-2026+ expiries;
profit-takes can land any time). Every pin below is only honest if written while **zero
resolutions exist anywhere** — which is true today and expires without warning (a 10× spike
would resolve PL tomorrow). Provenance: advisor review 2026-07-02 (P2-2, §2.3), verified gaps
(FBN §5 pins no fill haircut; per-position bootstrap ignores theme concentration), and the
counterfactual-mandate ledger proposal (§2.3 of the same review).

## §1 — Fill-realism sensitivity band (simulated books mark at MID; mid is most fictional on far-OTM wings)

- **Pin:** every simulated-book tail read (shadow / 3A / 3B) is reported as a **two-column
  band**: *frictionless* (mid-to-mid, the current computation) and *conservative* (round-trip
  haircut at the eligibility bound: realized multiple × (1−h)/(1+h) with **h = 0.125** — half
  of the 25% `max_bid_ask_pct` cap each way). **A gate/apparatus claim must hold under BOTH
  columns** to be stated as a finding; holding only frictionless is reported as
  "friction-fragile," verbatim.
- Report-time-only (no stored values change, no migration). The real book needs no haircut
  (actual fills).
- *Flagged follow-up, not pinned:* record bid/ask at entry in the attempt telemetry so a
  MEASURED haircut can replace the bound later; the real book's own fills accumulate as the
  friction calibration.

## §2 — Cluster-blocked bootstrap (post-fork null books are deliberately theme-concentrated)

- **Pin:** the decision-bearing bootstrap CI for every per-book tail quantile resamples
  **cluster-blocks**, not positions: blocks = the deterministic `clusters.py` symbol→cluster
  map (a symbol outside every cluster = its own singleton block); resample blocks with
  replacement, pool their positions. Position-level CIs stay displayed as the secondary
  (narrower, optimistic) column. Quantile list and B unchanged from FBN §5.
- Rationale: with cluster caps OFF in the null books, nuclear×n / silver×n positions violate
  per-position independence; a position-level CI overstates effective n exactly where the
  books are most concentrated.

## §3 — Resolution calendar + minimum-n floor (the 2026-11-02 checkpoint gets a known denominator)

- **Pin:** the checkpoint report publishes, per book, the **expected-resolution schedule** —
  for each open position `min(expiry, expiry − 21d time-stop)` (profit-takes arrive earlier,
  unknowable) — and states every read's denominator against it.
- **Pin (the floor): no directional claim** (gate-vs-null, council-marginal, or
  apparatus-vs-basket) **below n ≥ 10 resolved positions in EACH compared book AND ≥ 3
  distinct clusters represented among them.** Below the floor the report says "accruing —
  below the pre-registered floor," verbatim, regardless of how suggestive the numbers look.
  PRIMARY stays p95 (FBN §5); no quantile substitution at low n.

## §4 — Counterfactual-mandate ledger (branch-3 evidence, replayed offline from the recorded booleans)

- **Pin (variants, fixed now, blind):** from each deliberated proposal's persisted strategist
  booleans (`structural_vs_fad` / `under_narrated` / `at_inflection` + conviction), compute the
  would-have-included set under: **V1** any-2-of-3 criteria; **V2** drop `at_inflection` from
  the AND; **V3** conviction floor HIGH (a *tightening* — symmetric honesty); **V4** the actual
  mandate (identity control).
- **Pin (outcome attribution):** a variant's hypothetical include maps to the **shadow book's**
  realized multiple for the same symbol where a shadow position opened within **±5 trading
  days** of the proposal (both sit atop the same gate); unmatched includes are reported
  UNRESOLVED, never proxied further. Scope caveat pinned: proposer-stage abstentions carry no
  booleans — the replay covers deliberated names only.
- Report-only, never a trade path, no new data collection (the booleans persist since PR-B).
  At D (2027-03-02) this upgrades branch-3 from "reconsider somehow" to "each named relaxation
  would have booked set S with outcome X."

## §5 — Status

DRAFT. Nothing builds until the operator ratifies §1–§4 each (edits welcome — the VALUES are
the operator's; the blindness deadline is the point). After the freeze: one small report-time
PR (no migration, no schema change, stamped), extending the existing tail/report code paths.
