# PREREG_THEMATIC_CONVEXITY.md — Thematic Cheap-Convexity Inflection Trading

> **Pre-registration.** This document is the operating contract for the thematic
> cheap-convexity strategy. It is frozen **before any signal/gate code is written**
> (T0). The risk frame, the eligibility gate, and the IV / cheap-convexity gate — with
> their thresholds — are fixed here. Code reads these parameters from `config.json`; the
> *structure* of the gates is fixed by this doc.
>
> **This is NOT a backtest pass/fail gate.** A 6–12-month hold cannot reach statistical
> significance in tolerable time, and the LLM council can never be backtested (guardrail
> §6). So the discipline shifts: we **pre-register the risk frame and the gates, then
> calibrate forward** — we do not "prove" an edge. The protection is bounded premium, hard
> deterministic vetoes, and a kill rule — not a backtest. See
> `dramatic-options-validation-methodology` (memory) §"How to apply".
>
> **Status: T0 — frozen. T1 (minimal paper loop) implements against this contract.**

---

## 1. Strategy (frozen definition)

> **Amendment 2026-06-01 — thesis framing clarified (no rule change to this sleeve).** The
> operator clarified the intent: buy the **mispriced far extreme** of an option (long-dated, far
> strike) whose price is wrong **if an anticipated trend changes**, and the long tenor is
> **runway** for that thesis, not a 6–12-month holding *commitment*. The natural reading is "exit
> when the mispricing corrects." For the **far-OTM sleeve this resolves to: keep holding the
> tail.** A calibration head-to-head (`PREREG_CONVEXITY_CALIBRATION` §4 amendment) tested a
> delta-trigger "exit-when-the-move-played-out" rule against hold-the-tail and graded it
> **EV-inferior on OTM**: it caps the convex tail you paid for (p99 ~14× → ~1.8× at δ=0.5) and
> raises the break-even hit-rate from **19% → ~50–68%** — and the GBM-no-jumps bias *favored* the
> early exit, yet it still lost. So the OTM book's edge **is** the fat tail; §6a exits below are
> **unchanged** (this is the hold-the-tail venture sleeve). The **reprice-capture** behavior the
> operator wants is a genuinely *different edge* (high-delta, no tail to forfeit) and is **deferred
> to a separately-pre-registered ITM sleeve** — its own financing/extrinsic gate (a skew test would
> mis-fire on ITM by put-call parity), its own reprice + invalidation exits — to be built once
> forward evidence warrants it (not on the GBM harness alone). See the v2 `IMPLEMENTATION_PLAN`.

1. Identify a secular theme at **inflection** — a real tailwind the market hasn't narrated
   yet, or a real headwind/rollover before consensus turns.
2. Express it with **long-dated (6–12 month), far-OTM, defined-risk** options (calls for
   tailwinds, put/bear structures for rollovers). Long options are inherently
   defined-risk: max loss = premium paid.
3. **The edge is the gate:** trade only when the option's implied vol is **NOT already
   pricing the theme** — the convexity is *cheap* ("copper-not-rockets"). A beloved,
   richly-priced theme is a pass however right the narrative.
4. Run a **portfolio of small convex bets**: most expire worthless, a few pay many-fold
   (venture-style payoff).
5. Discipline lives in **sizing and risk control**, not validation.

## 2. The hard seam — deterministic gates dispose; judgment only proposes

Code-enforced, non-overridable (Layer 1): the **IV / cheap-convexity gate** (§4),
**eligibility** (§3), **sizing / caps / book budget** (§5), the **kill rule** (§6).
Judgment (the council, T2+; hand-seeded in T1): *which* theme is at inflection, structural
vs. fad, the cleanest name, narrative ahead-of vs. behind fundamentals. Judgment is *input*
to a proposal that must still pass every deterministic gate. The council can be wrong; it
**cannot** buy expensive convexity, breach a cap, or defeat the kill rule.

## 3. Eligibility gate (frozen) — is the contract tradable for us?

