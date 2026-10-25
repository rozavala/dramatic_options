#!/usr/bin/env bash
# Scheduled, unattended Claude Code runs for Dramatic Options (cron on the DEV box) — the nightly L1 grade and the
# Sunday review. Replaces the session-only crons, which died with the interactive session (2026-10-22). Cloud
# routines can't reach this box's DB, journals or memory directory, so the job runs here, headless, in its own
# runner worktree (never the interactive worktree, never the live checkout).
#
#   scheduled_review.sh grade    weekdays 20:37 UTC  read-only grade + one memory banner
#   scheduled_review.sh sunday   Sundays 14:23 UTC   Sunday review; may open ONE records PR, never merges
#   scheduled_review.sh <job> --dry-run              print the command, no claude call, no Pushover
#
# The cron times are UTC but the runs reviewed are ET-anchored systemd timers (L1 15:45 ET, reach Sun 09:40 ET), so
# a fixed UTC time fires an hour early once DST ends (#341). Each job therefore waits for the run it reviews: today's
# dramatic-options-l1 (grade) or dramatic-options-reach (sunday) must have exited before claude starts; after
# WAIT_MIN minutes it pages and gives up rather than review a run that hasn't happened.
#
# Safety (mirrors real_options' triage_scheduled.sh): one run per job (flock); waits for load; a hard spend cap
# (--max-budget-usd); write commands denied (grade: every git/gh write; sunday: merges and anything outside its one
# records PR); the result goes to Pushover with the command to resume the session.
set -euo pipefail
export PATH="$HOME/.local/bin:$HOME/bin:/usr/local/bin:$PATH"   # cron's PATH lacks claude and gh

JOB="${1:-}"; DRY=0; [ "${2:-}" = "--dry-run" ] && DRY=1
case "$JOB" in grade|sunday) ;; *) echo "usage: $0 grade|sunday [--dry-run]" >&2; exit 2;; esac

LIVE=/home/rozavala/dramatic_options
RUNNER_DIR="${DRAMATIC_RUNNER_DIR:-/home/rozavala/dramatic_options-claude-runner}"
STATE_DIR="$HOME/.local/state/dramatic-options"
LOCK="$STATE_DIR/$JOB.lock"
mkdir -p "$STATE_DIR"
ts() { date -u +%FT%TZ; }
push() {  # title, message, priority — the live checkout's notify.py + .env (execution only; nothing written there)
  [ "$DRY" -eq 1 ] && { echo "[dry-run] push: $1 — $2"; return 0; }
  ( cd "$LIVE" && venv/bin/python notify.py --priority "${3:-0}" "$1" "$2" ) >/dev/null 2>&1 || true
}
trap 'rc=$?; push "[DEV] Dramatic $JOB FAILED" "launcher error rc=$rc at line $LINENO — see $STATE_DIR/cron.log"; exit $rc' ERR

exec 9>"$LOCK"
flock -n 9 || { echo "$(ts) $JOB already running — skip"; exit 0; }

# The runner worktree: a detached checkout of origin/main with the live venv linked in (packages only).
if [ ! -d "$RUNNER_DIR/.git" ] && [ ! -f "$RUNNER_DIR/.git" ]; then
  git -C "$LIVE" worktree add --detach "$RUNNER_DIR" origin/main
fi
git -C "$RUNNER_DIR" fetch -q origin
git -C "$RUNNER_DIR" checkout -q --detach origin/main
[ -e "$RUNNER_DIR/venv" ] || ln -s "$LIVE/venv" "$RUNNER_DIR/venv"

# Wait for the run this job reviews (#341): its unit exited today (UTC date) and is not running again.
UNIT=dramatic-options-$([ "$JOB" = grade ] && echo l1 || echo reach).service
WAIT_MIN="${DRAMATIC_REVIEW_WAIT_MIN:-120}"
ran_today() {
  local st ex
  st=$(systemctl show "$UNIT" -p ActiveState --value 2>/dev/null || true)
  ex=$(systemctl show "$UNIT" -p ExecMainExitTimestamp --value 2>/dev/null || true)
  [ -n "$ex" ] && [ "$st" != active ] && [ "$st" != activating ] \
    && [ "$(date -u -d "$ex" +%F 2>/dev/null)" = "$(date -u +%F)" ]
}
if [ "$DRY" -eq 1 ]; then
  echo "[dry-run] would wait up to ${WAIT_MIN}m for $UNIT to have exited today (now: $(ran_today && echo yes || echo no))"
