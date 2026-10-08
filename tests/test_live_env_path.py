"""scripts/_live_env.py — the probes must find the live checkout's .env from any worktree."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_p = Path(__file__).resolve().parent.parent / "scripts" / "_live_env.py"
_spec = importlib.util.spec_from_file_location("_live_env", _p)
live_env = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(live_env)


def test_plain_checkout_uses_its_own_env(tmp_path):
    (tmp_path / ".git").mkdir()
    assert live_env.live_env_path(tmp_path) == tmp_path / ".env"


def test_linked_worktree_resolves_to_main_checkout(tmp_path):
    main, wt = tmp_path / "main", tmp_path / "wt"
    (main / ".git" / "worktrees" / "wt").mkdir(parents=True)
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {main}/.git/worktrees/wt\n")
    assert live_env.live_env_path(wt) == main / ".env"


def test_override_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("DRAMATIC_OPTIONS_ENV_FILE", str(tmp_path / "x.env"))
    assert live_env.live_env_path(tmp_path) == tmp_path / "x.env"
