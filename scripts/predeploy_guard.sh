#!/bin/bash
# =============================================================================
# T4 arming (#468): the predeploy guard. Both arming guards, run against the checkout AS IT IS NOW, before anything
# moves it. Exit 0 = go on; exit 1 = refused (it never changes anything itself; it only reads).
#
#   ENV_NAME=PROD bash scripts/predeploy_guard.sh [SYSTEMD_DST UNIT...]
#
# Callers:
#   * .github/workflows/deploy.yml runs it from the CURRENT live checkout before its self-heal, `git fetch`,
#     `git checkout` and `git reset --hard`. A refusal fails the job with the checkout untouched, so the armed timers
#     keep running the code that was deployed with them (not a new commit that never had its deps, migrations or
#     verify). A checkout older than #468 has no copy of this file; the workflow then skips it.
#   * deploy.sh runs it first, before the lock and before systemd is touched (a manual deploy), passing its own
#     SYSTEMD_DST and LIVE_UNITS.
#
# ENV_NAME is the value the CALLER gave (empty when none): live_deploy_guard needs to know it was not given.
# The guards themselves (live_deploy_guard, live_strip_guard) live in scripts/live_arming.sh, next to this file.
# =============================================================================

# Defaults for the workflow call (deploy.sh passes its own). Constants, not env-overridable.
PREDEPLOY_SYSTEMD_DST="/etc/systemd/system"
PREDEPLOY_LIVE_UNITS=("dramatic-options-l1.service" "dramatic-options-l2.service")

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$HERE")"
if [ ! -f "$HERE/live_arming.sh" ]; then
    # This file and the helper ship in the same commit; one without the other is a broken tree. Fail closed.
    echo "!!! predeploy guard: $HERE/live_arming.sh is missing; refusing (fail-closed)"
    exit 1
fi
# shellcheck source=scripts/live_arming.sh
. "$HERE/live_arming.sh"

given="${ENV_NAME:-}"
dst="${1:-$PREDEPLOY_SYSTEMD_DST}"
if [ "$#" -gt 1 ]; then shift; units=("$@"); else units=("${PREDEPLOY_LIVE_UNITS[@]}"); fi

if ! live_deploy_guard "$given" \
        || ! live_strip_guard "$REPO_ROOT/.env" "${given:-DEV}" "$dst" "${units[@]}"; then
    echo "!!! ===================================================== !!!"
    echo "!!! DEPLOY ABORTED BEFORE ANY CHANGE: $LIVE_GUARD_REASON"
    echo "!!! Nothing was changed. See DEPLOYMENT.md, \"Arming PROD (T4)\": the guards, and Disarm."
    echo "!!! Manual deploy: if you already moved this checkout (git pull / reset) before running deploy.sh, the armed"
    echo "!!! timers are now running that commit without its deps, migrations or verify; move it back to the"
    echo "!!! deployed commit until this guard passes."
    echo "!!! ===================================================== !!!"
    exit 1
fi
echo "  predeploy guard: passed"
exit 0
