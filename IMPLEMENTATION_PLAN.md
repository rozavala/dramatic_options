# Dramatic Options — Implementation Plan
## v2: Thematic Cheap-Convexity Inflection Trading

> **Companion to `SPEC.md` and `PREREG_THEMATIC_CONVEXITY.md`.** This supersedes the
> backtest-gated plan (divergence / FSSD), preserved at
> `shelf/IMPLEMENTATION_PLAN_backtest_gated.md`. Those edges were pre-registered, tested,
> and graded negative — this is a deliberate pivot to a **forward, discretionary** strategy,
> not a patch. Work one phase per session, in plan mode; each phase ends green.
>
> **Status: T0 · T1 · T1.5 · calibration · T2 (the council) · T2.5 (run-it-forward: PR1 close-side
> execution + PR2 systemd timers/deploy/notify) COMPLETE · T3 sentinels IN PROGRESS — PR1 (deterministic
> discovery core) + PR2 (LLM framer + origin-aware grounding + provenance + slot reservation) landed & green; PR3-core (weekly L0 systemd/deploy + §C cold-cache timing) BUILT & green, held UNARMED until §A; PR3b (brain-off null shadow book) BUILT & green; then T4.**
> T2.5 PR2 operationalized the forward loop: `Type=oneshot` `orchestrator.py` on systemd timers
> (L1 daily 15:45 ET pre-close = full cycle; L2 ~30min intraday `--monitor`), a fail-closed
> `is_market_open()` gate + `FORWARD_ENABLED` flag (no entries/LLM-spend when closed or inert), a
> `deploy.sh` that installs units on both envs but arms timers only where `FORWARD_ENABLED=true`
> (PROD stays installed-but-inert until T4), and Pushover paging (`OnFailure` + in-app for the
> soft exit-0 trips). DEV=paper runs it with `DRY_RUN=false`. See `DEPLOYMENT.md`.
> **Thesis framing clarified 2026-06-01 (reprice-capture; tenor = runway).** For the far-OTM sleeve
> this stays **hold-the-tail**: a calibration head-to-head graded a delta-trigger "exit-on-playout"
> rule EV-inferior (caps the tail, break-even hit-rate 19%→~67%; GBM bias favored it yet it lost),
> so the OTM exits (§6a) are unchanged and the T4 thresholds (venture shape) stand. The
> reprice-capture behavior is a distinct edge **deferred to a future, separately-pre-registered ITM
> sleeve** (financing/extrinsic gate + reprice/invalidation exits), to be decided by forward
> evidence. See `PREREG_THEMATIC_CONVEXITY` §1 amendment + `PREREG_CONVEXITY_CALIBRATION` §4 finding.
> (Sentinels T3 not started.) T1.5 added the L2 monitor (mark-to-market + deterministic
> profit-take/time-stop/expiry exits) and the real DRY_RUN-gated Alpaca paper-submit path; the
> calibration harness (`PREREG_CONVEXITY_CALIBRATION.md`) graded the exit structure (→ 4×→10×
> profit-take). T2 adds `council/` — the three-role LLM judgment layer that proposes themes.

---

## 0. What changed, and why

The prior plan demanded a *pre-validated, backtested* edge before deploying capital. Two
such edges (narrative-vs-delivery divergence; forced-supply secondary drift) graded
negative — and the analysis showed *why*: clean, backtestable, uncrowded edges in liquid
equity options barely exist for a small player. The durable edges are judgment-based, and
judgment edges cannot be backtested (training-data lookahead — guardrail §6).

- **From** "prove an edge on the harness, then trade it" **to** "deploy a conviction thesis
  forward, small and bounded, and let live results + risk control do the work."
- The thesis: **long-dated (6–12mo) far-OTM convex options on secular themes at an
  inflection point** — long the un-priced tailwinds, bearish the un-priced rollovers.
- **The harness's role flips:** no longer a pre-trade *validation gate*; now an
  *execution + risk-control + forward-scoring* engine.
- A forward-only strategy needs only **current** option data (which we have) → the "no
  historical options data" wall that blocked backtesting is irrelevant here.

## 1. The strategy (frozen — see PREREG_THEMATIC_CONVEXITY §1)

