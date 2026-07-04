# 2026-07-04 — READ-LAYER pre-registration: four blind pins before the first resolution exists

**Status: DRAFT v2 (self-red-teamed 2026-07-04 — four weaknesses found and fixed, listed in
§0) — values proposed by CC; each pin requires the operator's EXPLICIT per-value ratification
(never merge-inheritance). Freeze = the operator's word on each of §1–§4 → dated FROZEN stamp
→ then the (small, report-time-only) build. At freeze, a one-line dated pointer to this doc is
added to `PREREG_FIXED_BASKET_NULL.md` §5 (the pins COMPOSE with FBN §5; nothing there is
edited).**

## §0 — What the v2 self-review changed (so the red-team starts where v1 ended)

1. §1 now states **where the haircut actually bites** (absolute and sim-vs-real reads) and
   where it provably cannot (a uniform multiplicative haircut is ORDER-INVARIANT for
   sim-vs-sim contrasts) — v1 implied it protected the `shadow − 3A` read, which it does not.
2. §2 adds the **block-count honesty rule** (n_blocks displayed; <5 ⇒ "unstable" tag), pins
   the **map version** (report-time current), and names the method's residual limit
   (cross-cluster commodity beta).
3. §3 fixes sloppy arithmetic (`min(expiry, expiry−21d)` = just `expiry−21d`) and pre-states
   that the 2026-11-02 checkpoint will very likely read "accruing" — expected, not a failure.
4. §4 adds the **judgments-held-fixed caveat** (the replay is valid for ENFORCEMENT-layer
   variants only), the **per-vintage match-rate** requirement (the pre-fork censored window is
   a known matching hole; post-fork the uncapped null books make match-rates ≈ 1), the
   **all-other-rules-identical** clause, and the **pinned metric** (else "which stat do we
   quote for V2" becomes a post-hoc choice).

**Why now, with a clock:** the real book's first position (PL, 2026-07-01) and the null books'
June–July vintages start resolving ~Nov–Dec 2026 (21-DTE time-stops on Dec-2026+ expiries;
profit-takes can land any time). Every pin below is only honest if written while **zero
resolutions exist anywhere** — which is true today and expires without warning (a 10× spike
would resolve PL tomorrow). Provenance: advisor review 2026-07-02 (P2-2, §2.3), verified gaps
(FBN §5 pins no fill haircut; per-position bootstrap ignores theme concentration), and the
counterfactual-mandate ledger proposal (§2.3 of the same review).

## §1 — Fill-realism sensitivity band (simulated books enter and mark at MID)

- **Pin:** every simulated-book tail read (shadow / 3A / 3B — NOT shares, which carries its
  own pinned frictionless-benchmark caveat) is reported as a **two-column band**:
  *frictionless* (mid-to-mid, the current computation) and *conservative* (round-trip haircut
  at the eligibility bound: realized multiple × (1−h)/(1+h), **h = 0.125** = half of the 25%
  `spread_pct` cap, which is spread/mid — verified against `options_tradability.spread_pct`).
  **Any ABSOLUTE claim ("the book beats 1×", P(total loss), "worth running") and any
  SIM-VS-REAL claim must hold under BOTH columns**; holding only frictionless is reported as
  "friction-fragile," verbatim.
- **Honesty about scope (v2):** the haircut is a uniform multiplicative factor, so it CANNOT
  change the ordering of two simulated books' quantiles — `shadow − 3A` (the gate contrast) is
  haircut-invariant by construction. Its bite is exactly where flattery lives: sim books vs
  the REAL book (whose fills are actual), and absolute performance claims.
- **Bound regime, stated:** h is an entry-time bound. At exit, winners (deep ITM) typically
  carry tighter relative spreads (the bound is conservative there); near-worthless losers can
  carry wider ones (immaterial in $; a total loss is M=0 under both columns). The bound is not
  a measurement — which is why the follow-up below exists.
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
- **Pin (map version, v2):** the CURRENT config map at report time, applied to all positions,
  with the map's git provenance stated on the report (re-partitions are dated operator acts; a
  report never mixes two maps).
