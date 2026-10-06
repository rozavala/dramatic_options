"""Stage-2 probe — the LLM layer: neutralize → DESCRIBE (roster) → CLASSIFY direction → score → RULE.

``PREREG_NARRATION_PROBE §4`` (FROZEN-B). Wires the deterministic core (:mod:`generator.probe`) to
the live deploy roster:

1. **neutralize** — redact the claim's specific entity names + quantity VALUES from the statement
   (→ ``[COMPANY]`` / ``[FIGURE]``), keeping the driver→effect→class mechanism. Recall of the redacted
   specifics IS the narration signal.
2. **describe** — each deploy-roster model (narration-maximal) recalls the specifics from training only.
3. **classify** — the ring-fenced ≥2-vendor classifier labels each description's direction; with
   agreement required, an ambiguous (disagreeing) label is NO-MATCH → permissive (§2 loss asymmetry).
4. **score + RULE** — the P1 deterministic legs (entity, quantity) + the direction match → per-model
   ``clears_all_three`` → REJECT iff ≥2 concur (§5).

Fail-closed/permissive: a router/transport error on a describer drops that model's score (it cannot
clear) and a parse failure on the classifier is NO-MATCH — both bias toward PASS, never a false reject.
The cost rides the council ledger. INERT: the live trading loop never imports ``generator/``.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Any

from council.agents import extract_json
from generator.probe import ModelScore, ProbeVerdict, probe_claim, score_claim_against_description
from generator.probe_prompts import CLASSIFIER_SYSTEM, DESCRIBER_SYSTEM, describer_user
from generator.prompts import MECHANISM_VOCAB

log = logging.getLogger("generator.probe_llm")


def _redact(statement: str, named_entities: list[dict] | None,
            headline_quantities: list[dict] | None) -> str:
    """Redact the claim's specific entity names + quantity values from the statement (case-insensitive,
    whole-word for the names; literal for the figure strings), keeping the mechanism structure."""
    s = str(statement or "")
    toks: set[str] = set()
    for e in named_entities or []:
        for f in ("canonical", "ticker", "name"):
            if e.get(f):
                toks.add(str(e[f]))
        for a in e.get("aliases") or []:
            if a:
                toks.add(str(a))
    for t in sorted((t for t in toks if t.strip()), key=len, reverse=True):  # longest first
        s = re.sub(rf"\b{re.escape(t)}\b", "[COMPANY]", s, flags=re.IGNORECASE)
    for q in headline_quantities or []:
        v = str((q or {}).get("value") or "").strip()
        if v and v in s:
            s = s.replace(v, "[FIGURE]")
    return s


def _entity_class(statement: str) -> str:
    """The trailing entity-class phrase of a '<driver> -> <effect> -> <entity class>' statement (the
    SECTOR, not a specific name) — kept to orient the recall. Empty if the arrow form is absent."""
    for sep in ("->", "→"):
        if sep in statement:
            return statement.rsplit(sep, 1)[1].strip()
    return ""


def neutralize(claim: dict[str, Any]) -> str:
    """The describer USER message for a claim: the redacted statement + the (non-specific) entity class."""
    stmt = str(claim.get("statement") or "")
    return describer_user(_redact(stmt, claim.get("named_entities"), claim.get("headline_quantities")),
                          _entity_class(stmt))


def parse_direction(text: str) -> tuple[str, str] | None:
    """Parse the classifier's JSON → (vocab, sign) from the frozen enum, else None (fail-closed)."""
    try:
        obj = extract_json(text)
    except Exception:  # noqa: BLE001 — a parse failure is NO-MATCH (permissive)
        return None
    vocab, sign = str(obj.get("vocab", "")).strip(), str(obj.get("sign", "")).strip()
    return (vocab, sign) if vocab in MECHANISM_VOCAB and sign in ("+", "-") else None


def classify_direction(description: str, *, router: Any, roles: list[str],
                       require_agreement: bool = True) -> tuple[tuple[str, str] | None, list]:
    """Ring-fenced ≥2-vendor direction classifier. Returns (label_or_None, raw_labels). With
    ``require_agreement``, the label is returned only if ≥2 roles agree on the same (vocab, sign);
    a disagreement → None (ambiguous → NO-MATCH → permissive, §2)."""
    labels: list[tuple[str, str] | None] = []
    for role in roles:
        try:
            resp = router.call(role=role, system=CLASSIFIER_SYSTEM, user=description)
            labels.append(parse_direction(resp.text or ""))
        except Exception as e:  # noqa: BLE001 — a classifier hiccup contributes no label (permissive)
            log.warning("probe classifier role=%s failed: %s", role, e)
            labels.append(None)
    valid = [x for x in labels if x]
    if not valid:
        return None, labels
    if not require_agreement:
        return valid[0], labels
    top, n = Counter(valid).most_common(1)[0]
    return (top if n >= 2 else None), labels


def probe_claim_live(
    claim: dict[str, Any], *, router: Any, describer_roles: list[str], classifier_roles: list[str],
    edgar_names: dict[str, str] | None = None,
) -> tuple[ProbeVerdict, list[dict[str, Any]]]:
    """Probe ONE claim live: describe over the roster, classify each description's direction, score via
    the P1 core, apply the §5 RULE. Returns (verdict, per-model diagnostics)."""
    user = neutralize(claim)
    md = claim.get("mechanism_direction") or {}
    want = (str(md.get("vocab", "")), str(md.get("sign", "")))
    scores: list[ModelScore] = []
    diags: list[dict[str, Any]] = []
    for role in describer_roles:
        try:
            desc = router.call(role=role, system=DESCRIBER_SYSTEM, user=user).text or ""
        except Exception as e:  # noqa: BLE001 — a describer drop cannot clear (permissive), never a false reject
            log.warning("probe describer role=%s failed: %s", role, e)
            desc = ""
        label, raw = classify_direction(desc, router=router, roles=classifier_roles)
        dmatch = label is not None and label == want
        scores.append(score_claim_against_description(claim, role, desc, direction_match=dmatch,
                                                      edgar_names=edgar_names))
        diags.append({"role": role, "description": desc, "direction_label": label,
                      "direction_match": dmatch})
    return probe_claim(claim, scores), diags


def probe_claims_live(
    claims: list[dict[str, Any]], *, router: Any, describer_roles: list[str], classifier_roles: list[str],
    edgar_names: dict[str, str] | None = None,
) -> list[tuple[ProbeVerdict, list[dict[str, Any]]]]:
    """Probe a batch of claims live (the §7 rejection-rate read is :func:`generator.probe.rejection_rate`
    over the verdicts)."""
    return [probe_claim_live(c, router=router, describer_roles=describer_roles,
                             classifier_roles=classifier_roles, edgar_names=edgar_names)
            for c in claims]