1. Identify a secular theme at **inflection**.
2. Express it with **long-dated, far-OTM, defined-risk** options.
3. **The gate — the edge:** trade only when implied vol is **not** already pricing the theme
   (convexity is *cheap* — "copper-not-rockets").
4. Run a **portfolio of small convex bets** (venture-style payoff).
5. Discipline lives in **sizing and risk control**, not validation.

## 2. The hard seam — deterministic gates vs. council judgment

The council **proposes**; deterministic, code-enforced rules **dispose**.
**Deterministic (hard):** the IV/cheap-convexity gate, eligibility, sizing / caps / book
budget, the kill rule. **Judgment (council, forward-scored, never sole authority):** which
themes are at inflection, structural vs. fad, the cleanest name, narrative ahead-of vs.
behind fundamentals. The council can be wrong; it cannot buy expensive convexity, breach a
cap, or defeat the kill rule. (PREREG §2.)

## 3. Reuse map (as built)

**Reuse (plumbing, kept at repo root):** `clock.py`, `state.py`, `config_loader.py` +
`config.json`, `orchestrator.py`, `risk.py`, `universe.py`, `options_tradability.py`
(→ eligibility), `data/alpaca_client.py` (chain + IV/greeks/bid-ask), `data/cache.py`
(point-in-time cache, also used to accrue an IV baseline going forward). The wider
point-in-time data adapters (`data/market,news,filings,insider,fundamentals,edgar_index,
finra_si,prospectus,shares_out`) stay at `data/` as the reusable PIT data layer.

**Shelve (parked, not deleted — `shelf/`):** the backtest harness (`backtest/`),
divergence signal (`divergence,narrative,substance,watchlist`), FSSD modules
(`friction,fssd_stage1` + runners), their tests, and the `divergence`/`fssd` config blocks.
A real asset for any future deterministic idea; does not gate this strategy. See
`shelf/README.md`.

## 4. Risk frame — FIRST-CLASS, pre-registered (PREREG §5)

Frozen in `config.json:convexity_book` / `kill_rule` (operator decisions, 2026-05-31):
- **Convexity book = 10%** of account (total premium-at-risk; the only money that can be
  lost — long options are inherently defined-risk).
- **Per-name cap ≤ 1%** of account; per-theme = per-name for T1.
- **Per-cluster cap ≤ 2%** of account (correlation budget — PREREG §5 amendment 2026-06-03): a
  deterministic, operator-curated `symbol→cluster` map (never an LLM label), **entry-premium** basis
  counting committed-incl-**pending**; composes as `min(per-name, book, cluster)`; applies to the
  brain-off shadow book too.
- **Max concurrent positions = 15.**
- **Sizing = flat-by-slots, capped — NOT Kelly** (a far-OTM lotto Kelly-sizes to ~0).
- **Kill rule:** halt new entries at **20% book drawdown OR 9 months** zero payoff; plus the
  always-on `KILL` switch.
- **Survivorship log:** every evaluated bet recorded, winners and zeros.

## 5. Phased build

**T0 — Repurpose & freeze ✅ COMPLETE.**
Stripped to reusable plumbing; shelved the backtest machinery; wrote
`PREREG_THEMATIC_CONVEXITY.md` (risk frame + IV gate, frozen *before* signal code); installed
this plan; updated `SPEC.md` / `CLAUDE.md`. No alpha logic.

**T1 — Minimal paper loop ✅ COMPLETE (+ T1.5).**
Smallest thing that can actually trade on paper:
hand-seeded theme+name → pull current chain + trailing realized vol → eligibility gate →
IV/cheap-convexity gate → propose a defined-risk long-dated structure → size per §4 → log a
paper position with a structured rationale + survivorship-log every evaluation →
forward-track P&L. Seeded from `themes.json`. **T1.5** added the L2 monitor (mark-to-market +
deterministic exits) and the real DRY_RUN-gated Alpaca paper-submit + reconciliation path.

