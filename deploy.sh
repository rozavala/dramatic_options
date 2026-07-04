#!/bin/bash
set -e
# =============================================================================
# dramatic_options — Deployment Script (T2.5 PR2: forward loop, oneshot+timer)
#
# Run model: the single-cycle orchestrator.py is fired by systemd TIMERS, not a
# long-lived service:
#   • dramatic-options-l0.{service,timer}  — weekly Sun 08:00 ET discovery scan (--discover, no trading)
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
TIMERS=("${SERVICE_PREFIX}-l0.timer" "${SERVICE_PREFIX}-l1.timer" "${SERVICE_PREFIX}-l2.timer")
SERVICES=("${SERVICE_PREFIX}-l0.service" "${SERVICE_PREFIX}-l1.service" "${SERVICE_PREFIX}-l2.service")
# The §5b observability dashboard — a LONG-RUNNING service (not a oneshot timer-fired one), armed separately
# (apply_dashboard) and fail-soft: its failure never rolls back trading. install_units globs *.service so the
# unit lands on both boxes automatically; only the arming differs by env.
DASHBOARD_SERVICE="${SERVICE_PREFIX}-dashboard.service"
WEB_SERVICE="${SERVICE_PREFIX}-web.service"        # the React/FastAPI dashboard (dashboard_web/); armed like DASHBOARD_SERVICE, fail-soft
ENV_FILE="$REPO_ROOT/.env"                         # the file systemd EnvironmentFile reads
HEALTH_URL="${HEALTH_URL:-}"                       # EMPTY: the trading loop has no HTTP endpoint. (The §5b
                                                   # dashboard IS an HTTP server on 8601, deliberately kept OUT
                                                   # of the verify gate — its failure is fail-soft.)

# Prevent overlapping deploys
DEPLOY_LOCK="/tmp/${SERVICE_PREFIX}-deploy.lock"
echo "$$" > "$DEPLOY_LOCK"
trap "rm -f '$DEPLOY_LOCK'" EXIT

