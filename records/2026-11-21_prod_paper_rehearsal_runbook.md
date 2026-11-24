# 2026-11-21 — The PROD paper rehearsal: runbook (#468)

**Status: a runbook, operator-run. Amended 2026-11-24 to a SHARED-ACCOUNT rehearsal on the operator's answers of
that day (§14). Nothing here arms live trading. The triple gate stays shut throughout: `PAPER=true`,
`LIVE_TRADING_ENABLED=false`, no `--live` in any unit (`config_loader.py:180-194`). `DRY_RUN=true` stays on for the
whole window.**

**Basis.**
- The operator's word of 2026-11-12 ("OK to draft the inert arming PR and a 1-week paper rehearsal on a separate
  paper account"; `records/2026-11-12_operator_decisions_roadmap.md`; IMPLEMENTATION_PLAN, decision 5).
- **Changed by the operator's answers of 2026-11-24:**
  - the rehearsal runs on **DEV's paper account, shared**, not a second account;
  - pages use **DEV's existing Pushover app**, told apart by #544's `[PROD]` title tag;
  - the X token is shared;
  - the #466 and #463 drills are **deferred** (§9).
- It builds on §5 of the draft `records/2026-11-10_t4_go_no_go_checklist_DRAFT.md` (branch
  `records/roadmap-protocol-drafts-2026-11-10`).

Code citations are against main `4fc9ab0` unless noted. Items marked **UNVERIFIED** could not be checked from DEV
without ssh to PROD.

## 0. Decisions, and why

