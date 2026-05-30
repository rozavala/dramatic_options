#!/bin/bash
# =============================================================================
# dramatic_options — Post-Deployment Verification
# Returns 0 if healthy, 1 if critical failure (triggers rollback in deploy.sh).
#
# Adapted from real_options. Checks run best-effort; only CRITICAL issues
# (FAILED=1) abort the deploy. Add app-specific checks as the app grows.
# =============================================================================
# No 'set -e' — we want to run every check and report.

REPO_ROOT=$(pwd)
HEALTH_LOG="logs/deploy_health.log"
mkdir -p logs

echo "$(date --iso=s) — Starting post-deploy verification" >> "$HEALTH_LOG"
FAILED=0

# -------------------------------------------------------------------------
# CHECK 1: Disk space
# -------------------------------------------------------------------------
echo "  [verify] Checking disk space..."
DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | tr -d '%')
if [ "${DISK_USAGE:-0}" -gt 90 ]; then
    echo "  [verify] WARNING: Disk usage at ${DISK_USAGE}%"
    echo "$(date --iso=s) — WARN: disk ${DISK_USAGE}%" >> "$HEALTH_LOG"
fi

# -------------------------------------------------------------------------
# CHECK 2: Core module imports (flat layout — no top-level package)
# -------------------------------------------------------------------------
echo "  [verify] Checking core module imports..."
if [ -f "config_loader.py" ]; then
    PYBIN="python"
    [ -x "venv/bin/python" ] && PYBIN="venv/bin/python"
    if ! "$PYBIN" -c "import config_loader" 2>/dev/null; then
        echo "  [verify] CRITICAL: cannot import config_loader"
        echo "$(date --iso=s) — FAIL: import config_loader" >> "$HEALTH_LOG"
        FAILED=1
    fi
else
    echo "  [verify] (config_loader.py not present yet — skipping import check)"
fi

# -------------------------------------------------------------------------
# CHECK 3: HTTP health endpoint (webapp) — only if HEALTH_URL is set
# -------------------------------------------------------------------------
if [ -n "$HEALTH_URL" ]; then
    echo "  [verify] Checking health endpoint $HEALTH_URL ..."
    if ! curl -fsS --max-time 10 "$HEALTH_URL" >/dev/null 2>&1; then
        echo "  [verify] CRITICAL: Health endpoint did not respond OK"
        echo "$(date --iso=s) — FAIL: health endpoint" >> "$HEALTH_LOG"
        FAILED=1
    fi
else
    echo "  [verify] (HEALTH_URL not set — skipping HTTP check)"
fi

# -------------------------------------------------------------------------
# CHECK 4: Critical files exist
# -------------------------------------------------------------------------
echo "  [verify] Checking critical files..."
CRITICAL_FILES=("deploy.sh" "orchestrator.py")
for _f in "${CRITICAL_FILES[@]}"; do
    if [ ! -f "$_f" ]; then
        echo "  [verify] CRITICAL: Missing $_f"
        echo "$(date --iso=s) — FAIL: missing $_f" >> "$HEALTH_LOG"
        FAILED=1
    fi
done

if [ "$FAILED" -eq 1 ]; then
    echo "  [verify] ❌ Verification FAILED"
    echo "$(date --iso=s) — VERIFICATION FAILED" >> "$HEALTH_LOG"
    exit 1
fi

echo "  [verify] ✅ All critical checks passed"
echo "$(date --iso=s) — VERIFICATION PASSED" >> "$HEALTH_LOG"
exit 0
