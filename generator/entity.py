"""P0 — citation-anchored entity RESOLUTION (no LLM; ``PREREG_THEME_GENERATOR §3``, fixture-exempt).

The entity-level mechanism of the §3 citation gate, the LOAD-BEARING defense against the LLM's
narrated-corpus recall bias. **This module builds RESOLUTION only** — the full §3 verifier (the
DROP gate + the split ``dropped_entity_unresolved`` / ``dropped_fact_untraced`` counters) is P2,
held for the operator red-team and explicitly NOT built here (§6 build phases).

**Citation-anchored (the P1 round-2 fix).** A claim's ``named_entities[]`` resolve against **the
records the claim CITES**, not against an external map. Each entity resolves iff it appears — by
**cik / symbol / name** — in at least one cited corpus record. ``EdgarClient.ticker_to_cik`` is
**OPTIONAL secondary confirmation, never the primary gate** (§3): its map is keyed by *current US
ticker* (``data/filings.py:98-108``, title discarded), so a CIK-mandatory gate would false-drop
renamed / de-SPAC'd / foreign-listed issuers — the quiet end of the distribution (the NXE worked
example: ``us_listed=False, "tsx"`` in the cited URNM record, named explicitly yet US-CIK-absent).
US-optionability is a downstream curation-Rule-1 concern, never this gate's job.

**Symbol-keyed sources:** for ``customer_concentration`` (record carries ``cik`` only) the symbol
identity lives in the citation COORD's ``key`` (the cache is keyed by symbol). So resolution checks
the coord ``key`` as an identity token too — otherwise a perfectly-cited concentration disclosure
would be unresolvable. §11 is honored: a coord ``(source, key, ts)`` may map to MULTIPLE records
(``ts`` not unique within a key), so we resolve a coord to the SET of records sharing that exact
``ts`` and test the entity against the union.

**Fail-soft (§3 / required test):** a citation naming a source/key with no cached coverage resolves
to ``[]`` records — it simply contributes no identity tokens (it never raises into assembly). An
entity present in NO cited record is **unresolved** (genuine confabulation in P2's DROP terms).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

# Record fields that can carry §3 entity identity (cik / symbol / name), across the entity-bearing
# adapters: capital_raises {cik, company}, customer_concentration {cik}, etf_constituents
# {symbol, name}, federal_awards {recipient} (free-text). Entity-free macro sources (bls/eia/nrc)
# contribute no identity tokens, by design.
_IDENTITY_FIELDS = ("cik", "symbol", "ticker", "name", "company", "recipient")


def _norm(s: Any) -> str:
    """Normalize an identity token for comparison: trimmed, collapsed-ws, lower-cased."""
    return " ".join(str(s or "").split()).strip().lower()


def _norm_cik(s: Any) -> str:
    """CIKs compare zero-stripped (the cache may store ``"0000899629"``; a claim may cite ``899629``)."""
    t = _norm(s)
    return t.lstrip("0") or ("0" if t else "")


@dataclass(frozen=True)
class Citation:
    """A corpus coord a claim draws from: ``(source, key, ts)`` (``ts`` optional → whole key)."""

    source: str
    key: str
    ts: str | None = None


def _coord_records(cache: Any, cit: Citation) -> list[dict[str, Any]]:
    """The cited record(s) for one coord. Fail-soft: a missing/uncovered coord → ``[]`` (never raises).

    §11: ``ts`` is not unique within a key, so when a ``ts`` is given we return ALL records whose
    ``ts`` matches exactly (same-day collisions, e.g. multiple 424B5s). With no ``ts`` the whole
    key's coverage is the cited slice.
    """
    end = _safe_dt(cit.ts)
    try:
        # read_between is start-exclusive; pass start=None for an open lower bound, then (when a ts
        # was cited) keep only the exact-ts collision set — never the whole forward slice.
        recs = cache.read_between(cit.source, cit.key, None, end) if end else \
            cache.read_between(cit.source, cit.key, None, _FAR_FUTURE)
    except Exception:  # noqa: BLE001 — a corpus-source hiccup contributes no tokens, never breaks
        return []
    if cit.ts is not None:
        want = _norm(cit.ts)
        recs = [r for r in recs if _norm(r.get("ts")) == want]
    return recs


def _identity_tokens(records: list[dict[str, Any]], coord_key: str) -> tuple[set[str], set[str]]:
    """(name/symbol tokens, cik tokens) drawn from a coord's records + its key.

    The coord ``key`` is included because symbol-keyed sources (customer_concentration) carry the
    symbol identity in the cache key, not the record body. CIKs are tracked separately so they
    compare zero-stripped.
    """
    names: set[str] = set()
    ciks: set[str] = set()
    if coord_key:
        names.add(_norm(coord_key))  # the key itself (a symbol for symbol-keyed sources)
    for r in records:
        for f in _IDENTITY_FIELDS:
            v = r.get(f)
            if v in (None, ""):
                continue
            if f == "cik":
                ciks.add(_norm_cik(v))
            else:
                names.add(_norm(v))
    return names, ciks


def _entity_tokens(entity: dict[str, Any]) -> tuple[set[str], str | None]:
    """(name/ticker tokens to match, optional cik) from a §3 ``named_entities[]`` object."""
    toks: set[str] = set()
    for f in ("canonical", "ticker", "name"):
        v = entity.get(f)
        if v not in (None, ""):
            toks.add(_norm(v))
    for a in entity.get("aliases", []) or []:
        if a not in (None, ""):
            toks.add(_norm(a))
    cik = _norm_cik(entity["cik"]) if entity.get("cik") not in (None, "") else None
    return {t for t in toks if t}, cik


def resolve_entity(
    entity: dict[str, Any],
    citations: list[Citation],
    cache: Any,
    *,
    edgar: Any | None = None,
) -> bool:
    """True iff ``entity`` appears — by cik / symbol / name — in at least one CITED record.

    ``edgar`` is OPTIONAL secondary confirmation only (§3): if (and only if) the entity carries a
    *ticker* and resolved nowhere in the cited records, a ``ticker_to_cik`` hit on a cited record's
    CIK is accepted — this NEVER drops a citation-resolved entity and NEVER substitutes for the
    citation anchor (a ticker with no cited record stays unresolved; that is the gaming channel §3
    closes). Pass ``edgar=None`` (the default + every test) to skip it entirely.
    """
    ent_names, ent_cik = _entity_tokens(entity)

    cited_names: set[str] = set()
    cited_ciks: set[str] = set()
    for cit in citations:
        names, ciks = _identity_tokens(_coord_records(cache, cit), cit.key)
        cited_names |= names
        cited_ciks |= ciks

    # Primary, citation-anchored: name/symbol/ticker token OR cik appears in a cited record.
    if ent_names & cited_names:
        return True
    if ent_cik and ent_cik in cited_ciks:
        return True

    # Secondary (OPTIONAL): a ticker→CIK hit that lands on a CITED record's CIK. Still anchored to
    # the citation (the CIK must be one the claim cited); only the ticker→CIK map is the assist.
    ticker = _norm(entity.get("ticker"))
    if edgar is not None and ticker and cited_ciks:
        try:
            cik = edgar.ticker_to_cik(ticker.upper())
        except Exception:  # noqa: BLE001 — the secondary assist must never raise
            cik = None
        if cik and _norm_cik(cik) in cited_ciks:
            return True

    return False


def resolve_named_entities(
    named_entities: list[dict[str, Any]],
    citations: list[Citation],
    cache: Any,
    *,
    edgar: Any | None = None,
) -> dict[str, bool]:
    """Resolution map ``canonical → bool`` for a claim's ``named_entities`` (P0 mechanism, no DROP).

    P2 turns the ``False`` entries into ``dropped_entity_unresolved`` and DROPs the claim; P0 only
    exposes the resolution so the smoke tests + the future verifier can build on it.
    """
    return {
        str(e.get("canonical") or e.get("ticker") or e.get("name") or _norm(e)):
            resolve_entity(e, citations, cache, edgar=edgar)
        for e in named_entities
    }


def as_citations(raw: list[Any]) -> list[Citation]:
    """Coerce the generator's emitted ``citations`` (tuples or dicts) into :class:`Citation`.

    Accepts ``(source, key)`` / ``(source, key, ts)`` tuples and ``{"source","key","ts"}`` dicts;
    anything malformed is skipped (fail-soft — a junk citation simply anchors nothing)."""
    out: list[Citation] = []
    for c in raw or []:
        if isinstance(c, Citation):
            out.append(c)
        elif isinstance(c, dict) and c.get("source") and c.get("key"):
            out.append(Citation(str(c["source"]), str(c["key"]), _opt_str(c.get("ts"))))
        elif isinstance(c, (list, tuple)) and len(c) >= 2 and c[0] and c[1]:
            out.append(Citation(str(c[0]), str(c[1]), _opt_str(c[2]) if len(c) > 2 else None))
    return out


def _opt_str(v: Any) -> str | None:
    return None if v in (None, "") else str(v)


# A far-future bound for "read the whole key" coord reads (read_between needs an explicit end).
_FAR_FUTURE = datetime(2100, 1, 1)


def _safe_dt(ts: str | None) -> datetime | None:
    """Parse a citation ``ts`` to a naive/aware datetime; ``None`` (whole-key) on absent/garbage."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
