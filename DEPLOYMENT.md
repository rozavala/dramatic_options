# Deployment

Adapted from the `real_options` deployment method. **Currently inert** — the
files are in place but nothing auto-deploys until the GitHub Actions secrets are
set and an app entry point exists.

## Flow

```
push to main        → GitHub Actions (deploy.yml) → SSH into DEV host  → ./deploy.sh   (ENV_NAME=DEV)
push to production  → GitHub Actions (deploy.yml) → SSH into PROD host → ./deploy.sh   (ENV_NAME=PROD)
```

`deploy.sh` runs: stop service → rotate logs → venv + deps → scaffolding →
migrations → **verify gate** (`scripts/verify_deploy.sh`; rolls back on failure)
→ start service → final check → **sync the `dramatic_options-claude` worktree**
(`scripts/sync_worktree.sh`).

## Files

| File | Role |
|---|---|
| `.github/workflows/deploy.yml` | CI/CD trigger: `main`→DEV, `production`→PROD |
| `deploy.sh` | Deployment lifecycle with automatic rollback |
| `scripts/verify_deploy.sh` | Post-deploy health gate (disk, imports, HTTP `HEALTH_URL`, critical files) |
| `scripts/sync_worktree.sh` | Keeps the `claude` worktree in sync with `main` |
| `scripts/dramatic-options.service` | systemd unit (set `ExecStart` once the app exists) |
| `.env.example` | Per-host config template (copy to `.env`) |

## To go live (later)

1. Set the app entry point in `scripts/dramatic-options.service` (`ExecStart`) and
   in `scripts/verify_deploy.sh` (critical files / `import`).
2. Install the unit on the target host:
   `sudo cp scripts/dramatic-options.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable dramatic-options`
3. Set repo secrets (Settings → Secrets and variables → Actions):
   `SSH_PRIVATE_KEY`, `DROPLET_HOST_DEV`, `DROPLET_USER_DEV`,
   `DROPLET_HOST_PROD`, `DROPLET_USER_PROD`.
   Add the matching **public** key to the target host's `~/.ssh/authorized_keys`.
4. Push to `main` to deploy to DEV; push to `production` to deploy to PROD.

> Manual deploy on a host (no CI needed): `cd ~/dramatic_options && ENV_NAME=DEV ./deploy.sh`
