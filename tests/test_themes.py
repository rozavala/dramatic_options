"""Theme loading + validation, and the shipped themes.json."""

from pathlib import Path

import pytest

from dramatic_options.themes import ThemeError, active_themes, load_themes

REPO = Path(__file__).resolve().parent.parent


def _write(tmp_path, obj):
    import json
    p = tmp_path / "themes.json"
    p.write_text(json.dumps(obj))
    return p


def test_load_valid(tmp_path):
    p = _write(tmp_path, {"themes": [
        {"name": "copper", "symbol": "fcx", "direction": "bullish", "thesis": "t"},
        {"name": "rollover", "symbol": "XYZ", "direction": "bearish", "active": False},
    ]})
    themes = load_themes(p)
    assert len(themes) == 2
    assert themes[0].symbol == "FCX"  # upper-cased
    assert themes[0].direction == "bullish"
    assert active_themes(themes) == [themes[0]]


def test_comment_entry_skipped(tmp_path):
    p = _write(tmp_path, {"themes": [
        {"_comment": "ignore me"},
        {"name": "a", "symbol": "A", "direction": "bullish"},
    ]})
    assert len(load_themes(p)) == 1


def test_bad_direction_raises(tmp_path):
    p = _write(tmp_path, {"themes": [{"name": "x", "symbol": "X", "direction": "up"}]})
    with pytest.raises(ThemeError, match="direction"):
        load_themes(p)


def test_missing_field_raises(tmp_path):
    p = _write(tmp_path, {"themes": [{"name": "x", "direction": "bullish"}]})
    with pytest.raises(ThemeError):
        load_themes(p)


def test_missing_file_raises(tmp_path):
    with pytest.raises(ThemeError, match="not found"):
        load_themes(tmp_path / "nope.json")


def test_shipped_themes_json_loads():
    themes = load_themes(REPO / "themes.json")
    assert any(t.symbol == "FCX" for t in themes)
    for t in themes:
        assert t.direction in ("bullish", "bearish")