# --- Timer-tick collision guard (2026-07-04) --------------------------------
# A deploy's stop_units SIGTERMs an in-flight oneshot: the 2026-07-02 19:59:59 deploy killed
# the 20:00 L2 mid-marks (benign for a mark-only unit, NOT guaranteed benign for L1). The
# L1/L2 ticks are :00/:30 13:00-20:30 UTC plus 19:45. If a deploy starts within 60s BEFORE a
# tick (the unit is about to start) or 90s AFTER one (a oneshot is likely mid-run), WAIT until
# the window clears (bounded; timers-inert hours skip instantly).
wait_clear_of_ticks() {
    local now h m s tick_s dist after
    for _ in $(seq 1 12); do  # bounded: at most ~9 min of waiting, then proceed regardless
        now=$(date -u +%H:%M:%S); h=${now:0:2}; m=${now:3:2}; s=${now:6:2}
        # active timer hours only (13:00-20:30 UTC incl. the 19:45 L1)
        if (( 10#$h < 12 || 10#$h > 20 )); then return 0; fi
        local secs=$(( 10#$h*3600 + 10#$m*60 + 10#$s ))
        local danger=0
        # L2 ticks (:00/:30): the monitor finishes in ~15-25s → +90s after-window.
        for tick_s in $(seq $((13*3600)) 1800 $((20*3600+1800))); do
            dist=$(( secs - tick_s ))
            if (( dist >= -60 && dist <= 90 )); then danger=1; break; fi
        done
        # The 19:45 L1 runs ~3-5 min (council round-trips) → +360s after-window: a deploy at
        # 19:47 would SIGTERM a council MID-FLIGHT — the worst case, not the benign one.
        if (( danger == 0 )); then
            dist=$(( secs - (19*3600 + 45*60) ))
            if (( dist >= -60 && dist <= 360 )); then danger=1; fi
        fi
        if (( danger == 0 )); then return 0; fi
        echo "deploy: within a timer-tick window (UTC $now) — waiting 45s to avoid SIGTERMing an in-flight cycle"
        sleep 45
    done
    return 0  # never block a deploy indefinitely
}
wait_clear_of_ticks

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

# Arm the LONG-RUNNING dashboard service. Distinct from apply_timers: armed where this env OBSERVES — DEV
# always (watch even a paused book), PROD once it goes live (forward_enabled=true at T4) — else installed but
# stopped (start when needed). FAIL-SOFT by design: a dashboard problem must NEVER fail or roll back the
# trading deploy, so this swallows errors and is never in the verify gate. Guards on the wrapper's PRESENCE
# (a rollback ACROSS the introducing commit has no wrapper → don't enable a unit whose ExecStart is gone).
apply_dashboard() {
    if [ ! -f scripts/dashboard_run.sh ]; then
        echo "  Dashboard: no scripts/dashboard_run.sh in this tree — leaving it stopped."
        sudo systemctl disable --now "$DASHBOARD_SERVICE" 2>/dev/null || true
        return 0
    fi
    chmod +x scripts/dashboard_run.sh 2>/dev/null || true   # repair an exec bit stripped on the box
    if [ "$(forward_enabled)" = "true" ] || [ "$ENV_NAME" = "DEV" ]; then
        echo "  Dashboard: enabling + starting ($DASHBOARD_SERVICE)."
        sudo systemctl enable --now "$DASHBOARD_SERVICE" \
            || echo "  WARNING: dashboard enable --now failed (fail-soft — trading is unaffected)"
    else
        echo "  Dashboard: installed but stopped on $ENV_NAME (start when needed: systemctl start $DASHBOARD_SERVICE)."
        sudo systemctl disable --now "$DASHBOARD_SERVICE" 2>/dev/null || true
    fi
}

# Arm the LONG-RUNNING web dashboard (dashboard_web/: FastAPI + React SPA on :8602). Mirrors apply_dashboard
# — armed where this env OBSERVES (DEV always / forward_enabled at T4), else installed-but-stopped — equally
# FAIL-SOFT and OUTSIDE the verify gate. Builds the SPA here (fail-soft): a build failure leaves the prior
# dist or serves API-only (server.py mounts dist only if present), never blocking trading. Every command is
# guarded so `set -e` can't trip on it. Guards on the wrapper's PRESENCE (a rollback across the introducing
# commit has no wrapper → don't enable a unit whose ExecStart is gone).
apply_web_dashboard() {
    if [ ! -f scripts/dashboard_web_run.sh ]; then
        echo "  Web dashboard: no scripts/dashboard_web_run.sh in this tree — leaving it stopped."
        sudo systemctl disable --now "$WEB_SERVICE" 2>/dev/null || true
        return 0
    fi
    chmod +x scripts/dashboard_web_run.sh 2>/dev/null || true   # repair an exec bit stripped on the box
    if [ -d dashboard_web/ui ] && command -v npm >/dev/null 2>&1; then
        echo "  Web dashboard: building the SPA (npm ci && build)..."
        ( cd dashboard_web/ui && npm ci --no-audit --no-fund && npm run build ) \
            || echo "  WARNING: web SPA build failed (fail-soft — API serves without the SPA; trading unaffected)"
    else
        echo "  Web dashboard: npm or dashboard_web/ui missing — skipping build (API-only if started)."
    fi
    if [ "$(forward_enabled)" = "true" ] || [ "$ENV_NAME" = "DEV" ]; then
        echo "  Web dashboard: enabling + starting ($WEB_SERVICE)."
        sudo systemctl enable --now "$WEB_SERVICE" \
            || echo "  WARNING: web dashboard enable --now failed (fail-soft — trading is unaffected)"
    else
        echo "  Web dashboard: installed but stopped on $ENV_NAME (start when needed: systemctl start $WEB_SERVICE)."
        sudo systemctl disable --now "$WEB_SERVICE" 2>/dev/null || true
    fi
}

# Stop scheduling AND any in-flight oneshot so a `git reset` never lands under a live cycle (R4).
stop_units() {
    sudo systemctl stop "${TIMERS[@]}" "${SERVICES[@]}" "$DASHBOARD_SERVICE" "$WEB_SERVICE" 2>/dev/null || true
    # Belt-and-suspenders: reap a hand-started dashboard (the pre-service manual instance / an orphan).
    # PORT-qualified — real_options' dashboard is ALSO `streamlit run dashboard.py` on this host (port 8501),
    # so match ONLY our port (8601) to never SIGTERM theirs.
    pkill -f "streamlit.*server.port 8601" 2>/dev/null || true
    pkill -f "uvicorn.*dashboard_web/api" 2>/dev/null || true   # the web dashboard (its own service / a manual run; pattern-qualified, distinct from real_options' uvicorn dashboard_api.app)
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
        apply_dashboard    # re-arm the dashboard per the rolled-back tree (fail-soft, guarded)
        apply_web_dashboard # re-arm the web dashboard per the rolled-back tree (fail-soft, guarded)
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
# The §5b dashboard's deps (streamlit) — kept OUT of requirements.txt so the trading runtime stays lean;
# installed here so the live venv can run dramatic-options-dashboard.service. (CI's test-dashboard job
# installs the same combined set, so a dep conflict fails CI rather than only the box.)
[ -f requirements-dashboard.txt ] && pip install -r requirements-dashboard.txt

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
apply_dashboard       # fail-soft, never rolls back trading
apply_web_dashboard   # fail-soft, never rolls back trading (builds the SPA + arms the web service)

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
