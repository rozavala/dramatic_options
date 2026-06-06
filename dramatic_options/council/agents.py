"""Council agent prompts + strict parsers (T2) — Proposer / Adversary / Strategist.

**Direction-relative roles** (the book is two-sided — `structure.py: DIRECTION_KIND =
{"bullish":"C","bearish":"P"}`): the **Proposer** argues *for* the candidate's stated direction;
the **Adversary** (Devil's Advocate) argues *against the proposed direction, whichever it is* —
the bull case on a bearish candidate. A hard-named "bear" would invert on the short side and
reintroduce the directional anchoring bias that symmetric Permabull/Permabear exists to kill.
The **Strategist** synthesizes both into a verdict + a conviction in the strict vocabulary.

Each agent returns a single JSON object; parsers are defensive (extract the first ``{...}`` even
if the model fences it or adds prose) and coerce confidence to the strict vocabulary. A parse
failure resolves to NEUTRAL (fail-closed — the candidate is dropped, never traded).
"""

from __future__ import annotations

import json

from dramatic_options.council.proposal import normalize_conviction

OPPOSITE = {"bullish": "bearish", "bearish": "bullish"}

_COMMON = (
    "You are part of a disciplined options council that trades long-dated, far-OTM, defined-risk "
    "convexity on secular themes ONLY when implied vol has not yet priced the move. You PROPOSE; a "
    "deterministic IV/cheap-convexity gate DISPOSES and can veto you. Reason only from the EVIDENCE "
    "provided. If the evidence lacks numeric content, return NEUTRAL rather than inventing facts. "
    "Use confidence strictly from {LOW, MODERATE, HIGH, EXTREME, NEUTRAL}. Reply with ONE JSON "
    "object and nothing else."
)

PROPOSER_SYSTEM = (
    _COMMON + " ROLE: Inflection Analyst. Argue FOR the candidate's stated direction: is this theme "
    "at a real inflection the market hasn't narrated, is it structural (not a fad), and is this the "
    "cleanest single-name expression? JSON keys: theme, symbol, direction, structural_vs_fad "
    "('structural'|'fad'|'unclear'), inflection_thesis (string, cite evidence), confidence, "
    "cited (array of short evidence strings you relied on)."
)

ADVERSARY_SYSTEM = (
    _COMMON + " ROLE: Devil's Advocate. You argue AGAINST the proposed direction — make the strongest "
    "honest case that the proposed trade is wrong (already consensus/priced, a fad, or the move is "
    "behind it). JSON keys: counter_case (string, cite evidence), weakest_point (the single biggest "
    "hole in the proposal), is_fad (bool), already_consensus (bool), confidence (your confidence in "
    "the COUNTER case), cited (array)."
)

STRATEGIST_SYSTEM = (
    _COMMON + " ROLE: Master Strategist. Weigh the FOR case against the AGAINST case and decide whether "
    "to propose this trade to the deterministic gates. Be a conviction dampener at extremes. JSON keys: "
    "include (bool), theme, symbol, direction ('bullish'|'bearish'), conviction, structural_vs_fad, "
    "weakest_point, summary (one or two sentences; this becomes the trade thesis)."
)


def extract_json(text: str) -> dict:
    """Pull the first balanced JSON object out of an LLM response. Raises ValueError on failure."""
    if not text:
        raise ValueError("empty response")
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object found")
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[start : i + 1])
    raise ValueError("unbalanced JSON object")


# ── Prompt builders ─────────────────────────────────────────────────────────────────────────


def proposer_prompt(pack) -> tuple[str, str]:
    return PROPOSER_SYSTEM, pack.as_prompt_block()


def adversary_prompt(pack, proposer_raw: dict) -> tuple[str, str]:
    against = OPPOSITE.get(pack.direction, "the opposite")
    user = (
        f"{pack.as_prompt_block()}\n\n"
        f"The Inflection Analyst proposed a {pack.direction} trade with this thesis:\n"
        f"  {proposer_raw.get('inflection_thesis', '(none)')}\n\n"
        f"Make the strongest case AGAINST a {pack.direction} position in {pack.symbol} "
        f"(i.e. the {against} case)."
    )
    return ADVERSARY_SYSTEM, user


def strategist_prompt(pack, proposer_raw: dict, adversary_raw: dict, *, for_first: bool = True) -> tuple[str, str]:
    for_block = (
        "FOR the proposed direction (Inflection Analyst):\n"
        f"  thesis: {proposer_raw.get('inflection_thesis', '(none)')}\n"
        f"  structural_vs_fad: {proposer_raw.get('structural_vs_fad', '?')}\n"
        f"  confidence: {proposer_raw.get('confidence', '?')}"
    )
    against_block = (
        "AGAINST the proposed direction (Devil's Advocate):\n"
        f"  counter_case: {adversary_raw.get('counter_case', '(none)')}\n"
        f"  weakest_point: {adversary_raw.get('weakest_point', '?')}\n"
        f"  already_consensus: {adversary_raw.get('already_consensus', '?')}, "
        f"is_fad: {adversary_raw.get('is_fad', '?')}\n"
        f"  confidence: {adversary_raw.get('confidence', '?')}"
    )
    # Randomized presentation order (position-bias guard) — order is recorded in the rationale.
    first, second = (for_block, against_block) if for_first else (against_block, for_block)
    user = f"{pack.as_prompt_block()}\n\n{first}\n\n{second}\n\nDecide."
    return STRATEGIST_SYSTEM, user


