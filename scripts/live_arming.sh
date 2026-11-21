# shellcheck shell=bash
# =============================================================================
# T4 arming (#468): the deploy-time source of the THIRD live key, `--live`.
#
# Sourced (never executed) by deploy.sh, which renders `--live` into the trading units, and by
# scripts/verify_deploy.sh, whose CHECK 5 then requires the LIVE key pair instead of the paper pair.
# Both ask the same question through live_arming_check, so the two can never disagree.
#
# The triple gate (CLAUDE.md guardrail 1; config_loader.live_allowed) is PAPER=false AND
# LIVE_TRADING_ENABLED=true AND an explicit `--live`. The first two are .env acts. `--live` stays a
# SEPARATE act: it is never derived from the .env. It comes from a marker the operator creates by hand,
# as root, outside the repo and outside the .env:
#
#     /etc/dramatic-options/live-armed     exactly one line: PROD
#
# live_arming_check sets LIVE_ARMED=1 only when ALL hold:
#   1. the deploy's ENV_NAME is PROD (LIVE_ARMABLE_ENV): no other env can be armed;
#   2. the marker is a regular file (not a symlink), owned by root, not group- or other-writable, readable,
#      in a directory that is root-owned and not group- or other-writable, and it holds exactly one line
#      (trailing whitespace allowed) equal to ENV_NAME, with no further non-empty line;
#   3. the .env already says armed: PAPER=false, LIVE_TRADING_ENABLED=true and FORWARD_ENABLED=true, each
#      assigned without a conflicting second value.
# Anything else, including any read that fails, is LIVE_ARMED=0 (fail-closed). A marker alone renders
# nothing; the flags alone render nothing. Nothing in this repo writes the marker.
#
# live_deploy_guard is the deploy's first check: when a marker exists, the deploy must have been given the env
# the marker names. Otherwise it aborts before changing anything (a defaulted ENV_NAME=DEV on an armed box would
# re-render L1/L2 without --live and leave live positions unmanaged).
#
# A rendered `--live` is still only the third key: config_loader.live_allowed re-reads the two .env flags
# on every run, and DRY_RUN=true still keeps AlpacaLiveBroker from transmitting.
#
# Outputs (globals): LIVE_ARMED (1|0), LIVE_ARMING_REASON (one line; flag values and names only, never a
# key value), LIVE_ARMING_LOUD (1 when the state is ambiguous or refused and the caller must say so loudly),
# LIVE_GUARD_REASON (why live_deploy_guard refused).
# =============================================================================

# Constants, not env-overridable: a caller's environment must not be able to move the marker.
LIVE_MARKER="/etc/dramatic-options/live-armed"
LIVE_MARKER_OWNER_UID=0
LIVE_ARMABLE_ENV="PROD"

# One raw .env value, read the way python-dotenv would at most: surrounding whitespace and ONE pair of matching
# surrounding quotes stripped, lowercased. Nothing inside the value is deleted, so `tr ue` or `t"r"ue` never reads
# as `true` (the shell's armed reading must be a subset of dotenv's).
_arming_norm() {
    local v="$1"
    v="${v#"${v%%[![:space:]]*}"}"
    v="${v%"${v##*[![:space:]]}"}"
    if [ "${#v}" -ge 2 ]; then
        case "$v" in
            \"*\") v="${v:1:${#v}-2}" ;;
            \'*\') v="${v:1:${#v}-2}" ;;
        esac
    fi
    printf '%s' "${v,,}"
}

# The value of KEY in FILE (normalized): grep, never `source` (the .env must never execute). `export KEY=` lines
# count too. Prints "" when the key is absent, or "<conflict>" when the file assigns it more than one distinct
# value (dotenv and systemd each take a last one; arming refuses to guess).
_arming_env_value() {
    local file="$1" key="$2" line v known k
    local -a vals=()
    while IFS= read -r line; do
        v=$(_arming_norm "${line#*=}")
        known=0
        for k in "${vals[@]}"; do [ "x$k" = "x$v" ] && known=1; done
        [ "$known" = 1 ] || vals+=("$v")
    done < <(grep -E "^[[:space:]]*(export[[:space:]]+)?${key}[[:space:]]*=" "$file" 2>/dev/null)
    case "${#vals[@]}" in
        0) printf '' ;;
        1) printf '%s' "${vals[0]}" ;;
        *) printf '<conflict>' ;;
    esac
}

