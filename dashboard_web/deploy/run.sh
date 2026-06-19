#!/usr/bin/env bash
# Run the read-only observability web dashboard: FastAPI serving the built SPA + /api on ONE port, bound to
# this box's Tailscale IP. KEYLESS (DRAMATIC_SKIP_DOTENV=1), read-only, NO-FETCH. FAIL-CLOSED: it never binds
# a wildcard/public interface — if the tailnet IP can't be resolved it exits rather than expose the book.
set -euo pipefail

REPO="${DRAMATIC_WEB_REPO:-/home/rodrigo/dramatic_options-claude}"   # the worktree (its venv has trading+fastapi; the live venv stays minimal)
VENV="$REPO/venv"
PORT="${DRAMATIC_WEB_PORT:-8503}"
export DRAMATIC_SKIP_DOTENV=1
export DRAMATIC_DB="${DRAMATIC_DB:-/home/rodrigo/dramatic_options/data/dramatic_options.db}"
export DRAMATIC_CACHE_DIR="${DRAMATIC_CACHE_DIR:-/home/rodrigo/dramatic_options/data/cache}"

# Resolve the tailnet IP (poll ~60s so boot-lag doesn't burn the systemd StartLimit). Fail-closed.
ip=""
for _ in $(seq 1 60); do
  ip="$(tailscale ip -4 2>/dev/null | head -1 || true)"
  [ -z "$ip" ] && ip="$(ip -4 addr show tailscale0 2>/dev/null | grep -oP 'inet \K[0-9.]+' || true)"
  [ -n "$ip" ] && break
  sleep 1
done
if [ -z "$ip" ]; then
  echo "no tailscale IP — refusing to bind (fail-closed)" >&2
  exit 1
fi

# cd to the repo root so themes.json / config.json resolve (the curation/CWD finding).
cd "$REPO"
exec "$VENV/bin/uvicorn" --app-dir dashboard_web/api server:app --host "$ip" --port "$PORT" --log-level warning
