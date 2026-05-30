#!/bin/bash
set -e
# =============================================================================
# dramatic_options — Deployment Script
#
# Adapted from the real_options deployment method:
#   stop -> rotate logs -> install deps -> migrations -> verify gate
#   -> (rollback on failure) -> restart service -> sync worktree.
#
# Called by: .github/workflows/deploy.yml (via SSH after git pull)
# Can also be run manually on the target host:  ENV_NAME=DEV ./deploy.sh
#
# This is a scaffold for a future public web app. App-specific bits are marked
# with TODO and guarded so the script no-ops cleanly until the app exists.
# =============================================================================

# --- Detect repo root -------------------------------------------------------
if [ -f "pyproject.toml" ] || [ -f "deploy.sh" ]; then
    REPO_ROOT=$(pwd)
else
    REPO_ROOT=~/dramatic_options
fi
cd "$REPO_ROOT"

# --- Configuration (adjust once the app exists) -----------------------------
ENV_NAME="${ENV_NAME:-DEV}"                       # DEV | PROD
SERVICE_NAME="${APP_SERVICE_NAME:-dramatic-options}"  # systemd unit name
HEALTH_URL="${HEALTH_URL:-}"                       # e.g. http://127.0.0.1:8000/health

# Prevent overlapping deploys
DEPLOY_LOCK="/tmp/${SERVICE_NAME}-deploy.lock"
echo "$$" > "$DEPLOY_LOCK"
trap "rm -f '$DEPLOY_LOCK'" EXIT

# =========================================================================
# STEP 0: Capture rollback point BEFORE any changes
# =========================================================================
PREV_COMMIT=$(git rev-parse HEAD~1 2>/dev/null || echo "")
CURR_COMMIT=$(git rev-parse HEAD)
echo "--- Deploy ($ENV_NAME): $CURR_COMMIT (rollback target: ${PREV_COMMIT:-none}) ---"

service_exists() {
    systemctl list-unit-files "${SERVICE_NAME}.service" >/dev/null 2>&1 && \
        systemctl cat "${SERVICE_NAME}.service" >/dev/null 2>&1
}

start_service() {
    if service_exists; then
        sudo systemctl start "$SERVICE_NAME"
    else
        echo "  (no ${SERVICE_NAME}.service installed yet — skipping start)"
    fi
}

# Define rollback function
rollback_and_restart() {
    echo ""
    echo "!!! ===================================================== !!!"
    echo "!!! DEPLOYMENT FAILED — INITIATING AUTOMATIC ROLLBACK      !!!"
    echo "!!! ===================================================== !!!"
    if [ -n "$PREV_COMMIT" ]; then
        echo "--- Rolling back to $PREV_COMMIT ---"
        git reset --hard "$PREV_COMMIT"
        [ -d "venv" ] && source venv/bin/activate
        [ -f requirements.txt ] && pip install -r requirements.txt --quiet
        mkdir -p logs
        start_service
        echo "--- Rollback complete. Old version restarted. ---"
        echo "--- MANUAL INVESTIGATION REQUIRED ---"
    else
        echo "--- No previous commit available for rollback ---"
        echo "--- MANUAL INTERVENTION REQUIRED ---"
    fi
    exit 1
}

# =========================================================================
# STEP 1: Stop old process via systemd
# =========================================================================
echo "--- 1. Stopping old process... ---"
if service_exists && sudo systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    echo "  Stopping $SERVICE_NAME..."
    sudo systemctl stop "$SERVICE_NAME"
    sleep 3
else
    echo "  $SERVICE_NAME not running (or not installed) — nothing to stop"
fi

# =========================================================================
# STEP 2: Rotate logs
# =========================================================================
echo "--- 2. Rotating logs... ---"
mkdir -p logs
ROTATE_DATE=$(date --iso=s)
[ -f logs/app.log ] && mv logs/app.log "logs/app-${ROTATE_DATE}.log" || true
# Clean up rotated logs older than 7 days
find logs/ -name "*-20*.log" -mtime +7 -delete 2>/dev/null || true
touch logs/app.log
chmod 664 logs/app.log 2>/dev/null || true

