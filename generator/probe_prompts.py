"""Stage-2 probe prompts — the DESCRIBER + the ring-fenced mechanism_direction CLASSIFIER.

``PREREG_NARRATION_PROBE §4`` (FROZEN-B: free-text elicitation + a ring-fenced controlled-vocab
classifier). Both are **freeze-grade / record-segmenting** (they shape the probe's forward output), so
they are byte-pinned by ``tests/test_generator_probe_llm.py`` (the CGS §10.7 / SYNTHESIS_SYSTEM
discipline) — a drifted byte is unshippable without re-pinning the sha.

- **DESCRIBER** (the deploy roster, narration-maximal): given a mechanism with the specific companies
  and figures REDACTED, it RECALLS the specifics from training only (no documents). Recall of the
  redacted specifics IS the narration signal — a narrated theme is recoverable, a quiet one is not.
- **CLASSIFIER** (ring-fenced, controlled-vocab, ≥2-vendor): maps a description's prose → (vocab, sign)
  from the frozen enum; it NEVER sees the claim, only the description (decorrelation). Its label is the
  §4 direction leg; its reliability is validated to the blind §4 agreement bar pre-DEPLOY (not here).
"""

from __future__ import annotations

from generator.prompts import MECHANISM_VOCAB

_VOCAB_LIST = ", ".join(MECHANISM_VOCAB)

# The describer is asked for prose (2–5 sentences). The deterministic legs then check whether the
# claim's real entities / quantities appear in that prose (§4 legs 1 & 3); the classifier reads the
# prose for the direction leg. Worded to FORBID padding/invention so a quiet theme reads low, not
# confabulated-high (the false-narrated direction is invisible, §2 — so we bias the describer honest).
DESCRIBER_SYSTEM = (
    "You are a market-knowledge RECALL probe. You will be given a secular market MECHANISM with the "
    "specific companies and figures REDACTED (shown as [COMPANY] and [FIGURE]). Using ONLY your own "
    "training knowledge — no documents, no browsing — identify what this specific mechanism most "
    "likely refers to:\n"
    "1. the specific publicly-traded COMPANIES it points to (give the company name AND its ticker);\n"
    "2. the specific headline QUANTITIES involved (lead times in weeks, dollar amounts, percentages, "
    "multiples like \"2x\", or counts like reactors / GW);\n"
    "3. the mechanism's DIRECTION in one phrase.\n"
    "Be concrete and name real tickers and real numbers — but ONLY if you genuinely know them for THIS "
    "specific mechanism. If you do not know the specific companies or figures, say so plainly; do NOT "
    "invent, pad, or guess. Reply in plain prose, 2 to 5 sentences."
)

CLASSIFIER_SYSTEM = (
    "You label a market-mechanism description with its DIRECTION. Read the description and reply with "
    "ONE JSON object: {\"vocab\": <one term>, \"sign\": \"+\" or \"-\"}. Choose the single best-fitting "
    f"vocab term from EXACTLY this set: {_VOCAB_LIST}. The sign is \"+\" if the mechanism is "
    "increasing / tightening / growing, \"-\" if decreasing / loosening / easing. Reply with the JSON "
    "object and nothing else."
)


def describer_user(redacted_statement: str, entity_class: str = "") -> str:
    """The describer USER message: the redacted mechanism (+ the sector/entity class, which is NOT a
    specific name, so it is kept to orient the recall to the right domain)."""
    block = f"Mechanism (specific companies and figures redacted): {redacted_statement}"
    if entity_class:
        block += f"\nSector / entity class: {entity_class}"
    return block
