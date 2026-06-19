#!/usr/bin/env bash
# Dramatic Options — WEB dashboard launch wrapper. The dramatic-options-web.service ExecStart.
# FastAPI serves the built React SPA + the read-only /api on ONE port (8503), bound to the per-box
# Tailscale IP. Mirrors scripts/dashboard_run.sh (the Streamlit wrapper):
#
#   • resolve the per-box Tailscale IP AT START, POLLING ~60s (After=tailscaled guarantees STARTED, not
#     that it has an IP — cold boot / re-auth can lag it). Absorbing that here means boot timing never
#     burns the unit StartLimit.
#   • FAIL-CLOSED: no tailnet IPv4 → exit non-zero (Restart retries); NEVER bind a wildcard/public address
#     (it renders the confidential book + cluster-map view).
#   • Keyless by construction: the unit sets DRAMATIC_SKIP_DOTENV=1, so config_loader never reads .env.
#   • Runs from the LIVE checkout (cd repo root) so data/, themes.json and config.json resolve (the latter
#     is what lets the curation panel render rather than fail-soft to an error).
set -u

cd "$(dirname "$0")/.." || { echo "dashboard_web_run: cannot cd to repo root" >&2; exit 1; }

TS="$(command -v tailscale || echo /usr/bin/tailscale)"
ADDR=""
for _ in $(seq 1 12); do                       # ~60s (12 × 5s)
    ADDR="$("$TS" ip -4 2>/dev/null | head -n1)"
    [ -n "$ADDR" ] && break
    sleep 5
done
[ -n "$ADDR" ] || { echo "dashboard_web_run: no Tailscale IPv4 after ~60s — refusing to bind (no wildcard fallback)" >&2; exit 1; }

# Serves dashboard_web/ui/dist (if built) + /api on the tailnet. server.py mounts the SPA only if dist
# exists, so a missing/failed build degrades to API-only rather than crashing.
exec venv/bin/uvicorn --app-dir dashboard_web/api server:app \
    --host "$ADDR" --port 8503 --log-level warning
