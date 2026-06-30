# PREREG — Universe curation as a refresh rule (lower-priced, cap-fitting thematic names)

**Status: FROZEN 2026-06-09 (operator-merged — the merge is the freeze act).** Written **blind**: no
candidate had been screened against these criteria at freeze; the criteria are committed before any
name is looked at (the anti-HARKing firewall, cf. the divergence/FSSD graves and
`PREREG_COUNCIL_GATE_SEPARATION` — "CGS" below). The three at-freeze operator picks, recorded:
**§3 = quarterly windows + tag-only exceptions; §5 target = ~1 viable entry/month; §7 = resolution
(a)** (the event-provider wiring is the next session; the §5 sizing clock counts only scans on the
final funnel configuration).

Converged over two relayed advisor red-team rounds (2026-06-09); the multiplicative-funnel framing —
expected entries ≈ Σ names × P(surface) × P(framer) × P(council ≥MODERATE) × P(gate-cheap) ×
P(cap-fit) — is the advisor's, adopted.

## 1. Motivation (the demonstrated binding constraint)

The live universe (16 liquid mega/large-caps) is structurally un-enterable under the frozen risk
frame: one 25%-OTM 180–365d contract runs **$2.9k–$8.1k vs the $1,000 per-name cap** — at L1 #111
(2026-06-09) the first-ever gate-pass (RKLB, iv/rv 1.066) died at the cluster cap ($2,866/contract >
$2,000 budget); the read-only cap check found the one thesis-survivor (GEV) blocked at
$8,125/contract, and every cap-fitting gate-cheap name a thesis-reject (CGS §10.5). The cap is
frozen and is NOT raised (§7 of CGS; the cap-vs-contract-granularity question is out of scope, §9).
The fix attacked here is the **universe**: curate lower-priced unloved thematic names
("copper-not-rockets", NNE-type) whose far-OTM contracts (~$150–900) actually fit, into the
operator-authored discovery scan baskets `config.universe.themes`.

**The hard seam is unchanged** and `config.universe._comment` already sanctions the process:
"operator authors them, optionally LLM-assisted OUTSIDE the loop." The basket lands only by
operator-authored config edit; discovery surfaces on its existing floors; the council judges; the
deterministic gates dispose. **No gate / cap / floor / mandate / conviction threshold is touched by
this pre-reg.**

## 2. Criteria — the thesis/feasibility split (the anti-HARK core)

- **Thesis = operator-only.** Secular theme; second-order / under-narrated expression. Never
  delegated to the apparatus.
- **Feasibility = deterministic screen, EXISTING floors only — no new thresholds invented:**
  1. one contract of the selected 25%-OTM 180–365d structure ≤ **$1,000** (the frozen per-name cap,
     measured on the real chain via the production `select_structure` + `convexity_position_size`);
  2. a listed tenor exists in **180–365d**;
  3. two-sided far-OTM quote; spread ≤ the live eligibility **25%**; OI ≥ **50 (when present)**
     — matching `structure.py:contract_eligible` (the OI floor is informational where the chain
     reports no OI; window #1's was vacuous cohort-wide [every 6/9 name `OI: n/a`], UROY = N=1
     logged toward a future-window decision on tag-flagging OI-absent admissions as
     marginal-liquidity) [§2.3 reconcile, frozen 2026-06-22 with the dual-read close-out];
  4. price ≥ **$3**; ADV ≥ **$3M** (SIP) — the existing `universe.py`/discovery floors.
- **Info columns (pure arithmetic, NEVER selection thresholds):** cluster-budget fit ($2,000);
  **achieved OTM% + neighbor-strike interval** (low-priced chains have coarse strikes;
  `select_structure` snaps to the nearest listed strike, and a basket whose achieved structure sits
  far from the calibrated ~25% cell is a **different payoff object** — calibration finding #3 makes
  moneyness first-order; recorded so curation happens with eyes open); **half-spread as % of
  premium** (round-trip cost drag, paid again at the 21-DTE time-stop sell; material on the smallest
  contracts).
