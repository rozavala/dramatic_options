#!/usr/bin/env bash
# Dramatic Options — dashboard launch wrapper (§5b). The systemd unit's ExecStart.
#
# Resolves the per-box Tailscale IP AT START (so one unit is correct on DEV + PROD and survives an IP change),
# POLLING up to ~60s: After=tailscaled guarantees tailscaled has STARTED, not that it has an IP yet (cold boot /
# re-auth can lag it tens of seconds). Absorbing that lag here means boot timing never burns the unit's
# StartLimit — only a genuine persistent failure (no binary / no IP ever / a dep break) trips it to `failed`.
#
# FAIL-CLOSED: if there is still no tailnet IPv4, exit non-zero (the unit's Restart retries) — NEVER bind a
# wildcard/public address, which would put the confidential book + cluster-map view on the public interface.
#
# Keyless by construction: the unit sets DRAMATIC_SKIP_DOTENV=1, so config_loader never reads .env.
set -u

cd "$(dirname "$0")/.." || { echo "dashboard_run: cannot cd to repo root" >&2; exit 1; }

TS="$(command -v tailscale || echo /usr/bin/tailscale)"
ADDR=""
for _ in $(seq 1 12); do                       # ~60s (12 × 5s)
    ADDR="$("$TS" ip -4 2>/dev/null | head -n1)"
    [ -n "$ADDR" ] && break
    sleep 5
done
[ -n "$ADDR" ] || { echo "dashboard_run: no Tailscale IPv4 after ~60s — refusing to bind (no wildcard fallback)" >&2; exit 1; }

# ABSOLUTE app path: the sibling real_options deploy runs `pkill -f "streamlit run dashboard.py"`, which
# matches any repo's relative-path invocation (observed collateral kill 2026-07-08). With the absolute path
# our cmdline no longer contains that substring, so an unqualified sibling pattern cannot hit this process.
exec venv/bin/streamlit run "$PWD/dashboard.py" \
    --server.address "$ADDR" --server.port 8601 --server.headless true
