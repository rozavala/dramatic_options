"""Stage-2 — the narration PROBE: the DETERMINISTIC scorer core + the reject RULE (no LLM).

``PREREG_NARRATION_PROBE.md`` (FROZEN 2026-06-17). The under-narration FUNNEL on Stage-1 generator
output: it measures how NARRATED a mechanism claim is, so a genuinely-quiet claim clears the council's
``under_narrated`` bar WITHOUT loosening it (the HARK leash — measure the criterion, never relax it).
**FIAT-PERMISSIVE (§2):** the threshold is a deterministic RULE pinned blind; only its cutoff value
is by fiat. ADDITIVE atop the §9 coverage-count sensor (§1) — never a supersession.

This module is the **deterministic core (no LLM, fixture-exempt)**: the entity + quantity overlap
scorers (§4 legs 1 & 3, fully deterministic), the per-model all-three-high test, and the reject RULE
(all-three-high ∧ ≥2-roster-concur, §5). The LLM layer — the free-text DESCRIBER elicitation over the
deploy roster + the ring-fenced ``mechanism_direction`` classifier (§4 FROZEN-B) — feeds this core and
is built separately (keyed). The describer/classifier PRODUCE the per-model inputs; this core DECIDES.

**§5 empty/absent-field rule (load-bearing, REQUIRED test):** an empty/absent field is NOT
high-overlap, so the all-three conjunction is unsatisfiable → the claim PASSES (the protector of
quantity-less structural claims — an NRC-docket mechanism with no headline number must not be rejected).

INERT: the live trading loop never imports ``generator/`` (the §6.4 import-graph guard).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from generator.prompts import BUCKET_FAMILIES
from generator.verify import (
    _bucket_for_value as _value_bucket,  # pct_/usd_/cnt_ value→bucket classifier
)
from generator.verify import _family_of

# ── FROZEN constants (PREREG_NARRATION_PROBE §4/§5/§7) ───────────────────────────────────────────
FIELD_WEIGHTS: dict[str, float] = {                 # §4 (favor the deterministic legs)
    "named_entities": 0.40, "mechanism_direction": 0.30, "headline_quantities": 0.30}
HIGH_OVERLAP_CUTOFF: float = 0.80                   # §5 per-LIST-field overlap ≥ 0.80 (operator-set blind)
CONCUR_MIN: int = 2                                 # §5 ≥2 deploy-roster models concur to reject
REJECT_BAND: tuple[float, float] = (0.15, 0.35)     # §7 expected rejection band (operator-set blind)
INERT_N_FLOOR: int = 20                             # §7 cumulative N-floor on "0% = inert" (operator-set blind)

# §4 classifier-agreement bar — PINNED BLIND HERE (the build-spec pin, BEFORE any hand-labeled
# validation runs; PREREG_NARRATION_PROBE §4/§10 require it be set blind, not a post-hoc pick). The
# ring-fenced mechanism_direction classifier (controlled-vocab sign+responsiveness, ≥2-vendor) must
# agree with the hand labels at ≥ this on the pre-deploy validation set before the probe is wired
# live. 0.85: a controlled-vocab label on a small set is an easy task, so a bar above the 0.80
# overlap cutoff is the reasoned blind default; the operator may adjust before validation runs.
CLASSIFIER_AGREEMENT_BAR: float = 0.85

_NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def _norm(s: Any) -> str:
    """Trimmed, collapsed-ws, lower-cased (the comparison normal form)."""
    return " ".join(str(s or "").split()).strip().lower()


def _num(s: str) -> float:
    return float(s.replace(",", ""))


# ── §4 leg 1: named_entities overlap (fully deterministic) ──────────────────────────────────────

def _entity_match_tokens(entity: dict[str, Any], edgar_names: dict[str, str] | None) -> set[str]:
    """The match tokens for one named_entity: canonical / ticker / name / aliases, ∪ the EDGAR
    company name for the ticker (when an ``edgar_names`` map {TICKER: name} is supplied — §4 leg 1)."""
    toks: set[str] = set()
    for f in ("canonical", "ticker", "name"):
        v = entity.get(f)
        if v:
            toks.add(_norm(v))
    for a in entity.get("aliases") or []:
        if a:
            toks.add(_norm(a))
    tkr = str(entity.get("ticker") or "").strip().upper()
    if edgar_names and tkr and tkr in edgar_names:
        toks.add(_norm(edgar_names[tkr]))
    return {t for t in toks if t}


def _token_in_text(token: str, text_norm: str) -> bool:
    """Token presence in the normalized description: a short all-alnum token (a ticker/acronym, e.g.
    'BA') matches on a WORD BOUNDARY (so it does not fire inside 'backlog'); a longer name/alias is a
    substring match."""
    if len(token) <= 5 and token.replace(".", "").isalnum():
        return re.search(rf"\b{re.escape(token)}\b", text_norm) is not None
    return token in text_norm


def entity_overlap(description: str, named_entities: list[dict[str, Any]] | None, *,
                   edgar_names: dict[str, str] | None = None) -> float:
    """§4 leg 1: fraction of the claim's named_entities surfaced in the description (deterministic).

    An entity is surfaced iff ANY of its match tokens appears in the description. Empty
    named_entities → 0.0 (an absent field is NOT high-overlap, §5)."""
    ents = named_entities or []
    if not ents:
        return 0.0
    tn = _norm(description)
    hit = sum(1 for e in ents
              if any(_token_in_text(t, tn) for t in _entity_match_tokens(e, edgar_names)))
    return hit / len(ents)


# ── §4 leg 3: headline_quantities overlap (fully deterministic, 5-family unit-aware) ─────────────

_DUR_ORDER = BUCKET_FAMILIES["dur_"]   # weeks_lt10 < weeks_10_50 < weeks_50plus < months_12_36 < years_3plus
_X_ORDER = BUCKET_FAMILIES["x_"]       # x_lt2 < x_2plus < x_5plus < x_10plus

_USD_SCALE = {"trillion": 1e12, "tn": 1e12, "t": 1e12,
              "billion": 1e9, "bn": 1e9, "b": 1e9,
              "million": 1e6, "mm": 1e6, "m": 1e6,
              "thousand": 1e3, "k": 1e3}
_WEEKS_PER = {"week": 1.0, "weeks": 1.0, "wk": 1.0, "wks": 1.0,
              "month": 4.345, "months": 4.345, "mo": 4.345,
              "year": 52.18, "years": 52.18, "yr": 52.18, "yrs": 52.18}


def _dur_bucket(weeks: float) -> str:
    """A duration (in canonical WEEKS) → its dur_ family bucket (ordered ladder; ±1 smooths bounds)."""
    w = abs(weeks)
    if w < 10:
        return "dur_weeks_lt10"
    if w < 50:
        return "dur_weeks_10_50"
    if w < 52:
        return "dur_weeks_50plus"
    if w < 156:                 # ~12–36 months
        return "dur_months_12_36"
    return "dur_years_3plus"


def _x_bucket(mult: float) -> str:
    m = abs(mult)
    if m < 2:
        return "x_lt2"
    if m < 5:
        return "x_2plus"
    if m < 10:
        return "x_5plus"
    return "x_10plus"


def _description_buckets(description: str, family: str) -> set[str]:
    """The set of ``family`` buckets the description's parsed magnitudes fall into (unit-aware).

    Each family extracts its own candidate magnitudes from free text, then classifies:
      pct_ → number before %/percent;  usd_ → $-amount with B/M/K scale;  cnt_ → bare number;
      dur_ → number + week/month/year (→ canonical weeks);  x_ → number + x/fold/times (the multiplier).
    Returns the buckets so the claim's stated bucket can be tested within ±1 (same-OOM, §4)."""
    text = _norm(description)
    out: set[str] = set()
    if family in ("pct_", "usd_", "cnt_"):
        if family == "pct_":
            for m in re.finditer(rf"({_NUM.pattern})\s*(?:%|percent|pct\b)", text):
                b = _value_bucket(_num(m.group(1)), "pct_")
                if b:
                    out.add(b)
        elif family == "usd_":
            for m in re.finditer(rf"\$?\s*({_NUM.pattern})\s*(trillion|billion|million|thousand|tn|bn|mm|[tbmk])\b",
                                 text):
                out_b = _value_bucket(_num(m.group(1)) * _USD_SCALE.get(m.group(2), 1.0), "usd_")
                if out_b:
                    out.add(out_b)
        else:  # cnt_ — bare number magnitudes (the metric carries the unit; least-precise family)
            for m in _NUM.finditer(text):
                b = _value_bucket(_num(m.group()), "cnt_")
                if b:
                    out.add(b)
    elif family == "dur_":
        for m in re.finditer(rf"({_NUM.pattern})\s*(weeks?|wks?|months?|mo|years?|yrs?)\b", text):
            out.add(_dur_bucket(_num(m.group(1)) * _WEEKS_PER.get(m.group(2), 1.0)))
    elif family == "x_":
        for m in re.finditer(rf"({_NUM.pattern})\s*(?:x\b|-?fold\b|times\b)", text):
            out.add(_x_bucket(_num(m.group(1))))
    return out


