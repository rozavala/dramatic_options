# STANDING STATE — the relay sync header

**as_of: 2026-10-27T05:30Z · supersedes: 2026-10-25T15:00Z · L1 #1816 (10-26): the §10.10 tripwire cleared on both
sessions · HL the first above-floor verdict since #508, ordered and cancelled unfilled · W43's four issues fixed
(#340, #341, #342, #343) · the driver-scope count (#348) · order quotes + pages (#350) · the carry-over proposal
(#349, awaiting the word) · **PROD promoted to `2892d64` (#356)**. On top of the W43 Sunday review
(`records/2026-10-25_sunday_w43.md`).**

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
  third (expected 0–3). **CLEARED:** 10-23 #1798 0/12 (raw 1); 10-26 #1816 1/12 (HL), raw and final alike.
- **Quote filter: $B restatements pooled (2026-10-24, operator word; #336; from the first L1 after deploy):** the
  authenticity filter's evidence pool also carries each rendered $-figure ≥ $1,000M in billions (1/2 decimals; gross
  margin excluded). Found at L1 #1798 (PWR strategist MODERATE → LOW on `$33.55B` for the rendered `$33550.0M`; FLNC
  `$6.4B`). Stamp `runs.model_mix.quote_filter = musd_billions_v1`, record-segmenting (final convictions change; raw
  ones don't). The §10.10 tripwire is read on both raw and final convictions so the two changes stay separable.
- **Analyst-coverage meter RESTORED (2026-10-24, operator word; #337/#338; from the first L1 after deploy, planned
  Mon 10-26):** stockanalysis.com's `/api/symbol/s/{T}/overview` has 404'd since ~07-10, so no council pack carried
  the §19 `ANALYST_COVERAGE` line for three months; sentinel packs fell back to `NEWS_COVERAGE: N article(s)` where
  N was the marker-line count (15 for every name on #1798), and the agents read it as press coverage, both ways.
  The meter now reads `/stocks/{t}/__data.json` (same buckets; 46/47 recent names resolve, TGB has none); a wired
  meter that returns nothing renders `ANALYST_COVERAGE: unknown`, never the marker count. Stamp
  `coverage_meter = analyst_v2` (v1 stamped through the outage); L1 log line `Coverage meter: analyst counts n/m`
  (0 hits is a WARNING). **Record consequence:** every segment from ~07-10 to 10-23 judged `under_narrated`
  without the meter (the F4 pack's 44% included). **Tripwire:** Monday is also §10.10's second session, so its
  read carries both changes; restored counts are more likely to tighten `under_narrated` than loosen it.
- **⭐ Criterion (3), name-level evidence (2026-10-29, operator word "adopt 388"; PREREG_COUNCIL_GATE_SEPARATION
  §10.11; adopted ahead of the 11-02 look):** one sentence appended to (3): *"The driver must still be visibly
  changing in THIS name's own current evidence — its fresh price markers or its latest filing; the basket's story
  alone does not show it, and a stale or annual-only figure cannot establish acceleration."* It followed the
  driver-scope count reaching 3 on 10-29 (HL, AG, PAAS; all silver_deficit). New pins `cd34e754aa48ca09 /
  98f11177de0612e0 / bc33c3e2dd66f0e4`; `runs.model_mix.prompts` changes from the first L1 after deploy (planned Fri
  10-30): a new record segment. Expected: fewer above-floor verdicts than 10-23 → 10-29 (2 in 5 sessions); zero at
  the floor for 10 consecutive sessions ⇒ an operator look.
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
- **OTM side guard everywhere the gate is measured (2026-10-25, operator word; #343/#345):** the feasibility probe
  (§2 admission reads) and the survivor cards' band axis now select as the gate of record does. The two weekly
  sweeps were aligned by dated amendments (PREREG_MISS_BASERATE §7; PREREG_UNIVERSE_CURATION §6 amendment). The
  boundary is the **2026-11-01 sweep**; earlier rows/aggregates stay as written. A test keeps every
  `select_structure` caller on the guard (exempt: two evidence copies, one one-off measurement).
- **Sentinel TTL by ET scan date (2026-10-25, operator word; #342):** `expire_stale_sentinels` compares US-Eastern
  calendar dates (dormant when the date last seen < the run's date − 35 days), not wall-clock seconds. A lineage
  now lives a fixed 5 missed weekly scans (dormant at the 6th) whatever the start-second jitter or DST. No
  retroactive change: 10-25's seven dormancies hold under the new rule. Membership-relevant from the 11-01 L0.
- **Corpus refetch on filing (2026-10-25, operator word, option b; #340):** at L1 a name's SEC companyfacts raw is
  refetched when it was fetched on or before the ET date of the name's newest 10-Q/10-K/20-F/40-F on EDGAR, whatever
  its age (the 7-day policy otherwise unchanged). A same-day fetch is retried the next day and then stops, so an
  upstream gap (NEE) costs at most two extra fetches per filing. Found: RTX/NOC sat on Q2 for ~8 days after their
  10-20 10-Qs. Stamp `runs.model_mix.corpus_refresh = filing_date_v1` from the first L1 after deploy,
  record-segmenting (fresher packs); L1 log `Corpus refetch on filing: n (…)`. The staleness telemetry stays
  telemetry.
- **Carry-over ON (2026-10-29, operator word; #386/#387, #349 §4):** an L1 entry still unfilled at the close is
  re-gated through the full entry pipeline and resubmitted the next NYSE trading day from 10:00 ET, its limit walking
  from mid to the ask in ⅓ steps hourly (the ask from 13:00), cancelled at 15:30 ET (close − 30 min on a half day);
  one carry per approval. Pages: ORDER CARRIED / SUBMITTED / FILL / NOT FILLED. Every cancel is settled (a partial
  fill opens the filled quantity), and a name with a working order is never entered twice. The real book's entry
  price and date can now differ from the L1's. Execution only; `frame_version` unchanged.
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
- **Review crontab vs DST — resolved without a crontab change (#341, 2026-10-25):** `scheduled_review.sh` now waits for
  the run it reviews (today's `dramatic-options-l1` / `-reach` exit, up to 120 min, then a "NOT RUN" page). From 11-01
  the Sunday review (14:23) waits for the 14:40 reach run, and from 11-02 the grade (20:37) waits for the 20:45 L1.
  First live checks: Sun 11-01 and Mon 11-02.
- **BNTX (bench Tier A):** $930 / 19.2% / 235 d on the 10-25 Sunday quote — in band, under the cap. Returns only on a
  fresh operator word and a mid-session read.
- **NRC 2026-21801 (effective 2026-11-25, DOE/DoW-authorized reactor designs in NRC licensing):** a class-(a)-shaped
  pin suggestion for `nuclear_fuel` (BWXT / NNE); unpinned — the operator's read.
- **Entry carry-over (#349, proposal; `records/2026-10-27_entry_carryover_proposal.md`):** an unfilled L1 entry gets
  one more session (re-gate on fresh quotes from 10:00 ET, a bounded limit walk, cancel 15:30 ET; working orders
  reserve the book-level caps). Nothing built; **§4's parameters await the operator's word**. Until then an
  above-floor entry gets the ~12 minutes between the 15:45 L1 and the close (DAY order); #350 pages it either way.
- **HL (above floor 10-26, #1816):** cancelled unfilled; re-judged at each L1 this week; dormant at the 11-01 scan
  unless it re-surfaces (last seen 09-20). Its verdict seeds the driver-scope count.

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
- **Tue 2026-10-27 (tonight):** the first L1 with order quotes logged and order pages (#350); the grade's first
  driver-scope count (seed 1). HL's second read under §10.10.
- **Sun 2026-11-01 (L0 at 13:00 UTC after DST):** TTL by ET date (#342) ⇒ **8 lineages go dormant unless
  re-surfaced** (last seen 09-20: AG, AMSC, HL, KLAR, KTOS, PAAS, RDW, VIAV); the 09-27 five (ATKR, CDE, FLY, FRO,
  STUB) run to 11-08 (the DST hour no longer costs them a scan). The union 35 → ~27 + new.
  KMT pin #18 expires. Tenor: the cliff names regain structure only with a July-2027 listing or when Jan-2028 enters
  the window (~2027-01-21).
- **2026-11-02:** posture LOOK (PREREG_THEMATIC_CONVEXITY §6 amendment). (The driver-scope decision it also held was
  taken early, on 10-29: §10.11.)
- **~2026-11-03:** one-night shadow check of the candidate council models (claude-opus-5-5 / gemini-3.8-flash /
  grok-4.7) on real packs — parse rate, cost, latency only (no outcome scoring).
- **2026-11-05 (after the F4 review):** the planned model refresh, all roles at once, one dated segment; plumbing in
  #331 (`council.anthropic` knobs, refusal routing, unpriced-model guard). Gemini/xAI prices to verify at the switch.
- **2026-11-04:** formerly the F4 date (session 30) — the review was held early on 10-23; a dated look at the
  §10.10 segment's first two weeks instead.
- **2026-11-16:** the EPA rule's effective date (no stay reported; D.C. Circuit petitions pending).
- **~early December:** NTSK's falsifier read (10-Q for the quarter ending 2026-10-31; revenue growth < +20%).

## Board & book
- Box: DEV = main `4e94c2d` (up since 2026-10-17); **PROD = `2892d64` (#356, promoted 2026-10-27 05:14 UTC — level
  with main)**, inert: timers disabled, `LIVE_TRADING_ENABLED=false`, `DRY_RUN=true`, `FORWARD_ENABLED=false`
  (its `.env` carries `PAPER=false`; the triple gate stays shut on the other two). Rebooted 2026-10-18. Both healthy
  (0 failed units); units on `-m orchestrator` on both; Real Options `trading-bot` active on PROD.
- Apps:
  - DEV: `https://all-options-dev.tail57521e.ts.net:8602`
  - PROD: `https://all-options-prod.tail57521e.ts.net:8602`
  - Both are tailnet-only `tailscale serve` → 127.0.0.1:8602 (the React/FastAPI dashboard; the Streamlit :8601
    dashboard is retired, 2026-10-06). `/api/version` reports the running commit; `/api/status` is the light
    cached read (verdict, heartbeats, KILL, drawdown vs halt, book, last council, T4 — under 5 KB, no positions).
- Universe 50 names · 16 clusters (book fills at most 5). Expressible 39 of 50 (10-25; no structure AMSC/ATKR/CC/
  FRO/HBM/IRDM/NNE/PL/STUB/UROY/UUUU). Active sentinel lineages 35 (10-25).
- Book: real 1 (PL, $690, unrealized ≈ −$681 on 10-26). Null books accruing (shadow · 3A · 3B · shares). **Last
  above-floor conviction: run #1816, 2026-10-26 (HL MODERATE)** — real order #2, 5× `HL270617C00017000` LIMIT 1.76
  ($880), cancelled unfilled at the 16:00 L2; before it, #508 (2026-07-10).
- Open issues: 6, all dashboard/API read-only (filed 2026-10-27): #351 "why no entry" per name · #352 Edge tails
  in-frame first · #353 cached `/api/status` + docs call :8601 retired (PR #361) · #354 ET date + STALE chip on run ids · #355 display-only
  10% drawdown warn + T4 condition 5 · #357 `GET /api/hub` (the hub's shared status contract; pairs with #353).
  W43's #340–#343 are fixed (#344–#347).
- NVDA opra canary at or above 1.0 for 9 prints (10-26 1.0535) after eight below (low 0.9818).
