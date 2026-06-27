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

# The frozen `headline_quantities[].bucket` taxonomy — the RATIFIED enumeration (operator-confirmed
# 2026-06-22; supersedes the three exemplary values the §6 smoke seeded). Buckets are UNSIGNED
# magnitude bins ORGANIZED BY FAMILY (sign comes from `mechanism_direction`, never the bucket). The
# families are ORDERED low→high so the P2 fact-level match can apply a ±1-bucket (same-OOM) tolerance
# WITHIN a family. A bucket outside this set (or a value that resolves to NO bucket) is FLAGGED for a
# schema-REOPEN escalation, never auto-added (§4 / the schema-REOPEN flag).
#
# The frozen `weeks_x2plus` exemplar maps into the x_ family as `x_2plus` (per the ratified taxonomy).
BUCKET_FAMILIES: dict[str, tuple[str, ...]] = {
    "pct_": ("pct_0_10", "pct_10_25", "pct_25_50", "pct_50_100", "pct_100_300", "pct_300plus"),
    "usd_": ("usd_millions", "usd_tens_of_millions", "usd_hundreds_of_millions",
             "usd_billions", "usd_tens_of_billions", "usd_hundreds_of_billions_plus"),
    "dur_": ("dur_weeks_lt10", "dur_weeks_10_50", "dur_weeks_50plus",
             "dur_months_12_36", "dur_years_3plus"),
    "x_": ("x_lt2", "x_2plus", "x_5plus", "x_10plus"),
    "cnt_": ("cnt_lt100", "cnt_100_10k", "cnt_10k_1m", "cnt_1m_plus"),
}

# The flat frozen set (every family member) — the membership the emit-cleanliness check resolves
# against. Derived from BUCKET_FAMILIES so the two can never drift.
HEADLINE_BUCKETS: tuple[str, ...] = tuple(b for fam in BUCKET_FAMILIES.values() for b in fam)

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
    "Each headline_quantities[].bucket is an UNSIGNED magnitude bin (the sign lives in "
    "mechanism_direction, never the bucket). Use ONLY a bucket from this set: "
    "pct_0_10, pct_10_25, pct_25_50, pct_50_100, pct_100_300, pct_300plus; "
    "usd_millions, usd_tens_of_millions, usd_hundreds_of_millions, usd_billions, "
    "usd_tens_of_billions, usd_hundreds_of_billions_plus; "
    "dur_weeks_lt10, dur_weeks_10_50, dur_weeks_50plus, dur_months_12_36, dur_years_3plus; "
    "x_lt2, x_2plus, x_5plus, x_10plus; "
    "cnt_lt100, cnt_100_10k, cnt_10k_1m, cnt_1m_plus. "
    "Reply with the JSON object and nothing else."
)


def synthesis_prompt(corpus_block: str) -> tuple[str, str]:
    """(system, user) for the synthesis call. ``corpus_block`` is the rendered corpus union."""
    return SYNTHESIS_SYSTEM, corpus_block


def synthesis_prompt_sha() -> str:
    """16-char sha of the frozen ``SYNTHESIS_SYSTEM`` — stamped into each generator artifact so the scorer
    can enforce §3's matched-version requirement (a prompt edit segments the record)."""
    import hashlib

    return hashlib.sha256(SYNTHESIS_SYSTEM.encode()).hexdigest()[:16]
