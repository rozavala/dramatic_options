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
import logging

from council.proposal import normalize_conviction

log = logging.getLogger(__name__)

OPPOSITE = {"bullish": "bearish", "bearish": "bullish"}

# The three council strings below are the CGS §10.7 FROZEN config (sha256/16-pinned; see
# tests/test_council_prompts.py — the run-of-record is records/2026-06-10_retightened_rescore.txt).
# Thesis-only: cheapness judgment belongs SOLELY to the deterministic IV gate. Do not edit these
# without a new pre-registered freeze.
_COMMON = (
    "You are part of a disciplined options council that trades long-dated, far-OTM, defined-risk "
    "convexity on secular themes. You PROPOSE on THESIS ONLY; a deterministic IV/cheap-convexity "
    "gate DISPOSES on cheapness and can veto you — never judge whether vol or optionality is cheap "
    "or priced. A theme qualifies ONLY if ALL THREE hold: (1) STRUCTURAL — a real, durable driver, "
    "not a fad; (2) UNDER-NARRATED — not already the market's consensus story; a name at the center "
    "of a dominant, widely-covered narrative does not qualify however correct the thesis; (3) AT A "
    "GENUINE INFLECTION — the change is happening NOW: if the large move has already happened, the "
    "inflection is BEHIND the name and it does not qualify unless the evidence shows a NEW, distinct "
    "inflection. Reason only from the EVIDENCE provided. If the evidence lacks numeric content, "
    "return NEUTRAL rather than inventing facts. Use confidence strictly from {LOW, MODERATE, HIGH, "
    "EXTREME, NEUTRAL}. Reply with ONE JSON object and nothing else."
)

PROPOSER_SYSTEM = (
    _COMMON + " ROLE: Inflection Analyst. Argue FOR the candidate's stated direction: is this theme "
    "at a real inflection the market hasn't narrated, is it structural (not a fad), and is this the "
    "cleanest single-name expression? JSON keys: theme, symbol, direction, structural_vs_fad "
    "('structural'|'fad'|'unclear'), inflection_thesis (string, cite evidence), confidence, "
    "cited (array of short evidence strings you relied on)."
)

ADVERSARY_SYSTEM = (
    _COMMON +
    " ROLE: Devil's Advocate. You argue AGAINST the proposed direction — make the strongest honest "
    "case ON THESIS GROUNDS that the proposed trade is wrong: already consensus (the story is widely "
    "told), a fad (not structural), or not a genuine inflection (the move already happened / no "
    "fresh change). Never argue from option pricing or volatility — cheapness is the deterministic "
    "gate's job. JSON keys: counter_case (string, cite evidence), weakest_point (the single biggest "
    "hole in the proposal), is_fad (bool), already_consensus (bool), inflection_passed (bool — true "
    "if the move is behind the name), confidence (your confidence in the COUNTER case), cited "
    "(array)."
)

STRATEGIST_SYSTEM = (
    _COMMON +
    " ROLE: Master Strategist. Weigh the FOR case against the AGAINST case and decide whether to "
    "propose this trade to the deterministic gates. Be a conviction dampener at extremes. The three "
    "criteria are HARD: you may set include=true ONLY if structural_vs_fad='structural' AND "
    "under_narrated=true AND at_inflection=true — each asserted on the evidence, not by default. "
    "JSON keys: include (bool), theme, symbol, direction ('bullish'|'bearish'), conviction, "
    "structural_vs_fad, under_narrated (bool), at_inflection (bool), weakest_point, summary (one or "
    "two sentences; this becomes the trade thesis)."
)


def extract_json(text: str) -> dict:
    """Pull the first balanced JSON object out of an LLM response. Raises ValueError on failure.

    Two bounded repairs are attempted on a damaged response, then it fails closed:
    ``_strip_invalid_quote_escapes`` — the gemini JSON-mode invalid ``\\'`` escape observed
    live 2026-07-20 (run #612: ``Nvidia\\'s`` at a natural STOP; ``\\'`` is never valid JSON) —
    and ``_repair_tail`` — the tail-mangling family observed live 2026-07-07/09 (runs
    #458/#491: a natural STOP with the final ``}`` dropped, or a stray duplicate ``]``).
    A repaired object still passes through the caller's post-parse schema validation, so a bad
    repair fails closed exactly like a parse failure."""
    if not text:
        raise ValueError("empty response")
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object found")
    try:
        return _balanced_parse(text, start)
    except ValueError as err:  # json.JSONDecodeError subclasses ValueError
        fixed, n_esc = _strip_invalid_quote_escapes(text, start)
        if n_esc:
            try:
                obj = _balanced_parse(fixed, start)
                log.warning("extract_json: \\' escape-repair succeeded (%d fixed; original "
                            "error: %s)", n_esc, err)
                return obj
            except ValueError:
                pass  # escape damage can coexist with tail damage — chain into the tail repair
        try:
            obj = _repair_tail(fixed, start)
        except ValueError:
            raise err from None
        log.warning("extract_json: bracket tail-repair succeeded%s (original error: %s)",
                    f" after {n_esc} \\' escape fix(es)" if n_esc else "", err)
        return obj


