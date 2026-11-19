# STANDING STATE — the relay sync header

**as_of: 2026-11-15T15:30Z · supersedes: 2026-11-08T15:30Z · **Sunday W46** (`records/2026-11-15_sunday_w46.md`): **the §10.11 floor-drought clock was 8 of 10 at 11-13 → the pinned operator look is owed after Tue 11-17 if Mon and Tue are 0 at the floor** · **TITN's lineage went dormant on TTL while TITN #7 is held** (the #464 gap; the slate will likely stop reading it) · L0 #2058 scanned 49, 6 re-surfaced (CDE/PAAS/STUB/FLY/KLAR bears, FRO bull), 0 new, 4 dormant (FCX/MOS/MRK/TITN); active 40 · RDW filled 11-13 as backfill #13 ($950) after a carry veto and a re-entry; first read include=false · expressible 35 of 49 on the Sunday probe; **the 11-23 cliff still costs 7 names (now BWXT/FLNC/FLY/KTOS/RDW/SMR/UEC → ~28)**; no Aug-2027 listing · miss sweep #9, the first like-for-like under the floor (universe 30/28, market 30/28) · no pin expired; EPA rule effective 11-16, no stay · **DEV + PROD both reboot-required since 11-13 (libc6)** · PROD `29a86e4`, 7 PRs behind. On top of the 11-12/11-14 rulings (kill rule, boundary B, the #456 probe Arm A).**

Maintained by CC; updated on every ruling, clock change, staged-PR change, or pending-act change.
**Relay rule (both directions): a strategy question or advice arriving WITHOUT this header, or carrying an
`as_of` older than the latest ruling, is treated as UNSYNCED — verify against the record before acting.**
The header's absence is itself a signal.