**T2 — Council does the theme work �doing.** A minimal-but-real **three-role** council
(Proposer → direction-relative Adversary → Master Strategist) over the `themes.json` **candidate
watchlist** — it judges (inflection, structural-vs-fad, cleanest name, bull/bear), it does NOT
discover (that's T3). Roles run across distinct providers via a heterogeneous router (`council/`)
with a first-class cost ledger; SDKs are lazy-imported and `--demo`/tests use a deterministic
FakeRouter. The deterministic gates still dispose — **conviction is recorded + forward-scored
(Brier + contribution) ONLY; it never sizes a position and never overrides a veto** (the hard
seam). Kill checks precede any LLM spend; over-budget/failure fail closed to zero entries.

**T3 — Sentinel inflection discovery (in progress).** A weekly **L0** scan that PROPOSES new
candidates into the council's candidate set — discovery proposes, the council judges, the
deterministic gates dispose (the hard seam, unchanged; both judgment layers forward-scored, never
backtested §6). The prescreen is a **motion/structural funnel**, NOT a cheapness/alpha claim:
surface a name iff it clears a **disjunctive ABSOLUTE floor** (`|momentum|≥floor` OR `rv_slope≥floor`
OR a rare structural filing — 424B5/13D/S-1), with **within-basket z** ranking only the survivors
(so a dead week surfaces nothing and a low-vol basket isn't buried under a high-vol one). Cheapness
stays the IV gate's job (fresh, authoritative; ranking on it would pre-select for gate-pass and
defeat the gate's independence). Candidates union into the council **hand-seed-first then ranked**
(so the `max_candidates` cap drops the weakest sentinel, never a conviction); lineage is
`(symbol,direction)`, updated in place on re-surface (continuous provenance), TTL→dormant.
Forward-scored: traded→outcome+Brier+**realized multiple**; never-traded + a **random control
cohort** → label-only reference forward-return (survivorship/terminal-event guarded), compared on
the **tail**, not the mean. **PR1 (done, offline):** `discovery.py` prescreen + `sentinels.py`
(store/union) + `sentinel_scoring.py` + `orchestrator.py --discover` (FakeRouter, kill-before-spend)
+ the L1 union + `config.discovery`/scan baskets + migration 0007. **PR2 (landed):** the bounded LLM framer (a skeptic adjudicating
real-inflection/artifact/mean-reversion, model-decorrelated, fail-closed-to-zero) + **origin-aware
grounding** (sentinels ground the framer AND the council on their MARKERS, not news — else a
pre-news discovery is NEUTRAL-dropped) + the provenance chain (sentinel→proposal→position; traded →
resolve at close with outcome+Brier+realized-multiple, never-traded → the reference sweep) + the
`sentinel_max_slots` reservation (`veto-sentinel-slots`) + hard-seam guard tests. **PR3-core (BUILT
& green):** weekly L0 systemd timer (Sun 08:00 ET, Persistent, OnFailure) + deploy wiring + docs;
`TimeoutStartSec=900` **derived** from the §C cold-cache run (exit-0 in 11s; $0.0019 over 8
gemini-flash-lite framer calls — the first live LLM round-trip §A couldn't reach). Held UNARMED
until §A re-verifies the live L1/L2 loop (merging auto-arms L0 = the go-live act). **PR3b (BUILT & green):**
the **brain-off null shadow book** (`shadow_book.py` + migration 0008 + fail-soft L1/L2 wiring) — a
parallel book running the deterministic pipeline over the SAME
candidate union the council sees but brain-OFF (every gate-passer, no council include/exclude, no
framer drop), **simulated fills only — NEVER the broker** (its own `shadow_positions` table + a
never-broker merge-blocker test; fail-soft so a shadow bug never halts the real cycle), origin-tagged
(hand-seed vs sentinel), scored on the per-position realized-multiple **TAIL** — the gap to the real
book = the LLM layer's marginal contribution. **Pre-T4:** the per-theme/cluster exposure cap
**LANDED 2026-06-03** (PREREG §5 amendment, `clusters.py` + `cluster_fraction=0.02` + migration 0009;
fixed the false diversification the first §C scan exposed — 7 correlated AI-capex-power names across two
baskets). **REMAINING:** a basket-quality report (close the survivorship → basket-curation loop); the
**fixed-basket null** — **PR1 pre-registration FROZEN 2026-06-03** (`PREREG_FIXED_BASKET_NULL.md`,
written BLIND via the R2/R3 plan red-team): the no-IV-gate book is the **headline gate test**
(`shadow − 3A` = FSSD null≈signal on the edge), `real − 3B` the **bundled** beat-the-basket read;
**p95**-tail + **bootstrap CIs** + **with/without-top-k** on the event-enriched gate-rejected cohort;
shares = descriptive secondary; **live basket → `real − 3B` is the clean read**. **PR2a (book 3A)
BUILT 2026-06-03** (`fixed_basket.py` + migration 0010, gate-OFF over the same union, cap-ON, fail-soft
+ never-broker; `--demo`: shadow books 1 vs no-gate-3A books 2, the gate rejected NVDA; 335 tests).
**BUILD next:** PR2b (3B whole-basket equal-weight + the shares null, weekly L0) — the null the T4
real-money decision hinges on; and a fast-follow trailing-return-**correlation diagnostic**
(report-not-gate, the curation backstop — lands before the next Sunday L0 scan).

**T4 — Graduate to tiny real money.** On a pre-committed rule (N paper trades logged, payoff
distribution sane, risk frame held with no breaches) → tiny real capital under the identical
risk frame, behind the existing three live gates.

**T5 — Calibrate & scale.** Refine forward scoring, calibrate sizing to the observed payoff
shape, build a theme library, broaden the universe; consider graduating the IV gate from the
RV proxy to a true IV-rank once enough chain snapshots have accrued (PREREG §4b).

## 5b. Cross-cutting workstreams (operator-requested 2026-06-03) — each its own plan-mode + red-team session

**Observability / monitoring dashboard (Streamlit; greenfield — no `dashboard.py` yet).** A single
operator surface over what the system is doing and how it's performing — read-only over the SQLite
journal + the PIT cache, never a trade/authorization path, fail-soft, safe against the live DB:
- **Discovery / scanning:** the latest L0 scan — surfaced sentinels (markers, `inflection_score`,
  framer verdict), the random controls, the `ai_compute`-style baskets, TTL/dormancy, the cost ledger.
- **Data gathered:** accrued chain snapshots (the forward IV baseline), realized-vol series, the
  marker corpus — the substrate that later graduates the IV gate (§4b) and feeds the nulls.
- **Positions:** the real `convexity_positions` book + the brain-off `shadow_positions` book +
  (later) the fixed-basket null — status, marks, DTE, the survivorship `convexity_eval` log, and
  **per-cluster occupancy vs the cap** (PREREG §5 amendment).
- **Performance (the point):** realized-multiple **tails** per origin, Brier + council contribution,
  the **real−shadow gap** (does the LLM layer add value) and the **book−fixed-basket gap** (does the
  apparatus beat the basket), premium-bled-vs-paid, drawdown vs the kill threshold. Forward-only —
  read as calibration, never a pass-gate (§6 / guardrail §6).

**File-structure / architecture for scale** (currently **22 flat root modules** + `council/` /
`data/` / `calibration/` / `scripts/` packages). Evolve toward domain packages — e.g. `discovery/`,
`trading/` (structure · gate · sizing · clusters · paper_loop · monitor · broker · risk ·
shadow_book), `data/`, `council/`, `observability/`, `infra/` (orchestrator · config · state · clock ·
notify) — **incrementally and nimbly**: group the obvious clusters first; don't over-engineer a
paper-stage system. **Hard constraints (high blast radius):** keep `orchestrator.py`'s entry stable
for the systemd `ExecStart` + `deploy.sh` paths (or update them in lockstep); preserve the
flat-layout `sys.path` shim in `conftest.py` (or migrate to an installed package); migrations stay
numbered under `scripts/migrations/`. Its own carefully-sequenced PR(s), full suite green at each
step — never mid-flight with the live loop unverified.

## 6. Forward measurement — calibration, not a pass-gate (PREREG §7)

Per bet: theme, inflection thesis, IV-gate verdict, structure, size, rationale, outcome,
P&L. Metrics: hit rate, payoff distribution, premium-bled-vs-paid; Brier + council
contribution arrive with T2. **6–12mo holds mean *years* to significance.** Forward data
informs calibration, sizing, and the kill decision — it does **not** prove an edge. A good
run is not validation; a bad run is not disproof until the kill rule trips.

## 7. Standing guardrails

- Paper-first; real money only via the T4 rule + the three live gates (`PAPER=false` AND
  `LIVE_TRADING_ENABLED=true` AND `--live`).
- Fail-closed; kill switch always live; defined-risk default; log every decision.
- The IV gate is a hard veto — a beloved theme with rich convexity is still a pass.
- The operator builds tooling; a human authorizes any capital. Not investment advice; the
  forward results decide.
