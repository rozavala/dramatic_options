# Deployment

Adapted from the `real_options` deployment method. The forward loop runs as systemd
**timers driving a `Type=oneshot` `orchestrator.py`** — not a long-lived service.

## Flow

```
push to main        → GitHub Actions (deploy.yml) → SSH into DEV host  → ./deploy.sh   (ENV_NAME=DEV)
push to production  → GitHub Actions (deploy.yml) → SSH into PROD host → ./deploy.sh   (ENV_NAME=PROD)
```

`deploy.sh` runs: stop timers/in-flight cycle → rotate logs → venv + deps → migrations →
**verify gate** (`scripts/verify_deploy.sh`; rolls back on failure) → **render + install the
systemd units** → **arm the timers** (only where `FORWARD_ENABLED=true`) → **verify the timers
are active** → sync the `dramatic_options-claude` worktree. On any failure it rolls back the
code **and re-syncs the unit files** (not just `git reset`).

## The run model (oneshot + timer)

| Unit | Fires | Does |
|---|---|---|
| `dramatic-options-l0.{service,timer}` | `Sun 08:00 ET`, `Persistent=true` | one **discovery** scan: `--discover` — surfaces sentinels for the next L1 council; **never trades / no broker** |
| `dramatic-options-l1.{service,timer}` | `Mon..Fri 15:45 ET`, `Persistent=true` | one **full** cycle: monitor → council → gates → entries |
| `dramatic-options-l2.{service,timer}` | `Mon..Fri 09..16:00/30 ET`, `Persistent=false` | `--monitor` only: mark-to-market + deterministic exits (**no council → no LLM spend**) |
| `dramatic-options-notify@.service` | `OnFailure=` of L0/L1/L2 | Pushover page for a unit that exited **non-zero** |

The units under `scripts/systemd/` are **templates** (`__REPO_ROOT__`/`__USER__`/`__GROUP__`)
rendered by `deploy.sh` at install time, so the same tracked files are correct on DEV
(`rodrigo`) and PROD (`console`). They are installed on **both** envs; the **timers are enabled
only where `FORWARD_ENABLED=true`**. The `.service` oneshots are **never** `systemctl start`ed
by the deploy (that would run a full live cycle synchronously) — only the timers are armed.

**Why `L1=15:45` (pre-close) and why catch-up is safe.** L1 fires *before* the 16:00 options
close so entries and the monitor's `SELL_TO_CLOSE` transact at **live** prices and reconcile the
same session (not into a closed after-hours book). `Persistent=true` lets a run missed because
the box was down fire on next boot; that catch-up is safe because (a) acting on slightly-stale
marks is immaterial to a 6–12-month hold, and (b) the orchestrator computes `is_market_open()`
once per cycle **fail-closed** and, when the market is closed, **skips entries and runs the
monitor mark-only** (no real submit) — so a post-close catch-up can never submit into a closed
market. The orchestrator also **re-checks market-open immediately before submitting entries**
(after the possibly-slow council), so "no entry outside RTH" is literally enforced, not merely
bounded by `TimeoutStartSec`. 15:45 is also kept **off** the L2 `:00/:30` grid so the two timers
never start the same monitor pass concurrently.

**L0 (weekly sentinel discovery — T3 PR3).** `Sun 08:00 ET` is off-market and off the L1/L2 grids:
discovery reads as-of (Friday-close) data and **submits nothing**, surfacing candidates the Monday
L1 council judges (the hard seam — discovery proposes, council judges, gates dispose). Its
`TimeoutStartSec=900` is **derived from the §C cold-cache measurement**, not guessed: a healthy
cold scan measured ≈11s ($0.0019 over 8 gemini-3.1-flash-lite framer calls); the ≤`scan_top_k`
sequential framer calls bound the worst case ≈1460s; 900s clears a realistic-slow-but-healthy run
(~540s) yet SIGTERMs+pages a broadly-degraded-provider scan ("fail loud", cf. L2). **L0 is held
UNARMED until §A** — the live L1/L2 daily loop re-verified clean on paper post-T3 deploy. Because
`deploy.sh` arms every timer where `FORWARD_ENABLED=true`, **merging the L0 PR is itself the
go-live act**: it arms the weekly scan, and the surfaced sentinels then trigger the first real
*council* LLM spend on the live book at the next L1.

**Hang detection.** Each oneshot has `TimeoutStartSec=` (L0 900s / L1 1800s / L2 180s) — a stalled
LLM/broker call is killed → non-zero exit → `OnFailure` → page. The three **soft, exit-0**
conditions `OnFailure` cannot catch (kill-rule trip, fail-closed council, cost-cap trip) page
**in-app** from the orchestrator via `notify.py`.

## The four operational flags (orthogonal)

Real money requires the **live triple-gate**; `FORWARD_ENABLED` is a **separate** "does this env
trade on the loop at all" switch.

| Flag | DEV (paper) | PROD (real-money) | Meaning |
|---|---|---|---|
| `PAPER` | `true` | `true` | paper endpoint |
| `LIVE_TRADING_ENABLED` | `false` | `false` | half of the live gate |
| `--live` (CLI) | not passed | not passed | the other half — `live_allowed` needs all three |
| `FORWARD_ENABLED` | **`true`** | **`false`** | this env runs the scheduled loop |

