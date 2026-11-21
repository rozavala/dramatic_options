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
#     /etc/dramatic-options/live-armed     one line: this box's ENV_NAME (e.g. PROD)
#
# live_arming_check sets LIVE_ARMED=1 only when BOTH hold:
#   1. the marker is a regular file (not a symlink), owned by root, not group- or other-writable,
#      readable, and its content is exactly the deploy's ENV_NAME;
#   2. the .env already says armed: PAPER=false, LIVE_TRADING_ENABLED=true and FORWARD_ENABLED=true, each
#      assigned without a conflicting second value.
# Anything else, including any read that fails, is LIVE_ARMED=0 (fail-closed). A marker alone renders
# nothing; the flags alone render nothing. Nothing in this repo writes the marker.
#
# A rendered `--live` is still only the third key: config_loader.live_allowed re-reads the two .env flags
# on every run, and DRY_RUN=true still keeps AlpacaLiveBroker from transmitting.
#
# Outputs (globals): LIVE_ARMED (1|0), LIVE_ARMING_REASON (one line; flag values and names only, never a
# key value), LIVE_ARMING_LOUD (1 when the state is ambiguous or refused and the caller must say so loudly).
# =============================================================================

# Constants, not env-overridable: a caller's environment must not be able to move the marker.
LIVE_MARKER="/etc/dramatic-options/live-armed"
LIVE_MARKER_OWNER_UID=0

# The value of KEY in FILE, lowercased and unquoted: grep, never `source` (the .env must never execute).
# Prints "" when the key is absent, or "<conflict>" when the file assigns it more than one distinct value
# (dotenv and systemd both take the last one; arming refuses to guess).
_arming_env_value() {
    local file="$1" key="$2"
    local -a vals=()
    mapfile -t vals < <(grep -E "^[[:space:]]*${key}[[:space:]]*=" "$file" 2>/dev/null \
        | cut -d= -f2- | tr -d "\"' \t\r" | tr '[:upper:]' '[:lower:]' | sort -u)
    case "${#vals[@]}" in
        0) printf '' ;;
        1) printf '%s' "${vals[0]}" ;;
        *) printf '<conflict>' ;;
    esac
}

# Why the marker does not arm this env ("" when it is valid). Never prints the marker's content unless it is
# a plain env-name token.
_arming_marker_problem() {
    local env_name="$1" st owner mode content
    if [ -L "$LIVE_MARKER" ]; then echo "the marker $LIVE_MARKER is a symlink"; return; fi
    if [ ! -e "$LIVE_MARKER" ]; then echo "absent"; return; fi
    if [ ! -f "$LIVE_MARKER" ]; then echo "the marker $LIVE_MARKER is not a regular file"; return; fi
    if [ ! -r "$LIVE_MARKER" ]; then echo "the marker $LIVE_MARKER is unreadable"; return; fi
    st=$(stat -c '%u %a' "$LIVE_MARKER" 2>/dev/null) || { echo "the marker $LIVE_MARKER could not be stat'ed"; return; }
    owner=${st% *}; mode=${st#* }
    if [ "$owner" != "$LIVE_MARKER_OWNER_UID" ]; then
        echo "the marker $LIVE_MARKER is owned by uid $owner, not uid $LIVE_MARKER_OWNER_UID (create it with sudo)"; return
    fi
    case "$mode" in *[!0-7]*|"") echo "the marker $LIVE_MARKER has an unreadable mode '$mode'"; return ;; esac
    if (( 8#$mode & 8#022 )); then echo "the marker $LIVE_MARKER is group- or other-writable (mode $mode)"; return; fi
    content=$(tr -d ' \t\r\n' < "$LIVE_MARKER" 2>/dev/null) || { echo "the marker $LIVE_MARKER is unreadable"; return; }
    if [ -z "$env_name" ]; then echo "ENV_NAME is unset, so the marker cannot match it"; return; fi
    if [ "$content" != "$env_name" ]; then
        if [[ "$content" =~ ^[A-Za-z0-9_-]{1,32}$ ]]; then
            echo "the marker $LIVE_MARKER names '$content', not this env '$env_name'"
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
    if [ -z "$marker" ] && [ -z "$flags" ]; then
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