else
  waited=0
  until ran_today; do
    if [ "$waited" -ge "$WAIT_MIN" ]; then
      push "[DEV] Dramatic $JOB NOT RUN" "$UNIT has not exited today after ${WAIT_MIN}m of waiting — nothing reviewed" 0
      echo "$(ts) $JOB: $UNIT not run today after ${WAIT_MIN}m — giving up"; exit 0
    fi
    [ "$waited" -eq 0 ] && echo "$(ts) $JOB: waiting for $UNIT to finish today's run"
    sleep 60; waited=$((waited + 1))
  done
fi

NCPU=$(nproc)
[ "$DRY" -eq 1 ] || for _ in $(seq 1 30); do
  L=$(cut -d' ' -f1 /proc/loadavg)
  awk -v l="$L" -v n="$NCPU" 'BEGIN{exit !(l < n)}' && break
  echo "$(ts) load $L >= $NCPU — waiting 60s"; sleep 60
done

DATE=$(date -u +%F)
SID=$(uuidgen)
RAW="$STATE_DIR/${DATE}-${JOB}.json"
PROMPT_FILE="$RUNNER_DIR/scripts/ops/prompts/$([ "$JOB" = grade ] && echo nightly_grade || echo sunday_review).md"
PROMPT=$(cat "$PROMPT_FILE")

DENY=("Bash(gh pr merge:*)" "Bash(gh pr close:*)" "Bash(gh pr review:*)" "Bash(gh pr edit:*)"
      "Bash(gh issue:*)" "Bash(gh api -X:*)" "Bash(gh api --method:*)" "Bash(gh api graphql:*)"
      "Bash(gh release:*)" "Bash(gh secret:*)" "Bash(gh workflow:*)" "Bash(git push --force:*)"
      "Bash(git push -f:*)" "Bash(systemctl start:*)" "Bash(systemctl restart:*)" "Bash(systemctl stop:*)"
      "Bash(sudo:*)" "Bash(python orchestrator.py:*)" "Bash(venv/bin/python -m orchestrator:*)")
if [ "$JOB" = grade ]; then
  DENY+=("Bash(git commit:*)" "Bash(git push:*)" "Bash(gh pr create:*)" "Bash(gh pr comment:*)" "Bash(gh pr ready:*)")
  BUDGET="${DRAMATIC_GRADE_BUDGET_USD:-5}"
else
  BUDGET="${DRAMATIC_SUNDAY_BUDGET_USD:-12}"
fi

CMD=(claude -p "$PROMPT" --session-id "$SID" -n "dramatic $JOB $DATE (scheduled)"
     --permission-mode auto --output-format json --max-budget-usd "$BUDGET"
     --disallowedTools "${DENY[@]}" --model "${DRAMATIC_MODEL:-opus}" --effort "${DRAMATIC_EFFORT:-high}")

HEAD_SHA=$(git -C "$RUNNER_DIR" rev-parse --short=10 HEAD)
echo "$(ts) start $JOB: session=$SID main=$HEAD_SHA budget=\$$BUDGET raw=$RAW"
if [ "$DRY" -eq 1 ]; then
  printf '[dry-run] cd %q &&' "$RUNNER_DIR"; printf ' %q' "${CMD[@]:0:2}"; echo " … (${#PROMPT} chars) ${CMD[*]:3}"
  exit 0
fi

set +e
( cd "$RUNNER_DIR" && "${CMD[@]}" ) > "$RAW" 2> "$STATE_DIR/${DATE}-${JOB}.stderr"
RC=$?
set -e

RESULT=$("$LIVE/venv/bin/python" - "$RAW" <<'PY' 2>/dev/null || true
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    print("no JSON result"); sys.exit()
text = str(d.get("result") or "")
head = [ln for ln in text.splitlines() if ln.startswith("HEADLINE:")]
cost = d.get("total_cost_usd")
print((head[-1] if head else text[-300:].replace("\n", " ")) + (f" · ${cost:.2f}" if isinstance(cost, (int, float)) else ""))
PY
)
RESUME="cd $RUNNER_DIR && claude --resume $SID"
PRIO=-1; [ "$JOB" = sunday ] && PRIO=0
echo "$RESULT" | grep -q -E "FINDINGS: (0|none)" || [ "$JOB" = sunday ] || PRIO=0
[ "$RC" -eq 0 ] || { PRIO=0; RESULT="claude exited rc=$RC — $RESULT"; }
push "[DEV] Dramatic $JOB $DATE" "$RESULT — resume: $RESUME" "$PRIO"
echo "$(ts) done $JOB rc=$RC: $RESULT"
