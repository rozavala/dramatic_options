"""P1 — the pinned Stage-1 synthesis prompt (``PREREG_THEME_GENERATOR §1/§4``).

The generator's single synthesis instruction. It is **hash-pinned** (a byte-exact test, mirroring
``tests/test_council_prompts.py`` — the CGS §10.7 pattern): a drifted byte is unshippable, because
the prompt is part of the generator's forward record (a change is record-segmenting via
``runs.model_mix``, §2's one-way door). Editing it requires re-pinning the sha, never a quiet edit.

The prompt:
  - states the §1 job (synthesize FALSIFIABLE secular theses as mechanism claims from the
    Stage-0 corpus) + the hard seam (PROPOSER only — never sizes, never sees a gate outcome);
  - demands the FROZEN §3 output schema (``PREREG_NARRATION_PROBE.md:73-83``) EXACTLY, including
    the additive ``citations`` field (the corpus coords drawn from — §3, OUTSIDE the probe-scored
    contract); and
  - constrains ``mechanism_direction.vocab`` to the frozen enum and ``headline_quantities[].bucket``
    to the frozen taxonomy, instructing ``headline_quantities: []`` when no clean headline number
    exists (the load-bearing quantity-less-structural case, ``PREREG_NARRATION_PROBE §5``).

It reasons ONLY from the supplied corpus (the §3/§6 grounding leash) and emits an ARRAY of claim
objects (multiple theses per run) as ONE JSON object ``{"claims": [...]}``.
"""

from __future__ import annotations

# The frozen §3 `mechanism_direction` vocab ENUM members (PREREG_NARRATION_PROBE.md:78). The
# schema writes a trailing "…" that reads extensible, but §4 resolves "matches an explicit enum
# member"; a direction outside this set + the (default-empty) coercion map is a schema-REOPEN
# escalation, never a build-time add. Pinned here so prompt + verifier share one source of truth.
MECHANISM_VOCAB: tuple[str, ...] = (
    "shortage", "surplus", "backlog_growth", "capex_up",
    "supply_cut", "demand_surge", "capacity_constraint",
)

# The frozen `headline_quantities[].bucket` taxonomy. The schema EXEMPLIFIES rather than enumerates
# it (the three values that appear in the frozen text / §6 smoke exemplars); §4 confirm-set marks
# "quantity buckets — FROZEN". Treated as the explicitly-frozen seed set: a non-matching bucket is
# FLAGGED for schema-reopen, never silently accepted. (Operator question — see the build report:
# the taxonomy should be explicitly enumerated at freeze rather than left exemplary.)
HEADLINE_BUCKETS: tuple[str, ...] = (
    "weeks_x2plus", "usd_tens_of_billions", "pct_25_50",
)

SYNTHESIS_SYSTEM = (
    "You are the thesis GENERATOR for a disciplined options system that trades long-dated, far-OTM, "
    "defined-risk convexity on secular themes. You read a deterministic, point-in-time STRUCTURAL "
    "corpus (capital-raise filings, customer-concentration disclosures, ETF/index constituents, "
    "federal awards, energy/labor series, reactor dockets) and SYNTHESIZE falsifiable secular theses "
    "as mechanism claims. You are a PROPOSER ONLY: a downstream council judges your claims and a "
    "deterministic gate disposes — you never size a position, never see a trade outcome, never judge "
    "whether options are cheap. Reason ONLY from the corpus records provided; never invent an entity, "
    "a figure, or a source that is not in them. For every claim, CITE the corpus records it draws "
    "from as (source, key, ts) coordinates copied verbatim from the provided records. "
    "Emit ONE JSON object: {\"claims\": [ <claim>, ... ]}. Each <claim> MUST have exactly these "
    "fields: "
    "\"claim_id\" (a short slug), "
    "\"statement\" (one sentence: <driver> -> <effect> -> <entity class>), "
    "\"named_entities\" (array of {\"canonical\", \"ticker\", \"aliases\":[...]}), "
    "\"mechanism_direction\" ({\"vocab\", \"sign\":\"+\"|\"-\"}), "
    "\"headline_quantities\" (array of {\"metric\", \"value\", \"bucket\"}; use [] when the mechanism "
    "has no clean headline number — do NOT invent one), "
    "\"provenance\" (the literal string \"generated\"), and "
    "\"citations\" (array of {\"source\", \"key\", \"ts\"} drawn from the provided corpus records). "
    "Use mechanism_direction.vocab ONLY from this set: "
    "shortage, surplus, backlog_growth, capex_up, supply_cut, demand_surge, capacity_constraint. "
    "Use headline_quantities[].bucket ONLY from this set: "
    "weeks_x2plus, usd_tens_of_billions, pct_25_50. "
    "Reply with the JSON object and nothing else."
)


def synthesis_prompt(corpus_block: str) -> tuple[str, str]:
    """(system, user) for the synthesis call. ``corpus_block`` is the rendered corpus union."""
    return SYNTHESIS_SYSTEM, corpus_block