PROD is inert by several independent margins until T4: `FORWARD_ENABLED=false` (timers stay
disabled), **no real-money broker path in code** (`AlpacaPaperBroker` hardcodes `paper=True`),
`DRY_RUN` not set false, and the live triple-gate unsatisfied. DEV runs `DRY_RUN=false`
(real two-sided paper submit) for an honest forward record toward T4.

## Observability dashboard (read-only)

A long-running **systemd service** (`dramatic-options-dashboard.service`, `Type=simple`) — distinct from the
oneshot L0/L1/L2 trading units. `deploy.sh apply_dashboard` **enables + starts** it where `forward_enabled ||
ENV_NAME=DEV` (DEV always — observe even a paused book; PROD auto-arms at T4 go-live), else installs-but-stops
it (start when needed: `sudo systemctl start dramatic-options-dashboard`).

- **Bind:** `scripts/dashboard_run.sh` resolves the per-box **Tailscale IP** at start (polls ~60s; **fail-closed**
  — never a wildcard/public bind) and runs `streamlit run dashboard.py --server.port 8502` (port 8502 so it never
  collides with real_options' dashboard on 8501). Reach it at `all-options-<env>.tail57521e.ts.net:8502`.
- **Keyless:** the unit omits `EnvironmentFile` **and** sets `DRAMATIC_SKIP_DOTENV=1`, so
  `config_loader.load_config` loads `config.json` tunables but **never reads `.env`** — the read-only process
  holds no broker/LLM/Pushover keys. Confirm on the box:
  `tr '\0' '\n' </proc/$(pgrep -f 'server.port 8502')/environ | grep -cE 'ALPACA|GEMINI|XAI|ANTHROPIC|PUSHOVER'` ⇒ 0.
- **Fail-soft:** arming swallows errors and is **outside** the verify/rollback gate — a dashboard problem never
  fails or rolls back the trading deploy. `streamlit` installs from `requirements-dashboard.txt` (deploy STEP 3),
  kept out of `requirements.txt`; a CI `test-dashboard` job installs the combined venv so a dep conflict fails CI.
- Stricter exposure (if the tailnet trust set changes): keep a localhost bind + SSH tunnel, or a Tailscale ACL on 8502.

## Files

| File | Role |
|---|---|
| `.github/workflows/deploy.yml` | CI/CD trigger: `main`→DEV, `production`→PROD (runs `./deploy.sh`) |
| `deploy.sh` | lifecycle: verify-gated install + timer arming, with rollback that re-syncs units |
| `scripts/verify_deploy.sh` | health gate (disk, imports, critical files, **live-checkout `.env`**) |
| `scripts/systemd/*.{service,timer}` | unit templates (L0, L1, L2, notify@, dashboard) rendered at install |
| `scripts/dashboard_run.sh` | dashboard launch wrapper — resolves the tailnet IP (fail-closed), binds 8502 |
| `requirements-dashboard.txt` | dashboard-only deps (streamlit); installed by deploy STEP 3, not in CI's base job |
| `notify.py` | Pushover sender (in-app + `--systemd-failure` for `OnFailure`) |
| `scripts/sync_worktree.sh` | keeps the `…-claude` worktree in sync |
| `.env.example` | per-host config template (copy to `.env`) |

## Preconditions

1. **The live-checkout `.env`** (`~/dramatic_options/.env` — the file the units read, *not* the
   worktree's) must exist with the keys below on any env where `FORWARD_ENABLED=true`. The
   verify gate **fails the deploy and rolls back** if a key is missing/placeholder on a trading
   env (a missing-`.env` failure cannot self-page — the `notify@` unit reads the same file).
   ```
   ALPACA_API_KEY= ALPACA_SECRET_KEY=   ALPACA_PAPER=true
   PAPER=true  LIVE_TRADING_ENABLED=false  DRY_RUN=false  FORWARD_ENABLED=true
   GEMINI_API_KEY=  XAI_API_KEY=  ANTHROPIC_API_KEY=
   PUSHOVER_API_TOKEN=  PUSHOVER_USER_KEY=
   ```
2. **CI deploy secrets** (Settings → Secrets and variables → Actions): `SSH_PRIVATE_KEY`,
   `DROPLET_HOST_DEV`/`DROPLET_USER_DEV`, `DROPLET_HOST_PROD`/`DROPLET_USER_PROD`,
   `SSH_KNOWN_HOSTS` (host-bound, pins server identity). Pushing to `main` deploys to DEV;
   pushing to `production` deploys to PROD.
3. **sudoers** must let the deploy user run `systemctl` (install/daemon-reload/enable/disable)
   for the `dramatic-options-*` units.

> Manual deploy on a host (no CI): `cd ~/dramatic_options && ENV_NAME=DEV ./deploy.sh`
> Inspect timers: `systemctl list-timers 'dramatic-options-*'` · logs: `journalctl -u dramatic-options-l1.service`
