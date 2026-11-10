# STANDING STATE — the relay sync header

**as_of: 2026-11-08T15:30Z · supersedes: 2026-11-05T00:30Z · **Sunday W45** (`records/2026-11-08_sunday_w45.md`): **ATKR is delisted** (Atkore taken private: 25-NSE 10-19, 15-12G 10-29) and sat in the 50-name universe, held on every slate → **removed 2026-11-09** (operator word; `records/2026-11-09_atkr_removal.md`; universe 49) · the 09-27 five dormant as docketed; all 8 surfaced bearish (AG/HL back as BEARS; new UROY bear); active 38 · KMT pin #19 lapsed (retired; August Comtrade now $32.54/kg, so its fact changed anyway) · expressible 34 of 50 on the Sunday probe (35 nightly), the 15% floor took BWXT/KLAR/NOC; **the 11-23 cliff now costs 7 names (→ ~27)** · miss sweep #8 = the floor boundary · #434 → #435 (dual-read page judges the current session) and #431/#432/#433 since 11-05 · DEV + PROD rebooted 11-07 (operator apt upgrade) · 1 open issue (#421). On top of the 11-05 header (15% floor adopted, restate_v1 staged for ~11-12, the two-week look, backfill live, first carry fills).**

Maintained by CC; updated on every ruling, clock change, staged-PR change, or pending-act change.
**Relay rule (both directions): a strategy question or advice arriving WITHOUT this header, or carrying an
`as_of` older than the latest ruling, is treated as UNSYNCED — verify against the record before acting.**
The header's absence is itself a signal.

## Rulings in force
- **Minimum moneyness 15% (2026-11-04, operator word "Adopt both the 15% floor and A+B+C at the 11-12 boundary";
  #416; PREREG_THEMATIC_CONVEXITY minimum-moneyness amendment + PREREG_FIXED_BASKET_NULL note; from the first L1 after
  deploy):** `convexity_gate.min_otm_moneyness = 0.15`. Every book and gate path admits only contracts ≥ 15% OTM
  (achieved, thesis side) and fails closed otherwise. Found at L1 #1918 (TITN's backfill fallback to C25, 7% OTM).
  **Frame boundary `frame-f86f37a0bd4f` → `frame-880e893e1660`.** Survivor cards (own 15–35% band) are consistent;
  the weekly sweeps apply it from the **2026-11-08 sweep** (#427, operator word 2026-11-05; PREREG_MISS_BASERATE §8,
  PREREG_UNIVERSE_CURATION §6). Slate effect: 5–7 of 38
  gate-of-record wings were below 15% on 11-04 (all cheap); each re-selects farther or becomes unexpressible.
- **Persistence watch (2026-11-04, the two-week look; measurement only, adopted with its merge; AMENDED 2026-11-09,
  operator word, `records/2026-11-09_persistence_watch_amendment.md`):** the nightly grade reports, for each real
  entry, the strategist's verdicts at the same name's **next 3 reads**. The entry **persisted** if the majority (≥ 2 of
  3) are still ≥ the floor, or for a backfill `include = true` at ≥ LOW. It is decided as soon as 2 reads agree.
  (Before 11-09 this was a single next read, which proved too noisy: FLNC and TITN flipped criteria back on unchanged
  filings at #1969.) Recount under the amended rule: 0 of 2 measurable persisted (HL #1816 and FLNC #1918, each LOW on
  all 3 next reads), and TITN's backfill reversed (decided at #1952). **Pinned trigger (unchanged):** fewer than half
  of the first 5 real entries persist ⇒ a dated operator look at a confirmation-read rule (which must settle whether
  a carry waits for the next L1). No rule changes.
- **Ranked backfill ENABLED (2026-11-03, operator word; `records/2026-11-03_backfill_enabling.md`; in force from the
  first L1 after the enabling PR deploys):** `convexity_book.backfill.enabled = true` with the PREREG §5 amendment
  2026-11-03 values. When the book has held ≤ 5 committed slots for 28 days (true now), the L1 sends the top 3
  ranked non-floor structural proposals (conviction ≥ LOW) to the unchanged gates after every above-floor name;
  at most 1 backfill entry per trailing 7 days; positions carry `origin = backfill`; stop rule pre-stated.
  **Frame boundary `frame-3a810daad056` → `frame-f86f37a0bd4f`.** Reads: the first week nightly, then a dated look
  after 4 entries or 6 weeks.
