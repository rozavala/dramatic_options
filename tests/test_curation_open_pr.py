"""The §11 additive-only invariant + the minimal-diff invariant for the curation executor's register
merge (scripts/curation_open_pr)."""
import json
from pathlib import Path

import pytest

from scripts.curation_open_pr import insert_theme_text, merge_theme


def test_merge_theme_additive_and_pure():
    reg = {"_comment": "x", "themes": {"a": {"thesis": "t"}}}
    out = merge_theme(reg, "b", {"thesis": "u"})
    assert set(out["themes"]) == {"a", "b"}
    assert out["themes"]["a"] == {"thesis": "t"}        # existing preserved
    assert out["themes"]["b"] == {"thesis": "u"}        # new appended
    assert reg["themes"] == {"a": {"thesis": "t"}}      # input not mutated


def test_merge_theme_refuses_clobber():
    reg = {"themes": {"a": {"thesis": "t"}}}
    with pytest.raises(ValueError, match="already exists"):   # §11 additive-only
        merge_theme(reg, "a", {"thesis": "new"})


def test_merge_theme_requires_themes_object():
    with pytest.raises(ValueError, match="no 'themes'"):
        merge_theme({}, "a", {"thesis": "t"})


# ── the minimal-diff invariant (insert_theme_text) ───────────────────────────────────────────────
# The executor's safety case (keyless, inert, eyeball-the-diff) depends on a MINIMAL diff: add ONLY
# the new theme, leave everything else — notably the hand-aligned compact windows.admitted one-liners
# — byte-for-byte unchanged. A full json.dumps re-serialize reformats the whole file; these pin it does not.

# a register with a COMPACT (one-line) windows.admitted entry — the format json.dumps(indent=2) explodes.
SYNTH = (
    '{\n'
    '  "_comment": "x",\n'
    '  "themes": {\n'
    '    "alpha": {\n'
    '      "provenance": "operator",\n'
    '      "thesis": "ta",\n'
    '      "cluster_default": "alpha"\n'
    '    },\n'
    '    "beta": {\n'
    '      "provenance": "operator",\n'
    '      "thesis": "tb",\n'
    '      "cluster_default": "beta"\n'
    '    }\n'
    '  },\n'
    '  "windows": {\n'
    '    "1": {"admitted": {"XYZ": {"basket": "alpha", "per_contract_usd": 102, "tag": "rule"}}}\n'
    '  }\n'
    '}\n'
)

ENTRY = {
    "provenance": "operator",
    "added": "2026-06-30 (test)",
    "thesis": "tc",
    "falsifier": "fc",
    "sources": ["SRC_C"],
    "cluster_default": "gamma",
}


def test_insert_theme_deep_equals_intended():
    out = insert_theme_text(SYNTH, "gamma", ENTRY)
    base = json.loads(SYNTH)
    assert json.loads(out) == {**base, "themes": {**base["themes"], "gamma": ENTRY}}


def test_insert_theme_preserves_everything_after_themes_byte_for_byte():
    out = insert_theme_text(SYNTH, "gamma", ENTRY)
    tail = SYNTH[SYNTH.index('  "windows"'):]   # the compact one-liner + windows block
    assert out.endswith(tail)
    assert '"XYZ": {"basket": "alpha", "per_contract_usd": 102, "tag": "rule"}' in out  # one-liner survived


def test_insert_theme_indentation_matches_themes_level():
    out = insert_theme_text(SYNTH, "gamma", ENTRY)
    assert '    "gamma": {' in out                  # key at 4 spaces (themes level)
    assert '      "provenance": "operator"' in out  # fields at 6
    assert '        "SRC_C"' in out                 # array items at 8


def test_insert_theme_raises_on_missing_anchor():
    with pytest.raises(ValueError, match="anchor not found"):
        insert_theme_text('{\n  "themes": {}\n}\n', "g", ENTRY)


def test_live_register_accepts_the_splice():
    """The real universe_register.json must accept the splice (anchor present, deep-equal holds,
    everything past themes preserved) — so the next register run produces a minimal diff."""
    base = (Path(__file__).resolve().parents[1] / "universe_register.json").read_text()
    out = insert_theme_text(base, "__probe__", ENTRY)
    b = json.loads(base)
    assert json.loads(out) == {**b, "themes": {**b["themes"], "__probe__": ENTRY}}
    assert out.endswith(base[base.index('  "windows"'):])


# ── adversarial robustness (the gate must be robust to ARBITRARY future theme names/values, not just
#    the clean cases) — string-manipulation-of-structured-data risk, neutralized by json.dumps escaping
#    + a structural anchor + the caller's PARSED-object deep-equal. ──────────────────────────────────
def test_insert_theme_robust_to_structural_text_in_values():
    """A thesis/falsifier/source containing JSON-structural text — braces, quotes, and the LITERAL
    themes-close anchor pattern with real newlines — must not shift the splice. json.dumps escapes it
    inline (string newlines → \\n, never a real indent-2 `},\\n  "windows"`), so the structural anchor is
    untouched, the parsed deep-equal holds, and the compact windows block survives byte-for-byte."""
    adversarial = {
        "provenance": "operator",
        "thesis": 'braces { } and "quotes" and the literal },\n  "windows" anchor pattern inline',
        "falsifier": 'more {nested-looking} text, "windows", and a },\n  "windows" lookalike',
        "sources": ['a source with } and "windows" and a real\nnewline inside'],
        "cluster_default": "x",
    }
    out = insert_theme_text(SYNTH, "weird_theme", adversarial)
    base = json.loads(SYNTH)
    assert json.loads(out) == {**base, "themes": {**base["themes"], "weird_theme": adversarial}}
    assert out.endswith(SYNTH[SYNTH.index('  "windows"'):])   # adversarial value did NOT shift the anchor


def test_insert_theme_robust_to_structural_chars_in_key():
    """Defensive — keys are snake_case slugs in practice, but the gate must be robust to arbitrary future
    names: a key containing a brace/quote is escaped by json.dumps → valid JSON → deep-equal holds."""
    out = insert_theme_text(SYNTH, 'odd"}key', {"thesis": "t"})
    base = json.loads(SYNTH)
    assert json.loads(out) == {**base, "themes": {**base["themes"], 'odd"}key': {"thesis": "t"}}}
    assert out.endswith(SYNTH[SYNTH.index('  "windows"'):])