# ── Parsers (defensive; coerce to strict vocabulary; NEUTRAL on failure) ─────────────────────
#
# Two failure surfaces, both → NEUTRAL fail-closed:
#   1. extract_json RAISES (no/unbalanced JSON — the #37 thinking-starvation truncation).
#   2. Valid JSON of the WRONG SHAPE ({}, partial, truncated-but-balanced) — once response_mime_type
#      forces parseable JSON this becomes the dominant mode; without a key check it silently coerces
#      to NEUTRAL (the bug in a new costume). So we validate required keys per role.
# A genuine NEUTRAL abstention is allowed to be minimal; only a NON-NEUTRAL claim must carry its
# structure. Required key sets are DERIVED from the prompt templates above (kept in lock-step by a
# test that asserts FakeRouter's per-role output satisfies them).

RAW_TEXT_MAX = 2000  # how much of a failed model response to persist for forensics
_PROPOSER_CLAIM_KEYS = ("structural_vs_fad", "inflection_thesis")
_ADVERSARY_CLAIM_KEYS = ("counter_case",)


def parse_error_fallback(text: str, *, reason: str, finish_reason=None, thoughts_tokens=None, **extra) -> dict:
    """Fail-closed fallback that PRESERVES the evidence: the raw text + why it failed + the provider
    finish_reason / thinking-token count. (The empty-text case has raw_text='' → finish_reason is the
    only diagnostic, which is exactly why it's captured.) Flows to ``council_agent_outputs.raw``."""
    d = {"confidence": "NEUTRAL", "parse_error": True, "raw_text": (text or "")[:RAW_TEXT_MAX],
         "validation_error": reason, "finish_reason": finish_reason, "thoughts_tokens": thoughts_tokens}
    d.update(extra)
    return d


def parse_proposer(text: str, *, finish_reason=None, thoughts_tokens=None) -> dict:
    try:
        d = extract_json(text)
    except (ValueError, json.JSONDecodeError) as e:
        return parse_error_fallback(text, reason=f"extract_json: {e}", finish_reason=finish_reason, thoughts_tokens=thoughts_tokens)
    if "confidence" not in d:
        return parse_error_fallback(text, reason="missing 'confidence'", finish_reason=finish_reason, thoughts_tokens=thoughts_tokens)
    conf = normalize_conviction(d.get("confidence"))
    if conf != "NEUTRAL":
        missing = [k for k in _PROPOSER_CLAIM_KEYS if not d.get(k)]
        if missing:
            return parse_error_fallback(text, reason=f"non-NEUTRAL proposer missing {missing}",
                                        finish_reason=finish_reason, thoughts_tokens=thoughts_tokens)
    d["confidence"] = conf
    return d


def parse_adversary(text: str, *, finish_reason=None, thoughts_tokens=None) -> dict:
    try:
        d = extract_json(text)
    except (ValueError, json.JSONDecodeError) as e:
        return parse_error_fallback(text, reason=f"extract_json: {e}", finish_reason=finish_reason, thoughts_tokens=thoughts_tokens)
    if "confidence" not in d:
        return parse_error_fallback(text, reason="missing 'confidence'", finish_reason=finish_reason, thoughts_tokens=thoughts_tokens)
    conf = normalize_conviction(d.get("confidence"))
    if conf != "NEUTRAL":
        missing = [k for k in _ADVERSARY_CLAIM_KEYS if not d.get(k)]
        if missing:
            return parse_error_fallback(text, reason=f"non-NEUTRAL adversary missing {missing}",
                                        finish_reason=finish_reason, thoughts_tokens=thoughts_tokens)
    d["confidence"] = conf
    return d


def parse_strategist(text: str, *, finish_reason=None, thoughts_tokens=None) -> dict:
    try:
        d = extract_json(text)
    except (ValueError, json.JSONDecodeError) as e:
        return parse_error_fallback(text, reason=f"extract_json: {e}", include=False, conviction="NEUTRAL",
                                    finish_reason=finish_reason, thoughts_tokens=thoughts_tokens)
    if "conviction" not in d:
        return parse_error_fallback(text, reason="missing 'conviction'", include=False, conviction="NEUTRAL",
                                    finish_reason=finish_reason, thoughts_tokens=thoughts_tokens)
    d["conviction"] = normalize_conviction(d.get("conviction"))
    d["include"] = bool(d.get("include", False))
    if d["include"] and d["conviction"] != "NEUTRAL" and not d.get("summary"):
        return parse_error_fallback(text, reason="strategist include without summary", include=False,
                                    conviction="NEUTRAL", finish_reason=finish_reason, thoughts_tokens=thoughts_tokens)
    return d