- **Pin (block-count honesty, v2):** every cluster-blocked CI displays **n_blocks**; any CI
  built on **n_blocks < 5 carries an "unstable" tag** and cannot support a directional claim
  on its own (composes with the §3 floor).
- **Named residual limit (v2):** blocks cannot capture CROSS-cluster correlation (nuclear /
  silver / copper share commodity beta) — the blocked CI is less optimistic than
  per-position, not a guarantee of independence. Recorded so a later reader cannot claim we
  thought otherwise.

## §3 — Resolution calendar + minimum-n floor (the 2026-11-02 checkpoint gets a known denominator)

- **Pin:** the checkpoint report publishes, per book, the **expected-latest-resolution
  schedule** — for each open position, the 21-DTE time-stop date (**expiry − 21d**); actual
  resolutions can only arrive EARLIER (profit-take, deterministic exits). Every read states
  its denominator against this schedule.
- **Pin (the floor): no directional claim** (gate-vs-null, council-marginal, or
  apparatus-vs-basket) **below n ≥ 10 resolved positions in EACH compared book AND ≥ 3
  distinct clusters represented among them.** Below the floor the report says "accruing —
  below the pre-registered floor," verbatim, regardless of how suggestive the numbers look.
  PRIMARY stays p95 (FBN §5); no quantile substitution at low n.
- **Pre-stated expectation (v2):** on current expiries (Dec-2026 → mid-2027), the 2026-11-02
  checkpoint will very likely read "accruing" on every contrast — that is the schedule
  working, not a verdict; the checkpoint exists so a censored-looking state is SEEN, not so a
  verdict is forced.

## §4 — Counterfactual-mandate ledger (branch-3 evidence, replayed offline from the recorded booleans)

- **Pin (variants, fixed now, blind):** from each deliberated proposal's persisted strategist
  booleans (`structural_vs_fad` / `under_narrated` / `at_inflection` + conviction), compute the
  would-have-included set under: **V1** any-2-of-3 criteria; **V2** drop `at_inflection` from
  the AND; **V3** conviction floor HIGH (a *tightening* — symmetric honesty); **V4** the actual
  mandate (identity control). **All other rules identical in every variant** (floor stays
  MODERATE except V3; include still required; gate/caps/exits untouched — variants are
  ENFORCEMENT-layer only).
- **Pin (validity scope — judgments held fixed, v2):** the recorded booleans were produced
  under the CURRENT sha-pinned prompts; the replay answers "what would the deterministic
  enforcement have passed given the SAME judgments." A variant that would require different
  prompts or criteria definitions is OUT OF SCOPE of this instrument (it would need its own
  forward run — never a backtest, guardrail §6).
- **Pin (outcome attribution):** a variant's hypothetical include maps to the **shadow book's**
  realized multiple for the same symbol where a shadow position opened within **±5 trading
  days** of the proposal (both sit atop the same gate); unmatched includes are reported
  UNRESOLVED, never proxied further. Scope caveat pinned: proposer-stage abstentions carry no
  booleans — the replay covers deliberated names only. **Match-rate is reported PER VINTAGE
  (v2):** the 06-10→07-02 slot-censored window is a known matching hole (structural, poor
  coverage); post-fork the uncapped null books book every gate-passer, so match-rates approach
  1 — the ledger's strength is forward-loaded, stated now.
- **Pin (the metric, v2):** at resolution windows each variant reports set size, match rate,
  and the matched realized-multiple tail — the SAME quantile list, §1 band, and §2 blocked CIs
  as every other read, **subject to the same §3 floor** (a variant below floor reads
  "accruing").
- Report-only, never a trade path, no new data collection (the booleans persist since PR-B).
  At D (2027-03-02) this upgrades branch-3 from "reconsider somehow" to "each named relaxation
  would have booked set S with outcome X."

## §5 — Status

DRAFT. Nothing builds until the operator ratifies §1–§4 each (edits welcome — the VALUES are
the operator's; the blindness deadline is the point). After the freeze: one small report-time
PR (no migration, no schema change, stamped), extending the existing tail/report code paths.
