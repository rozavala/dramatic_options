#!/bin/bash
set -e
# === dramatic_options — Log Collection (adapted from real_options) ===
# Collects log/data/state snapshots and pushes them to the orphan `logs` branch.
#
# CRITICAL: uses a git worktree (in /tmp) instead of switching branches, so the
# live checkout's working directory is NEVER modified — the running app and any
# dashboard keep their files during collection.
#
# Both DEV and PROD push to the SAME `logs` branch, each into its own subdir:
#   dev/   (LOG_ENV_NAME=dev)   prod/  (LOG_ENV_NAME=prod)
#
# Driven by cron on each box. Schedule-independent; safe to run any time.
# This is generic scaffolding — once the app produces logs/ and data/, those
# are picked up automatically. Until then it captures system snapshots.

# Load .env if present (optional path/branch overrides)
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs) || true
fi

ENV_NAME="${LOG_ENV_NAME:-dev}"
REPO_DIR="${DRAMATIC_OPTIONS_PATH:-$(pwd)}"
BRANCH="${LOG_BRANCH:-logs}"
SERVICE_NAME="${APP_SERVICE_NAME:-dramatic-options}"
WORKTREE_DIR="/tmp/dramatic-options-logs-worktree"
DEPLOY_LOCK="/tmp/${SERVICE_NAME}-deploy.lock"
COLLECT_LOCK="/tmp/${SERVICE_NAME}-collect.lock"

echo "dramatic_options Log Collection"
echo "Environment: $ENV_NAME"
echo "Repository:  $REPO_DIR"
echo "Branch:      $BRANCH"
echo "=========================="

# === CLEANUP TRAP: always remove worktree + lock on exit ===
cleanup() {
    local exit_code=$?
    if [ -d "$WORKTREE_DIR" ]; then
        echo "Cleanup: removing worktree..."
        cd "$REPO_DIR" 2>/dev/null || true
        git worktree remove --force "$WORKTREE_DIR" 2>/dev/null || rm -rf "$WORKTREE_DIR"
    fi
    rm -f "$COLLECT_LOCK"
    exit $exit_code
}
trap cleanup EXIT

# === Skip if a deploy is in progress (don't fight deploy.sh) ===
if [ -f "$DEPLOY_LOCK" ]; then
    LOCK_AGE=$(( $(date +%s) - $(stat -c %Y "$DEPLOY_LOCK") ))
    LOCK_PID=$(cat "$DEPLOY_LOCK" 2>/dev/null)
    if [ "$LOCK_AGE" -gt 1800 ]; then
        echo "Deploy lock >30min old, treating as stale"
        rm -f "$DEPLOY_LOCK"
    elif kill -0 "$LOCK_PID" 2>/dev/null; then
        echo "Deploy in progress (PID $LOCK_PID, age ${LOCK_AGE}s), skipping"
        exit 0
    else
        echo "Stale deploy lock (process gone), removing"
        rm -f "$DEPLOY_LOCK"
    fi
fi

# Our own lock so deploy.sh waits for us
echo "$$" > "$COLLECT_LOCK"

cd "$REPO_DIR" || exit 1

# Keep git memory modest on small droplets
git config pack.windowMemory 512m
git config pack.threads 1

# === SET UP WORKTREE FOR THE logs BRANCH ===
if [ -d "$WORKTREE_DIR" ]; then
    echo "Removing stale worktree from previous run..."
    git worktree remove --force "$WORKTREE_DIR" 2>/dev/null || rm -rf "$WORKTREE_DIR"
fi

git fetch origin "$BRANCH" 2>/dev/null || true

if git rev-parse --verify "origin/$BRANCH" >/dev/null 2>&1; then
    git branch -f "$BRANCH" "origin/$BRANCH" 2>/dev/null || true
    git worktree add "$WORKTREE_DIR" "$BRANCH"
else
    echo "Creating new orphan $BRANCH branch..."
    git worktree add --detach "$WORKTREE_DIR"
    cd "$WORKTREE_DIR"
    git checkout --orphan "$BRANCH"
    git rm -rf . 2>/dev/null || true
    touch .keep
    git add .keep
    git commit -m "Initial logs branch"
    git push -u origin "$BRANCH"
fi

cd "$WORKTREE_DIR" || exit 1
git reset --hard "origin/$BRANCH" 2>/dev/null || true

DEST_DIR="$WORKTREE_DIR/$ENV_NAME"
rm -rf "$DEST_DIR"
mkdir -p "$DEST_DIR"

echo "Gathering snapshot for $ENV_NAME..."

# === LOG FILES (current *.log, excluding rotated dated ones) ===
if [ -d "$REPO_DIR/logs" ]; then
    mkdir -p "$DEST_DIR/logs"
    for f in "$REPO_DIR/logs/"*.log; do
        [ -f "$f" ] || continue
        fn=$(basename "$f")
        [[ "$fn" =~ -202[0-9]- ]] && continue   # skip rotated app-2026-...log
        cp "$f" "$DEST_DIR/logs/"
    done