1. **Window: Tue 11-24 → Tue 12-01.** That is 5 sessions: Tue 11-24, Wed 11-25, the Fri 11-27 half day (Thu is
   closed), Mon 11-30 and Tue 12-01. The run includes Sun 11-29's L0 and reach. The seed was taken Mon 11-23 after the 16:30 ET tick. PROD is
   rebooted (libc6), promoted (#548) and armed before Tue 11-24 09:00 ET. It returns to inert Tue 12-01 after
   16:35 ET. All of this is before boundary B (12-05/06) and the 12-07 → 12-18 stamp freeze.
2. **Shared paper account.** It is safe because PROD transmits nothing and can cancel only rows in its own DB (§1).
   Two shared-account divergences are accepted and logged: a foreign-quantity veto after a same-day DEV fill, and the
   shared Alpaca rate limit. A rate-limit hit is an abort (§11).
3. **The copied open positions stay as they are** (no edit to the copy). Under DRY_RUN nothing compares them with
   the venue. Keeping them is what makes slots, the cluster budget, the backfill trigger and the kill rule match
   DEV. They diverge only if an exit triggers (§1, row 3).
4. **`DRY_RUN=true` throughout.** The DRY_RUN=false window does not apply on a shared account (§10). The drills are
   deferred to a separate account before T4 (§9).
5. **The live pair is commented out of PROD's `.env`** for the window. The pre-rehearsal `.env` is backed up and
   restored exactly at the end.
6. **No code.** #544's `[PROD]` page tag reaches PROD with this promotion.

## 1. What PROD does with a DEV copy on DEV's paper account (read-only code read)

Flags: `PAPER=true` with DEV's paper pair, `LIVE_TRADING_ENABLED=false`, `DRY_RUN=true`, `FORWARD_ENABLED=true`, and
units without `--live`. The broker is `AlpacaPaperBroker` (`orchestrator.py:324-334`, `:856`, `:920`), fixed to the
paper endpoint (`broker.py:153`, `:353`).

| # | Path | What PROD does | Consequence on the shared account |
|---|---|---|---|
| 1 | **Order transmission** | `submit_paper` and `submit_spread` return a simulated fill before any `submit_order` (`broker.py:212-215`, `:281-285`). DRY_RUN entries are booked `open` at the limit, never `pending` (`paper_loop.py:632-633`). | PROD sends no order to DEV's account. |
| 2 | **Venue/journal check (#481)** | Off under DRY_RUN: `venue_check.run_tick` returns at `venue_check.py:564-574`; the orchestrator passes the configured `dry_run` (`orchestrator.py:1015-1019`). | PROD never pages a venue mismatch. DEV's own check is unchanged: PROD adds nothing at the venue. |
| 3 | **L2 marks and exits** | Marks come from market data. `real_submit` is false under DRY_RUN (`monitor.py:194`), so a triggered profit-take or time-stop is booked in-DB at the mark (`monitor.py:342-357`). Under DRY_RUN this happens on a closed-market tick too (`orchestrator.py:450-461`), where DEV defers the exit (#451), sells, or orphans (#444). Expiry books intrinsic on both. | A known divergence, only if a trigger fires. **PROD never sells DEV's contracts.** No trigger is near (§8). |
| 4 | **Foreign-quantity veto (`broker.venue_quantity`)** | Runs on every NEW entry, DRY_RUN or not (`paper_loop.py:558-590`). It reads the shared account's quantity in that one contract and compares it with PROD's journal. Held names are blocked earlier by the per-name dedup (`paper_loop.py:203`). | **Known divergence 1:** if DEV fills a name before PROD's L1 reads it, PROD sees venue N against journal 0, vetoes the entry (`veto-foreign-quantity`) and pages priority 1 ("Foreign quantity — entry refused", tagged `[PROD]`). This is logged, not a failure. |
| 5 | **Reconcile, the 15:30 carry cancel, the KILL cancel** | `cancel_order` is **not** DRY_RUN-gated (`broker.py:342-346`). It is reached only through `carry.cancel_and_settle` (`carry.py:117-122`), which is called by `reconcile_pending` (`monitor.py:574-611`, every cycle at `orchestrator.py:939`), the carry worker, and the KILL cancel (`orchestrator.py:765-845`). Each acts only on `pending` rows with an order id, or on `carried` intents, in **PROD's own DB**. | The seed has none, and DRY_RUN creates none (row 1). So **PROD can never cancel DEV's orders**, though the keys would allow it. That is why the seed rule (no `pending`, `carried` or `closing` row) is load-bearing here. |
| 6 | **`closing` rows** | `_reconcile_closing` runs only when `real_submit` is true (`monitor.py:200`). | Nothing to do. The seed has none. |
| 7 | **Held reads (post-L1)** | On in config; capped at $1.00 a pass (`council/held_reads.py:60`, `:257`). The repeat probe stays off until #519. | The 5 copied positions are re-read nightly. These are LLM reads: differences are recorded, not failures. |
| 8 | **Kill rule and drawdown page** | Both read only the DB and config (`paper_loop.py:77-122`; `orchestrator.py:145-167`). | Identical to DEV. DEV had no `drawdown_warn_state.json`, so none was copied. |
| 9 | **Sizing and `runs.equity`** | Sizing uses `convexity_book.account_equity` from config (`paper_loop.py:183`). `runs.equity` is read from the account. | Same account, so `runs.equity` matches DEV as well. |
| 10 | **Alpaca rate limit** | Both boxes call the API with the same key pair: marks, chains, clock and venue reads. | **Known divergence 2:** they share one limit. About 72 bound requests per tick per box, against about 200 per minute per key (estimate; **UNVERIFIED** against Alpaca's current limit). Any HTTP 429 or rate-limit line on either box is an **abort** (§11). |
| 11 | **Spend tripwire** | MTD is summed from the box's own DB (`orchestrator.py:304-317`, `state.py:1140`). | Neither box sees the combined spend (§12). |
| 12 | **Pages** | With #544 (on main), titles carry `Dramatic Options [PROD]` or `[DEV]`, from `DRAMATIC_ENV`, which the deploy renders into every unit (`notify.py` on main). | DEV's app and user key are shared. The tag tells the boxes apart. PROD gets #544 with the #548 promotion. |

**Expected PROD pages:** none in normal operation, except a foreign-quantity page after a same-day DEV fill (row 4).

## 2. Preconditions

**Operator:**
1. Reboot PROD (libc6) before arming, outside Real Options' activity. Answered: yes.
2. One go for CC to ssh to PROD read-only each evening of the window. Answered: given.

**CC:**
1. The seed. **Done 2026-11-23** (§5).
2. Promotion #548 (`production ← main`) at the commit DEV runs. PROD was at `d276bf1`, which lacks #527, #533/#535,
   the 0024 repair, #531 and #544.
3. STANDING_STATE says PROD is armed until 12-01 before the Sun 11-29 Sunday review, which checks PROD's units.
4. A merge hold on trading-path changes to main (§3).

## 3. Timeline

| When (ET) | Who | What |
|---|---|---|
| Mon 11-23, after 16:35 | CC, on DEV | The seed. **Done:** `SEED OK` (§5). |
| Mon 11-23 night → Tue 11-24 before 09:00 | operator | Reboot PROD; merge #548 (the CI deploy lands inert); move the seed; back up and edit `.env`; preflight; arm (§5-§7). |
| Tue 11-24 → Tue 12-01 | timers; CC each evening | L2 ticks, the 15:45 L1, the 16:10 post-L1. On Sun 11-29, L0 and reach. Nightly comparison after 16:45 (§8). |
| Fri 11-27 | — | A half day (13:00 close). The 15:45 L1 finds the market closed: no entries and no council spend. |
| Tue 12-01, after 16:35 | operator | Return to inert (§13). CC writes the dated record. |
| Sat 12-05 / Sun 12-06 | — | Boundary B merges on main for DEV, as planned. PROD stays inert. |

**Merge hold (answered: yes), Tue 11-24 → Tue 12-01 16:35 ET.**
- No trading-path merge to main: `orchestrator.py`, `paper_loop.py`, `monitor.py`, `broker.py`, `carry.py`,
  `council/`, `convexity_*`, `config.json`.
- Records, dashboard and test-only merges may land.
- An off-cycle fix (money-safety, fail-closed outage) is promoted to PROD before the next L1 and noted in the record.

**The stamp freeze is not touched.** The window ends before 12-07. PROD's runs stamp only PROD's DB. The nightly
grade reads DEV's DB only (`scripts/ops/prompts/nightly_grade.md:7`), and so does the segment register
(`records/segment_register.md:15-16`).

## 4. The promotion (#548)

#548 promotes main's HEAD, which must be the commit DEV runs (check DEV's `/api/version`). With `FORWARD_ENABLED=false`
still in PROD's `.env`, its CI deploy is inert:
- the key check is skipped (`scripts/verify_deploy.sh:94-133`);
- the timers stay disabled (`deploy.sh:173-185`);
- the migrations run on PROD's current DB (`deploy.sh:327-328`).

Afterwards, PROD's `/api/version` must show the same commit as DEV's.

## 5. The seed (DEV, done) and its transport

**Done by CC on Mon 11-23 after the 16:30 ET tick.** CC used the script below: SQLite's backup API from a
`?mode=ro` connection, never `cp` of a live WAL DB.
- File: `~/rehearsal/seed_2026-11-23.db` on DEV.
- Result: `SEED OK`. Last run `#2160`, `2026-11-23 21:30` UTC.
- Open rows: 1 PL, 6 FLNC, 7 TITN, 13 RDW, 16 SMCI.
- sha256: `d72700e70b65150453c1dfa366465267303ff01070b8f5932d5caec6ec9d9f10`.
- DEV had no `data/drawdown_warn_state.json`, so none goes with it.

The script, for the record and for any re-take:
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

Transport (operator; PROD user `console`):
```bash
ssh console@all-options-prod 'mkdir -p ~/rehearsal && chmod 700 ~/rehearsal'
scp ~/rehearsal/seed_2026-11-23.db console@all-options-prod:~/rehearsal/
ssh console@all-options-prod 'sha256sum ~/rehearsal/seed_2026-11-23.db'
# must print d72700e70b65150453c1dfa366465267303ff01070b8f5932d5caec6ec9d9f10
```

`data/cache/` (471 MB) is not copied. It is a point-in-time read-through cache, and its history-bearing parts are
telemetry only (`attention.py:10`, `capex_cycle.py:8`, the IV term and chain snapshots). PROD's first L1 runs cold
and slower; the L1 limit is 1800 s. **UNVERIFIED:** that a cold cache changes no gate or council input.

## 6. PROD `.env`: back up, edit, check (operator)

On PROD, after the #548 deploy, with the timers inert:
```bash
cd ~/dramatic_options
cp -p .env ~/rehearsal/env.pre-rehearsal            # restored exactly at the end; mode 600 kept
```

**The diff, names and flags only.** The verified state of 2026-11-12 was `PAPER=false`,
`LIVE_TRADING_ENABLED=false`, `DRY_RUN=true`, `FORWARD_ENABLED=false`, with the live Alpaca pair only.

| Line | Before | Rehearsal |
|---|---|---|
| `PAPER` | `false` | **`true`** |
| `LIVE_TRADING_ENABLED` | `false` | `false` (unchanged) |
| `DRY_RUN` | `true` | `true` (unchanged; the key must be present, `verify_deploy.sh:100-101`) |
| `FORWARD_ENABLED` | `false` | **`true`** (arms the timers at the next deploy) |
| `ALPACA_LIVE_KEY_ID`, `ALPACA_LIVE_SECRET_KEY` | present | **commented out** (`#`) |
| `ALPACA_PAPER_KEY_ID`, `ALPACA_PAPER_SECRET_KEY` | absent | **added: DEV's paper pair** |
| `PUSHOVER_API_TOKEN`, `PUSHOVER_USER_KEY` | UNVERIFIED | DEV's values (one app; `[PROD]` tags PROD's pages) |
| `GEMINI_API_KEY`, `XAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `PERPLEXITY_API_KEY`, `EDGAR_USER_AGENT`, `EIA_API_KEY`, `USDA_NASS_API_KEY`, `X_BEARER_TOKEN` | UNVERIFIED | DEV's values (shared), so the council packs match |

No legacy name (`ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_PAPER`) may appear; the verify gate fails on one
(`verify_deploy.sh:107-113`). Check names and flags only, never values:
```bash
grep -oE '^[A-Z_]+=' .env | sort
grep -E '^(PAPER|LIVE_TRADING_ENABLED|DRY_RUN|FORWARD_ENABLED)=' .env
# expect: PAPER=true  LIVE_TRADING_ENABLED=false  DRY_RUN=true  FORWARD_ENABLED=true; no ALPACA_LIVE_ line
```

## 7. Place the seed, preflight, arm (operator, on PROD)

1. Nothing may be armed or running. Both of these must list nothing:
   ```bash
   systemctl list-timers 'dramatic-options-*' --no-legend
   systemctl list-units 'dramatic-options-*' --state=activating --no-legend
   ```
2. Archive PROD's current DB (never delete it), then place the seed. **UNVERIFIED:** what PROD's DB holds; it is
   expected to be schema-only.
   ```bash
   mkdir -p ~/rehearsal/pre-rehearsal
   mv data/dramatic_options.db* ~/rehearsal/pre-rehearsal/
   cp ~/rehearsal/seed_2026-11-23.db data/dramatic_options.db
   ```
   The web dashboard may hold the old file open until the arming deploy restarts it (`deploy.sh:225-226`, `:353`).
3. Preflight, read-only:
   - **The verify gate, by hand.** It must end with `All critical checks passed`. Run it first because a failed verify
     inside `deploy.sh` rolls the code back one commit and **re-arms the timers per `.env`** (`deploy.sh:254-276`).
     ```bash
     bash scripts/verify_deploy.sh
     ```
   - **The account must be DEV's paper account.** The account number must match DEV's (ending `…8X2M`), with
     options level 3. A different account means the wrong pair: stop.
     ```bash
     venv/bin/python -c "from config_loader import load_config, require_alpaca_credentials as r; \
     from data.alpaca_client import AlpacaClient; c = load_config(); k, s = r(c); a = AlpacaClient(k, s, paper=True).get_account(); \
     print(a.account_number, a.status, getattr(a, 'options_trading_level', '?'), getattr(a, 'options_approved_level', '?'))"
     ```
   - **Old timer stamps:** `ls /var/lib/systemd/timers/ 2>/dev/null | grep dramatic`. If any exist, a `Persistent=true`
     unit may fire once at arming. That is harmless (the market is closed), but note it in the record. **UNVERIFIED.**
4. Arm before Tue 11-24 09:00 ET:
   ```bash
   ENV_NAME=PROD ./deploy.sh
   systemctl list-timers 'dramatic-options-*' --no-legend      # expect 5: l0, l1, l2, reach, post-l1
   systemctl cat dramatic-options-l1.service | grep -E 'ExecStart|DRAMATIC_ENV'   # no --live; DRAMATIC_ENV=PROD
   ```
   The deploy re-runs the migrations on the seed (a no-op at the same commit), installs the units, and enables the
   timers because `FORWARD_ENABLED=true` (`deploy.sh:173-181`). **If it prints `DEPLOYMENT FAILED — INITIATING
   AUTOMATIC ROLLBACK`, go straight to §13.**
5. Check that `https://all-options-prod.tail57521e.ts.net:8602/api/version` shows the same commit as DEV.

## 8. Each evening: the DEV vs PROD comparison

**Who reads:** CC, in one session each weekday evening after 16:45 ET, with the operator's ssh go for the window (given).
The DEV nightly grade is unchanged. CC writes `records/2026-12-01_prod_rehearsal_record.md` at the end, with one section per
day.

**The read:** the same script on both DBs, `?mode=ro`, for the day's UTC date (L1 = 20:45 UTC, L0 = 13:00 UTC).
Tested on DEV against 11-20. Save it as `~/rehearsal/cmp.py` on DEV:
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
D=2026-11-24
python3 ~/rehearsal/cmp.py /home/rozavala/dramatic_options/data/dramatic_options.db $D > ~/rehearsal/dev_$D.txt
ssh console@all-options-prod "python3 - /home/console/dramatic_options/data/dramatic_options.db $D" \
    < ~/rehearsal/cmp.py > ~/rehearsal/prod_$D.txt
diff ~/rehearsal/dev_$D.txt ~/rehearsal/prod_$D.txt
```
**Each evening, on both boxes' journals (an abort check, §11):**
```bash
# DEV
journalctl -u 'dramatic-options-*' --since today | grep -iE ' 429|rate.?limit|too many requests'
# PROD: the same grep, plus anything PROD may have sent
ssh console@all-options-prod "journalctl -u 'dramatic-options-*' --since today | \
    grep -iE ' 429|rate.?limit|too many requests|SUBMITTED|FILLED|foreign-quantity|ERROR'"
```
Both must print no rate-limit line. PROD must print no `SUBMITTED` or `FILLED` line. Its `DRY_RUN (not sent)` lines
are expected.

**Must match** (a difference is a finding):
- the stamps `frame_version`, `model_mix` and `data_feed`;
- the gate of record per name. It is the same OPRA chain read seconds apart, so `structured`, `cheap` and the wing
  are equal. A small `iv_rv` delta is recorded; a flip is investigated;
- Sunday 11-29's L0 surfaced set, on the deterministic markers;
- the backfill line, and the null books' opens and closes;
- the intended order (contract, quantity, limit) for the same name.

**Expected to differ** (recorded, not failures):
- council verdicts and held reads (LLM output);
- run, proposal and position ids;
- cold-cache telemetry;
- a triggered exit (§1, row 3). At the 11-20 marks no exit is near: FLNC ×2.18 against the 4× profit-take; PL's
  21-DTE time-stop starts 12-25;
- a foreign-quantity veto after a same-day DEV fill (§1, row 4);
- a DEV entry that rests and carries while PROD's DRY_RUN entry fills at once. From that day the slots and budgets
  differ; note the day.

## 9. #466 and #463: deferred

Deferred on the operator's answer of 2026-11-24, together with the expiring spread (#444 item 3). Both drills place
**real paper orders**. On the shared account:
- DEV's venue check would read them as mismatches (`venue_check.py`, on for DEV);
- they could net into, or sell, DEV's contracts.

They need a **separate paper account** before T4. The tools are ready and need no change:
- `scripts/drill_exit_paths.py` sets its own transmit flag (`dry_run=not send`, `:324`), refuses any live key
  (`:208-215`) and uses a scratch journal;
- `scripts/smoke_order_roundtrip.py` sets `dry = not args.send` (`:224`) and never writes the journal.

## 10. A `DRY_RUN=false` window: not applicable

On a shared account, the PROD loop sending orders would place `do-open-` and `do-close-` orders into DEV's account.
DEV's journal does not explain them, so DEV's venue check and foreign-quantity veto would fire. PROD's own venue check
would also see DEV's positions as foreign. The answer of 2026-11-24 is: no DRY_RUN=false window.

## 11. Abort criteria (any one: §13 at once)

1. **Any HTTP 429 or rate-limit line in DEV's or PROD's journal** (§1, row 10; §8). The shared limit must never
   cost DEV a mark or an order.
2. PROD transmitted: a `SUBMITTED` or `FILLED` line from a PROD unit. Or DEV's account shows a `do-open-` or
   `do-close-` order, or a cancel, that DEV's journal does not explain.
3. PROD's `.env` flags drift from §6, or `--live` appears in a unit's `ExecStart`.
4. DEV's record is disturbed: an unexplained DEV run, a venue-check page on DEV caused by PROD, or a
   `segment_register.py --check` drift on DEV.
5. Real Options is affected: `trading-bot` fails, restarts or is killed during our runs, or the host's load or memory
   alarms.
6. Shared-key exhaustion: a `Council provider-dead` page or a spend-tripwire page on either box.

A PROD unit failure (`OnFailure` page, tagged `[PROD]`) is investigated first. If it repeats the next day, abort.

## 12. Risks and containment

- **DEV's orders, reachable with the shared keys.** `cancel_order` is the only venue-writing call that is not
  DRY_RUN-gated. It acts only on `pending` or `carried` rows in PROD's DB (§1, row 5). The seed has none, and DRY_RUN
  creates none. The `KILL` cancel on PROD also reads PROD's journal only (`orchestrator.py:786-789`).
- **The shared Alpaca rate limit.** See §1, row 10. Contained by the nightly grep and abort 1.
- **LLM spend on shared keys** (measured on DEV, W42-W46):
  - council about $1.3 a week; held reads about $0.20 a day;
  - realistic extra for the window: about $2.5-3. The Fri 11-27 L1 has no council;
  - ceiling from the caps: about $30;
  - neither box's tripwire sees the combined spend. **UNVERIFIED:** the provider console limits.
- **X API:** the shared token doubles the x_lists reads. **UNVERIFIED:** its quota. A failure there fails closed and
  is counted.
- **Pages:** one shared app. `[PROD]` and `[DEV]` tell them apart (#544), and the verify gate requires both
  `PUSHOVER_*` keys (`verify_deploy.sh:100-101`).
- **Load beside Real Options**, measured on DEV on 11-19/20:
  - L1: about 15 s CPU over 5-6 min, about 360 MB;
  - L2: about 2.6 s CPU, 15 s, 112 MB;
  - post-L1: about 3 s CPU, 80 s, 200 MB.

  **UNVERIFIED:** PROD's headroom. Check `trading-bot` after the first two L1s.
- **A deploy rollback re-arms the timers on old code** (`deploy.sh:254-276`). Contained by running the verify gate by
  hand first.
- **The Sunday review (11-29) sees PROD armed.** Contained by the STANDING_STATE note.
- **Reach writes untracked `records/digests/` and `records/cards/` files on PROD.** Harmless; they are never
  committed from PROD.

## 13. Return to inert (Tue 12-01 after 16:35 ET, or at once on an abort)

On PROD, in `~/dramatic_options`:
1. On an abort only: `touch KILL`. Every unit halts at its next start. With no `pending` row, the KILL cancel has
   nothing to do.
2. Restore the `.env` exactly, then check the flags:
   ```bash
   cp -p ~/rehearsal/env.pre-rehearsal .env
   grep -E '^(PAPER|LIVE_TRADING_ENABLED|DRY_RUN|FORWARD_ENABLED)=' .env
   # expect PAPER=false LIVE_TRADING_ENABLED=false DRY_RUN=true FORWARD_ENABLED=false
   ```
3. Deploy, which disarms the timers (`apply_timers` with `FORWARD_ENABLED=false` runs `disable --now`,
   `deploy.sh:183-184`):
   ```bash
   ENV_NAME=PROD ./deploy.sh      # expect "FORWARD_ENABLED=false → timers installed-but-inert"
   systemctl list-timers 'dramatic-options-*' --no-legend           # must list 0 timers
   systemctl is-active dramatic-options-{l1,l2,post-l1}.service     # every line must say inactive
   ```
4. Archive the rehearsal DB into a dated directory, keeping the file names. This is #541's pattern: the three files
   move together, and an existing directory is refused, never merged.
   ```bash
   label=rehearsal
   mkdir -p data/archive && d="data/archive/$(date +%F)-$label" && mkdir "$d" && {
     sudo systemctl stop dramatic-options-web.service
     for f in data/dramatic_options.db data/dramatic_options.db-wal data/dramatic_options.db-shm; do
       if [ -e "$f" ]; then mv "$f" "$d/"; fi; done
     sudo systemctl start dramatic-options-web.service
     echo "ARCHIVED to $d"; } || echo "REFUSED: $d already exists or could not be created; nothing moved"
   python3 -c "import sqlite3, sys; c = sqlite3.connect(f'file:{sys.argv[1]}/dramatic_options.db?mode=ro', uri=True); \
   print(c.execute('PRAGMA integrity_check').fetchone()[0], c.execute('SELECT MAX(id) FROM runs').fetchone()[0])" "$d"
   ```
   Leave `data/` without a DB. #541's arming precheck expects the real book to start empty. The pre-rehearsal DB
   stays in `~/rehearsal/pre-rehearsal/`.
5. Remove `KILL` if it was set. Confirm again that 0 timers are listed.
6. CC updates STANDING_STATE (PROD inert, rehearsal done, the record's link) and writes the dated record.

## 14. The operator's answers (2026-11-24)

1. **Window:** start Tue 11-24. The run is 11-24 → 12-01 on a seed taken 11-23.
2. **Account:** DEV's paper account, shared. No second account.
3. **The live pair:** commented out of PROD's `.env` for the window.
4. **DRY_RUN=false window:** none.
5. **Merge hold:** yes, on trading-path merges, 11-24 → 12-01.
6. **`X_BEARER_TOKEN`:** shared.
7. **The nightly read:** CC, with one ssh go for the window. Given.
8. **#466, #463 and the expiring spread:** deferred to a separate account before T4.
9. **PROD's libc6 reboot:** yes, before arming.
10. **Pushover:** DEV's token and user key. Pages are told apart by #544's `[PROD]` tag.

## 15. Follow-ups that would need code (none is needed for the rehearsal)

- A committed comparison script (`scripts/ops/`) if the rehearsal is repeated. The §8 snippet is enough for one
  window.
- #444's possible follow-ups: read `OPEXP`/`OPXRC`/`OPASN` in the venue check, and a tool to hold a 1-lot vertical
  through expiry on paper (for the separate-account drills).

## UNVERIFIED (collected)

1. PROD's current `.env` beyond the 11-12 names and flags.
2. What PROD's current `data/dramatic_options.db` holds.
3. Whether systemd timer stamps exist on PROD (a catch-up at arming).
4. That a cold cache changes no gate or council input.
5. Alpaca's current per-key rate limit, and the per-tick request count (about 72 a box is an estimate).
6. The provider-console spend limits on the shared LLM keys, and the X API quota.
7. PROD's CPU and RAM headroom beside `trading-bot`, and Real Options' schedule.
8. Spread handling at expiry (#444), deferred with the drills.