- **FORBIDDEN as curation criteria** (named): **IV/RV cheapness** (reverse-selection toward the
  gate — CGS §7); **momentum / rv_slope in either direction** (gaming the motion funnel, either to
  surface or to look quiet); **any LLM-set risk-relevant label**. The screen outputs **no cheapness
  column and no motion columns**.
- **Gate-IV provenance, pinned now so no post-hoc anchor choice can arise:** the IV gate consumes
  the FEED's published per-contract IV (`OptionsSnapshot.implied_volatility`), fail-closed when
  missing (PREREG_THEMATIC_CONVEXITY §4). There is **no in-house IV computation** anywhere in the
  gate path, and none may be introduced (e.g. to rescue a marginal wide-quoted small-cap wing)
  without its own pre-registration.

## 3. The refresh rule — the universe is a flow, not a hand-list

Addition TIMING is the HARK vector an additions-only rule leaves open: an operator notices names
when they move or make news, so ad-hoc additions are a low-bandwidth momentum signal entering
through the sanctioned seam (and the 3B/shares null books inherit the timing). Therefore:

- **Fixed calendar edit windows** — **quarterly** (proposed; **OPERATOR PICKS AT FREEZE**). Each
  window: re-pull the §4 seed sources → re-run the §2 screen → operator curates **additions** →
  dated `config.universe.themes` edit + the screen output committed as the window record.
- **This pre-reg's PR-B is window #1.** Dated honesty note: window #1's operator-suggested names
  (e.g. NNE) predate this rule and were noticed through the ordinary narrative channel; there was no
  prior record to HARK against — clean, and said explicitly.
- **Out-of-window additions** are permitted only as **dated, documented exceptions, tagged per-name**
  (config `_comment` + the screen record), so the surfaced-vs-control and 3B reads can be computed
  with and without exception names. (Stricter alternative — exceptions commit any time but become
  scan-eligible only at the next window open — **OPERATOR PICKS AT FREEZE**; the tag-only variant is
  recommended: an exception exists because of urgency, and the tag preserves auditability.)
- **Removals stay frozen-frame-grade** (an operator-authorized dated amendment, never routine):
  basket **membership ≠ enterability**. A name that rerates out of cap-fit STAYS in the basket — a
  scan list costs nothing and throughput is bounded elsewhere (§9) — and simply fails cap-fit at
  entry time. Pruning it would be an outcome-correlated removal, which the fixed-basket
  maturity-gate rule forbids (3B/shares null integrity). The window screen **records** fit drift; it
  never acts on it.

## 4. Sourcing hierarchy (the fourth anti-quietness instance, named)

An LLM recalls names roughly in proportion to text written about them — free recall samples the same
corpus consensus comes from (the fourth instance of the anti-quietness pattern, after the motion
funnel, news-grounding, and framer survivor-bias). Therefore, **deterministic/structural sources
FIRST**, LLM free recall only as a supplement, and **every candidate carries a source tag**:

- small-cap thematic ETF / index **constituent files** (URNM/NLR, GRID, COPX-type);
- **10-K customer-concentration disclosures** (a small-cap naming a mega-cap as a >10% customer —
  mechanical second-order discovery);
- **FERC interconnection queues / NRC dockets** (grid + nuclear project pipelines);
- **SAM.gov / DoD daily contract announcements** (filing-named defense suppliers);
- operator reading / domain knowledge (tagged as such).

## 5. Empirical sizing — measured rates, a pre-committed target, and named ceilings

Universe N is sized from **measured per-stage rates**, never priors: the basket-quality stage funnel
+ `sentinel_candidates` give surface / framer / council / gate / cap-fit rates per stage (the
surface-reason split motion-vs-rv-vs-event is reconstructable read-only from the persisted
`markers` JSON vs the config floors — no schema change).

