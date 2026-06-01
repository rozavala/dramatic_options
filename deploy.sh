#!/bin/bash
set -e
# =============================================================================
# dramatic_options — Deployment Script (T2.5 PR2: forward loop, oneshot+timer)
#
# Run model: the single-cycle orchestrator.py is fired by systemd TIMERS, not a
# long-lived service:
#   • dramatic-options-l1.{service,timer}  — daily 15:45 ET full cycle (council + entries + monitor)
#   • dramatic-options-l2.{service,timer}  — ~30min intraday monitor (--monitor, no council/LLM)
#   • dramatic-options-notify@.service     — OnFailure Pushover pager (instanced per failed unit)
#
# This script: stop timers/in-flight cycle -> rotate logs -> deps -> migrations
#   -> verify gate (rolls back on failure) -> install+render units -> arm timers
#   -> verify timers active -> sync worktree.
#
# Units are INSTALLED on BOTH envs but the timers are ENABLED only where
# FORWARD_ENABLED=true (DEV=paper trades; PROD=real-money stays installed-but-inert
# until T4). The oneshot .service units are NEVER `systemctl start`ed by this script
# (that would run a full live cycle synchronously) — only the timers are armed.
#
# Called by: .github/workflows/deploy.yml (SSH after git pull). Manual:
#   cd ~/dramatic_options && ENV_NAME=DEV ./deploy.sh
# =============================================================================

# --- Detect repo root -------------------------------------------------------
if [ -f "pyproject.toml" ] || [ -f "deploy.sh" ]; then
    REPO_ROOT=$(pwd)
else
    REPO_ROOT=~/dramatic_options
fi
cd "$REPO_ROOT"

# --- Configuration ----------------------------------------------------------
ENV_NAME="${ENV_NAME:-DEV}"                       # DEV | PROD
SERVICE_PREFIX="dramatic-options"
SYSTEMD_SRC="scripts/systemd"                      # unit templates (rendered at install time)
SYSTEMD_DST="/etc/systemd/system"
TIMERS=("${SERVICE_PREFIX}-l1.timer" "${SERVICE_PREFIX}-l2.timer")
SERVICES=("${SERVICE_PREFIX}-l1.service" "${SERVICE_PREFIX}-l2.service")
ENV_FILE="$REPO_ROOT/.env"                         # the file systemd EnvironmentFile reads
HEALTH_URL="${HEALTH_URL:-}"                       # intentionally EMPTY — no HTTP server in this app

# Prevent overlapping deploys
DEPLOY_LOCK="/tmp/${SERVICE_PREFIX}-deploy.lock"
echo "$$" > "$DEPLOY_LOCK"
trap "rm -f '$DEPLOY_LOCK'" EXIT

# =========================================================================
# STEP 0: Capture rollback point BEFORE any changes
# =========================================================================
PREV_COMMIT=$(git rev-parse HEAD~1 2>/dev/null || echo "")
CURR_COMMIT=$(git rev-parse HEAD)
echo "--- Deploy ($ENV_NAME): $CURR_COMMIT (rollback target: ${PREV_COMMIT:-none}) ---"

# --- Helpers ----------------------------------------------------------------

# Read FORWARD_ENABLED from the LIVE-CHECKOUT .env. We GREP a single key — we never `source`
# the file (it must never execute arbitrary content). Absent/unset/anything-not-truthy => false.
forward_enabled() {
    [ -f "$ENV_FILE" ] || { echo "false"; return; }
    local v
    v=$(grep -E '^[[:space:]]*FORWARD_ENABLED[[:space:]]*=' "$ENV_FILE" 2>/dev/null \
        | tail -1 | cut -d= -f2- | tr -d "\"' \t\r")
    case "$(printf '%s' "$v" | tr '[:upper:]' '[:lower:]')" in
        1|true|yes|on) echo "true" ;;
        *)             echo "false" ;;
    esac
}

# Render a unit template to stdout, substituting the install-time placeholders so the same
# tracked file is correct on DEV (rodrigo) and PROD (console) without hardcoded paths.
render_unit() {
    sed -e "s|__REPO_ROOT__|${REPO_ROOT}|g" \
        -e "s|__USER__|$(id -un)|g" \
        -e "s|__GROUP__|$(id -gn)|g" \
        "$1"
}