def _within_one(claim_bucket: str, desc_bucket: str, order: tuple[str, ...]) -> bool:
    try:
        return abs(order.index(claim_bucket) - order.index(desc_bucket)) <= 1
    except ValueError:
        return False


def _quantity_recovered(q: dict[str, Any], description: str) -> bool:
    """True iff the description recovers this headline_quantity within ±1 bucket in its family."""
    bucket = str((q or {}).get("bucket", "")).strip()
    fam = _family_of(bucket)
    if fam is None:
        return False
    order = BUCKET_FAMILIES[fam]
    return any(_within_one(bucket, db, order) for db in _description_buckets(description, fam))


def quantity_overlap(description: str, headline_quantities: list[dict[str, Any]] | None) -> float:
    """§4 leg 3: fraction of the claim's headline_quantities recovered in the description.

    Empty headline_quantities → 0.0 (the §5 load-bearing case: an absent quantity field is NOT
    high-overlap, so the conjunction is unsatisfiable and the claim PASSES — never rejected on a
    structural, quantity-less mechanism)."""
    qs = headline_quantities or []
    if not qs:
        return 0.0
    hit = sum(1 for q in qs if _quantity_recovered(q, description))
    return hit / len(qs)


# ── per-model "clears all three" + the reject RULE (§5) ──────────────────────────────────────────

