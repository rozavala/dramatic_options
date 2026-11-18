# 2026-11-10 — The live notional ceiling and closes: a PREREG_REAL_MONEY_BROKER §3 amendment draft (#473)

> **Status: DRAFT for issue #473. Nothing here is in force.** PREREG_REAL_MONEY_BROKER §3 is SIGNED OFF (frozen
> 2026-07-01). It changes only by the operator's dated word. Merging this file ratifies nothing: merge-as-
> ratification is a named failure mode in this project (PREREG_THEMATIC_CONVEXITY §6 ownership addendum). The
> amendment text in §5 is what would be appended to PREREG_REAL_MONEY_BROKER on the word. This also answers the
> #468 checklist draft's decision 3 ("the ceiling and closes"); the two should be ruled together.

## 1. The frozen text (quoted exactly)
PREREG_REAL_MONEY_BROKER §3, "Real-money safeguard — a hard per-order notional ceiling (the SOLE broker-level
guard, SIGNED OFF)":
> `AlpacaLiveBroker` rejects **fail-closed** (`Fill(False, …)`, nothing transmitted) any order whose
> premium notional (`qty × limit × 100`) exceeds a configured `safety.live_max_order_notional`
> (no default → absent config fails closed to reject; the operator sets it at arm time). This bounds a
> sizing/pricing bug from placing a large real order, independent of the book/cluster caps upstream.

The purpose clause is "a large real **order**", and it gives sizing and pricing as the bugs it guards against. The
text does not separate buys from sells. The §3a amendment (2026-10-03) later took the opposite line for its own
guards: "Closes are never blocked by it, so a defect cannot trap an open position" (§3a.2, the restricted list);
"Closes are exempt: selling a long option needs no buying power" (§3a.4, the reserve).

## 2. The code (verified on `origin/main` d2971be)
- `broker.AlpacaLiveBroker._reject_precheck` computes `notional = qty × limit × 100`. It then returns a rejecting
  `Fill` when `_max_order_notional is None` ("no safety.live_max_order_notional configured"), or when `notional >
  _max_order_notional` ("exceeds the … per-order ceiling (fail-closed)"). **Both checks run before `if is_buy:`**,
  so they apply to every order. Only the §3a.4 reserve check sits behind `is_buy`.
- Callers: `submit_paper` (single leg, both sides) and `submit_spread` (the vertical; precheck on the long leg's
  symbol at the NET limit, `is_buy=opening`). Both run it **before** the DRY_RUN branch, so a breach rejects even in
  simulation. `AlpacaPaperBroker` inherits the base hook, which returns `None`, so the paper path has no ceiling.
- The ceiling comes from `safety.live_max_order_notional`, or from the env `LIVE_MAX_ORDER_NOTIONAL`
  (`config_loader.load_config`). Its comment describes arming the env ceiling "AT SESSION TIME and unset it after"
  for the §5 smoke. `config.json` carries no value.