# Render every template in $SYSTEMD_SRC and install into $SYSTEMD_DST when it differs.
# Sets UNITS_CHANGED=1 and reloads systemd if anything changed.
UNITS_CHANGED=0
install_units() {
    UNITS_CHANGED=0
    if [ ! -d "$SYSTEMD_SRC" ]; then
        echo "  (no $SYSTEMD_SRC in this tree — nothing to install)"
        return 0
    fi
    local src name tmp
    for src in "$SYSTEMD_SRC"/*.service "$SYSTEMD_SRC"/*.timer; do
        [ -f "$src" ] || continue
        name=$(basename "$src")
        tmp=$(mktemp)
        render_unit "$src" > "$tmp"
        if ! diff -q "$tmp" "$SYSTEMD_DST/$name" >/dev/null 2>&1; then
            echo "  Installing unit: $name"
            if sudo cp "$tmp" "$SYSTEMD_DST/$name"; then
                UNITS_CHANGED=1
            else
                echo "  WARNING: could not install $name (check sudoers)"
            fi
        fi
        rm -f "$tmp"
    done
    if [ "$UNITS_CHANGED" -eq 1 ]; then
        sudo systemctl daemon-reload || echo "  WARNING: daemon-reload failed"
    fi
}

# Arm timers where this env trades; otherwise guarantee they are inert. NEVER starts the
# oneshot .service units (that would run a full live cycle now).
apply_timers() {
    if [ "$(forward_enabled)" = "true" ]; then
        echo "  FORWARD_ENABLED=true → enabling timers (this env trades)."
        sudo systemctl enable --now "${TIMERS[@]}" || echo "  WARNING: enable --now failed (verified in STEP 8)"
    else
        echo "  FORWARD_ENABLED=false → timers installed-but-inert (no trading on this env)."
        sudo systemctl disable --now "${TIMERS[@]}" 2>/dev/null || true
    fi
}

# Stop scheduling AND any in-flight oneshot so a `git reset` never lands under a live cycle (R4).
stop_units() {
    sudo systemctl stop "${TIMERS[@]}" "${SERVICES[@]}" 2>/dev/null || true
}

# Verify the TIMERS are active where the env trades. We assert the timers (a oneshot .service is
# `inactive` between runs — asserting its is-active would falsely fail). No-op on an inert env.
verify_timers() {
    [ "$(forward_enabled)" = "true" ] || { echo "  (FORWARD_ENABLED=false — timers intentionally inert)"; return 0; }
    local t
    for t in "${TIMERS[@]}"; do
        if ! sudo systemctl is-active --quiet "$t"; then
            echo "  ERROR: timer $t is NOT active after enable!"
            return 1
        fi
    done
    echo "  Timers active: ${TIMERS[*]}"
    return 0
}

# Rollback: reset code AND re-sync the unit files (R4) — /etc must match the running commit and
# the timers must be re-armed per the (rolled-back) .env, not just `git reset`.
# NOTE: rolling back ACROSS the commit that first introduced the units (i.e. the very first PR2
# deploy) finds no templates in the prior tree, so it can only stop/disable the timers — verify
# by hand (this is exactly the path the pre-merge DEV rehearsal exercises).
rollback_and_restart() {
    echo ""
    echo "!!! ===================================================== !!!"
    echo "!!! DEPLOYMENT FAILED — INITIATING AUTOMATIC ROLLBACK      !!!"
    echo "!!! ===================================================== !!!"
    if [ -n "$PREV_COMMIT" ]; then
        echo "--- Rolling back to $PREV_COMMIT ---"
        stop_units
        git reset --hard "$PREV_COMMIT"
        [ -d "venv" ] && source venv/bin/activate
        [ -f requirements.txt ] && pip install -r requirements.txt --quiet
        mkdir -p logs
        install_units      # re-render the rolled-back tree's units (R4)
        apply_timers       # re-arm per the rolled-back .env
        echo "--- Rollback complete. Units re-synced to $PREV_COMMIT. ---"
        echo "--- MANUAL INVESTIGATION REQUIRED ---"
    else
        echo "--- No previous commit available for rollback ---"
        echo "--- MANUAL INTERVENTION REQUIRED ---"
    fi
    exit 1
}

# =========================================================================
# STEP 1: Stop timers + any in-flight cycle (before touching the checkout)
# =========================================================================
echo "--- 1. Stopping timers / in-flight cycle... ---"
stop_units

# =========================================================================
# STEP 2: Rotate logs (deploy's own log; the units themselves log to journald)
# =========================================================================
echo "--- 2. Rotating logs... ---"
mkdir -p logs
ROTATE_DATE=$(date --iso=s)
[ -f logs/app.log ] && mv logs/app.log "logs/app-${ROTATE_DATE}.log" || true
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
# STEP 6: Post-deploy verification gate (rolls back on failure)
# =========================================================================
echo "--- 6. Running post-deploy verification... ---"
chmod +x scripts/verify_deploy.sh 2>/dev/null || true
if [ -f "scripts/verify_deploy.sh" ]; then
    if ! ENV_NAME="$ENV_NAME" HEALTH_URL="$HEALTH_URL" bash scripts/verify_deploy.sh; then
        rollback_and_restart
    fi
else
    echo "  No verification script found, skipping"
fi

# =========================================================================
# STEP 7: Install systemd units + arm timers
# =========================================================================
echo "--- 7. Installing systemd units + arming timers... ---"
install_units
apply_timers

# =========================================================================
# STEP 8: Verify the timers are active (where this env trades)
# =========================================================================
echo "--- 8. Verifying timers... ---"
if ! verify_timers; then
    sudo systemctl list-timers "${SERVICE_PREFIX}-*" --no-pager 2>/dev/null || true
    rollback_and_restart
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
echo "--- Commit: $CURR_COMMIT ($ENV_NAME, FORWARD_ENABLED=$(forward_enabled)) ---"
echo "--- $(date) ---"
