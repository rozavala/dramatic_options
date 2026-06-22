"""P2 — the §3 citation VERIFIER (deterministic, no-LLM DROP gate; ``PREREG_THEME_GENERATOR §3/§11``).

The LOAD-BEARING defense against the LLM's narrated-corpus recall bias (§1): the deterministic
backstop on the proposer's free recall. A parsed §3 claim is admitted only if it verifies against
**the records it CITES** — entity-anchored AND (for entity-bearing sources) figure-traced. Failure
action is **DROP, never dampen** (the quote-authenticity pattern ``council/filters.py:37-54``
re-implemented HARD — a synthesis device, never a memory). NO LLM here, by design (§3).

Two legs:

- **Entity leg — MANDATORY, CITATION-ANCHORED** (reuses :mod:`generator.entity`). Each
  ``named_entities[]`` must resolve — by cik / symbol / name — in at least one CITED record. **An
  emitted claim's ``ts=None`` (whole-key) citations are REJECTED** (§11 / the ratified P2 decision):
  a claim must cite a *specific dated record*, so resolution runs over the concrete-``ts`` citations
  only. An entity in no such cited record → ``dropped_entity_unresolved`` → DROP (genuine
  confabulation). ``ticker_to_cik`` stays OPTIONAL-secondary (``edgar``, default off).

- **Fact leg — split by SOURCE-CLASS** (the ratified split): a ``headline_quantities[]`` figure is
  traced to the cited records' numeric magnitudes with a **±1-bucket (same-OOM) tolerance** WITHIN a
  family.
  - **(a) entity-bearing** (``capital_raises`` / ``customer_concentration`` / ``etf_constituents``)
    → record-keyed numeric trace, **fact-MANDATORY**: a claim that cites a class-(a) source and
    asserts a headline figure that traces to NO cited record → ``dropped_fact_untraced`` → DROP.
  - **(b) entity-free macro** (``bls`` / ``eia`` / ``nrc``) → SOURCE+KEY+value-bucket trace,
    **fact-where-present** (an untraced figure is tolerated — the sparse-tolerant precedent).
  - **(c) free-text recipient** (``federal_awards``) → ``recipient`` name-normalization tolerance +
    the award ``amount`` magnitude, **fact-where-present**.

**Counters (split, §3):** ``dropped_entity_unresolved`` (named entity in no cited record) +
``dropped_fact_untraced`` (real entity, untraced figure) + the total — the §5 band reads the split
to tell a degenerate yield apart (high ``_fact_untraced`` ⇒ corpus; high ``_entity_unresolved`` ⇒
model). Each carries a hand-checked exact-value test (§9, anti-HARK).

**Over-citation telemetry (§11 caution #1):** the entity leg is necessary-not-sufficient — a model
that OVER-cites can make most entities resolve, so a *suspiciously-low* ``dropped_entity_unresolved``
is the over-citation tell. We emit per-claim ``citation_count`` / ``coords_per_entity`` (and their
batch means) so over-citation is OBSERVABLE; it is telemetry, never a gate (citation *relevance* is
the council's axis, per the hard seam, NOT §3's job).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from corpus.bls_series import SOURCE as BLS_SOURCE
from corpus.capital_raises import SOURCE as CAP_SOURCE
from corpus.customer_concentration import SOURCE as CC_SOURCE
from corpus.eia_series import SOURCE as EIA_SOURCE
from corpus.etf_constituents import SOURCE as ETF_SOURCE
from corpus.federal_awards import SOURCE as AWARDS_SOURCE
from corpus.nrc_dockets import SOURCE as NRC_SOURCE
from generator.entity import Citation, _norm, as_citations, resolve_entity
from generator.prompts import BUCKET_FAMILIES

# ── source-class map (the ratified split) ─────────────────────────────────────────────────────
ENTITY_BEARING = "entity_bearing"        # (a) record-keyed trace, fact-MANDATORY
ENTITY_FREE_MACRO = "entity_free_macro"  # (b) source+key+value trace, fact-where-present
FREE_TEXT_RECIPIENT = "free_text_recipient"  # (c) name-normalization tolerance, fact-where-present

SOURCE_CLASS: dict[str, str] = {
    CAP_SOURCE: ENTITY_BEARING,
    CC_SOURCE: ENTITY_BEARING,
    ETF_SOURCE: ENTITY_BEARING,
    BLS_SOURCE: ENTITY_FREE_MACRO,
    EIA_SOURCE: ENTITY_FREE_MACRO,
    NRC_SOURCE: ENTITY_FREE_MACRO,
    AWARDS_SOURCE: FREE_TEXT_RECIPIENT,
}

# Record fields that can carry a traceable numeric MAGNITUDE, per family. The fact trace reads the
# cited record(s)' values from these fields and classifies each into its family ordinal; a claim's
# stated bucket then matches iff it is within ±1 of the record value's bucket in the SAME family.
# (`capital_raises` deliberately exposes NO magnitude field — structural filing metadata only — so a
# headline figure citing only capital_raises is correctly untraceable.)
_NUMERIC_FIELDS_BY_FAMILY: dict[str, tuple[str, ...]] = {
    "pct_": ("percentage", "weight_pct"),
    "usd_": ("amount",),
    "cnt_": ("n_customers", "shares", "rank"),
    "dur_": (),   # no structural duration field in the corpus today (reserved; future filings)
    "x_": (),     # multiples are derived/narrative — never a raw corpus field
    # entity-free macro `value` is family-agnostic; handled separately (see _macro_value_buckets).
}

_NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


@dataclass(frozen=True)
class ClaimVerdict:
    """The per-claim §3 verdict. ``dropped`` ⇒ the claim is removed; the reason is one of the split
    counters' axes. ``citation_count`` / ``coords_per_entity`` are over-citation telemetry."""

    claim_id: str
    dropped: bool
    reason: str | None                 # "entity_unresolved" | "fact_untraced" | None (kept)
    unresolved_entities: list[str] = field(default_factory=list)
    untraced_quantities: list[str] = field(default_factory=list)
    citation_count: int = 0            # concrete-ts citations the claim made (the trace anchors)
    coords_per_entity: float = 0.0     # citation_count / n_entities — the over-citation tell


