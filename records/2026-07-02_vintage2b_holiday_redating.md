# 2026-07-02 — Vintage 2b re-dated to Mon 2026-07-06 (market holiday) + two pre-weekend verifications

**Status: written and merged BEFORE the Fri 2026-07-03 19:45 UTC L1 fires** — the blind window
for this amendment closes at that tick. Caught by the operator's external advisor review
(2026-07-02 evening); every claim below re-verified live before recording.

## 1. The re-dating (the substantive amendment)

**Fact (verified live, 2026-07-02 ~20:45 UTC, Alpaca trading calendar on the DEV paper key):**
Friday 2026-07-03 is a full US market holiday (July 4, 2026 falls on a Saturday → observed
Friday). The calendar has **no 2026-07-03 session** (sessions: 07-01, 07-02, then 07-06);
`clock.next_open = Mon 2026-07-06 09:30 ET`. Equities and listed options are closed the whole
session.

**The pinned expectation this amends:** the FBN §4 activation addendum and
`records/2026-07-02_burst_prediction_PINNED.md` (ACTUAL section) both say **"vintage 2b opens
at the Fri 2026-07-03 L1."** That L1 is scheduled on a closed market.

**Precedent (verified from the run record):** Juneteenth, Fri 2026-06-19 — the same holiday
class, loop live. The 19:45 UTC L1 fired (run **250**) with `council_health = NULL` (the
fail-closed `is_market_open()` gate skipped the council/entry path), and **zero bookings in
every book** that date (shadow 0, 3A/3B 0). The market-closed guard is already built and
live-proven; no new code is needed (advisor item A2 resolved as ALREADY-BUILT).

**The amendment (pre-observation):** tomorrow's L1 is expected to reproduce run 250's shape —
market-closed skip, `council_health NULL`, **0 bookings in every book, 0 LLM spend**.
**Vintage 2b opens at the Mon 2026-07-06 19:45 UTC L1** (the first post-activation L1 on an
open market). The pinned expectation itself is UNCHANGED in content: the remaining cheap union
names book (~11, incl. PAAS), after which the arm's binding constraint is the market. Only the
date moves, and it moves for an exchange-calendar reason verified before observation.

**Grading note:** if tomorrow's holiday L1 books ANYTHING or spends on the council, that is a
market-closed-gate failure — page-worthy, independent of the vintage 2b bands.

**Also flagged (pre-existing, no action):** the Sunday 12:00 UTC L0 has always run on a closed
market (stale Thu/Fri-close quotes); its books (3B/shares) are weekly by design. Recorded as
known behavior, not a deviation.

## 2. Branch-3 measurement-channel census (advisor P1 — verified POPULATED)

The concern: if council deaths on shadow-booked names are all proposer-abstentions (which emit
no per-criterion booleans), the D-day (2027-03-02) criteria-reconsideration branch would have
an empty evidence segment — a falsifier that cannot fire.

**Census (read-only, all 127 council proposals over the 12 distinct shadow-booked symbols,
run 2026-07-02):**

| death mode | n |
|---|---|
| explicit `at_inflection = false` strategist verdict | **61** |
| proposer NEUTRAL (no strategist stage reached) | 44 |
| strategist stage reached, `at_inflection` absent/null | 20 |
| survived to a conviction with `at_inflection = true` | 2 |

**8 of 12 shadow-booked symbols** (AG, FCX, FLNC, HBM, NXE, PL, RTX, UUUU) carry at least one
explicit `at_inflection = false` verdict; of tonight's vintage-2a burst cohort, 4 of 5
(UUUU/NXE/HBM/AG — not yet HL). **The instrument is populated** — at resolution, the
shadow-booked ∩ explicitly-inflection-vetoed segment supports the branch-3 read directly. No
amendment needed; the reasoned-abstention death class (44+20) is real but does not empty the
segment. The #139 reserve feeds this segment going forward (quiet-cheap names get judged at
all).

## 3. Verified gaps queued for the weekend window (recorded here, built separately)

- **FBN §5 pins no fill-realism haircut** for the simulated books (entries/marks vs a mid that
  is most fictional on far-OTM wings) — a blind read-layer amendment is queued BEFORE any
  resolution exists (advisor P2-2(i)).
- **`safety.live_max_order_notional` has no env override** — `config_loader` reads
  PAPER/LIVE_TRADING_ENABLED/DRY_RUN from env but not the ceiling, and `config.json` is
  git-tracked (a box-local edit is clobbered by the next deploy's reset). Fail-safe today
  (absent → live broker rejects all); an env-path PR is queued so the smoke session can arm
  without committing a live-money knob to git (advisor P3-2).
