#!/usr/bin/env bash
# Dramatic Options — WEB dashboard launch wrapper. The dramatic-options-web.service ExecStart.
# FastAPI serves the built React SPA + the read-only /api on ONE port (8602), bound to LOCALHOST only.
#
#   • Reachable ONLY through the box's tailnet-only HTTPS proxy (the Real Options pattern, 2026-10-06):
#       tailscale serve --bg --https=8602 http://127.0.0.1:8602
#     → https://<box>.<tailnet>.ts.net:8602. HTTPS is what lets the dashboard install as an app
#     (dashboard_web/api/pwa.py), and the localhost bind leaves the tailnet's :8602 free for the proxy.
#     Without the serve entry the dashboard is simply unreachable — fail-closed, never a wildcard/public
#     bind (it renders the confidential book + cluster-map view).
#   • Keyless by construction: the unit sets DRAMATIC_SKIP_DOTENV=1, so config_loader never reads .env.
#   • Runs from the LIVE checkout (cd repo root) so data/, themes.json and config.json resolve (the latter
#     is what lets the curation panel render rather than fail-soft to an error).
set -u

cd "$(dirname "$0")/.." || { echo "dashboard_web_run: cannot cd to repo root" >&2; exit 1; }

exec venv/bin/uvicorn --app-dir dashboard_web/api server:app \
    --host 127.0.0.1 --port 8602 --log-level warning
