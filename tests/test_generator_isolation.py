"""MERGE-BLOCKER: the generator's write isolation (``PREREG_THEME_GENERATOR §6.4``).

``records/`` co-houses the BLIND artifacts the 7/10 close-out review consumes
(``gate_baserate_surfaced.csv``, the dated ``*_closeout_*`` / window-screen reads), so the
generator writing anywhere but ``records/generator/`` would corrupt that blind. This is the
``records/generator/``-only invariant from §6.4 / §9, asserted statically over the package source
in the never-broker merge-blocker style (``tests/test_fixed_basket.py:144`` —
``test_fixed_basket_never_touches_the_broker``).

Mechanism: the generator routes EVERY write through :data:`generator.GENERATOR_RECORDS_DIR`. This
test asserts (a) that constant points under ``records/generator/``, and (b) no generator module
hardcodes any *other* ``records/...`` path — in particular none of the named blind artifacts, nor
a bare ``records/`` write, nor the config / register the curation rule owns. A new module that
writes a blind artifact would have to name that path as a string literal, which this catches.
"""

from __future__ import annotations

import ast
import pathlib

import generator

_PKG = pathlib.Path(generator.__file__).resolve().parent

# Blind artifacts (the 7/10 close-out's substrate) + the config/register the curation Rule owns —
# the generator must NEVER name any of these as a write target. A literal mentioning one is the
# tell the merge-blocker exists to catch.
_FORBIDDEN_PATH_FRAGMENTS = (
    "gate_baserate_surfaced",          # the pinned blind base-rate CSV (§6.4)
    "_closeout_",                      # the dated 7/10 close-out reads
    "window1_feasibility_screen",      # window-screen blind reads
    "window1_longlist",
    "retightened_rescore",
    "config.json",                     # config-over-code: never written by the generator
    "universe_register.json",          # the curation register (operator|generated provenance)
    "corpus_content.json",
)


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """ids of the Constant nodes that are docstrings (module/class/func first-statement strings).

    Docstrings are PROSE (these very files name the blind artifacts to document the invariant), so
    they must be excluded — only operative path literals are write targets."""
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                out.add(id(body[0].value))
    return out


def _path_like_literals(src: str) -> list[str]:
    """Operative, PATH-SHAPED string literals (not docstrings, not prose).

    A write target is a filesystem path: whitespace-free and either containing ``/`` or ending in a
    data-file suffix. Prose that merely *mentions* an artifact (in a docstring or a message string)
    contains spaces, so it is never a path candidate — this keeps the guard about real write paths.
    """
    tree = ast.parse(src)
    skip = _docstring_nodes(tree)
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
            v = node.value
            if v and not any(c.isspace() for c in v) and (
                "/" in v or v.endswith((".csv", ".json", ".md", ".txt"))
            ):
                out.append(v)
    return out


def test_generator_records_dir_is_under_records_generator():
    # The single declared write root resolves under records/generator/ — nothing else is sanctioned.
    d = generator.GENERATOR_RECORDS_DIR
    assert d.replace("\\", "/").rstrip("/") == "records/generator", d
    assert d.startswith("records/generator")


def test_generator_writes_only_under_records_generator():
    # No generator module may name a blind `records/*` artifact or the config/register as a path.
    offenders: list[str] = []
    for f in sorted(_PKG.glob("*.py")):
        for lit in _path_like_literals(f.read_text()):
            low = lit.replace("\\", "/")
            if any(frag in low for frag in _FORBIDDEN_PATH_FRAGMENTS):
                offenders.append(f"{f.name}: {lit!r}")
            # A bare `records/...` literal is only allowed if it is the generator subtree itself.
            elif "records/" in low and "records/generator" not in low:
                offenders.append(f"{f.name}: {lit!r} (records/ write outside records/generator/)")
    assert not offenders, (
        "PREREG_THEME_GENERATOR §6.4 — the generator may write ONLY under records/generator/; "
        f"offending path literal(s): {offenders}"
    )