- **Target, pre-committed HERE (never set after the data): ~1 viable entry per month** (proposed —
  coherent with the frame: ~250d holds × 1/month ≈ 8 concurrent ≤ 15 slots; ~$1,000/month against
  the $10,000 book; **OPERATOR CONFIRMS/EDITS AT FREEZE**). A measured shortfall sizes the NEXT
  window's additions; it never loosens a floor, gate, cap, or the conviction threshold.
- **The read**: after **≥4 weekly scans counted only from the FINAL funnel configuration** (§7).
- **Measured quantities include slot-occupancy by cap-unfittable names**: of the ≤8 surfaced per
  scan, how many could not fit one contract under the per-name cap. Recent movers include
  just-rerated-out names, so the global top-K door can systematically fill with un-enterable names
  that still consume framer/council spend and `sentinel_max_slots` — this quantity decides how
  urgent §9(c)'s fit-aware door is.

## 6. Gate base-rate sweep — aggregate-only by construction (the §5 de-starver)

The §5 conditional chain (gate-cheap GIVEN surface→framer→council) will likely be unmeasured at the
read date (n≈0 downstream of a ≤8/week door). A **weekly read-only sweep**
(`scripts/probe_basket_gate_baserate.py`) therefore runs the production gate over the **whole
basket** on the **gate-of-record feed** (config `option_gate` — it tracks a future OPRA flip
automatically) and emits **basket-level aggregates ONLY**: n, gate-cheap count, veto-reason counts,
and the surfaced-subset fit count (§5's slot-occupancy). **Per-name results are sealed — never
written**: per-name gate-cheap visibility would teach which name-types pass the gate and
reverse-select window-#2 curation toward it — the CGS §7 channel reopened at curation time. The
sealing boundary, precisely: it covers **non-surfaced** names; surfaced names are already public in
the council/eval record. Sealing is a discipline boundary on the **recorded artifact** (the only
thing curation may consult), not cryptography. Run manually each week (Sundays, beside L0); wiring
it into L0 as a fail-soft step is deferred and named here so it isn't ad-hoc later.

## 7. Ordering dependency — §5 must measure the funnel we intend to run

The structural-filing leg of the disjunctive surface gate is **dormant live** (`orchestrator.py`
passes no `event_provider`; `has_event` is always False), yet it is plausibly the **highest-value
surface path for exactly this cohort** — 424B5/S-1 capital-raisers are small-caps, and the event leg
is the only quiet-compatible door (it fires without motion). Measuring §5's rates on a motion-only
funnel and then changing the funnel would stale the read mid-measurement. **Resolution
(recommended; OPERATOR PICKS AT FREEZE):**

- **(a) The event-provider wiring is pulled forward as the NEXT session** — its own small pre-reg
  (a non-authorizing funnel change; reuses the shelved FSSD EDGAR plumbing `data/edgar_index` /
  `data/prospectus` in exactly the sanctioned non-authorizing role; the FSSD grave does not bar
  this — the event is a surface trigger here, not an alpha claim). The **§5 measurement clock starts
  only once the funnel configuration is final** (motion + event legs live). Window #1 lands
  regardless — feasibility is funnel-independent; scans accrue to basket-quality from the first
  Sunday; they just don't count toward §5 sizing.
- **(b) Fallback** (if the event session slips or is declined): the §5 read is stamped
  **"motion-only funnel rates"** with a pre-committed re-measurement after the event leg lands.

Not bundled into this pre-reg's PRs (one phase per session; an event taxonomy/provider deserves its
own red-team).

## 8. Evaluation pre-commitment

The basket edit is judged by the **existing** instruments — the basket-quality report (surfaced /
framer-passed / traded / resolved per basket, controls as a separate baseline) and the null books
(3B/shares book the whole basket weekly; the real−3B bundled read) — **never by entry count**.
Honest expectations, stated now: this unlocks **enterability, not entries** (an entry still needs
surface → council ≥MODERATE [the OLD cheapness-aware council config until the CGS §5-gated re-arch
ships] → gate-cheap → cap-fit, on the same name); quiet names still won't surface (§7/§9); and **the
gate may correctly reject most of the new cohort** — far-OTM small-cap options are the most
systematically rich corner of the listed market, so a low gate-cheap rate on the new basket is the
gate **working**, not a separation failure and not grounds to touch a threshold.