@dataclass(frozen=True)
class VerifyResult:
    """The batch verdict: the surviving claims + the split counters + over-citation telemetry."""

    kept: list[dict[str, Any]]
    verdicts: list[ClaimVerdict]
    dropped_entity_unresolved: int
    dropped_fact_untraced: int

    @property
    def dropped_total(self) -> int:
        return self.dropped_entity_unresolved + self.dropped_fact_untraced

    @property
    def n_in(self) -> int:
        return len(self.verdicts)

    @property
    def n_kept(self) -> int:
        return len(self.kept)

    @property
    def mean_coords_per_entity(self) -> float:
        """Batch over-citation tell: a high mean alongside a near-zero ``dropped_entity_unresolved``
        is the over-citation signature (§11 #1) — surfaced, never gated."""
        vals = [v.coords_per_entity for v in self.verdicts]
        return sum(vals) / len(vals) if vals else 0.0

    @property
    def mean_citation_count(self) -> float:
        vals = [v.citation_count for v in self.verdicts]
        return sum(vals) / len(vals) if vals else 0.0


# ── value → family-bucket classification (for the fact trace) ─────────────────────────────────

def _family_of(bucket: str) -> str | None:
    """The family prefix (``pct_`` / ``usd_`` / …) a frozen bucket belongs to, else None."""
    b = str(bucket or "").strip()
    for fam, members in BUCKET_FAMILIES.items():
        if b in members:
            return fam
    return None


def _threshold_bucket(value: float, thresholds: tuple[tuple[float, str], ...], top: str) -> str:
    """The first bucket whose upper bound ``abs(value)`` falls under, else ``top`` (the open tail)."""
    v = abs(value)
    for upper, name in thresholds:
        if v < upper:
            return name
    return top


# Per-family upper-bound ladders (low→high), each ordered like BUCKET_FAMILIES so the classified
# bucket is the family's ordinal for the value (the ±1 tolerance then compares ordinals).
_PCT_LADDER = ((10, "pct_0_10"), (25, "pct_10_25"), (50, "pct_25_50"),
               (100, "pct_50_100"), (300, "pct_100_300"))
_USD_LADDER = ((1e7, "usd_millions"), (1e8, "usd_tens_of_millions"),
               (1e9, "usd_hundreds_of_millions"), (1e10, "usd_billions"),
               (1e11, "usd_tens_of_billions"))
