# 2026-11-21 — The PROD paper rehearsal: runbook (#468)

**Status: a runbook, operator-run. Nothing here arms live trading. The triple gate stays shut throughout: `PAPER=true`,
`LIVE_TRADING_ENABLED=false`, no `--live` in any unit (`config_loader.py:180-194`). `DRY_RUN=true` stays on for the
whole comparison week.** It implements the operator's word of 2026-11-12 ("OK to draft the inert arming PR and a
1-week paper rehearsal on a separate paper account"), as detailed the same day ("accept all"): a separate paper
account, a separate Pushover app token, shared LLM keys, and starting DB (i), a copy of DEV's DB taken on a Friday
after the 16:00 ET L2 with no pending or carried rows (`records/2026-11-12_operator_decisions_roadmap.md`;
IMPLEMENTATION_PLAN, decision 5). The draft it builds on is §5 of `records/2026-11-10_t4_go_no_go_checklist_DRAFT.md`
(branch `records/roadmap-protocol-drafts-2026-11-10`). Code citations are against main `4fc9ab0`. Items marked
**UNVERIFIED** could not be checked from DEV without ssh to PROD.

## 0. Decisions in this runbook, and why

1. **Window: W48.** Copy DEV's DB on Fri 2026-11-27 after its last tick (16:30 ET), promote and arm PROD on Sat
   11-28, run Sun 11-29 (L0) through Fri 12-04 (5 L1s), and disarm Fri 12-04 evening. This is before boundary B
   (the #510/#519/#525/#526 merge set on 12-05/06) and before the 12-07 → 12-18 stamp freeze, so DEV and PROD run
   one commit all week and no boundary falls inside it. A fallback is in §3.
2. **The copied open positions stay as they are** (no edit to the copy). Under `DRY_RUN=true` nothing reads the
   venue for them (§1), and they are what make slots, the cluster budget, the backfill trigger and the kill rule
   match DEV. Deleting them would make PROD's book diverge from the first L1. They diverge only if an exit triggers;
   none is expected in W48 (§1, row 3).
3. **`DRY_RUN=true` all week. #466 and #463 do NOT need `DRY_RUN=false`.** Both are out-of-band scripts that pick
   their own transmit flag (`--send`): `scripts/drill_exit_paths.py:324` builds its broker with `dry_run=not send`,
   and `scripts/smoke_order_roundtrip.py:224` sets `dry = not args.send`. Neither reads the loop's `DRY_RUN`, and
   neither touches the journal. They run against the rehearsal paper account beside the DRY_RUN loop (§9). The
   `DRY_RUN=false` window stays an explicit operator option, not recommended (§10).
4. **The live pair is commented out of PROD's `.env` for the rehearsal** (recommended; operator's choice). With
   `PAPER=true` it is never read (`config_loader.py:161`), so removing it costs nothing and removes one margin of
   error. The pre-rehearsal `.env` is backed up and restored at the end.
5. **No code.** Every step uses existing entry points. Optional follow-ups are in §15.

## 1. What PROD does with a DEV copy, under the rehearsal flags (read-only code read)

Flags: `PAPER=true` (its own pair), `LIVE_TRADING_ENABLED=false`, `DRY_RUN=true`, `FORWARD_ENABLED=true`, units
without `--live`. The broker is `AlpacaPaperBroker` (`orchestrator.py:324-334`, `:856`, `:920`), fixed to the
paper endpoint (`broker.py:153`, `:353`).