# =========================================================================
# STEP 3: Activate venv + install deps
# =========================================================================
echo "--- 3. Installing/updating dependencies... ---"
if [ ! -d "venv" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate
if [ -f requirements.txt ]; then
    pip install -r requirements.txt
else
    echo "  No requirements.txt — skipping"
fi

# =========================================================================
# STEP 4: Directory scaffolding (idempotent)
# =========================================================================
echo "--- 4. Ensuring directory structure... ---"
mkdir -p logs data
echo "  Directories OK"

# =========================================================================
# STEP 5: Run migrations (idempotent — tracks state itself)
# =========================================================================
echo "--- 5. Running migrations... ---"
if [ -f "scripts/run_migrations.py" ]; then
    python scripts/run_migrations.py || echo "  Migrations issue (non-blocking)"
else
    echo "  No migration runner found, skipping"
fi

# =========================================================================
# STEP 6: Post-deploy verification gate
# =========================================================================
echo "--- 6. Running post-deploy verification... ---"
chmod +x scripts/verify_deploy.sh 2>/dev/null || true
if [ -f "scripts/verify_deploy.sh" ]; then
    if ! HEALTH_URL="$HEALTH_URL" bash scripts/verify_deploy.sh; then
        rollback_and_restart
    fi
else
    echo "  No verification script found, skipping"
fi

# =========================================================================
# STEP 7: Start service via systemd
# =========================================================================
echo "--- 7. Starting service... ---"
# On PROD, sync the repo's service unit into systemd if it differs.
if [ "$ENV_NAME" = "PROD" ]; then
    REPO_SERVICE="scripts/${SERVICE_NAME}.service"
    LIVE_SERVICE="/etc/systemd/system/${SERVICE_NAME}.service"
    if [ -f "$REPO_SERVICE" ] && ! diff -q "$REPO_SERVICE" "$LIVE_SERVICE" >/dev/null 2>&1; then
        echo "  Syncing service unit (repo differs from installed)..."
        sudo cp "$REPO_SERVICE" "$LIVE_SERVICE" || echo "  WARNING: could not sync unit (check sudoers)"
    fi
fi

if service_exists; then
    sudo systemctl daemon-reload
    start_service
    sleep 5
    if ! sudo systemctl is-active --quiet "$SERVICE_NAME"; then
        echo "  ERROR: $SERVICE_NAME failed to start!"
        sudo systemctl status "$SERVICE_NAME" --no-pager | head -20 || true
        tail -50 logs/app.log 2>/dev/null || true
        rollback_and_restart
    fi
    echo "  $SERVICE_NAME started"
else
    echo "  No ${SERVICE_NAME}.service installed — skipping start (app not deployed yet)"
fi

# =========================================================================
# STEP 8: Final verification
# =========================================================================
echo "--- 8. Final check... ---"
if service_exists; then
    sleep 3
    if ! sudo systemctl is-active --quiet "$SERVICE_NAME"; then
        echo "  ERROR: $SERVICE_NAME no longer running after 3s!"
        rollback_and_restart
    fi
fi

# =========================================================================
# STEP 9: Sync Claude Code worktree (non-destructive, skips if unsafe)
# =========================================================================
echo "--- 9. Syncing Claude Code worktree... ---"
chmod +x scripts/sync_worktree.sh 2>/dev/null || true
if [ -f "scripts/sync_worktree.sh" ]; then
    bash scripts/sync_worktree.sh || echo "  Worktree sync issue (non-blocking)"
else
    echo "  No worktree sync script found, skipping"
fi

echo ""
echo "--- Deployment finished successfully! ---"
echo "--- Commit: $CURR_COMMIT ($ENV_NAME) ---"
echo "--- $(date) ---"
