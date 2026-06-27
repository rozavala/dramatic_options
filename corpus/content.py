"""Stage-0 corpus CONTENT layer — theme → corpus pulls (the assemble_corpus coords).

The "what to pull per theme" layer (``PREREG_THEME_GENERATION_STUB`` Stage 0; overlaps
``PREREG_UNIVERSE_CURATION`` §4), distinct from the "how to pull" adapters. Reads ``corpus_content.json``
(the per-theme map) + the loop config (for basket symbols) and produces:

- :func:`corpus_pulls` — the flat, typed pull specs (``source`` + ``params`` + ``theme`` + the cache
  ``key``) a future scheduled L0 assembler executes against the adapters;
- :func:`read_coords` — the de-duplicated ``(source, key)`` coords ``corpus.assemble.assemble_corpus``
  reads back.

The ``key`` is computed with each adapter's OWN cache-key logic, so a pull's read coord is exactly
where the adapter writes it (no drift). §2 (no prices/IV/momentum/sentiment) is the adapters' job,
enforced by the package import guard — this layer only ROUTES. INERT until the assembler/Stage-1
wire it; this module imports no market source and is not loaded by the trading loop.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from corpus import (
    bls_series,
    capital_raises,
    eia_series,
    etf_constituents,
    federal_awards,
    nrc_dockets,
)
from corpus.customer_concentration import SOURCE as CC_SOURCE

ALL_BASKET_SYMBOLS = "@all_basket_symbols"  # sentinel: the union of config.universe.themes baskets


def load_content(path: str | Path = "corpus_content.json") -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def all_basket_symbols(config: dict[str, Any]) -> list[str]:
    """Sorted union of every config.universe.themes basket symbol (the customer-concentration universe)."""
    themes = (config.get("universe", {}) or {}).get("themes", {}) or {}
    syms = {s.upper() for k, v in themes.items() if not k.startswith("_") for s in (v or [])}
    return sorted(syms)


def _dod_agencies(content: dict[str, Any]) -> list[dict[str, str]]:
    agency = ((content.get("universe", {}) or {}).get("federal_awards", {}) or {}).get(
        "agency", "Department of Defense")
    return [{"type": "awarding", "tier": "toptier", "name": agency}]


def corpus_pulls(content: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    """The flat pull spec list: one ``{source, theme, key, params}`` per corpus pull.

    ``key`` is each adapter's own cache key (so it matches where the adapter writes); ``params`` is
    what the future assembler hands the adapter to execute the pull. Deterministic ordering.
    """
    pulls: list[dict[str, Any]] = []
    uni = content.get("universe", {}) or {}

    # ── universe-wide pulls ──────────────────────────────────────────────────
    for form in uni.get("capital_raises", {}).get("forms", []):
        pulls.append({"source": capital_raises.SOURCE, "theme": None, "key": form,
                      "params": {"form": form}})

    cc = uni.get("customer_concentration", {}) or {}
    cc_syms = cc.get("symbols")
    symbols = all_basket_symbols(config) if cc_syms == ALL_BASKET_SYMBOLS else [s.upper() for s in (cc_syms or [])]
    for sym in symbols:
        pulls.append({"source": CC_SOURCE, "theme": None, "key": sym, "params": {"symbol": sym}})

    fa = uni.get("federal_awards")
    if fa:
        agencies = _dod_agencies(content)
        types = list(fa.get("award_type_codes", federal_awards.DEFAULT_AWARD_TYPE_CODES))
        pulls.append({"source": federal_awards.SOURCE, "theme": None,
                      "key": federal_awards.cache_key(agencies, types, None),
                      "params": {"agencies": agencies, "award_type_codes": types, "naics_codes": None}})

    # ── per-theme pulls ──────────────────────────────────────────────────────
    for theme, spec in (content.get("themes", {}) or {}).items():
        if theme.startswith("_") or not isinstance(spec, dict):
            continue
        for etf in spec.get("etfs", []):
            pulls.append({"source": etf_constituents.SOURCE, "theme": theme, "key": etf.upper(),
                          "params": {"etf": etf.upper()}})
        for series_id in spec.get("bls", []):
            pulls.append({"source": bls_series.SOURCE, "theme": theme, "key": series_id,
                          "params": {"series_id": series_id}})
        for e in spec.get("eia", []):
            pulls.append({"source": eia_series.SOURCE, "theme": theme,
                          "key": eia_series.cache_key(e["route"], e["value_field"], e.get("params")),
                          "params": {"route": e["route"], "value_field": e["value_field"],
                                     "params": e.get("params")}})
        if spec.get("nrc"):
            pulls.append({"source": nrc_dockets.SOURCE, "theme": theme, "key": nrc_dockets.KEY,
                          "params": {}})
        naics = spec.get("federal_awards_naics")
        if naics:
            agencies = _dod_agencies(content)
            types = list(federal_awards.DEFAULT_AWARD_TYPE_CODES)
            pulls.append({"source": federal_awards.SOURCE, "theme": theme,
                          "key": federal_awards.cache_key(agencies, types, naics),
                          "params": {"agencies": agencies, "award_type_codes": types,
                                     "naics_codes": naics}})
    return pulls


def read_coords(content: dict[str, Any], config: dict[str, Any]) -> list[tuple[str, str]]:
    """De-duplicated ``(source, key)`` coords for ``corpus.assemble.assemble_corpus``."""
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    for p in corpus_pulls(content, config):
        coord = (p["source"], p["key"])
        if coord not in seen:
            seen.add(coord)
            out.append(coord)
    return out


def restrict_to_theme(content: dict[str, Any], seed_theme: str) -> dict[str, Any]:
    """A copy of ``content`` with ``themes`` filtered to the single ``seed_theme`` — the seeded-generator
    corpus slice (PREREG_SEEDED_GENERATOR_DIAGNOSTIC). The human names the (quiet) sector; the generator
    then synthesizes only over that sector's pulls. Raises ``KeyError`` if the theme isn't routed (so a
    typo fails loud, not silently over the whole corpus)."""
    themes = content.get("themes", {}) or {}
    if seed_theme not in themes:
        routed = sorted(k for k in themes if not k.startswith("_"))
        raise KeyError(f"seed theme '{seed_theme}' is not routed in corpus_content.json (routed: {routed})")
    return {**content, "themes": {seed_theme: themes[seed_theme]}}
