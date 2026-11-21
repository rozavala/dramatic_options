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

# -------------------------------------------------------------------------
# CHECK 5: live-checkout .env present + complete (only where this env TRADES)
# -------------------------------------------------------------------------
# Load-bearing (PR2): the systemd units read $REPO_ROOT/.env, and a failure CAUSED by a
# missing/incomplete .env cannot self-page (the notify@ unit reads the same empty file). So we
# refuse to arm trading timers without a real .env — this is the deploy-time stop that makes the
# missing-.env case safe. Gated on FORWARD_ENABLED=true (DEV trades / PROD stays inert).
ENV_FILE="$REPO_ROOT/.env"

_env_truthy() {   # FORWARD_ENABLED from .env — grep, never `source`
    [ -f "$ENV_FILE" ] || { echo "false"; return; }
    local v
    v=$(grep -E '^[[:space:]]*FORWARD_ENABLED[[:space:]]*=' "$ENV_FILE" 2>/dev/null \
        | tail -1 | cut -d= -f2- | tr -d "\"' \t\r")
    case "$(printf '%s' "$v" | tr '[:upper:]' '[:lower:]')" in
        1|true|yes|on) echo "true" ;; *) echo "false" ;;
    esac
}
_env_val() {      # value of a key in .env (empty if absent)
    grep -E "^[[:space:]]*$1[[:space:]]*=" "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d "\"' \t\r"
}

# T4 arming (#468): which Alpaca pair a trading env must carry. The SAME decision deploy.sh renders `--live` from
# (scripts/live_arming.sh: the operator's root-owned marker AND PAPER=false, LIVE_TRADING_ENABLED=true,
# FORWARD_ENABLED=true). Armed → the LIVE pair; every other trading env → the paper pair, exactly as before. A missing
# helper is "not armed" (the paper rule, which fails a live-keyed box loudly rather than passing it).
_LIVE_ARMED=0
_ARMING_HELPER="$(dirname "${BASH_SOURCE[0]}")/live_arming.sh"
if [ -f "$_ARMING_HELPER" ]; then
    # shellcheck source=scripts/live_arming.sh
    . "$_ARMING_HELPER"
    live_arming_check "$ENV_FILE" "${ENV_NAME:-}"
    _LIVE_ARMED="$LIVE_ARMED"
fi

echo "  [verify] Checking live-checkout .env ($ENV_FILE)..."
if [ "$(_env_truthy)" = "true" ]; then
    if [ ! -f "$ENV_FILE" ]; then
        echo "  [verify] CRITICAL: FORWARD_ENABLED=true but $ENV_FILE is missing"
        echo "$(date --iso=s) — FAIL: .env missing on trading env" >> "$HEALTH_LOG"
        FAILED=1
    else
        REQUIRED_KEYS=(GEMINI_API_KEY XAI_API_KEY \
            ANTHROPIC_API_KEY DRY_RUN FORWARD_ENABLED PUSHOVER_API_TOKEN PUSHOVER_USER_KEY)
        MISSING=0
        # Alpaca keys (issue #279 item 6, STRICT): the venue-named pair, and NO legacy name (the loop refuses to
        # start with one set). A trading env is paper (the PAPER pair) unless it is ARMED (#468): then the LIVE pair,
        # the one config_loader.alpaca_credentials hands the live venue. Names only — a value is never printed.
        if [ "$_LIVE_ARMED" = "1" ]; then
            _pair=live; _kvar=ALPACA_LIVE_KEY_ID; _svar=ALPACA_LIVE_SECRET_KEY
            echo "  [verify] live arming: $LIVE_ARMING_REASON — requiring the LIVE key pair"
        else
            _pair=paper; _kvar=ALPACA_PAPER_KEY_ID; _svar=ALPACA_PAPER_SECRET_KEY
            if [ "${LIVE_ARMING_LOUD:-0}" = "1" ]; then
                echo "  [verify] live arming $LIVE_ARMING_REASON — not armed, so the paper pair is required"
            fi
        fi
        _pk=$(_env_val "$_kvar"); _ps=$(_env_val "$_svar")
        _legacy=""
        for _lv in ALPACA_API_KEY ALPACA_SECRET_KEY ALPACA_PAPER; do
            grep -qE "^[[:space:]]*${_lv}[[:space:]]*=" "$ENV_FILE" 2>/dev/null && _legacy="$_legacy $_lv"
        done
        if [ -n "$_legacy" ]; then
            echo "  [verify] CRITICAL: legacy Alpaca name(s) in .env:$_legacy — rename (issue #279)"
            echo "$(date --iso=s) — FAIL: .env legacy Alpaca names:$_legacy" >> "$HEALTH_LOG"
            FAILED=1; MISSING=1
        elif [ -n "$_pk" ] && [ -n "$_ps" ] && [[ "$_pk" != your_* ]] && [[ "$_ps" != your_* ]]; then
            echo "  [verify] Alpaca: venue-named $_pair pair present"
        else
            echo "  [verify] CRITICAL: no Alpaca $_pair key pair ($_kvar/$_svar)"
            echo "$(date --iso=s) — FAIL: .env Alpaca $_pair pair missing/placeholder" >> "$HEALTH_LOG"
            FAILED=1; MISSING=1
        fi
        for _k in "${REQUIRED_KEYS[@]}"; do
            _v=$(_env_val "$_k")
            if [ -z "$_v" ] || [[ "$_v" == your_* ]]; then
                echo "  [verify] CRITICAL: .env key $_k missing or a placeholder"
                echo "$(date --iso=s) — FAIL: .env $_k missing/placeholder" >> "$HEALTH_LOG"
                FAILED=1; MISSING=1
            fi
        done
        [ "$MISSING" -eq 0 ] && echo "  [verify] .env present with all required keys (trading env)"
    fi
else
    echo "  [verify] (FORWARD_ENABLED!=true — inert env; .env key assertion skipped)"
fi

if [ "$FAILED" -eq 1 ]; then
    echo "  [verify] ❌ Verification FAILED"
    echo "$(date --iso=s) — VERIFICATION FAILED" >> "$HEALTH_LOG"
    exit 1
fi

echo "  [verify] ✅ All critical checks passed"
echo "$(date --iso=s) — VERIFICATION PASSED" >> "$HEALTH_LOG"
exit 0