Reuses `options_tradability.py`. A candidate contract must satisfy all of:
- Relative bid/ask spread `(ask−bid)/mid ≤ 0.25`.
- Open interest `≥ 50`.
- Per-contract price within `[0.10, 100.0]`.
- Underlying passes the `universe.py` filter (min price, min avg dollar volume,
  no leveraged ETFs).
**Fail-closed:** missing quote/OI/price → ineligible → no trade.

## 4. IV / cheap-convexity gate (frozen) — the edge, as a hard veto

**The problem (flagged at pre-registration):** "cheap" normally means low IV-rank /
IV-percentile versus the name's *own IV history*. **We have no historical options IV** —
chains are forward-only (see `dramatic-options-edge-toolkit` memory, "harness can't"
walls). So IV-rank is not computable today. We resolve this two ways:

**(a) Substitute the underlying's realized-vol history as the baseline.** Realized vol IS
computable — from the daily bars cache we already hold (point-in-time, no options history
needed). The variance-risk-premium framing answers "is vol expensive?" without an IV time
series.

**(b) Read the convexity price directly off the live snapshot** via the skew shape — the
specific wing we are buying.

The gate, computed from **one current chain snapshot + trailing realized vol**:

| Metric | Definition | Frozen threshold | Meaning |
|---|---|---|---|
| **IV/RV ratio** | `IV_atm / RV_h`, where `RV_h` = annualized realized vol over the trailing window (`rv_window_days`, matched toward tenor) | `≤ τ_ivrv = 1.2` | ATM vol isn't richly bid over what the name actually realizes |
| **OTM skew premium** | `IV(target wing strike) − IV_atm`, in vol points | `≤ τ_skew = 10.0` | the *wing we are buying* isn't already bid up, even if ATM looks calm |

**Pass ⇔ both hold.** Either rich → **veto** (defined-risk default; the council cannot
override).

**Fail-closed:** missing IV, ATM reference, wing IV, or insufficient bars for `RV_h`
→ treat as **NOT cheap** → veto. A gate that cannot be evaluated does not pass.

**Thresholds are frozen for the current forward cohort.** They live in
`config.json:convexity_gate` and are changed **only** by an explicit, documented operator
edit — **never** moved to justify a specific trade (no post-hoc gate moving).

**Accrue our own IV baseline going forward.** The point-in-time cache (`data/cache.py`,
immutable entries) is the mechanism: persisting each cycle's chain snapshot into it builds a
real IV history over months, after which the gate can **graduate** from the RV proxy to a
true IV-rank / IV-percentile. (T1 establishes the loop and the cache; wiring the per-cycle
snapshot write is the immediate next step. The graduation itself is a future,
separately-pre-registered change.)

Frozen values (T0): `τ_ivrv = 1.2`, `τ_skew = 10.0` vol pts, `rv_window_days = 252`,
tenor window `[180, 365]` days, `target_moneyness = 0.25` (≈25% OTM).

## 5. Risk frame (frozen) — FIRST-CLASS; the discipline

Operator decisions, set 2026-05-31, in `config.json:convexity_book`:

- **Convexity book = 10% of account** — the total premium-at-risk. The **only** money the
  strategy can lose; the other 90% is untouched.
- **Per-name cap ≤ 1% of account.** Per-theme cap = per-name for T1 (one name per theme).
- **Max concurrent positions = 15.**
- **Sizing = flat-by-slots, capped — NOT Kelly.** A far-OTM lotto Kelly-sizes to ~0 (low
  win probability); that is the wrong instrument here. Each shot gets a small, roughly
  equal slice of the book, capped at the per-name limit and never exceeding the book
  remaining. Aggression comes from convex *structure* and the *number* of small shots —
  never from size on an unproven view. No naked, no uncapped, no leverage-on-conviction.
- **Survivorship log.** Record **every** evaluated bet — eligible or vetoed, winner or
  zero — append-only. This is the only honest basis for ever judging edge vs. luck, and it
  counters the bias toward remembering the winners.