_CNT_LADDER = ((100, "cnt_lt100"), (10_000, "cnt_100_10k"), (1_000_000, "cnt_10k_1m"))


def _pct_bucket(v: float) -> str:
    return _threshold_bucket(v, _PCT_LADDER, "pct_300plus")


def _usd_bucket(v: float) -> str:
    return _threshold_bucket(v, _USD_LADDER, "usd_hundreds_of_billions_plus")


def _cnt_bucket(v: float) -> str:
    return _threshold_bucket(v, _CNT_LADDER, "cnt_1m_plus")


_FAMILY_CLASSIFIER = {"pct_": _pct_bucket, "usd_": _usd_bucket, "cnt_": _cnt_bucket}


def _bucket_for_value(value: float, family: str) -> str | None:
    """Classify a raw numeric ``value`` into ``family``'s ordinal bucket (None for dur_/x_, which
    have no raw corpus field to classify against)."""
    fn = _FAMILY_CLASSIFIER.get(family)
    return fn(value) if fn else None


def _within_one_bucket(claim_bucket: str, record_bucket: str) -> bool:
    """True iff the two buckets are in the SAME family AND within ±1 ordinal (same-OOM tolerance)."""
    fam = _family_of(claim_bucket)
    if fam is None or _family_of(record_bucket) != fam:
        return False
    order = BUCKET_FAMILIES[fam]
    try:
        return abs(order.index(claim_bucket) - order.index(record_bucket)) <= 1
    except ValueError:
        return False


def _record_buckets(records: list[dict[str, Any]], family: str) -> set[str]:
    """The set of family buckets the cited records' numeric magnitude fields fall into."""
    out: set[str] = set()
    for f in _NUMERIC_FIELDS_BY_FAMILY.get(family, ()):  # entity-bearing/free-text magnitude fields
        for r in records:
            v = r.get(f)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                b = _bucket_for_value(float(v), family)
                if b:
                    out.add(b)
    return out


def _macro_value_buckets(records: list[dict[str, Any]], family: str) -> set[str]:
    """Entity-free-macro trace (b): classify each record's family-agnostic ``value`` into the claim's
    family. The macro series value carries no intrinsic unit, so it is classified into whatever family
    the claim asserts (a pct series value into pct_, an MWh count into cnt_, etc.)."""
    out: set[str] = set()
    for r in records:
        v = r.get("value")
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            b = _bucket_for_value(float(v), family)
            if b:
                out.add(b)
    return out


def _quantity_text(q: dict[str, Any]) -> str:
    """The free-text of a headline_quantity (metric + value) for the (c) name-normalization trace."""
    return _norm(f"{q.get('metric', '')} {q.get('value', '')}")


# ── the verifier ──────────────────────────────────────────────────────────────────────────────

def _concrete_ts_citations(raw_citations: list[Any]) -> list[Citation]:
    """The claim's citations coerced to :class:`Citation`, KEEPING only concrete-``ts`` coords.

    The ratified P2 rule: an emitted claim must cite a *specific dated record* — a ``ts=None``
    (whole-key) citation is REJECTED for verification (§11). So a claim that cites only whole-key
    coords anchors nothing and its entities go unresolved (the DROP path)."""
    return [c for c in as_citations(raw_citations) if c.ts is not None]


def _trace_quantity(
    q: dict[str, Any],
    records_by_class: dict[str, list[dict[str, Any]]],
) -> bool:
    """True iff the headline_quantity ``q`` traces to a cited record under ANY source-class.

    A figure traces when its stated bucket is within ±1 of a bucket some cited record's magnitude
    falls into — entity-bearing (a) numeric fields, entity-free-macro (b) ``value``, or the free-text
    (c) award amount. A non-numeric / bucket-less / family-less quantity is treated as TRACED iff its
    text appears in a cited free-text-recipient record (the (c) name-normalization tolerance) — and is
    otherwise NOT counted against an entity-bearing claim only when no class-(a) source was cited
    (caller enforces the MANDATORY split)."""
    bucket = str((q or {}).get("bucket", "")).strip()
    fam = _family_of(bucket)
    if fam is not None:
        cand: set[str] = set()
        cand |= _record_buckets(records_by_class.get(ENTITY_BEARING, []), fam)
        cand |= _record_buckets(records_by_class.get(FREE_TEXT_RECIPIENT, []), fam)
        cand |= _macro_value_buckets(records_by_class.get(ENTITY_FREE_MACRO, []), fam)
        if any(_within_one_bucket(bucket, rb) for rb in cand):
            return True
    # (c) name-normalization tolerance: the quantity's text overlaps a cited award recipient/desc.
    qt = _quantity_text(q)
    if qt:
        for r in records_by_class.get(FREE_TEXT_RECIPIENT, []):
            hay = _norm(f"{r.get('recipient', '')} {r.get('naics_desc', '')}")
            if hay and (qt in hay or hay in qt):
                return True
    return False


