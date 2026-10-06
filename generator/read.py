"""P0 — the generator's corpus reader (no LLM; ``PREREG_THEME_GENERATOR §5/§6``, fixture-exempt).

A thin, deterministic reader returning the Stage-0 point-in-time corpus union that the Stage-1
synthesis reads. It composes the existing Stage-0 pieces with NO new fetch logic and NO LLM:

    ``corpus.content.read_coords(content, config)``  →  the de-duplicated ``(source, key)`` coords
    ``corpus.assemble.assemble_corpus(cache, as_of, coords)``  →  the as-of union grouped by source

**§5 blinding boundary:** this is Phase 0 — corpus-read only, NO generator LLM — so it emits no
thesis count and no ``dropped_*`` count and **cannot un-blind the §10 yield band** (it is the
explicit Phase-0 exemption). Fail-soft is inherited from ``assemble_corpus`` (a missing/short
coord yields ``[]``, never raises).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from corpus.assemble import assemble_corpus
from corpus.content import read_coords


def read_corpus(
    cache: Any,
    as_of: datetime,
    content: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """The as-of Stage-0 corpus union the synthesis reads, grouped by source.

    ``content`` is the ``corpus_content.json`` map; ``config`` is the loop config (for basket
    symbols). Every requested source appears as a key (possibly ``[]``), so the caller can tell
    "source had nothing as-of T" from "source not requested" (``assemble_corpus`` contract).
    """
    coords = read_coords(content, config)
    # tag_key=True: carry each record's cache COORD key (form / symbol / series_id / hash /
    # "power_reactors") so the synthesis render can show the LLM a coord the §3 verifier resolves.
    # Without it the model cites a record-body id (accession / PIID) that mis-resolves for 5 of 7
    # sources (only bls/etf coincide), deflating the §3 grounding gate (the citation-key contract gap).
    return assemble_corpus(cache, as_of, coords, tag_key=True)


def iter_records(corpus: dict[str, list[dict[str, Any]]]) -> list[tuple[str, dict[str, Any]]]:
    """Flatten the grouped union into ``(source, record)`` pairs in a deterministic order.

    Convenience for the entity-resolution + (future P2) citation-trace layers, which reason over
    individual ``(source, key, ts)``-addressable records rather than the per-source grouping.
    """
    out: list[tuple[str, dict[str, Any]]] = []
    for source in sorted(corpus):
        for rec in corpus[source]:
            out.append((source, rec))
    return out
