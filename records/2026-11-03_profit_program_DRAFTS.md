# 2026-11-03 — Profit program: DRAFT amendments → operator word given 2026-11-03

## Status after the operator's word (2026-11-03, in session: "Sure, let's do that. Let's follow your suggested steps
and get this implemented ASAP" — the order D0 → D4 → D3b → D1 → D3)
D0–D3 step 1 merged in rozavala/dramatic_options#411 (2026-11-03, DEV deploy green). D3 step 2 follows on the same
branch. Merging changes no live behavior: the telemetry items are read-only, and D1 and D3 are inert until their
config blocks are added.

| Item | State | What switches it on |
|---|---|---|
| D0 execution ledger | **built** (`execution_ledger.py`, dashboard Edge → Telemetry) | merge; read after 5 decided orders under carry-over |
| D4 IV history | **built** (`iv_history.py`; the sweep now writes `iv_term_snapshot` nightly) | merge; percentiles at 120 sessions (~early Dec), term/ΔIV after 21 sessions |
| D3b falsifier ledger | **built** (`falsifier_ledger.py`, `falsifier_specs.json`, L1 hook) | merge; **operator to confirm the five CC-encoded specs** |
| D1 ranked backfill | **built, inert** (`backfill.py`; PREREG_THEMATIC_CONVEXITY §5 amendment 2026-11-03) | a dated edit adding `convexity_book.backfill = {"enabled": true}` (the one `frame_version` boundary) |
| D3 verticals | **built, inert**: selector + probe (step 1); order path (step 2: `broker.submit_spread`, migration 0021, `paper_loop`, `monitor`, carry walk, shadow/3A/3B parity; PREREG §5 amendment 2026-11-03b) | the checklist below, then a dated edit adding `convexity_gate.vertical_for_over_cap = {"enabled": true}` |
| D5 step 1 capex cycle | **built** (`capex_cycle.py`; L1 writes one `capex_cycle` record per day from the corpus's XBRL capex; dashboard Edge → Telemetry) | merge; filing diff and per-cluster driver series are later D5 parts |
| D6 / D7 | drafts, not started | — |

**D3 switch-on checklist (in order):**
1. On DEV, run the paper multi-leg round-trip and paste its output into a dated record:
   `python scripts/smoke_order_roundtrip.py --endpoint paper --contract <long OCC> --limit <debit>
   --vertical-short <short OCC> --sell-limit <credit> --send` (pick the pair with
   `scripts/probe_vertical_feasibility.py`). It proves the account accepts multi-leg orders and records how the
   venue signs the net fill. The code sends positive prices and reads fills with `abs()`; Alpaca's docs could not
   be reached from the cloud session to confirm the credit sign, and neither reading can cost more than the
   natural price, but the round-trip is the evidence.
2. Before T4: confirm the live account's options approval level allows multi-leg (selling the short leg).
3. The dated enabling edit (`convexity_gate.vertical_for_over_cap.enabled = true`), which moves `frame_version`.
Known gap: the dashboard's positions table shows the long leg only (the short leg is on the row and in the
rationale).

---

**Original status: DRAFTS.** Nothing here was in force when written. Each draft names its boundary, its stamp and what the operator
decides. They follow the house pattern: telemetry before rendering, rendering before gating, one dated
record segment per change. Background: `records/2026-11-03_literature_review.md`; harness evidence:
`records/2026-11-03_calibration_v2_finding.md` (the v2 run under the blind 2026-11-03 amendment).

