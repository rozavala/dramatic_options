# 2026-10-27 — Proposal: carry an unfilled L1 entry into the next session (for the operator's word)

**Status: PROPOSAL — nothing is built.** It changes the real-book execution path, which is the path that will place
live orders at T4, so it is staged-class: it waits for the operator's word on §4, then ships with tests and one
paper-day check before it is relied on.

## 1. The problem (L1 #1816, 2026-10-26)
- HL was the first above-floor verdict since run #508 (2026-07-10). It passed the gate (IV/RV 0.83, skew 0.7 vp) and
  was submitted at 19:48:30 UTC (15:48 ET): 5× `HL270617C00017000`, LIMIT 1.76 (mid), $880.
- Entries are **DAY** orders (`broker.py`, `TimeInForce.DAY`) placed by the 15:45 ET L1. They get ~12 minutes before
  the close. The 16:00 ET L2 found it resting and cancelled it (`execution.cancel_unfilled`). It would have expired
  at the close anyway, so the cancel isn't the binding limit; the window is.
- The window has filled once: PL on 2026-07-01 (submitted 19:48:10, filled before the 20:00:04 L2), a $6.90 contract.
  It did not fill for HL's $1.76 one on a thin far-OTM chain. Above-floor verdicts are rare (one in 3½ months), so
  each one lost to the window costs a forward observation of the real book.

## 2. The proposal
1. **The evening attempt stays** as now: L1 submits at mid; the 16:00 L2 reconciles.
2. **If unfilled, carry instead of drop.** The 16:00 L2 cancels the resting order and marks the row `carried`
   (`carry_until` = the next trading day 15:30 ET) instead of `cancelled`. One carry per approval; it never rolls a
   second time.
3. **Next session, re-gate and resubmit.** At the first L2 at or after **10:00 ET** (the open's quotes are the
   widest), a carried row goes through the **same checks as an L1 entry**, on fresh quotes:
   KILL → kill rule → cluster cap → sentinel slots → `select_structure` (side guard on) → `is_cheap_convexity` →
   dual-read veto → sizing; on the live path, also the restricted list, the shared-account reserve and the
   foreign-quantity check.
   - Any veto drops it with a `carry-veto-<reason>` row, and the selection may land on a different contract if spot
     moved. Nothing is submitted that the L1 path wouldn't submit.
   - If it passes, it submits a DAY limit at mid.
4. **Walk the limit, bounded.** At each later L2 tick the order is still unfilled, re-quote and step the limit toward
   the ask. The bounds:
   - never above the ask;
   - never past the step cap in §4;
   - the position re-sized at the walked price inside the per-name / cluster / book caps (contracts may drop; under
     one contract → stop);
   - the wing IV implied by the limit price (Black-Scholes inversion over `calibration/pricing.bs_price`) must still
     pass the skew bound.

   On HL's 10-26 numbers the skew bound alone would allow a price well past the ask, so in practice the spread and
   the caps bind.
5. **Cancel at 15:30 ET**, before the next L1 judges the name again. If the council re-affirms it, that L1 makes a
   fresh evening attempt (and a fresh carry); if not, the approval lapses.
6. **Working orders reserve budget.** The cluster cap already counts `pending` (`cluster_open_premium`, deliberately,
   for same-cycle siblings). The book-level counts (book premium, position count, sentinel slots) use
   `_EXPOSURE_STATES` = open + closing only, a documented choice for a 12-minute order ("the ~10-slot book absorbs
   that window"). For orders working all day beside others, `pending` and `carried` rows count toward those caps
   too. Per-name dedup needs no change: a carried row is resolved before the next L1.

## 3. What does not change
- The council, the gate thresholds, sizing rules and every frozen risk number. The frame hash covers
  `convexity_book`, which this doesn't touch.
- The null books (shadow / 3A / 3B / shares): they book at marks, not fills.
- Forward scoring of the council (Brier/contribution): it scores proposals, not fills.
- The record: a fill can now come the next session at a walked price, so the real book's entry price and date
  differ from the L1's. Each row keeps `proposal_id`, the L1 `run_id`, and the carry/walk trail in its rationale,
  plus a STANDING_STATE entry from the first carried row.

## 4. Parameters — the operator's word
| | proposed | why |
|---|---|---|
| resubmit start | first L2 ≥ 10:00 ET | skip the open's widest quotes |
| walk step | ¼ of the half-spread, once an hour (every 2nd L2 tick) | fills cheap if it can, moves slowly |
| walk cap | 3 steps (at most ¾ of the way from mid to the ask) | never pays the full spread on a thin chain |
| cancel | 15:30 ET | clear before the 15:45 L1 re-judges |
| carries per approval | 1 | an approval is a one-session ticket; the council renews it nightly |
| evening attempt | kept | it has filled once (PL) |

## 5. Build notes (for after the word)
- **Order ids:** `make_client_order_id` is one id per (action, contract, ET date). A walk needs a new id per step
  (`…-w1`, `…-w2`) or Alpaca's replace-order. Which one works for options orders gets verified on paper before
  anything relies on it.
- **Tests:**
  - the carry state machine (pending → carried → resubmitted → filled / lapsed);
  - every veto on the resubmission path;
  - the walk bounds (ask, step cap, caps re-size, skew at the limit);
  - reservation of working orders;
  - the 15:30 cancel;
  - one carry only.
- **Rollout:** a config switch (`execution.carry_unfilled`, default off), turned on by a dated edit after one
  observed paper day, as with the earlier switches.
- **Effort:** about a day including tests. Not before tonight's L1: if HL is re-affirmed tonight, it gets the same
  12-minute window.
