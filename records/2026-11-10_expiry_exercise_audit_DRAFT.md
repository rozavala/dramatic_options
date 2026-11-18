# 2026-11-10 — Real long options at the venue through expiry while the journal shows them closed: an audit draft (#444)

> **Status: DRAFT for issue #444. Nothing here is in force.** The exits are frozen (PREREG_THEMATIC_CONVEXITY §6a).
> Option (a) below is a read-only check. Options (b) and (c) change what an exit does or what the journal records,
> so each needs the operator's dated word. Merging this file ratifies nothing: merge-as-ratification is a named
> failure mode in this project (§6 ownership addendum). The texts in §6 would be recorded on the word.

## 1. The venue facts (fetched 2026-11-10)
**Access.** Alpaca's documentation site (`docs.alpaca.markets`) and support site (`alpaca.markets/support`) are
blocked from this session: the network proxy answered 403 to both. To read them, the session's network settings
must allow those hosts. The facts below therefore come from Alpaca's **own published sources that this session
could fetch**:
- **[S1]** Alpaca's Trading API OpenAPI specification (`info.version: 2.0.1`), as published in Alpaca's own
  repository: https://github.com/alpacahq/alpaca-java/blob/cb1e4484b92508f29a924116252cc95b468047c6/specs/trading/openapi.yaml
  (blob `48987bc`, matching the fetched file);
- **[S2]** the `TradingClient` of `alpaca-py`, the SDK this project pins (`requirements.txt`: `alpaca-py==0.43.4`),
  read from the installed 0.43.4 package and from
  https://github.com/alpacahq/alpaca-py/blob/2433fb731f19829cae594646239681245cc14ccd/alpaca/trading/client.py.

A search engine's summaries of the blocked pages are **not** used as facts here. Where they make a claim, it is
listed under "not established" as a lead to check.

**Established:**
- **F1. Auto-exercise is the default.** [S1], the exercise and do-not-exercise endpoints, and [S2]: "By default,
  Alpaca will automatically exercise in-the-money (ITM) contracts at expiry."
- **F2. A do-not-exercise instruction exists in the venue API.** [S1] `POST
  /v2/positions/{symbol_or_contract_id}/do-not-exercise`: "This endpoint enables users to submit a do-not-exercise
  (DNE) instruction for a held option contract, preventing automatic exercise at expiry. … This endpoint allows
  users to override that behavior." Its 403 examples are "no available position for the specified contract" and
  "cannot submit DNE for short position".
- **F3. The pinned SDK has no DNE call.** `alpaca-py` 0.43.4's `TradingClient` has `exercise_options_position`
  only. Its docstring: "To cancel an exercise request or to submit a Do-not-exercise (DNE) instruction, please
  contact our support team." The HEAD `client.py` above has no do-not-exercise method either. A DNE from this code
  would need a raw REST call or an SDK change.
- **F4. Manual exercise is immediate, with an hours restriction.** [S1]: "Exercise requests will be processed
  immediately once received. Exercise requests submitted between market close and midnight will be rejected to
  avoid any confusion about when the exercise will settle." [S2] says instead "Exercise requests submitted outside
  market hours will be rejected." The two Alpaca sources disagree on the window.
- **F5. The venue records the events.** [S1] defines account activities `OPEXC` ("Option exercise"), `OPEXP`
  ("Option expiry") and `OPTRD` ("Trading activity that is paired with the assignment/exercise"). A post-expiry
  check can read what happened from these.

**Not established** (each needs the blocked pages, Alpaca support, or a paper observation):
- **N1. The auto-exercise threshold** (how far in the money; which price decides). A search summary of the docs says
  $0.01 ITM at the official close. Not fetched, not quoted.
- **N2. Expiry day with insufficient buying power to exercise.** A search summary says Alpaca sells the position
  out within an hour before expiry. Not fetched.
- **N3. Timing:** when expiry processing runs, and the last moment a DNE is accepted. The search summaries
  disagree with each other (4:00 PM, 6:00 PM, "best-efforts" by email after 4:00 PM ET).
- **N4. Paper-account differences.** Whether the paper venue simulates auto-exercise, DNE and sell-outs as live
  does. Nothing fetched speaks to paper.