def _balanced_parse(text: str, start: int) -> dict:
    """Parse the first balanced JSON object starting at ``start``. Raises ValueError."""
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


def _strip_invalid_quote_escapes(text: str, start: int) -> tuple[str, int]:
    """Drop the backslash from ``\\'`` sequences in escape position inside JSON strings.

    ``\\'`` is never a valid JSON escape, so removing the backslash is always safe — but only
    with real escape-state tracking: a legitimate ``\\\\`` (escaped backslash) followed by a
    plain apostrophe must never be altered, which a naive text replace would corrupt. Only the
    exact backslash+apostrophe pair is touched; every other escape (valid or not) passes
    through untouched for the parser to judge. Returns ``(text, n_fixed)``."""
    out = list(text[:start])
    in_str = False
    pending_backslash = False
    fixed = 0
    for ch in text[start:]:
        if pending_backslash:  # previous char opened an escape inside a string
            pending_backslash = False
            if ch == "'":
                fixed += 1  # emit the apostrophe alone
            else:
                out.append("\\")
            out.append(ch)
            continue
        if in_str:
            if ch == "\\":
                pending_backslash = True
                continue
            if ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        out.append(ch)
    if pending_backslash:  # dangling backslash at end-of-text — keep it for forensics
        out.append("\\")
    return "".join(out), fixed


def _repair_tail(text: str, start: int) -> dict:
    """Bounded structural second chance for a bracket-damaged JSON tail.

    Bracket-level ONLY: characters inside strings are never altered; at most 3 stray closing
    brackets are dropped and at most 4 missing closers appended. Anything beyond that — or a
    result ``json.loads`` still rejects — raises ValueError (the caller re-raises the ORIGINAL
    error, so forensics keep the true signature)."""
    out: list[str] = []
    stack: list[str] = []
    in_str = False
    esc = False
    dropped = 0
    for ch in text[start:]:
        if in_str:
            out.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
        elif ch in "{[":
            stack.append(ch)
            out.append(ch)
        elif ch in "}]":
            if stack and stack[-1] == ("{" if ch == "}" else "["):
                stack.pop()
                out.append(ch)
                if not stack:
                    return json.loads("".join(out))
            else:
                dropped += 1  # stray closer (the doubled-']' shape) — drop it
                if dropped > 3:
                    raise ValueError("unrepairable: too many stray closers")
        else:
            out.append(ch)
    if in_str or not stack or len(stack) > 4:
        raise ValueError("unrepairable: tail damage exceeds the bounded repair")
    out.extend("}" if b == "{" else "]" for b in reversed(stack))
    return json.loads("".join(out))


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
# SANCTIONED exception to the derive-from-prompt rule: the §10.7 adversary prompt adds
# `inflection_passed`, but it is recording-only — NOT claim-required (a bool has no
# missing-content failure mode like counter_case, and no enforcement rule consumes it).
# Do not "fix" it into this tuple; that would add a parse surface with no consumer.
_ADVERSARY_CLAIM_KEYS = ("counter_case",)
# CGS §10.7/§10.9: the strategist's tri-criteria ASSERTIONS. On an include=true ∧ non-NEUTRAL
# row these KEYS must be PRESENT (absent → parse_error: truncation/non-compliance, the #37
# discipline — a provider that stops emitting them must grade DEGRADED, never read as
# "deliberated" vetoes). An explicit null/false value is a deliberated NON-assertion and is
# handled as a criteria-veto downstream (debate.run_candidate / select_for_trade), NOT here.
# structural_vs_fad is deliberately NOT in this tuple: it is shape-required at the PROPOSER
# (_PROPOSER_CLAIM_KEYS) and the strategist-or-proposer fallback in debate.py is sanctioned.
_STRATEGIST_INCLUDE_BOOL_KEYS = ("under_narrated", "at_inflection")


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
    # Shape checks evaluate the model's RAW include claim, shape-first (a tri-fail row that also
    # lacks summary is a parse_error, deterministically) — coercion/criteria evaluation happens
    # downstream where the proposer fallback is in scope (debate.run_candidate).
    if d["include"] and d["conviction"] != "NEUTRAL":
        if not d.get("summary"):
            return parse_error_fallback(text, reason="strategist include without summary", include=False,
                                        conviction="NEUTRAL", finish_reason=finish_reason, thoughts_tokens=thoughts_tokens)
        missing = [k for k in _STRATEGIST_INCLUDE_BOOL_KEYS if k not in d]
        if missing:
            return parse_error_fallback(text, reason=f"strategist include missing tri keys {missing}",
                                        include=False, conviction="NEUTRAL",
                                        finish_reason=finish_reason, thoughts_tokens=thoughts_tokens)
    return d