# The env name the marker holds, by the one-line rule: the first line with trailing whitespace (and \r) stripped,
# and no further non-empty line. Returns 1 (prints nothing) when the marker cannot be read or breaks the rule.
_arming_marker_name() {
    local first rest
    [ -f "$LIVE_MARKER" ] && [ -r "$LIVE_MARKER" ] || return 1
    first=$(head -n 1 "$LIVE_MARKER" 2>/dev/null) || return 1
    first="${first%"${first##*[![:space:]]}"}"
    rest=$(tail -n +2 "$LIVE_MARKER" 2>/dev/null | tr -d '[:space:]') || return 1
    [ -n "$first" ] && [ -z "$rest" ] || return 1
    printf '%s' "$first"
}

# Why the marker does not arm this env ("" when it is valid). Never prints the marker's content unless it is
# a plain env-name token.
_arming_marker_problem() {
    local env_name="$1" st owner mode dir name target
    if [ -L "$LIVE_MARKER" ]; then echo "the marker $LIVE_MARKER is a symlink"; return; fi
    if [ ! -e "$LIVE_MARKER" ]; then echo "absent"; return; fi
    if [ ! -f "$LIVE_MARKER" ]; then echo "the marker $LIVE_MARKER is not a regular file"; return; fi
    if [ ! -r "$LIVE_MARKER" ]; then echo "the marker $LIVE_MARKER is unreadable"; return; fi
    dir=$(dirname "$LIVE_MARKER")
    if [ -L "$dir" ]; then echo "the marker's directory $dir is a symlink"; return; fi
    for target in "$dir" "$LIVE_MARKER"; do
        st=$(stat -c '%u %a' "$target" 2>/dev/null) || { echo "$target could not be stat'ed"; return; }
        owner=${st% *}; mode=${st#* }
        if [ "$owner" != "$LIVE_MARKER_OWNER_UID" ]; then
            echo "$target is owned by uid $owner, not uid $LIVE_MARKER_OWNER_UID (create it with sudo)"; return
        fi
        case "$mode" in *[!0-7]*|"") echo "$target has an unreadable mode '$mode'"; return ;; esac
        if (( 8#$mode & 8#022 )); then echo "$target is group- or other-writable (mode $mode)"; return; fi
    done
    if [ -z "$env_name" ]; then echo "ENV_NAME is unset, so the marker cannot match it"; return; fi
    if ! name=$(_arming_marker_name); then
        echo "the marker $LIVE_MARKER is not exactly one line naming an env"; return
    fi
    if [ "$name" != "$env_name" ]; then
        if [[ "$name" =~ ^[A-Za-z0-9_-]{1,32}$ ]]; then
            echo "the marker $LIVE_MARKER names '$name', not this env '$env_name'"
        else
            echo "the marker $LIVE_MARKER does not contain exactly this env's name '$env_name'"
        fi
        return
    fi
    echo ""
}

# Why the .env does not say armed ("" when it does). Prints flag values only (never a key).
_arming_flags_problem() {
    local env_file="$1" paper live fwd why=""
    if [ ! -f "$env_file" ]; then echo "no .env at $env_file"; return; fi
    paper=$(_arming_env_value "$env_file" PAPER)
    live=$(_arming_env_value "$env_file" LIVE_TRADING_ENABLED)
    fwd=$(_arming_env_value "$env_file" FORWARD_ENABLED)
    case "$paper" in 0|false|no|off) ;; *) why="$why PAPER=${paper:-<unset>} (needs false);" ;; esac
    case "$live" in 1|true|yes|on) ;; *) why="$why LIVE_TRADING_ENABLED=${live:-<unset>} (needs true);" ;; esac
    case "$fwd" in 1|true|yes|on) ;; *) why="$why FORWARD_ENABLED=${fwd:-<unset>} (needs true);" ;; esac
    echo "${why# }"
}