fi

# === DATA FILES (csv/json only; skip sqlite/binary caches to avoid bloat) ===
if [ -d "$REPO_DIR/data" ]; then
    mkdir -p "$DEST_DIR/data"
    cp "$REPO_DIR/data/"*.csv  "$DEST_DIR/data/" 2>/dev/null || true
    cp "$REPO_DIR/data/"*.json "$DEST_DIR/data/" 2>/dev/null || true
    # One level of per-symbol subdirs (e.g. data/AAPL/, data/TSLA/)
    for d in "$REPO_DIR/data/"*/; do
        [ -d "$d" ] || continue
        sub=$(basename "$d")
        mkdir -p "$DEST_DIR/data/$sub"
        cp "$d"*.csv  "$DEST_DIR/data/$sub/" 2>/dev/null || true
        cp "$d"*.json "$DEST_DIR/data/$sub/" 2>/dev/null || true
    done
    echo "Skipping .sqlite3 and binary caches to prevent repo bloat."
fi

# === CONFIG (redacted) ===
if [ -f "$REPO_DIR/config.json" ]; then
    echo "Copying config.json (redacted)..."
    python3 -c "import json,sys,re; r=lambda o: {k:(r(v) if not re.search(r'(key|token|secret|password|sig)',k,re.I) else '[REDACTED]') for k,v in o.items()} if isinstance(o,dict) else [r(x) for x in o] if isinstance(o,list) else o; json.dump(r(json.load(sys.stdin)), sys.stdout, indent=2)" < "$REPO_DIR/config.json" > "$DEST_DIR/config.json" 2>/dev/null || true
fi

# === STATE ===
[ -f "$REPO_DIR/state.json" ] && cp "$REPO_DIR/state.json" "$DEST_DIR/" 2>/dev/null || true

# === ENVIRONMENT-SPECIFIC SNAPSHOT ===
if [ "$ENV_NAME" = "prod" ]; then
    echo "Creating production health report..."
    {
        echo "=== PRODUCTION HEALTH REPORT ==="
        echo "Timestamp: $(date)"
        echo "Hostname:  $(hostname)"
        echo "Uptime:    $(uptime)"
        echo ""
        echo "=== DISK USAGE ==="; df -h; echo ""
        echo "=== MEMORY USAGE ==="; free -h; echo ""
        echo "=== LOAD AVERAGE ==="; cat /proc/loadavg; echo ""
        echo "=== PROCESS STATUS ==="
        ps aux | grep -E "(uvicorn|gunicorn|streamlit|app\.py|orchestrator)" | grep -v grep || true
        echo ""
        echo "=== SERVICE STATUS ==="
        systemctl is-active "$SERVICE_NAME" 2>/dev/null || echo "(service not installed)"
        echo ""
        echo "=== RECENT ERRORS ==="
        if [ -s "$REPO_DIR/logs/app.log" ]; then
            grep -i "error\|critical\|exception" "$REPO_DIR/logs/app.log" | tail -20 || true
        fi
    } > "$DEST_DIR/production_health_report.txt"
else
    echo "Creating system snapshot..."
    {
        echo "=== SYSTEM SNAPSHOT ($ENV_NAME) ==="
        echo "Timestamp: $(date)"
        echo "Hostname:  $(hostname)"
        echo "Uptime:    $(uptime)"
        echo ""
        echo "=== DISK USAGE ==="; df -h; echo ""
        echo "=== MEMORY USAGE ==="; free -h; echo ""
        echo "=== PROCESS STATUS ==="
        ps aux | grep -E "(python|uvicorn|gunicorn|streamlit)" | grep -v grep || true
    } > "$DEST_DIR/system_snapshot.txt"
fi

touch "$DEST_DIR/.keep"

# === COMMIT & PUSH (in the worktree, not the live checkout) ===
cd "$WORKTREE_DIR" || exit 1
git add "$ENV_NAME"

if git diff --cached --quiet; then
    echo "No changes since last snapshot, skipping commit."
else
    git commit -m "Snapshot $ENV_NAME: $(date +'%Y-%m-%d %H:%M')"
    # Retry with rebase if the other environment pushed since our fetch.
    PUSH_OK=0
    for attempt in 1 2 3; do
        if git push origin "$BRANCH" 2>&1; then
            echo "Snapshot pushed to $BRANCH branch."
            PUSH_OK=1
            break
        else
            echo "Push failed (attempt $attempt/3), rebasing and retrying..."
            git fetch origin "$BRANCH"
            git rebase "origin/$BRANCH"
        fi
    done
    if [ "$PUSH_OK" -ne 1 ]; then
        echo "ERROR: snapshot push failed after 3 attempts — $BRANCH not updated" >&2
        echo "[CRON-ALERT] collect_logs.sh push exhausted retries for $ENV_NAME" >&2
        exit 1
    fi
fi

echo "Successfully collected $ENV_NAME logs!"