## 9. Out of scope (named so they don't vanish)

- **Cap-vs-contract granularity** (the frozen risk frame): its own pre-registered, operator-authorized
  session — and only if a well-curated feasible universe still cannot fit (universe-first is the
  anti-HARK order; never raise a cap to force a name).
- **The §8 funnel re-target** (CGS §8) — three pre-dated notes for that session: (a) **per-basket
  top-K quotas** vs today's single global `scored[:top_k]` door (within-basket z tempers cross-basket
  magnitude domination, but the door is one and 8-wide per scan); (b) the **event-provider leg**
  (→ §7, recommended as its own next session); (c) a **fit-aware door** — deprioritizing names whose
  one contract can't fit before they consume slots is categorically different from
  cheapness-awareness (it selects on spot price / strike granularity vs a frozen cap, not on the
  gate's verdict, so it does not reverse-select toward gate-pass; its design question is that premium
  needs a chain fetch in the funnel vs a crude fetch-free spot proxy).
- **The §9 grounding leg** (CGS §9 — hand-seed/thin-news ungrounded drops).
- **`themes.json` hand-seeds** — deliberately NOT the vehicle for new names: hand-seeds ground on
  news, so thin names drop "ungrounded" (the FCX pattern); basket sentinels ground on markers.
- **Throughput ceilings** — `scan_top_k=8`, `sentinel_max_slots=6`, `council.max_candidates=12` put
  a hard ceiling on yield regardless of N; a much larger universe forces a pre-registered revisit.

## 10. Breadth-over-depth geometry (guidance, not thesis)

The near-entry binding constraint is the **per-cluster cap**: $2,000 = at most 2 full-size names per
cluster, and the $10,000 book needs **≥5 independent clusters/unclustered groups** to fill. Two
cap-fitting names in uncorrelated themes are therefore worth more than three in one; 4–5 thinner
baskets beat 2 deep ones. Each new name still requires a cluster-routing decision at edit time
(route to ≤1 cluster or documented-unclustered; the trailing-return correlation diagnostic remains
the report-not-gate backstop). Thesis calls remain the operator's.

## 11. AMENDMENT (2026-06-10, operator-authorized) — rule-based admission: the picks become a RULE

**What this amends, with the original visible.** §2 froze "Thesis = operator-only … Never delegated
to the apparatus" and §3 froze "operator curates **additions** within the window." This dated
amendment moves the operator's judgment one level up — from picking names to **authoring the rule
that picks names** — because operator noticing is itself narrative-correlated (names get noticed
when they move or make news: the same bias §4 names for LLM recall). Thesis authorship remains
operator-only at the **theme** level (Rule 0); per-name selection becomes mechanical (Rule 1); the
operator's per-window act becomes **veto-only** (Rule 3). Converged over two further advisor
red-team rounds (2026-06-09/10); the four design calls were operator-confirmed 2026-06-10:
**achieved-OTM band 15–35% · a new `nuclear_fuel` cluster · the operator-named-but-tagged channel
kept · veto-only review.** Per-name thesis judgment lives where it always did — the framer and the
council (forward-scored), with the gate and caps disposing.

- **Rule 0 — the THEME REGISTER (`universe_register.json`, committed, never loaded by the loop).**
  The recorded hypothesis layer. Each theme = key · falsifiable thesis statement · falsifier ·
  **named deterministic sources** (constituent files, filing queries — fetch-dated) · a **default
  cluster routing** · a **provenance tag** (`operator` now; `generated` reserved for the future
  generation layer, `PREREG_THEME_GENERATION_STUB.md`). Register changes are dated operator
  amendments. The register also carries each window's per-name admission record (the auditable
  trail).