- **What a refused close does.** `monitor._exit_position` (single leg) logs `"SELL_TO_CLOSE submit failed #%d %s —
  left open to retry"` and returns. The row stays `open` and is retried every L2 tick. **No page is sent.** The
  vertical path pages through `_page_once(... "VERTICAL CLOSE REFUSED" ...)` (#412).

**The issue's premise is correct.** Two additions:
- **The absent-ceiling branch traps closes too.** If the env ceiling is unset after the smoke, as `config_loader`'s
  comment describes, every live close is refused, not only large ones.
- **A refused close can run through expiry.** A profit-take refused at 10× keeps retrying while the mark stays ≥ 10×.
  If the mark falls back, the row rides on until its 21-DTE time-stop, and that close is refused too if it is still
  over the ceiling. The row then reaches expiry `open`. There `monitor_positions` books intrinsic in the journal on
  the first tick of the expiry date, while the venue auto-exercises an in-the-money long
  (`records/2026-11-10_expiry_exercise_audit_DRAFT.md`, #444). A large winner is exactly the case where it would be
  in the money.

## 3. Why the notional is the wrong unit for a close
A sell-to-close of a long option has two failure modes:
- **Selling more than is held.** This opens a short, i.e. naked exposure (CLAUDE.md guardrail 3). The bug is a
  **quantity** bug.
- **Selling too cheap.** A low limit means a *smaller* notional, so a ceiling never sees it. A limit far *above*
  the market simply rests unfilled.

A high close notional is money coming in. On a close, the notional ceiling therefore guards only the quantity bug,
and badly: it misfires on every legitimate winner whose value exceeds the ceiling, and it lets an oversell through
whenever the price is low. A direct quantity bound guards the real failure. **Not established** from the broker's
documentation (fetched today; its docs site is not reachable from this session): whether Alpaca itself rejects a
`SELL_TO_CLOSE` larger than the held quantity. So the bound has to be ours.

## 4. The options
1. **Exempt closes from the ceiling, and bound every close by quantity (recommended).** The notional ceiling, and
   its absent-config rejection, apply to **opening** orders only: `submit_paper` buys and `submit_spread(action=
   "open")`. Every close that would be **transmitted** must pass a quantity bound:
   - `qty ≤` the journal row's open contracts. The monitor sends exactly this; the bound is made explicit and
     tested.
   - `qty ≤` the venue's quantity of that contract (`broker.venue_quantity`, the same per-contract read §3a.3 uses,
     never a listing of the account). For a vertical, the short leg's venue quantity must be ≤ −qty.
   - A failed venue read refuses the close (fail-closed) and pages. The close is then retried next tick, so a
     transient read failure costs one tick, not a position.

   The bound lives in the shared base, so it also runs on the DEV paper account (§4 order-safety parity). There it
   catches journal/venue drift before T4. It runs **after** the DRY_RUN branch, because a simulated journal holds
   nothing at the venue.
   - **Cost:** one extra venue read per transmitted close.
   - **Effect:** a close can never be refused for its size, and can never sell more than both the journal and the
     venue hold.
   - **Consistency:** the same line as §3a.2 and §3a.4, and as the #468 draft's option (a).
2. **A separate, larger close ceiling** (for example the profit-take multiple × the per-name cap × a margin, so 10 ×
   $1,000 × 1.5 = $15,000), also bounded by the journal quantity. This is the issue's recommendation. It traps the
   very tail the book exists for. The profit-take fires on the first tick that sees ≥ 10×, and a catalyst gap can
   take the mark straight past 15× (PREREG_THEMATIC_CONVEXITY §6a: "the real catalyst-driven tail is fatter than
   modeled"). A $1,000 position first seen at 25× is a $25,000 sale, refused every tick. A second number would also
   need its own setting and its own fail-closed rule. Not recommended.
3. **Raise the single ceiling** above the largest plausible close (≥ $10,000, which is the whole book). The entry
   guard would then be ten times weaker: one mis-sized buy could commit the entire book in one order. It still traps
   a gap past the new value. Not recommended.

Under every option the KILL switch, the shared-account root guard (SPY/XSP/SPX/SPXW rejected on both sides) and
DRY_RUN are unchanged.

## 5. Amendment text, to be appended to PREREG_REAL_MONEY_BROKER on the word
> **§3b Amendment ([date], operator word: "[quote]"; #473) — the ceiling bounds opening orders; closes are bounded
> by quantity.** §3's ceiling, and its absent-config rejection, apply to **opening** orders only (a single-leg
> buy-to-open and a vertical's open). A close is never rejected for its notional. A position that reaches the
> 10× profit-take is worth about ten times the per-name cap, and a ceiling set near that cap would refuse its sale
> on every cycle, leaving the book's largest winner unsellable and, at expiry, exercised at the venue. Instead,
> every transmitted close, on the paper and the live account alike, is rejected fail-closed (`Fill(False, …)`,
> nothing transmitted) when its quantity exceeds either the journal row's open contracts or the venue's quantity of
> that contract (`venue_quantity`, the §3a.3 per-contract read; for a vertical, the short leg's held quantity too),
> or when the venue read fails. A simulated (DRY_RUN) close makes no venue read. A refused close is paged at most
> once per position per day and retried every cycle. This page is not the per-order live paging §3 deselected: it
> fires only on a refusal, as the vertical close's page already does (#412). §3's purpose is unchanged: the
> ceiling bounds a sizing or pricing bug on the way in. On the way out, the bug that matters is selling more than
> is held, and the quantity bound guards that directly. `frame_version` does not move (`safety` is outside the
> hashed frame), and no live order has ever been placed, so no record segments.

**STANDING_STATE "Rulings in force", appended to the "Shared live account (#279 …; §3a)" entry:**
> - **Closes bounded by quantity, not notional ([date], operator word "[quote]"; #473; PREREG_REAL_MONEY_BROKER
>   §3b):** the live ceiling applies to opening orders only; every transmitted close (paper and live) must not
>   exceed the journal's or the venue's held quantity (venue read fails → refused); a refused single-leg close
>   pages once per position per day.

**What does NOT change:** the ceiling on buys and its fail-closed absent-config rule; the §3a guards (reserved
roots on both sides, restricted list on buys, foreign-quantity check at entry, the $5,250 reserve on buys, no
equity fallback, `do-` ids); the triple gate; DRY_RUN; §6a exit rules and thresholds; `frame_version`. The
ceiling's **value** stays the operator's, set at arm time (the #468 checklist).

## 6. Tests the code PR must carry
In `tests/test_broker.py` (the `_live_broker` fixture) and `tests/test_monitor.py`:
1. **Regression, fails on main:** live broker, ceiling $1,000, venue holds 10. `submit_paper(qty=10, side="sell",
   limit_price=10.00)` (a $10,000 close) is transmitted.
2. **Regression, fails on main:** the same close with `max_order_notional=None` is transmitted.
3. The same close with qty 11 while the venue holds 10 is rejected, nothing is transmitted, and the note names
   both quantities.
4. The venue read returns `None` (failure): the close is rejected and nothing is transmitted.
5. Under DRY_RUN a close simulates without any venue read, and an over-ceiling close is not rejected.
6. A buy over the ceiling is still rejected. A buy with an absent ceiling is still rejected. Both run before the
   DRY_RUN branch (the existing four ceiling tests pass, renamed to say "buy").
7. `submit_spread(action="close")` over the ceiling is transmitted when both legs' venue quantities cover it.
   `action="open"` over the ceiling is rejected.
8. The reserve precheck is still buy-only (existing `tests/test_shared_account.py` unchanged).
9. `AlpacaPaperBroker`: an over-quantity transmitted close is rejected (the bound lives in the base).
10. Monitor: a refused single-leg close leaves the row `open`, pages "CLOSE REFUSED" once per position per ET day
    (a second refusal the same day does not page; the next day it pages again), and the next cycle retries.
11. Monitor: the page goes through `_page_once`, so a failing `notify.send` never breaks the pass.

## 7. The page on a refused single-leg close (in the same PR)
`monitor._exit_position`, single-leg branch, at `if not fill.filled:`, add `_page_once(conn, pos, today, "CLOSE
REFUSED", f"#{pid} {contract} {reason} ×{contracts} @ {bid:.2f}: {fill.note}. Left open; retried each cycle.")`
before the `return`. This reuses the per-position, per-ET-day stamp in `rationale.paged` that the vertical, expiry
and price-lookup pages already use. It pages on paper as well, which is the point: today an Alpaca submit error on
a close is only a log line. It is safe to land **ahead of** the §3b word. It changes no order behaviour, only
whether a refusal is seen, so the operator may authorize it separately (decision D3).

## 8. Decisions for the operator
- **D1** Option 1 (recommended), 2 or 3. This also answers #468 decision 3.
- **D2** The quantity bound in the shared base (paper and live, recommended), or live only.
- **D3** The refused-close page: in the same PR, or ahead of it as a separate small change (it moves no order).
- **D4** Order of landing: before #466's exit fire drill, so the drill exercises the bound (recommended).