| # | Path | What PROD does | Consequence |
|---|---|---|---|
| 1 | **Order transmission** | `submit_paper` and `submit_spread` return a simulated fill before any `submit_order` (`broker.py:212-215`, `:281-285`). DRY_RUN entries are booked `open` at the limit, never `pending`. | Nothing is sent by the loop. |
| 2 | **Venue/journal check (#481)** | Off under DRY_RUN: `venue_check.run_tick` returns at `venue_check.py:564-574`; the orchestrator passes the configured `dry_run` (`orchestrator.py:1015-1019`). | The 4 copied contracts are never read against the venue. No page. |
| 3 | **L2 marks and exits** | Marks come from market data, as on DEV. `real_submit` is false under DRY_RUN (`monitor.py:194`), so a triggered profit-take or time-stop is booked in-DB at the mark (`monitor.py:342-357`). Under DRY_RUN a closed-market tick books it too (`orchestrator.py:450-461`: `(dry_run, mark_only) = (True, False)`), where DEV defers it (#451), sells it, or tags it orphaned (#444). Expiry books intrinsic on both. | A known divergence, only if a trigger fires. At the 11-20 marks no trigger is near: FLNC #6 ×2.18, RDW #13 ×1.58, TITN #7 ×0.55, PL #1 ×0.005 against the 4× profit-take; PL's 21-DTE time-stop starts 12-25, after W48. |
| 4 | **Foreign-quantity veto (`broker.venue_quantity`)** | Runs on every NEW entry, DRY_RUN or not (`paper_loop.py:558-590`): the venue quantity on the rehearsal account must equal the journal's. | It never reaches a copied contract: held names are blocked earlier by the per-name dedup (`paper_loop.py:203`, `state.entry_blocked_symbols`). A new name reads venue 0 = journal 0 and passes. |
| 5 | **Reconcile, 15:30 carry cancel, KILL cancel** | `cancel_order` is **not** DRY_RUN-gated (`broker.py:342-346`). It is reached only through `carry.cancel_and_settle` (`carry.py:117-122`) from `reconcile_pending` (`monitor.py:574-611`, called every cycle at `orchestrator.py:939`), the carry worker, and the KILL cancel (`orchestrator.py:765-845`). Each acts only on `pending` rows with an order id or on `carried` intents. | With a seed that has none, and DRY_RUN creating none (row 1), these paths have nothing to act on. Even a slipped row could only reach the rehearsal account: DEV's order ids are unknown there (`order_status` reads `None`), and DEV's keys are not on PROD. The cost would be a stuck slot on PROD, which is why the seed check rejects one. |
| 6 | **`closing` rows** | `_reconcile_closing` runs only when `real_submit` (`monitor.py:200`). | A copied `closing` row would stay `closing` on PROD forever. The seed check rejects one. |
| 7 | **Held reads (post-L1)** | `council.held_reads.enabled` is true in config; the pass re-reads every held position nightly, capped at $1.00 a pass (`council/held_reads.py:60`, `:257`). The repeat probe stays off until #519 (`council.repeat_probe.enabled=false`). | The 4 copied positions are re-read nightly on PROD. LLM output, so differences are expected and recorded, not failures. |
| 8 | **Kill rule and drawdown page** | Both read only the DB and config (`paper_loop.py:77-122`; `orchestrator.py:145-167`). The latch file sits beside the DB (`data/drawdown_warn_state.json`); DEV had none on 11-21. | Identical to DEV (drawdown ~4%, dry clock from 2026-07-01). A copied latch, if one exists on 11-27, goes with the seed. |
| 9 | **Sizing** | Uses `convexity_book.account_equity` from config (100,000), not the account (`paper_loop.py:183`). `runs.equity` records the rehearsal account's equity. | The rehearsal account's size does not change any decision. `runs.equity` differs from DEV; ignore it. |
| 10 | **Spend tripwire** | MTD is summed from the box's own DB (`orchestrator.py:304-317`, `state.py:1140`). | Each box sees its own spend plus, on PROD, DEV's copied month. Neither sees the combined spend (§12). |
| 11 | **Pages** | Titles are `Dramatic Options — <title>` with no environment (`notify.py:33`, `:59`). | Only the separate app token tells PROD's pages apart (§12). |

**Expected pages from PROD this week:** none in normal operation. Any page from the rehearsal app is read the same
evening.

## 2. Preconditions

**Operator:**
1. The second Alpaca **paper** account and its key pair. Set its options level to the highest the paper account
   allows (multi-leg needs level 3 for #463). **UNVERIFIED:** the default level and equity of a new paper account.
2. A new Pushover **application** (its own `PUSHOVER_API_TOKEN`), named so it is unmistakable, for example
   "DO PROD rehearsal", with its own icon. The user key stays the same.
3. The go for CC to ssh to PROD read-only once each evening of W48 (§7).
4. The answers to §14.

**CC:**
1. The `production ← main` promotion PR on Sat 11-28, at the commit DEV runs (§4). PROD is at `d276bf1` and lacks
   #527 (orphan policy), #533/#535 (mark bound), #534 (migration 0024) and #531 (term capture), so it must be
   promoted before arming.
2. STANDING_STATE updated before the Sun 11-29 Sunday review (14:23 UTC), saying PROD is armed for the rehearsal
   until 12-04. That review checks PROD's units and would otherwise flag armed timers.
3. A merge hold on trading-path changes to main from Sat 11-28 to Fri 12-04 16:30 ET (§3).

## 3. Timeline

| When (ET) | Who | What |
|---|---|---|
| Fri 11-27 (half day, 13:00 close), after 16:35 | CC or operator, on DEV | Take the seed (§5). If it is rejected, stop: no W48 rehearsal. |
| Sat 11-28 | CC, then operator | Promotion PR; the operator merges; the CI deploy lands PROD inert. Optionally reboot PROD first (libc6 pending since 11-13), outside Real Options' activity. |
| Sat 11-28 | operator, on PROD | Back up `.env`, place the seed, edit `.env`, preflight, arm (§5-§7). |
| Sun 11-29 08:00 / 09:40 | timers | L0 and reach on both boxes. |
| Mon 11-30 → Fri 12-04 | timers; CC each evening | L2 ticks, the 15:45 L1, the 16:10 post-L1. Nightly comparison after 16:45 (§8). |
| Mon 11-30 → Wed 12-02 | operator, on PROD | #466 week-1 drill paths and the #463 round-trip (§9). |
| Fri 12-04, after 16:35 | operator | Return to inert (§13). CC writes the dated rehearsal record. |
| Sat 12-05 / Sun 12-06 | — | Boundary B merges on main for DEV, as planned. PROD stays inert. |

**The merge hold.** A merge to main redeploys DEV at once. During W48 hold anything that touches the trading path
(`orchestrator.py`, `paper_loop.py`, `monitor.py`, `broker.py`, `carry.py`, `council/`, `convexity_*`, `config.json`).
A records, dashboard or test-only merge may land. If an off-cycle fix (money-safety, fail-closed outage) must land, promote the same
commit to PROD before the next L1 and note it in the record.

**Fallback window (if 11-27 is not clean).** Copy Fri 12-04, run Sun 12-06 → Fri 12-11. PROD must then be
promoted to the boundary-B commit DEV deploys on 12-05/06, after DEV's deploy. The arming deploy's migrations bring
the seed to that schema; check its `schema_version` equals DEV's. The §10.12 probe then runs on both boxes (up to
$1.50 a session more on the shared Anthropic key). **The stamp freeze is not broken:** PROD's runs stamp only
PROD's DB. The nightly grade reads DEV's DB only (`scripts/ops/prompts/nightly_grade.md:7`), and so does the segment
register (`records/segment_register.md:15-16`, `--db` = DEV's live DB). But a defect the rehearsal finds could not
land on main before 12-18 unless it is in an off-cycle class. That is why W48 is preferred.

## 4. The promotion

CC opens `production ← main` at main's HEAD on Sat 11-28. That must be the commit DEV is running (check DEV's
`/api/version`). With `FORWARD_ENABLED=false` still in PROD's `.env`, the CI deploy is inert: it skips the key check
(`scripts/verify_deploy.sh:94-133`) and leaves the timers disabled (`deploy.sh:173-185`). The migrations run on PROD's
current DB (`deploy.sh:327-328`). Afterwards, PROD's `/api/version` and DEV's must show the same commit.

## 5. The seed (DEV) and its transport

On DEV, Fri 11-27, after 16:35 ET (21:35 UTC). The last L2 tick is 16:30 ET (`Mon..Fri 09..16:00/30`). The
post-L1 unit fires at 16:10 and refuses quietly on a half day, because there was no council L1.

1. Check that no unit is running. Only `dramatic-options-web.service` may be listed:
   ```bash
   systemctl list-units 'dramatic-options-*' --state=active,activating --no-legend
   ```
2. Save the script below as `~/rehearsal/seed.py` (`mkdir -p ~/rehearsal && chmod 700 ~/rehearsal`), then run it.
   It opens DEV's DB read-only (`?mode=ro`) and makes one consistent copy through SQLite's backup API (never `cp` of
   a live WAL database):
   ```bash
   python3 ~/rehearsal/seed.py ~/rehearsal/seed_2026-11-27.db
   ```
   ```python
   import hashlib, sqlite3, sys
   SRC = "/home/rozavala/dramatic_options/data/dramatic_options.db"
   DST = sys.argv[1]                                   # must not exist yet
   src = sqlite3.connect(f"file:{SRC}?mode=ro", uri=True)   # DEV's DB is only read
   dst = sqlite3.connect(DST)
   src.backup(dst)                                     # one consistent snapshot
   dst.execute("PRAGMA journal_mode=DELETE")           # one self-contained file to move
   fails = []
   if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
       fails.append("integrity_check is not ok")
   for (t,) in src.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
       a = src.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
       b = dst.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
       print(f"  {t:28s} {b}")
       if a != b:
           fails.append(f"{t}: DEV {a} vs seed {b}")
   for row in dst.execute("SELECT id, symbol, status FROM convexity_positions "
                          "WHERE status IN ('pending','carried','closing')"):
       fails.append(f"in-flight row #{row[0]} {row[1]} {row[2]}")
   for row in dst.execute("SELECT id, symbol FROM convexity_positions WHERE status='open' AND "
                          "(CASE WHEN json_valid(rationale) THEN json_extract(rationale,'$.orphaned') END) IS NOT NULL"):
       print(f"  NOTE orphaned open row #{row[0]} {row[1]} (a known divergence: DRY_RUN books its exit in-DB)")
   print("  open rows:", dst.execute("SELECT group_concat(id||' '||symbol, ', ') FROM convexity_positions "
                                     "WHERE status='open'").fetchone()[0])
   print("  last run:", dst.execute("SELECT id, started_at, mode FROM runs ORDER BY id DESC LIMIT 1").fetchone())
   print("  schema_version:", dst.execute("SELECT MAX(version) FROM schema_version").fetchone()[0])
   dst.close()
   print("  sha256:", hashlib.sha256(open(DST, "rb").read()).hexdigest())
   print("SEED OK" if not fails else "SEED REJECTED:\n  " + "\n  ".join(fails))
   sys.exit(1 if fails else 0)
   ```
   It must print `SEED OK`. The last run must be the 16:30 ET tick (`2026-11-27 21:30`). Run on DEV on 11-21 into a
   scratch file, it printed `SEED REJECTED: in-flight row #14 SMCI carried`. That is correct: SMCI's carry is worked
   Mon 11-23. A carry from a Wed 11-25 entry is worked and wound down by 12:30 ET on the half day, and the Fri L1
   (15:45, market closed) places nothing. So 11-27 should be clean. **UNVERIFIED** until it runs.
3. If `data/drawdown_warn_state.json` exists on DEV, copy it beside the seed.
4. Transport (operator; PROD user `console`):
   ```bash
   ssh console@all-options-prod 'mkdir -p ~/rehearsal && chmod 700 ~/rehearsal'
   scp ~/rehearsal/seed_2026-11-27.db console@all-options-prod:~/rehearsal/
   ssh console@all-options-prod 'sha256sum ~/rehearsal/seed_2026-11-27.db'   # must equal the printed sha256
   ```
5. Do not copy `data/cache/` (471 MB). It is a point-in-time read-through cache, so PROD refetches the same data.
   Its history-bearing parts are telemetry only: `attention_history` (`attention.py:10`), `capex_cycle`
   (`capex_cycle.py:8`), and the IV term and chain snapshots. PROD's first L1 runs on a cold cache and will be
   slower. The L1 limit is 1800 s; DEV's warm L1 takes about 5-6 min. **UNVERIFIED:** that a cold cache changes no
   gate or council input.

## 6. PROD `.env`: back up, edit, check (operator)

On PROD, Sat 11-28, after the promotion deploy, with the timers inert:
```bash
cd ~/dramatic_options
cp -p .env ~/rehearsal/env.pre-rehearsal            # restored at the end; mode 600 kept
```

**The diff, names and flags only.** The 11-12 verified state was `PAPER=false`, `LIVE_TRADING_ENABLED=false`,
`DRY_RUN=true`, `FORWARD_ENABLED=false`, with the live Alpaca pair only.

| Line | Before | Rehearsal |
|---|---|---|
| `PAPER` | `false` | **`true`** |
| `LIVE_TRADING_ENABLED` | `false` | `false` (unchanged) |
| `DRY_RUN` | `true` | `true` (unchanged; the key must be present, `verify_deploy.sh:100-101`) |
| `FORWARD_ENABLED` | `false` | **`true`** (this arms the timers at the next deploy) |
| `ALPACA_LIVE_KEY_ID`, `ALPACA_LIVE_SECRET_KEY` | present | **commented out** (`#`) |
| `ALPACA_PAPER_KEY_ID`, `ALPACA_PAPER_SECRET_KEY` | absent | **added: the REHEARSAL account's pair, never DEV's** |
| `PUSHOVER_API_TOKEN` | UNVERIFIED | **the new rehearsal app's token** |
| `PUSHOVER_USER_KEY` | UNVERIFIED | the operator's user key (same as DEV) |
| `GEMINI_API_KEY`, `XAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `PERPLEXITY_API_KEY`, `EDGAR_USER_AGENT`, `EIA_API_KEY`, `USDA_NASS_API_KEY` | UNVERIFIED | DEV's values (shared keys), so the council packs match |
| `X_BEARER_TOKEN` | UNVERIFIED | DEV's value **or omitted**: see §12 and §14 |

No legacy name (`ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_PAPER`) may appear; the verify gate fails on one
(`verify_deploy.sh:107-113`). Check names and flags only, never values:
```bash
grep -oE '^[A-Z_]+=' .env | sort
grep -E '^(PAPER|LIVE_TRADING_ENABLED|DRY_RUN|FORWARD_ENABLED)=' .env
# expect: PAPER=true  LIVE_TRADING_ENABLED=false  DRY_RUN=true  FORWARD_ENABLED=true; no ALPACA_LIVE_ line
```

## 7. Place the seed, preflight, arm (operator, on PROD)

1. Confirm that nothing is armed or running: `systemctl list-timers 'dramatic-options-*' --no-legend` lists
   nothing, and `systemctl list-units 'dramatic-options-*' --state=activating --no-legend` lists nothing.
2. Archive PROD's current DB (never delete it) and place the seed. **UNVERIFIED:** what PROD's DB holds; a
   schema-only DB is expected, since PROD has never run a cycle.
   ```bash
   mkdir -p ~/rehearsal/pre-rehearsal
   mv data/dramatic_options.db* ~/rehearsal/pre-rehearsal/
   cp ~/rehearsal/seed_2026-11-27.db data/dramatic_options.db
   # and data/drawdown_warn_state.json, if one came with the seed
   ```
   The web dashboard may hold the old file open until the arming deploy restarts it (`deploy.sh:225-226`, `:353`).
   That is harmless.
3. Preflight, read-only:
   - The verify gate by hand. It must end `All critical checks passed`. If it fails, fix `.env` first: a failed
     verify inside `deploy.sh` rolls the code back one commit **and re-arms the timers per `.env`**
     (`deploy.sh:254-276`).
     ```bash
     bash scripts/verify_deploy.sh
     ```
   - **The account is the rehearsal account, not DEV's.** Run this on both boxes and compare. The account numbers
     must differ:
     ```bash
     venv/bin/python -c "from config_loader import load_config, require_alpaca_credentials as r; \
     from data.alpaca_client import AlpacaClient; c = load_config(); k, s = r(c); a = AlpacaClient(k, s, paper=True).get_account(); \
     print(a.account_number, a.status, getattr(a, 'options_trading_level', '?'), getattr(a, 'options_approved_level', '?'))"
     ```
   - **Market-data entitlement** (SIP bars and OPRA chains on the new keys; **UNVERIFIED**). This probe runs the
     production gate pipeline on both option feeds and places nothing:
     `PYTHONPATH=. venv/bin/python scripts/probe_opra_dualread.py`. An entitlement error means stop. Without OPRA
     the gate fails closed, and the dual-read revert latch could write `OPRA_REVERTED` (`dualread_executor.py:48`),
     which would move PROD's `data_feed` stamp.
   - Whether the timers have old stamps: `ls /var/lib/systemd/timers/ 2>/dev/null | grep dramatic`. If any exist, a
     `Persistent=true` L0, L1 or post-L1 may fire once at arming. That is harmless (the market is closed: no entries,
     no council spend), but note it in the record. An L0 that fires at arming is a scan DEV did not run.
     **UNVERIFIED.**
4. Arm:
   ```bash
   ENV_NAME=PROD ./deploy.sh
   systemctl list-timers 'dramatic-options-*' --no-legend   # expect 5: l0, l1, l2, reach, post-l1
   systemctl cat dramatic-options-l1.service | grep ExecStart  # no --live
   ```
   The deploy re-runs the migrations on the seed (a no-op at the same commit; `deploy.sh:327-328`), installs the units,
   and enables the timers because `FORWARD_ENABLED=true` (`deploy.sh:173-181`). It also rebuilds the web SPA, which
   causes a short CPU spike, so arm on the weekend. **If it prints `DEPLOYMENT FAILED — INITIATING AUTOMATIC
   ROLLBACK`, go straight to §13, steps 1 and 4.**
5. Check `https://all-options-prod.tail57521e.ts.net:8602/api/version`: the same commit as DEV. The dashboard now
   shows the seed's book.

## 8. Each evening: the DEV vs PROD comparison

**Who reads:** CC, in one session each weekday evening after 16:45 ET, with the operator's go for the week to ssh to
PROD read-only. The DEV nightly grade is unchanged and reads DEV only. CC writes one dated record at the end,
`records/2026-12-04_prod_rehearsal_record.md`, with one section per day.

**The read:** the same script on both DBs, `?mode=ro`, for the day's UTC date (L1 = 20:45 UTC, L0 = 13:00 UTC). Run
on DEV against 11-20, it printed the stamps, the 12 council proposals, the 50 OPRA gate rows and SMCI's entry. Save
it as `~/rehearsal/cmp.py` on DEV:
```python
import sqlite3, sys
db, day = sys.argv[1], sys.argv[2]          # day: the UTC date, YYYY-MM-DD
c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
def show(label, sql):
    rows = c.execute(sql, (day,)).fetchall()
    print(f"## {label} ({len(rows)})")
    for r in rows:
        print("  ", r)
show("L1 stamps", "SELECT frame_version, model_mix, data_feed, council_health FROM runs "
     "WHERE date(started_at)=? AND model_mix IS NOT NULL")
show("L0 surfaced", "SELECT symbol, direction, kind, status FROM sentinel_candidates "
     "WHERE date(last_seen_at)=? ORDER BY symbol")
show("council", "SELECT p.symbol, p.direction, p.conviction, p.status FROM council_proposals p "
     "JOIN runs r ON r.id=p.run_id WHERE date(r.started_at)=? ORDER BY p.symbol")
show("gate of record (opra)", "SELECT symbol, structured, round(iv_rv,3), round(otm_skew,1), cheap, wing "
     "FROM gate_dualread WHERE date(evaluated_at)=? AND feed='opra' ORDER BY symbol")
show("real-book evals", "SELECT symbol, decision, round(iv_rv,3), round(otm_skew,1) FROM convexity_eval "
     "WHERE date(evaluated_at)=? ORDER BY symbol")
show("real-book opened", "SELECT symbol, contract_symbol, contracts, entry_premium_per_contract, status "
     "FROM convexity_positions WHERE date(opened_at)=?")
show("real-book closed", "SELECT id, contract_symbol, exit_reason, realized_pnl FROM convexity_positions "
     "WHERE date(closed_at)=?")
show("null books opened", "SELECT 'shadow', symbol, contract_symbol, contracts FROM shadow_positions "
     "WHERE date(opened_at)=?1 UNION ALL SELECT book, symbol, contract_symbol, contracts "
     "FROM fixed_basket_positions WHERE date(opened_at)=?1")
show("null books closed", "SELECT 'shadow', contract_symbol, exit_reason FROM shadow_positions "
     "WHERE date(closed_at)=?1 UNION ALL SELECT book, contract_symbol, exit_reason "
     "FROM fixed_basket_positions WHERE date(closed_at)=?1")
show("held reads", "SELECT symbol, conviction, include, dropped FROM held_reads WHERE date(created_at)=?")
```
```bash
D=2026-11-30
python3 ~/rehearsal/cmp.py /home/rozavala/dramatic_options/data/dramatic_options.db $D > ~/rehearsal/dev_$D.txt
ssh console@all-options-prod "python3 - /home/console/dramatic_options/data/dramatic_options.db $D" \
    < ~/rehearsal/cmp.py > ~/rehearsal/prod_$D.txt
diff ~/rehearsal/dev_$D.txt ~/rehearsal/prod_$D.txt
```
Plus, each evening, from PROD's journal: `journalctl -u 'dramatic-options-*' --since today | grep -E 'DRY_RUN \(not sent\)|SUBMITTED|FILLED|ERROR'`.
The rehearsal app's pages are checked too.

**Must match** (a difference is a finding):
- the stamps `frame_version`, `model_mix` and `data_feed`;
- the gate of record per name. It is the same OPRA chain read seconds apart, so `structured`, `cheap` and the wing
  should be equal. A small `iv_rv` delta from a quote tick is recorded; a flip is investigated;
- the L0 surfaced set on the deterministic markers (the framer is an LLM; its text may differ);
- the backfill line, and the null books' opens and closes (shadow, 3A, 3B, shares);
- for the same name, the intended order: contract, quantity and limit.

**Expected to differ** (recorded, not failures):
- council verdicts and held reads (LLM output);
- run, proposal and position ids;
- `runs.equity`;
- cold-cache telemetry;
- an exit that fires (§1, row 3).

Also: **a DEV entry rests as a real limit and may carry, while PROD's DRY_RUN entry fills at once.** From that day
the two books' slots and budgets differ. Note the day, and compare later decisions knowing that.

## 9. #466 and #463 on the rehearsal account (DRY_RUN stays true)

The operator runs both from PROD's live checkout during market hours. They use the rehearsal paper pair. Neither
writes PROD's journal, and the DRY_RUN loop beside them transmits nothing, so the account holds only their orders.

- **#466, the exit drill:** follow the run order in `scripts/drill_exit_paths.py:57-108` with
  `D=~/drill466`. Use its scrubbed-environment wrapper with `~/drill466/paper.env`, which holds only the rehearsal
  pair and `PAPER=true`. The drill refuses any `ALPACA_LIVE_*` in its environment, `LIVE_TRADING_ENABLED=true` or
  `PAPER=false` (`:208-215`), and any path that resolves to the production journal.
  - Week-1 paths (profit-take, time-stop, unsellable, pre-market, resting-close) fit Mon 11-30 to Tue 12-01.
  - The expiry paths need contracts that expire Fri 12-04. Their `observe` steps run through Tue 12-08, after the
    loop is disarmed. That is fine: they need only `paper.env`.
  - Flatten any exercised shares by hand in the paper dashboard.
  - It answers #444's open questions first hand: `OPEXP`, exercise or liquidation, and when the position API shows
    each.
- **#463, the spread round-trip:**
  1. List candidates read-only: `PYTHONPATH=. venv/bin/python scripts/probe_vertical_feasibility.py`.
  2. Run one 1-lot round-trip:
     `python scripts/smoke_order_roundtrip.py --endpoint paper --contract <LONG OCC> --limit <debit> --vertical-short <SHORT OCC> --sell-limit <credit> --send`.
     It reads `PROD/.env`; with `PAPER=true` that is the rehearsal pair.
  3. Record acceptance, the raw `filled_avg_price` and its sign on the open and on the close, and the time to fill.
- **Not covered by any tool:** a spread held to expiry (#444 item 3). Either the operator places one by hand in the
  paper dashboard and records it, or it becomes a follow-up (§15).
- Order ids on the account: `do-drill-…` (drill), `do-smoke…` (smoke). Any `do-open-…` or `do-close-…` order means
  the loop transmitted: **abort** (§11).

## 10. Option, not recommended: a bounded `DRY_RUN=false` window

**What it would add:** the loop's own real paper path on PROD: `do-open-` entries, the carry walk, reconcile, closes,
and the venue check. DEV already runs exactly this code with `DRY_RUN=false` every day on its own paper account. The
new information would be PROD's host, keys and units only.

**Why not on the seed:** with `DRY_RUN=false` the venue check turns on (`venue_check.py:564`).
- It would read venue 0 against the journal for the 4 copied contracts, and for every row PROD opened under DRY_RUN,
  and page them.
- A triggered exit on such a row would try a real `SELL_TO_CLOSE` of a contract the account does not hold. Alpaca's
  answer is **UNVERIFIED** (expected: a rejection, then a daily "CLOSE REFUSED" page, `monitor.py:311-321`).

**If the operator wants it anyway**, it is a separate step after the comparison week:
1. Disarm (§13, steps 1-3).
2. Archive the rehearsal DB.
3. Start from an **empty** DB (starting option ii). The deploy's migrations create the schema.
4. Set `DRY_RUN=false`, arm, and run for at most 3 sessions.
5. Disarm.

**Blast radius:**
- the rehearsal paper account only. The broker class is fixed to the paper endpoint (`broker.py:153`, `:353`). The
  triple gate is unchanged (`PAPER=true`, `LIVE_TRADING_ENABLED=false`, no `--live`, live pair commented out);
- simulated money only, bounded by the frozen frame: at most $1,000 per name, $10,000 for the book, 15 open;
- DEV's account is unreachable, because its keys are not on PROD;
- DEV's record is untouched.

## 11. Abort criteria (any one: §13 at once)

1. The loop transmitted while `DRY_RUN=true`: a `do-open-` or `do-close-` order on the rehearsal account, or a
   `SUBMITTED`/`FILLED` line from an l1 or l2 unit on PROD.
2. The account check fails: PROD's pair resolves to DEV's account, or `.env` flags drift from §6.
3. `--live` appears in a unit's `ExecStart`.
4. Real Options is affected: `trading-bot` fails, restarts or is killed during our runs, or the host's load or memory
   alarms.
5. Shared-key exhaustion: a `Council provider-dead` page or a spend-tripwire page on either box, or the provider
   console shows a shared key near its limit.
6. DEV's record shows anything PROD could have written (impossible by construction): an unexplained DEV run, or a
   `segment_register.py --check` drift on DEV.
7. PROD's pages arrive under DEV's app (the wrong token).

A PROD unit failure (an `OnFailure` page) is investigated first. It is an abort if it repeats the next day.

## 12. Risks and containment

- **The wrong paper pair on PROD (DEV's).** DRY_RUN still sends nothing. The only path that reaches the venue
  unconditionally, `cancel_order`, would then have a target. Contained by the account-number check (§7.3) and the
  seed rule (no `pending`, `carried` or `closing` rows).
- **LLM spend on shared keys.** Measured on DEV from `council_agent_outputs`, W42-W46:
  - council: Anthropic $0.81-0.99 a week, Gemini $0.24-0.26, xAI $0.11-0.13, about $1.3 a week;
  - held reads: about $0.20 a day (11-16 to 11-20);
  - L0 framer: about $0.002.
  - **Realistic extra for W48: about $2.5-3.**
  - **Ceiling from the caps:** council $5 × 5 + held reads $1 × 5 + discovery $3 + drafter $0.50 = **$33.50**
    (+$7.50 if the probe runs in the fallback week).
  - November Anthropic MTD on DEV was $2.88 at 11-20, against a $10 page.
  - The risk is the provider-side cap shared with other users of the keys (the 2026-08-26 case). Neither box's
    tripwire sees the combined spend. **UNVERIFIED:** the console limits. The operator checks the headroom before arming.
- **X API (`X_BEARER_TOKEN`).** A shared token doubles the x_lists reads. **UNVERIFIED:** its quota. If headroom is
  unknown, omit it on PROD: the channel fails closed and is counted, the council packs differ, and that is recorded.
- **Pages.** `verify_deploy.sh:100-101` requires `PUSHOVER_API_TOKEN` and `PUSHOVER_USER_KEY` on a FORWARD_ENABLED
  env, so the deploy fails without them. Titles carry no environment (`notify.py:59`); the separate app's name and
  icon are the distinction. **UNVERIFIED:** how the operator's Pushover client displays the app.
- **Load beside Real Options.** Measured on DEV on 11-19/20:
  - L1: about 14-15 s CPU over 5-6 min wall, about 360 MB peak;
  - L2: about 2.6 s CPU, 15 s, 112 MB;
  - post-L1: about 3 s CPU, 80 s, 200 MB.

  The L1 is bounded at 1800 s. The `pkill` class is fixed on both sides (#312; real_options #4953), and our
  `stop_units` patterns are port- and path-qualified (`deploy.sh:225-232`). **UNVERIFIED:** PROD's RAM and CPU
  headroom, and Real Options' schedule. Check `trading-bot` after each 15:45 L1 on the first two days.
- **A deploy rollback re-arms on old code** (`deploy.sh:254-276`). Contained by the hand-run verify gate before arming.
- **The Sunday review sees PROD armed.** Contained by the STANDING_STATE note before 11-29.
- **The reach unit writes `records/digests/` and `records/cards/` as untracked files in PROD's checkout**, and uses
  up to $0.50 of drafter spend. Harmless. Leave the files, or move them into the archive at teardown. They are never
  committed from PROD.
- **A reboot during the week.** `Persistent=true` catch-ups are safe by design (DEPLOYMENT.md), but a missed 15:45
  L1 shifts PROD's decisions to after the close. Reboot before arming, not during W48.

## 13. Return to inert (Fri 12-04 after 16:35 ET, or at once on an abort)

On PROD:
1. On an abort only: `touch ~/dramatic_options/KILL`. Every unit halts at its next start. With no `pending` rows the
   KILL cancel has nothing to do (`orchestrator.py:786-789`).
2. Disarm and wait for any running oneshot to end:
   ```bash
   sudo systemctl disable --now dramatic-options-l0.timer dramatic-options-l1.timer dramatic-options-l2.timer \
       dramatic-options-reach.timer dramatic-options-post-l1.timer
   systemctl list-units 'dramatic-options-*' --state=activating --no-legend   # until empty
   ```
3. Restore the `.env` exactly, then check the flags:
   ```bash
   cp -p ~/rehearsal/env.pre-rehearsal ~/dramatic_options/.env
   grep -E '^(PAPER|LIVE_TRADING_ENABLED|DRY_RUN|FORWARD_ENABLED)=' ~/dramatic_options/.env
   # expect PAPER=false LIVE_TRADING_ENABLED=false DRY_RUN=true FORWARD_ENABLED=false
   ```
4. Archive the rehearsal DB (never delete it). No writer is running, so move the database together with its WAL and
   SHM files, then put the pre-rehearsal DB back:
   ```bash
   mkdir -p ~/rehearsal/archive_2026-12-04
   mv ~/dramatic_options/data/dramatic_options.db* ~/rehearsal/archive_2026-12-04/
   mv ~/dramatic_options/data/drawdown_warn_state.json ~/rehearsal/archive_2026-12-04/ 2>/dev/null
   cp -p ~/rehearsal/pre-rehearsal/dramatic_options.db* ~/dramatic_options/data/
   python3 -c "import sqlite3; c = sqlite3.connect('file:$HOME/rehearsal/archive_2026-12-04/dramatic_options.db?mode=ro', uri=True); print(c.execute('PRAGMA integrity_check').fetchone()[0], c.execute('SELECT MAX(id) FROM runs').fetchone()[0])"
   ```
5. Remove `KILL` if it was set, then re-run the deploy to prove the env is inert:
   ```bash
   cd ~/dramatic_options && ENV_NAME=PROD ./deploy.sh   # expect "FORWARD_ENABLED=false → timers installed-but-inert"
   systemctl list-timers 'dramatic-options-*' --no-legend   # expect nothing
   ```
6. Keep the rehearsal paper account and `~/drill466/` (the expiry observations run to 12-08). Disable the rehearsal
   Pushover app when the drill is done.
7. CC updates STANDING_STATE (PROD inert, rehearsal done, the record's link) and writes the dated record.

## 14. Open questions for the operator

1. **Window:** W48 (copy Fri 11-27, run 11-29 → 12-04), with 12-06 → 12-11 as the fallback?
2. **The live pair:** comment it out of PROD's `.env` for the rehearsal (recommended)?
3. **`DRY_RUN=false` window:** none (recommended), or §10 after the comparison week on an empty DB?
4. **Merge hold:** trading-path merges to main held Sat 11-28 → Fri 12-04 16:30 ET?
5. **`X_BEARER_TOKEN` on PROD:** share it (if the quota allows), or omit it?
6. **The nightly read:** CC with one ssh go for the week (recommended), or the operator?
7. **An expiring spread for #444:** placed by hand in the paper dashboard, or a follow-up tool?
8. **PROD's libc6 reboot:** before arming on 11-28?

## 15. Follow-ups that would need code (none is needed for the rehearsal)

- The environment name in page titles (`notify.py:59`). Telemetry, with no stamp.
- A committed comparison script (`scripts/ops/`) if the rehearsal is repeated. The §8 snippet is enough for one week.
- #444's possible follow-ups: read `OPEXP`/`OPXRC`/`OPASN` in the venue check, and a tool to hold a 1-lot vertical
  through expiry on paper.

## UNVERIFIED (collected)

1. PROD's current `.env` beyond the 11-12 names and flags: whether it holds the LLM, Pushover, EDGAR, EIA, USDA and
   X keys.
2. What PROD's current `data/dramatic_options.db` holds.
3. SIP and OPRA entitlement on the new paper account's keys.
4. The new paper account's default options level and equity.
5. Whether systemd timer stamps exist on PROD (a catch-up at arming).
6. That DEV is clean (no `pending`, `carried` or `closing` row) on Fri 11-27 after 16:30 ET.
7. That a cold cache changes no gate or council input.
8. The provider-console spend limits on the shared LLM keys, and the X API quota.
9. PROD's CPU and RAM headroom beside `trading-bot`, and Real Options' schedule.
10. How the Pushover client shows the rehearsal app's pages.
11. Alpaca's answer to a `SELL_TO_CLOSE` for a contract the account does not hold (only relevant to §10).
12. Spread handling at expiry (#444): no tool covers it.