- **Rule 1 — mechanical admission, each quarterly window.** Basket(theme) gains every name that is:
  in the theme's named sources ∩ US-listed optionable (the screen pulls a live chain and selects a
  structure) ∩ §2 feasibility (one contract ≤ $1,000 + the existing price/ADV/spread/tenor floors)
  ∩ **achieved OTM within 15–35%**. No human picks. **The band supersedes, for automated admission
  only, §2's "achieved OTM% … never selection thresholds"** (original visible above): without it a
  rule admits names whose chains cannot express the strategy — recorded motivation from the
  window-#1 screen: IE "fit" at $440 with an only-eligible contract 30% **ITM**; LTBR/ITRI achieved
  ~9% (near-ATM, a different payoff object than the calibrated ~25% cell); DRS 37% overshoot. The
  band is a structural-integrity check in the same class as "a 180–365d tenor exists" — the
  cheapness and motion prohibitions remain absolute and the screens still output neither.
- **Rule 2 — additive only.** A name leaving a source list does NOT leave the basket (ETFs drop
  names after crashes/acquisitions — mechanical removal would be the outcome-correlated pruning §3
  forbids). It is tagged `source-departed, retained`. Removals stay manual, dated,
  frozen-frame-grade (§3 unchanged).
- **Rule 3 — operator review is veto-only.** The window's mechanical admission DIFF is reviewed;
  exclusions need a dated reason and are **tagged** so surfaced-vs-control and 3B reads compute
  with/without them (the §3 exception-tag pattern, applied to vetoes). Operator-NAMED additions
  remain permitted but tagged (the NNE channel) — the tag is what lets the record answer whether
  the named channel earns its keep.
- **Rule 4 — mechanical cluster routing.** New admissions inherit the theme's `cluster_default`
  (the map stays deterministic and operator-owned — the cap never keys on anything LLM-set);
  re-routing and cross-cluster migrations are dated operator amendments recorded in the register;
  the trailing-return correlation diagnostic remains the backstop.
- **Rule 5 — thesis-premise-currency check (gate; 2026-06-30 amendment; between Rule-1 feasibility
  and admission).** Before a theme's names are admitted, a **current-state pull** (latest filings +
  trailing news/coverage) must confirm the thesis premise is **presently true**: (a) the named
  narrative/mechanism still holds — not exited, faded, or inverted — and (b) the name(s) remain
  **attention-displaced** (thin coverage, not the loud leader / battleground / meme). A failed
  premise → **drop or re-thesise, never an automatic pass.** This is orthogonal to Rule-1 feasibility
  (which tests tradeability, not currency) and to the council's `under_narrated` read (which only
  judges what reaches it) — a pre-admission gate so a stale-premise name is caught by the **funnel,
  not by luck**. The cheapness/motion prohibitions are unchanged: the pull verifies the THESIS is
  current and the name is QUIET, never that it is cheap or has moved. **Proof-of-need (2026-06-30 —
  every name passed Rule-1 feasibility, every name dropped here):** AUR (already multi-lane → the
  "single-lane pilot" premise pre-falsified); ERII (CO2-refrigeration wound down + desal guidance cut
  → premise inverted); ALTM/WBA (delisted / taken-private at the revulsion low); SEDG/WBD (turnaround
  already priced, +85%/+170% off the bottom). Three demonstrated catch-types — **mechanism-stale,
  name-delisted, thesis-already-priced**. See `records/2026-06-30_premise_currency_check.md`.

**Disclosure tiers, clarified (binds the future generation layer).** The §6 sweep's per-basket
aggregates are pinned OPEN at the operator tier (per-basket = per-theme; the frozen §6 already says
curation may consult them). Any future theme GENERATOR sees **nothing gate-derived at all** — not
the aggregates, only dormancy flags (see the stub) — else theme-level reverse-selection reopens the
CGS §7 channel one floor up.

**Window #1 is this rule's first mechanical run** (the §3 honesty note stands: the operator-named
NNE predates the rule — and was subsequently also verified as an NLR constituent). The admission
record lives in the register; the screen output is committed under `records/`.