**Amendment 2026-06-03 — per-theme/cluster exposure cap (operator-authorized, §C-instance-cited).**
The per-name 1% cap treats every underlying as independent, so a basket of *correlated* names reads as
"diversified" when it is one bet. The first live discovery scan (2026-06-03) made this concrete: 7 of 8
surfaced sentinels were a single AI-capex-into-power bet (VRT/PWR/GEV/ETN datacenter power + CCJ uranium
+ RKLB/KTOS space-defense) spanning **two** scan baskets — at 1%/name they would have loaded **7% of the
10% book** into one trade the log would record as "7 diversified positions." This adds a **cluster-level
entry-premium cap**:

- **Cluster cap.** Aggregate **entry** premium-at-risk across a *correlation cluster* ≤
  `cluster_fraction` × account equity (`config.json:convexity_book.cluster_fraction = 0.02` = **2 full
  names** = 20% of book). It composes with the existing caps:
  `alloc = min(per_name_cap, book_remaining, cluster_remaining)`. Graduate to 0.03 only once **≥4
  clusters** are curated (two clusters at 0.03 = 60% of book in two correlated bets) — itself a dated
  re-amendment.
- **Cluster = an operator-curated, DETERMINISTIC `symbol → cluster` partition** (a name in **≤1**
  cluster), documented **by driver** so future names route correctly. It is **never** keyed on a
  theme/basket *label* (a sentinel's label can be set by the LLM framer; letting that move a risk cap
  would breach the §2 hard seam). Shipped: `ai_capex_power` (AI-datacenter power demand) =
  VRT/PWR/GEV/ETN/CCJ/CEG/NEE (CEG/NEE folded in, CCJ kept, **FCX dropped** — copper variance is
  diluted; a power/uranium ETF like URA would co-cluster); `space_defense` (defense/space budgets) =
  RKLB/KTOS. Overlap / `cluster_fraction < per_name_fraction` / a malformed map **fail closed** (raise
  at load); an **absent** map is inert (every name a singleton) — an optional additive control must not
  fail-closed-to-zero-trades on absence.
- **Direction-agnostic, no netting.** The cap sums premium-at-risk regardless of direction (defined
  risk: you can lose all of it); it does **not** net long/short — a netting model would need clean beta
  the free feed can't give. Clusters are curated to be directionally coherent; a mixed-direction cluster
  logs a non-fatal warning.
- **Committed basis (incl. pending).** The cluster cap counts `status IN (open, closing, pending)` —
  unlike the book cap's open/closing basis — so a same-cycle just-submitted (`DRY_RUN=false` resting
  limit, reconciled only in the monitor pass) mate is counted and a tight cluster cannot over-admit on
  its next mate the same cycle. The ~10-slot book absorbs that window; a 2-slot cluster cannot.
- **Gates new entries, never force-closes** a pre-cap over-budget cluster (mirrors §6). Applies
  **identically to the brain-off shadow book** (a deterministic cap; only the council selection differs).
  **Breach = an entry admitted in violation of the THEN-LIVE frame**, not "book currently within caps":
  each run stamps its frame version (`runs.frame_version`, migration 0009) and each cluster decision
  stamps the per-decision occupancy/cap/equity into the survivorship log, so the T4 breach audit
  recomputes within-cap-ness at the admission rather than trusting the enforcement code.

This only **tightens** the frame (the lowest-risk §5 edit) and makes no edge claim — pure concentration
risk-control. Converged over the operator's R2/R3/R4 plan red-team. *(Operator-authorized 2026-06-03.)*

## 6. Kill rule (frozen)

Halt **new entries** for human review if **either**:
- the book draws down **≥ 20%** of its premium budget, **or**
- the book **bleeds 9 months** with zero payoff.

Plus the always-on `KILL` file / env switch, checked every cycle (fail-closed). Open
positions are not force-closed by the kill rule; it stops *new* risk pending review.
Thresholds in `config.json:kill_rule`.

