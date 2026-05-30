#!/bin/bash
set -e
# =============================================================================
# dramatic_options — Worktree Sync (called by deploy.sh after a successful deploy)
#
# Keeps the Claude Code worktree (~/dramatic_options-claude) in sync with the
# latest main. Non-destructive: skips if there are uncommitted changes or an
# active Claude Code session.
#
# Adapted from real_options. The idle/parking branch here is "claude": when the
# worktree sits on it, we fast-forward to main; any other branch is treated as a
# feature branch and rebased onto main.
# =============================================================================

WORKTREE_DIR="$HOME/dramatic_options-claude"
MAIN_BRANCH="main"
IDLE_BRANCH="claude"

# --- Guard: worktree must exist (e.g. absent on PROD) ---
[ -d "$WORKTREE_DIR" ] || exit 0

echo "  🔄 Syncing Claude Code worktree..."
cd "$WORKTREE_DIR" || exit 0

git fetch origin "$MAIN_BRANCH" 2>/dev/null || true

BRANCH=$(git branch --show-current 2>/dev/null)
DIRTY=$(git status --porcelain 2>/dev/null | wc -l)

# --- Guard: uncommitted changes ---
if [ "$DIRTY" -gt 0 ]; then
    echo "  ⚠️  Worktree has $DIRTY uncommitted change(s) on '$BRANCH' — skipping sync"
    git status --short 2>/dev/null | sed 's/^/       /'
    echo "     Run manually: cd $WORKTREE_DIR && git stash && git rebase origin/$MAIN_BRANCH && git stash pop"
    exit 0
fi

# --- Guard: Claude Code actively running in this directory ---
if pgrep -f "claude.*$WORKTREE_DIR" > /dev/null 2>&1; then
    echo "  ⚠️  Claude Code appears to be running — skipping sync"
    echo "     Run manually when done: cd $WORKTREE_DIR && git fetch origin && git rebase origin/$MAIN_BRANCH"
    exit 0
fi

# --- Sync based on branch type ---
if [ "$BRANCH" = "$IDLE_BRANCH" ] || [ "$BRANCH" = "$MAIN_BRANCH" ]; then
    # Idle/parking: fast-forward to match main
    if git merge "origin/$MAIN_BRANCH" --ff-only 2>/dev/null; then
        echo "  ✅ Worktree '$BRANCH' fast-forwarded to latest $MAIN_BRANCH"
    else
        echo "  ⚠️  Fast-forward failed ('$BRANCH' has diverged). Manual merge needed."
        echo "     Run: cd $WORKTREE_DIR && git rebase origin/$MAIN_BRANCH"
    fi
else
    # Feature branch: rebase onto latest main
    if git rebase "origin/$MAIN_BRANCH" 2>/dev/null; then
        echo "  ✅ Worktree branch '$BRANCH' rebased onto latest $MAIN_BRANCH"
    else
        git rebase --abort 2>/dev/null || true
        echo "  ⚠️  Rebase of '$BRANCH' onto $MAIN_BRANCH has conflicts — aborted automatically"
        echo "     Resolve manually: cd $WORKTREE_DIR && git rebase origin/$MAIN_BRANCH"
    fi
fi