@dataclass(frozen=True)
class ModelScore:
    """One deploy-roster model's overlap scores for a claim (the LLM layer fills these)."""

    model: str
    entity_overlap: float
    quantity_overlap: float
    direction_match: bool          # the ring-fenced classifier's (vocab,sign) == the claim's (§4 leg 2)
    # diagnostics
    description: str = ""

    def clears_all_three(self) -> bool:
        """§5: high-overlap on ALL THREE simultaneously. List fields use the 0.80 cutoff; direction
        is a single (vocab,sign) so 'high-overlap' = EXACT match. An empty field scores 0.0 < 0.80 →
        NOT high → cannot clear (the empty-field-passes rule falls out by construction)."""
        return (self.entity_overlap >= HIGH_OVERLAP_CUTOFF
                and self.quantity_overlap >= HIGH_OVERLAP_CUTOFF
                and self.direction_match)


@dataclass(frozen=True)
class ProbeVerdict:
    """The §5 verdict for one claim: REJECTED (narrated) iff ≥2 roster models clear all-three."""

    claim_id: str
    rejected: bool
    n_concur: int                  # how many models cleared all-three
    scores: list[ModelScore] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.rejected


def probe_claim(claim: dict[str, Any], scores: list[ModelScore]) -> ProbeVerdict:
    """Apply the §5 RULE to one claim given the per-model scores: REJECT iff ≥CONCUR_MIN models each
    clear all-three-high. Permissive by construction — an empty field (entity/quantity 0.0) or a
    direction miss makes a model fail to clear, so a quantity-less structural claim never reaches the
    concurrence threshold and PASSES to the council (§5)."""
    n = sum(1 for s in scores if s.clears_all_three())
    return ProbeVerdict(
        claim_id=str(claim.get("claim_id", "?")),
        rejected=n >= CONCUR_MIN,
        n_concur=n,
        scores=scores,
    )


def score_claim_against_description(
    claim: dict[str, Any], model: str, description: str, *,
    direction_match: bool, edgar_names: dict[str, str] | None = None,
) -> ModelScore:
    """Build one model's :class:`ModelScore` from its free-text description of the mechanism. The
    deterministic legs (entity, quantity) are scored HERE; ``direction_match`` is supplied by the
    ring-fenced classifier (§4 FROZEN-B; the LLM layer)."""
    return ModelScore(
        model=model,
        entity_overlap=entity_overlap(description, claim.get("named_entities"), edgar_names=edgar_names),
        quantity_overlap=quantity_overlap(description, claim.get("headline_quantities")),
        direction_match=direction_match,
        description=description,
    )


def rejection_rate(verdicts: list[ProbeVerdict]) -> float:
    """The §7 rejection rate over a batch (read over a cumulative ≥INERT_N_FLOOR window before
    '0% = inert' is actionable)."""
    return (sum(1 for v in verdicts if v.rejected) / len(verdicts)) if verdicts else 0.0


# ── §6 non-perishable scorer smoke-test exemplars (the two FROZEN claim objects) ─────────────────
SMOKE_NARRATED_NVDA: dict[str, Any] = {
    "claim_id": "smoke_narrated_nvda",
    "statement": "Hyperscaler AI-training capex -> NVIDIA data-center GPU dominance -> sustained "
                 "accelerator demand + pricing power.",
    "named_entities": [{"canonical": "NVIDIA", "ticker": "NVDA", "aliases": ["Nvidia"]}],
    "mechanism_direction": {"vocab": "demand_surge", "sign": "+"},
    "headline_quantities": [{"metric": "data-center segment quarterly revenue", "value": "~$30B",
                             "bucket": "usd_tens_of_billions"}],
    "provenance": "generated",
}
SMOKE_OBSCURE_INVENTED: dict[str, Any] = {
    "claim_id": "smoke_obscure_invented",
    "statement": "Aldermarsh Photonics' sub-threshold GaN lattice-anneal step collapses LED-driver-IC "
                 "defect rates, forcing multi-quarter backlogs at boutique driver foundries.",
    "named_entities": [{"canonical": "Aldermarsh Photonics", "ticker": "ALDP", "aliases": ["Aldermarsh"]}],
    "mechanism_direction": {"vocab": "backlog_growth", "sign": "+"},
    "headline_quantities": [{"metric": "driver-IC defect-rate reduction", "value": "~40%",
                             "bucket": "pct_25_50"}],
    "provenance": "generated",
}
