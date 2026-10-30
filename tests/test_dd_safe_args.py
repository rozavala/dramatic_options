"""#369: ``dd.safe(fn, *args, **kwargs)`` only guards ``fn``'s own call. An argument that is itself a call is
evaluated BEFORE ``safe`` runs, so its exception escapes the guard and takes the whole page down instead of one
panel (#362's ``collect_run_ids`` had this shape). Every ``safe`` call must pass names / constants / lambdas, never
a call result: wrap such work in a lambda (``dd.safe(lambda: f(g(x)))``)."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_SKIP = {"venv", ".venv", "node_modules", ".git", ".claude"}   # .claude/worktrees may hold other branches' code


def _is_safe_call(node: ast.Call) -> bool:
    f = node.func
    if isinstance(f, ast.Attribute):
        return f.attr == "safe" and isinstance(f.value, ast.Name) and f.value.id in {"dd", "dashboard_data"}
    return isinstance(f, ast.Name) and f.id == "safe"


def _pre_evaluated_args() -> list[str]:
    hits = []
    for p in sorted(ROOT.rglob("*.py")):
        if _SKIP & set(p.relative_to(ROOT).parts):
            continue
        for n in ast.walk(ast.parse(p.read_text(), filename=str(p))):
            if isinstance(n, ast.Call) and _is_safe_call(n):
                for a in [*n.args[1:], *(k.value for k in n.keywords)]:
                    if isinstance(a, ast.Call):
                        hits.append(f"{p.relative_to(ROOT)}:{n.lineno} {ast.unparse(a)[:80]}")
    return hits


def test_no_dd_safe_argument_is_a_call_result():
    assert _pre_evaluated_args() == [], "dd.safe argument evaluated outside the guard — wrap in a lambda"


def test_the_scan_catches_the_shape(tmp_path, monkeypatch):
    # the guard must actually see the pattern, or the test above passes vacuously
    bad = ast.parse("dd.safe(dd.positions_panel, conn, time_stop_dte=int(cfg['x']))").body[0].value
    good = ast.parse("dd.safe(lambda: dd.positions_panel(conn, time_stop_dte=int(cfg['x'])))").body[0].value
    assert _is_safe_call(bad) and _is_safe_call(good)
    assert any(isinstance(k.value, ast.Call) for k in bad.keywords)
    assert not any(isinstance(a, ast.Call) for a in good.args[1:])
