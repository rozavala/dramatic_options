# 2026-11-10 — The kill rule's "9 months dry" leg: a conformance draft (#465, R1), and the drawdown leg's definition (#472)

> **Status: DRAFT for issue #465. Nothing here is in force.** The kill rule is frozen (PREREG_THEMATIC_CONVEXITY §6);
> it changes, or gains an operational definition, only by the operator's dated word. Merging this file ratifies
> nothing: merge-as-ratification is a named failure mode in this project (§6 ownership addendum, 2026-07-02). The
> entry texts in §6 below are what would be recorded **on the word**, with the chosen options filled in.
>
> **Part II (§9–§15, added for #472)** covers the other frozen leg, "draws down ≥ 20% of its premium budget", so
> the operator rules on the whole kill rule once. Part I (§1–§8) is the #465 draft as first written; the only edits
> to it are this paragraph, the title, and two pointers (end of §1, D4). Part II's entry texts (§14) are written to
> sit beside §6's, and §14.3 gives the single combined entry for a same-day ruling on both legs.

## 1. The gap, precisely
- **The frozen rule.** PREREG_THEMATIC_CONVEXITY §6: halt **new entries** for human review if *either* "the book
  draws down **≥ 20%** of its premium budget" *or* "the book **bleeds 9 months** with zero payoff". Open positions
  are not force-closed. Thresholds in `config.json:kill_rule`, which holds `book_drawdown_halt: 0.20` and
  `dry_months_halt: 9`.
- **The code.** `paper_loop.kill_rule_status` reads only `book_drawdown_halt`. It computes the drawdown with
  `state.convexity_book_drawdown` and trips on `book_dd >= dd_halt`. It returns `months_dry=0.0` as a literal, and
  `dry_months_halt` is read nowhere in the code (a repo-wide grep finds it only in `config.json` and test fixtures).
  The docstring says `months_dry` "does not trip until realized payoff tracking exists". That tracking has existed
  since T1.5: migration 0004 added `realized_pnl`, `closed_at` and `exit_reason` to `convexity_positions`, and
  `state.close_convexity_position` writes them. The docstring also says T1 "does not mark-to-market"; the L2
  monitor has marked every cycle since T1.5. Both statements are stale.
- **The dashboard.** `dashboard_data.risk_panel` returns `kill_rule = {tripped, reasons, book_drawdown, have_marks,
  drawdown_halt, drawdown_warn, level}`, with no dry clock. The hub's "Kill rule" check
  (`dashboard_web/api/hub.py:_checks`) renders "drawdown x% vs 20% halt" only. Nobody can see the second leg.
- **The record says otherwise.** `records/2026-07-04_first_real_entry_ERRATUM.md` §4: "the original kill-rule clocks
  (20% book drawdown / 9-month bleed) are now LIVE on a real position". The drawdown clock is live; the bleed
  clock has never existed in code. This draft corrects that sentence by citation, not by editing the erratum.
- **What a trip stops today.** `kill_rule_status(...).tripped` is read by the real entry path
  (`paper_loop.run_paper_cycle` step 2), by the council build (`orchestrator.py`, "Kill state active — council
  skipped"), by the L0 discovery scan ("Kill rule tripped — discovery scan skipped"), and by **every null book**:
  `shadow_book.py` (run_shadow_cycle), `fixed_basket.py` (3A and 3B), `shares_basket.py`. So a dry-leg trip wired
  into the same function would also stop the shadow, 3A, 3B and shares entries and the council's LLM spend. Issue
  #465's acceptance line "the shadow and null books are unaffected" is therefore **not** what the existing wiring
  does; it would need a separate branch. See decision D4.

**Adjacent, not proposed here:** `state.convexity_book_drawdown` counts OPEN and CLOSING positions only. Its
docstring: "Closed/realized losses are NOT counted here". When PL closes at its time-stop (§3), its loss of about
$688 leaves the drawdown figure, which then falls. Whether "draws down ≥ 20% of its premium budget" should include
realized losses is a separate question about the drawdown leg. It needs its own issue and its own word.
*(Filed as #472; drafted in Part II below.)*

## 2. The posture review is a different instrument
§6's 2026-07-02 amendment added an **entries-side** clock: anchored at forward-loop go-live (2026-06-02), an
interim LOOK on 2026-11-02, and **D = 2027-03-02**. If the real book has had zero entries ever by D, a mandatory
operator posture review triggers. It is **review-not-kill**: no automatic halt, and not evidence about the edge.

| | Dry leg (§6 frozen text) | Posture review (§6 amendment 2026-07-02) |
|---|---|---|
| Watches | the payoff side: premium bled with no payoff | the entries side: zero entries ever |
| Effect | automatic halt of NEW entries, pending human review | a scheduled decision point; nothing automatic |
| Can it fire now? | yes, once its clock reaches 9 months (§3) | no: PL entered 2026-07-01, so "zero entries ever by D" is false (ERRATUM §4) |
| In code | no (`months_dry=0.0`) | no code needed; it is a docketed look |

**How they compose.** They never conflict: one halts, the other only schedules a look. The posture review's
trigger is dead, so D survives only as a date. Under option B below the dry leg also binds on 2027-03-02, so one
review covers both. Under option A it binds a month after D. D then makes a natural place for a "30 days to bind"
look at the dry clock. Neither instrument changes the other's text. **UNVERIFIED:** whether the 2026-11-02
interim LOOK was held. STANDING_STATE's docket lists it without "DONE", and I found no record of it.

## 3. The operational definition — options
§6 does not define "bleeds", "payoff" or when the 9 months start. Each choice below is the operator's.

**Clock start**
- **A (recommended): the first real fill.** The earliest `opened_at` among real positions that ever held exposure
  (`status IN ('open','closing','closed')`). `state.confirm_convexity_fill` overwrites `opened_at` with the fill
  time, so this is the fill date, not the L1 date. Reason: "bleeds" presupposes premium at risk, which is the
  premise the 07-02 amendment itself states for both clauses.
- **B: forward-loop go-live, 2026-06-02.** Symmetric with the posture review's anchor. It counts a month in which
  nothing could bleed.
- **C: A, but only days with premium at risk count.** The clock pauses while the real book holds nothing. It
  differs from A only if the book ever empties. The real book has held PL continuously since 2026-07-01.

**Reset:** on every real close with `realized_pnl > 0`, the clock restarts at that row's `closed_at` (all options).

**What counts as payoff**
- **P1 (recommended): a realized profitable close**, `realized_pnl > 0`, under any exit reason (profit-take,
  time-stop salvage above cost, expiry in the money). It is irreversible and already recorded.
- **P2: P1, or an open position marked above its cost.** Not recommended. A mark is reversible, and the L2 marks
  on `data_feed.option_monitor = indicative`, so one tick above cost would reset nine months.
- **P3: only a profit-take close (≥ 10×).** Not recommended. "Zero payoff" reads as no payoff at all, and P3
  would ignore a time-stop that returns more than the premium.
- **A hazard for P1: #451.** On a closed-market tick the monitor runs with `dry_run` forced true, so
  `monitor._exit_position` books a triggered exit in the DB at the mark, with no sell (`real_submit` false). A
  profit-take fired on such a tick would write `realized_pnl > 0` with the contract still at the venue, and reset
  the clock on a payoff that never happened. Recommendation: the dry-leg PR lands after #451's fix. If it lands
  first, it counts only closes that carry a broker fill. **UNVERIFIED:** whether `close_order_id` is set on an
  immediately filled close, which is what a "has a broker fill" test would read.

**Which rows count:** every real-book row (`convexity_positions`), **including `origin = backfill`**. The kill rule
watches the book, and backfill premium is book premium. Outside-frame tagging does not apply: the six
`OUTSIDE_FRAME_SQL` positions are null-book rows (`state.outside_frame_positions`), and no real row matches it.
Null books never feed the clock. **Cancelled orders and carried-but-unfilled orders never start it**: a `cancelled`
row (`state.drop_convexity_position`; HL #1816 and AG #1867 were cancelled unfilled) and a `pending` row
held no position. A partial fill starts the clock at its fill.

**Unit:** calendar months on the US-Eastern date of `clock.now()`, so 9 months from 07-01 is 04-01. A 30.44-day
month would land a day or two away and is harder to state.

## 4. The dates for the real book as it stands
The book (STANDING_STATE "Board & book", 2026-11-08): PL `PL270115C00040000`, opened 2026-07-01, $690, marked
0.015. FLNC #6 10× `FLNC270521P00005000` and TITN #7 3× `TITN270617C00030000` (backfill), both filled 2026-11-04.
No real position has closed. The time-stops (`convexity_exits.time_stop_dte = 21`): PL first reads ≤ 21 DTE on
**2026-12-25** (an NYSE holiday, so the #451 path applies). The first open session after that is Mon 2026-12-28.
FLNC reaches 21 DTE on 2027-04-30 and TITN on 2027-05-27. At 0.015, PL's close will be a loss (P1: no reset).

| Option | Clock start | Binds if no payoff (P1) | What is still open on that day |
|---|---|---|---|
| **A** (first real fill) | 2026-07-01 (PL) | **Thu 2027-04-01** | FLNC (to 04-30) and TITN (to 05-27) can still pay; entries halt meanwhile |
| **B** (go-live) | 2026-06-02 | **Tue 2027-03-02** (= D) | the same, one month earlier |
| **C** (exposed days only) | 2026-07-01 | 2027-04-01 while exposure stays continuous | as A |

Under every option, the leg cannot have bound on any past date. The earliest bind is 2027-03-02, so **no past
admission would have been decided differently**. A realized profitable close before the bind date restarts the
clock at that close. FLNC or TITN reaching a profit-take, or closing above cost at its time-stop, would do it.

## 5. The code change, and frame_version
**The change** (one PR, safety-critical set: `paper_loop.py`, `state.py`, `dashboard_data.py`):
- `state.real_book_dry_clock(conn) -> (start, last_payoff_at)`, read-only, per the chosen options.
- `paper_loop.kill_rule_status` reads `kill_rule.dry_months_halt` (absent: the leg is off, as the drawdown leg
  defaults today) and computes `months_dry` from state. It trips when the ET date ≥ start + N calendar months, with
  the reason `book dry since YYYY-MM-DD (≥ 9 months, no realized payoff)`. `KillRuleStatus` gains `dry_since` and
  `dry_binds_on`. The stale docstring lines go.
- A state-read error raises, exactly as a failed drawdown read does today. The cycle then fails closed.
- `dashboard_data.risk_panel` adds `months_dry`, `dry_since`, `dry_binds_on` and `dry_months_halt`. The hub's
  "Kill rule" check text appends "dry 4.3 of 9 mo (binds 2027-04-01)".
- **Release (decision D5):** once tripped, the leg stays tripped until a P1 payoff or a dated operator re-anchor. I
  recommend a new key, `kill_rule.dry_clock_reanchored_on: "YYYY-MM-DD"`, written only on the word after the
  review. It is in the hashed `kill_rule` block, so it **would** move `frame_version`. That is right: the
  post-review book is a new regime.
- **Thresholds unchanged:** 20% and 9 stay as they are. No config value changes in this PR.

**frame_version: my position is that it should not move.** `config_loader.frame_version` hashes the comment-free
`convexity_book`, `convexity_gate`, `convexity_exits` and `kill_rule` config blocks, and no code, so a code-only
PR leaves it unchanged by construction. It should also stay unchanged on the merits:
1. The frozen frame already includes the dry leg. `dry_months_halt: 9` has sat in the hashed block since T0, so
   every stamp since then names a frame that *contained* the rule. The code is being brought up to the stamp, not
   the other way round.
2. Segments exist to separate admissions made under different rules (§5 amendment 2026-06-03, "Breach = an entry
   admitted in violation of the THEN-LIVE frame"). §4 shows that no past admission would have changed. A new
   segment would split the record over a difference that changed nothing.
3. A conformance amendment that changes behaviour moves the stamp through its config switch, as #276 did with
   `otm_side_guard`. Here no switch exists, and none should be added: the rule is not optional.
The cost: from the merge commit on, the same stamp covers code that can halt on the dry leg. The conformance
note names the merge commit, so the boundary is recorded in words. Issue #465 asks for this reading to be
confirmed with the operator; it is decision D6.

## 6. Entry texts, to be applied on the word (fill the bracketed choices)
**PREREG_THEMATIC_CONVEXITY §6, appended after the ownership addendum:**
> <!-- #465 dry-leg conformance note -->
> **Conformance note ([date], operator word: "[quote]"; #465).** The second halt, "the book bleeds 9 months with
> zero payoff", was frozen here and in `config.json:kill_rule.dry_months_halt = 9` but never implemented:
> `paper_loop.kill_rule_status` returned `months_dry = 0.0`. From commit [sha] it is computed as follows. The clock
> starts at [the first real fill's `opened_at` (2026-07-01, PL) | forward-loop go-live (2026-06-02)] and restarts at
> the `closed_at` of each real-book close with `realized_pnl > 0`. Backfill positions count; cancelled or unfilled
> orders do not; null books never feed it. "Months" are calendar months on the US-Eastern date. At ≥ 9 months the
> rule halts NEW entries (never a force-close) exactly as the drawdown leg does, and therefore also the council,
> the L0 scan and the null books' entries [| except the null books, which keep booking]. It stays tripped until a
> payoff close or a dated operator re-anchor (`kill_rule.dry_clock_reanchored_on`, a `frame_version` boundary).
> Thresholds are unchanged (20%, 9 months). `frame_version` does not move: the hashed block already contained the
> rule. On today's book the leg binds on [2027-04-01 | 2027-03-02] if no real position closes above cost first. It
> composes with the 2026-07-02 posture review (review-not-kill, D = 2027-03-02) without changing it.

**STANDING_STATE "Rulings in force", new entry:**
> - **Kill rule dry leg implemented (2026-[MM-DD], operator word "[quote]"; #465; PREREG_THEMATIC_CONVEXITY §6
>   conformance note):** `kill_rule_status` now computes `months_dry`. Clock from [first real fill 2026-07-01 |
>   go-live 2026-06-02], reset by a real close with `realized_pnl > 0`; payoff = [P1]. **Binds [2027-04-01 |
>   2027-03-02]** absent a payoff; the dashboard risk panel shows the clock. Thresholds unchanged; `frame_version`
>   unchanged (`frame-880e893e1660`). A trip halts entries [and the null books], never closes positions.

## 7. Tests the code PR must carry
1. No real row, or only `cancelled`/`pending` rows: clock not started, `months_dry = 0`, not tripped.
2. One fill dated 9 months + 1 day before `clock.now()`, no close: tripped. The reason names the start date.
3. The same at 9 months − 1 day: not tripped; `dry_binds_on` is the exact calendar date (07-01 → 04-01).
4. A close with `realized_pnl > 0` resets: tripped before it, not tripped after it, with the start at its `closed_at`.
5. A close with `realized_pnl ≤ 0` (the PL shape) does not reset.
6. A backfill-origin fill starts the clock. A null-book (shadow / 3A / 3B) close never resets it.
7. `dry_months_halt` absent: the leg is off and the drawdown leg is unchanged. The existing drawdown tests pass
   unmodified.
8. A DB read error raises, and `run_paper_cycle` opens nothing (fail-closed).
9. `frame_version(config)` is identical before and after the PR, on the same `config.json`.
10. `risk_panel` and the hub check render the clock. The snapshot-parity test (`dashboard_web/api`) is updated.
11. If D4 keeps the null books booking: a tripped dry leg still halts the real book and the council, and the
    shadow cycle still books. A mutation that makes it halt the shadow book fails this test.

## 8. Decisions for the operator
- **D1** Clock start: A (recommended), B or C.
- **D2** Payoff: P1 (recommended), P2 or P3, and whether the PR waits for #451 (recommended: yes).
- **D3** Backfill counts, cancelled orders do not: confirm.
- **D4** Does a dry trip also stop the null books and the council, as a drawdown trip already does? Recommendation:
  the real book and the council halt, and the null books keep booking. A dry book is the moment the brain-off
  comparison is most needed, and the nulls never touch the broker. This needs one new branch in the four null
  callers. *(Part II, D10: the same question for the drawdown leg; one answer should cover both legs.)*
- **D5** Release: a payoff close, or a dated `kill_rule.dry_clock_reanchored_on` (a frame boundary).
- **D6** `frame_version` stays unchanged for the conformance PR (recommended).

---

# Part II — The drawdown leg: what "draws down ≥ 20% of its premium budget" counts (#472)

> **Status: DRAFT for issue #472. Nothing here is in force.** Same footing as Part I: the frozen §6 text does not
> change; it gains an operational definition only by the operator's dated word. Code checked against `origin/main`
> at d2971be.

## 9. The gap, precisely (verified)
- **The frozen rule.** §6: halt new entries if "the book draws down **≥ 20%** of its premium budget". §6 does not
  say what the drawdown is measured against, or whether a closed loss still counts.
- **The code.** `paper_loop.kill_rule_status` sets `book_budget = account_equity × book_fraction` from config
  ($100,000 × 0.10 = **$10,000**), calls `state.convexity_book_drawdown(conn, book_budget)` and trips on
  `book_dd >= dd_halt`. That function sums `total_premium` and `mark × contracts × 100` over
  `status IN _EXPOSURE_STATES`, with `_EXPOSURE_STATES = "('open', 'closing')"` (`state.py`, defined just below
  the function). It returns `(entry_total − marked_total) / book_budget`. Its docstring: "Closed/realized losses
  are NOT counted here — this is the open-book mark drawdown the kill rule watches." Unmarked rows carry at cost.
  Gains net against losses across positions, and the figure can go **negative**.
- **So a closed loss leaves the figure.** `state.close_convexity_position` sets `status = 'closed'` and writes
  `realized_pnl`, and the row then drops out of the sum. A partial close (`state.record_partial_close`, #449)
  shrinks the open row's `contracts` and `total_premium` pro rata, so the sold part's loss leaves the figure too.
  The part's realized P&L sits in `rationale.partial_closes`.
- **Who reads it.** Every caller of `kill_rule_status` reads this one figure, computed on the **real** book's
  `convexity_positions`. The callers:
  - the real entry path (`paper_loop.run_paper_cycle` step 2);
  - the council build (`orchestrator.py`, "Kill state active — council skipped");
  - the L0 scan ("Kill rule tripped — discovery scan skipped");
  - the shadow book (`shadow_book.run_shadow_cycle`), 3A and 3B (`fixed_basket.py`, two calls) and the shares book
    (`shares_basket.py`);
  - the dashboard (`dashboard_data.risk_panel`, which feeds the hub's "Kill rule" check and `/api/status`).

  Two more read `state.convexity_book_drawdown` directly: the drawdown pager (`orchestrator._page_drawdown_warn` →
  `drawdown_warn.page_on_upward_crossing`, the 10% warn and the 20% page) and the `_print_book_summary` log line.
  **The null books have no drawdown of their own: they halt on the real book's figure.** So any change here also
  changes when they stop booking (D10).
- **The issue's "`open_premium_total`".** No state function has that name. It is the sizing argument
  (`convexity_sizing.convexity_position_size(open_premium_total=…)`), which the real path fills with
  `state.committed_book_premium(conn)` (open + closing + pending, #386). The issue's point stands: `book_remaining =
  book_budget − open_premium_total`, and a closed row counts in neither, so a realized loss frees its budget (§11).
- **To date the definitions have never differed.** No real position has closed (STANDING_STATE "Board & book",
  2026-11-08; Part I §4). HL #1816 and AG #1867 were cancelled unfilled and never held exposure. With no realized
  P&L, open-only and cumulative give the same number on every past day, so **no past admission or halt would have
  been decided differently** under any option below. **UNVERIFIED on DEV.** A read-only check:
  `SELECT COUNT(*) FROM convexity_positions WHERE status = 'closed' OR rationale LIKE '%partial_closes%'` should
  return 0. The definitions first diverge at PL's close (§12).

## 10. The options
1. **Cumulative (recommended).** `(Σ realized_pnl of real rows closed since the anchor + Σ partial-close P&L +
   Σ unrealized of open/closing rows) ÷ book_budget`, reported as a loss (sign flipped, as today).
   - **The anchor** is the first real fill (2026-07-01), the same anchor as Part I option A. Before any close the
     figure equals today's.
   - **What it means:** "the share of the book budget the strategy has lost, net". It never recovers without a
     winner.
   - **Why it fits:** §7 asks this of the kill rule ("a bad run is not disproof until the kill rule actually
     trips"). A convex book is expected to lose most bets between rare winners. This figure crosses 20% only when
     the winners have not paid for the losers.
   - **Precedent in the code:** the backfill stop rule's `backfill.bled_fraction` already counts "closed at
     realized, open at mark" over the same rows (§5 amendment 2026-11-03).
2. **High-water mark of book equity.** Equity = budget + realized + unrealized; drawdown = (peak − now) ÷ budget.
   This is the standard meaning of "drawdown", and it recovers after a payoff. It has three problems here:
   - **No history to take a peak from.** Marks are overwritten (`state.mark_convexity_position` is an UPDATE; the
     #453 draft's finding). The peak would need a new stored running maximum, updated every L2 tick.
   - **Indicative marks set the peak.** The L2 marks on `data_feed.option_monitor = indicative`, so one spuriously
     high mark would raise the peak for good and manufacture a drawdown later. A variant, **2R**, takes the peak on
     the *realized* curve only (cumulative realized P&L after each close) and adds today's unrealized. It needs no
     new storage, and it equals option 1 until the first profitable close.
   - **It fights the payoff shape.** After a 10× winner, two or three ordinary total losses ($2,000) trip it, though
     the book is far ahead. For a lottery-shaped book that is noise, not evidence. Not recommended.
3. **Keep open-only, and say so in §6.** The figure then measures how far the open book is marked below cost, and
   the dry leg (Part I) covers realized bleed. But one payoff close resets the dry clock. So a book that pays once
   every 9 months while losing money net is never stopped by either leg. Not recommended.

*Variant 1b (conservative):* count only open positions' unrealized *losses*, so an indicative gain cannot mask a
realized loss. Not recommended for now: today's code nets gains, and changing the netting would be a second change
stacked on the first.

## 11. Is the 10% book a one-time loss budget, or 10% at risk at any moment?
- **The text reads both ways.** §5 says "Convexity book = 10% of account — the total **premium-at-risk**", which is
  a measure at any moment. The same bullet says "The **only** money the strategy can lose; the other 90% is
  untouched", which is a lifetime bound.
- **The code reads it as "at any moment" (R2).** Sizing's `book_remaining = book_budget − committed premium`, and a
  closed row leaves the committed sum, so its budget is reused. `account_equity` is a frozen nominal ($100,000, "a
  paper nominal until a broker supplies it") that never shrinks with losses (`dashboard_data.account_panel`: "the
  broker number never resizes the frame"). Over a few years, a rolling book of 6–12-month positions spends several
  times $10,000.
- **R1, a one-time loss budget,** would size against `budget + cumulative realized − committed`, so the book shrinks
  as it loses.
- **How the two questions interact.** Under option 1 or 2R, the kill rule bounds the loss before a human must act.
  It trips at a net loss of $2,000. The open positions, which are never force-closed, can then lose at most their
  remaining marked value, which is at most $10,000. So under R2 the worst case before review is about **1.2 books
  ($12,000, 12% of the nominal account)**, and under R1 it is about the same. Under option 3 with R2 there is **no**
  lifetime bound, only the dry leg, which one payoff resets. Option 1 makes R1-versus-R2 a small question; option 3
  makes it a large one.
- **Recommendation: R2, written into §5, with option 1 as the lifetime stop.** It is what the code does, and a
  rolling portfolio of shots is the strategy (the backfill exists to fill idle slots). It needs no sizing change.
- **A T4 consequence to carry to #468, not decided here.** Live funding is "about $10,000, the frame's maximum
  premium-at-risk" (`records/2026-10-03_shared_account_capital.md`). Under R2, after realized losses the frame
  still commits up to $10,000 while the funded slice holds less. The difference would come out of the shared
  account's other cash, because the §3a.4 reserve protects only alpha_options' $5,250. Either the slice is topped
  up after losses, or live sizing is capped at the slice.

## 12. Worked example: the real book as it stands
Budget $10,000. The marks are from the 11-06 L2 (STANDING_STATE "Board & book", 2026-11-08); the arithmetic is
mine:

| Position | Entry | Mark | Marked value |
|---|---|---|---|
| PL #1, 1 × $690.00 | $690.00 | 0.015 | $1.50 |
| FLNC #6, 10 × $100.00 | $1,000.00 | 1.35 | $1,350.00 |
| TITN #7, 3 × $260.00 | $780.00 | 2.105 | $631.50 |
| **Book** | **$2,470.00** | | **$1,983.00** |

Net **−$487.00, a 4.87% drawdown**. The header's own "unrealized ≈ −$474" does not match its listed marks; the gap
is UNVERIFIED without DEV. FLNC's +$350 nets against PL and TITN under every option, as it does today.

**When PL closes.** PL's time-stop first reads ≤ 21 DTE on Fri 2026-12-25, an NYSE holiday.
- On current main, the 09:00 ET L2 tick that day is closed-market, so `monitor._exit_position` books the exit in
  the DB at the mark (#451).
- With #451's fix, the exit waits for the first open tick, Mon 12-28. A bid under `min_close_bid = 0.05` then books
  it in the DB at the mark (the #444 unsellable path).

Either way, at 0.015 the realized P&L is −$688.50.

| | Today | After PL closes at 0.015 (FLNC, TITN unchanged) | What would trip it on this book |
|---|---|---|---|
| **1** cumulative | 4.87% | **4.87%** (−688.50 realized + 201.50 unrealized) | FLNC + TITN marked at ≤ $468.50 combined, −76% from $1,981.50 |
| **2** HWM, all marks | ≥ 4.87%; the true peak is unknowable (no mark history) | ≥ 4.87% | depends on a peak nobody recorded |
| **2R** realized peak | 4.87% | 4.87% | as option 1 until a profitable close |
| **3** open-only | 4.87% | **−2.0%** (open $1,780 marked $1,981.50) | **nothing**: open premium is $1,780 < $2,000, so it cannot reach 20% without new entries |

Under option 1, if FLNC and TITN decay toward their time-stops (2027-04-30 and 2027-05-27), the drawdown leg could
bind in the same spring as the dry leg (Part I §4: 2027-04-01 under option A). One review would then cover both.

## 13. The code change, and frame_version
**The change** is one PR in the safety-critical set (`state.py`, `paper_loop.py`, `dashboard_data.py`,
`orchestrator.py`):
- `state.convexity_book_drawdown` keeps its signature and takes the chosen definition. Under option 1 it adds the
  `realized_pnl` of real rows with `status = 'closed'` and `closed_at >= anchor`, plus each open row's
  `rationale.partial_closes` P&L.
  - `have_marks` becomes "any marked open row, or any closed row".
  - The docstring's "NOT counted" line goes.
  - Every reader in §9 then follows automatically: the kill rule, the null-book and council guards, the risk
    panel, the hub, `/api/status`, the 10% warn and 20% page, and the log line.
- A read error raises, as today (fail-closed).
- **Release (D9).** Under option 1 a trip clears only through a payoff or a mark recovery, never because a loser
  closes. I recommend a dated `kill_rule.drawdown_reanchored_on: "YYYY-MM-DD"` that moves the anchor, written only
  on the word after the review.
  - It mirrors Part I D5's `dry_clock_reanchored_on`. Like that key, it sits in the hashed `kill_rule` block, so
    writing it **would** move `frame_version`. That is right: a post-review book is a new regime.
  - Two keys rather than one, so that a review of one leg does not wipe the other leg's history.
- `drawdown_warn`'s hysteresis is unchanged. Under option 1 the figure no longer falls when a loser closes, so the
  warn level holds where today it would re-arm.
- **Thresholds unchanged:** 20% and 9 months. No config value changes in this PR.

**frame_version: unchanged (D12), for Part I's reasons and one more.**
- The hash covers config only, so a code-only PR cannot move it.
- The stamp names a frame whose text already says "draws down ≥ 20% of its premium budget". The code is being
  brought to a reading of that text.
- If the PR merges **before PL's close (about 2026-12-25)**, the two definitions never disagreed on any day of the
  record (§9), so there is nothing to segment. If it merges after, the conformance note names the days they
  differed and gives both figures.

**Tests the code PR must carry** (numbered on from Part I §7):
12. Open-only regression (fails on main): a book with one real close at −$700 and its open positions at cost reads
    7.0% under option 1. On main it reads 0%.
13. A partial close's sold part stays in the figure (the #449 shape).
14. Null-book rows (`shadow_positions`, 3A/3B, shares) and `cancelled`/`pending`/`carried` rows never enter it.
15. A close before the anchor (or before `drawdown_reanchored_on`) is excluded; a close after it is included.
16. Before any close, the figure is identical to main's on the same rows (the pre-PL record is unchanged).
17. The 20% trip is `>=` on the new figure at every reader: `kill_rule_status`, `risk_panel`, the hub check, and
    `drawdown_warn.drawdown_level`.
18. A state read error raises, and `run_paper_cycle` opens nothing.
19. `frame_version(config)` is identical before and after, on the same `config.json`.
20. If D10 keeps the null books booking: a drawdown trip halts the real book, the council and L0, while the shadow
    cycle still books. A mutation that halts the shadow book fails.

## 14. Entry texts, to be applied on the word
**14.1 PREREG_THEMATIC_CONVEXITY §6, appended after Part I's conformance note:**
> <!-- #472 drawdown-leg conformance note -->
> **Conformance note ([date], operator word: "[quote]"; #472).** From commit [sha], "the book draws down ≥ 20% of
> its premium budget" is measured as [the book's net loss since the first real fill (2026-07-01): realized P&L of
> real-book closes, partial closes included, plus unrealized P&L of open and closing positions at their marks,
> divided by the premium budget (`account_equity × book_fraction`, $10,000) | the open book only: entry premium
> minus marked value of open and closing positions, divided by the premium budget; a closed loss leaves the figure,
> and realized bleed is the dry leg's]. Before this note the code measured the open book only. No real position had
> closed before [this commit | PL's close], so the two readings [never differed | differed only on [dates], as
> recorded in [record]]. Null books never feed the figure. At ≥ 20% the rule halts NEW entries exactly as the dry
> leg does [, and therefore also the council, the L0 scan and the null books' entries | : the real book, the
> council and the L0 scan halt, and the null books keep booking]. A trip clears by a payoff, a mark recovery, or a
> dated operator re-anchor (`kill_rule.drawdown_reanchored_on`, a `frame_version` boundary). Thresholds are
> unchanged, and `frame_version` does not move.

**14.2 PREREG_THEMATIC_CONVEXITY §5, appended after the risk-frame bullets (the replenishment ruling):**
> **Reading note ([date], operator word: "[quote]"; #472).** "Convexity book = 10% of account — the total
> premium-at-risk" means [**10% committed at any moment** (R2): a closed position frees its premium budget, and the
> lifetime loss before review is bounded by the §6 drawdown leg, at most about 1.2 books | **a one-time loss
> budget** (R1): sizing's remaining book is the budget plus cumulative realized P&L minus committed premium].
> "The only money the strategy can lose" is read accordingly. No frozen number changes.

**14.3 STANDING_STATE "Rulings in force".** If both legs are ruled together, record this one entry; otherwise record
Part I §6's entry and this one separately:
> - **Kill rule made operational (2026-[MM-DD], operator word "[quote]"; #465, #472; PREREG_THEMATIC_CONVEXITY §6
>   conformance notes + §5 reading note):** the **dry leg** runs from [first real fill 2026-07-01 | go-live
>   2026-06-02], resets on a real close with `realized_pnl > 0`, and binds [2027-04-01 | 2027-03-02] absent a
>   payoff. The **drawdown leg** = [net loss since 2026-07-01, realized + unrealized | open book only] ÷ $10,000.
>   The book is [10% committed at any moment | a one-time loss budget]. A trip of either leg halts entries [and the
>   null books | but not the null books] and never closes positions. Release is by payoff or a dated re-anchor
>   (`dry_clock_reanchored_on` / `drawdown_reanchored_on`, each a frame boundary). Thresholds unchanged;
>   `frame_version` unchanged (`frame-880e893e1660`). The risk panel shows both legs.

**What does NOT change:**
- the 20% and 9-month thresholds;
- §5's numbers (10% book, 1% per name, 2% per cluster, 15 open);
- flat-by-slots sizing (R2 leaves it byte-identical);
- the KILL switch and §6a exits;
- "open positions are not force-closed";
- the null books' own lifecycles;
- `frame_version`.

## 15. Decisions for the operator (Part II)
- **D7** Drawdown definition: **option 1** (recommended), 2, 2R or 3.
- **D8** Replenishment: **R2, written into §5** (recommended), or R1. Either way, the T4 funding consequence goes to
  #468.
- **D9** Release after a drawdown trip: a dated `kill_rule.drawdown_reanchored_on` (recommended), mirroring D5.
- **D10** Do the null books halt on a kill-rule trip? One answer should cover both legs (Part I D4). Recommendation,
  as for D4: the real book, the council and L0 halt, and the null books keep booking.
- **D11** Land the PR before PL's close (~2026-12-25), so the record never holds a day where the two readings differ
  (recommended).
- **D12** `frame_version` stays unchanged for the conformance PR (recommended, as D6).