- **N5. Whether the venue rejects a `SELL_TO_CLOSE` larger than the held quantity** (relevant to #473).

**What follows from F1 alone:** a long option the journal has closed, but which the venue still holds at expiry,
becomes **stock** if it finishes in the money, by default. One contract of PL's $40 call is a $4,000 purchase. TITN
#7's 3 × $30 calls are $9,000. FLNC #6's 10 × $5 **puts** deliver a *sale* of 1,000 shares. With no shares held,
that sale is a **short stock position**: unbounded risk, the opposite of the defined-risk mandate (CLAUDE.md
guardrail 3). What the venue does when the account cannot carry it is N2, not established.

## 2. The code paths (verified on `origin/main` d2971be)
The issue names two paths. There are five:
1. **The unsellable in-DB close.** In `monitor._exit_position`, when the bid is below `convexity_exits.min_close_bid`
   (0.05), it sets `reason = reason + "_unsellable"` and calls `_close_and_resolve` at the mark. Nothing is sent.
   The venue keeps the contract until expiry.
   - **The issue calls this an edge case.** For this book's typical loser it is the expected path. PL is marked
     0.015 at about 70 DTE, so its time-stop will almost certainly be unsellable.
2. **The closed-market in-DB close (#451).** `orchestrator.py` passes `dry_run=dry_run or not market_open`. On a
   closed tick `real_submit` is false, so any triggered exit books in the DB at the mark. The 09:00 ET L2 tick is
   pre-market, and `dte` is date-based, so every time-stop is first seen with the market closed. This is the
   systematic case.
3. **Expiry booked on the morning of the expiry date.** `monitor_positions` checks `today >= expiry` before
   marking, so an open real row is booked at intrinsic on the **first tick of the expiry date** (09:00 ET,
   pre-market). It uses that moment's underlying price, while the contract trades all session and the venue decides
   exercise at or after the close (N1, N3).
4. **Expiry while closing.** `_reconcile_closing` cancels the resting sell, settles it (`carry.cancel_and_settle`,
   #445), and books the fill, intrinsic, or a blend. This happens on the expiry date too.
5. **A refused or never-filled close.** A close refused every tick (#473's notional ceiling, or any submit error:
   "left open to retry") or a resting sell that never fills reaches path 3 or 4.

**What reconciles venue against journal today:** only the §3a.3 foreign-quantity check (`paper_loop`, before an
entry, for that one contract). Nothing reads the venue for a row the journal has closed. Nothing models an
exercise: `grep -n 'exercise' broker.py monitor.py` finds none. One side effect: a contract orphaned by path 1 or 2
would make a later entry into the **same contract** fail the foreign-quantity check (`veto-foreign-quantity`,
paged), because the venue holds what the journal does not explain.

## 3. Worked example: PL #1 (`PL270115C00040000`, 1 × $40 call, expiry Fri 2027-01-15)
- **Time-stop.** PL first reads ≤ 21 DTE on Fri 2026-12-25, an NYSE holiday. On current main, the 09:00 ET L2 tick
  is closed-market, so path 2 books PL closed at its mark that morning.
- **With #451's fix,** the exit waits for the first open tick, Mon 12-28. There, a bid under 0.05 (mark 0.015 on
  11-06) takes path 1: closed in the DB at the mark, nothing sent.
- **Either way,** the paper account holds the contract from then until 2027-01-15, about three weeks, with the
  journal showing it closed.
- **If PL closes above $40 on 01-15,** by F1 the paper venue (subject to N4) exercises it into 100 shares, a
  $4,000 debit that nothing in the journal knows about.
- **This is the first chance to observe the venue's behaviour.** It is on paper, so it costs no money, and option
  (a) would see it.

## 4. The options (the issue comment's three, with the venue facts)
- **(a) Read-only venue-vs-journal check (recommended now, before T4, and before PL's window opens on 12-25).**
  Each L2 tick, market open or closed:
  - For every real-book contract whose expiry is today or later and whose row ever held exposure (open, closing or
    closed), read `broker.venue_quantity(contract)`. This is the §3a.3 per-contract read, **never** a listing of
    the account, so it is safe in the shared live account.
  - Compare the read with the journal's open + closing contracts for that symbol.
  - Page on any difference, once per contract per ET day. Within 5 NYSE trading days of expiry, page at priority 1
    with the underlying's distance to the strike. A failed read pages as "unknown", never as zero.
  - After the expiry date, read the contract once more (expected 0). On the paper account only, the check may also
    read the underlying's share quantity, to catch an exercise. On the live account the operator's own stock makes
    that read ambiguous, so it is a T4 question (#468). The venue's `OPEXC`/`OPEXP` activities (F5) are the cleaner
    evidence, but reading them lists account-wide activity, so it needs the operator's word under §3a.3.
  - It sends no order and changes no exit.
  - **An expected orphan is not an alarm.** A row closed by path 1 is *expected* at the venue, so the page for it
    should state "orphan by design, n days to expiry, X% from the strike", with priority rising as expiry nears.
- **(b) The unsellable path still sends a sell at the minimum price increment.** This changes §6a's behaviour and
  needs a dated amendment.
  - Where any bid exists, the contract leaves the venue for about nothing, and the journal books the real fill.
  - Where no bid exists (the far-OTM case), the order rests and expires at the close. The row then cycles open →
    closing → open each day: the churn the T2.5 design avoided. The contract is still at the venue at expiry.
  - The venue's minimum price increment for each contract is **not established** here.
- **(c) Keep the row open, marked as an orphan, until expiry, instead of booking it closed.** This changes what the
  journal reports and needs a dated §6a note. It changes no threshold.
  - **For it:** the journal equals the venue for the whole window. The L2 keeps marking the row. Because the
    time-stop condition stays true, the first tick that sees a bid ≥ `min_close_bid` sells it through the
    unchanged sell path, so a late recovery is captured instead of being lost to an in-DB close. The row counts in
    `_EXPOSURE_STATES` (slots, the book cap, the drawdown at its mark) for at most 21 days. That is honest: the
    venue does hold it.
  - **What (c) needs alongside it.** Path 3 must change for real-submit rows: book expiry **after the close** on
    the expiry date, not at the 09:00 ET tick. Otherwise (c) only shrinks the gap from three weeks to one session.
  - **What (c) does not solve on its own:** a contract in the money by less than `min_close_bid`, or with no bid,
    at the close. By F1 that contract is still exercised. For that tail, F2 offers a DNE on expiry day for any
    contract the book still holds. It forfeits at most a few cents of intrinsic, and the book never takes delivery.
    Its timing (N3), its paper behaviour (N4) and the missing SDK call (F3) are not established, so it is a later
    decision, not part of (c).

**Recommendation, given the venue facts:**
1. **(a) now.** F1 makes the risk real by default, and (a) covers all five paths without touching a frozen rule.
2. **Then (c), not (b),** with the expiry-after-the-close change, once #451 has landed. (b) sends orders that
   mostly cannot fill and still leaves the no-bid contract at the venue. (c) keeps the record true and keeps the
   upside of a late recovery.
3. **The DNE backstop:** decide after N1–N4 are established, either from the docs with the hosts allowed or from
   Alpaca support, and after (a) has watched PL's window on paper.

**The #451 interaction.** #451's fix (in flight) makes a closed-market tick defer triggered exits to the next open
tick instead of booking them in the DB. That removes path 2, the systematic one. It does not remove path 1: the
deferred time-stop of a far-OTM loser goes unsellable at the open tick, as PL's will. #451's plan keeps "expiry at
intrinsic … still books" on closed-market ticks, which is path 3. So (c)'s expiry-after-the-close change touches the
same lines of `monitor_positions` as #451's `mark_only` flag. It should land after #451, or be reviewed with it.
(a) is independent of both. **With #465 and #472:** a path-1 or path-2 close books `realized_pnl` at the mark (≤ 0
here), so it never resets the dry clock. Under #472's option 1 (cumulative) the drawdown is the same whether the
orphan is realized at its mark or held open at it. So (c) is neutral for the kill rule under option 1, and under
option 3 (open-only) it keeps the loss in the figure until expiry.

## 5. The code that follows each word
- **(a)**, one PR in the safety-critical set (`monitor.py` or a new read-only module called from the L2 in
  `orchestrator.py`; no change to `broker.py`):
  - `venue_journal_check(conn, broker, today)` returns the per-contract differences and pages through
    `_page_once`-style per-contract stamps.
  - Tests:
    1. A journal-closed row whose contract the venue still holds pages, and names the days to expiry and the
       distance to the strike.
    2. Matching quantities send no page.
    3. A read returning `None` pages "unknown" and does not raise.
    4. The check never calls a position-listing API (a broker spy asserts only `get_open_position` per contract).
    5. The check never calls `submit_paper`, `submit_spread` or `cancel_order`.
    6. It runs on a closed-market tick.
    7. The page priority rises within 5 trading days of expiry.
    8. Paging never breaks the monitor pass.
- **(c)**, after #451 (`monitor.py`):
  - The unsellable branch keeps the row `open` with `rationale.orphan = {since, reason}` instead of calling
    `_close_and_resolve`.
  - On the expiry date, a real-submit row books expiry only from the first tick at or after 16:00 ET.
  - Tests:
    1. An unsellable time-stop leaves the row open, marked as an orphan, with nothing sent.
    2. A later tick with a bid ≥ 0.05 sells it through the normal path.
    3. A 09:00 ET expiry-date tick does not book expiry for a real-submit row; the 16:00 tick does.
    4. DRY_RUN and the null books still book in the DB exactly as today.
    5. The forward-scoring resolution keys (`_unsellable` reason prefix) are unchanged for the eventual close.
- **(b)**, if chosen instead of (c): in the unsellable branch, a sell at the venue's minimum increment through
  `submit_paper`, and an increment table taken from the venue's documentation (not established).

## 6. Entry texts, to be applied on the word
**(a), STANDING_STATE "Rulings in force":**
> - **Venue-vs-journal expiry check ON ([date], operator word "[quote]"; #444):** each L2 tick reads the venue
>   quantity of every real-book contract not yet expired (per contract, never an account listing; §3a.3) and pages
>   any difference from the journal's open + closing quantity, at priority 1 within 5 trading days of expiry.
>   Read-only; no exit changes; `frame_version` unchanged.

**(c), PREREG_THEMATIC_CONVEXITY §6a, appended after the 2026-06-01 amendment:**
> **Dated note ([date], operator word: "[quote]"; #444) — an unsellable exit stays open until it sells or
> expires.** The broker exercises in-the-money long options at expiry by default (Alpaca Trading API, the exercise
> and do-not-exercise endpoints). So a triggered exit whose bid is below `min_close_bid` no longer books the
> position closed at its mark while the venue still holds it. The row stays open, labelled an orphan, is marked
> every cycle, and is sold through the ordinary path on the first tick its bid reaches `min_close_bid`. On its
> expiry date a real position is booked at intrinsic only after the close. The thresholds (10×, 21 DTE,
> `min_close_bid`) are unchanged. DRY_RUN and the null books book as before. From commit [sha]; `frame_version`
> does not move.

**(b), if chosen instead, PREREG_THEMATIC_CONVEXITY §6a:**
> **Amendment ([date], operator word: "[quote]"; #444).** A triggered exit whose bid is below `min_close_bid` is
> still sent as a sell-to-close at the venue's minimum price increment, and booked at its fill. An unfilled order
> rests to the close and is retried the next session. [Thresholds unchanged.]

**What does NOT change** (under any option): the 10× profit-take, the 21-DTE time-stop and `min_close_bid`; the
entry path; the §3a.3 foreign-quantity check; DRY_RUN semantics; the null books; `frame_version`.

## 7. Decisions for the operator
- **D1** (a) now, read-only (recommended), before PL's window opens (12-25).
- **D2** Allow `docs.alpaca.markets` and `alpaca.markets` in the session network (or ask Alpaca support) to settle
  N1–N5. Record the answers in this file's successor.
- **D3** For the unsellable path: (c) with expiry booked after the close (recommended, after #451), or (b).
- **D4** The expiry-day DNE backstop: defer until N3/N4 are known and (a) has watched PL's window on paper.
- **D5** Whether the post-expiry check may read account activities (`OPEXC`/`OPEXP`), which lists account-wide
  events (a §3a.3 question), or stays per-contract only.