# live_arming_check ENV_FILE ENV_NAME — sets LIVE_ARMED / LIVE_ARMING_REASON / LIVE_ARMING_LOUD. Always returns 0.
live_arming_check() {
    local env_file="$1" env_name="$2" marker flags
    LIVE_ARMED=0
    LIVE_ARMING_LOUD=0
    marker=$(_arming_marker_problem "$env_name")
    flags=$(_arming_flags_problem "$env_file")
    if [ "$marker" != "absent" ] && [ "$env_name" != "$LIVE_ARMABLE_ENV" ]; then
        LIVE_ARMING_LOUD=1
        LIVE_ARMING_REASON="REFUSED: only $LIVE_ARMABLE_ENV can be armed, and this deploy is ENV_NAME='$env_name' (a marker is present at $LIVE_MARKER)"
    elif [ -z "$marker" ] && [ -z "$flags" ]; then
        LIVE_ARMED=1
        LIVE_ARMING_LOUD=1
        LIVE_ARMING_REASON="ARMED: the marker $LIVE_MARKER names '$env_name' and the .env says PAPER=false, LIVE_TRADING_ENABLED=true, FORWARD_ENABLED=true"
    elif [ "$marker" = "absent" ] && [ -n "$flags" ]; then
        LIVE_ARMING_REASON="not armed (no marker at $LIVE_MARKER)"
    elif [ "$marker" = "absent" ]; then
        LIVE_ARMING_LOUD=1
        LIVE_ARMING_REASON="REFUSED: the .env says armed but there is no marker at $LIVE_MARKER, so the third key is absent (live_allowed stays False)"
    elif [ -n "$marker" ]; then
        LIVE_ARMING_LOUD=1
        LIVE_ARMING_REASON="REFUSED: $marker${flags:+; and the .env is not armed: $flags}"
    else
        LIVE_ARMING_LOUD=1
        LIVE_ARMING_REASON="REFUSED: the marker is present but the .env is not armed: $flags"
    fi
    return 0
}

# live_deploy_guard GIVEN_ENV_NAME — returns 1 (and sets LIVE_GUARD_REASON) when a marker exists but this deploy
# was not explicitly given the env the marker names; 0 otherwise (always 0 when there is no marker, so an unarmed
# box deploys exactly as before). deploy.sh calls it before it takes the lock or touches systemd.
live_deploy_guard() {
    local given="$1" name
    LIVE_GUARD_REASON=""
    if [ ! -e "$LIVE_MARKER" ] && [ ! -L "$LIVE_MARKER" ]; then return 0; fi
    if [ -z "$given" ]; then
        LIVE_GUARD_REASON="a marker exists at $LIVE_MARKER but ENV_NAME was not given (this deploy would default to DEV)"
        return 1
    fi
    if ! name=$(_arming_marker_name); then
        LIVE_GUARD_REASON="a marker exists at $LIVE_MARKER but it cannot be read as one line naming an env"
        return 1
    fi
    if [ "$name" != "$given" ]; then
        if [[ "$name" =~ ^[A-Za-z0-9_-]{1,32}$ ]]; then
            LIVE_GUARD_REASON="the marker $LIVE_MARKER names '$name' but this deploy is ENV_NAME='$given'"
        else
            LIVE_GUARD_REASON="the marker $LIVE_MARKER does not name this deploy's ENV_NAME='$given'"
        fi
        return 1
    fi
    return 0
}

# live_strip_guard ENV_FILE ENV_NAME DST UNIT... — returns 1 (and sets LIVE_GUARD_REASON) when an INSTALLED live unit
# carries --live, this deploy's decision is NOT armed, and the .env still runs the timers (FORWARD_ENABLED not
# explicitly off). That deploy would strip --live from a live book's L1/L2 while their timers keep firing: a marker
# that turned bad (a chmod), a marker removed with the .env still armed, or a jump straight from armed to the paper
# rehearsal. The documented disarm sets FORWARD_ENABLED=false first (every timer is then disabled), so it passes.
# With no --live installed (every unarmed box) this is a no-op.
live_strip_guard() {
    local env_file="$1" env_name="$2" dst="$3" u fwd live_units=""
    shift 3
    LIVE_GUARD_REASON=""
    for u in "$@"; do
        grep -qE '^ExecStart=.* --live$' "$dst/$u" 2>/dev/null && live_units="$live_units $u"
    done
    [ -z "$live_units" ] && return 0
    live_arming_check "$env_file" "$env_name"
    [ "$LIVE_ARMED" = "1" ] && return 0
    fwd=$(_arming_env_value "$env_file" FORWARD_ENABLED)
    case "$fwd" in ""|0|false|no|off) return 0 ;; esac
    LIVE_GUARD_REASON="the installed$live_units carry --live but this deploy would not render it ($LIVE_ARMING_REASON), while FORWARD_ENABLED=$fwd keeps the timers firing; to disarm, set FORWARD_ENABLED=false first (DEPLOYMENT.md, Disarm)"
    return 1
}
