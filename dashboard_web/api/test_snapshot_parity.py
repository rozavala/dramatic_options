"""Parity guard (H1): the web API's PANEL_KEYS must match dashboard.load_all's panel set.

If the live Streamlit shell gains / renames / drops a panel, snapshot.build_snapshot silently diverges and
the React UI quietly loses (or mis-keys) data. This test fails the moment they drift.

It reads load_all's returned dict literal via AST — NOT by importing dashboard.py, which pulls in streamlit
(absent in the plain CI `test` job). snapshot.py is streamlit-free, so importing it here is safe in both jobs.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

_API = Path(__file__).resolve().parent
_REPO_ROOT = _API.parents[1]
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

import snapshot  # noqa: E402 — after the sys.path insert above


def _load_all_panel_keys() -> set[str]:
    """The string keys of the (non-_fatal) dict literal returned by dashboard.load_all, via AST."""
    tree = ast.parse((_REPO_ROOT / "dashboard.py").read_text())
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "load_all")
    dicts = [n for n in ast.walk(fn) if isinstance(n, ast.Dict)]
    # the panel dict is the big one; the early `{"_fatal": ...}` return has a single key.
    panel = max(dicts, key=lambda d: len(d.keys))
    return {k.value for k in panel.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}


def test_panel_keys_match_load_all() -> None:
    api_keys = set(snapshot.PANEL_KEYS)
    load_all_keys = _load_all_panel_keys()
    assert api_keys == load_all_keys, (
        f"PANEL_KEYS drift vs dashboard.load_all — "
        f"only in API: {sorted(api_keys - load_all_keys)}; only in load_all: {sorted(load_all_keys - api_keys)}"
    )


def test_panel_keys_are_unique() -> None:
    assert len(snapshot.PANEL_KEYS) == len(set(snapshot.PANEL_KEYS))