## 6a. Exit rules (frozen) — the L2 reflex, deterministic, no LLM

Open positions are marked to the current option mid each cycle and exited by **deterministic,
code-enforced** rules (`monitor.py`; SPEC §3 "open slow, close fast"). The intelligence is
front-loaded at entry; this loop only watches and fires. Rules (`config.json:convexity_exits`):

- **Profit-take:** close when the mark reaches **≥ 10× the entry premium** (a convex winner is
  realized rather than round-tripped).
- **Time-stop:** close when **≤ 21 calendar days to expiry** (avoid the gamma/theta endgame).
- **Expiry:** close at intrinsic; a far-OTM option that never came in → **−premium**, the
  expected zero (the venture payoff shape).

Realized P&L is recorded per close (the calibration substrate, §7). These thresholds are
frozen for the current cohort; changed only by a documented operator edit, never to rescue a
specific position. *(Added 2026-05-31, before live forward results exist.)*

**Amendment 2026-06-01 — profit-take raised 4× → 10× (operator-authorized, calibration-cited).**
The payoff-mechanics calibration (`PREREG_CONVEXITY_CALIBRATION.md`) showed the **4× cap clips
the convex right tail that is the entire point of the book**: at the live cell (25% OTM, 270d,
σ_entry = 1.2× realized) the capped p99 was ~4.5× vs ~10× uncapped, while the **mean barely
moved** (≈0.86–0.88× across drift scenarios — tail events are rare, so capping them costs almost
nothing on average but forfeits the many-fold winners the strategy is sized for). Above ~12× the
profit-take rarely fires (the 21-DTE time-stop takes over) and metrics converge. **10× sits just
before that plateau** — it still imposes profit discipline (realize a spectacular winner before
it round-trips, and before a far-OTM option that has gone ~10× has become a spent-convexity delta
bet) while recovering most of the tail. The protective **time-stop stays 21 DTE** (the
calibration showed it cuts P(total loss) ~72%→56% vs hold, by salvaging theta on losers).
*Caveat acknowledged:* GBM has no jumps, so the real catalyst-driven tail is fatter than modeled
— which only strengthens the case against an eager cap. This is a calibration of **structure**,
not an edge claim (the §1 walls hold). `config.json:convexity_exits.profit_take_multiple = 10.0`.

## 7. Forward measurement — calibration, not a pass-gate

Per bet, logged: theme, inflection thesis, IV-gate verdict + metrics, structure, size,
rationale, outcome, P&L. Tracked: hit rate, payoff distribution, premium-bled-vs-paid
(Brier + council contribution arrive with the council, T2+). **6–12-month holds mean
*years* to significance.** Forward data informs calibration, sizing, and the kill
decision — it does **not** prove an edge. A good run is not validation; a bad run is not
disproof until the kill rule actually trips.

## 8. Scope of this contract

T0 freezes §§1–7. **T1** implements the minimal paper loop against this contract
(hand-seeded themes → both gates → defined-risk structure → flat-by-slots sizing → logged
paper position + survivorship log). The council (T2) is built; **sentinels (T3) are in build —
PR1 (the deterministic discovery core) has landed.** T3 adds a discovery layer **upstream** of the
council and **changes no frozen gate**: it only widens the *candidate set*, and every discovered
candidate still faces the unchanged §3 eligibility + §4 IV gate + §5 sizing/caps + §6 kill. Its
prescreen thresholds are a candidate **funnel** (like eligibility), config-tunable, NOT
pre-registered frozen gates; **prescreen rank is a funnel, never a tradeable signal** (the reused
divergence plumbing is not a revived edge). *(The per-theme/cluster exposure cap foreseen here LANDED
2026-06-03 as the §5 amendment above — the `ai_compute`-style cluster made the per-name cap false
diversification on the very first live scan.)* Any change to a frozen
threshold or gate structure is a documented edit to this doc + `config.json`, dated, never retroactive.

---

*Frozen 2026-05-31, before signal/gate code (T0). — Dramatic Options*
