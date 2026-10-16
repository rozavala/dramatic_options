# STANDING STATE — the relay sync header

**as_of: 2026-10-16T00:30Z · supersedes: 2026-10-06T06:00Z (the prior text is in git history) · reflects the
weeks of 2026-10-05 and 2026-10-12: register thesis A2 merged (#292) and its A2.1 wording (#301) · Federal Register
pin suggestions (#294) · snapshot mode/book and /api/version + next_at for the hub (#304, #310) · reach noise fixes
(#305) · the F4 evidence pack (#308) · window #10: NTSK admitted (#309) · the shared-host pkill fix and deploy
hardening (#312–#314) · PROD promoted three times (#300, #311, #315).**

Maintained by CC; updated on every ruling, clock change, staged-PR change, or pending-act change.
**Relay rule (both directions): a strategy question or advice arriving WITHOUT this header, or carrying an
`as_of` older than the latest ruling, is treated as UNSYNCED — verify against the record before acting.**
The header's absence is itself a signal.

## Rulings in force
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
    Rule 0 amendment), with the A2.1 wording on coverage and the falsifier deadline. Running tally after 4
    sessions: consensus-leak 0 · strategist misuse 0 · adversary falsifier misuse 2 (both 10-13).
  - `forward_catalysts.sentinel_scope` (channel prereg §11): pins render for sentinels; F-c is a live guard. The
    EPA item (2026-11-16) has been judged irrelevant/non-nuclear six times running (NEE ×2, CEG ×4), no leak.
- **Frame stamp `frame-a80e6abea2b9` from run #1681 (2026-10-15).** The hash covers `convexity_book` including the
  cluster map, so window #10's `cyber_sase` cluster moved it. Every frozen risk number is unchanged; for the ITM-
  guard segment it is the same regime as `frame-a6da3dee9171`.
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
- **F4 review (≈ 2026-11-04, session 30):** the interim evidence is `records/2026-10-13_f4_review_evidence_pack.md`
  (session 14). On it, `at_inflection` binds harder than `under_narrated`. Re-run its §1–§4 at session 30.
- **Marker freshness (proposal being drafted by CC):** the council's 12-month momentum markers are a median 31
  days old (they refresh only when the weekly scan resurfaces a name). A change would alter the pack and is the
  operator's word + a dated amendment.
- **PROD reboot:** `/var/run/reboot-required` is set (up since 2026-10-06). Operator's call, away from
  alpha_options' 09:00 / 21:45 UTC jobs and Real Options' trading hours.
- **Hub:** `version: /api/version` to be added to `rozavala/hub`'s registry for the dev/prod commit row.

## Shared hosts (DEV + PROD also run Real Options and alpha_options)
- Our L0/L1/L2 start as `python -u -m orchestrator` (#312): Real Options' `pkill -9 -f orchestrator.py` SIGKILLed
  our L2 on 2026-10-15 14:30. Their side is rozavala/real_options#4948 (in progress: kill only PIDs whose cwd is
  their checkout).
- Unit installs: a unit that cannot be installed fails the deploy (#313). PROD (classic sudo) installs with
  `NOPASSWD: /usr/bin/cp /tmp/* /etc/systemd/system/*`; DEV runs **sudo-rs**, which rejects wildcards, so it has
  one exact `NOPASSWD: /usr/bin/tee /etc/systemd/system/<unit>` per unit (`/etc/sudoers.d/dramatic-options-units`,
  #314). **A new unit file needs one more line there**, and the deploy will say so.

## Dated docket
- **2026-10-18 Sunday W42:** NTSK's first L0 scan. KMT pin #16 expires (re-verify Comtrade). FR pin suggestions.
  Miss sweep #5. Bench tenor glance for new Jun-2027 / Jan-2028 listings (the cliff, below). BNTX/BWXT only on a
  fresh word (weekly cadence, no cap-line camping).
- **Tenor cliff, started 2026-10-15:** FRO/HBM/TGB lost structure on both feeds. From ~10-19 AMSC · ATKR · CC ·
  NNE · PL · STUB · UUUU follow (April 2027 leaves the window). PL's real Jan-2027 position is unaffected.
- **2026-11-02:** posture LOOK (PREREG_THEMATIC_CONVEXITY §6 amendment).
- **2026-11-04 (≈ session 30 under direction coherence):** the F4 review.
- **2026-11-16:** the EPA rule's effective date.
- **~early December:** NTSK's falsifier read (10-Q for the quarter ending 2026-10-31; revenue growth < +20%).

## Board & book
- Box: DEV = main (`d391c8a`); PROD = `production` (`dd99e5b`), inert (timers disabled, live gate closed). Both
  healthy; units on `-m orchestrator` on both.
- Apps:
  - DEV: `https://all-options-dev.tail57521e.ts.net:8602`
  - PROD: `https://all-options-prod.tail57521e.ts.net:8602`
  - Both are tailnet-only `tailscale serve` → 127.0.0.1:8602; `/api/version` reports the running commit.
- Universe 48 names · 16 clusters (book fills at most 5).
- Book: real 1 (PL, $690, unrealized −$680). Null books accruing (shadow · 3A · 3B · shares). Last above-floor
  conviction: run #508, 2026-07-10.
- Open issues: 0. NVDA opra canary back above 1.0 (10-14 1.0127, 10-15 1.0204) after eight prints below (low
  0.9818).
