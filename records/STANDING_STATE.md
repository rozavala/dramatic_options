# STANDING STATE — the relay sync header

**as_of: 2026-10-23T01:30Z · supersedes: 2026-10-22T02:10Z · reflects the W42 Sunday review
(`records/2026-10-18_sunday_w42.md`): the L1 marker refresh ON (#319/#320, its telemetry #322) · KMT re-pin #17 ·
the April-2027 tenor cliff from Monday 10-19 · Real Options' pkill fix (#4953) · NTSK's first scan.**

Maintained by CC; updated on every ruling, clock change, staged-PR change, or pending-act change.
**Relay rule (both directions): a strategy question or advice arriving WITHOUT this header, or carrying an
`as_of` older than the latest ruling, is treated as UNSYNCED — verify against the record before acting.**
The header's absence is itself a signal.

## Rulings in force
- **⭐ Criterion (3) RE-SPECIFIED (2026-10-23, the F4 review held early at session 21, operator word "B";
  PREREG_COUNCIL_GATE_SEPARATION §10.10; `records/2026-10-23_f4_review_early.md`):** "AT A LIVE INFLECTION — the
  driver is still changing within the option's 6-12-month horizon; a move that already happened disqualifies
  only if the driver's change has peaked, stalled or reversed." **New prompts stamp
  `48f6d57f1212ee54/8a4d329193c38172/6cb63ff75ae5f118` from the first L1 after deploy (10-23)** — a new record
  segment. **Tripwire:** ≥ 6 of 12 at the floor on either of its first two sessions ⇒ operator review before the
  third (expected 0–3).
- **Mandate:** the §10.7 tri-criteria thesis-only council (structural ∧ under_narrated ∧ at_inflection at
  ≥ MODERATE). Hard seam, HARK leash, never-backtest-the-council all standing.
- **PREREG_DIRECTION_COHERENCE (FROZEN 2026-09-24):**
  - The rule: a sentinel framed bearish is withheld from the union when its latest filed quarter shows revenue
    growing AND accelerating.
  - Segment boundary: run #1437.
  - **F2 PASSED 5/5 on 2026-09-30.** F1 harm read: h = 126, n ≥ 10. F4: the dated operator review at the 30th
    session (≈ 2026-11-04) if there is still no above-floor conviction.
- **ITM side guard (#276, option 1, 2026-09-29/30):**
  - `convexity_gate.otm_side_guard = true`: the selector never takes a wrong-side contract and fails closed
    when no OTM contract is eligible.
  - Frame boundary: `frame-a6da3dee9171`.
  - The six legacy wrong-side null-book positions are tagged outside-frame; tail reads show with / without.
  - Option 2 (the 15–35% band on the live path) was not adopted.
- **Council pack:**
  - A1 (boundary L1 #1558, 2026-10-05): `council.pack_provenance` — the framer's text is `DISCOVERY_SUMMARY`,
    never `OPERATOR_THESIS`.
  - **A2 (boundary L1 #1575, 2026-10-06) + A2.1 (boundary L1 #1644, 2026-10-12; stamp
    `pack_provenance=provenance_v1+register_thesis_v1.1`):**
    sentinel packs show the basket's operator-adopted `council_thesis` + falsifier (PREREG_UNIVERSE_CURATION
    Rule 0 amendment), with the A2.1 wording on coverage and the falsifier deadline. Running tally after 5
    sessions: consensus-leak 0 · strategist misuse 0 · adversary falsifier misuse 3 (10-13 ×2, 10-16 borderline).
  - `forward_catalysts.sentinel_scope` (channel prereg §11): pins render for sentinels; F-c is a live guard. The
    EPA item (2026-11-16) has been judged irrelevant/non-nuclear seven times running (NEE ×2, CEG ×5), no leak.
- **L1 marker refresh ON (2026-10-16, operator word; PREREG_FRESH_INFLECTION_FUNNEL §7.1a):** `council.marker_refresh
  = "both"` — sentinel price markers recomputed at each L1 and dated, beside the surfacing values. Stamp
  `runs.model_mix.markers = l1_refresh_both_v1` from L1 #1712 (2026-10-16). The §7.1 catch-race trigger still
  reads `hold` (the cheapness-watch panel now says the verdict is moot under §7.1a); adopted on the
  input-quality ground. Session 1: fresh values used as current, 0 surfacing values misread, no verdict flipped.
- **Expressible-first slate ON (2026-10-21, operator word):** `council.demote_unexpressible = true` (#329) — a
  sentinel whose latest fresh gate-of-record read found no structure only backfills empty council slots. Stamp
  `union_rank …+expressible_v1` from the first L1 after deploy (2026-10-21). Membership-only.
- **PREREG_REJECTION_REASON_AUDIT FROZEN (2026-10-21, operator word):** does the timing test filter losers?
  Timing-only vs narration-failed judgments on the miss ledger's big-move definition; first decision read at
  n_T ≥ 30 (≈ February 2027); nothing changes automatically.
- **Frame stamp `frame-3a810daad056` from the first run after #325 (2026-10-19; was `a80e6abea2b9` from #1681,
  10-15).** The hash covers `convexity_book` including the cluster map, so window #10's `cyber_sase` cluster and
  window #11's CF/BWXT additions moved it. Every frozen risk number is unchanged; for the ITM-guard segment it is
  the same regime as `frame-a6da3dee9171`.
- **Window #10 (2026-10-14, operator word):** NTSK admitted (`cyber_sase`, new cluster #16; $395 / 19.2% / 246d at
  the 13:37 read). BNTX ($1,175) and BWXT ($1,100) near-miss over the cap at the 15:07 LAST read; the word lapsed
  for both. BWXT's routing, if it returns, is `nuclear_fuel`. `records/2026-10-14_window10_bntx_bwxt_ntsk.md`.
- **Shared live account (#279, finance#947; PREREG_REAL_MONEY_BROKER §3a):**
  - SPY/XSP/SPX/SPXW rejected on both sides.
  - Restricted-list buys rejected at the order layer.
  - Pre-open foreign-quantity check.
  - Live buys keep options buying power ≥ `safety.shared_account_reserve_usd = 5250` (alpha_options' declared
    max risk).
  - No sizing fallback to account equity.
  - `do-` order ids.
  - Keys are venue-named (`ALPACA_PAPER_*` / `ALPACA_LIVE_*`); legacy names refuse to start.
- **Capital (operator, 2026-10-03):** base stays $100k → **~$10k live funding at T4 arming**, a disjoint slice of
  the shared account. **None now (paper-only).** `records/2026-10-03_shared_account_capital.md`.
- **PREREG_UNIVERSE_CURATION §12:** admission reads must select ≥ 200 days to expiry.
- **x_lists CUT (2026-09-24). Drafter seat KEPT** (CC true-form rewrite; cheapness/momentum clauses struck).
- **Restricted list:** R-001 = LIFE (person-anchored). Min-N pins N₁/N₂/N₃ as ratified 2026-07-15.
- **Closed lines (do not revive without a standalone thesis):** the idea-supply automation line, incl. the
  fundamental-acceleration feed (closed 2026-07-01).

## Staged / pending (the operator's)
- **PROD reboot:** `/var/run/reboot-required` is still set (up since 2026-10-06). Operator's call, away from
  alpha_options' 09:00 / 21:45 UTC jobs and Real Options' trading hours.
- **Homonym guard, acronym class (W42):** the SMR card matched the generic "small modular reactor" acronym and
  Holtec's "Palisades SMR, LLC". CC proposes extending the guard to industry acronyms that equal a ticker.

## Shared hosts (DEV + PROD also run Real Options and alpha_options)
- Our L0/L1/L2 start as `python -u -m orchestrator` (#312): Real Options' `pkill -9 -f orchestrator.py` SIGKILLed
  our L2 on 2026-10-15 14:30. Their side is fixed too (#4953: kill only PIDs whose cwd is their checkout; closes
  rozavala/real_options#4948, promoted 10-16).
- Unit installs: a unit that cannot be installed fails the deploy (#313). PROD (classic sudo) installs with
  `NOPASSWD: /usr/bin/cp /tmp/* /etc/systemd/system/*`; DEV runs **sudo-rs**, which rejects wildcards, so it has
  one exact `NOPASSWD: /usr/bin/tee /etc/systemd/system/<unit>` per unit (`/etc/sudoers.d/dramatic-options-units`,
  #314). **A new unit file needs one more line there**, and the deploy will say so.

## Scheduled reviews (unattended, DEV crontab — 2026-10-22)
- Nightly L1 grade (weekdays 20:37 UTC) and Sunday review (14:23 UTC) run headless via
  `scripts/ops/scheduled_review.sh grade|sunday` (#332) in the runner worktree, under a spend cap with write commands
  denied: the grade is read-only; the Sunday review opens one records PR and never merges. Pushover carries the
  HEADLINE and the resume command. Their expectations come from this file and the newest memory banner — keep both
  current. Cloud routines can't reach the box's DB/journals/memory, so they are not used.

## Dated docket
- **Mon 2026-10-19 — the April-2027 tenor cliff:** AMSC · CC · NNE · PL · STUB · UUUU · ERO · UROY lose structure
  (next listed expiry Jan-2028, outside 180–365d); ATKR has nothing after April; FRO · HBM · TGB · IRDM already
  have none. **Expressible universe ~35 of 48** (43 on 10-16). PL's real Jan-2027 position is unaffected. NTSK's
  first council read can come the same night.
- **2026-10-25 Sunday W43:** re-check for July-2027 listings (the October monthly expired 10-16); KMT pin #17
  expires; marker-refresh week 1 read.
- **2026-11-02:** posture LOOK (PREREG_THEMATIC_CONVEXITY §6 amendment).
- **~2026-11-03:** one-night shadow check of the candidate council models (claude-opus-5-5 / gemini-3.8-flash /
  grok-4.7) on real packs — parse rate, cost, latency only (no outcome scoring).
- **2026-11-05 (after the F4 review):** the planned model refresh, all roles at once, one dated segment; plumbing in
  #331 (`council.anthropic` knobs, refusal routing, unpriced-model guard). Gemini/xAI prices to verify at the switch.
- **2026-11-04:** formerly the F4 date (session 30) — the review was held early on 10-23; a dated look at the
  §10.10 segment's first two weeks instead.
- **2026-11-16:** the EPA rule's effective date (no stay reported; D.C. Circuit petitions pending).
- **~early December:** NTSK's falsifier read (10-Q for the quarter ending 2026-10-31; revenue growth < +20%).

## Board & book
- Box: DEV = main (rebooted 2026-10-17); PROD = `production` (`dd99e5b`), inert (timers disabled, live gate
  closed). Both healthy; units on `-m orchestrator` on both.
- Apps:
  - DEV: `https://all-options-dev.tail57521e.ts.net:8602`
  - PROD: `https://all-options-prod.tail57521e.ts.net:8602`
  - Both are tailnet-only `tailscale serve` → 127.0.0.1:8602; `/api/version` reports the running commit.
- Universe 50 names · 16 clusters (book fills at most 5).
- Book: real 1 (PL, $690, unrealized −$684.50). Null books accruing (shadow · 3A · 3B · shares). Last above-floor
  conviction: run #508, 2026-07-10.
- Open issues: 0. NVDA opra canary back above 1.0 (10-14 1.0127, 10-15 1.0204, 10-16 1.0315) after eight prints below (low
  0.9818).
