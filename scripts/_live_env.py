"""Locate and load the LIVE checkout's .env for out-of-band probe scripts.

The probes run from any worktree but need the live keys, which are never committed and exist
only in the main checkout. Resolution, first hit wins:
  1. $DRAMATIC_OPTIONS_ENV_FILE
  2. the main checkout's .env (a linked worktree's `.git` file points back at it)
  3. this checkout's own .env
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def main_checkout(root: Path) -> Path:
    git = root / ".git"
    if git.is_file():  # linked worktree: "gitdir: <main>/.git/worktrees/<name>"
        text = git.read_text().strip()
        if text.startswith("gitdir:"):
            gitdir = Path(text.split(":", 1)[1].strip())
            if not gitdir.is_absolute():
                gitdir = (root / gitdir).resolve()
            if gitdir.parent.name == "worktrees":
                return gitdir.parent.parent.parent
    return root


def live_env_path(root: Path | None = None) -> Path:
    override = os.environ.get("DRAMATIC_OPTIONS_ENV_FILE")
    if override:
        return Path(override)
    root = root or Path(__file__).resolve().parents[1]
    return main_checkout(root) / ".env"


def load_live_env() -> None:
    load_dotenv(live_env_path())
