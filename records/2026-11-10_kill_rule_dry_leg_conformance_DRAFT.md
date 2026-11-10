# 2026-11-10 — The kill rule's "9 months dry" leg: a conformance draft (#465, R1)

> **Status: DRAFT for issue #465. Nothing here is in force.** The kill rule is frozen (PREREG_THEMATIC_CONVEXITY §6);
> it changes, or gains an operational definition, only by the operator's dated word. Merging this file ratifies
> nothing: merge-as-ratification is a named failure mode in this project (§6 ownership addendum, 2026-07-02). The
> entry texts in §6 below are what would be recorded **on the word**, with the chosen options filled in.

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
  callers.
- **D5** Release: a payoff close, or a dated `kill_rule.dry_clock_reanchored_on` (a frame boundary).
- **D6** `frame_version` stays unchanged for the conformance PR (recommended).
