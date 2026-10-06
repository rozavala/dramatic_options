# STANDING STATE — the relay sync header

**as_of: 2026-10-06T06:00Z · supersedes: 2026-09-27T15:00Z (the prior text is in git history) · reflects the
week of 2026-09-28: the ITM side guard (#277/#278) · sentinel pack provenance + forward-catalyst sentinel scope
(#280) · the shared-live-account guards and capital decision (#281) · venue-named Alpaca keys (#284/#285) · PROD
promoted to current main (#286/#289) · the installable web app on DEV + PROD (#287/#288) · the Streamlit
dashboard retired (#291) · the telemetry fixes (#290) · register thesis A2 staged (#292, awaiting the operator).**

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
- **Council pack (record boundary = L1 #1558, 2026-10-05):**
  - `council.pack_provenance` (PREREG_EVIDENCE_GROUNDING A1): the framer's text is `DISCOVERY_SUMMARY`, never
    `OPERATOR_THESIS`.
  - `forward_catalysts.sentinel_scope` (channel prereg §11): pins render for sentinels too; F-c is a live guard.
  - First sentinel forward-dated judgment: NEE, 2026-10-05, on the EPA item.
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
- **#292 — register thesis A2:** sentinel packs show the operator's COUNCIL-FACING `council_thesis` (structural
  claim only, 14 lines drafted by CC) + falsifier, instead of "(none on file)". Merging adopts the 14 lines and
  segments the record.
- **Forward-catalyst sources (charter §3b):** CC's recommendation is in the 2026-10-06 session note (FDA AdComm:
  defer until ≥2 biotech names; DoD contracts: not forward-dated → no; instead weekly Federal Register
  effective-date pin SUGGESTIONS for universe names, operator pins).
- **DEV droplet reboot:** up since 2026-08-13, kernel/libc patches pending, 63 updates. The operator reboots
  outside 13:00–20:00 UTC weekdays and away from alpha_options' 09:00 / 21:45 UTC jobs. PROD was updated and
  rebooted 2026-10-06.

## Dated docket
- **~2026-10-19:** April 2027 leaves the tenor window → AMSC · ATKR · CC · HBM · NNE · PL · STUB · UUUU lose
  structure (live OPRA, 2026-10-04). The real PL position (Jan-2027) is unaffected.
- **2026-10-11 Sunday:** W41. BioPharma Dive's first pull (replaced Fierce Biotech, #283). KMT pin #15 expires —
  re-verify Comtrade August. Miss sweep #4.
- **2026-11-04 (≈30 sessions under direction coherence):** F4 review if still no above-floor conviction.
- **2026-11-16:** the EPA rule's effective date (litigation filed, no stay as of 2026-10-04).

## Board & book
- Box: DEV = main (`89a549b`); PROD = `production` (`aaae1d1`), inert (timers disabled, live gate closed).
  Both healthy.
- Apps:
  - DEV: `https://all-options-dev.tail57521e.ts.net:8602`
  - PROD: `https://all-options-prod.tail57521e.ts.net:8602`
  - Both are tailnet-only `tailscale serve` → 127.0.0.1:8602.
- Universe 47 names · 15 clusters (book fills at most 5).
- Book: real 1 (PL, $690, dd 7%) · null books accruing (shadow · 3A · 3B · shares).
- Open issues: 0. NVDA opra canary first printed below 1.0 on 2026-10-02 (0.9908).
