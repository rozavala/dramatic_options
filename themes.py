"""Hand-seeded theme store (T1) — PREREG_THEMATIC_CONVEXITY §1, IMPLEMENTATION_PLAN T1.

T1 is hand-seeded: the operator lists conviction themes (theme + single-name expression +
direction + thesis) in ``themes.json``; the paper loop consumes the active ones. Auto-
discovery (sentinels) and council-driven theme selection arrive in T2/T3 — until then this
file *is* the input. Schema-validated on load (fail-closed: a malformed theme raises).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

VALID_DIRECTIONS = ("bullish", "bearish")


@dataclass(frozen=True)
class Theme:
    name: str
    symbol: str       # the cleanest single-name expression (underlying)
    direction: str    # "bullish" (tailwind → calls) | "bearish" (rollover → puts)
    thesis: str
    active: bool = True


class ThemeError(ValueError):
    """Raised when themes.json is malformed."""


def _parse_theme(raw: dict) -> Theme:
    try:
        name = str(raw["name"]).strip()
        symbol = str(raw["symbol"]).strip().upper()
        direction = str(raw["direction"]).strip().lower()
    except KeyError as e:
        raise ThemeError(f"theme missing required field {e}") from e
    if not name or not symbol:
        raise ThemeError(f"theme has empty name/symbol: {raw!r}")
    if direction not in VALID_DIRECTIONS:
        raise ThemeError(f"theme {name!r} direction must be one of {VALID_DIRECTIONS}, got {direction!r}")
    return Theme(
        name=name,
        symbol=symbol,
        direction=direction,
        thesis=str(raw.get("thesis", "")).strip(),
        active=bool(raw.get("active", True)),
    )


def load_themes(path: str | Path) -> list[Theme]:
    """Load + validate themes from a JSON file. Returns ALL themes (active and not)."""
    p = Path(path)
    if not p.exists():
        raise ThemeError(f"themes file not found: {p}")
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        raise ThemeError(f"themes file is not valid JSON: {e}") from e
    raw_themes = data.get("themes", [])
    if not isinstance(raw_themes, list):
        raise ThemeError("themes.json: 'themes' must be a list")
    return [_parse_theme(t) for t in raw_themes if not (isinstance(t, dict) and t.get("_comment"))]


def active_themes(themes: list[Theme]) -> list[Theme]:
    return [t for t in themes if t.active]
