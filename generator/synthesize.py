"""P1 — synthesis + strict §3 parser + emit-cleanliness SHAPE (``PREREG_THEME_GENERATOR §4/§6``).

Builds the synthesis prompt from the Stage-0 corpus union, calls the council router (``FakeRouter``
the DEFAULT — roster is CONFIG-DRIVEN, never hardcoded here), and parses the response to the FROZEN
§3 schema (``PREREG_NARRATION_PROBE.md:73-83``), **fail-closed** (mirrors ``council.agents.
extract_json`` + the per-role required-key validation): a truncated / empty / wrong-shape response
yields NO claims rather than a malformed one (the #37 discipline — a "valid but empty shape" is the
bug in a new costume).

It also implements the **emit-cleanliness SHAPE check** (§4): over the emitted claims, **100% of
``mechanism_direction.vocab`` RESOLVES** (a frozen-enum member OR a pinned coercion-map entry —
the map defaults EMPTY, an operator artifact) **AND 100% of non-empty ``headline_quantities``
resolve to a frozen bucket.** Any miss is FLAGGED as a schema-REOPEN escalation — it is NOT added
to the enum at build time (§4: "never a build-time add").

**§5 blinding:** this module invokes the generator LLM, so PRE-FREEZE it must run against
``FakeRouter`` / a pinned fixture corpus ONLY (never the live corpus) — a live-corpus run emits the
thesis count + ``dropped_*`` the §10 band gates. The fixture/Fake default enforces that here; the
live wiring + the kill/cost gates are P3 (not built).

This module builds the PARSER + the SHAPE check only. The §3 citation VERIFIER (the entity/fact
DROP gate + the split ``dropped_entity_unresolved`` / ``dropped_fact_untraced`` counters) is P2 —
the ``citations`` field is parsed and preserved here, but NOT yet adjudicated.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from council.agents import extract_json
from council.router import FakeRouter
from generator.prompts import HEADLINE_BUCKETS, MECHANISM_VOCAB, synthesis_prompt

# The §3 claim fields that MUST be present + correctly typed (the generator-core contract). A claim
# missing/mistyping any is dropped fail-closed (the #37 "valid but empty shape" guard). `provenance`
# must be the literal "generated"; `citations` is additive-but-required (§3 — the verifier's input).
_REQUIRED_FIELDS = ("claim_id", "statement", "named_entities", "mechanism_direction",
                    "headline_quantities", "provenance", "citations")


@dataclass(frozen=True)
class EmitCleanliness:
    """The §4 SHAPE verdict over a batch of parsed claims (NOT a yield count — §5-safe shape only).

    ``clean`` iff every emitted direction RESOLVES and every non-empty quantity resolves to a frozen
    bucket. Misses are recorded (value + claim_id) as schema-REOPEN escalations, never auto-added.
    """

    clean: bool
    n_claims: int
    unresolved_vocab: list[tuple[str, str]] = field(default_factory=list)      # (claim_id, vocab)
    unresolved_buckets: list[tuple[str, str]] = field(default_factory=list)    # (claim_id, bucket)

    @property
    def reopen_required(self) -> bool:
        """True ⇒ a frozen-schema REOPEN escalation is owed (a dated PROBE-pre-reg amendment, §4)."""
        return not self.clean


def _resolves_vocab(vocab: str, coercion_map: dict[str, str]) -> bool:
    """A direction RESOLVES iff it is a frozen-enum member OR a pinned coercion-map key (§4)."""
    v = str(vocab or "").strip()
    return v in MECHANISM_VOCAB or v in (coercion_map or {})


def _resolves_bucket(bucket: str) -> bool:
    """A non-empty bucket RESOLVES iff it is a frozen-taxonomy member (§4)."""
    return str(bucket or "").strip() in HEADLINE_BUCKETS


def _is_valid_claim(claim: Any) -> bool:
    """Shape gate: a dict with every required §3 field present + correctly typed, provenance literal.

    Fail-closed, like the council parsers — a claim that fails this is dropped, never repaired.
    """
    if not isinstance(claim, dict):
        return False
    if any(f not in claim for f in _REQUIRED_FIELDS):
        return False
    if not isinstance(claim.get("claim_id"), str) or not claim["claim_id"].strip():
        return False
    if not isinstance(claim.get("statement"), str) or not claim["statement"].strip():
        return False
    if not isinstance(claim.get("named_entities"), list) or not claim["named_entities"]:
        return False
    md = claim.get("mechanism_direction")
    if not isinstance(md, dict) or "vocab" not in md or str(md.get("sign")) not in ("+", "-"):
        return False
    if not isinstance(claim.get("headline_quantities"), list):  # may be [] (permissive-correct)
        return False
    if claim.get("provenance") != "generated":
        return False
    if not isinstance(claim.get("citations"), list):
        return False
    return True


def parse_synthesis(text: str) -> list[dict[str, Any]]:
    """Parse a synthesis response to the list of well-formed §3 claims, fail-closed.

    Pulls the first balanced JSON object (the ``extract_json`` discipline), reads ``claims`` (an
    array; a bare single claim object is also accepted), and keeps ONLY claims that pass the §3
    shape gate. A parse failure / wrong shape yields ``[]`` (the #37 fail-closed-to-zero rule) —
    never a partial or invented claim.
    """
    try:
        obj = extract_json(text)
    except (ValueError, json.JSONDecodeError):
        return []
    if isinstance(obj.get("claims"), list):
        raw = obj["claims"]
    elif _is_valid_claim(obj):       # a lone claim object (no wrapper) is tolerated
        raw = [obj]
    else:
        return []
    return [c for c in raw if _is_valid_claim(c)]


def check_emit_cleanliness(
    claims: list[dict[str, Any]], *, coercion_map: dict[str, str] | None = None
) -> EmitCleanliness:
    """The §4 emit-cleanliness SHAPE verdict over already-parsed claims.

    100% of directions must RESOLVE (frozen enum OR pinned coercion map) AND 100% of non-empty
    quantities must resolve to a frozen bucket. Misses are returned as schema-REOPEN escalations.
    """
    cmap = coercion_map or {}
    bad_vocab: list[tuple[str, str]] = []
    bad_bucket: list[tuple[str, str]] = []
    for c in claims:
        cid = str(c.get("claim_id", "?"))
        vocab = (c.get("mechanism_direction") or {}).get("vocab", "")
        if not _resolves_vocab(vocab, cmap):
            bad_vocab.append((cid, str(vocab)))
        for q in c.get("headline_quantities") or []:
            bucket = (q or {}).get("bucket", "")
            if str(bucket).strip() == "":       # empty bucket on a present quantity is malformed-but
                bad_bucket.append((cid, ""))     # we treat it as a non-resolving bucket (reopen-flag)
            elif not _resolves_bucket(bucket):
                bad_bucket.append((cid, str(bucket)))
    return EmitCleanliness(
        clean=not bad_vocab and not bad_bucket,
        n_claims=len(claims),
        unresolved_vocab=bad_vocab,
        unresolved_buckets=bad_bucket,
    )


def render_corpus_block(corpus: dict[str, list[dict[str, Any]]], *, max_per_source: int = 200) -> str:
    """Render the Stage-0 corpus union into the synthesis prompt's grounding block (deterministic).

    One section per source (sorted). Each entry is rendered as
    ``{"cite": {"source","key","ts"}, "record": {...}}`` so the model can copy the EXACT coordinate
    the §3 verifier resolves. The ``key`` is the cache COORD key (carried as ``_coord_key`` by
    ``assemble_corpus(tag_key=True)`` — capital_raises=``form``, customer_concentration/etf=``symbol``,
    bls=``series_id``, federal_awards=``hash``, nrc=``power_reactors``), NOT a record-body id
    (accession / PIID). Exposing it is the citation-key-contract fix: without the coord shown, the
    model guesses the key from the record body and mis-cites every source whose cache key is not a
    body field (5 of 7), causing false ``entity_unresolved`` drops. ``max_per_source`` bounds the
    prompt; the bound is a rendering cap only (it never changes which coords exist for the trace)."""
    lines: list[str] = [
        'CORPUS (point-in-time structural records). Each entry is '
        '{"cite": {"source","key","ts"}, "record": {...}}. To cite a record, copy its "cite" object '
        "VERBATIM into a claim's citations — that triple is the coordinate the verifier resolves:"
    ]
    for source in sorted(corpus):
        recs = corpus[source]
        lines.append(f"\n## {source} ({len(recs)} records)")
        for r in recs[:max_per_source]:
            body = {k: v for k, v in r.items() if k != "_coord_key"}
            cite = {"source": source, "key": r.get("_coord_key"), "ts": r.get("ts")}
            lines.append(json.dumps({"cite": cite, "record": body}, sort_keys=True, default=str))
    return "\n".join(lines)


@dataclass
class SynthesisResult:
    """The synthesis output: the (verified) claims + the §4 emit-cleanliness verdict + raw text.

    ``claims`` holds the SURVIVING claims after the P2 §3 citation verifier DROPs (when a verifying
    cache is supplied); ``parsed`` is the pre-DROP parsed set (so the DROP yield is inspectable) and
    ``verify`` the :class:`generator.verify.VerifyResult` (the split counters + over-citation
    telemetry). With no cache, ``claims == parsed`` and ``verify is None`` (P1 parse-only). The §4
    ``cleanliness`` is a SHAPE property of what the model EMITTED, so it is read over ``parsed`` —
    independent of citation verification (the DROP gate is a separate, deterministic concern)."""

    claims: list[dict[str, Any]]
    cleanliness: EmitCleanliness
    raw_text: str
    parsed: list[dict[str, Any]] = field(default_factory=list)
    verify: Any | None = None  # generator.verify.VerifyResult | None (None ⇒ no verification run)
    model: str | None = None   # the synthesis model id (for the artifact's matched-version stamp, §3)


def synthesize(
    corpus: dict[str, list[dict[str, Any]]],
    *,
    router: Any | None = None,
    role: str = "generator",
    coercion_map: dict[str, str] | None = None,
    max_tokens: int | None = None,
    verify_against: Any | None = None,
    edgar: Any | None = None,
) -> SynthesisResult:
    """Run one synthesis pass: render → call router → parse §3 → check emit-cleanliness → VERIFY.

    ``router`` defaults to ``FakeRouter()`` (offline, no keys, no network — the §5 fixture-only
    default + the test path). The LIVE router is built CONFIG-DRIVEN by the caller via
    ``council.router.build_router`` (roster is config, never hardcoded here). Fail-closed: a
    router/transport error or a wrong-shape response yields zero claims (the response text is
    preserved for forensics).

    When ``verify_against`` (a point-in-time cache) is supplied, the P2 §3 citation VERIFIER
    (:func:`generator.verify.verify_claims`) runs after the parse: a parsed claim whose entities do
    not resolve in its CITED records, or whose headline figure does not trace (for an entity-bearing
    citation), is DROPPED — ``claims`` then holds only the survivors. ``edgar`` is the OPTIONAL
    ticker→CIK secondary (default off). With no cache the verifier is skipped (P1 parse-only).
    """
    router = router or FakeRouter()
    system, _ = synthesis_prompt("")
    user = render_corpus_block(corpus)
    resp = router.call(role=role, system=system, user=user, max_tokens=max_tokens)
    text = resp.text or ""
    parsed = parse_synthesis(text)
    cleanliness = check_emit_cleanliness(parsed, coercion_map=coercion_map)
    verify_result = None
    kept = parsed
    if verify_against is not None:
        from generator.verify import verify_claims  # local import keeps the P1 parse path LLM-clean
        verify_result = verify_claims(parsed, verify_against, edgar=edgar)
        kept = verify_result.kept
    return SynthesisResult(
        claims=kept,
        cleanliness=cleanliness,
        raw_text=text,
        parsed=parsed,
        verify=verify_result,
        model=getattr(resp, "model", None),
    )
