"""The CGS §10.7 prompt freeze, verified MECHANICALLY (sha256/16 pins).

The three council strings are a FROZEN pre-registered config
(`PREREG_COUNCIL_GATE_SEPARATION.md` §10.7, validated 0/16 = SCARCITY in §10.8; run-of-record
`records/2026-06-10_retightened_rescore.txt`). The §10.8 gated run printed and matched these
exact hashes — this test makes a drifted byte unshippable. Editing the prompts requires a new
pre-registered freeze (new pins committed BEFORE the gated run, per §10.4/§10.7), never a quiet
edit here.
"""

import hashlib

from council import agents

# The §10.7 pins (sha256 hexdigest[:16] of the EXACT strings; adversary/strategist pins are over
# the full `_COMMON + role suffix` concatenation, matching scripts/probe_rescore_thesis_only.py).
PINS = {
    "_COMMON": "d96f18ebc865a384",
    "ADVERSARY_SYSTEM": "dc3d21ca8f6444cb",
    "STRATEGIST_SYSTEM": "ecbf363c9802289d",
}


def _sha16(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def test_council_prompts_match_s107_pins():
    for name, pin in PINS.items():
        assert _sha16(getattr(agents, name)) == pin, (
            f"{name} drifted from the CGS §10.7 frozen config (pin {pin}) — prompts are "
            "pre-registered; a change needs a new freeze, not an edit."
        )


def test_proposer_role_suffix_unchanged():
    # §10.7: PROPOSER_SYSTEM's role text is unchanged — it inherits the new _COMMON only.
    suffix = agents.PROPOSER_SYSTEM[len(agents._COMMON):]
    assert suffix.startswith(" ROLE: Inflection Analyst.")


def test_strategist_prompt_names_the_enforced_keys():
    # The deterministic enforcement (parse/debate/select) keys must appear verbatim in the frozen
    # prompt — the schema and the prompt may only change together (a desync would fail-close every
    # include). Lock-step companion to test_fakerouter_outputs_satisfy_validation.
    for key in agents._STRATEGIST_INCLUDE_BOOL_KEYS:
        assert key in agents.STRATEGIST_SYSTEM
    assert "structural_vs_fad" in agents.STRATEGIST_SYSTEM
    assert "inflection_passed" in agents.ADVERSARY_SYSTEM
