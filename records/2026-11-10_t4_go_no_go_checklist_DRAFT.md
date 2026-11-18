# 2026-11-10 — T4 go/no-go checklist and the PROD rehearsal (#468, R4)

> **Status: DRAFT for issue #468. Nothing here is in force.** The T4-unlock conditions are the operator's
> (IMPLEMENTATION_PLAN, 2026-06-03) and change only by the operator's dated word. So do the checklist below,
> turning PROD's timers on, and arming. Merging this file ratifies nothing: merge-as-ratification is a named failure
> mode in this project (PREREG_THEMATIC_CONVEXITY §6 ownership addendum).

## 1. The five conditions as written, and where each stands
IMPLEMENTATION_PLAN.md, "Pre-committed T4-unlock conditions (operator, 2026-06-03)". T4 = "building the real-money
broker path LAST, behind the triple-gate; it is a process/discipline gate, not a proof gate." The T4 line says: "On a
pre-committed rule (N paper trades logged, payoff distribution sane, risk frame held with no breaches)". It names
no N.

| # | Text (verbatim) | Now |
|---|---|---|
| 1 | "the council fix merged **and** a multi-L1 prod window showed a HEALTHY apparatus (parse-fail ~0, adversary+strategist firing, the parse-fail page silent)" | Marked "✅ MET 2026-06-05". `t4_scoreboard` re-derives it live from the last `RECENT_COUNCIL_N` (4) runs (all `ROUNDTRIP_CONFIRMED`, ≥ 2). **UNVERIFIED:** today's verdict (no DB in this session). |
| 2 | "the null reads are live-plumbed (real / shadow / 3A per-position p95 + bootstrap CIs computing each cycle, with ≥ some RESOLVED positions — plumbing, not significance)" | Real resolved = **0**: no real position has closed (STANDING_STATE "Board & book"). Shadow and 3A counts: **UNVERIFIED**. The scoreboard shows the counts with `verdict: None`. |
| 3 | "the cluster-cap breach audit has run over the window with zero breaches (the `frame_version` recompute)" | `breach_audit.audit_cluster_breaches`. It renders PASS / VACUOUS / BREACH. **UNVERIFIED:** the current count. |
| 4 | "resolved paper positions show a payoff SHAPE matching the calibration's venture profile (sanity, not significance)" | Nothing to read: 0 real resolved. The scoreboard shows `verdict: None`. |
| 5 | "the remaining pre-T4 items are done (PR2c ✅, the correlation diagnostic ✅ + basket-quality report ✅ … the §5b file-structure refactor remains)" | Rendered `manual` (#355). Its listed items are done, except "the §5b file-structure refactor remains". **UNVERIFIED:** whether that refactor finished. |

## 2. Numbers for conditions (2) and (4)
**(2) How many resolved positions.** The known real resolutions: PL's time-stop (~2026-12-28; the first ≤ 21 DTE
day is the 12-25 holiday, the #451 path), FLNC's (2027-04-30) and TITN's (2027-05-27), unless an earlier exit.
- **2A:** ≥ 10 resolved real positions, and ≥ 30 resolved in each of shadow and 3A.
- **2B (recommended):** ≥ 5 resolved real positions covering at least 2 distinct exit paths, and ≥ 30 resolved in
  each of shadow and 3A, with the p95 and CI rendering for all three books. Condition (2) says "plumbing, not
  significance", and 10 resolutions at about one entry a week would push T4 into late 2027 for no gain in
  significance. Five is enough to exercise every computation on real rows. The ≥ 2 exit paths cover the
  mechanics. The bar is stricter than "≥ some".
**(4) A checkable "venture profile".** The reference is calibration v2's `live_10x` cell
(`records/2026-11-03_calibration_v2_finding.md`, Rule J, the live exits under jumps): mean M 1.13×, median −0.04×,
p99 10.7×, P(M ≥ 1) 23%, P(total loss) 59% (`calibration/v2.py` reports `p_total_loss`; `calibration/metrics.py`
defines a total loss as M ≤ 0.02).
- **4A (recommended): a shape test that can fail.** Over the resolved real positions
  (`state.convexity_realized_multiples`), each of the following must hold. (i) Every M ≥ 0: no loss beyond the premium,
  which is the defined-risk check. (The journal's `realized_pnl` carries no commissions; UNVERIFIED that the venue
  charges any.) (ii) The median M ≤ 1: most bets lose. (iii) Every close is
  one of the three §6a exits, and its M agrees with that rule: a profit-take at ≥ 10× of entry at trigger, an expiry
  at intrinsic. (iv) P(M ≥ 1) lies inside the two-sided 95% binomial interval around 0.23 for the observed N.
  Items (i)–(iii) are mechanics and fail on a bug. Item (iv) only catches gross mismatch at small N, which is all
  "sanity, not significance" asks for.
- **4B:** 4A (iv) alone, plus the same test for P(total loss) around 0.59. It is purely distributional and passes
  vacuously at small N.

## 3. Added mechanics items (none existed on 2026-06-03)
| Item | Evidence source | Pass rule | Owner |
|---|---|---|---|
| Exits proven end to end | #466 fire drill (paper); #444; #451 | each of profit-take, time-stop and expiry closed by the system on the paper account, the journal equal to the venue afterwards; #444 and #451 closed | CC builds; operator reads |
| Measured slippage | #467: `scripts/smoke_order_roundtrip.py --endpoint live` (PREREG_REAL_MONEY_BROKER §5) | the one-contract live round trip done under a hard `< $X` cap with the operator's go at execution; fill vs mid recorded; a haircut applied to paper results | operator authorizes; CC runs |
| Kill rule complete | #465 (`records/2026-11-10_kill_rule_dry_leg_conformance_DRAFT.md`) | the dry leg is in code with the conformance note | CC |
| Options approval level | the live account, read-only | single-leg long options allowed; multi-leg too if `vertical_for_over_cap` is enabled (#463 after its paper round trip). **UNVERIFIED:** the account's level and Alpaca's level numbering | operator |
| Shared-account reserve exercised | `AlpacaLiveBroker._reserve_precheck` on the live smoke | one live buy shows the options-buying-power read and the $5,250 reserve applied (`safety.shared_account_reserve_usd`) | CC |
| Foreign-quantity check exercised | `paper_loop` `veto-foreign-quantity` via `broker.venue_quantity` | one read against a contract the account holds outside this journal returns that quantity and vetoes. The no-collision case runs on DEV daily (§3a.3) | CC + operator |
| Live notional ceiling set | `safety.live_max_order_notional` or env `LIVE_MAX_ORDER_NOTIONAL` (`config_loader.load_config`) | set, and the close question below decided | operator |
| Key names | PROD `.env`, names only | `ALPACA_LIVE_KEY_ID`/`_SECRET_KEY` present; no legacy name (`config_loader.alpaca_credentials` refuses to start) | operator |
| Page path tested | `notify.send` from PROD | a test page arrives and reads as PROD (see §5, pages) | CC |
| Layer scoreboard | #453 | context only, not a gate (no layer has a verdict before mid-2027, per #453) | — |

**Two findings that block arming as the code stands:**
1. **The ceiling also applies to closes.** `AlpacaLiveBroker._reject_precheck` checks `qty × limit × 100` against the
   ceiling before its `if is_buy` branch, so a SELL_TO_CLOSE is capped too. Sizing keeps every entry at or under
   the $1,000 per-name cap, including a walked carry limit (`paper_loop.py`: "Sizing and every cap below use THIS
   price"). A 10× profit-take on a $1,000 position is a close of at least $10,000. At a $1,000 ceiling that close is
   rejected, and `monitor._exit_position` logs "left open to retry" and tries again every cycle until the 21-DTE
   time-stop. PREREG_REAL_MONEY_BROKER §3 says "any order". The options are: **(a, recommended)** a dated §3
   amendment so the ceiling bounds opening orders only (a close sells what is held and cannot exceed it); or (b)
   set the ceiling at or above about 10× the cap, which weakens the guard on buys tenfold.
2. **No path arms PROD.** The L1/L2 unit templates run `python -u -m orchestrator` / `--monitor` with no `--live`
   (`scripts/systemd/*.service`), so `live_allowed` is False on every box whatever `.env` says. Separately,
   `scripts/verify_deploy.sh` requires the **paper** key pair on any `FORWARD_ENABLED=true` env ("A trading env
   (FORWARD_ENABLED) is paper until T4"), so a live-keyed PROD fails its own deploy. Arming therefore needs a code
   PR: a per-env `--live` in the rendered units, and the live pair accepted when PROD is armed.

## 4. The arming procedure and the first week (as the code implements the gate)
`config_loader.live_allowed` = `safety.paper is False` ∧ `safety.live_trading_enabled is True` ∧ `--live`. Env wins
over file (`load_config`). `orchestrator._select_broker` builds `AlpacaLiveBroker` only when it is True. DRY_RUN
still simulates on both brokers (`_AlpacaBrokerBase.submit_paper`/`submit_spread`).
1. All checklist rows PASS. The operator's dated word is recorded (STANDING_STATE plus a records note). Only the
   operator arms.
2. Fund about $10,000 as a disjoint slice of the shared account (`records/2026-10-03_shared_account_capital.md`).
3. Merge the arming PR from §3 finding 2, and the §3 finding 1 amendment if (a) is chosen.
4. PROD `.env`: the live pair; `PAPER=false`, `LIVE_TRADING_ENABLED=true`, `FORWARD_ENABLED=true`, the ceiling.
   **Keep `DRY_RUN=true` for the first L1**, so the whole live path runs and logs "DRY_RUN (not sent) … [LIVE — REAL
   MONEY]" before any transmission.
5. PROD's DB: the real book starts **empty**, so the journal equals the venue. Archive any rehearsal DB (§5).
6. Flip `DRY_RUN=false` on the operator's word on the morning of an ordinary session (not an expiry Friday).
**First-week watch (daily, CC; the operator reads):** every submit's log line carries `[LIVE — REAL MONEY]`. Every
buy shows its ceiling, reserve and venue-quantity read. Each fill is compared with its limit (slippage). Pending
orders reconcile at the next L2. The L2 must run with `--live` too. Without it, `run_once` builds the paper broker,
so live orders never reconcile, and `_cancel_resting_entries_on_kill` holds a LIVE run's order as `wrong_venue`
rather than cancelling it. Read the live account's positions by hand each
day and compare them with the journal; the loop never lists them, by design (§3a.3). Check the kill-rule and
drawdown state, and that the expected pages arrived. **Disarm:** `touch KILL`. It is checked every cycle and also
cancels resting entries (#389). Then set `LIVE_TRADING_ENABLED=false`.

## 5. The PROD rehearsal (one week, timers on, triple gate shut)
**What "timers disabled" means today.** `deploy.sh` arms timers only where `.env` has `FORWARD_ENABLED=true`, and
PROD has `false`, so no L0/L1/L2/reach unit ever fires there. The web dashboard runs keyless. PROD is at `a7548e8`
(#392), 31 merges behind main on 11-08 (STANDING_STATE). **PROD's DB is separate:** `database.path` is
`data/dramatic_options.db` relative to each box's checkout. **UNVERIFIED:** what it holds now.
**Keys: two contradictions to settle read-only first.** DEPLOYMENT.md's flag table says PROD `PAPER=true`;
STANDING_STATE says PROD's `.env` "carries `PAPER=false`". DEPLOYMENT.md also says PROD's `.env` "still carries the
legacy names because `production` runs pre-#284 code". But PROD's code (`a7548e8`) already contains
`LEGACY_KEY_VARS` and refuses to start on a legacy name. DEPLOYMENT.md's "no real-money broker path in code" also
predates `AlpacaLiveBroker`. **UNVERIFIED:** PROD's key names. Check over `ssh console@all-options-prod`, names
only, never values:
`grep -oE '^[A-Z_]+=' ~/dramatic_options/.env`,
`grep -E '^(PAPER|LIVE_TRADING_ENABLED|DRY_RUN|FORWARD_ENABLED)=' ~/dramatic_options/.env`,
`systemctl cat dramatic-options-l1.service | grep ExecStart` (no `--live`), and
`systemctl list-timers 'dramatic-options-*'`.
**The rehearsal `.env` (the operator edits it; it must not send orders):**
- `PAPER=true`, with a paper pair. Under `PAPER=false`, `alpaca_credentials` would hand the live pair to the paper
  broker, and `verify_deploy.sh` would fail the deploy without a paper pair.
- `LIVE_TRADING_ENABLED=false`, `DRY_RUN=true`, `FORWARD_ENABLED=true` (this is what arms the timers), and no
  `--live` in the units.
- Each layer is enough alone: `DRY_RUN` returns before `submit_order`, and the paper broker is built with
  `paper=True`.
- **One gap:** `cancel_order` is not DRY_RUN-gated (`_AlpacaBrokerBase.cancel_order`). DRY_RUN entries open
  directly (no `pending` rows), so PROD can only cancel order ids in a DB it was given. **Use a separate paper
  account** (UNVERIFIED that one exists). If PROD shares DEV's account, copy no DB that holds `pending` or carried
  rows, or PROD's 15:30 carry cancel and L2 reconcile would cancel DEV's real paper orders.
**Starting state (operator's choice):** **(i, recommended)** a copy of DEV's DB taken at a quiet moment (no pending
or carried rows, after the Friday L2), so slots, dedup, the backfill trigger and the sentinel lineages match DEV and
the decisions are comparable; it is archived before arming. Or (ii) an empty DB, which rehearses a cold start but
makes every slot and backfill decision diverge.
**Compare with DEV, nightly:** the L0 surfaced set; the council's union and slate order; per-name gate-of-record
`iv/rv`, skew and structure (the same OPRA chain at the same 15:45 ET, so these should match); the backfill line;
intended orders (contract, qty, limit); exits fired; stamps (`frame_version`, `model_mix`) identical. Council
verdicts are LLM output and are expected to differ; record each difference, but do not count it as a failure. The
nightly grade reads DEV only (DEV crontab). PROD's journal is readable by the review user (STANDING_STATE). CC reads
PROD's DB `?mode=ro` over ssh and writes one dated rehearsal record.
**Risks and containment:**
- **Shared host with Real Options** (`trading-bot` active on PROD): the `pkill` class is fixed on both sides
  (#312, real_options #4953). Watch Real Options' health during PROD's 15:45 L1 and its load. The L1
  `TimeoutStartSec=1800` bounds a hang.
- **LLM spend doubles:** the caps are per run (`council.cost_cap_usd` 5.0, discovery 3.0, drafter 0.5). That is a
  ceiling of about $29 extra for the week, not a measured cost. Shared provider keys mean PROD can exhaust a shared
  spend cap (the 2026-08-26 Anthropic case dropped 9 of 12 candidates). Use separate keys, or confirm the headroom.
- **Pages double:** `notify.send` titles are "Dramatic Options — …" with no environment, so PROD pages look like
  DEV's. `verify_deploy.sh` requires `PUSHOVER_*` on a trading env. Use a separate Pushover app token for PROD, or
  add the environment name to the title (a small code change, telemetry only).
- **PROD's L2 books in-DB exits under DRY_RUN** (the monitor's `real_submit` is false): harmless, and comparable.

## 6. The scoreboard once frozen
`t4_scoreboard` would read a checklist file instead of hard-coded rows. (1) and (3) stay binary. (3) also shows
`n_clustered_admissions`. (2) shows MET or NOT_YET against the chosen N for real, shadow and 3A. (4) shows 4A's
items (i)–(iv), each PASS or FAIL, with N. (5) becomes the §3 rows, each with its evidence pointer (an issue or a
record) and a state: OPEN, or PASS with the record's path. No row stays `manual` without a source. The note
"A scoreboard, NOT a graduation verdict" stays: arming is still the operator's act.

## 7. The operator's decisions
1. Condition (2): 2A or **2B**. Condition (4): **4A** or 4B.
2. Adopt the §3 mechanics rows as part of the frozen checklist.
3. The ceiling and closes: **(a)** a §3 amendment to bound opening orders only, or (b) a high ceiling. Then the
   value.
4. The arming PR (per-env `--live`; the live pair accepted by the verify gate) is authorized to be built, inert.
5. The rehearsal: turn on PROD's timers for one week (`FORWARD_ENABLED=true`, `PAPER=true`, `DRY_RUN=true`). Choose
   a separate paper account, a separate Pushover token and separate LLM keys; and the starting DB, (i) or (ii).
6. The live smoke (#467) date and its cap `X`, given at execution time (PREREG_REAL_MONEY_BROKER §5).