## Rulings in force
- **Operator decisions on the roadmap drafts (2026-11-12; `records/2026-11-12_operator_decisions_roadmap.md`):**
  - **Kill rule made operational** (#465, #472; PREREG_THEMATIC_CONVEXITY §6 conformance notes and §5 reading note):
    - **Dry leg:** runs from the first real fill (2026-07-01) and resets on a real close with `realized_pnl > 0`. It
      binds **2027-04-01** absent a payoff.
    - **Drawdown leg:** the cumulative net loss since 2026-07-01 (realized + unrealized) ÷ $10,000.
    - **R2:** the 10% book is premium committed at any moment.
    - **Effect of a trip:** it halts the real book and the council, and **the null books keep booking**. KILL still
      halts all. Release is by a payoff or a mark recovery.
    - **Code: merged 2026-11-12** (#487: the dry leg, the cumulative drawdown leg, null books keep booking; #489:
      L0 scans on a trip, the re-anchor keys). Thresholds are unchanged, and so is `frame_version`. Live readout at
      merge: drawdown 1.8%, dry since 2026-07-01, binds 2027-04-01. (Corrected 2026-11-17, #515: this line said the
      code would land by 12-25.)
    - **Second word 2026-11-12 ("accept all"):** L0 keeps scanning on a trip (framer included). The re-anchor keys
      (`dry_clock_reanchored_on`, `drawdown_reanchored_on`) are built (#489) and written only on the operator's word;
      each is a frame boundary.
  - **Scheduled record boundary B** (#470): record-segmenting changes (a `frame_version`, prompt-hash, model or
    `model_mix` move) land on **the first Monday L1 of each month**, deployed the weekend before its Sunday L0.
    - **Next:** Mon **2026-12-07**.
    - **Off-cycle, recorded the same day with its reason (worded 2026-11-12, "accept all"):** a money-safety defect, a
      fail-closed outage, or a frame-conformance defect (the #276 class).
    - **Exempt and staging:** as drafted (#470). Config-gated changes ship default-off; prompt and constant-stamp
      changes stay as draft PRs.
    - **Tooling:** the segment register only, with no CI fingerprint check.
    - **Model refresh:** it rides 12-07 only if its PR and the Gemini/xAI price checks are ready. restate_v1 (#426)
      was the last unscheduled boundary (11-12).
  - **T4 conditions (2) = 2B, (4) = 4A** (#468; IMPLEMENTATION_PLAN dated note). **No live arming.**
    - **Decision 2:** the mechanics rows are adopted.
    - **Decision 3:** the ceiling bounds opening orders only (PREREG_REAL_MONEY_BROKER §3b, #473).
    - **Decision 6:** the live smoke is deferred.
    - **Rehearsal:** a separate paper account, a separate Pushover app token, shared LLM keys, and a starting DB
      copied from DEV on a Friday after the 16:00 L2 with no pending or carried rows.
  - **PROD `.env` verified 2026-11-12:** `PAPER=false` with the live pair only (no paper pair, no legacy names),
    `LIVE_TRADING_ENABLED=false`, `DRY_RUN=true`, `FORWARD_ENABLED=false`, code `a7548e8`. DEPLOYMENT.md is corrected.
  - **Backfill and `include=false` (RDW):** decided at #456's look.
  - **The remaining #476 drafts, in priority order:** (1) #456, the cheaper arm; (2) #455 and #462; (3) #464, option B;
    later #453, #460, #457, #459 and #461.
  - **PROD promoted, inert:** #491 (`29a86e4`, 2026-11-12 05:50 UTC), verified read-only on 2026-11-14 (board below).
  - **Authorized but not done:**
    - an inert arming PR, a draft only;
    - a 1-week paper rehearsal on a **separate paper account**.
  - **#469 deferred.**
- **Operator word 2026-11-18, second ("merge and follow your suggestions on the rest"):**
  - **#455 frozen as `PREREG_CHEAP_THEN_REPRICED.md`** (with #453's shared-data rows folded in), every §11
    recommendation adopted: the nightly term record gains `rv63`/`rv21` and quotes for the tracked contracts (the
    selected wings plus every open position's contract; no new fetch, no migration, inside the sink's try/except so it
    can never change the gate read); universe cohort only; rows from the first sweep after the capture deploys (wings
    over 40% OTM excluded); primary outcome the mid multiple; splits E1 (cheapest `iv_rv` tercile) primary, E2 (RV63 >
    1.2 among passes) secondary, E3 counts only; horizons 21/42/63 sessions; guard ≥ 20 rows and ≥ 8 names; derived at
    read time, no ledger file. Telemetry: no stamp, so neither boundary B nor the 12-07 → 12-18 freeze holds it.
  - **#462 frozen as `PREREG_CONVEXITY_REGIME_SERIES.md`**, every §11 recommendation adopted: the series of record is a
    270-day constant-maturity IV ÷ RV252 from the term record (frame-independent), population R frozen at 49 names,
    derived at read time, first percentile ~2027-04-27; built with #455's capture as one telemetry PR. The
    `market_context` mislabel is a separate small fix (#529).
  - **#457 (gate graduation) moves to the first #455 outcome read, ~2027-01-17** (no #455 outcome can exist by 12-18;
    the 12-18 look gets #455 exposure counts only).
- **Operator word 2026-11-18 ("Aligned with your suggestions"), on CC's recommendations for the open decisions:**
  - **#471 — held names leave the backfill pool** (PREREG_THEMATIC_CONVEXITY backfill conformance note). Boundary B, 12-07.
  - **#477 — the null books skip profit-take and time-stop on closed-market ticks**, as the real book does since #451
    (PREREG_FIXED_BASKET_NULL conformance note; a `model_mix` stamp). Boundary B, 12-07.
  - **#444 — an unsellable real position stays open, tagged `orphaned`** (PREREG_REAL_MONEY_BROKER §3c), re-tried each
    open tick, settled through the venue-checked expiry path. Boundary B, 12-07.
    **Landed OFF-CYCLE (operator word 2026-11-19, "Sure"; boundary B's money-safety class):** on 2026-11-18 a junk
    opening quote marked real-book #13 (RDW $6 put) at 10.10, and the old unsellable path booked a phantom +$9,150
    in-DB close while the broker still held the contracts (#533 mark bound; #534 journal repair). #527 carries no
    `model_mix` stamp, so the 12-07 → 12-18 probe freeze is unaffected. The broker's auto-exercise policy is
    to be confirmed from its docs before T4.
  - **Rehearsal:** #466 (exit drill) and #463 (spread round-trip) run on the separate rehearsal paper account, not the DEV
    paper book; #467's live smoke stays deferred until arming. **Waiting on the operator to create the rehearsal paper
    account and its Pushover app token.**
  - **Roadmap order:** draft #455 (cheap-then-repriced, with #453's scoreboard folded in) and #462 (the regime series)
    now; #457 (gate graduation) is decided after the §10.12 look (12-18) with #455 data; #459, #460 and #461 deferred.
  - **#470's segment register** (decided 2026-11-12) is built now.
  - **Sequencing for boundary B (from the #525–#527 review):** the §10.12 probe stops its segment for good on ANY
    `runs.model_mix` change after its first session. #525 adds `model_mix.backfill` and #526 adds `model_mix.null_exits`,
    so both must be **deployed and stamping before the Mon 12-07 L1** (merge on 12-05/06, as planned). **Stamp freeze
    12-07 → 12-18:** nothing that adds, removes or changes a `model_mix` key lands during the probe segment, and the
    backfill block is not toggled (it gates #525's key).
- **Operator word 2026-11-16 ("Sure, let's keep moving with your recommendations"):**
  - **Floor-drought look, decided in advance: A** (PREREG_COUNCIL_GATE_SEPARATION §10.11a). §10.11 unchanged; a second
    10-session drought after 12-18 triggers another look. **Applied 2026-11-17** (the clock hit 10/10 at L1 #2090). `records/2026-11-16_floor_drought_look_decision.md`.
  - **Held-name tracking, Option B** (#464; §10.13; `records/2026-11-16_held_name_thesis_tracking_optionB_PREREG.md`):
    a post-L1 pass re-reads every held position nightly into `held_reads`; starts with the first L1 after its code
    merges; cap $1.00 per pass. Measurement only.
    **Scoring pin (2026-11-17, operator word "Merge and on 508 let's follow your suggestion"; #508):** a `dropped` read is excluded from "the last 3"; the last 3
    non-dropped reads decide, and drops are counted beside the table.
  - **#505, the slate's date-aware demotion: approved, then WITHDRAWN by CC before any code (2026-11-16).** The sweep
    stores only the selected wing, not the name's other expiries, so the check would also demote names with another
    in-window expiry (LMT Jun/Sep-27, NXE Aug-27 on 11-23). That breaks the 2026-10-21 ruling's "positive, fresh
    evidence" principle to save at most one night of slots. Proposed instead: close #505 as a complexity-cut; the
    11-23 sweep corrects the slate from 11-24.
  - **The post-L1 unit:** the §10.12 probe and the §10.13 pass share one unit, `dramatic-options-post-l1`.
  - **#504 (moneyness ceiling):** decided later the same day: 40% at the 12-07 boundary (entry above).
- **Council repeat-read probe, Arm A (2026-11-14, operator word "Ok sure let's follow your recommendations"; #456;
  PREREG_COUNCIL_GATE_SEPARATION §10.12; `records/2026-11-14_council_repeat_probe_armA_PREREG.md`):** measurement only.
  - The strategist is re-asked 5× per name on the same night's pack and debate, by a separate unit after the L1.
  - Segment: L1s Mon **2026-12-07 → Fri 12-18** (10 sessions), switched on at the 12-07 boundary. The code ships
    before then, default-off (`council.repeat_probe`).
  - Read 1: < 70% majority match among ≥ 5 floor-contact names ⇒ a dated look at a k-read entry rule. Read 2:
    < 80% `include` majority match ⇒ a lone `include=false` read does not reverse an entry.
  - The look after 12-18 settles the RDW backfill `include=false` question and carry confirmation.
  - Caps $1.50 per session and $15 total; probe spend counts in the monthly page's MTD; the anthropic page is **$20
    for December 2026** (back to $10 in January, a dated edit).
- **Quote filter restatements, restate_v1 (adopted 2026-11-04, operator word "Adopt both the 15% floor and A+B+C at
  the 11-12 boundary"; #421; PREREG_FORWARD_CATALYST_GROUNDING §13; IN FORCE FROM THE FIRST L1 AFTER THE 2026-11-12 DEPLOY;
  operator 2026-11-12 "merge it": lands alone, ahead of the model refresh, which takes its own boundary):** council roles only. A: rendered signed 3-decimal figures pool their
  percent form (−0.628 → 62.8). B: $B to 3 decimals. C: the bare year of a rendered date. D (rounding, bps) is not
  adopted. Stamp `quote_filter = musd_billions_v1+iso_dates_v1+restate_v1` from the first L1 after deploy.
- **Maximum moneyness 40% (2026-11-16, operator word "merge and let's use your calls on the other pending ones"; #504; PREREG_THEMATIC_CONVEXITY
  maximum-moneyness amendment):** `convexity_gate.max_otm_moneyness = 0.40`, the mirror of the 15% floor on every book,
  gate and sweep path; fail closed (`no_eligible_contract_within_max_moneyness`). Lands at boundary B **Mon 2026-12-07**
  (a `frame_version` move). Open positions unaffected. Found on the W46 probe (KLAR at 81.2%; IRDM at 46.7% in two null
  books).
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
- **Model refresh (moved from 11-05 to ~11-12 by the operator, 11-01; NOT ready on 11-12, so restate_v1 landed alone
  that day, operator word 2026-11-12):** the planned model refresh, all roles at once, its own dated segment, after §10.11 has ~10 sessions; plumbing in
  #331 (`council.anthropic` knobs, refusal routing, unpriced-model guard). Gemini/xAI prices to verify at the switch.
- **2026-11-04: DONE**, the two-week look (`records/2026-11-04_council_two_week_look.md`); its persistence watch
  (amended 11-09: majority of the next 3 reads) is read when the 5th real entry is decided.
- **Sun 2026-11-08: DONE** (W45): the 09-27 five went dormant (none re-surfaced); KMT pin #19 lapsed, not re-pinned.
- **Sun 2026-11-15: DONE** (W46): TITN's lineage dormant while held; FCX/MOS/MRK dormant; 6 re-surfaced, 0 new.
- **Owed (operator):** the thesis-as-direction class (W45: MOS, KKR; W46: + the RDW adversary 11-09, the MOS and UEC
  strategists 11-11/11-12); TITN's slate presence while held (W46 §0; #464); whether the EPA pins lapse 11-23; the
  libc6 reboots on DEV and PROD. ATKR's removal: **decided 2026-11-09** (`records/2026-11-09_atkr_removal.md`).
- **Tue 2026-11-17: the §10.11 floor-drought look** — the clock was 8 of 10 at #2055 (11-13); if the 11-16 and 11-17
  L1s are 0 at the floor, the pinned operator look is owed ("the wording may be too tight; nothing reverts
  automatically").
- **~2026-11-19/20:** the backfill's weekly quota frees (RDW #9 entered 11-12).
- **2026-11-16:** the EPA rule's effective date (no stay reported; D.C. Circuit petitions pending).
- **Sun 2026-11-22:** the CEG and SMCI bullish lineages (rank slots) and the GEV/LHX/NOC/UEC/UUUU/VRT bearish ones go
  dormant unless re-surfaced (last seen 10-11). **11-29:** NTSK and PWR (last seen 10-18).
- **Mon 2026-11-23:** May-2027 drops under the gate's 180-day floor, on the first session after the November monthly
  expires (Fri 11-20). Re-read on W46 (11-15): no Aug-2027 quarterly listed; **BWXT/FLNC/FLY/KTOS/RDW/SMR/UEC have
  only Jan-2028 after May (KTOS Dec-2027)** → those 7 lose structure (KTOS to ~12-17) and **expressible falls ~35 →
  ~28**. LMT (Jun/Sep-27) and NXE (Aug-27) keep a later wing; LHX and TGB already lost structure. The three EPA pins
  expire the same day.
- **2026-11-25:** the NRC DOE/DoW-design rule's effective date (reviewed, not pinned — 11-01 decision).
- **~2026-12-19:** TITN's only in-window expiry (Jun-2027) drops under 180 days unless Sep-2027 lists (held #7 is
  Jun-27; exits unaffected).
- **~early December:** NTSK's falsifier read (10-Q for the quarter ending 2026-10-31; revenue growth < +20%).
- **Before Sat 2026-12-05:** the #456 probe code merged default-off (§10.12), with the anthropic page at $20.
- **Mon 2026-12-07:** boundary B; `council.repeat_probe` switched on with the first L1 (§10.12 segment, 10 sessions).
- **Fri 2026-12-18:** the probe segment's 10th session → the §10.12 look (Read 1, Read 2, RDW `include=false`,
  carry confirmation).
- **January 2027 (first L1):** `council.monthly_spend_page_usd.anthropic` back to $10 (dated edit, §10.12).

## Board & book
- Box: DEV = main `f36f9b5` (#520, deployed 2026-11-18 03:35 UTC; **rebooted 2026-11-07 19:24 UTC** after the
  operator's apt upgrade; **reboot-required since 2026-11-13 06:48 UTC, libc6**: hygiene only, no trading process is on
  the old libc, so a reboot waits for a quiet weekend); **PROD = `d276bf1` (#521, promoted 2026-11-18 05:32 UTC = main
  `f36f9b5`, #495–#520; reboot-required since 11-13 06:18 UTC, libc6), verified read-only 2026-11-18 ~05:35 UTC**
  (ssh with the operator's go): HEAD `d276bf1`, clean tree, 0 `dramatic-options-*` timers loaded (l0/l1/l2/reach/post-l1
  all inactive), 0 failed units, units on `-m orchestrator` (post-l1 `--post-l1`), `trading-bot` active, `/api/version`
  env `prod` at `d276bf1`; inert: `LIVE_TRADING_ENABLED=false`, `DRY_RUN=true`,
  `FORWARD_ENABLED=false` (its `.env` carries `PAPER=false`; the triple gate stays shut on the other two). Rebooted 2026-10-18. Both healthy
  (0 failed units); units on `-m orchestrator` on both; Real Options `trading-bot` active on PROD. PROD's journal is readable by the review user from 2026-11-03 (`systemd-journal`). PROD's first #392 deploy failed at `git fetch` (a stale `origin/claude` tracking ref blocked `claude/*` branches); pruned with the operator's go, deploy re-run green.
- Apps:
  - DEV: `https://all-options-dev.tail57521e.ts.net:8602`
  - PROD: `https://all-options-prod.tail57521e.ts.net:8602`
  - Both are tailnet-only `tailscale serve` → 127.0.0.1:8602 (the React/FastAPI dashboard; the Streamlit :8601
    dashboard is retired, 2026-10-06). `/api/version` reports the running commit; `/api/status` is the light
    cached read (verdict, heartbeats, KILL, drawdown vs halt, book, last council, T4 — under 5 KB, no positions).
- Universe **49 names** from the first run after the 2026-11-09 removal (ATKR delisted 2026-10-19, Atkore taken
  private; `records/2026-11-09_atkr_removal.md`; it stays in the frozen `ai_capex_power` cluster for its open
  null positions) · 16 clusters (book fills at most 5). Expressible 35 of 49 on the 11-15 Sunday probe (33 on #2055's `record_ok`; sweep #9
  30; no structure AMSC/CC/ERO/FRO/HBM/IRDM/LHX/NNE/NOC/PL/STUB/TGB/UROY/UUUU — ERO/LHX/NOC on the 15% floor).
  Active sentinel lineages 40 (11-15).
- Book: real 4 open, $3,420 (marks at the 11-13 21:30 L2; unrealized ≈ −$396, realized $0; kill-rule drawdown ~4%):
  PL ($690; 0.015), FLNC #6 10× `FLNC270521P00005000` @ 1.00 ($1,000, filled 11-04 via carry from #1918; 1.505), TITN #7
  3× `TITN270617C00030000` @ 2.60 ($780, backfill, filled 11-04 via carry; 2.1795; **lineage dormant 11-15**), RDW #13
  10× `RDW270521P00006000` @ 0.95 ($950, backfill, filled 11-13 18:00 UTC after the #8 carry veto and the #9 re-entry;
  0.85). space_smallcap $1,640 of $2,000 (RDW bear + PL bull). Null books accruing (shadow · 3A · 3B · shares; 3B booked
  LMT 11-15). **Last above-floor conviction: run #1918, 2026-11-03 (FLNC MODERATE)**; before it #1867 (AG) and #1816
  (HL), both cancelled unfilled.
- Open issues: as of 2026-11-12; no count kept (#446): `gh issue list` is the source. The parser reads only this
  bullet's continuation lines, so they carry no sub-bullets.
  **Roadmap tracker #452 and its children:** measurement #453–#456 (#454's audit shipped in #474, the issue left
  open) · the gate #457 · discovery #459 · calibration #460 · extensions #461–#463 · held-name tracking #464 · risk
  and T4 #465–#469 · the segment register #470.
  **Decided 2026-11-12:** #465 and #472 (the kill rule, implementation for 12-07) · #470 (boundary B) · #468, (2)
  and (4) only · #469, deferred.
  **Filed 2026-11-16:** #504 (moneyness ceiling 40%, decided 11-16, code for 12-07) · #505 (closed 11-16 as a
  complexity-cut) · #508 (held reads: the §3 timeline and the §4 scoring report, deferred from #507).
  **Filed 2026-11-17:** #515 (the boundary-B 12-07 checklist: #510, the §10.12 switch-on #519, the model refresh).
  **Filed 2026-11-18:** #529 (dashboard `market_context` relabel; #462 decision 7).
  **Defects:** #444 (the pre-T4 venue/journal audit; its first fix is #481) · #471 (held names take backfill slots)
  · #477 (null-book exits on closed-market ticks).
  **Partly shipped by the stopped session's wave 3 and left open on purpose:** #463, #466, #467.
  **Closed 11-12 to 11-14:** #473 (11-12) · #492 by #495 · #494 by #496 · #479 by #498 · #480 by #497.
  **Closed 11-10 to 11-12:** #421 by #426 (restate_v1, 11-12) · #437 by #441 · #440 by #442 · #445 by #447 ·
  #446 by #448 · #449 by #450 · #451 by #478 · #458 by #475.
- NVDA opra canary at or above 1.0 for 23 prints (11-13 1.1915, the streak's high, 0.0085 under the 1.2 gate line)
  after eight below (low 0.9818).
