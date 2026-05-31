# PREREG — FSSD v1 · Forced-Supply Secondary Drift

**Status: FROZEN for the audit (FREEZE-A, 2026-05-31, `fssd` hash `76587407f824a0bd`, k=0).**
Stage-1 gate params await FREEZE-B (§14). This document is the pre-registration: it was written
before any FSSD performance number existed, the way the divergence gate (SPEC §2a) was. The §8
eligible-N audit (coverage-only, no CAR, no k consumed) is the next runnable step.

**One-line thesis.** Registered secondary offerings (424B5 takedowns) inject *price-insensitive
supply*; the resulting negative drift is arbitraged away wherever the offsetting short is
cheap, and **survives only where short-sale friction makes that short uneconomic** — a corner
that is *deterministic and conditionable*, hence harness-gradeable, hence a real edge gate
rather than another forward-only council bet.

---

## 1. Mechanism (the gate question, answered)

Every directional edge must name *why the marginal participant on the other side isn't
trading on value*: **forced**, **absent**, or **siloed**. FSSD is **forced**: in a registered
takedown the seller distributes a fixed share count regardless of price — non-discretionary
supply. The textbook capture is to **short into the supply**; that trade competes the
unconditional drift toward zero.

**The arbitrage-resistance argument (why a residual survives):** capturing the drift requires
shorting, and shorting has frictions — borrow cost, low float, hard-to-borrow status. Where
those frictions make the short uneconomic, the arb *mechanically cannot run* and the forced-
supply drift persists. Those frictions are **deterministic and observable point-in-time**
(short interest, float, ADV, price level), so the un-arbed residual is a *pre-registrable
conditioner*, not council judgment. This is what dissolves the circularity objection ("the
property that makes it testable — public, dated — makes it arbitraged"): the *mean* event is
arbitraged; the *friction-conditioned corner* need not be.

This separates FSSD cleanly from everything previously tested: divergence was an **information**
edge (value the name better than the price-setter — unwinnable in watched names). FSSD is a
**flow** edge (the other side is *forced*, and the corrective arb is *blocked*). A flow edge
has no reason to be thematic — hence the broad universe (§4).

**Forced *buying* is deliberately out of v1 scope (deferred to a 2nd pre-registration).** The
mirror trade — forced *demand* (index additions, short-squeeze covering) → positive drift — is
real but **friction-asymmetric**: the corrective arb against forced buying (just sell/short the
overbought name) is mostly *unfrictioned*, so the effect arbitrages away far more completely
than forced selling does. It is therefore a *weaker* edge on its own axis and is set aside for a
separate pre-registered test on the **same friction infrastructure** built here (squeeze-
convexity). Note the tie-in: squeeze risk is precisely *part of why* the arb-short against a
secondary is deterred (§12, FREEZE-B #2), so it is intrinsic to FSSD's left tail, not a
separable strategy — v1 manages it via defined-risk structure (guardrail §3), not by trading it.

---

## 2. The borrow-in-the-puts problem → two-stage spend gate

**The deepest objection, conceded in full.** This is an *options* system, and the same short-
sale friction that preserves the stock drift is *embedded in the options*. In a hard-to-borrow
name, market-makers who sell puts hedge by shorting the stock, pay the borrow, and price it
into the premium — option-implied borrow bends put-call parity so **puts are dearest exactly
where the drift survives.** The drift you capture and the borrow you pay are, to first order,
the same number with opposite signs. **Therefore the edge must clear the friction-implied
options cost, not the gross stock drift.**

**Why this is a sequencing constraint, not an upfront build.** The implied-borrow cost only
matters *if the gross drift is non-zero in the friction corner*. If gross drift is ~0 there,
net-of-borrow is moot and we never pay for options data. The current stack has **no historical
options data** (confirmed: `alpaca_client.py` exposes the chain for the live watchlist only;
"point-in-time option liquidity back to 2022 does not exist, so the backtest must never gate
on it"). So:

- **Stage 1 — gross-CAR gate (FREE, now).** Friction-conditioned forward **CAR** on the
  underlying. Gradeable today on EDGAR + FINRA SI + XBRL float + bars. FAIL ⇒ kill cheaply,
  never buy options data.
- **Stage 2 — net-of-implied-borrow gate (PAID, only on a Stage-1 pass).** Purchase historical
  options data (ORATS / OptionMetrics-class), back implied borrow out of put-call parity,
  recompute net edge for the **best defined-risk structure** (see §2.1). Only a Stage-2 pass
  authorizes capital.

**Pre-committed spend rule (freeze this, not the spend):** *a Stage-1 GREEN/YELLOW pass on the
friction corner is the necessary-and-sufficient trigger to purchase historical options data
for Stage 2.* Pre-committing the rule (not the dollars) is what keeps Stage 2 from being a
post-hoc rescue of a dead signal.

### 2.1 Structure is a free variable (why net≈0 is not a foregone conclusion)
"The edge lives where options are most expensive" is *expression-dependent*. You pay the
borrow only if you **buy the dear leg**. Borrow-skew makes calls cheap relative to puts in the
same name, so a defined-risk bearish structure built to be **short the dear leg** (e.g. bear
*call* spread) *collects* part of the skew rather than paying it (long put). Stage 2 measures
net edge for the **best defined-risk structure**, not the naive long put — exactly the degree
of freedom guardrail §3 (defined-risk only) already forces. Second reason net≈0 is not
foregone: in HTB / low-float / thin-option names the **option market is itself frictioned**
(wide spreads, thin OI), so put-call parity binds *loosely* — the same limits-to-arbitrage
that preserve the stock drift also prevent the option market from fully repricing it.

---

## 3. Event definition

- **Trigger:** a `424B5` filing (prospectus supplement for a takedown off an effective shelf —
  the canonical "secondary offering" event). Timestamped by `acceptanceDateTime` (already the
  convention in `data/filings.py`), so no intraday lookahead.
- **Optional inclusion `⟨decide at freeze⟩`:** `424B3`/`424B4` (other prospectus forms). Default
  v1 = **424B5 only** (cleanest takedown semantics; B3/B4 mix in resales/IPO-related prospectuses).
- **Classification (best-effort, from the document):** primary (dilutive, company issues new
  shares) vs. secondary (selling holders) vs. ATM/shelf-refresh. Default v1 conditions on the
  *union* and reports the split; subtype-conditioning is a documented v1.1 knob.
- **Deal size (secondary conditioner — see §5, risk-flagged):** shares offered × offer price,
  scaled by ADV₂₀ and by shares-outstanding (supply-shock magnitude). Extracted from the
  424B5 primary document. **This is the hardest extraction in the build** (free-text prospectus,
  heterogeneous HTML). Pre-committed fallback: if audit recall < `size_min_recall ⟨decide⟩`,
  **drop size-conditioning for v1** and let friction (§5) carry the gate; size returns in v1.1.

---

## 4. Universe — broad, event-driven, survivorship-clean

- **Not the 67 thematic names.** A flow edge has no reason to be thematic; restricting to the
  thematic cluster reimports the correlated-draw power problem that hurt divergence (one risk-on
  beta blob). **This is a deliberate product pivot** (named in §11): FSSD reuses the harness but
  is a deterministic event-driven flow strategy with the council demoted to a forward-only
  overlay (§9) — not the AI-council thesis system the SPEC set out to build. Worth doing; named
  as such.
- **Enumeration (survivorship-clean):** build the event list from **EDGAR daily index files**
  (every filing's form + CIK, free), filtered to 424B5 over the window — so we catch issuers
  that *later delisted*, not just today's survivors. Resolve CIK→ticker as-of the event;
  require daily bars to exist (else drop, recorded in the audit).
- **Eligibility:** reuse the backtest floor (`min_price`, `min_adv_usd`) for tradability.
  Optionability/spread cannot be known point-in-time historically, so it is **proxied** by
  *current* optionability + the price/ADV floor and declared an approximation (same honesty as
  the divergence option-floor split).
- **Window:** explore + lockbox per §10.

---

## 5. Conditioners (the corner)

All point-in-time observable at the event date.

- **Friction composite (primary conditioner)** — higher = harder/costlier to short:
  - short interest as % of shares-outstanding (FINRA SI ÷ XBRL shares-out) — *new ingest*;
  - inverse float (XBRL shares-outstanding; smaller = tighter) — *new XBRL concept*;
  - inverse ADV₂₀ and inverse price level (`data/market.py`, exists).
  - Combined as a pre-registered z-scored sum `⟨weights decided at freeze⟩`; **deciles formed
    from a TRAILING (rolling) cross-section, not full-sample**, to avoid lookahead in the
    breakpoints. Honest caveat: SI%-of-shares-outstanding ≠ SI%-of-*free*-float (free float is
    not freely available); declared approximation.
- **Deal-size (secondary conditioner, risk-flagged §3).**
- **FINRA SI timing:** SI is bi-monthly; use it **as-of its publication date**, never the
  settlement date (publication lags settlement by ~8 trading days) — else lookahead.

**Core hypothesis:** forward CAR is most negative in the **high-friction** (and, if size
survives audit, **high-deal-size**) corner; near zero in the low-friction corner (arbitraged).
Reported as a friction×size decile grid.

---

## 6. Metric, resampling, gate bands

- **Metric:** forward **CAR** = raw return − β·SPY over horizon h, β from `market.beta`.
- **Primary statistic:** mean forward CAR of events in the **high-friction corner**, as a
  **monthly series** (one observation per calendar month = the resampling unit). This is how
  the clustering objection is honored in the math: 30 offerings in one month count as ~one
  draw, not 30. CI via the existing circular **block-bootstrap** (`backtest/metrics.py`,
  reused) at **Bonferroni α = 0.05/k**.
- **Direction:** pre-committed **bearish** (forced supply → negative CAR). A *positive* corner
  CAR is not a win — it is a sign-flip that fails the directional pre-commitment.
- **Primary horizon (ONE, pre-committed):** **h = 10 trading days** `⟨operator may override
  before freeze⟩`. Supply overhang distributes in days–weeks — faster than the 21td divergence
  clock. Sweep {3, 5, 10, 21} reported as **diagnostic only** (not gated), as divergence did.
- **Bands (in net-edge terms, the §2 lesson):** thresholds set on **CAR magnitude net of an
  assumed cost stub** at Stage 1, and on true net-of-implied-borrow at Stage 2.
  `⟨band thresholds decided at freeze⟩`. FAIL / YELLOW / GREEN, same ladder as the divergence
  gate. A Bonferroni CI spanning 0 ⇒ INCONCLUSIVE-ITERATE within budget, not "thesis dead"
  (same semantics as `metrics._verdict`).

---

## 7. Controls (plumbing falsifiers, reused discipline)

- **Null control:** randomize each event's date *within its own name's trading history* (keep
  the name, destroy the event-timing). The friction-corner drift **must vanish**. If it
  survives randomization, we are measuring a friction *characteristic* (e.g. small-illiquid
  names just drift down), not the *event* — and the result is void.
- **Positive control:** the documented **unconditional** post-424B5 drift must appear at modest
  magnitude across the full event sample. If even that is absent, the event detection / CAR
  plumbing is broken (directly analogous to the divergence momentum positive control IC≈+0.10
  that proved the harness wiring was live).

---

## 8. Eligible-N audit FIRST (the stop-before-gate)

Before *any* CAR is computed (coverage orthogonal to performance, like `engine.audit`):

- count 424B5 events over the window;
- × distinct **calendar months** (the true power denominator under monthly resampling);
- × the **friction ∩ optionable ∩ tradable-spread** intersection (the corner that actually
  matters — audit *that*, not the raw event count);
- report deal-size extraction **recall** (decides whether size-conditioning survives, §3);
- report FINRA-SI and XBRL-float coverage of the event names.

**Pre-committed stop:** if the friction-corner event count is below `n_min_months ⟨decide⟩`
distinct months, the test is **underpowered → stop before the gate** (do not spend a k-round).
**Honest prior:** borrow-in-the-puts (§2) + optionability (§4) frictions could hollow the
profitable-*and*-tradable corner to near-empty. That would be a cheap, honest finding —
unlike everything before it, FSSD fails *gradeably*, on a mechanism with a real reason to exist.

---

## 9. The seam (Layer 1 deterministic / Layer 2 council — hard boundary)

- **Layer 1 (this pre-registration):** deterministic forced-supply × friction core, harness-
  graded, two-stage (§2). This is the only layer that can authorize capital.
- **Layer 2 (council, forward-only):** sharpen — distributed-vs-overhang, distress-vs-
  opportunistic, primary-vs-secondary nuance — scored **forward by Brier + contribution**,
  never historically (guardrail §6). Additive overlay on a *validated base rate*.
- **The boundary is hard:** the backtest validates the base rate; forward Brier validates the
  overlay; **they never cross.** Capital may ride Layer 1 alone; Layer 2 earns capital only
  after forward scoring proves contribution. This is what makes the user's requested
  "art-and-faith" hybrid *responsible* rather than a §5 violation: faith is an enhancement on a
  proven mechanical base rate, never the sole edge.

**Falsifiability of the hybrid itself:** the hybrid is real **iff** the friction-conditioned
Layer 1 clears Stage 1. If even the conditioned core grades clean-zero, there is no hybrid —
only pure faith, which §5 forbids as a sole edge. The harness exists to settle exactly that bet.

---

## 10. Lockbox / explore split

- **Explore:** 2019-01-01 → 2022-12-31 (build, iterate, consume k-rounds here).
- **Lockbox:** 2023-01-01 → 2024-12-31, looked at **exactly once**, after Stage-1 explore is
  frozen. A bare lockbox pass is weak-confirmation/veto only — it does not upgrade a band
  (identical semantics to the divergence lockbox, which was never opened).
- `⟨split is a proposal; decide at freeze.⟩` Rationale: 2019–22 spans the 2021 issuance boom
  and the 2022 bear (regime variety in-sample); 2023–24 is the held-out confirmation.

---

## 11. Pre-committed decisions + open items

**Pre-committed (CONFIRMED at FREEZE-A 2026-05-31):**
- Direction = bearish. ✓ locked
- Primary horizon = 10 td (sweep {3,5,10,21} diagnostic). ✓ locked
- Resampling unit = calendar month; Bonferroni α = 0.05/k. ✓ locked
- Event = 424B5 only for v1. ✓ locked
- Friction is the primary conditioner; deal-size is secondary and audit-gated (min_recall 0.70). ✓ locked
- Spend rule: Stage-1 pass ⇒ buy options data for Stage 2. ✓ locked
- Product pivot to broad event-driven universe, council demoted to forward overlay — **accepted**. ✓ locked

**Open items `⟨decide at freeze⟩`:** B3/B4 inclusion · friction-composite weights · size_min_recall ·
n_min_months stop · band thresholds (net terms) · lockbox split · cost-stub for Stage-1 net bands.

---

## 12. Honest priors / kill conditions

- **Most likely cheap death:** §8 audit shows the friction ∩ tradable corner is too thin →
  stop, no k-round spent. Acceptable and informative.
- **Second most likely:** Stage-1 gross corner CAR is real, but Stage-2 net-of-implied-borrow
  ≈ 0 (the borrow is in the puts). Mitigated — not eliminated — by structure choice (§2.1).
- **Sign-flip / squeeze (FREEZE-B #2):** the high-friction corner *is* the short-squeeze setup
  (high SI%, low float, hard-to-borrow), so a secondary there can drift down (supply wins) *or*
  rip up (the raise de-risks the company; shorts cover) — the sign is *most unstable exactly
  where the thesis concentrates*. The frozen single **bearish** test is the fragile choice; at
  FREEZE-B, replace it with a pre-registered **per-friction-decile signed-CAR + dispersion grid**
  (estimate + CI per decile under the existing Bonferroni) rather than re-fishing a flipped sign.
- **The win condition is narrow and that is the point:** forced supply ∩ high friction ∩
  tradable options ∩ net-of-borrow-positive. If that set is non-empty and clears bands, it is a
  *mechanically-justified* edge — the first in this project to fail-or-pass on the harness
  rather than dying ungraded.

---

## 13. Build inventory (reuse vs. new) — maps to the build plan

**Reusable (the durable harness — the actual asset):**
- point-in-time cache + as-of/lookahead tripwire (`data/cache.py`);
- block-bootstrap CI, Bonferroni-k, residualization, bands (`backtest/metrics.py`);
- CAR primitives: `market.forward_return`, `market.beta` (raw − β·SPY);
- EDGAR CIK resolution + full-history submissions (`data/filings.py`);
- XBRL companyfacts pipeline (`data/fundamentals.py` — clone for the shares-out concept);
- audit-before-gate pattern, explore/lockbox + config-hash freeze (`backtest/run.py`).

**New (the FSSD-specific surface):**
1. **EDGAR daily-index enumerator** → survivorship-clean 424B5 event list (CIK + acceptance ts).
2. **424B5 deal-size/subtype extractor** (highest-risk; recall-gated per §3).
3. **FINRA short-interest ingest** (bi-monthly, free; as-of publication date).
4. **XBRL shares-outstanding** concept (clone `fundamentals.py` extraction).
5. **Friction composite** (z-scored, trailing-decile breakpoints).
6. **Event-study engine mode**: event-aligned CAR, friction×size binning, **monthly** resampling
   onto the existing bootstrap; null + positive controls.
7. **`fssd` config block** (frozen params) folded into the gate hash.

**Build order:** freeze prereg → (1)+(3)+(4) ingests → §8 audit → *stop-or-go* → (2)+(5)+(6)
Stage-1 gate → *stop-or-go* → Stage-2 (paid options data). Audit gates the build spend; Stage-1
gates the data spend. One phase per session, in plan mode, each ending green.

---

## 13a. FREEZE-B flags (decide before the Stage-1 gate; before any CAR is computed)

Recorded now so they survive across sessions. They do **not** affect the §8 coverage audit
(no returns computed there), so setting them at FREEZE-B is not results-fishing — no k is burned.
- **#2 sign-instability** → per-friction-decile **signed-CAR + dispersion grid**, not a single
  bearish test (see §12). Direction may be relaxed from frozen-bearish to signed-by-decile at B.
- **#4 friction reweighting** → the FREEZE-A composite equal-weights SI% with three *collinear
  illiquidity* proxies (inverse float/ADV/price), making it mostly a *smallness* score and
  diluting the actual **short-sale-cost** signal to ¼ weight. At B, lean the composite toward
  the borrow dimension (SI% / days-to-cover), using the §8b-measured input cross-correlation as
  the empirical input. If the conditioned core underperforms at Stage 1, this dilution is the
  first suspect.

## 8a result (recorded 2026-05-31) — RAW population PASS

Survivorship-clean enumeration from EDGAR quarterly full-index (`data/edgar_index.py`):
**16,442 424B5 events · 3,309 distinct issuers · 72/72 calendar months** over 2019–2024
(≥ `n_min_months`=24). Plumbing confirmed (GameStop's three 2021 ATM equity offerings present).
**Caveat:** this is the raw 424B5 *superset* — includes debt/preferred/baby-bond/closed-end-fund
prospectuses, not only common-equity secondaries. The equity-secondary thesis subset is far
smaller and is isolated in §8b (equity bars + price/ADV + optionability + friction corner).
8a clearing 72/72 months means raw power is not the constraint; **whether the tradable corner
clears 24 distinct months is the binding §8b test.** No CAR computed; no k consumed.

## 8b result (recorded 2026-06-02) — friction corner POWERED, but borrow-tax huge

Full pre-registered **explore window 2019-01-01 → 2022-12-31**, online (current option chain for
the tradability ceiling). Funnel: **11,579 raw 424B5 → 1,459 equity-eligible** (3,826 dropped =
no current ticker / delisted — the survivorship cost, *counted*; 3,220 no bars; 3,074 below the
price/ADV floor = the debt/preferred/CEF superset). Friction corner (top 20%): **292 events over
29 distinct months**; with a current tradable near-money put: **139 over 28 distinct months ≥ 24
→ PASS.**

**RESULT: PASS — the friction ∩ optionable ∩ tradable corner is powered** (28 ≥ 24 months).
Stage-1 CAR gate is justified. *But three findings temper it, and all three feed FREEZE-B:*
1. **The borrow-in-the-puts tax is enormous: median near-money put bid/ask spread ≈ 52%**
   (range 6%–188%) on the corner. This is a *current-snapshot ceiling* (best case; historical
   was almost certainly worse), and it is a loud prior that **Stage-2 net-of-implied-borrow may
   be ≤ 0 even if Stage-1 gross CAR is real.** The two-stage spend gate exists precisely to find
   this cheaply — do not buy options data until Stage-1 gross passes.
2. **Friction composite is partly a smallness score (FREEZE-B #4 confirmed):**
   `corr(si_pct, inv_float) = +1.00` (both ∝ 1/shares-out, nano-cap-tail-dominated), while the
   short-sale-cost dimension (si_pct, days-to-cover) is nearly orthogonal to the illiquidity
   proxies. → at FREEZE-B, reweight toward SI/days-to-cover so the corner measures *borrow
   friction*, not just *small*.
3. **Subtype split (XBRL Δshares-out): primary 154 / secondary 78 / unknown 11** — i.e. ~53% of
   the corner is *dilutive* (true new supply), ~27% pure selling-holder distribution. Deal-size
   recall 83% (prospectus 76% / XBRL-delta 83%) ≥ 0.70 → **size-conditioning survives to v1.**

Diagnostics healthy: float coverage 1,443/1,459; serial-diluter HHI 0.005 (479 distinct names,
top-name 3% — not repeat-issuer-dominated); SI staleness median 10d (the ~bi-monthly+lag cost,
as expected). No CAR computed; no k consumed — this remains a coverage gate.

## 14. Freeze record

- **FREEZE-A (audit scope) — FROZEN 2026-05-31.** `fssd` config hash:
  **`76587407f824a0bd`** · k consumed: **0** (the §8 audit is coverage-only and consumes no
  k-round). This freezes everything the §8 eligible-N audit depends on: event = **424B5 only**,
  primary horizon = **10 td** (sweep {3,5,10,21} diagnostic), direction = **bearish**,
  resampling = **calendar month**, friction inputs + corner quantile (0.8), explore 2019–22 /
  lockbox 2023–24, deal-size `min_recall` = 0.70, audit `n_min_months` = 24.
- **FREEZE-B (Stage-1 gate) — PENDING.** Stage-1-gate-only params remain placeholders until set
  *before the first CAR is computed*: `stage1_bands` (net-of-cost thresholds + `cost_stub_bps`)
  and the *final* friction `weights` (equal for the audit). Finalizing these consumes no k by
  itself; the **first Stage-1 gate run is k=1**.
- Status: **FROZEN for the audit.** The §8 audit may now run. No Stage-1 gate run is valid until
  FREEZE-B is recorded here.