- **Operator decisions 2026-11-01 (operator word; `records/2026-11-01_operator_decisions.md`):**
  - **KMT forward-catalyst pin RETIRED at expiry:** pin #19 **lapsed 2026-11-08, not re-pinned** (W45 reported it;
    Comtrade's August print, $32.54/kg vs July's $37.98, had changed the fact anyway). It rendered into no council prompt (KMT is neither a universe name nor a sentinel).
  - **NRC 2026-21801 reviewed, NOT pinned:** procedural, no expressible name (NNE unstructured, BWXT a bearish
    lineage), short pin life.
  - **Model refresh moved from 11-05 to ~11-12**, so it doesn't land inside §10.11's first sessions (see docket).
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
- **Quote filter: rendered ISO dates accepted (2026-10-31, operator word "A"; #403; PREREG_FORWARD_CATALYST_GROUNDING
  §12; from the first L1 after deploy, planned Mon 11-02):** a council role citing a full ISO date its prompt block
  showed (a fundamentals `period`/`filed` date, a catalyst or marker date) is no longer dampened; an unshown date
  flags once (`unsupported date: …`). The figure pool stays date-free; the discovery framer is unchanged. Found at
  L1 #1884 (FRO adversary 6 flags = a verbatim fundamentals line; SMR strategist on a cited filing date); 47 of 179
  dampened strategist outputs cite a date, none raw ≥ MODERATE. Stamp `runs.model_mix.quote_filter =
  musd_billions_v1+iso_dates_v1`, record-segmenting (final convictions change; raw ones don't); the §10.11 read is
  taken on raw and final convictions so the two stay separable. #402 (merged 10-31) now stores which claim flagged.
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
- **Profit program (operator word 2026-11-03; `records/2026-11-03_profit_program_DRAFTS.md`; merged as
  rozavala/dramatic_options#411, DEV deploy green 11-03; D3 step 2 follows on the same branch):** D0 execution ledger, D4 IV history (+ nightly `iv_term_snapshot`),
  D3b falsifier ledger (CC-encoded specs; **operator 2026-11-06:** bnpl_payments dropped as unreadable — KLAR has no XBRL quarterlies — and KKR's alt_capital kept as written, noted that GAAP `Revenues` includes investment income; FIG, STUB, NTSK still to confirm; the first read, FIG, has a correction note, #429) are telemetry; **D1 ranked backfill is
  LIVE since 2026-11-03** (#415, operator word; frame `f86f37a0bd4f`; first entry TITN #7, filled 11-04 via carry;
  weekly quota frees ~11-10); **D3 over-cap verticals built and inert**
  (PREREG §5 amendment 2026-11-03b; migration 0021) until the switch-on checklist in the drafts record (paper
  multi-leg smoke round-trip first) and a dated `convexity_gate.vertical_for_over_cap.enabled = true` edit. Calibration v2 (blind, 2026-11-03): J confirmed, S/R/T not candidates,
  V candidate (`records/2026-11-03_calibration_v2_finding.md`).
- **Review crontab vs DST — resolved without a crontab change (#341, 2026-10-25):** `scheduled_review.sh` now waits for
  the run it reviews (today's `dramatic-options-l1` / `-reach` exit, up to 120 min, then a "NOT RUN" page). From 11-01
  the Sunday review (14:23) waits for the 14:40 reach run, and from 11-02 the grade (20:37) waits for the 20:45 L1.
  **Sun 11-01: PASSED; Mon 11-02: PASSED** (the grade waited for the 20:45 L1); Sun 11-08 read the 14:41 cards.
- **BNTX (bench Tier A):** $930 / 19.2% / 235 d on the 10-25 Sunday quote, but **`no_otm_eligible_contract_in_tenor_window`
  on the 11-01 Sunday read** — the in-band read did not hold. Returns only on a fresh operator word and a mid-session read.
- **HL / AG / PAAS (silver_deficit; HL above floor 10-26 #1816, AG above floor 10-29 #1867, both cancelled unfilled
  before carry-over):** all three went dormant at the 11-01 L0 (last seen 09-20); they return only if re-surfaced.

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
- **2026-11-02:** posture LOOK (PREREG_THEMATIC_CONVEXITY §6 amendment). (The driver-scope decision it also held was
  taken early, on 10-29: §10.11.) Also the first L1 under `iso_dates_v1` (#403; read raw and final), and NEE's first
  read since re-surfacing (event leg: a SCHEDULE 13D/A filed 10-27; #340 refetch due on its 10-21 10-Q).
- **2026-11-03:** May-2027 contracts (201 d on 11-01) fall under §12's 200-day admission runway (admission reads only).
- **~2026-11-03:** one-night shadow check of the candidate council models (claude-opus-5-5 / gemini-3.8-flash /
  grok-4.7) on real packs — parse rate, cost, latency only (no outcome scoring).
- **~2026-11-12 (moved from 11-05 by the operator, 11-01):** the planned model refresh, all roles at once, one dated
  segment, after §10.11 has ~10 sessions; plumbing in
  #331 (`council.anthropic` knobs, refusal routing, unpriced-model guard). Gemini/xAI prices to verify at the switch.
- **2026-11-04: DONE**, the two-week look (`records/2026-11-04_council_two_week_look.md`); its persistence watch
  (amended 11-09: majority of the next 3 reads) is read when the 5th real entry is decided.
- **Sun 2026-11-08: DONE** (W45): the 09-27 five went dormant (none re-surfaced); KMT pin #19 lapsed, not re-pinned.
- **Owed (operator, from W45):** the thesis-as-direction class (MOS, KKR). ATKR's removal: **decided 2026-11-09**
  (`records/2026-11-09_atkr_removal.md`, scan basket only; #437 files the empty-chain mislabel).
- **~2026-11-10:** the backfill's weekly quota frees.
- **2026-11-16:** the EPA rule's effective date (no stay reported; D.C. Circuit petitions pending).
- **Mon 2026-11-23:** May-2027 drops under the gate's 180-day floor, on the first session after the November monthly
  expires (Fri 11-20). Re-read on W45 (11-08): nine names select May-27 today; SMCI and LMT have Jun/Sep-27 wings;
  **FLNC/FLY/LHX/RDW/TGB/UEC have only Jan-2028 after May, KTOS Dec-2027** → if no Aug-2027 quarterly lists, those
  7 lose structure (KTOS to ~12-17, the rest to ~2027-01-21) and **expressible falls ~34 → ~27** (the old 39 → ~31
  predates the 15% floor). Read which list Aug-2027, plus the nightly `record_ok`.
- **2026-11-25:** the NRC DOE/DoW-design rule's effective date (reviewed, not pinned — 11-01 decision).
- **~2026-12-19:** TITN's only in-window expiry (Jun-2027) drops under 180 days unless Sep-2027 lists (held #7 is
  Jun-27; exits unaffected).
- **~early December:** NTSK's falsifier read (10-Q for the quarter ending 2026-10-31; revenue growth < +20%).

## Board & book
- Box: DEV = main `2d3a85a` (#435, deployed 11-08 01:02 UTC; **rebooted 2026-11-07 19:24 UTC** after the operator's
  apt upgrade); **PROD = `a7548e8` (#392, promoted 2026-10-30 04:21 UTC; 31 merges / 24 PRs behind main on 11-08, incl.
  the profit program #411–#415 and the 15% floor #425; rebooted 2026-11-07 19:39 UTC)**, inert: timers disabled, `LIVE_TRADING_ENABLED=false`, `DRY_RUN=true`, `FORWARD_ENABLED=false`
  (its `.env` carries `PAPER=false`; the triple gate stays shut on the other two). Rebooted 2026-10-18. Both healthy
  (0 failed units); units on `-m orchestrator` on both; Real Options `trading-bot` active on PROD. PROD's journal is readable by the review user from 2026-11-03 (`systemd-journal`). PROD's first #392 deploy failed at `git fetch` (a stale `origin/claude` tracking ref blocked `claude/*` branches); pruned with the operator's go, deploy re-run green.
- Apps:
  - DEV: `https://all-options-dev.tail57521e.ts.net:8602`
  - PROD: `https://all-options-prod.tail57521e.ts.net:8602`
  - Both are tailnet-only `tailscale serve` → 127.0.0.1:8602 (the React/FastAPI dashboard; the Streamlit :8601
    dashboard is retired, 2026-10-06). `/api/version` reports the running commit; `/api/status` is the light
    cached read (verdict, heartbeats, KILL, drawdown vs halt, book, last council, T4 — under 5 KB, no positions).
- Universe **49 names** from the first run after the 2026-11-09 removal (ATKR delisted 2026-10-19, Atkore taken
  private; `records/2026-11-09_atkr_removal.md`; it stays in the frozen `ai_capex_power` cluster for its open
  null positions) · 16 clusters (book fills at most 5). Expressible 34 of 50 on the 11-08 Sunday probe (35 on #1969's `record_ok` and sweep #8; no
  structure AMSC/ATKR/BWXT/CC/FRO/HBM/IRDM/KLAR/NNE/NOC/NXE/PL/SMR/STUB/UROY/UUUU — BWXT/KLAR/NOC on the 15% floor).
  Active sentinel lineages 38 (11-08).
- Book: real 3 open, $2,470 (marks at the 11-06 L2: PL 0.015, FLNC 1.35, TITN 2.105; unrealized ≈ −$474, DD ~5%): PL ($690), FLNC #6 10× `FLNC270521P00005000` @ 1.00 ($1,000, filled
  11-04 via carry from #1918), TITN #7 3× `TITN270617C00030000` @ 2.60 ($780, backfill, filled 11-04 via carry);
  unrealized ≈ −$750, drawdown 8%. Null books accruing (shadow · 3A · 3B · shares; CF booked 11-04). **Last above-floor
  conviction: run #1918, 2026-11-03 (FLNC MODERATE)**; before it #1867 (AG) and #1816 (HL), both cancelled unfilled.
- Open issues: #421 (filter restatements; adopted 11-04, its PR #426 lands on the ~11-12 boundary); #444 (pre-T4
  audit: a real option left at the broker through expiry, auto-exercise not modelled; lane:profit). #445
  (expiry-while-closing settles the cancel) and #446 (this simplification) close with their PRs. As of 2026-11-10;
  no count is kept (#446): `gh issue list` is the source.
  Closed 11-10: #437 by #441 (an empty chain reports `empty_chain`), #440 by #442 (a raising price lookup is
  per-position in the real monitor and both null books; a stuck real-book expiry pages once a day).
  Closed: #416 by #425 (merged 11-05, frame `880e893e1660`), #427 by #428, #429 by #431, #430 by #432, #434 by #435.
- NVDA opra canary at or above 1.0 for 18 prints (11-06 1.1324) after eight below (low 0.9818).
