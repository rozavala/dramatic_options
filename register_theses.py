"""The operator's register theses, read for the council's context pack ONLY (PREREG_EVIDENCE_GROUNDING
amendment A2; PREREG_UNIVERSE_CURATION Rule 0 dated amendment, 2026-10-06).

Rule 0 keeps ``universe_register.json`` out of the trading loop: admission, routing and sizing read
``config.universe.themes`` alone. The amendment allows exactly one read: each theme's ``council_thesis``
(an operator-adopted, COUNCIL-FACING one-liner — the structural claim only) and its ``falsifier``, keyed by
theme (= basket) key, so a discovery candidate's pack can show the operator's admission hypothesis instead of
"none on file". The raw ``thesis`` is NEVER read: it is written for the operator and carries process notes
("under_narrated will very likely FAIL at the council"), price/drawdown and "convexity setup" language that a
thesis-only council must not see. Falsifiers lose their trailing process notes. Display only: nothing here
can admit, route, size, gate or veto. Fail-soft: an unreadable register returns ``{}`` and the pack falls back
to amendment A1's "(none on file)" line.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

log = logging.getLogger("register_theses")

DEFAULT_PATH = Path(__file__).resolve().parent / "universe_register.json"
MAX_CHARS = 900  # per field — the §7 pack-size discipline; a register thesis is a paragraph, not a document


def _clip(text) -> str:
    s = " ".join(str(text or "").split())
    return s if len(s) <= MAX_CHARS else s[: MAX_CHARS - 1].rstrip() + "…"


# Process notes appended to register falsifiers (provenance for the operator, not evidence for the council).
_FALSIFIER_META = (re.compile(r"\s*\((?:Draft-dated|AI-drafted)[^)]*\)\s*$"),
                   re.compile(r"^The card's pinned falsifier:\s*"),
                   re.compile(r"\s*[^.]*premise-currency[^.]*\.\s*"))


def clean_falsifier(text) -> str | None:
    s = _clip(text)
    for rx in _FALSIFIER_META:
        s = rx.sub(" ", s).strip()
    return s or None


def load(path: str | Path | None = None) -> dict[str, dict]:
    """``{theme_key: {"thesis", "falsifier", "added"}}`` for every register theme with an adopted
    ``council_thesis`` (``thesis`` here IS the council_thesis). ``{}`` on any error (logged) — never raises."""
    p = Path(path) if path is not None else DEFAULT_PATH
    try:
        themes = (json.loads(p.read_text()) or {}).get("themes") or {}
        out: dict[str, dict] = {}
        for key, t in themes.items():
            if str(key).startswith("_") or not isinstance(t, dict) or not t.get("council_thesis"):
                continue  # no council-facing thesis adopted → "(none on file)"; the raw thesis is never shown
            out[str(key)] = {"thesis": _clip(t.get("council_thesis")),
                             "falsifier": clean_falsifier(t.get("falsifier")),
                             "added": str(t.get("added") or "")[:10] or None}
        return out
    except Exception as e:  # noqa: BLE001 — display enrichment; absence falls back to "(none on file)"
        log.warning("register theses unavailable (pack falls back to none-on-file): %s", e)
        return {}
