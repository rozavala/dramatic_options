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

from council.proposal import normalize_conviction

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


def parse_proposer(text: str) -> dict:
    try:
        d = extract_json(text)
    except (ValueError, json.JSONDecodeError):
        return {"confidence": "NEUTRAL", "parse_error": True}
    d["confidence"] = normalize_conviction(d.get("confidence"))
    return d


def parse_adversary(text: str) -> dict:
    try:
        d = extract_json(text)
    except (ValueError, json.JSONDecodeError):
        return {"confidence": "NEUTRAL", "parse_error": True}
    d["confidence"] = normalize_conviction(d.get("confidence"))
    return d


def parse_strategist(text: str) -> dict:
    try:
        d = extract_json(text)
    except (ValueError, json.JSONDecodeError):
        return {"include": False, "conviction": "NEUTRAL", "parse_error": True}
    d["conviction"] = normalize_conviction(d.get("conviction"))
    d["include"] = bool(d.get("include", False))
    return d