## The problem, in the record's own numbers
- The real book holds **1 of 15** slots (PL, ≈ −$686 on $690). Three above-floor verdicts since July
  (#508 07-10, HL 10-26, AG 10-29). The two October ones were submitted at 15:48 ET and cancelled unfilled
  at 16:00, before carry-over (#386) existed.
- Each council tightening cut volume: §10.11's first night was 0 of 12; `at_inflection=false` on 29 of 50
  strategist reads in W44.
- Expressible falls **39 → ~31** at the 11-23 tenor cliff unless Aug-2027 quarterlies list; nine names are
  over the $1,000 per-name cap (NVDA, LHX, LMT, CEG, NOC, ETN, VRT, PWR, GEV — most of `ai_capex_power` and
  `space_defense`).
- The 9-month dry-spell kill rule (`kill_rule.dry_months_halt = 9`) counts against a book that rarely enters.

With a skewed payoff (Bessembinder 2018), P(at least one big winner) is set mainly by the number of
independent shots. At an illustrative 5% chance per shot of a 10×: 1 shot ⇒ 5%, 15 ⇒ 54%, 30 ⇒ 79%.

---

## D0 — Measure fills under carry-over (execution telemetry; no frame change) — RECOMMENDED FIRST
**What:** a per-approval execution line: approved → submitted → filled (same day / carry day) → cancelled,
with limit vs mid vs ask at each step. Pages already exist (ORDER CARRIED / SUBMITTED / FILL / NOT FILLED);
this adds the ledger and a dashboard count.
**Read:** after the first 5 approvals under carry-over. If fewer than 4 of 5 fill, consider moving the L1
entry submit to the next session's 10:00 ET for every approval (not only carries). Execution-only;
`frame_version` unchanged.
**Operator decides:** go for the telemetry (no segment).

## D1 — Ranked backfill: let the gate fill idle slots from the council's ranking (frame change)
**Thesis:** the deterministic gate is the edge (Coval & Shumway: unconditional OTM buying loses; Goyal &
Saretto: low IV/RV options do better). The council's tri-criteria conjunction at ≥ MODERATE is the
throttle. Its value over brain-off is exactly what `null_hierarchy`'s "council (real − shadow)" step
measures, and that step has no matured data yet.
**Rule (draft):** when the real book has **≥ 10 of 15 slots empty for 4 consecutive weekly L0s**, the next
L1 may enter **one** backfill per week: the gate-cheap, expressible, coherence-passing name whose council
read has the **highest raw strategist conviction**, provided no criterion is judged *false* at HIGH or above
by the strategist. Flat-by-slots sizing, the per-name, cluster and book caps, the kill rule and the hard
seam are unchanged. Origin is stamped `backfill` so `real_by_origin` scores it apart from above-floor
entries.
**Why not just lower the floor:** a lower floor changes every verdict's meaning and segments the council
record. Backfill leaves the floor intact and adds one labelled, separately-scored entry path.
**Boundary / stamp:** `convexity_book.backfill = {enabled, empty_slots_min: 10, weeks: 4, per_week: 1}`
⇒ `frame_version` changes (the hash covers `convexity_book`). New segment.
**Stop rule (pre-stated):** suspend backfill if the `backfill` origin's running premium-bled fraction
exceeds the above-floor origin's by more than 25 pp after ≥ 8 backfill entries have ≥ 90 days of age.
**Operator decides:** adopt / adopt with different numbers / defer until the null hierarchy matures.

## D2 — Tenor fallback past 365 days — NOT DRAFTED (calibration v2 Rule T: NOT A CANDIDATE)
Rule T found 540 d worse than 365 d at zero drift (and 1.38× the premium), so it is not drafted as a
replacement. The cliff stands; the 11-23 read decides which names lose structure, as docketed. **Open
question for the operator:** Rule T did not test the narrower fallback ("540 or no bet when [180, 365] is
empty"). If wanted, it needs its own blind rule and run; the finding's reading 5 says why the existing
numbers don't settle it.

## D3 — Wide call verticals for over-cap names only (frame change; calibration v2 Rule V: CANDIDATE)
**Rule (draft):** a name whose cheapest eligible naked contract exceeds the per-name cap may be expressed
as a debit call vertical: long the gate-of-record wing (≈25% OTM), short the wing ≈ **+75% OTM** (the K₂
that passed Rule V: premium 0.71× naked, mean M 0.98× naked under jumps). Both legs must pass
eligibility, and the **long** leg must pass the frozen cheapness gate. Fails closed when either leg is
missing. Atomic combo orders only (the order-manager safety pattern). Bearish theses are out of scope
(put verticals were not calibrated).
**What it costs:** the tail. p99 falls from about 10.7× to 7.0×. Each vertical is a smaller jackpot, but a
shot the book otherwise can't take at all. That is the trade the Rule V bar was written for.
**Which names it reaches (11-01 Sunday quotes, provisional):** at 0.71× the naked premium, NVDA ($1,068 →
≈ $760) and LHX ($1,100 → ≈ $780) fit under $1,000; the most expensive (LMT, CEG,
NOC, ETN, VRT, PWR, GEV) need a fresh read.
**Boundary / stamp:** `convexity_gate.vertical_for_over_cap = {enabled, short_moneyness: 0.75}`, a
`frame_version` change and a new segment. Needs `structure.py` + broker multi-leg support, its own tests, and
the dual-read discipline before any live use.

## D3b — Forward falsifier-accuracy ledger (telemetry; from calibration v2 Rule S)
Salvage failed only on false-alarm cost at a = 0.7 and passed everywhere at a = 0.9. The deciding number
is the falsifier's real accuracy, which we can measure forward: each registered thesis has a dated
falsifier. **What:** record, at each falsifier deadline, fired / not fired, and later the name's realized
directional move at 250 bars. Report-only. A salvage rule is re-proposed only with a measured accuracy and
a fresh blind rule. Also suggests (finding reading 3): date falsifiers to the first quarterly print, not
the annual.

## Not drafted — house-money roll (calibration v2 Rule R: NOT A CANDIDATE)
The roll lowered P(M ≥ 1) by about 5 pp and did not raise mean M; it moves outcomes into the tail. The
§6a exits stand.

## D4 — Our own IV history: percentile, term slope, ΔIV (telemetry first; gate graduation later)
**Thesis:** Goyal & Saretto (IV vs RV), Vasquez (term-structure slope) and An, Ang, Bali & Cakici (ΔIV
predicts direction) all need option-side history, which we have accrued since T1
(`convexity_data.persist_chain_snapshot`, called from `paper_loop.py`).
**Step 1 (telemetry, no segment):** at each L1, for each slated name compute and store: the target wing's
and ATM's IV percentile within the name's own snapshot history (only with ≥ 120 trading days of
snapshots, else `null`); term slope = ATM IV at the longest listed expiry ≤ 550 d minus ATM IV at the nearest
expiry ≥ 30 d; 21-trading-day ΔIV for the ATM call and put. Dashboard panel; nothing rendered to the council,
nothing gated.
**Step 2 (later, its own frozen prereg):** the PREREG §4 graduation. Thresholds pinned **blind** from the
pass-rate distribution (as PREREG_CHEAPNESS_WATCH §2.1.8 did), never from outcomes.
**Operator decides:** go for Step 1.

## D5 — Deterministic driver evidence for names already slated (telemetry first)
**Closed-line check:** STANDING_STATE closes "the idea-supply automation line, incl. the
fundamental-acceleration feed" unless revived with a standalone thesis. D5 is **not idea supply**. It adds
dated evidence lines for names the council already reads, to answer the criterion it fails most (§10.11
`at_inflection`, name-level). The standalone thesis is DellaVigna & Pollet (distant forecastable demand is
under-priced) plus Cohen, Malloy & Nguyen (filing changes are ignored). The operator rules whether that
clears the closed-line bar.
**Three computed lines per slated name, dated, from sources we already hold:**
1. **Filing diff** (Lazy Prices): the share of the latest 10-Q/10-K's risk-factor + MD&A text that changed
   vs the prior same-type filing, plus the top added sentences. From the EDGAR documents the corpus already
   fetches.
2. **Capex cycle** (Greenwood & Hanson): cluster-level capex YoY and its acceleration from XBRL
   `PaymentsToAcquirePropertyPlantAndEquipment` across the cluster's members.
3. **Driver series:** one per cluster, operator-named, from existing pullers (EIA, BLS, USAspending,
   Comtrade); the value, its YoY change and its acceleration, with the source's publication date.
**Step 1:** compute and store, dashboard only. **Step 2:** render into the council pack — a prompt change,
new stamp, new segment, with the usual two-session tripwire.

## D6 — Narration meter + consensus markers (telemetry first)
**Thesis:** Hong, Lim & Stein and Fang & Peress (low coverage diffuses slowly); Da, Engelberg & Gao (attention
spikes mark late stage); Ben-David et al. (a thematic-ETF launch is a dated consensus marker).
**Lines:** analyst count (have, `analyst_v2`); 90-day news-count trend (Alpaca news, have); Wikipedia
pageviews 90-day vs 1-year ratio (**not reachable from the cloud sandbox; verify on DEV** under the reach-
channel charter before wiring); a thematic-ETF launch or holdings-add touching the cluster in the last
12 months (`corpus/etf_constituents.py`). Combined into a **stage label** 0–3 (dormant / driver turning /
fundamentals confirming / narrated), telemetry only.

## D7 — Council probabilities with a reference class (prompt change)
**Thesis:** Tetlock & Gardner; Satopää et al. (extremized aggregation); Schoenegger et al. (LLM ensembles
match crowds; role biases are real).
**Rule (draft):** each role adds `p_big_move` (probability the name makes the miss-ledger's big move, ≥ +50%
directional within 250 bars) and names its reference class. Labels and the floor are unchanged. Brier
is scored forward on the probabilities, and the extremized three-role aggregate is reported beside the
strategist's label.
**Timing:** the model refresh is planned ~11-12 (all roles, one segment). Bundling saves a segment but
confounds the two changes; separate is cleaner. The operator's call.

---

## Suggested order
D0 → D4 step 1 → D3b → D1 → D3 → D5 step 1 → D6 → D7. Telemetry items (D0, D4.1, D3b, D5.1, D6) change
no record segment and can start on a single word.