def verify_claim(
    claim: dict[str, Any],
    cache: Any,
    *,
    edgar: Any | None = None,
) -> ClaimVerdict:
    """Verify ONE parsed §3 claim against the records it cites (entity leg, then fact leg).

    DROP order: entity-unresolved is checked first (a confabulated entity is the worse failure and
    its counter feeds the model-vs-corpus §5 read); only an entity-clean claim reaches the fact leg.
    """
    cid = str(claim.get("claim_id", "?"))
    citations = _concrete_ts_citations(claim.get("citations") or [])
    entities = claim.get("named_entities") or []
    n_ent = max(1, len(entities))
    coords_per_entity = len(citations) / n_ent

    # ── entity leg (citation-anchored; ts=None already rejected) ──
    unresolved = [
        str(e.get("canonical") or e.get("ticker") or e.get("name") or _norm(e))
        for e in entities
        if not resolve_entity(e, citations, cache, edgar=edgar)
    ]
    if unresolved:
        return ClaimVerdict(cid, dropped=True, reason="entity_unresolved",
                            unresolved_entities=unresolved,
                            citation_count=len(citations), coords_per_entity=coords_per_entity)

    # ── fact leg (split by source-class; MANDATORY only when a class-(a) source is cited) ──
    cited_classes = {SOURCE_CLASS.get(c.source) for c in citations}
    fact_mandatory = ENTITY_BEARING in cited_classes
    records_by_class = _records_by_class(citations, cache)
    untraced: list[str] = []
    if fact_mandatory:
        for q in claim.get("headline_quantities") or []:
            if not _trace_quantity(q, records_by_class):
                untraced.append(str((q or {}).get("metric") or (q or {}).get("value") or "?"))
    if untraced:
        return ClaimVerdict(cid, dropped=True, reason="fact_untraced",
                            untraced_quantities=untraced,
                            citation_count=len(citations), coords_per_entity=coords_per_entity)

    return ClaimVerdict(cid, dropped=False, reason=None,
                        citation_count=len(citations), coords_per_entity=coords_per_entity)


def _records_by_class(
    citations: list[Citation], cache: Any
) -> dict[str, list[dict[str, Any]]]:
    """Group the cited records by source-class for the fact trace. Reuses the entity module's
    fail-soft coord resolution (a missing/uncovered coord contributes no records, never raises)."""
    from generator.entity import _coord_records  # the §11 ts-collision-aware coord resolver
    by_class: dict[str, list[dict[str, Any]]] = {
        ENTITY_BEARING: [], ENTITY_FREE_MACRO: [], FREE_TEXT_RECIPIENT: []}
    for cit in citations:
        cls = SOURCE_CLASS.get(cit.source)
        if cls is None:
            continue
        by_class[cls].extend(_coord_records(cache, cit))
    return by_class


def verify_claims(
    claims: list[dict[str, Any]],
    cache: Any,
    *,
    edgar: Any | None = None,
) -> VerifyResult:
    """Verify a batch of parsed §3 claims; DROP failures and tally the split counters.

    Returns the surviving claims + per-claim verdicts + ``dropped_entity_unresolved`` /
    ``dropped_fact_untraced`` (+ ``dropped_total``) + the over-citation telemetry. No LLM, no I/O
    beyond the (fail-soft) PIT cache reads the entity/fact legs already do.
    """
    verdicts = [verify_claim(c, cache, edgar=edgar) for c in claims]
    kept = [c for c, v in zip(claims, verdicts, strict=True) if not v.dropped]
    return VerifyResult(
        kept=kept,
        verdicts=verdicts,
        dropped_entity_unresolved=sum(1 for v in verdicts if v.reason == "entity_unresolved"),
        dropped_fact_untraced=sum(1 for v in verdicts if v.reason == "fact_untraced"),
    )
