"""The §11 additive-only invariant for the curation executor's register merge (scripts/curation_open_pr)."""
import pytest

from scripts.curation_open_pr import merge_theme


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
