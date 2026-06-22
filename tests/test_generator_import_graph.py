"""Generator-specific CI import-graph invariant (``PREREG_THEME_GENERATOR §6.4 / §9``).

The hard seam is directional: **the generator imports the council router** (``build_router`` /
``FakeRouter`` — its synthesis LLM call), but **the live loop must NEVER import the generator.**
A live-loop module reaching into ``generator`` would couple the trading/forward path to the
INERT, fixture-built, never-backtested theme-generation layer — exactly what §1's hard seam and
§6's build posture forbid. This is the net-new generator analogue of the dashboard keyless
import-graph guard (``tests/test_dashboard_data.py:615``).

Two assertions:
  1. No live-loop module imports ``generator`` (the named live-loop set from §6, PLUS a broad
     whole-repo sweep so a future live module can't quietly add the edge).
  2. The generator DOES import the council router (the sanctioned, one-directional dependency) —
     a positive control that proves assertion 1 isn't vacuously green from a severed graph.
"""

from __future__ import annotations

import ast
import pathlib

import generator

_ROOT = pathlib.Path(generator.__file__).resolve().parent.parent
_GEN_PKG = pathlib.Path(generator.__file__).resolve().parent

# The live-loop / forward-path modules named in §6 (orchestrator, council/*, gate, structure,
# discovery, shadow, fixed_basket) — checked EXPLICITLY so a regression names the offender clearly.
_LIVE_LOOP_MODULES = (
    "orchestrator.py", "monitor.py", "paper_loop.py",
    "convexity_gate.py", "structure.py", "convexity_sizing.py",
    "discovery.py", "sentinels.py", "sentinel_scoring.py",
    "shadow_book.py", "fixed_basket.py", "shares_basket.py",
    "broker.py", "risk.py", "clusters.py", "gate_dualread.py",
    "council/agents.py", "council/debate.py", "council/council.py",
    "council/wiring.py", "council/context.py", "council/proposal.py",
    "council/scoring.py", "council/sentinel.py", "council/router.py",
    "council/filters.py",
)


def _imported_top_modules(path: pathlib.Path) -> set[str]:
    """Top-level module names imported by ``path`` (``import a.b`` / ``from a.b import c`` → ``a``)."""
    mods: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            mods.add(node.module.split(".")[0])
    return mods


def _is_generator_file(path: pathlib.Path) -> bool:
    return _GEN_PKG in path.resolve().parents or path.resolve() == _GEN_PKG


def test_live_loop_named_modules_do_not_import_generator():
    offenders = []
    for rel in _LIVE_LOOP_MODULES:
        p = _ROOT / rel
        if not p.exists():
            continue
        if "generator" in _imported_top_modules(p):
            offenders.append(rel)
    assert not offenders, (
        "PREREG_THEME_GENERATOR §6.4 — the live loop must NEVER import generator; "
        f"offending module(s): {offenders}"
    )


def test_no_repo_module_outside_generator_imports_generator():
    # Broad sweep: every .py under the repo root (excluding the generator package itself and the
    # test suite) — catches a future live module adding the forbidden edge that the named list misses.
    offenders = []
    for p in sorted(_ROOT.rglob("*.py")):
        rp = p.resolve()
        parts = set(rp.parts)
        if _is_generator_file(p) or "tests" in parts or "shelf" in parts:
            continue
        if ".venv" in parts or "venv" in parts or "site-packages" in parts:
            continue
        if "generator" in _imported_top_modules(p):
            offenders.append(str(rp.relative_to(_ROOT)))
    assert not offenders, (
        "PREREG_THEME_GENERATOR §6.4 — no module outside generator/ may import generator; "
        f"offending module(s): {offenders}"
    )


def test_generator_imports_the_council_router():
    # Positive control: the sanctioned one-way dependency exists, so the guard above is not
    # vacuously green from a disconnected graph (§2 reuses the council router + FakeRouter).
    importers = {
        p.name for p in sorted(_GEN_PKG.glob("*.py"))
        if "council" in _imported_top_modules(p)
    }
    assert importers, "generator must import the council router (build_router / FakeRouter) — §2"
