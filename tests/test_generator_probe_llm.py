"""Stage-2 probe — the LLM layer (neutralize / classify / orchestration) + the byte-pinned prompts.

Offline: a ``FakeRouter`` responder routes by the system prompt (describer vs classifier), so no keys
/ network. Covers the redaction, the classifier agreement, and the end-to-end RULE (narrated→reject,
quiet→pass, describer-failure→permissive).
"""

import hashlib
import json

from council.router import FakeRouter
from generator import probe_llm as L
from generator import probe_prompts as PP

DESCRIBER_ROLES = ["proposer", "adversary", "strategist"]
CLASSIFIER_ROLES = ["proposer", "strategist"]

_NVDA_CLAIM = {
    "claim_id": "nvda", "statement": "Hyperscaler AI capex -> NVIDIA GPU dominance -> accelerator demand",
    "named_entities": [{"canonical": "NVIDIA", "ticker": "NVDA", "aliases": ["Nvidia"]}],
    "mechanism_direction": {"vocab": "demand_surge", "sign": "+"},
    "headline_quantities": [{"metric": "dc rev", "value": "~$30B", "bucket": "usd_tens_of_billions"}],
}


def _responder(describer_text, label=None):
    """A FakeRouter responder: describer system → ``describer_text``; classifier system → ``label`` json."""
    def r(role, system, user):
        if "RECALL probe" in system:                       # the describer
            return describer_text
        return json.dumps(label or {"vocab": "demand_surge", "sign": "+"})  # the classifier
    return r


# ── freeze-grade prompts are byte-pinned (a drifted byte is unshippable without re-pinning) ──────

def test_describer_classifier_prompts_byte_pinned():
    assert hashlib.sha256(PP.DESCRIBER_SYSTEM.encode()).hexdigest()[:16] == "c008d83fe8dd0845"
    assert hashlib.sha256(PP.CLASSIFIER_SYSTEM.encode()).hexdigest()[:16] == "a8c48c932e4a8d2f"


# ── neutralization (§4) ──────────────────────────────────────────────────────────────────────────

def test_neutralize_redacts_entities_and_quantities():
    claim = dict(_NVDA_CLAIM, statement="NVIDIA and Nvidia ship $30B GPUs -> demand",
                 headline_quantities=[{"value": "$30B", "bucket": "usd_tens_of_billions"}])
    out = L.neutralize(claim)
    assert "NVIDIA" not in out and "Nvidia" not in out and "$30B" not in out
    assert "[COMPANY]" in out and "[FIGURE]" in out


def test_parse_direction_valid_and_invalid():
    assert L.parse_direction('{"vocab":"demand_surge","sign":"+"}') == ("demand_surge", "+")
    assert L.parse_direction('{"vocab":"not_a_vocab","sign":"+"}') is None
    assert L.parse_direction("not json") is None


# ── the ring-fenced classifier: ≥2-vendor agreement ──────────────────────────────────────────────

def test_classify_direction_requires_agreement():
    # both roles agree → the label; the FakeRouter responder returns the same json for any classifier role
    fr = FakeRouter(responder=_responder("x", {"vocab": "capex_up", "sign": "+"}))
    label, raw = L.classify_direction("desc", router=fr, roles=CLASSIFIER_ROLES)
    assert label == ("capex_up", "+") and len(raw) == 2

    # disagreement → None (ambiguous → NO-MATCH → permissive)
    seq = iter([{"vocab": "capex_up", "sign": "+"}, {"vocab": "demand_surge", "sign": "+"}])
    fr2 = FakeRouter(responder=lambda role, system, user: json.dumps(next(seq)))
    label2, _ = L.classify_direction("desc", router=fr2, roles=CLASSIFIER_ROLES)
    assert label2 is None


# ── end-to-end RULE through the live orchestration (FakeRouter) ──────────────────────────────────

def test_probe_claim_live_narrated_claim_is_rejected():
    # every describer surfaces the redacted specifics (NVDA + $30 billion) + the classifier matches the
    # direction → all-three-high on every roster model → ≥2 concur → REJECTED (narrated).
    fr = FakeRouter(responder=_responder(
        "This is NVIDIA (NVDA); its data-center revenue is about $30 billion with surging demand."))
    verdict, diags = L.probe_claim_live(_NVDA_CLAIM, router=fr, describer_roles=DESCRIBER_ROLES,
                                        classifier_roles=CLASSIFIER_ROLES)
    assert verdict.rejected is True and verdict.n_concur == 3
    assert all(d["direction_match"] for d in diags)


def test_probe_claim_live_quiet_claim_passes():
    # the describers cannot surface the specifics → entity/quantity legs low → no model clears → PASS.
    fr = FakeRouter(responder=_responder("Some unnamed companies in this sector; no specifics known."))
    verdict, _ = L.probe_claim_live(_NVDA_CLAIM, router=fr, describer_roles=DESCRIBER_ROLES,
                                    classifier_roles=CLASSIFIER_ROLES)
    assert verdict.passed is True and verdict.n_concur == 0


def test_probe_describer_failure_is_permissive_never_a_false_reject():
    # a router error on EVERY describer → empty descriptions → no model can clear → the claim PASSES
    # (the §2 permissive bias: a probe outage must never reject a good quiet claim).
    def boom(role, system, user):
        if "RECALL probe" in system:
            raise RuntimeError("describer down")
        return json.dumps({"vocab": "demand_surge", "sign": "+"})
    fr = FakeRouter(responder=boom)
    verdict, _ = L.probe_claim_live(_NVDA_CLAIM, router=fr, describer_roles=DESCRIBER_ROLES,
                                    classifier_roles=CLASSIFIER_ROLES)
    assert verdict.passed is True
